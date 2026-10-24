"""DAX probe (T17): check the Power BI model open in Desktop without calling any model.

Three subcommands:

    uv run python harness/dax_probe.py expected        # Mac: the reference numbers, from chDB
    uv run python harness/dax_probe.py prepare         # Windows: verify the bundle, make the working PBIPs
    uv run python harness/dax_probe.py probe --tier L1 # Windows: connect, run every check, plain-text report

``expected`` computes, with chDB reading ``$SEMDEBT_DATA_DIR/parquet/*.parquet`` directly (the very
files Power BI imports; no chDB data directory is opened, so it cannot collide with another run,
hard rule 9), the numbers each check must reproduce, and writes
``reports/validation/dax_probe_expected.json`` (committed). The DAX of each check is written per
tier with that model's names (L0 names at L0).

Checks (relative difference at most 0.5 %, task card T17 §做法 2):

- ``rows``      every table's row count (all tiers);
- ``sums``      sums and distinct counts of the main fact columns (all tiers);
- ``orphans``   the five relationships with orphan rows (source.yaml ``orphan_rows``): rows whose key
                is not in the one-side table, by value, and, where the model has the relationship,
                the rows that fall into the relationship's blank member. Listed apart in the report.
                The model keeps them as they are (no unknown member, no data fix) so that the DAX
                and SQL lines stay comparable;
- ``measures``  L2: measures against the totals source.yaml records and the Cube cross-checks
                (render/verify_cube.py), mapped to the DAX measure names;
- ``variants``  L2: the ten semantic-v1.4 variant measures, each on one slice (deferred from v1.4:
                "DAX 变体须经 T17 实测");
- ``alignment`` L2: checklist item 2, Codex T16's DAX alignment list (#156): each row as generic probes
                with the reference reading and, where a measure may read otherwise, the other readings,
                so the report names the one the engine took (reports/validation/t17-dax-alignment-acceptance.md);
- ``syntax``    L1: the depth-2 claims of render/syntax/dax.md that were written without a real
                engine (reports/validation/dax-syntax-t2.md), each as a query whose outcome the
                claim predicts.

The probe also reports what Desktop actually loaded: model identity (tables, columns, measures),
Desktop's own auto date tables, descriptions and synonyms (T10 handoff 二), relationship
activity, and at L2 whether each measure expression is the one the renderer wrote.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO = Path(__file__).resolve().parent.parent
EXPECTED_JSON = REPO / "reports" / "validation" / "dax_probe_expected.json"
TOLERANCE = 0.005
TIERS = ("L0", "L1", "L2")

SUMS = [  # (table, column, aggregate)
    ("FactSales", "SalesAmount", "sum"), ("FactSales", "SalesQuantity", "sum"), ("FactSales", "TotalCost", "sum"),
    ("FactSales", "ReturnAmount", "sum"), ("FactSales", "DiscountAmount", "sum"), ("FactSales", "StoreKey", "distinct"),
    ("FactOnlineSales", "SalesAmount", "sum"), ("FactOnlineSales", "SalesQuantity", "sum"),
    ("FactOnlineSales", "TotalCost", "sum"), ("FactOnlineSales", "ReturnAmount", "sum"),
    ("FactOnlineSales", "SalesOrderNumber", "distinct"), ("FactOnlineSales", "CustomerKey", "distinct"),
    ("FactInventory", "OnHandQuantity", "sum"), ("FactInventory", "OnOrderQuantity", "sum"),
    ("FactSalesQuota", "SalesAmountQuota", "sum"), ("FactSalesQuota", "SalesQuantityQuota", "sum"),
    ("FactStrategyPlan", "Amount", "sum"), ("FactITMachine", "CostAmount", "sum"), ("FactITSLA", "DownTime", "sum"),
    ("FactExchangeRate", "AverageRate", "sum"),
]


# ---------------------------------------------------------------------------
# Names per tier


class Names:
    """How one tier's model names a table / column, quoted for DAX."""

    def __init__(self, tier: str):
        from render.tmdl import Project, q

        self.tier, self._p, self._q = tier, Project(tier), q

    def t(self, table: str) -> str:
        return "'" + self._p.tname(table).replace("'", "''") + "'"

    def c(self, table: str, column: str) -> str:
        return f"{self.t(table)}[{self._p.cname(table, column)}]"

    def relationships(self) -> dict[tuple[str, str], bool]:
        return {(f, t): active for f, t, active in self._p.relationships()}


# ---------------------------------------------------------------------------
# chDB over the Parquet files (Mac)


def parquet_dir() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        raise SystemExit("SEMDEBT_DATA_DIR is not set")
    return Path(root).expanduser() / "parquet"


def on_parquet(sql: str, pq: Path) -> str:
    """``retail.T`` → the Parquet file Power BI imports for T."""
    return re.sub(r"\bretail\.(\w+)", lambda m: f"file('{pq}/{m.group(1)}.parquet', Parquet)", sql)


def make_rows(pq: Path):
    import chdb

    def rows(sql: str) -> list[list[str]]:
        out = chdb.query(on_parquet(sql, pq), "TSV").bytes().decode()
        return [line.split("\t") for line in out.splitlines() if line]

    return rows


def make_scalar(pq: Path):
    import chdb

    def scalar(sql: str) -> float:
        out = chdb.query(on_parquet(sql, pq), "TSV").bytes().decode().strip()
        if out in ("", "\\N", "nan"):
            return float("nan")
        return float(out)

    return scalar


def _row(expr: str) -> str:
    return f'EVALUATE ROW ( "v", {expr} )'


# ---------------------------------------------------------------------------
# The checks


def data_checks(scalar) -> list[dict]:
    from render.common import source

    names = {tier: Names(tier) for tier in TIERS}
    out: list[dict] = []

    def add(cid: str, group: str, title: str, dax: dict[str, str], sql: str | None, expected: float | None = None,
            origin: str = "chDB / Parquet") -> None:
        value = scalar(sql) if sql is not None else expected
        out.append({"id": cid, "group": group, "title": title, "dax": dax, "sql": sql, "expected": value,
                    "origin": origin})

    for ds in source()["datasets"]:
        t = ds["name"]
        add(f"rows.{t}", "rows", f"{t} 行数", {tier: _row(f"COUNTROWS ( {n.t(t)} )") for tier, n in names.items()},
            f"SELECT count() FROM retail.{t}")

    for t, c, agg in SUMS:
        dax_fn = "SUM" if agg == "sum" else "DISTINCTCOUNT"
        sql_fn = f"sum({c})" if agg == "sum" else f"uniqExact({c})"
        add(f"sums.{t}.{c}.{agg}", "sums", f"{t}.{c} {'合计' if agg == 'sum' else '去重计数'}",
            {tier: _row(f"{dax_fn} ( {n.c(t, c)} )") for tier, n in names.items()}, f"SELECT {sql_fn} FROM retail.{t}")

    for r in source()["relationships"]:
        if not r.get("orphan_rows"):
            continue
        (ft, fc), (tt, tc) = r["from"].split("."), r["to"].split(".")
        label = f"{r['from']} → {r['to']}"
        by_value = {}
        for tier, n in names.items():
            fk, pk = n.c(ft, fc), n.c(tt, tc)
            by_value[tier] = _row(f"SUMX ( FILTER ( ALL ( {fk} ), NOT ISBLANK ( {fk} ) && NOT ( {fk} IN ALLNOBLANKROW ( {pk} ) ) ), "
                                  f"CALCULATE ( COUNTROWS ( {n.t(ft)} ) ) ) + 0")
        sql_orphan = (f"SELECT countIf({fc} IS NOT NULL AND {fc} NOT IN (SELECT {tc} FROM retail.{tt} WHERE {tc} IS NOT NULL)) "
                      f"FROM retail.{ft}")
        got = scalar(sql_orphan)
        if got != r["orphan_rows"]:
            raise SystemExit(f"{label}: Parquet gives {got} orphan rows, source.yaml says {r['orphan_rows']}")
        add(f"orphans.{r['from']}.by_value", "orphans", f"{label} 孤儿行（按值）", by_value, sql_orphan)
        blank = {}
        for tier, n in names.items():
            active = n.relationships().get((r["from"], r["to"]))
            if active:                       # inactive ones would need USERELATIONSHIP; none of the five is
                blank[tier] = _row(f"CALCULATE ( COUNTROWS ( {n.t(ft)} ), ISBLANK ( {n.c(tt, tc)} ) ) + 0")
        if blank:
            add(f"orphans.{r['from']}.blank_member", "orphans", f"{label} 落进空白成员的行（键为空或找不到）", blank,
                f"SELECT countIf({fc} IS NULL OR {fc} NOT IN (SELECT {tc} FROM retail.{tt} WHERE {tc} IS NOT NULL)) "
                f"FROM retail.{ft}")
    return out


def _dax_by_cube_member() -> dict[str, str]:
    from render.common import metric_callables, metrics_file, variant_callables

    out = {}
    for m in metrics_file()["metrics"]:
        for _, dax, cube in metric_callables(m):
            out[cube] = dax
        for _, _, dax, cube, _ in variant_callables(m):
            out[cube] = dax
    return out


def measure_checks(scalar) -> list[dict]:
    from render import verify_cube as V

    dax = _dax_by_cube_member()
    filters = {"": None, V._Y2009: "'DimDate'[CalendarYear] = 2009",
               V._WORKDAY_2009: "'DimDate'[CalendarYear] = 2009, 'DimDate'[IsWorkDay] = \"WorkDay\""}
    out = []
    for member, where, expected, _tol, origin in V.EXPECTED:
        f = filters[where]
        expr = f"CALCULATE ( {dax[member]}, {f} )" if f else dax[member]
        out.append({"id": f"measures.{member}", "group": "measures",
                    "title": f"{dax[member]}{'（' + ('2009' if where == V._Y2009 else '2009 平日') + '）' if f else ''}",
                    "dax": {"L2": _row(expr)}, "sql": None, "expected": expected, "origin": f"source.yaml {origin}"})
    for member, direct in V.CROSS_CHECKS:
        out.append({"id": f"measures.{member}", "group": "measures", "title": dax[member],
                    "dax": {"L2": _row(dax[member])}, "sql": direct, "expected": scalar(direct),
                    "origin": "chDB / Parquet（render/verify_cube.py 的直接查询）"})
    return out


def variant_checks(scalar) -> list[dict]:
    """One slice per variant measure, with the reading metrics.yaml's ``scope`` states."""
    from render.common import metrics_file, variant_callables

    store = int(scalar("SELECT min(StoreKey) FROM retail.FactSales"))
    subcat = int(scalar("SELECT min(toInt64(ProductSubcategoryKey)) FROM retail.DimProduct "
                        "WHERE ProductKey IN (SELECT DISTINCT ProductKey FROM retail.FactSales)"))
    in_subcat = (f"ProductKey IN (SELECT ProductKey FROM retail.DimProduct WHERE toInt64(ProductSubcategoryKey) = {subcat})")
    in_cat = ("ProductKey IN (SELECT ProductKey FROM retail.DimProduct WHERE toInt64(ProductSubcategoryKey) IN "
              "(SELECT ProductSubcategoryKey FROM retail.DimProductSubcategory WHERE ProductCategoryKey = "
              f"(SELECT ProductCategoryKey FROM retail.DimProductSubcategory WHERE ProductSubcategoryKey = {subcat})))")
    out = []
    for m in metrics_file()["metrics"]:
        for vid, ds, dax, _cube, scope in variant_callables(m):
            key = (m["name"], vid)
            if key == ("销售额占比", "渠道内"):
                expr = f"CALCULATE ( {dax}, 'DimStore'[StoreKey] = {store} )"
                sql = (f"SELECT (SELECT sum(SalesAmount) FROM retail.{ds} WHERE StoreKey = {store}) / "
                       f"(SELECT sum(SalesAmount) FROM retail.{ds} WHERE channelKey = "
                       f"(SELECT any(channelKey) FROM retail.{ds} WHERE StoreKey = {store}))")
                where = f"门店 {store}"
            elif key == ("销售额占比", "品类内"):
                expr = f"CALCULATE ( {dax}, 'DimProductSubcategory'[ProductSubcategoryKey] = {subcat} )"
                sql = (f"SELECT (SELECT sum(SalesAmount) FROM retail.{ds} WHERE {in_subcat}) / "
                       f"(SELECT sum(SalesAmount) FROM retail.{ds} WHERE {in_cat})")
                where = f"子类 {subcat}"
            elif key == ("销售额环比增长率", "按季"):
                expr = f"CALCULATE ( {dax}, DATESBETWEEN ( 'DimDate'[DateKey], DATE ( 2009, 4, 1 ), DATE ( 2009, 6, 30 ) ) )"
                sql = (f"SELECT sumIf(SalesAmount, toStartOfQuarter(DateKey) = '2009-04-01') / "
                       f"sumIf(SalesAmount, toStartOfQuarter(DateKey) = '2009-01-01') - 1 FROM retail.{ds}")
                where = "2009 年第 2 季"
            elif key == ("同店销售额", "作基年"):
                expr = f"CALCULATE ( {dax}, 'DimDate'[CalendarYear] = 2008 )"
                sql = (f"SELECT sum(SalesAmount) FROM retail.{ds} WHERE toYear(DateKey) = 2008 AND StoreKey IN "
                       f"(SELECT DISTINCT StoreKey FROM retail.{ds} WHERE toYear(DateKey) = 2009)")
                where = "2008 年"
            elif vid == "按查询场景" and ds == "FactSalesQuota":
                col = {"目标销售额": "SalesAmountQuota", "目标销量": "SalesQuantityQuota", "目标毛利": "GrossMarginQuota"}[m["name"]]
                expr = f"CALCULATE ( {dax}, 'DimScenario'[ScenarioName] = \"Actual\" )"
                sql = (f"SELECT sum({col}) FROM retail.{ds} WHERE ScenarioKey = "
                       "(SELECT ScenarioKey FROM retail.DimScenario WHERE ScenarioName = 'Actual')")
                where = "场景 Actual"
            elif key == ("计划收入", "按查询场景"):
                expr = f"CALCULATE ( {dax}, 'DimScenario'[ScenarioName] = \"Actual\" )"
                sql = ("SELECT sum(Amount) FROM retail.FactStrategyPlan WHERE ScenarioKey = "
                       "(SELECT ScenarioKey FROM retail.DimScenario WHERE ScenarioName = 'Actual') AND AccountKey IN "
                       "(SELECT AccountKey FROM retail.DimAccount WHERE AccountName = 'Sale Revenue')")
                where = "场景 Actual"
            else:
                raise SystemExit(f"no probe slice for the variant {key} — add one before the DAX runs")
            out.append({"id": f"variants.{m['name']}.{vid}.{ds}", "group": "variants",
                        "title": f"{dax}（{m['name']}·{vid}，{where}）", "scope": scope,
                        "dax": {"L2": _row(expr)}, "sql": sql, "expected": scalar(sql), "origin": "chDB / Parquet"})
    return out


# ---------------------------------------------------------------------------
# Alignment acceptance (checklist item 2: Codex T16, reports/validation/t16_dax_reference_alignment.md)
#
# Each row of the list becomes generic probes on slices tied to no question. ``expected`` is the
# reference reading the list states; ``alternatives`` are the other readings a measure might take,
# so the report can say which one the engine took. ``record_only`` probes have no settled reference
# reading yet (the list asks for engine evidence first): they are reported, not judged.

ALIGN_ROWS = {
    "B-环比": ("销售额环比增长率", "已对齐／调用条件"),
    "B-新客": ("新客数、新客销售额、新客销售额占比", "已对齐（DAX 源码）／同源检查"),
    "B-目标": ("目标销售额、目标销量、目标毛利", "已对齐／调用条件"),
    "B-计划": ("计划收入", "已对齐／调用条件"),
    "C-占比": ("销售额占比（全局、父组范围）", "需对齐／调用条件"),
    "C-变体": ("销售额占比（品类内／渠道内变体）", "需条件验收"),
    "C-同店": ("同店销售额、作基年、同店销售额增长率", "已有变体／需条件验收"),
    "D-复核": ("库存、产品、日均、折扣（复核后不列为缺陷）", "已对齐（源码读法）"),
}


def _window(a: str, b: str) -> str:
    """DAX date-dimension window [a, b] (ISO dates)."""
    ya, ma, da = (int(x) for x in a.split("-"))
    yb, mb, db = (int(x) for x in b.split("-"))
    return f"DATESBETWEEN ( 'DimDate'[DateKey], DATE ( {ya}, {ma}, {da} ), DATE ( {yb}, {mb}, {db} ) )"


def alignment_checks(scalar, rows) -> list[dict]:
    out: list[dict] = []

    def add(row: str, n: int, title: str, dax: str, expected, *, alternatives=None, kind="scalar",
            record_only=False, note="") -> None:
        out.append({"id": f"align.{row}.{n:02d}", "group": "alignment", "row": row, "title": title, "kind": kind,
                    "dax": {"L2": dax}, "expected": expected, "alternatives": alternatives or {},
                    "record_only": record_only, "note": note, "origin": "chDB / Parquet"})

    def sales(t: str, where: str) -> float:
        v = scalar(f"SELECT sum(SalesAmount) FROM retail.{t} WHERE {where}")
        return 0.0 if math.isnan(v) else v

    def growth(cur: float, prev: float):
        return None if not prev else cur / prev - 1

    def period(a: str, b: str) -> str:
        return f"DateKey BETWEEN toDate('{a}') AND toDate('{b}')"

    # -- B 销售额环比增长率: month / quarter / year windows, cross-year, missing base, partial window,
    #    date-dimension column filters
    k = 0
    for t, mom, qoq in (("FactSales", "[Sales Amount MoM %]", "[Sales Amount QoQ %]"),
                        ("FactOnlineSales", "[Online Sales Amount MoM %]", "[Online Sales Amount QoQ %]")):
        cases = [
            ("月窗口 2009-03", mom, "2009-03-01", "2009-03-31", "2009-02-01", "2009-02-28"),
            ("跨年月 2009-01", mom, "2009-01-01", "2009-01-31", "2008-12-01", "2008-12-31"),
            ("跨年完整季 2009Q1（原成员）", mom, "2009-01-01", "2009-03-31", "2008-10-01", "2008-12-31"),
            ("跨年完整季 2009Q1（按季变体）", qoq, "2009-01-01", "2009-03-31", "2008-10-01", "2008-12-31"),
            ("完整年 2009（原成员）", mom, "2009-01-01", "2009-12-31", "2008-01-01", "2008-12-31"),
            ("缺基期 2007-01（基期无数据）", mom, "2007-01-01", "2007-01-31", "2006-12-01", "2006-12-31"),
            ("缺基期 2007Q1（按季变体）", qoq, "2007-01-01", "2007-03-31", "2006-10-01", "2006-12-31"),
        ]
        for title, m, a, b, pa, pb in cases:
            k += 1
            add("B-环比", k, f"{m} {title}", _row(f"CALCULATE ( {m}, {_window(a, b)} )"),
                growth(sales(t, period(a, b)), sales(t, period(pa, pb))))
        k += 1
        add("B-环比", k, f"{mom} 非完整期间 2009-03-01～15（原成员应为空）",
            _row(f"CALCULATE ( {mom}, {_window('2009-03-01', '2009-03-15')} )"), None)
        k += 1
        add("B-环比", k, f"{mom} 日期维的列筛选 年=2009、月=3（与日期函数窗口相容）",
            _row(f"CALCULATE ( {mom}, 'DimDate'[CalendarYear] = 2009, 'DimDate'[MonthNumber] = 3 )"),
            growth(sales(t, period("2009-03-01", "2009-03-31")), sales(t, period("2009-02-01", "2009-02-28"))))

    # -- B 新客: several consecutive cutoffs; sales window ≠ 90-day window; fact-date filter; business slice
    first = "(SELECT CustomerKey, min(DateKey) AS f FROM retail.FactOnlineSales GROUP BY CustomerKey)"

    def new_set(cutoff: str) -> str:
        return f"SELECT CustomerKey FROM {first} WHERE f BETWEEN toDate('{cutoff}') - 89 AND toDate('{cutoff}')"

    k = 0                       # first purchases fall in 2007-01..04 (and one in 2009-12): cutoffs sit there
    for a, b in (("2007-01-01", "2007-01-31"), ("2007-02-01", "2007-02-28"), ("2007-03-01", "2007-03-31"),
                 ("2007-04-01", "2007-04-30"), ("2009-12-01", "2009-12-31")):
        k += 1
        add("B-新客", k, f"[New Customer Count] 截止 {b}（窗口 {a[:7]}）",
            _row(f"CALCULATE ( [New Customer Count], {_window(a, b)} )"),
            scalar(f"SELECT count() FROM ({new_set(b)})"))
    for a, b in (("2007-04-01", "2007-04-30"), ("2007-04-01", "2007-05-31")):   # sales window < 90 days
        new_sales = sales("FactOnlineSales", f"{period(a, b)} AND CustomerKey IN ({new_set(b)})")
        total = sales("FactOnlineSales", period(a, b))
        win90 = sales("FactOnlineSales", f"DateKey BETWEEN toDate('{b}') - 89 AND toDate('{b}') AND CustomerKey IN ({new_set(b)})")
        k += 1
        add("B-新客", k, f"[New Customer Sales Amount] 销售窗口 {a}～{b}（认定窗口为截止前 90 天）",
            _row(f"CALCULATE ( [New Customer Sales Amount], {_window(a, b)} )"), new_sales,
            alternatives={"把 90 天认定窗口当成销售窗口": win90})
        k += 1
        add("B-新客", k, f"[New Customer Sales Share] 销售窗口 {a}～{b}",
            _row(f"CALCULATE ( [New Customer Sales Share], {_window(a, b)} )"), new_sales / total)
    # fact-date filter instead of the date dimension
    k += 1
    dax_fact = ("CALCULATE ( [New Customer Count], 'FactOnlineSales'[DateKey] >= DATE ( 2007, 4, 1 ) "
                "&& 'FactOnlineSales'[DateKey] <= DATE ( 2007, 4, 30 ) )")
    first_in_window = ("(SELECT CustomerKey, min(DateKey) AS f FROM retail.FactOnlineSales "
                       "WHERE DateKey BETWEEN toDate('2007-04-01') AND toDate('2007-04-30') GROUP BY CustomerKey)")
    add("B-新客", k, "[New Customer Count] 用事实表日期列筛 2007-04（不经日期维）", _row(dax_fact),
        scalar(f"SELECT count() FROM ({new_set('2007-04-30')})"),
        alternatives={"截止日取 2009-12-31、首购只在筛选窗口内认定": scalar(
            f"SELECT count() FROM {first_in_window} WHERE f BETWEEN toDate('2009-12-31') - 89 AND toDate('2009-12-31')")},
        note="参考读法：截止日 = 窗口最后一天，首购按全部历史认定")
    # business slice: one product category
    cat = int(scalar("SELECT min(ProductCategoryKey) FROM retail.DimProductCategory"))
    in_cat = ("ProductKey IN (SELECT ProductKey FROM retail.DimProduct WHERE toInt64(ProductSubcategoryKey) IN "
              f"(SELECT ProductSubcategoryKey FROM retail.DimProductSubcategory WHERE ProductCategoryKey = {cat}))")
    cat_first = (f"(SELECT CustomerKey, min(DateKey) AS f FROM retail.FactOnlineSales WHERE {in_cat} GROUP BY CustomerKey)")
    bought_cat = (f"SELECT DISTINCT CustomerKey FROM retail.FactOnlineSales WHERE {in_cat} AND "
                  f"{period('2007-04-01', '2007-04-30')}")
    k += 1
    add("B-新客", k, f"[New Customer Count] 截止 2007-04-30，业务切片：品类 {cat}",
        _row(f"CALCULATE ( [New Customer Count], {_window('2007-04-01', '2007-04-30')}, "
             f"'DimProductCategory'[ProductCategoryKey] = {cat} )"),
        scalar(f"SELECT count() FROM ({new_set('2007-04-30')}) WHERE CustomerKey IN ({bought_cat})"),
        alternatives={
            "首购只在切片内认定（品类内首购）": scalar(
                f"SELECT count() FROM {cat_first} WHERE f BETWEEN toDate('2007-04-30') - 89 AND toDate('2007-04-30')"),
            "首购全历史认定、切片内任何时候买过": scalar(
                f"SELECT count() FROM ({new_set('2007-04-30')}) WHERE CustomerKey IN "
                f"(SELECT DISTINCT CustomerKey FROM retail.FactOnlineSales WHERE {in_cat})"),
        },
        record_only=True,
        note="清单要求切片下仍是「有史以来首次购买」；切片内计哪些客户（窗口内买过切片 / 任何时候买过）清单没定，先记录引擎读法")

    # -- B 目标 / 计划收入: default Budget, explicit scenario overrides, grouping by the scenario
    #    dimension vs. by the fact's scenario key
    scen = {int(r[0]): r[1] for r in rows("SELECT ScenarioKey, ScenarioName FROM retail.DimScenario")}
    budget = next(k_ for k_, n in scen.items() if n == "Budget")
    k = 0
    for m, col in (("[Sales Amount Quota]", "SalesAmountQuota"), ("[Sales Quantity Quota]", "SalesQuantityQuota"),
                   ("[Gross Margin Quota]", "GrossMarginQuota")):
        per = {int(r[0]): float(r[1]) for r in rows(f"SELECT ScenarioKey, sum({col}) FROM retail.FactSalesQuota GROUP BY 1")}
        k += 1
        add("B-目标", k, f"{m} 不筛场景 = Budget", _row(m), per[budget])
        k += 1
        add("B-目标", k, f"{m} 显式筛 Forecast 覆盖默认", _row(f"CALCULATE ( {m}, 'DimScenario'[ScenarioName] = \"Forecast\" )"),
            per[next(k_ for k_, n in scen.items() if n == "Forecast")])
        k += 1
        add("B-目标", k, f"{m} 按场景维分组", f"EVALUATE SUMMARIZECOLUMNS ( 'DimScenario'[ScenarioName], \"v\", {m} )",
            {scen[s]: v for s, v in per.items()}, kind="table")
        k += 1
        add("B-目标", k, f"{m} 按事实表场景键分组（ISFILTERED 不触发）",
            f"EVALUATE SUMMARIZECOLUMNS ( 'FactSalesQuota'[ScenarioKey], \"v\", {m} )",
            {str(s): v for s, v in per.items()}, kind="table",
            alternatives={"只剩 Budget 一行（默认预算残留）": {str(budget): per[budget]}})
    revenue = ("AccountKey IN (SELECT AccountKey FROM retail.DimAccount WHERE AccountName = 'Sale Revenue')")
    per = {int(r[0]): float(r[1]) for r in rows(
        f"SELECT ScenarioKey, sum(Amount) FROM retail.FactStrategyPlan WHERE {revenue} GROUP BY 1")}
    k = 0
    k += 1
    add("B-计划", k, "[Plan Revenue] 不筛场景 = Budget", _row("[Plan Revenue]"), per[budget])
    k += 1
    add("B-计划", k, "[Plan Revenue] 显式筛 Actual，不残留预算",
        _row("CALCULATE ( [Plan Revenue], 'DimScenario'[ScenarioName] = \"Actual\" )"),
        per[next(k_ for k_, n in scen.items() if n == "Actual")])
    k += 1
    add("B-计划", k, "[Plan Revenue] 按场景维分组", "EVALUATE SUMMARIZECOLUMNS ( 'DimScenario'[ScenarioName], \"v\", [Plan Revenue] )",
        {scen[s]: v for s, v in per.items()}, kind="table")
    k += 1
    add("B-计划", k, "[Plan Revenue] 按事实表场景键分组（ISFILTERED 不触发）",
        "EVALUATE SUMMARIZECOLUMNS ( 'FactStrategyPlan'[ScenarioKey], \"v\", [Plan Revenue] )",
        {str(s): v for s, v in per.items()}, kind="table",
        alternatives={"只剩 Budget 一行（默认预算残留）": {str(budget): per[budget]}})

    # -- C 销售额占比（主成员）: period kept, parent group kept, complete denominator before sub-item selection
    k = 0
    by = rows("SELECT channelKey, sum(SalesAmount) FROM retail.FactSales WHERE toYear(DateKey) = 2009 GROUP BY 1")
    tot = sum(float(r[1]) for r in by)
    chan = {int(r[0]): r[1] for r in rows("SELECT ChannelKey, ChannelName FROM retail.DimChannel")}
    k += 1
    add("C-占比", k, "[Sales Amount Share] 按渠道、筛 2009 年（期间保留在分母里）",
        "EVALUATE SUMMARIZECOLUMNS ( 'DimChannel'[ChannelName], TREATAS ( { 2009 }, 'DimDate'[CalendarYear] ), "
        "\"s\", [Sales Amount Share] )", {chan[int(r[0])]: float(r[1]) / tot for r in by}, kind="table")
    yc = rows("SELECT toYear(DateKey), channelKey, sum(SalesAmount) FROM retail.FactSales GROUP BY 1, 2")
    ytot = {}
    for y, _, v in yc:
        ytot[int(y)] = ytot.get(int(y), 0.0) + float(v)
    grand = sum(ytot.values())
    k += 1
    add("C-占比", k, "[Sales Amount Share] 按年 × 渠道分组（父组：年）",
        "EVALUATE SUMMARIZECOLUMNS ( 'DimDate'[CalendarYear], 'DimChannel'[ChannelName], \"s\", [Sales Amount Share] )",
        {f"{int(y)}|{chan[int(c)]}": float(v) / ytot[int(y)] for y, c, v in yc}, kind="table",
        alternatives={"分母是全部年份（父组没保留）": {f"{int(y)}|{chan[int(c)]}": float(v) / grand for y, c, v in yc}})
    allc = rows("SELECT channelKey, sum(SalesAmount) FROM retail.FactSales GROUP BY 1")
    all_tot = sum(float(r[1]) for r in allc)
    sel = {int(r[0]): float(r[1]) for r in allc if int(r[0]) in (1, 2)}
    k += 1
    add("C-占比", k, "[Sales Amount Share] 只选渠道 1、2（分母应在子项筛选前确定）",
        "EVALUATE SUMMARIZECOLUMNS ( 'DimChannel'[ChannelName], TREATAS ( { 1, 2 }, 'DimChannel'[ChannelKey] ), "
        "\"s\", [Sales Amount Share] )", {chan[c]: v / all_tot for c, v in sel.items()}, kind="table",
        alternatives={"分母只含选中的子项": {chan[c]: v / sum(sel.values()) for c, v in sel.items()}})
    s1, s2 = (int(r[0]) for r in rows("SELECT DISTINCT StoreKey FROM retail.FactSales ORDER BY StoreKey LIMIT 2"))
    sc = rows(f"SELECT f.StoreKey, s.ProductCategoryKey, sum(f.SalesAmount) FROM retail.FactSales AS f "
              f"JOIN retail.DimProduct AS p ON f.ProductKey = p.ProductKey "
              f"JOIN retail.DimProductSubcategory AS s ON toInt64(p.ProductSubcategoryKey) = s.ProductSubcategoryKey "
              f"WHERE f.StoreKey IN ({s1}, {s2}) GROUP BY 1, 2")
    cells = {f"{int(s)}|{int(c)}": float(v) for s, c, v in sc}
    stot = {s: sales("FactSales", f"StoreKey = {s}") for s in (s1, s2)}
    for s in (s1, s2):                  # orphan products (and products without a category): the blank group
        rest = stot[s] - sum(v for key, v in cells.items() if key.startswith(f"{s}|"))
        if abs(rest) > 1e-6:
            cells[f"{s}|"] = rest
    two = sum(stot.values())
    k += 1
    add("C-占比", k, f"[Sales Amount Share] 门店 {s1}、{s2} × 品类（父组：门店；孤儿产品是空白组）",
        f"EVALUATE SUMMARIZECOLUMNS ( 'DimStore'[StoreKey], 'DimProductSubcategory'[ProductCategoryKey], "
        f"TREATAS ( {{ {s1}, {s2} }}, 'DimStore'[StoreKey] ), \"s\", [Sales Amount Share] )",
        {key: v / stot[int(key.split("|")[0])] for key, v in cells.items()}, kind="table",
        alternatives={"分母是两家门店合计": {key: v / two for key, v in cells.items()}})

    # -- C 变体: external child filter, fact-key grouping, parent kept, empty sub-group
    k = 0
    sub = int(scalar("SELECT min(toInt64(ProductSubcategoryKey)) FROM retail.DimProduct "
                     "WHERE ProductKey IN (SELECT DISTINCT ProductKey FROM retail.FactSales)"))
    cat_of_sub = ("ProductKey IN (SELECT ProductKey FROM retail.DimProduct WHERE toInt64(ProductSubcategoryKey) IN "
                  "(SELECT ProductSubcategoryKey FROM retail.DimProductSubcategory WHERE ProductCategoryKey = "
                  f"(SELECT ProductCategoryKey FROM retail.DimProductSubcategory WHERE ProductSubcategoryKey = {sub})))")
    of_sub = f"ProductKey IN (SELECT ProductKey FROM retail.DimProduct WHERE toInt64(ProductSubcategoryKey) = {sub})"
    black = "ProductKey IN (SELECT ProductKey FROM retail.DimProduct WHERE ColorName = 'Black')"
    k += 1
    add("C-变体", k, f"[Sales Amount Share In Category] 子类 {sub} + 外部子层筛选 颜色=Black",
        _row(f"CALCULATE ( [Sales Amount Share In Category], 'DimProductSubcategory'[ProductSubcategoryKey] = {sub}, "
             "'DimProduct'[ColorName] = \"Black\" )"),
        sales("FactSales", f"{of_sub} AND {black}") / sales("FactSales", f"{cat_of_sub} AND {black}"),
        alternatives={"分母去掉了外部颜色筛选（REMOVEFILTERS 删子层外部筛选）":
                      sales("FactSales", f"{of_sub} AND {black}") / sales("FactSales", cat_of_sub)},
        record_only=True, note="清单：有外部子层筛选时两端读法不同，应保留哪些过滤待定，先拿引擎证据")
    k += 1
    add("C-变体", k, f"[Sales Amount Share In Category] 子类 {sub}，2009 年、门店 {s1}（父组与期间保留）",
        _row(f"CALCULATE ( [Sales Amount Share In Category], 'DimProductSubcategory'[ProductSubcategoryKey] = {sub}, "
             f"'DimDate'[CalendarYear] = 2009, 'DimStore'[StoreKey] = {s1} )"),
        (lambda a, b: a / b if b else None)(
            sales("FactSales", f"{of_sub} AND toYear(DateKey) = 2009 AND StoreKey = {s1}"),
            sales("FactSales", f"{cat_of_sub} AND toYear(DateKey) = 2009 AND StoreKey = {s1}")))
    empty = int(scalar("SELECT min(ProductSubcategoryKey) FROM retail.DimProductSubcategory WHERE ProductSubcategoryKey "
                       "NOT IN (SELECT toInt64(ProductSubcategoryKey) FROM retail.DimProduct WHERE ProductKey IN "
                       "(SELECT DISTINCT ProductKey FROM retail.FactSales))"))
    k += 1
    add("C-变体", k, f"[Sales Amount Share In Category] 没有销售的子类 {empty}（应为空）",
        _row(f"CALCULATE ( [Sales Amount Share In Category], 'DimProductSubcategory'[ProductSubcategoryKey] = {empty} )"), None)
    ch = {int(r[0]): float(r[1]) for r in rows("SELECT channelKey, sum(SalesAmount) FROM retail.FactSales GROUP BY 1")}
    st = {int(r[0]): (int(r[1]), float(r[2])) for r in rows(
        f"SELECT StoreKey, any(channelKey), sum(SalesAmount) FROM retail.FactSales WHERE StoreKey IN ({s1}, {s2}) GROUP BY 1")}
    k += 1
    add("C-变体", k, f"[Sales Amount Share In Channel] 按维度键分组 门店 {s1}、{s2}",
        f"EVALUATE SUMMARIZECOLUMNS ( 'DimStore'[StoreKey], TREATAS ( {{ {s1}, {s2} }}, 'DimStore'[StoreKey] ), "
        "\"s\", [Sales Amount Share In Channel] )", {str(s): v / ch[c] for s, (c, v) in st.items()}, kind="table")
    k += 1
    add("C-变体", k, f"[Sales Amount Share In Channel] 按事实表键分组 门店 {s1}、{s2}",
        f"EVALUATE SUMMARIZECOLUMNS ( 'FactSales'[StoreKey], TREATAS ( {{ {s1}, {s2} }}, 'FactSales'[StoreKey] ), "
        "\"s\", [Sales Amount Share In Channel] )", {str(s): v / ch[c] for s, (c, v) in st.items()}, kind="table",
        alternatives={"每行都是 1（事实键筛选没去掉）": {str(s): 1.0 for s in st}})
    c1 = st[s1][0]
    k += 1
    add("C-变体", k, f"[Sales Amount Share In Channel] 门店 {s1}、2009 年（期间保留在分母里）",
        _row(f"CALCULATE ( [Sales Amount Share In Channel], 'DimStore'[StoreKey] = {s1}, 'DimDate'[CalendarYear] = 2009 )"),
        sales("FactSales", f"StoreKey = {s1} AND toYear(DateKey) = 2009")
        / sales("FactSales", f"channelKey = {c1} AND toYear(DateKey) = 2009"))

    # -- C 同店: store set decided on the whole store, then the category slice
    def stores(y: int, where: str = "1 = 1") -> str:
        return f"SELECT DISTINCT StoreKey FROM retail.FactSales WHERE toYear(DateKey) = {y} AND {where}"

    k = 0
    sss09 = sales("FactSales", f"toYear(DateKey) = 2009 AND StoreKey IN ({stores(2008)})")
    base08 = sales("FactSales", f"toYear(DateKey) = 2008 AND StoreKey IN ({stores(2009)})")
    k += 1
    add("C-同店", k, "[Same Store Sales Amount] 2009", _row("CALCULATE ( [Same Store Sales Amount], 'DimDate'[CalendarYear] = 2009 )"),
        sss09)
    k += 1
    add("C-同店", k, "[Same Store Sales Growth %] 2009（与金额、作基年同一门店集合）",
        _row("CALCULATE ( [Same Store Sales Growth %], 'DimDate'[CalendarYear] = 2009 )"),
        sss09 / sales("FactSales", f"toYear(DateKey) = 2008 AND StoreKey IN ({stores(2009)})") - 1)
    k += 1
    add("C-同店", k, "闭合：增长率 = 同店 2009 ÷ 作基年 2008 − 1",
        _row("VAR _g = CALCULATE ( [Same Store Sales Growth %], 'DimDate'[CalendarYear] = 2009 ) "
             "VAR _r = DIVIDE ( CALCULATE ( [Same Store Sales Amount], 'DimDate'[CalendarYear] = 2009 ), "
             "CALCULATE ( [Same Store Sales As Base Year], 'DimDate'[CalendarYear] = 2008 ) ) - 1 RETURN _g - _r"),
        0.0, note="相差为 0 即闭合（按绝对差判）")
    out[-1]["abs_tol"] = 1e-9
    drill = int(scalar("SELECT sub FROM (SELECT toInt64(p.ProductSubcategoryKey) AS sub, "
                       "uniqExactIf(f.StoreKey, toYear(f.DateKey) = 2009) + uniqExactIf(f.StoreKey, toYear(f.DateKey) = 2008) AS n "
                       "FROM retail.FactSales AS f JOIN retail.DimProduct AS p ON f.ProductKey = p.ProductKey "
                       "GROUP BY sub ORDER BY n, sub LIMIT 1)"))
    in_c = f"ProductKey IN (SELECT ProductKey FROM retail.DimProduct WHERE toInt64(ProductSubcategoryKey) = {drill})"
    drill_dax = f"'DimProductSubcategory'[ProductSubcategoryKey] = {drill}"
    whole = sales("FactSales", f"toYear(DateKey) = 2009 AND {in_c} AND StoreKey IN ({stores(2008)})")
    by_cat = sales("FactSales", f"toYear(DateKey) = 2009 AND {in_c} AND StoreKey IN ({stores(2008, in_c)})")
    k += 1
    add("C-同店", k, f"[Same Store Sales Amount] 2009，下钻子类 {drill}",
        _row(f"CALCULATE ( [Same Store Sales Amount], 'DimDate'[CalendarYear] = 2009, {drill_dax} )"), whole,
        alternatives={"按子类重新认定同店（该子类自身两年都有销售）": by_cat} if abs(by_cat - whole) > 1e-6 else None)
    base_whole = sales("FactSales", f"toYear(DateKey) = 2008 AND {in_c} AND StoreKey IN ({stores(2009)})")
    base_cat = sales("FactSales", f"toYear(DateKey) = 2008 AND {in_c} AND StoreKey IN ({stores(2009, in_c)})")
    k += 1
    add("C-同店", k, f"[Same Store Sales Growth %] 2009，下钻子类 {drill}",
        _row(f"CALCULATE ( [Same Store Sales Growth %], 'DimDate'[CalendarYear] = 2009, {drill_dax} )"), whole / base_whole - 1,
        alternatives={"按子类重新认定同店": by_cat / base_cat - 1}
        if abs((by_cat / base_cat) - (whole / base_whole)) > 1e-9 else None)
    k += 1
    add("C-同店", k, f"[Same Store Sales As Base Year] 2008，下钻子类 {drill}",
        _row(f"CALCULATE ( [Same Store Sales As Base Year], 'DimDate'[CalendarYear] = 2008, {drill_dax} )"), base_whole,
        alternatives={"按子类重新认定同店": base_cat} if abs(base_cat - base_whole) > 1e-6 else None)

    # -- D 复核后不列为缺陷: one generic slice each (store, year)
    k = 0
    inv_store = int(scalar("SELECT min(StoreKey) FROM retail.FactInventory"))
    snap = (f"SELECT sum(OnHandQuantity * UnitCost) / uniqExact(DateKey) FROM retail.FactInventory "
            f"WHERE StoreKey = {inv_store} AND toYear(DateKey) = 2008")
    k += 1
    add("D-复核", k, f"[Average On Hand Value] 门店 {inv_store}、2008（有记录的快照日平均）",
        _row(f"CALCULATE ( [Average On Hand Value], 'DimStore'[StoreKey] = {inv_store}, 'DimDate'[CalendarYear] = 2008 )"),
        scalar(snap))
    k += 1
    add("D-复核", k, f"[Inventory Turnover] 门店 {inv_store}、2008（分子分母同窗）",
        _row(f"CALCULATE ( [Inventory Turnover], 'DimStore'[StoreKey] = {inv_store}, 'DimDate'[CalendarYear] = 2008 )"),
        scalar(f"SELECT (SELECT sum(TotalCost) FROM retail.FactSales WHERE StoreKey = {inv_store} AND toYear(DateKey) = 2008) "
               f"/ ({snap})"))
    k += 1
    add("D-复核", k, f"[Current On Hand Quantity] 门店 {inv_store}（每店产品全历史最新快照）",
        _row(f"CALCULATE ( [Current On Hand Quantity], 'DimStore'[StoreKey] = {inv_store} )"),
        scalar(f"SELECT sum(OnHandQuantity) FROM retail.FactInventory AS i WHERE StoreKey = {inv_store} AND "
               f"(StoreKey, ProductKey, DateKey) IN (SELECT StoreKey, ProductKey, max(DateKey) FROM retail.FactInventory "
               f"WHERE StoreKey = {inv_store} GROUP BY StoreKey, ProductKey)"))
    k += 1
    add("D-复核", k, f"[Current On Hand Quantity] 门店 {inv_store}、筛 2008 年（当前成员不随期间变）",
        _row(f"CALCULATE ( [Current On Hand Quantity], 'DimStore'[StoreKey] = {inv_store}, 'DimDate'[CalendarYear] = 2008 )"),
        out[-1]["expected"])
    k += 1
    add("D-复核", k, f"[Average Daily Sales Amount] 门店 {s1}、2008（有销售天数作分母）",
        _row(f"CALCULATE ( [Average Daily Sales Amount], 'DimStore'[StoreKey] = {s1}, 'DimDate'[CalendarYear] = 2008 )"),
        scalar(f"SELECT sum(SalesAmount) / uniqExact(DateKey) FROM retail.FactSales WHERE StoreKey = {s1} AND toYear(DateKey) = 2008"))
    k += 1
    add("D-复核", k, f"[Product List Price] 品类 {cat}（产品平均，不是 MAX）",
        _row(f"CALCULATE ( [Product List Price], 'DimProductCategory'[ProductCategoryKey] = {cat} )"),
        scalar(f"SELECT avg(UnitPrice) FROM retail.DimProduct WHERE {in_cat}"))
    k += 1
    add("D-复核", k, f"[All Channel Discount Rate] 门店 {s1}、2008",
        _row(f"CALCULATE ( [All Channel Discount Rate], 'DimStore'[StoreKey] = {s1}, 'DimDate'[CalendarYear] = 2008 )"),
        scalar(f"SELECT sumIf(DiscountAmount, PromotionKey != 1) / sumIf(SalesAmount + DiscountAmount, PromotionKey != 1) "
               f"FROM retail.FactSales WHERE StoreKey = {s1} AND toYear(DateKey) = 2008"))
    k += 1
    add("D-复核", k, f"[Quota Attainment %] 门店 {s1}、2009（预算基数）",
        _row(f"CALCULATE ( [Quota Attainment %], 'DimStore'[StoreKey] = {s1}, 'DimDate'[CalendarYear] = 2009 )"),
        sales("FactSales", f"StoreKey = {s1} AND toYear(DateKey) = 2009") / scalar(
            f"SELECT sum(SalesAmountQuota) FROM retail.FactSalesQuota WHERE StoreKey = {s1} AND toYear(DateKey) = 2009 "
            f"AND ScenarioKey = {budget}"))
    return out


def build_expected() -> dict:
    pq = parquet_dir()
    scalar = make_scalar(pq)
    checks = data_checks(scalar) + measure_checks(scalar) + variant_checks(scalar) + alignment_checks(scalar, make_rows(pq))
    return {"tolerance": TOLERANCE, "parquet": {p.name: sha256_file(p) for p in sorted(pq.glob("*.parquet"))},
            "checks": checks}


# Depth-2 claims of render/syntax/dax.md, checked on the L1 model (the engine behaviour does not
# depend on the tier). ``expect``: "error", "ok", or ("rows", n) / ("rows>", n) / ("all_equal", col) /
# ("not_all_equal", col) / ("value", x) / ("inf", None) / ("blank_group", col) / ("a=b+1", None).
SYNTAX = [
    ("S01", "EVALUATE 后单个数值要包成 ROW", "EVALUATE 1", "error"),
    ("S01b", "同上（正例）", 'EVALUATE ROW ( "v", 1 )', "ok"),
    ("S02", "DEFINE MEASURE 要写明表", 'DEFINE MEASURE [x] = 1 EVALUATE ROW ( "v", [x] )', "error"),
    ("S02b", "同上（正例）", "DEFINE MEASURE 'FactSales'[x] = 1 EVALUATE ROW ( \"v\", [x] )", "ok"),
    ("S02c", "DEFINE VAR 可在 EVALUATE 里用", 'DEFINE VAR _t = { 1, 2 } EVALUATE _t', ("rows", 2)),
    ("S03", "ADDCOLUMNS 新列与已有列同名报错",
     "EVALUATE ADDCOLUMNS ( VALUES ( 'DimChannel'[ChannelName] ), \"ChannelName\", 1 )", "error"),
    ("S03b", "结果列名可以用中文", "EVALUATE ADDCOLUMNS ( VALUES ( 'DimChannel'[ChannelName] ), \"合计\", 1 )", "ok"),
    ("S04", "ORDER BY 只能排结果里有的列",
     "EVALUATE VALUES ( 'DimChannel'[ChannelName] ) ORDER BY 'DimChannel'[ChannelKey]", "error"),
    ("S04b", "ORDER BY 新算的列写 [结果列名]",
     "EVALUATE ADDCOLUMNS ( VALUES ( 'DimChannel'[ChannelName] ), \"n\", 1 ) ORDER BY [n] DESC", "ok"),
    ("S05", "TOPN 遇并列返回多于 N 行", "EVALUATE TOPN ( 1, VALUES ( 'DimChannel'[ChannelName] ), 1, DESC )", ("rows>", 1)),
    ("S06", "SUMMARIZECOLUMNS 去掉结果全为空的组合",
     "EVALUATE SUMMARIZECOLUMNS ( 'DimChannel'[ChannelName], \"v\", BLANK () )", ("rows", 0)),
    ("S07", "没有激活关系时每组同一个合计、不报错",
     "EVALUATE SUMMARIZECOLUMNS ( 'DimGeography'[ContinentName], \"v\", SUM ( 'FactSales'[SalesAmount] ) )",
     ("all_equal", 1)),
    ("S07b", "加 USERELATIONSHIP 后按组分开",
     "EVALUATE SUMMARIZECOLUMNS ( 'DimGeography'[ContinentName], \"v\", CALCULATE ( SUM ( 'FactSales'[SalesAmount] ), "
     "USERELATIONSHIP ( 'DimStore'[GeographyKey], 'DimGeography'[GeographyKey] ) ) )", ("not_all_equal", 1)),
    ("S08", "SUMMARIZECOLUMNS 放进逐行函数内部（说明里写「不要」；这里记录引擎实际行为）",
     "EVALUATE ADDCOLUMNS ( VALUES ( 'DimChannel'[ChannelName] ), \"n\", COUNTROWS ( SUMMARIZECOLUMNS ( "
     "'DimDate'[CalendarYear], \"v\", SUM ( 'FactSales'[SalesAmount] ) ) ) )", "error"),
    ("S09", "孤儿行归入空白组",
     "EVALUATE SUMMARIZECOLUMNS ( 'DimProduct'[BrandName], \"v\", SUM ( 'FactSales'[SalesAmount] ) )", ("blank_group", 0)),
    ("S10", "RELATED 只能在逐行计算的地方用", "EVALUATE ROW ( \"v\", RELATED ( 'DimChannel'[ChannelName] ) )", "error"),
    ("S11", "自连接用 LOOKUPVALUE 按键取值",
     "EVALUATE ROW ( \"v\", LOOKUPVALUE ( 'DimEmployee'[FirstName], 'DimEmployee'[EmployeeKey], 1 ) )", "ok"),
    ("S12", "CALCULATE 简写条件不能比较两张表的列",
     "EVALUATE ROW ( \"v\", CALCULATE ( SUM ( 'FactSales'[SalesAmount] ), 'FactSales'[StoreKey] = 'DimStore'[StoreKey] ) )",
     "error"),
    ("S12b", "CALCULATE 简写条件里用度量值（说明里写「改用 FILTER」；这里记录引擎实际行为）",
     "DEFINE MEASURE 'FactSales'[m] = 1 EVALUATE ROW ( \"v\", CALCULATE ( SUM ( 'FactSales'[SalesAmount] ), "
     "'FactSales'[SalesQuantity] > [m] ) )", "error"),
    ("S13", "字符串 = 不区分大小写", 'EVALUATE ROW ( "v", "abc" = "ABC" )', ("value", True)),
    ("S13b", "BLANK() = 0 为真", 'EVALUATE ROW ( "v", BLANK () = 0 )', ("value", True)),
    ("S13c", "BLANK() == 0 为假", 'EVALUATE ROW ( "v", BLANK () == 0 )', ("value", False)),
    ("S14", "/ 分母为零不报错、返回无穷大", 'EVALUATE ROW ( "v", 1 / 0 )', ("inf", None)),
    ("S15", "日期列不能和字符串比较",
     "EVALUATE FILTER ( VALUES ( 'DimDate'[DateKey] ), 'DimDate'[DateKey] >= \"2008-01-01\" )", "error"),
    ("S15b", "同上（正例：DATE）",
     "EVALUATE FILTER ( VALUES ( 'DimDate'[DateKey] ), 'DimDate'[DateKey] >= DATE ( 2008, 1, 1 ) )", ("rows>", 0)),
    ("S16", "RANKX 第一个参数写 VALUES 时每组都排第 1",
     "EVALUATE SUMMARIZECOLUMNS ( 'DimChannel'[ChannelName], \"r\", RANKX ( VALUES ( 'DimChannel'[ChannelName] ), "
     "CALCULATE ( SUM ( 'FactSales'[SalesAmount] ) ) ) )", ("all_equal", 1)),
    ("S16b", "RANKX 写 ALL 时正常排名",
     "EVALUATE SUMMARIZECOLUMNS ( 'DimChannel'[ChannelName], \"r\", RANKX ( ALL ( 'DimChannel'[ChannelName] ), "
     "CALCULATE ( SUM ( 'FactSales'[SalesAmount] ) ) ) )", ("not_all_equal", 1)),
    ("S17", "DISTINCTCOUNT 把空值算作一个值",
     "EVALUATE ROW ( \"a\", DISTINCTCOUNT ( 'FactInventory'[Aging] ), \"b\", DISTINCTCOUNTNOBLANK ( 'FactInventory'[Aging] ) )",
     ("a=b+1", None)),
    ("S18", "QUOTIENT 整数除法", 'EVALUATE ROW ( "v", QUOTIENT ( 7, 2 ) )', ("value", 3)),
]


def judge_syntax(expect, result) -> tuple[bool, str]:
    if expect == "error":
        return (not result.ok), ("报错" if not result.ok else "没有报错")
    if not result.ok:
        return False, f"报错：{(result.error or '')[:160]}"
    rows = result.rows or []
    if expect == "ok":
        return True, f"{len(rows)} 行"
    kind, arg = expect
    if kind == "rows":
        return len(rows) == arg, f"{len(rows)} 行"
    if kind == "rows>":
        return len(rows) > arg, f"{len(rows)} 行"
    if kind in ("all_equal", "not_all_equal"):
        values = {repr(r[arg]) for r in rows}
        same = len(values) == 1 and len(rows) > 1
        return (same if kind == "all_equal" else len(values) > 1), f"{len(rows)} 行，第 {arg + 1} 列 {len(values)} 种值"
    if kind == "value":
        got = rows[0][0] if rows else None
        return got == arg, f"值 {got!r}"
    if kind == "inf":
        got = rows[0][0] if rows else None
        return isinstance(got, float) and math.isinf(got), f"值 {got!r}"
    if kind == "blank_group":
        return any(r[arg] in (None, "") for r in rows), f"{len(rows)} 行，含空白组：{any(r[arg] in (None, '') for r in rows)}"
    if kind == "a=b+1":
        a, b = rows[0][0], rows[0][1]
        return a == b + 1, f"a={a} b={b}"
    raise ValueError(expect)


# ---------------------------------------------------------------------------
# Bundle (Windows side)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def data_root() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        raise SystemExit("SEMDEBT_DATA_DIR is not set")
    return Path(root).expanduser()


def bundle_dir() -> Path:
    return Path(os.environ.get("SEMDEBT_T17_BUNDLE") or data_root() / "t17-bundle")


def work_dir() -> Path:
    return data_root() / "t17-pbip-work"


_DATADIR_LINE = re.compile(r'^(expression DataDir = )"(?:[^"]|"")*"', re.MULTILINE)
_PART_SEP = re.compile(r'DataDir & "[\\/]')


def normalise_pbip_text(text: str) -> str:
    """The two things that depend on where the model is rendered: the DataDir value and the separator."""
    return _PART_SEP.sub('DataDir & "/', _DATADIR_LINE.sub(r'\1"<DataDir>"', text))


def verify_manifest(root: Path) -> list[str]:
    problems = []
    manifest = root / "MANIFEST.sha256"
    if not manifest.exists():
        return [f"{manifest} 不存在"]
    listed = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        listed.add(rel)
        path = root / Path(rel)
        if not path.exists():
            problems.append(f"缺少 {rel}")
        elif sha256_file(path) != digest:
            problems.append(f"哈希不符 {rel}")
    extra = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} - listed - {"MANIFEST.sha256", "BUNDLE.txt"}
    problems += [f"清单外的文件 {x}" for x in sorted(extra)]
    return problems


def compare_with_render(bundle_pbip: Path, rendered: Path) -> list[str]:
    """The bundle's PBIP must be what this checkout renders (up to DataDir and the path separator)."""
    a = {p.relative_to(bundle_pbip).as_posix(): p for p in bundle_pbip.rglob("*") if p.is_file()}
    b = {p.relative_to(rendered).as_posix(): p for p in rendered.rglob("*") if p.is_file()}
    problems = [f"只在压缩包里：{x}" for x in sorted(set(a) - set(b))] + [f"只在本机渲染里：{x}" for x in sorted(set(b) - set(a))]
    for rel in sorted(set(a) & set(b)):
        if normalise_pbip_text(a[rel].read_text(encoding="utf-8")) != normalise_pbip_text(b[rel].read_text(encoding="utf-8")):
            problems.append(f"内容不同：{rel}")
    return problems


def prepare(rendered: Path | None = None) -> int:
    root = bundle_dir()
    print(f"压缩包目录：{root}")
    problems = verify_manifest(root)
    if problems:
        print("清单校验不通过：\n  " + "\n  ".join(problems))
        return 1
    print("清单校验通过（parquet/、pbip/ 的哈希全部一致）")
    rendered = rendered or REPO / "build" / "pbip"
    problems = compare_with_render(root / "pbip", rendered)
    if problems:
        print("压缩包里的 PBIP 与本机仓库渲染出的不一致（仓库版本不对？先 render_all）：\n  " + "\n  ".join(problems[:20]))
        return 1
    print("压缩包里的 PBIP 与本机仓库渲染出的一致")
    parquet = (root / "parquet").resolve()
    for tier in TIERS:
        dst = work_dir() / f"retail-{tier}"
        if dst.exists():
            print(f"已存在，不覆盖：{dst}（要重建就先删掉它）")
            continue
        shutil.copytree(root / "pbip" / f"retail-{tier}", dst)
        expr = dst / f"retail-{tier}.SemanticModel" / "definition" / "expressions.tmdl"
        value = str(parquet).replace('"', '""')
        expr.write_text(_DATADIR_LINE.sub(lambda m: f'{m.group(1)}"{value}"', expr.read_text(encoding="utf-8")),
                        encoding="utf-8")
        for t in (dst / f"retail-{tier}.SemanticModel" / "definition" / "tables").glob("*.tmdl"):
            t.write_text(_PART_SEP.sub(lambda m: 'DataDir & "' + os.sep, t.read_text(encoding="utf-8")),
                         encoding="utf-8")
        print(f"写入 {dst}（DataDir = {parquet}）")
    return 0


# ---------------------------------------------------------------------------
# Probe (Windows)


def _key(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _close(got, exp, tol: float, abs_tol: float | None = None) -> bool:
    """One value against one reading; ``None`` = blank. A blank result counts as 0 only against 0."""
    if exp is None:
        return got is None or got == ""
    if got is None or got == "":
        got = 0.0
    try:
        g, e = float(got), float(exp)
    except (TypeError, ValueError):
        return False
    if math.isnan(g):
        return False
    return abs(g - e) <= abs_tol if abs_tol is not None else _rel(g, e) <= tol


def _matches(got, exp, kind: str, tol: float, abs_tol: float | None = None) -> bool:
    if kind == "table":
        return set(got) == set(exp) and all(_close(got[k], exp[k], tol) for k in exp)
    return _close(got, exp, tol, abs_tol)


def judge_check(check: dict, result, tol: float) -> tuple[bool, str | None, str]:
    """(matches the reference reading, the alternative reading it matches instead, what came back)."""
    if not result.ok:
        return False, None, f"{result.error_class}: {(result.error or '')[:200]}"
    rows = result.rows or []
    kind = check.get("kind", "scalar")
    if kind == "table":
        got = {"|".join(_key(v) for v in r[:-1]): r[-1] for r in rows}
        shown = f"{len(got)} 行"
    else:
        got = rows[0][0] if rows and rows[0] else None
        shown = "空" if got in (None, "") else (f"{float(got):,.6f}" if isinstance(got, (int, float)) else repr(got))
    if _matches(got, check["expected"], kind, tol, check.get("abs_tol")):
        return True, None, shown
    for label, alt in (check.get("alternatives") or {}).items():
        if _matches(got, alt, kind, tol, check.get("abs_tol")):
            return False, label, shown
    if kind == "table":
        exp = check["expected"]
        bad = sorted(set(exp) ^ set(got)) + [k for k in sorted(set(exp) & set(got)) if not _close(got[k], exp[k], tol)]
        shown += f"；不符的键 {bad[:6]}"
    return False, None, shown


def _show(v) -> str:
    if v is None:
        return "空"
    if isinstance(v, dict):
        return f"{len(v)} 行"
    return f"{v:,.6f}"


def _num(result) -> float | None:
    if not result.ok or not result.rows:
        return None
    v = result.rows[0][0]
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rel(got: float, expected: float) -> float:
    if expected == 0:
        return abs(got)
    return abs(got - expected) / abs(expected)


def _ws(s: str) -> str:
    return " ".join(s.split())


def probe(tier: str, out_dir: Path, executor=None, expected_path: Path = EXPECTED_JSON) -> tuple[int, str]:
    from harness.executors import (AUTO_TABLE_PREFIXES, DaxConnectionError, DaxExecutor, DaxModelMismatch,
                                   discover_port, expected_signature)
    from render.check_pbip import load_model

    lines = [f"T17 DAX 探测 · 档位 {tier} · {datetime.now().isoformat(timespec='seconds')}", ""]
    fails = 0

    def say(s: str = "") -> None:
        lines.append(s)
        print(s)

    say("== 连接")
    if executor is None:
        try:
            port, path = discover_port()
        except DaxConnectionError as exc:
            say(f"失败：{exc}")
            return 1, "\n".join(lines)
        say(f"端口 {port}（{path or 'SEMDEBT_PBI_PORT'}）")
        executor = DaxExecutor(tier, timeout_s=600, port=port)
    try:
        sig = executor.verify_model(expected_signature(tier))
        say(f"模型核对通过：retail-{tier}，{len(sig['tables'])} 张表（含 Desktop 自加的），{len(sig['measures'])} 个度量值")
    except (DaxConnectionError, DaxModelMismatch) as exc:
        say(f"失败：{exc}")
        return 1, "\n".join(lines)
    except Exception as exc:  # noqa: BLE001 - report whatever ADOMD raised
        say(f"失败：{type(exc).__name__}: {exc}")
        return 1, "\n".join(lines)

    say("")
    say("== Desktop 实际载入的模型")
    auto = [t for t in sig["tables"] if t.startswith(AUTO_TABLE_PREFIXES)]
    say(f"自动日期表：{len(auto)} 张（应为 0；模型里关掉了自动日期/时间）")
    fails += bool(auto)
    tables = executor.dmv("SELECT [Name], [Description] FROM $SYSTEM.TMSCHEMA_TABLES")
    columns = executor.dmv("SELECT [ExplicitName], [Description], [Type] FROM $SYSTEM.TMSCHEMA_COLUMNS")
    t_desc = sum(1 for _, d in tables if d)
    c_desc = sum(1 for _, d, ty in columns if d and int(ty) != 3)
    want_desc = tier != "L0"
    ok = (t_desc > 0 and c_desc > 0) if want_desc else (t_desc == 0 and c_desc == 0)
    fails += not ok
    say(f"描述：表 {t_desc} 个、列 {c_desc} 个带描述（{'应大于 0' if want_desc else '应为 0'}）{'' if ok else '  ← 不符'}")
    try:
        ling = executor.dmv("SELECT [Content] FROM $SYSTEM.TMSCHEMA_LINGUISTIC_METADATA")
        terms = sum(len(re.findall(r'"State"\s*:\s*"Authored"', str(c[0] or ""))) for c in ling)
        say(f"同义词（linguistic metadata）：{len(ling)} 份，约 {terms} 个条目（L0 应为 0）")
    except Exception as exc:  # noqa: BLE001
        say(f"同义词：DMV 读取失败（{type(exc).__name__}），记下来即可")
    rels = executor.dmv("SELECT [IsActive] FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS")
    model = load_model(tier)
    want_rels, want_inactive = len(model["relationships"]), sum(not r["active"] for r in model["relationships"])
    got_inactive = sum(1 for (a,) in rels if not a)
    ok = len(rels) == want_rels and got_inactive == want_inactive
    fails += not ok
    say(f"关系：{len(rels)} 条，非激活 {got_inactive} 条（应为 {want_rels} / {want_inactive}）{'' if ok else '  ← 不符'}")
    say("AI 指令（Copilot/Instructions/instructions.md）：DMV 读不到，请在 Desktop 里打开 Copilot 面板目测，结果手写在下面。")

    spec = json.loads(expected_path.read_text(encoding="utf-8"))
    tol = spec["tolerance"]
    groups = [("rows", "逐表行数"), ("sums", "合计与去重计数"), ("orphans", "孤儿行（5 条关系，照现状建模）"),
              ("measures", "度量值（L2）"), ("variants", "v1.4 变体度量值（L2）")]
    for group, title in groups:
        checks = [c for c in spec["checks"] if c["group"] == group and tier in c["dax"]]
        if not checks:
            continue
        say("")
        say(f"== {title}：{len(checks)} 项，容差 {tol:.1%}")
        for c in checks:
            res = executor.execute(c["dax"][tier])
            got = _num(res)
            exp = c["expected"]
            if got is None:
                fails += 1
                say(f"  失败  {c['title']}：{res.error_class or '非数值'} {(res.error or '')[:200]}")
                continue
            rel = _rel(got, exp)
            ok = rel <= tol
            fails += not ok
            say(f"  {'通过' if ok else '不符'}  {c['title']}：DAX {got:,.6f}  对照 {exp:,.6f}  相差 {rel:.4%}"
                f"  [{res.elapsed_s:.1f}s]")

    align = [c for c in spec["checks"] if c["group"] == "alignment" and tier in c["dax"]]
    if align:
        say("")
        say(f"== 对齐清单验收（检查清单第 2 项，Codex T16：reports/validation/t16_dax_reference_alignment.md）：{len(align)} 项")
        for row, (title, category) in ALIGN_ROWS.items():
            items = [c for c in align if c["row"] == row]
            if not items:
                continue
            say(f"  [{row}] {title}（清单类别：{category}）")
            for c in items:
                res = executor.execute(c["dax"][tier])
                ok, alt, shown = judge_check(c, res, tol)
                if c.get("record_only"):
                    verdict = "记录"
                    what = "参考读法" if ok else (f"「{alt}」" if alt else "都不是")
                    say(f"    {verdict}  {c['title']}：{shown}，与{what}一致（参考 {_show(c['expected'])}）")
                    continue
                fails += not ok
                tail = "" if ok else (f"，与「{alt}」一致" if alt else "") + f"（参考 {_show(c['expected'])}）"
                say(f"    {'通过' if ok else '不符'}  {c['title']}：{shown}{tail}  [{res.elapsed_s:.1f}s]")
                if c.get("note") and not ok:
                    say(f"          说明：{c['note']}")

    if tier == "L1":
        say("")
        say(f"== 写法说明 2 级条目（render/syntax/dax.md）：{len(SYNTAX)} 项")
        for sid, claim, query, expect in SYNTAX:
            res = executor.execute(query)
            ok, what = judge_syntax(expect, res)
            fails += not ok
            say(f"  {'符合' if ok else '不符'}  {sid} {claim}：{what}")
        res = executor.execute("EVALUATE INFO.PARTITIONS ()")
        ok = res.error_class == "metadata_function"
        fails += not ok
        say(f"  {'符合' if ok else '不符'}  执行器拒绝 INFO.：{res.error_class}")

    if tier == "L2":
        say("")
        say("== 度量值表达式：Desktop 载入的 vs 渲染器写的")
        loaded = {name: expr for _, name, expr in executor.dmv("SELECT [TableID], [Name], [Expression] FROM $SYSTEM.TMSCHEMA_MEASURES")}
        written = {k: v for t in model["tables"].values() for k, v in t["expressions"].items()}
        diff = [k for k in written if _ws(str(loaded.get(k, ""))) != _ws(written[k])]
        fails += bool(diff)
        say(f"  {len(written) - len(diff)} / {len(written)} 一致" + (f"；不同：{', '.join(diff[:20])}" if diff else ""))

    say("")
    say(f"结论：{'全部通过' if not fails else f'{fails} 项不通过或不符，贴回给 Mac 上的 agent'}")
    text = "\n".join(lines) + "\n"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"probe-{tier}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    path.write_text(text, encoding="utf-8")
    print(f"\n报告写入 {path}")
    return (1 if fails else 0), text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("expected", help="Mac: compute reference numbers from the Parquet files with chDB")
    sub.add_parser("prepare", help="Windows: verify the bundle and make the working PBIPs")
    p = sub.add_parser("probe", help="Windows: run the checks against the model open in Desktop")
    p.add_argument("--tier", required=True, choices=TIERS)
    args = ap.parse_args(argv)
    if args.cmd == "expected":
        spec = build_expected()
        EXPECTED_JSON.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        n = {g: sum(c["group"] == g for c in spec["checks"]) for g in ("rows", "sums", "orphans", "measures", "variants", "alignment")}
        print(f"写入 {EXPECTED_JSON.relative_to(REPO)}：{n}")
        return 0
    if args.cmd == "prepare":
        return prepare()
    return probe(args.tier, data_root() / "t17-probe")[0]


if __name__ == "__main__":
    raise SystemExit(main())
