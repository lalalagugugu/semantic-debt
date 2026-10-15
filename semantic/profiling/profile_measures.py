"""度量与行级派生逻辑的探查：金额列之间的算术关系、打折的判定、退货行的形态、
各维度被事实表用到的程度。

写 `source.yaml` 的 metrics 节和 `widetables.sql` 的派生列之前跑这个，
保证每条派生逻辑都是数据里成立的，而不是照常识猜的。

产物：semantic/profiling/out/measures.md

重跑：
    uv run python semantic/profiling/profile_measures.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT = Path(__file__).resolve().parent / "out"

CHECKS: list[tuple[str, str]] = [
    ("线上销售：退货行（SalesQuantity = 0）上其余金额列是什么样",
     """SELECT SalesQuantity = 0 AS is_return_row, count() AS rows,
               round(sum(SalesAmount), 2) AS sales, round(sum(ReturnAmount), 2) AS returns,
               round(sum(DiscountAmount), 2) AS discount, round(sum(TotalCost), 2) AS cost,
               round(min(UnitPrice), 2) AS min_unit_price, round(max(UnitPrice), 2) AS max_unit_price
        FROM retail.FactOnlineSales GROUP BY is_return_row ORDER BY is_return_row"""),
    ("线上销售：SalesAmount 与 UnitPrice × SalesQuantity − DiscountAmount 是否相等",
     """SELECT count() AS rows,
               countIf(abs(SalesAmount - (UnitPrice * SalesQuantity - DiscountAmount)) < 0.005) AS matches,
               round(max(abs(SalesAmount - (UnitPrice * SalesQuantity - DiscountAmount))), 4) AS max_gap
        FROM retail.FactOnlineSales"""),
    ("全渠道销售：SalesAmount 与 UnitPrice × SalesQuantity − DiscountAmount 是否相等",
     """SELECT count() AS rows,
               countIf(abs(SalesAmount - (UnitPrice * SalesQuantity - DiscountAmount)) < 0.005) AS matches,
               round(max(abs(SalesAmount - (UnitPrice * SalesQuantity - DiscountAmount))), 4) AS max_gap
        FROM retail.FactSales"""),
    ("线上销售：TotalCost 与 UnitCost × SalesQuantity 是否相等（退货行会不等）",
     """SELECT SalesQuantity = 0 AS is_return_row, count() AS rows,
               countIf(abs(TotalCost - UnitCost * SalesQuantity) < 0.005) AS matches
        FROM retail.FactOnlineSales GROUP BY is_return_row ORDER BY is_return_row"""),
    ("全渠道销售：TotalCost 与 UnitCost × SalesQuantity 是否相等",
     """SELECT count() AS rows,
               countIf(abs(TotalCost - UnitCost * SalesQuantity) < 0.005) AS matches,
               round(max(abs(TotalCost - UnitCost * SalesQuantity)), 4) AS max_gap
        FROM retail.FactSales"""),
    ("「是否打折」两种判定是否一致：PromotionKey != 1 与 DiscountAmount > 0",
     """SELECT 'FactOnlineSales' AS t, count() AS rows,
               countIf(PromotionKey != 1) AS promo_not_1,
               countIf(DiscountAmount > 0) AS discount_gt_0,
               countIf((PromotionKey != 1) != (DiscountAmount > 0)) AS disagree
        FROM retail.FactOnlineSales
        UNION ALL
        SELECT 'FactSales', count(), countIf(PromotionKey != 1),
               countIf(DiscountAmount > 0), countIf((PromotionKey != 1) != (DiscountAmount > 0))
        FROM retail.FactSales"""),
    ("折扣金额为 0 却挂了促销的行，是哪些促销",
     """SELECT p.PromotionName, p.DiscountPercent, count() AS rows
        FROM retail.FactSales f JOIN retail.DimPromotion p ON f.PromotionKey = p.PromotionKey
        WHERE f.PromotionKey != 1 AND f.DiscountAmount = 0
        GROUP BY p.PromotionName, p.DiscountPercent ORDER BY rows DESC LIMIT 10"""),
    ("毛利：销售额 − 总成本，按渠道看合计与毛利率",
     """SELECT c.ChannelName, round(sum(f.SalesAmount), 2) AS sales,
               round(sum(f.TotalCost), 2) AS cost,
               round(sum(f.SalesAmount) - sum(f.TotalCost), 2) AS gross_margin,
               round((sum(f.SalesAmount) - sum(f.TotalCost)) / sum(f.SalesAmount), 4) AS gm_pct
        FROM retail.FactSales f JOIN retail.DimChannel c ON f.channelKey = c.ChannelKey
        GROUP BY c.ChannelName ORDER BY sales DESC"""),
    ("退货率：退货数量 ÷ 销售数量，两张事实表各自的全量值",
     """SELECT 'FactOnlineSales' AS t, sum(SalesQuantity) AS sales_qty,
               sum(ReturnQuantity) AS return_qty,
               round(sum(ReturnQuantity) / sum(SalesQuantity), 6) AS return_rate
        FROM retail.FactOnlineSales
        UNION ALL
        SELECT 'FactSales', sum(SalesQuantity), sum(ReturnQuantity),
               round(sum(ReturnQuantity) / sum(SalesQuantity), 6)
        FROM retail.FactSales"""),
    ("客单价：线上销售的销售额 ÷ 去重订单数",
     """SELECT round(sum(SalesAmount), 2) AS sales, uniqExact(SalesOrderNumber) AS orders,
               round(sum(SalesAmount) / uniqExact(SalesOrderNumber), 4) AS avg_order_value
        FROM retail.FactOnlineSales"""),
    ("日均销售（约定 4）：先按天汇总再平均，节假日 vs 平日（2009 年，全渠道）",
     """SELECT d.IsHoliday, count() AS days, round(sum(day_sales), 2) AS sales,
               round(avg(day_sales), 2) AS avg_daily_sales
        FROM (SELECT DateKey, sum(SalesAmount) AS day_sales FROM retail.FactSales
              WHERE DateKey BETWEEN '2009-01-01' AND '2009-12-31' GROUP BY DateKey) f
        JOIN retail.DimDate d ON f.DateKey = d.DateKey
        GROUP BY d.IsHoliday ORDER BY d.IsHoliday"""),
    ("事实表的日期是否连续覆盖（有没有一天都没有销售的日子）",
     """SELECT 'FactSales' AS t, uniqExact(DateKey) AS fact_days,
               dateDiff('day', min(DateKey), max(DateKey)) + 1 AS span_days FROM retail.FactSales
        UNION ALL
        SELECT 'FactOnlineSales', uniqExact(DateKey),
               dateDiff('day', min(DateKey), max(DateKey)) + 1 FROM retail.FactOnlineSales"""),
    ("维度被用到的程度：各维度表有多少行从没出现在全渠道销售里",
     """SELECT 'DimProduct' AS dim, count() AS dim_rows,
               countIf(ProductKey IN (SELECT ProductKey FROM retail.FactSales)) AS used
        FROM retail.DimProduct
        UNION ALL SELECT 'DimStore', count(),
               countIf(StoreKey IN (SELECT StoreKey FROM retail.FactSales)) FROM retail.DimStore
        UNION ALL SELECT 'DimPromotion', count(),
               countIf(PromotionKey IN (SELECT PromotionKey FROM retail.FactSales)) FROM retail.DimPromotion
        UNION ALL SELECT 'DimDate', count(),
               countIf(DateKey IN (SELECT DateKey FROM retail.FactSales)) FROM retail.DimDate
        UNION ALL SELECT 'DimProductSubcategory', count(),
               countIf(ProductSubcategoryKey IN (
                   SELECT toInt32(ProductSubcategoryKey) FROM retail.DimProduct
                   WHERE ProductSubcategoryKey IS NOT NULL)) FROM retail.DimProductSubcategory"""),
    ("战略计划表能否挂到门店：DimStore.EntityKey 与计划表的 EntityKey 的重合",
     """SELECT (SELECT uniqExact(EntityKey) FROM retail.FactStrategyPlan) AS plan_entities,
               (SELECT uniqExact(toInt64(EntityKey)) FROM retail.DimStore) AS store_entities,
               (SELECT count() FROM retail.FactStrategyPlan
                WHERE EntityKey NOT IN (SELECT toInt64(EntityKey) FROM retail.DimStore)) AS plan_rows_without_store"""),
    ("三张表的「实际」口径是否互相对得上：全渠道销售额 vs 计划表 Actual/Sale Revenue vs 目标表 Actual",
     """SELECT (SELECT round(sum(SalesAmount), 2) FROM retail.FactSales) AS factsales_total,
               (SELECT round(sum(p.Amount), 2) FROM retail.FactStrategyPlan p
                JOIN retail.DimAccount a ON p.AccountKey = a.AccountKey
                JOIN retail.DimScenario s ON p.ScenarioKey = s.ScenarioKey
                WHERE a.AccountName = 'Sale Revenue' AND s.ScenarioName = 'Actual') AS plan_actual_revenue,
               (SELECT round(sum(q.SalesAmountQuota), 2) FROM retail.FactSalesQuota q
                JOIN retail.DimScenario s ON q.ScenarioKey = s.ScenarioKey
                WHERE s.ScenarioName = 'Actual') AS quota_actual_amount"""),
    ("销售目标表各渠道的预算目标（目标达成率按渠道算时要用）",
     """SELECT c.ChannelName, round(sum(q.SalesAmountQuota), 2) AS budget_quota
        FROM retail.FactSalesQuota q
        JOIN retail.DimChannel c ON q.ChannelKey = c.ChannelKey
        JOIN retail.DimScenario s ON q.ScenarioKey = s.ScenarioKey
        WHERE s.ScenarioName = 'Budget' GROUP BY c.ChannelName ORDER BY budget_quota DESC"""),
    ("当前库存：最近一次快照的规模与金额",
     """WITH latest AS (
            SELECT StoreKey, ProductKey, max(DateKey) AS d
            FROM retail.FactInventory GROUP BY StoreKey, ProductKey)
        SELECT count() AS rows, sum(i.OnHandQuantity) AS on_hand,
               round(sum(i.OnHandQuantity * i.UnitCost), 2) AS on_hand_value,
               sum(i.OnOrderQuantity) AS on_order,
               countIf(i.OnHandQuantity < i.SafetyStockQuantity) AS below_safety_stock
        FROM retail.FactInventory i
        JOIN latest l ON i.StoreKey = l.StoreKey AND i.ProductKey = l.ProductKey AND i.DateKey = l.d"""),
    ("库存的 Aging / DaysInStock 这些列是什么含义线索：与数量的关系",
     """SELECT Aging, count() AS rows, round(avg(OnHandQuantity), 1) AS avg_on_hand,
               round(avg(DaysInStock), 1) AS avg_days_in_stock,
               round(min(MinDayInStock), 1) AS min_min, round(max(MaxDayInStock), 1) AS max_max
        FROM retail.FactInventory GROUP BY Aging ORDER BY Aging"""),
    ("产品维度缺的那 284 个键是连续的一段还是散落的",
     """SELECT min(k) AS min_missing, max(k) AS max_missing, count() AS missing_keys FROM (
            SELECT DISTINCT ProductKey AS k FROM retail.FactSales
            WHERE ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct))"""),
    ("缺行的产品键在各品类上有没有系统性（用线上销售的单价区间间接看）",
     """SELECT count() AS orphan_rows, round(min(UnitPrice), 2) AS min_price,
               round(max(UnitPrice), 2) AS max_price, round(avg(UnitPrice), 2) AS avg_price
        FROM retail.FactOnlineSales
        WHERE ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)"""),
    ("门店类型与全渠道销售的关系：哪些类型的门店真的有销售",
     """SELECT s.StoreType, count() AS stores,
               countIf(s.StoreKey IN (SELECT StoreKey FROM retail.FactSales)) AS with_sales,
               countIf(s.StoreKey IN (SELECT StoreKey FROM retail.FactOnlineSales)) AS with_online_sales
        FROM retail.DimStore s GROUP BY s.StoreType ORDER BY stores DESC"""),
    ("门店的开关店状态：Status 与 CloseDate 的配合",
     """SELECT Status, CloseDate = '2090-12-31' AS never_closed, count() AS stores
        FROM retail.DimStore GROUP BY Status, never_closed ORDER BY stores DESC"""),
]


def chdb_dir() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        sys.exit("SEMDEBT_DATA_DIR 未设置（见 AGENTS.md「环境」）")
    d = Path(root).expanduser() / "chdb"
    if not d.is_dir():
        sys.exit(f"chDB 数据目录不存在：{d}（先跑 data/load.py）")
    return d


def main() -> None:
    from chdb import session

    OUT.mkdir(parents=True, exist_ok=True)
    sess = session.Session(str(chdb_dir()))
    lines = [
        "# 度量与行级派生逻辑探查",
        "",
        "由 `semantic/profiling/profile_measures.py` 生成，不要手改。",
        "",
        "`source.yaml` 的 metrics 节与 `widetables.sql` 的每个派生列都要在这里找到依据。",
        "",
    ]
    try:
        for i, (claim, sql) in enumerate(CHECKS, 1):
            print(f"[{i}/{len(CHECKS)}] {claim}", flush=True)
            fmt = sess.query(sql, "PrettyCompactNoEscapes").bytes().decode("utf-8")
            lines += [f"## {i}. {claim}", "", "```sql", " ".join(sql.split()), "```", "",
                      "```", fmt.rstrip("\n"), "```", ""]
    finally:
        sess.close()
    (OUT / "measures.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"写出 {OUT / 'measures.md'}")


if __name__ == "__main__":
    main()
