"""Run the Cube measures' SQL on chDB and compare with the totals recorded in source.yaml.

Cube itself only runs in T16 (Docker). What can be checked here is the ClickHouse
SQL that the model hands to the engine: each cube's `sql`, and each measure's
aggregate expression with its filters. This script compiles every measure the way
Cube does for a plain aggregate (type + sql + filters → one aggregate expression),
runs it over the cube's SQL, and compares the results with the full-table values
that source.yaml states in its notes. Multi-stage measures (time_shift, group_by)
are only planned by Cube, so they are listed as not checked here.

    uv run python render/verify_cube.py      # writes reports/validation/cube_measures.md
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from render.common import REPO  # noqa: E402
from render.cube import build_model  # noqa: E402
from render.measures import AS_OF  # noqa: E402

REPORT = REPO / "reports" / "validation" / "cube_measures.md"
_REF = re.compile(r"\{(\w+)\}")

# (cube.member, WHERE on the cube's rows or "", expected value, relative tolerance, where the number is from)
_Y2009 = "toYear(c.DateKey) = 2009"
_WORKDAY_2009 = "c.DateKey IN (SELECT DateKey FROM retail.DimDate WHERE CalendarYear = 2009 AND IsWorkDay = 'WorkDay')"
EXPECTED = [
    ("online_sales.sales_amount", "", 2718202629.81, 1e-9, "FactOnlineSales.differs_from"),
    ("sales.sales_amount", "", 12413657608.86, 1e-9, "FactSales.SalesAmount"),
    ("online_sales.return_rate", "", 0.007996, 1e-3, "退货率.note"),
    ("sales.return_rate", "", 0.009257, 1e-3, "退货率.note"),
    ("online_sales.order_count", "", 1674320, 0, "订单数.note"),
    ("online_sales.order_line_count", "", 12627608, 0, "FactOnlineSales.rows"),
    ("online_sales.lines_per_order", "", 7.542, 1e-4, "每单行数.note"),
    ("online_sales.average_order_value", "", 1623.4666, 1e-7, "客单价.note"),
    ("online_sales.customer_count", "", 18869, 0, "客户数.note"),
    ("online_sales.active_customer_count", "", 16890, 0, "活跃客户数.note"),
    ("online_sales.at_risk_customer_count", "", 1841, 0, "有流失风险客户数.note"),
    ("online_sales.churned_customer_count", "", 138, 0, "已流失客户数.note"),
    ("sales.store_count", "", 306, 0, "门店数.note"),
    ("sales.average_daily_sales_amount", _WORKDAY_2009, 10260907.86, 1e-9, "日均销售额.note（2009 平日）"),
    ("inventory.current_on_hand_quantity", "", 11897661, 0, "当前在手库存数量.note"),
    ("inventory.current_on_hand_value", "", 1291296461.45, 1e-9, "当前在手库存金额.note"),
    ("inventory.current_on_order_quantity", "", 494285, 0, "当前在订库存数量.note"),
    ("inventory.below_safety_stock_count", "", 89591, 0, "低于安全库存的门店产品数.note"),
    ("inventory.store_product_pair_count", "", 600241, 0, "门店产品组合数.note"),
    ("sales_quota.sales_amount_quota", "", 10667465363.67, 1e-9, "目标销售额.note"),
    ("sales_quota.sales_quantity_quota", "", 44300085, 1e-9, "目标销量.note"),
    ("sales_quota.quota_attainment_pct", _Y2009, 3740483119.18 / 3084785562.03, 1e-9, "目标达成率.note（2009）"),
    ("strategy_plan.plan_revenue", "", 11548720849.89, 1e-9, "计划收入.note"),
    ("it_machine.it_cost", "", 240765805, 1e-9, "IT 成本.note"),
    ("it_sla.down_time", "", 396699, 1e-9, "停机时长.note"),
    ("it_sla.outage_count", "", 4925, 0, "故障次数.note"),
]

# Plain aggregates that must equal the same aggregate on the source table: they
# check that the UNION ALL cubes do not leak the extra rows into a measure.
CROSS_CHECKS = [
    ("inventory.snapshot_on_hand_quantity", "SELECT sum(OnHandQuantity) FROM retail.FactInventory"),
    ("inventory.snapshot_on_hand_value", "SELECT sum(OnHandQuantity * UnitCost) FROM retail.FactInventory"),
    ("inventory.snapshot_below_safety_stock_count",
     "SELECT countIf(OnHandQuantity < SafetyStockQuantity) FROM retail.FactInventory"),
    ("sales_quota.gross_margin_quota",
     "SELECT sum(GrossMarginQuota) FROM retail.FactSalesQuota WHERE ScenarioKey = "
     "(SELECT ScenarioKey FROM retail.DimScenario WHERE ScenarioName = 'Budget')"),
    ("inventory.inventory_turnover",
     "SELECT (SELECT sum(TotalCost) FROM retail.FactSales) / "
     "(SELECT sum(OnHandQuantity * UnitCost) / uniqExact(DateKey) FROM retail.FactInventory)"),
    ("sales.same_store_sales_amount",
     "SELECT sum(SalesAmount) FROM retail.FactSales AS f WHERE (StoreKey, toYear(DateKey) - 1) IN "
     "(SELECT DISTINCT StoreKey, toYear(DateKey) FROM retail.FactSales)"),
    ("sales.same_store_sales_as_base_year",          # semantic-v1.4 variant: this year and the next
     "SELECT sum(SalesAmount) FROM retail.FactSales AS f WHERE (StoreKey, toYear(DateKey) + 1) IN "
     "(SELECT DISTINCT StoreKey, toYear(DateKey) FROM retail.FactSales)"),
    ("sales_quota.sales_amount_quota_by_scenario",     # semantic-v1.4 variant: every scenario, the query filters
     "SELECT sum(SalesAmountQuota) FROM retail.FactSalesQuota"),
    ("online_sales.new_customer_count",
     "SELECT uniqExactIf(CustomerKey, first >= toDate('2009-12-31') - 89) FROM "
     "(SELECT CustomerKey, min(DateKey) AS first FROM retail.FactOnlineSales GROUP BY CustomerKey)"),
]


def compile_measure(cube: dict, name: str) -> str:
    measures = {m["name"]: m for m in cube.get("measures", [])}
    dims = {d["name"]: d for d in cube["dimensions"]}

    def expr(sql: str) -> str:
        def sub(m: re.Match) -> str:
            ref = m.group(1)
            if ref == "CUBE":
                return "c"
            if ref in measures:
                return f"({agg(measures[ref])})"
            return dims[ref]["sql"].replace("{CUBE}", "c")
        return _REF.sub(sub, sql)

    def agg(m: dict) -> str:
        if m.get("multi_stage"):
            raise NotImplementedError("multi_stage")
        conds = [f"({expr(f['sql'])})" for f in m.get("filters", [])]
        if m.get("rolling_window"):
            # Cube plans rolling windows per period; here the one period is the whole data, which ends on
            # the as-of date, so the trailing window is (as-of − N days, as-of].
            n, unit = m["rolling_window"]["trailing"].split()
            if unit != "day" or m["rolling_window"].get("offset", "end") != "end":
                raise NotImplementedError("rolling_window other than trailing N day / end")
            conds.append(f"(c.DateKey > toDate('{AS_OF}') - {int(n)})")
        cond = " AND ".join(conds)
        t = m["type"]
        if t == "number":
            return expr(m["sql"])
        if t == "count":
            return f"countIf({cond})" if cond else "count()"
        fn = {"sum": "sum", "count_distinct": "uniqExact", "avg": "avg", "min": "min", "max": "max"}[t]
        x = expr(m["sql"])
        return f"{fn}If({x}, {cond})" if cond else f"{fn}({x})"

    return agg(measures[name])


def from_clause(cube: dict) -> str:
    return f"({cube['sql']}) AS c" if "sql" in cube else f"{cube['sql_table']} AS c"


def main() -> None:
    from chdb import session

    model = build_model()
    sess = session.Session(str(Path(os.environ["SEMDEBT_DATA_DIR"]).expanduser() / "chdb"))

    def scalar(sql: str) -> float:
        out = sess.query(sql, "TSV").bytes().decode().strip()
        return float(out) if out not in ("", "\\N", "nan") else float("nan")

    lines = ["# Cube 指标的 SQL 在 chDB 上的核对（T10）", "",
             "由 `uv run python render/verify_cube.py` 生成。Cube 本身在 T16 才跑；这里核对的是模型交给引擎的",
             "ClickHouse SQL：每个 cube 的 `sql` 与每个指标的聚合表达式（含 filters），按 Cube 对普通聚合的编法",
             "拼成一条查询在 chDB 上执行。", ""]
    failures = []
    try:
        lines += ["## 一、与 source.yaml 记录的全量值比对", "",
                  "| 指标 | 条件 | 期望 | 实际 | 相对误差 | 出处 | 结果 |", "|---|---|---|---|---|---|---|"]
        for member, where, expected, tol, origin in EXPECTED:
            cube_name, name = member.split(".")
            cube = model[cube_name]
            sql = f"SELECT {compile_measure(cube, name)} FROM {from_clause(cube)}" + (f" WHERE {where}" if where else "")
            got = scalar(sql)
            rel = abs(got - expected) / abs(expected) if expected else abs(got)
            ok = rel <= tol if tol else got == expected
            if not ok:
                failures.append(member)
            lines.append(f"| `{member}` | {'2009' if where == _Y2009 else ('2009 平日' if where else '全量')} | "
                         f"{expected:,.6g} | {got:,.6g} | {rel:.2e} | {origin} | {'通过' if ok else '**不通过**'} |")
        lines += ["", "## 二、与源表上同一口径的直接查询比对", "",
                  "这几项检查 UNION ALL 拼出来的 cube（库存、销售目标）没有让额外的行混进指标，以及同店、新客的写法。", "",
                  "| 指标 | 直接查询 | 实际 | 期望 | 结果 |", "|---|---|---|---|---|"]
        for member, direct in CROSS_CHECKS:
            cube_name, name = member.split(".")
            cube = model[cube_name]
            got = scalar(f"SELECT {compile_measure(cube, name)} FROM {from_clause(cube)}")
            exp = scalar(direct)
            ok = abs(got - exp) <= 1e-9 * max(1.0, abs(exp))
            if not ok:
                failures.append(member)
            lines.append(f"| `{member}` | `{direct}` | {got:,.10g} | {exp:,.10g} | {'通过' if ok else '**不通过**'} |")

        lines += ["", "## 三、全部指标能否执行", "", "每个非多阶段指标都编译成一条全量查询执行一次，不报错即通过。", ""]
        not_checked, errors, ran = [], [], 0
        for cube_name, cube in model.items():
            for m in cube.get("measures", []):
                if m.get("multi_stage"):
                    not_checked.append(f"{cube_name}.{m['name']}")
                    continue
                try:
                    scalar(f"SELECT {compile_measure(cube, m['name'])} FROM {from_clause(cube)}")
                    ran += 1
                except Exception as e:  # noqa: BLE001 - the report records the engine's message
                    errors.append(f"{cube_name}.{m['name']}: {str(e).splitlines()[0][:200]}")
        failures += errors
        lines.append(f"执行 {ran} 个，报错 {len(errors)} 个。")
        lines += [f"- 报错：`{e}`" for e in errors]
        lines += ["", f"多阶段指标（time_shift / group_by，由 Cube 规划，这里不核对，留给 T16）：{len(not_checked)} 个", ""]
        lines += [f"- `{x}`" for x in not_checked]
    finally:
        sess.close()

    lines += ["", f"**结论：{'全部通过' if not failures else '有 ' + str(len(failures)) + ' 项不通过：' + '、'.join(failures)}**", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"写入 {REPORT.relative_to(REPO)}；不通过 {len(failures)} 项")
    if failures:
        print("\n".join(failures))
        sys.exit(1)


if __name__ == "__main__":
    main()
