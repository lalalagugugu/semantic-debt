"""逐条把 `semantic/conventions.md` 的 15 条约定拿到数据上核实。

约定清单是定稿、不得修改（AGENTS.md）。本脚本只负责**查**：每条约定里凡是能被数据证伪
或证实的断言（科目名、场景名、促销键、快照频率、币种、渠道、日期上限……），都跑一条查询。
与数据矛盾的，由会话写进 `decisions/open-questions.md` 交用户，脚本不作判断之外的任何修改。

产物：semantic/profiling/out/conventions_check.md

重跑：
    uv run python semantic/profiling/check_conventions.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT = Path(__file__).resolve().parent / "out"

# (约定号, 要核实的断言, SQL)。SQL 的结果原样抄进报告，由人判断。
CHECKS: list[tuple[str, str, str]] = [
    ("1/2", "DimChannel 的键与渠道名对应关系",
     "SELECT ChannelKey, ChannelName FROM retail.DimChannel ORDER BY ChannelKey"),
    ("1/2", "FactSales 各渠道的行数与销售额（channelKey 的 c 是小写，数据原样）",
     """SELECT f.channelKey AS k, c.ChannelName AS name, count() AS rows,
               round(sum(f.SalesAmount), 2) AS sales
        FROM retail.FactSales f JOIN retail.DimChannel c ON f.channelKey = c.ChannelKey
        GROUP BY k, name ORDER BY k"""),
    ("1/2", "FactOnlineSales 只落在哪几个门店；这几个门店在 DimStore 里是什么类型",
     """SELECT s.StoreKey, s.StoreName, s.StoreType, count() AS rows
        FROM retail.FactOnlineSales f JOIN retail.DimStore s ON f.StoreKey = s.StoreKey
        GROUP BY s.StoreKey, s.StoreName, s.StoreType ORDER BY s.StoreKey"""),
    ("1/2", "线上渠道两张表的口径差：FactSales 的 Online 渠道 vs FactOnlineSales 合计",
     """SELECT 'FactSales channel=Online' AS src, count() AS rows,
               round(sum(SalesAmount), 2) AS sales, round(sum(ReturnAmount), 2) AS returns
        FROM retail.FactSales WHERE channelKey = (
            SELECT ChannelKey FROM retail.DimChannel WHERE ChannelName = 'Online')
        UNION ALL
        SELECT 'FactOnlineSales', count(), round(sum(SalesAmount), 2), round(sum(ReturnAmount), 2)
        FROM retail.FactOnlineSales"""),
    ("2", "FactSales 的粒度里是否含渠道：按约定写的四列（天、店、品、促销）是否已唯一",
     """SELECT count() AS rows,
               uniqExact((DateKey, StoreKey, ProductKey, PromotionKey)) AS without_channel,
               uniqExact((DateKey, channelKey, StoreKey, ProductKey, PromotionKey)) AS with_channel
        FROM retail.FactSales"""),
    ("2", "FactSales 有没有订单号样式的列（建表语句里的列名清单）",
     """SELECT name FROM system.columns
        WHERE database = 'retail' AND table = 'FactSales' ORDER BY position"""),
    ("3", "各事实表的 DateKey 上限是否就是 2009-12-31",
     """SELECT * FROM (
          SELECT 'FactOnlineSales' AS t, max(DateKey) AS max_date FROM retail.FactOnlineSales
          UNION ALL SELECT 'FactSales', max(DateKey) FROM retail.FactSales
          UNION ALL SELECT 'FactInventory', max(DateKey) FROM retail.FactInventory
          UNION ALL SELECT 'FactSalesQuota', max(DateKey) FROM retail.FactSalesQuota
          UNION ALL SELECT 'FactStrategyPlan', max(DateKey) FROM retail.FactStrategyPlan
          UNION ALL SELECT 'FactITSLA', max(DateKey) FROM retail.FactITSLA
          UNION ALL SELECT 'FactITMachine', max(DateKey) FROM retail.FactITMachine
          UNION ALL SELECT 'FactExchangeRate', max(DateKey) FROM retail.FactExchangeRate
        ) ORDER BY t"""),
    ("4", "「节假日」与「周末」在 DimDate 里是不是同一批天（IsHoliday vs IsWorkDay 交叉表）",
     """SELECT IsHoliday, IsWorkDay, count() AS days, min(DateKey) AS first, max(DateKey) AS last
        FROM retail.DimDate GROUP BY IsHoliday, IsWorkDay ORDER BY IsHoliday, IsWorkDay"""),
    ("4", "IsHoliday='Yes' 的天是不是正好是周六周日",
     """SELECT CalendarDayOfWeekLabel, countIf(IsHoliday = 'Yes') AS holiday_days, count() AS days
        FROM retail.DimDate GROUP BY CalendarDayOfWeekLabel
        ORDER BY min(CalendarDayOfWeekNumber)"""),
    ("5", "客户所在地与门店所在地走的是两条不同的路：两张表各自的 GeographyKey 覆盖",
     """SELECT 'DimCustomer' AS t, uniqExact(GeographyKey) AS geo_keys FROM retail.DimCustomer
        UNION ALL SELECT 'DimStore', uniqExact(GeographyKey) FROM retail.DimStore"""),
    ("5", "按客户所在地只能走线上销售：FactSales 里有没有 CustomerKey",
     """SELECT count() AS has_customerkey FROM system.columns
        WHERE database = 'retail' AND table = 'FactSales' AND name = 'CustomerKey'"""),
    ("5", "DimGeography 的层级：GeographyType 与各级字段的空值情况",
     """SELECT GeographyType, count() AS rows,
               countIf(CityName IS NULL) AS city_null,
               countIf(StateProvinceName IS NULL) AS state_null,
               countIf(RegionCountryName = '') AS country_empty
        FROM retail.DimGeography GROUP BY GeographyType ORDER BY rows DESC"""),
    ("5", "门店与客户各自用到的 GeographyType 是哪一级",
     """SELECT 'store' AS side, g.GeographyType, count() AS rows
        FROM retail.DimStore s JOIN retail.DimGeography g ON s.GeographyKey = g.GeographyKey
        GROUP BY g.GeographyType
        UNION ALL
        SELECT 'customer', g.GeographyType, count()
        FROM retail.DimCustomer c JOIN retail.DimGeography g ON c.GeographyKey = g.GeographyKey
        GROUP BY g.GeographyType"""),
    ("6", "CurrencyKey = 1 是不是美元；各事实表用到几种币种",
     """SELECT CurrencyKey, CurrencyName, CurrencyDescription FROM retail.DimCurrency
        WHERE CurrencyKey = 1"""),
    ("6", "各事实表用到的币种个数（都只有 1 种才谈得上「无需换算」）",
     """SELECT * FROM (
          SELECT 'FactOnlineSales' AS t, uniqExact(CurrencyKey) AS currencies FROM retail.FactOnlineSales
          UNION ALL SELECT 'FactSales', uniqExact(CurrencyKey) FROM retail.FactSales
          UNION ALL SELECT 'FactInventory', uniqExact(CurrencyKey) FROM retail.FactInventory
          UNION ALL SELECT 'FactSalesQuota', uniqExact(CurrencyKey) FROM retail.FactSalesQuota
          UNION ALL SELECT 'FactStrategyPlan', uniqExact(CurrencyKey) FROM retail.FactStrategyPlan
        ) ORDER BY t"""),
    ("7", "退货行的形态：线上销售里 SalesQuantity 与 ReturnQuantity 的组合",
     """SELECT SalesQuantity, ReturnQuantity, count() AS rows,
               round(sum(SalesAmount), 2) AS sales, round(sum(ReturnAmount), 2) AS returns
        FROM retail.FactOnlineSales GROUP BY SalesQuantity, ReturnQuantity
        ORDER BY SalesQuantity, ReturnQuantity"""),
    ("7", "全渠道销售里退货是不是写在同一行上（ReturnQuantity > 0 的行同时有销售额）",
     """SELECT ReturnQuantity > 0 AS has_return, count() AS rows,
               countIf(SalesQuantity > 0) AS also_has_sales,
               round(sum(SalesAmount), 2) AS sales, round(sum(ReturnAmount), 2) AS returns
        FROM retail.FactSales GROUP BY has_return ORDER BY has_return"""),
    ("7", "毛利 = 销售额 − 总成本：有多少行算出来是负的",
     """SELECT * FROM (
          SELECT 'FactOnlineSales' AS t, count() AS rows,
                 countIf(SalesAmount - TotalCost < 0) AS negative_margin_rows
          FROM retail.FactOnlineSales
          UNION ALL SELECT 'FactSales', count(), countIf(SalesAmount - TotalCost < 0)
          FROM retail.FactSales
        ) ORDER BY t"""),
    ("8", "订单号的形态：线上销售的订单数、行数、每单行数",
     """SELECT count() AS lines, uniqExact(SalesOrderNumber) AS orders,
               round(count() / uniqExact(SalesOrderNumber), 3) AS lines_per_order,
               max(SalesOrderLineNumber) AS max_line_no
        FROM retail.FactOnlineSales"""),
    ("8", "一个订单号会不会跨客户或跨天（影响按订单去重计数的口径）",
     """SELECT countIf(cust > 1) AS orders_with_many_customers,
               countIf(days > 1) AS orders_with_many_days,
               count() AS orders
        FROM (SELECT SalesOrderNumber, uniqExact(CustomerKey) AS cust, uniqExact(DateKey) AS days
              FROM retail.FactOnlineSales GROUP BY SalesOrderNumber)"""),
    ("9", "产品表的标价与成本：空值与非正数",
     """SELECT count() AS rows,
               countIf(UnitPrice IS NULL) AS price_null,
               countIf(UnitCost IS NULL) AS cost_null,
               countIf(UnitPrice <= 0) AS price_nonpos,
               countIf(UnitCost <= 0) AS cost_nonpos,
               countIf(UnitPrice < UnitCost) AS price_below_cost
        FROM retail.DimProduct"""),
    ("10", "促销键 1 是不是「无折扣」",
     """SELECT PromotionKey, PromotionName, DiscountPercent, PromotionType, PromotionCategory
        FROM retail.DimPromotion ORDER BY PromotionKey LIMIT 3"""),
    ("10", "促销键 1 的交易是不是真的没有折扣金额",
     """SELECT PromotionKey = 1 AS is_no_discount, count() AS rows,
               round(sum(DiscountAmount), 2) AS discount_amount,
               sum(DiscountQuantity) AS discount_qty
        FROM retail.FactOnlineSales GROUP BY is_no_discount ORDER BY is_no_discount"""),
    ("10", "全渠道销售里促销键 1 的折扣金额",
     """SELECT PromotionKey = 1 AS is_no_discount, count() AS rows,
               round(sum(DiscountAmount), 2) AS discount_amount,
               sum(DiscountQuantity) AS discount_qty
        FROM retail.FactSales GROUP BY is_no_discount ORDER BY is_no_discount"""),
    ("11", "库存快照的频率：不同日期个数、相邻日期间隔",
     """SELECT uniqExact(DateKey) AS snapshot_dates, min(DateKey) AS first, max(DateKey) AS last
        FROM retail.FactInventory"""),
    ("11", "库存快照日期的间隔分布（天）",
     """SELECT gap, count() AS times FROM (
            SELECT dateDiff('day', lagInFrame(d) OVER (ORDER BY d), d) AS gap FROM (
                SELECT DISTINCT DateKey AS d FROM retail.FactInventory))
        WHERE gap IS NOT NULL AND gap > 0 GROUP BY gap ORDER BY times DESC"""),
    ("11", "库存快照日期落在星期几",
     """SELECT d.CalendarDayOfWeekLabel, count() AS snapshot_dates FROM (
            SELECT DISTINCT DateKey FROM retail.FactInventory) f
        JOIN retail.DimDate d ON f.DateKey = d.DateKey
        GROUP BY d.CalendarDayOfWeekLabel ORDER BY snapshot_dates DESC"""),
    ("11", "「当前库存」：每个门店 × 产品的最后一次快照是不是都在同一天",
     """SELECT last_date, count() AS store_product_pairs FROM (
            SELECT StoreKey, ProductKey, max(DateKey) AS last_date
            FROM retail.FactInventory GROUP BY StoreKey, ProductKey)
        GROUP BY last_date ORDER BY last_date DESC LIMIT 10"""),
    ("12", "战略计划表的科目：「收入」对应的 Sale Revenue 是否存在、键是多少",
     """SELECT AccountKey, AccountName, AccountDescription, AccountType, ValueType
        FROM retail.DimAccount WHERE AccountName ILIKE '%revenue%' OR AccountName ILIKE '%income%'
        ORDER BY AccountKey"""),
    ("12", "Sale Revenue 这个科目在战略计划表里有没有数据",
     """SELECT s.ScenarioName, count() AS rows, round(sum(p.Amount), 2) AS amount
        FROM retail.FactStrategyPlan p
        JOIN retail.DimAccount a ON p.AccountKey = a.AccountKey
        JOIN retail.DimScenario s ON p.ScenarioKey = s.ScenarioKey
        WHERE a.AccountName = 'Sale Revenue'
        GROUP BY s.ScenarioName ORDER BY s.ScenarioName"""),
    ("12", "场景表的三个场景",
     "SELECT ScenarioKey, ScenarioName FROM retail.DimScenario ORDER BY ScenarioKey"),
    ("12", "战略计划表的实体是哪一级（约定说「实体 × 品类 × 科目」）",
     """SELECT e.EntityType, count() AS rows, uniqExact(p.EntityKey) AS entities
        FROM retail.FactStrategyPlan p JOIN retail.DimEntity e ON p.EntityKey = e.EntityKey
        GROUP BY e.EntityType ORDER BY rows DESC"""),
    ("12", "销售目标表的粒度：约定说「门店 × 产品 × 日期」，数据里还有渠道",
     """SELECT count() AS rows,
               uniqExact((DateKey, StoreKey, ProductKey, ScenarioKey)) AS without_channel,
               uniqExact((DateKey, ChannelKey, StoreKey, ProductKey, ScenarioKey)) AS with_channel
        FROM retail.FactSalesQuota"""),
    ("12", "销售目标表三个场景的目标销售额合计",
     """SELECT s.ScenarioName, count() AS rows, round(sum(q.SalesAmountQuota), 2) AS amount_quota,
               sum(q.SalesQuantityQuota) AS qty_quota
        FROM retail.FactSalesQuota q JOIN retail.DimScenario s ON q.ScenarioKey = s.ScenarioKey
        GROUP BY s.ScenarioName ORDER BY s.ScenarioName"""),
    ("12", "目标达成率的两个口径都算得出来吗：2009 年全渠道实际销售额 vs 预算场景目标销售额",
     """SELECT (SELECT round(sum(SalesAmount), 2) FROM retail.FactSales
                WHERE DateKey BETWEEN '2009-01-01' AND '2009-12-31') AS actual_allchannel_2009,
               (SELECT round(sum(q.SalesAmountQuota), 2) FROM retail.FactSalesQuota q
                JOIN retail.DimScenario s ON q.ScenarioKey = s.ScenarioKey
                WHERE s.ScenarioName = 'Budget'
                  AND q.DateKey BETWEEN '2009-01-01' AND '2009-12-31') AS budget_quota_2009"""),
    ("12", "销售目标表的日期是不是每月 1 号（月粒度）",
     """SELECT uniqExact(DateKey) AS dates, countIf(toDayOfMonth(DateKey) != 1) AS not_first_of_month
        FROM (SELECT DISTINCT DateKey FROM retail.FactSalesQuota)"""),
    ("13", "客户分层：最近一次购买距 2009-12-31 的月数分布（只有线上销售带客户）",
     """SELECT CASE WHEN months <= 6 THEN '活跃 (<=6)'
                    WHEN months <= 12 THEN '有流失风险 (7-12)'
                    ELSE '已流失 (>12)' END AS tier,
               count() AS customers
        FROM (SELECT CustomerKey,
                     dateDiff('month', max(DateKey), toDate('2009-12-31')) AS months
              FROM retail.FactOnlineSales GROUP BY CustomerKey)
        GROUP BY tier ORDER BY tier"""),
    ("13", "有多少客户在线上销售里一次都没出现过",
     """SELECT (SELECT count() FROM retail.DimCustomer) AS customers_total,
               (SELECT uniqExact(CustomerKey) FROM retail.FactOnlineSales) AS customers_with_sales"""),
    ("14", "新客：首次购买日的分布（按年看）",
     """SELECT toYear(first_buy) AS y, count() AS customers FROM (
            SELECT CustomerKey, min(DateKey) AS first_buy
            FROM retail.FactOnlineSales GROUP BY CustomerKey)
        GROUP BY y ORDER BY y"""),
    ("15", "同店口径：2008 与 2009 都有全渠道销售的门店数",
     """SELECT countIf(y2008 > 0 AND y2009 > 0) AS both_years,
               countIf(y2008 > 0) AS in_2008, countIf(y2009 > 0) AS in_2009, count() AS stores
        FROM (SELECT StoreKey,
                     countIf(toYear(DateKey) = 2008) AS y2008,
                     countIf(toYear(DateKey) = 2009) AS y2009
              FROM retail.FactSales GROUP BY StoreKey)"""),
    ("—", "产品维度缺行：事实表里引用了 DimProduct 没有的 ProductKey",
     """SELECT 'DimProduct rows' AS what, count() AS n FROM retail.DimProduct
        UNION ALL SELECT 'DimProduct key range', max(ProductKey) - min(ProductKey) + 1 FROM retail.DimProduct
        UNION ALL SELECT 'ProductKeys used by FactSales', uniqExact(ProductKey) FROM retail.FactSales
        UNION ALL SELECT 'of which missing from DimProduct',
               uniqExact(ProductKey) FROM retail.FactSales
               WHERE ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)"""),
    ("—", "产品维度缺行的影响：内连接产品表会丢掉多少销售额",
     """SELECT 'FactSales' AS t, count() AS rows, round(sum(SalesAmount), 2) AS sales,
               countIf(ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)) AS orphan_rows,
               round(sumIf(SalesAmount, ProductKey NOT IN (
                   SELECT ProductKey FROM retail.DimProduct)), 2) AS orphan_sales
        FROM retail.FactSales
        UNION ALL
        SELECT 'FactOnlineSales', count(), round(sum(SalesAmount), 2),
               countIf(ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)),
               round(sumIf(SalesAmount, ProductKey NOT IN (
                   SELECT ProductKey FROM retail.DimProduct)), 2)
        FROM retail.FactOnlineSales"""),
    ("—", "门店经理：DimStore.StoreManager 存的是名字还是员工号",
     """SELECT s.StoreKey, s.StoreName, s.StoreManager, s.EmployeeKey,
               e.FirstName, e.LastName, e.Title
        FROM retail.DimStore s LEFT JOIN retail.DimEmployee e ON s.EmployeeKey = e.EmployeeKey
        ORDER BY s.StoreKey LIMIT 5"""),
    ("—", "StoreManager 是不是就等于 EmployeeKey",
     """SELECT count() AS rows,
               countIf(toString(toInt64(EmployeeKey)) = StoreManager) AS manager_equals_employeekey,
               countIf(EmployeeKey IS NULL) AS employeekey_null
        FROM retail.DimStore"""),
    ("—", "DimStore.EmployeeKey 的那 1 个孤儿是哪家店",
     """SELECT StoreKey, StoreName, EmployeeKey FROM retail.DimStore
        WHERE EmployeeKey IS NOT NULL
          AND toInt64(EmployeeKey) NOT IN (SELECT EmployeeKey FROM retail.DimEmployee)"""),
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
        "# 约定清单逐条核实",
        "",
        "由 `semantic/profiling/check_conventions.py` 生成，不要手改。",
        "",
        "`semantic/conventions.md` 是定稿、不得修改。本报告只把每条约定里可被数据证实或证伪的",
        "断言跑一遍，结果原样抄下。与数据矛盾的条目由会话写进 `decisions/open-questions.md`。",
        "",
    ]
    try:
        for i, (clause, claim, sql) in enumerate(CHECKS, 1):
            print(f"[{i}/{len(CHECKS)}] 约定 {clause}: {claim}", flush=True)
            fmt = sess.query(sql, "PrettyCompactNoEscapes").bytes().decode("utf-8")
            lines += [
                f"## {i}. 约定 {clause}：{claim}",
                "",
                "```sql",
                " ".join(sql.split()),
                "```",
                "",
                "```",
                fmt.rstrip("\n"),
                "```",
                "",
            ]
    finally:
        sess.close()
    (OUT / "conventions_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"写出 {OUT / 'conventions_check.md'}")


if __name__ == "__main__":
    main()
