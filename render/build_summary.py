"""重建 L1.5S 汇总层（chDB 的 `ads` 库），并核对每张汇总表的可加指标合计。

把 `semantic/summary/summary.sql` 的语句在 chDB 上执行，然后做任务卡 T08 的验收核对：
**每张汇总表的可加指标在全量范围内的合计，与对应事实表的合计一致。**

比对用 `sum(toDecimal128(列, 6))`，定点数求和与行序无关，可以逐位核。

用法：
    uv run python render/build_summary.py              # 重建 + 核对
    uv run python render/build_summary.py --check-only # 只核对，不重建

产物（不入库）：reports/validation/summary.md
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SQL_FILE = REPO / "semantic" / "summary" / "summary.sql"
REPORT = REPO / "reports" / "validation" / "summary.md"

# 可加指标的对账清单：(汇总表, 汇总表列, 事实表来源的表达式, 说明)
# 「事实表来源」写成完整的 SELECT，因为有的要带筛选（场景、促销），要说清口径。
RECONCILE: list[tuple[str, str, str, str]] = [
    # ---- R01 集团经营月报 ----
    ("ads_sales_month_channel", "销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactSales", "全渠道销售额全量"),
    ("ads_sales_month_channel", "销售数量",
     "SELECT sum(toDecimal128(SalesQuantity, 6)) FROM retail.FactSales", "全渠道销售数量全量"),
    ("ads_sales_month_channel", "退货金额",
     "SELECT sum(toDecimal128(ReturnAmount, 6)) FROM retail.FactSales", "全渠道退货金额全量"),
    ("ads_sales_month_channel", "总成本",
     "SELECT sum(toDecimal128(TotalCost, 6)) FROM retail.FactSales", "全渠道总成本全量"),
    ("ads_sales_month_channel", "折扣金额",
     "SELECT sum(toDecimal128(DiscountAmount, 6)) FROM retail.FactSales", "全渠道折扣金额全量"),
    ("ads_sales_month_channel", "打折销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactSales WHERE PromotionKey != 1",
     "约定 10：促销键 != 1 的销售额"),
    # ---- R02 渠道与区域周报 ----
    ("ads_sales_week_channel_country", "销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactSales", "全渠道销售额全量"),
    ("ads_sales_week_channel_country", "毛利",
     "SELECT sum(toDecimal128(SalesAmount, 6)) - sum(toDecimal128(TotalCost, 6)) FROM retail.FactSales",
     "毛利 = 销售额 − 总成本（约定 7）"),
    # ---- R03 预算执行月报（拆成按门店、按品类两张） ----
    ("ads_plan_month_store_account", "计划金额",
     "SELECT sum(toDecimal128(Amount, 6)) FROM retail.FactStrategyPlan",
     "战略计划全量（三个场景、17 个科目都留在粒度里，所以等于全表）"),
    ("ads_plan_month_category_account", "计划金额",
     "SELECT sum(toDecimal128(Amount, 6)) FROM retail.FactStrategyPlan",
     "同上，换成按品类汇总，总额不变"),
    # ---- R04 销售目标达成月报 ----
    ("ads_quota_month_channel_store_category", "销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactSales", "全渠道销售额全量（分子）"),
    ("ads_quota_month_channel_store_category", "目标销售额",
     """SELECT sum(toDecimal128(q.SalesAmountQuota, 6)) FROM retail.FactSalesQuota q
        JOIN retail.DimScenario s ON q.ScenarioKey = s.ScenarioKey
        WHERE s.ScenarioName = 'Budget'""",
     "约定 12：只有预算场景是正式目标（分母）"),
    ("ads_quota_month_channel_store_category", "目标销量",
     """SELECT sum(toDecimal128(q.SalesQuantityQuota, 6)) FROM retail.FactSalesQuota q
        JOIN retail.DimScenario s ON q.ScenarioKey = s.ScenarioKey
        WHERE s.ScenarioName = 'Budget'""",
     "预算场景的目标销量"),
    # ---- R05 门店经营月报 ----
    ("ads_sales_month_store", "销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactSales", "全渠道销售额全量"),
    ("ads_sales_month_store", "净销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) - sum(toDecimal128(ReturnAmount, 6)) FROM retail.FactSales",
     "净销售额 = 销售额 − 退货金额（约定 7）"),
    # ---- R05 同店用的年表 ----
    ("ads_sales_year_store", "销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactSales", "全渠道销售额全量"),
    # ---- R06 门店日销周报 ----
    ("ads_sales_day_store", "销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactSales", "全渠道销售额全量"),
    ("ads_sales_day_store", "折扣金额",
     "SELECT sum(toDecimal128(DiscountAmount, 6)) FROM retail.FactSales", "全渠道折扣金额全量"),
    # ---- R07 电商运营周报 ----
    ("ads_online_week_store", "销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactOnlineSales", "线上销售额全量"),
    ("ads_online_week_store", "退货金额",
     "SELECT sum(toDecimal128(ReturnAmount, 6)) FROM retail.FactOnlineSales", "线上退货金额全量"),
    ("ads_online_week_store", "订单行数",
     "SELECT toDecimal128(count(), 6) FROM retail.FactOnlineSales", "线上订单行数全量"),
    ("ads_online_week_total", "销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactOnlineSales", "线上销售额全量"),
    ("ads_online_week_total", "订单行数",
     "SELECT toDecimal128(count(), 6) FROM retail.FactOnlineSales", "线上订单行数全量"),
    # ---- R08 电商客户月报 ----
    ("ads_online_customer_month_tier", "销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactOnlineSales", "线上销售额全量"),
    ("ads_online_customer_month_tier", "订单行数",
     "SELECT toDecimal128(count(), 6) FROM retail.FactOnlineSales", "线上订单行数全量"),
    # ---- R09 客户画像季报 ----
    ("ads_online_customer_profile_quarter", "销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactOnlineSales", "线上销售额全量"),
    ("ads_online_customer_profile_quarter", "订单行数",
     "SELECT toDecimal128(count(), 6) FROM retail.FactOnlineSales", "线上订单行数全量"),
    # ---- R10 商品销售月报（检验「未知产品」分组确实保住了总额） ----
    ("ads_sales_month_product", "销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactSales",
     "全渠道销售额全量——这一条专门检验产品维度缺 284 行时「未知（产品维度缺行）」组保住了总额"),
    ("ads_sales_month_product", "销售数量",
     "SELECT sum(toDecimal128(SalesQuantity, 6)) FROM retail.FactSales", "全渠道销售数量全量"),
    ("ads_sales_month_product", "总成本",
     "SELECT sum(toDecimal128(TotalCost, 6)) FROM retail.FactSales", "全渠道总成本全量"),
    # ---- R11 库存周报（半可加：跨快照日求和在业务上没意义，这里只做算术完整性核对） ----
    ("ads_inventory_week_store_category", "在手数量",
     "SELECT sum(toDecimal128(OnHandQuantity, 6)) FROM retail.FactInventory",
     "库存快照全量。**这是算术完整性核对，不是业务指标**：库存半可加，跨快照日求和在业务上无意义（约定 11）"),
    ("ads_inventory_week_store_category", "在订数量",
     "SELECT sum(toDecimal128(OnOrderQuantity, 6)) FROM retail.FactInventory", "同上，算术完整性核对"),
    ("ads_inventory_week_store_category", "安全库存数量",
     "SELECT sum(toDecimal128(SafetyStockQuantity, 6)) FROM retail.FactInventory", "同上，算术完整性核对"),
    ("ads_inventory_week_store_category", "在手库存金额",
     "SELECT sum(toDecimal128(OnHandQuantity, 6) * toDecimal128(UnitCost, 6)) FROM retail.FactInventory",
     "在手库存金额 = 在手数量 × 单位成本，同上为算术完整性核对"),
    # ---- R11 当前库存 ----
    ("ads_inventory_current_store_category", "在手数量",
     """SELECT sum(toDecimal128(i.OnHandQuantity, 6)) FROM retail.FactInventory i
        INNER JOIN (SELECT StoreKey, ProductKey, max(DateKey) AS d
                    FROM retail.FactInventory GROUP BY StoreKey, ProductKey) l
          ON i.StoreKey = l.StoreKey AND i.ProductKey = l.ProductKey AND i.DateKey = l.d""",
     "约定 11 的当前库存：每个门店 × 产品最近一次快照"),
    ("ads_inventory_current_store_category", "在手库存金额",
     """SELECT sum(toDecimal128(i.OnHandQuantity, 6) * toDecimal128(i.UnitCost, 6))
        FROM retail.FactInventory i
        INNER JOIN (SELECT StoreKey, ProductKey, max(DateKey) AS d
                    FROM retail.FactInventory GROUP BY StoreKey, ProductKey) l
          ON i.StoreKey = l.StoreKey AND i.ProductKey = l.ProductKey AND i.DateKey = l.d""",
     "约定 11 的当前库存金额"),
    ("ads_inventory_current_store_category", "门店产品组合数",
     "SELECT toDecimal128(uniqExact((StoreKey, ProductKey)), 6) FROM retail.FactInventory",
     "门店 × 产品组合数"),
    # ---- R12 促销效果月报 ----
    ("ads_promotion_month_channel", "销售额",
     "SELECT sum(toDecimal128(SalesAmount, 6)) FROM retail.FactSales",
     "全渠道销售额全量——无折扣档保留在表里做基线，所以等于全表"),
    ("ads_promotion_month_channel", "折扣金额",
     "SELECT sum(toDecimal128(DiscountAmount, 6)) FROM retail.FactSales", "全渠道折扣金额全量"),
]

# 去重计数列：这些列**不能跨行相加**，所以不做合计对账。
# 这里只核对「在它自己的粒度上算出来的最大值不超过全量去重值」这个必要条件，
# 并把它们逐列列进报告，提醒口径。
DEDUP_COLUMNS: list[tuple[str, str, str]] = [
    ("ads_sales_month_channel", "有销售天数", "SELECT uniqExact(DateKey) FROM retail.FactSales"),
    ("ads_sales_month_channel", "门店数", "SELECT uniqExact(StoreKey) FROM retail.FactSales"),
    ("ads_sales_month_channel", "产品数", "SELECT uniqExact(ProductKey) FROM retail.FactSales"),
    ("ads_sales_week_channel_country", "有销售天数", "SELECT uniqExact(DateKey) FROM retail.FactSales"),
    ("ads_sales_week_channel_country", "门店数", "SELECT uniqExact(StoreKey) FROM retail.FactSales"),
    ("ads_sales_month_store", "有销售天数", "SELECT uniqExact(DateKey) FROM retail.FactSales"),
    ("ads_sales_month_store", "产品数", "SELECT uniqExact(ProductKey) FROM retail.FactSales"),
    ("ads_sales_year_store", "有销售天数", "SELECT uniqExact(DateKey) FROM retail.FactSales"),
    ("ads_online_week_store", "订单数", "SELECT uniqExact(SalesOrderNumber) FROM retail.FactOnlineSales"),
    ("ads_online_week_store", "客户数", "SELECT uniqExact(CustomerKey) FROM retail.FactOnlineSales"),
    ("ads_online_week_total", "订单数", "SELECT uniqExact(SalesOrderNumber) FROM retail.FactOnlineSales"),
    ("ads_online_week_total", "客户数", "SELECT uniqExact(CustomerKey) FROM retail.FactOnlineSales"),
    ("ads_online_customer_month_tier", "订单数", "SELECT uniqExact(SalesOrderNumber) FROM retail.FactOnlineSales"),
    ("ads_online_customer_month_tier", "客户数", "SELECT uniqExact(CustomerKey) FROM retail.FactOnlineSales"),
    ("ads_online_customer_profile_quarter", "订单数", "SELECT uniqExact(SalesOrderNumber) FROM retail.FactOnlineSales"),
    ("ads_online_customer_profile_quarter", "客户数", "SELECT uniqExact(CustomerKey) FROM retail.FactOnlineSales"),
    ("ads_sales_month_product", "产品数", "SELECT uniqExact(ProductKey) FROM retail.FactSales"),
]


# 每张汇总表聚合的是哪张事实表。用来核对「ads 里不得出现任何明细事实表」：
# 汇总表的行数必须显著少于它的基表。
BASE_FACT: dict[str, str] = {
    "ads_sales_month_channel": "retail.FactSales",
    "ads_sales_week_channel_country": "retail.FactSales",
    "ads_plan_month_store_account": "retail.FactStrategyPlan",
    "ads_plan_month_category_account": "retail.FactStrategyPlan",
    "ads_quota_month_channel_store_category": "retail.FactSalesQuota",
    "ads_sales_month_store": "retail.FactSales",
    "ads_sales_year_store": "retail.FactSales",
    "ads_sales_day_store": "retail.FactSales",
    "ads_online_week_store": "retail.FactOnlineSales",
    "ads_online_week_total": "retail.FactOnlineSales",
    "ads_online_customer_month_tier": "retail.FactOnlineSales",
    "ads_online_customer_profile_quarter": "retail.FactOnlineSales",
    "ads_sales_month_product": "retail.FactSales",
    "ads_inventory_week_store_category": "retail.FactInventory",
    "ads_inventory_current_store_category": "retail.FactInventory",
    "ads_promotion_month_channel": "retail.FactSales",
}

# 汇总表行数相对基表的上限。超过就不算汇总了。
MAX_ROW_SHARE = 0.5

# 运行时填：汇总表 → 基表行数（写报告用）
BASE_ROWS: dict[str, int] = {}


def chdb_dir() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        sys.exit("SEMDEBT_DATA_DIR 未设置（见 AGENTS.md「环境」）")
    d = Path(root).expanduser() / "chdb"
    if not d.is_dir():
        sys.exit(f"chDB 数据目录不存在：{d}（先跑 data/load.py）")
    return d


def statements(sql: str) -> list[str]:
    no_comments = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true", help="不重建，只核对")
    args = ap.parse_args()

    from chdb import session

    sql = SQL_FILE.read_text(encoding="utf-8")
    sess = session.Session(str(chdb_dir()))
    failures: list[str] = []
    recon_rows: list[tuple[str, str, str, str, str, str]] = []
    dedup_rows: list[tuple[str, str, str, str, str]] = []
    table_rows: list[tuple[str, int]] = []
    try:
        def scalar(q: str) -> str:
            return sess.query(q, "TabSeparated").bytes().decode("utf-8").strip()

        if not args.check_only:
            for stmt in statements(sql):
                m = re.search(
                    r"(?:CREATE OR REPLACE VIEW|CREATE TABLE|DROP TABLE IF EXISTS|CREATE DATABASE IF NOT EXISTS)\s+(\S+)",
                    stmt,
                )
                print(f"执行：{m.group(1) if m else stmt[:50]}", flush=True)
                sess.query(stmt)

        # 硬规则核对：ads 里不得出现任何明细事实表。
        # 判据不是「行数恰好等于某张事实表」（太窄），而是「相对它自己的基表有没有真的聚合」：
        # 汇总表的行数必须显著少于基表。阈值取 50%——再松就谈不上汇总了。
        # 这一条实测抓到过真问题：原来的 ads_plan_month_store_category_account 粒度与
        # FactStrategyPlan 完全相同（实体与门店一一对应），2,750,628 行，是明细表换了列名。
        objs = scalar(
            "SELECT name FROM system.tables WHERE database = 'ads' ORDER BY name"
        ).splitlines()
        tables_in_ads = [o for o in objs if o]
        for name in tables_in_ads:
            kind = scalar(
                f"SELECT engine FROM system.tables WHERE database = 'ads' AND name = '{name}'"
            )
            if kind == "View":
                continue
            n = int(scalar(f"SELECT count() FROM ads.`{name}`"))
            table_rows.append((name, n))
            base = BASE_FACT.get(name)
            if base is None:
                failures.append(f"ads.{name} 没有在 BASE_FACT 里登记基表，无法核对它是否真的做了聚合")
                continue
            base_rows = int(scalar(f"SELECT count() FROM {base}"))
            BASE_ROWS[name] = base_rows
            if n > base_rows * MAX_ROW_SHARE:
                failures.append(
                    f"ads.{name} 有 {n:,} 行，基表 {base} 有 {base_rows:,} 行"
                    f"（{n / base_rows:.1%}），超过 {MAX_ROW_SHARE:.0%} 就谈不上汇总，"
                    f"疑似明细事实表进了 ads"
                )

        print("\n-- 可加指标合计对账 --", flush=True)
        for table, col, fact_sql, note in RECONCILE:
            got = scalar(f"SELECT sum(toDecimal128(`{col}`, 6)) FROM ads.`{table}`")
            want = scalar(" ".join(fact_sql.split()))
            ok = got == want
            recon_rows.append((table, col, got, want, "一致" if ok else "**不一致**", note))
            print(f"{'OK ' if ok else '差异'} ads.{table}.{col} = {got}（应为 {want}）", flush=True)
            if not ok:
                failures.append(f"ads.{table}.{col} 合计 {got} ≠ 事实表 {want}（{note}）")

        print("\n-- 去重计数列（不做合计对账） --", flush=True)
        for table, col, fact_sql in DEDUP_COLUMNS:
            mx = int(scalar(f"SELECT max(`{col}`) FROM ads.`{table}`"))
            total = int(scalar(" ".join(fact_sql.split())))
            summed = int(scalar(f"SELECT sum(`{col}`) FROM ads.`{table}`"))
            ok = mx <= total
            dedup_rows.append((table, col, str(mx), str(total), str(summed)))
            if not ok:
                failures.append(
                    f"ads.{table}.{col} 某一行的值 {mx} 超过了全量去重值 {total}，不可能"
                )
            print(
                f"{'OK ' if ok else '异常'} ads.{table}.{col}: 单行最大 {mx:,}，"
                f"全量去重 {total:,}，直接相加会得到 {summed:,}（相加是错的）",
                flush=True,
            )
    finally:
        sess.close()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 汇总层（L1.5S）校验报告",
        "",
        "由 `render/build_summary.py` 生成，不要手改。重建与重跑：",
        "",
        "```sh",
        "uv run python render/build_summary.py",
        "```",
        "",
        "建表语句在 `semantic/summary/summary.sql`，物化在 chDB 的独立库 `ads`；",
        "报表需求清单在 `semantic/summary/requirements.md`，列级说明在 `semantic/summary/summary.yaml`。",
        "",
        "## `ads` 库里的汇总表",
        "",
        "硬规则：`ads` 里不得出现任何明细事实表。脚本的判据是**相对基表有没有真的聚合**：",
        "每张汇总表的行数不得超过它所聚合的事实表的 50%。这一条实测抓到过真问题——原来的",
        "`ads_plan_month_store_category_account` 粒度与 `FactStrategyPlan` 完全相同"
        "（实体与门店一一对应），2,750,628 行，是明细表换了个列名，已拆成下面按门店、按品类两张。",
        "",
        "| 汇总表 | 行数 | 基表 | 基表行数 | 占基表 |",
        "|---|---:|---|---:|---:|",
    ]
    for name, n in sorted(table_rows):
        base = BASE_FACT.get(name, "—")
        br = BASE_ROWS.get(name)
        share = f"{n / br:.2%}" if br else "—"
        lines.append(f"| `ads.{name}` | {n:,} | `{base}` | {br:,} | {share} |" if br
                     else f"| `ads.{name}` | {n:,} | {base} | — | — |")
    lines += [
        "",
        "## 可加指标合计对账",
        "",
        "验收项：**每张汇总表的可加指标在全量范围内的合计，与对应事实表的合计一致。**",
        "比对用 `sum(toDecimal128(列, 6))`，定点数求和与行序无关，可逐位核。",
        "",
        "| 汇总表.列 | 汇总表合计 | 事实表合计 | 判定 | 口径说明 |",
        "|---|---:|---:|---|---|",
    ]
    for table, col, got, want, verdict, note in recon_rows:
        lines.append(f"| `ads.{table}.{col}` | {got} | {want} | {verdict} | {note} |")
    lines += [
        "",
        "## 去重计数列",
        "",
        "这些列**不能跨行相加**（客户数、订单数、门店数、产品数、有销售天数、门店产品组合数）。",
        "所以不对它们做合计对账，只核对一个必要条件：任何一行的值都不能超过全量去重值。",
        "下表的「直接相加会得到」一列就是把它们相加的错误结果，和「全量去重」对比能看出差多少。",
        "",
        "| 汇总表.列 | 单行最大 | 全量去重 | 直接相加（错误） |",
        "|---|---:|---:|---:|",
    ]
    for table, col, mx, total, summed in dedup_rows:
        lines.append(f"| `ads.{table}.{col}` | {int(mx):,} | {int(total):,} | {int(summed):,} |")
    lines += [
        "",
        "## 结论",
        "",
        "全部通过。" if not failures else "**未通过：**\n" + "\n".join(f"- {x}" for x in failures),
        "",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n写出 {REPORT}")

    if failures:
        sys.exit("校验未通过：\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
