# 约定清单逐条核实

由 `semantic/profiling/check_conventions.py` 生成，不要手改。

`semantic/conventions.md` 是定稿、不得修改。本报告只把每条约定里可被数据证实或证伪的
断言跑一遍，结果原样抄下。与数据矛盾的条目由会话写进 `decisions/open-questions.md`。

## 1. 约定 1/2：DimChannel 的键与渠道名对应关系

```sql
SELECT ChannelKey, ChannelName FROM retail.DimChannel ORDER BY ChannelKey
```

```
   ┌─ChannelKey─┬─ChannelName─┐
1. │          1 │ Store       │
2. │          2 │ Online      │
3. │          3 │ Catalog     │
4. │          4 │ Reseller    │
   └────────────┴─────────────┘
```

## 2. 约定 1/2：FactSales 各渠道的行数与销售额（channelKey 的 c 是小写，数据原样）

```sql
SELECT f.channelKey AS k, c.ChannelName AS name, count() AS rows, round(sum(f.SalesAmount), 2) AS sales FROM retail.FactSales f JOIN retail.DimChannel c ON f.channelKey = c.ChannelKey GROUP BY k, name ORDER BY k
```

```
   ┌─k─┬─name─────┬────rows─┬─────────sales─┐
1. │ 1 │ Store    │ 2173872 │ 6942853195.14 │ -- 6.94 billion
2. │ 2 │ Online   │  629223 │ 2677599035.07 │ -- 2.68 billion
3. │ 3 │ Catalog  │  194976 │ 1078007547.23 │ -- 1.08 billion
4. │ 4 │ Reseller │  408018 │ 1715197831.44 │ -- 1.72 billion
   └───┴──────────┴─────────┴───────────────┘
```

## 3. 约定 1/2：FactOnlineSales 只落在哪几个门店；这几个门店在 DimStore 里是什么类型

```sql
SELECT s.StoreKey, s.StoreName, s.StoreType, count() AS rows FROM retail.FactOnlineSales f JOIN retail.DimStore s ON f.StoreKey = s.StoreKey GROUP BY s.StoreKey, s.StoreName, s.StoreType ORDER BY s.StoreKey
```

```
   ┌─s.StoreKey─┬─StoreName──────────────────────────┬─StoreType─┬────rows─┐
1. │        199 │ Contoso North America Online Store │ Online    │ 4645792 │ -- 4.65 million
2. │        306 │ Contoso Europe Online Store        │ Online    │ 3847281 │ -- 3.85 million
3. │        307 │ Contoso Asia Online Store          │ Online    │ 4134535 │ -- 4.13 million
   └────────────┴────────────────────────────────────┴───────────┴─────────┘
```

## 4. 约定 1/2：线上渠道两张表的口径差：FactSales 的 Online 渠道 vs FactOnlineSales 合计

```sql
SELECT 'FactSales channel=Online' AS src, count() AS rows, round(sum(SalesAmount), 2) AS sales, round(sum(ReturnAmount), 2) AS returns FROM retail.FactSales WHERE channelKey = ( SELECT ChannelKey FROM retail.DimChannel WHERE ChannelName = 'Online') UNION ALL SELECT 'FactOnlineSales', count(), round(sum(SalesAmount), 2), round(sum(ReturnAmount), 2) FROM retail.FactOnlineSales
```

```
   ┌─src──────────────────────┬─────rows─┬─────────sales─┬─────returns─┐
1. │ FactSales channel=Online │   629223 │ 2677599035.07 │ 32983261.29 │ -- 32.98 million
2. │ FactOnlineSales          │ 12627608 │ 2718202629.81 │  29244318.2 │ -- 29.24 million
   └──────────────────────────┴──────────┴───────────────┴─────────────┘
```

## 5. 约定 2：FactSales 的粒度里是否含渠道：按约定写的四列（天、店、品、促销）是否已唯一

```sql
SELECT count() AS rows, uniqExact((DateKey, StoreKey, ProductKey, PromotionKey)) AS without_channel, uniqExact((DateKey, channelKey, StoreKey, ProductKey, PromotionKey)) AS with_channel FROM retail.FactSales
```

```
   ┌────rows─┬─without_channel─┬─with_channel─┐
1. │ 3406089 │         3406089 │      3406089 │ -- 3.41 million
   └─────────┴─────────────────┴──────────────┘
```

## 6. 约定 2：FactSales 有没有订单号样式的列（建表语句里的列名清单）

```sql
SELECT name FROM system.columns WHERE database = 'retail' AND table = 'FactSales' ORDER BY position
```

```
    ┌─name─────────────┐
 1. │ SalesKey         │
 2. │ DateKey          │
 3. │ channelKey       │
 4. │ StoreKey         │
 5. │ ProductKey       │
 6. │ PromotionKey     │
 7. │ CurrencyKey      │
 8. │ UnitCost         │
 9. │ UnitPrice        │
10. │ SalesQuantity    │
11. │ ReturnQuantity   │
12. │ ReturnAmount     │
13. │ DiscountQuantity │
14. │ DiscountAmount   │
15. │ TotalCost        │
16. │ SalesAmount      │
    └──────────────────┘
```

## 7. 约定 3：各事实表的 DateKey 上限是否就是 2009-12-31

```sql
SELECT * FROM ( SELECT 'FactOnlineSales' AS t, max(DateKey) AS max_date FROM retail.FactOnlineSales UNION ALL SELECT 'FactSales', max(DateKey) FROM retail.FactSales UNION ALL SELECT 'FactInventory', max(DateKey) FROM retail.FactInventory UNION ALL SELECT 'FactSalesQuota', max(DateKey) FROM retail.FactSalesQuota UNION ALL SELECT 'FactStrategyPlan', max(DateKey) FROM retail.FactStrategyPlan UNION ALL SELECT 'FactITSLA', max(DateKey) FROM retail.FactITSLA UNION ALL SELECT 'FactITMachine', max(DateKey) FROM retail.FactITMachine UNION ALL SELECT 'FactExchangeRate', max(DateKey) FROM retail.FactExchangeRate ) ORDER BY t
```

```
   ┌─t────────────────┬───max_date─┐
1. │ FactExchangeRate │ 2009-07-01 │
2. │ FactITMachine    │ 2009-01-01 │
3. │ FactITSLA        │ 2009-12-31 │
4. │ FactInventory    │ 2009-12-26 │
5. │ FactOnlineSales  │ 2009-12-31 │
6. │ FactSales        │ 2009-12-31 │
7. │ FactSalesQuota   │ 2009-12-01 │
8. │ FactStrategyPlan │ 2009-12-01 │
   └──────────────────┴────────────┘
```

## 8. 约定 4：「节假日」与「周末」在 DimDate 里是不是同一批天（IsHoliday vs IsWorkDay 交叉表）

```sql
SELECT IsHoliday, IsWorkDay, count() AS days, min(DateKey) AS first, max(DateKey) AS last FROM retail.DimDate GROUP BY IsHoliday, IsWorkDay ORDER BY IsHoliday, IsWorkDay
```

```
   ┌─IsHoliday─┬─IsWorkDay─┬─days─┬──────first─┬───────last─┐
1. │ No        │ WorkDay   │ 1825 │ 2005-01-03 │ 2011-12-30 │
2. │ Yes       │ WeekEnd   │  731 │ 2005-01-01 │ 2011-12-31 │
   └───────────┴───────────┴──────┴────────────┴────────────┘
```

## 9. 约定 4：IsHoliday='Yes' 的天是不是正好是周六周日

```sql
SELECT CalendarDayOfWeekLabel, countIf(IsHoliday = 'Yes') AS holiday_days, count() AS days FROM retail.DimDate GROUP BY CalendarDayOfWeekLabel ORDER BY min(CalendarDayOfWeekNumber)
```

```
   ┌─CalendarDayOfWeekLabel─┬─holiday_days─┬─days─┐
1. │ Monday                 │            0 │  365 │
2. │ Tuesday                │            0 │  365 │
3. │ Wednesday              │            0 │  365 │
4. │ Thursday               │            0 │  365 │
5. │ Friday                 │            0 │  365 │
6. │ Saturday               │          366 │  366 │
7. │ Sunday                 │          365 │  365 │
   └────────────────────────┴──────────────┴──────┘
```

## 10. 约定 5：客户所在地与门店所在地走的是两条不同的路：两张表各自的 GeographyKey 覆盖

```sql
SELECT 'DimCustomer' AS t, uniqExact(GeographyKey) AS geo_keys FROM retail.DimCustomer UNION ALL SELECT 'DimStore', uniqExact(GeographyKey) FROM retail.DimStore
```

```
   ┌─t───────────┬─geo_keys─┐
1. │ DimStore    │      263 │
2. │ DimCustomer │      476 │
   └─────────────┴──────────┘
```

## 11. 约定 5：按客户所在地只能走线上销售：FactSales 里有没有 CustomerKey

```sql
SELECT count() AS has_customerkey FROM system.columns WHERE database = 'retail' AND table = 'FactSales' AND name = 'CustomerKey'
```

```
   ┌─has_customerkey─┐
1. │               0 │
   └─────────────────┘
```

## 12. 约定 5：DimGeography 的层级：GeographyType 与各级字段的空值情况

```sql
SELECT GeographyType, count() AS rows, countIf(CityName IS NULL) AS city_null, countIf(StateProvinceName IS NULL) AS state_null, countIf(RegionCountryName = '') AS country_empty FROM retail.DimGeography GROUP BY GeographyType ORDER BY rows DESC
```

```
   ┌─GeographyType──┬─rows─┬─city_null─┬─state_null─┬─country_empty─┐
1. │ City           │  517 │         0 │          0 │             0 │
2. │ State/Province │  120 │       120 │          0 │             0 │
3. │ Country/Region │   34 │        34 │         34 │             0 │
4. │ Continent      │    3 │         3 │          3 │             3 │
   └────────────────┴──────┴───────────┴────────────┴───────────────┘
```

## 13. 约定 5：门店与客户各自用到的 GeographyType 是哪一级

```sql
SELECT 'store' AS side, g.GeographyType, count() AS rows FROM retail.DimStore s JOIN retail.DimGeography g ON s.GeographyKey = g.GeographyKey GROUP BY g.GeographyType UNION ALL SELECT 'customer', g.GeographyType, count() FROM retail.DimCustomer c JOIN retail.DimGeography g ON c.GeographyKey = g.GeographyKey GROUP BY g.GeographyType
```

```
   ┌─side─────┬─GeographyType─┬──rows─┐
1. │ store    │ City          │   306 │
2. │ customer │ City          │ 18869 │
   └──────────┴───────────────┴───────┘
```

## 14. 约定 6：CurrencyKey = 1 是不是美元；各事实表用到几种币种

```sql
SELECT CurrencyKey, CurrencyName, CurrencyDescription FROM retail.DimCurrency WHERE CurrencyKey = 1
```

```
   ┌─CurrencyKey─┬─CurrencyName─┬─CurrencyDescription─┐
1. │           1 │ USD          │ US Dollar           │
   └─────────────┴──────────────┴─────────────────────┘
```

## 15. 约定 6：各事实表用到的币种个数（都只有 1 种才谈得上「无需换算」）

```sql
SELECT * FROM ( SELECT 'FactOnlineSales' AS t, uniqExact(CurrencyKey) AS currencies FROM retail.FactOnlineSales UNION ALL SELECT 'FactSales', uniqExact(CurrencyKey) FROM retail.FactSales UNION ALL SELECT 'FactInventory', uniqExact(CurrencyKey) FROM retail.FactInventory UNION ALL SELECT 'FactSalesQuota', uniqExact(CurrencyKey) FROM retail.FactSalesQuota UNION ALL SELECT 'FactStrategyPlan', uniqExact(CurrencyKey) FROM retail.FactStrategyPlan ) ORDER BY t
```

```
   ┌─t────────────────┬─currencies─┐
1. │ FactInventory    │          1 │
2. │ FactOnlineSales  │          1 │
3. │ FactSales        │          1 │
4. │ FactSalesQuota   │          1 │
5. │ FactStrategyPlan │          1 │
   └──────────────────┴────────────┘
```

## 16. 约定 7：退货行的形态：线上销售里 SalesQuantity 与 ReturnQuantity 的组合

```sql
SELECT SalesQuantity, ReturnQuantity, count() AS rows, round(sum(SalesAmount), 2) AS sales, round(sum(ReturnAmount), 2) AS returns FROM retail.FactOnlineSales GROUP BY SalesQuantity, ReturnQuantity ORDER BY SalesQuantity, ReturnQuantity
```

```
   ┌─SalesQuantity─┬─ReturnQuantity─┬─────rows─┬─────────sales─┬────returns─┐
1. │             0 │              1 │   100166 │             0 │ 29244318.2 │ -- 29.24 million
2. │             1 │              0 │ 12527442 │ 2718202629.81 │          0 │
   └───────────────┴────────────────┴──────────┴───────────────┴────────────┘
```

## 17. 约定 7：全渠道销售里退货是不是写在同一行上（ReturnQuantity > 0 的行同时有销售额）

```sql
SELECT ReturnQuantity > 0 AS has_return, count() AS rows, countIf(SalesQuantity > 0) AS also_has_sales, round(sum(SalesAmount), 2) AS sales, round(sum(ReturnAmount), 2) AS returns FROM retail.FactSales GROUP BY has_return ORDER BY has_return
```

```
   ┌─has_return─┬────rows─┬─also_has_sales─┬──────────sales─┬──────returns─┐
1. │          0 │ 2925146 │        2925146 │ 10429326015.01 │            0 │
2. │          1 │  480943 │         480943 │  1984331593.87 │ 156839375.87 │ -- 156.84 million
   └────────────┴─────────┴────────────────┴────────────────┴──────────────┘
```

## 18. 约定 7：毛利 = 销售额 − 总成本：有多少行算出来是负的

```sql
SELECT * FROM ( SELECT 'FactOnlineSales' AS t, count() AS rows, countIf(SalesAmount - TotalCost < 0) AS negative_margin_rows FROM retail.FactOnlineSales UNION ALL SELECT 'FactSales', count(), countIf(SalesAmount - TotalCost < 0) FROM retail.FactSales ) ORDER BY t
```

```
   ┌─t───────────────┬─────rows─┬─negative_margin_rows─┐
1. │ FactOnlineSales │ 12627608 │               369350 │
2. │ FactSales       │  3406089 │                    0 │
   └─────────────────┴──────────┴──────────────────────┘
```

## 19. 约定 8：订单号的形态：线上销售的订单数、行数、每单行数

```sql
SELECT count() AS lines, uniqExact(SalesOrderNumber) AS orders, round(count() / uniqExact(SalesOrderNumber), 3) AS lines_per_order, max(SalesOrderLineNumber) AS max_line_no FROM retail.FactOnlineSales
```

```
   ┌────lines─┬──orders─┬─lines_per_order─┬─max_line_no─┐
1. │ 12627608 │ 1674320 │           7.542 │        4972 │
   └──────────┴─────────┴─────────────────┴─────────────┘
```

## 20. 约定 8：一个订单号会不会跨客户或跨天（影响按订单去重计数的口径）

```sql
SELECT countIf(cust > 1) AS orders_with_many_customers, countIf(days > 1) AS orders_with_many_days, count() AS orders FROM (SELECT SalesOrderNumber, uniqExact(CustomerKey) AS cust, uniqExact(DateKey) AS days FROM retail.FactOnlineSales GROUP BY SalesOrderNumber)
```

```
   ┌─orders_with_many_customers─┬─orders_with_many_days─┬──orders─┐
1. │                       2034 │                     0 │ 1674320 │ -- 1.67 million
   └────────────────────────────┴───────────────────────┴─────────┘
```

## 21. 约定 9：产品表的标价与成本：空值与非正数

```sql
SELECT count() AS rows, countIf(UnitPrice IS NULL) AS price_null, countIf(UnitCost IS NULL) AS cost_null, countIf(UnitPrice <= 0) AS price_nonpos, countIf(UnitCost <= 0) AS cost_nonpos, countIf(UnitPrice < UnitCost) AS price_below_cost FROM retail.DimProduct
```

```
   ┌─rows─┬─price_null─┬─cost_null─┬─price_nonpos─┬─cost_nonpos─┬─price_below_cost─┐
1. │ 2233 │          0 │         0 │            0 │           0 │                0 │
   └──────┴────────────┴───────────┴──────────────┴─────────────┴──────────────────┘
```

## 22. 约定 10：促销键 1 是不是「无折扣」

```sql
SELECT PromotionKey, PromotionName, DiscountPercent, PromotionType, PromotionCategory FROM retail.DimPromotion ORDER BY PromotionKey LIMIT 3
```

```
   ┌─PromotionKey─┬─PromotionName──────────────────────────┬─DiscountPercent─┬─PromotionType─────┬─PromotionCategory─┐
1. │            1 │ No Discount                            │               0 │ No Discount       │ No Discount       │
2. │            2 │ North America Spring Promotion         │            0.05 │ Seasonal Discount │ Store             │
3. │            3 │ North America Back-to-School Promotion │             0.1 │ Seasonal Discount │ Store             │
   └──────────────┴────────────────────────────────────────┴─────────────────┴───────────────────┴───────────────────┘
```

## 23. 约定 10：促销键 1 的交易是不是真的没有折扣金额

```sql
SELECT PromotionKey = 1 AS is_no_discount, count() AS rows, round(sum(DiscountAmount), 2) AS discount_amount, sum(DiscountQuantity) AS discount_qty FROM retail.FactOnlineSales GROUP BY is_no_discount ORDER BY is_no_discount
```

```
   ┌─is_no_discount─┬────rows─┬─discount_amount─┬─discount_qty─┐
1. │              0 │ 8727716 │    268904117.39 │      8727716 │ -- 8.73 million
2. │              1 │ 3899892 │               0 │            0 │
   └────────────────┴─────────┴─────────────────┴──────────────┘
```

## 24. 约定 10：全渠道销售里促销键 1 的折扣金额

```sql
SELECT PromotionKey = 1 AS is_no_discount, count() AS rows, round(sum(DiscountAmount), 2) AS discount_amount, sum(DiscountQuantity) AS discount_qty FROM retail.FactSales GROUP BY is_no_discount ORDER BY is_no_discount
```

```
   ┌─is_no_discount─┬────rows─┬─discount_amount─┬─discount_qty─┐
1. │              0 │ 2239789 │    204157104.08 │      5088853 │ -- 5.09 million
2. │              1 │ 1166300 │               0 │            0 │
   └────────────────┴─────────┴─────────────────┴──────────────┘
```

## 25. 约定 11：库存快照的频率：不同日期个数、相邻日期间隔

```sql
SELECT uniqExact(DateKey) AS snapshot_dates, min(DateKey) AS first, max(DateKey) AS last FROM retail.FactInventory
```

```
   ┌─snapshot_dates─┬──────first─┬───────last─┐
1. │            156 │ 2007-01-06 │ 2009-12-26 │
   └────────────────┴────────────┴────────────┘
```

## 26. 约定 11：库存快照日期的间隔分布（天）

```sql
SELECT gap, count() AS times FROM ( SELECT dateDiff('day', lagInFrame(d) OVER (ORDER BY d), d) AS gap FROM ( SELECT DISTINCT DateKey AS d FROM retail.FactInventory)) WHERE gap IS NOT NULL AND gap > 0 GROUP BY gap ORDER BY times DESC
```

```
   ┌───gap─┬─times─┐
1. │     7 │   155 │
2. │ 13519 │     1 │
   └───────┴───────┘
```

## 27. 约定 11：库存快照日期落在星期几

```sql
SELECT d.CalendarDayOfWeekLabel, count() AS snapshot_dates FROM ( SELECT DISTINCT DateKey FROM retail.FactInventory) f JOIN retail.DimDate d ON f.DateKey = d.DateKey GROUP BY d.CalendarDayOfWeekLabel ORDER BY snapshot_dates DESC
```

```
   ┌─CalendarDayOfWeekLabel─┬─snapshot_dates─┐
1. │ Saturday               │            156 │
   └────────────────────────┴────────────────┘
```

## 28. 约定 11：「当前库存」：每个门店 × 产品的最后一次快照是不是都在同一天

```sql
SELECT last_date, count() AS store_product_pairs FROM ( SELECT StoreKey, ProductKey, max(DateKey) AS last_date FROM retail.FactInventory GROUP BY StoreKey, ProductKey) GROUP BY last_date ORDER BY last_date DESC LIMIT 10
```

```
    ┌──last_date─┬─store_product_pairs─┐
 1. │ 2009-12-26 │               27425 │
 2. │ 2009-12-19 │               14680 │
 3. │ 2009-12-12 │                7990 │
 4. │ 2009-12-05 │                7409 │
 5. │ 2009-11-28 │               23471 │
 6. │ 2009-11-21 │                6754 │
 7. │ 2009-11-14 │                1044 │
 8. │ 2009-11-07 │                 791 │
 9. │ 2009-10-31 │                 678 │
10. │ 2009-10-24 │               15850 │
    └────────────┴─────────────────────┘
```

## 29. 约定 12：战略计划表的科目：「收入」对应的 Sale Revenue 是否存在、键是多少

```sql
SELECT AccountKey, AccountName, AccountDescription, AccountType, ValueType FROM retail.DimAccount WHERE AccountName ILIKE '%revenue%' OR AccountName ILIKE '%income%' ORDER BY AccountKey
```

```
   ┌─AccountKey─┬─AccountName──┬─AccountDescription─┬─AccountType─┬─ValueType─┐
1. │          2 │ Income       │ Income             │ Income      │ Income    │
2. │          4 │ Sale Revenue │ Sale Revenue       │ Income      │ Income    │
   └────────────┴──────────────┴────────────────────┴─────────────┴───────────┘
```

## 30. 约定 12：Sale Revenue 这个科目在战略计划表里有没有数据

```sql
SELECT s.ScenarioName, count() AS rows, round(sum(p.Amount), 2) AS amount FROM retail.FactStrategyPlan p JOIN retail.DimAccount a ON p.AccountKey = a.AccountKey JOIN retail.DimScenario s ON p.ScenarioKey = s.ScenarioKey WHERE a.AccountName = 'Sale Revenue' GROUP BY s.ScenarioName ORDER BY s.ScenarioName
```

```
   ┌─ScenarioName─┬──rows─┬─────────amount─┐
1. │ Actual       │ 84574 │ 12413657608.89 │ -- 12.41 billion
2. │ Budget       │ 84574 │ 11548720849.89 │ -- 11.55 billion
3. │ Forecast     │ 84574 │ 12318305704.57 │ -- 12.32 billion
   └──────────────┴───────┴────────────────┘
```

## 31. 约定 12：场景表的三个场景

```sql
SELECT ScenarioKey, ScenarioName FROM retail.DimScenario ORDER BY ScenarioKey
```

```
   ┌─ScenarioKey─┬─ScenarioName─┐
1. │           1 │ Actual       │
2. │           2 │ Budget       │
3. │           3 │ Forecast     │
   └─────────────┴──────────────┘
```

## 32. 约定 12：战略计划表的实体是哪一级（约定说「实体 × 品类 × 科目」）

```sql
SELECT e.EntityType, count() AS rows, uniqExact(p.EntityKey) AS entities FROM retail.FactStrategyPlan p JOIN retail.DimEntity e ON p.EntityKey = e.EntityKey GROUP BY e.EntityType ORDER BY rows DESC
```

```
   ┌─EntityType─┬────rows─┬─entities─┐
1. │ Store      │ 2750628 │      306 │
   └────────────┴─────────┴──────────┘
```

## 33. 约定 12：销售目标表的粒度：约定说「门店 × 产品 × 日期」，数据里还有渠道

```sql
SELECT count() AS rows, uniqExact((DateKey, StoreKey, ProductKey, ScenarioKey)) AS without_channel, uniqExact((DateKey, ChannelKey, StoreKey, ProductKey, ScenarioKey)) AS with_channel FROM retail.FactSalesQuota
```

```
   ┌────rows─┬─without_channel─┬─with_channel─┐
1. │ 7465911 │         7465911 │      7465911 │ -- 7.47 million
   └─────────┴─────────────────┴──────────────┘
```

## 34. 约定 12：销售目标表三个场景的目标销售额合计

```sql
SELECT s.ScenarioName, count() AS rows, round(sum(q.SalesAmountQuota), 2) AS amount_quota, sum(q.SalesQuantityQuota) AS qty_quota FROM retail.FactSalesQuota q JOIN retail.DimScenario s ON q.ScenarioKey = s.ScenarioKey GROUP BY s.ScenarioName ORDER BY s.ScenarioName
```

```
   ┌─ScenarioName─┬────rows─┬───amount_quota─┬─qty_quota─┐
1. │ Actual       │ 2488637 │ 12413657608.89 │  53320454 │ -- 53.32 million
2. │ Budget       │ 2488637 │ 10667465363.67 │  44300085 │ -- 44.30 million
3. │ Forecast     │ 2488637 │  12917294708.2 │  53875174 │ -- 53.88 million
   └──────────────┴─────────┴────────────────┴───────────┘
```

## 35. 约定 12：目标达成率的两个口径都算得出来吗：2009 年全渠道实际销售额 vs 预算场景目标销售额

```sql
SELECT (SELECT round(sum(SalesAmount), 2) FROM retail.FactSales WHERE DateKey BETWEEN '2009-01-01' AND '2009-12-31') AS actual_allchannel_2009, (SELECT round(sum(q.SalesAmountQuota), 2) FROM retail.FactSalesQuota q JOIN retail.DimScenario s ON q.ScenarioKey = s.ScenarioKey WHERE s.ScenarioName = 'Budget' AND q.DateKey BETWEEN '2009-01-01' AND '2009-12-31') AS budget_quota_2009
```

```
   ┌─actual_allchannel_2009─┬─budget_quota_2009─┐
1. │          3740483119.18 │     3084785562.03 │ -- 3.08 billion
   └────────────────────────┴───────────────────┘
```

## 36. 约定 12：销售目标表的日期是不是每月 1 号（月粒度）

```sql
SELECT uniqExact(DateKey) AS dates, countIf(toDayOfMonth(DateKey) != 1) AS not_first_of_month FROM (SELECT DISTINCT DateKey FROM retail.FactSalesQuota)
```

```
   ┌─dates─┬─not_first_of_month─┐
1. │    36 │                  0 │
   └───────┴────────────────────┘
```

## 37. 约定 13：客户分层：最近一次购买距 2009-12-31 的月数分布（只有线上销售带客户）

```sql
SELECT CASE WHEN months <= 6 THEN '活跃 (<=6)' WHEN months <= 12 THEN '有流失风险 (7-12)' ELSE '已流失 (>12)' END AS tier, count() AS customers FROM (SELECT CustomerKey, dateDiff('month', max(DateKey), toDate('2009-12-31')) AS months FROM retail.FactOnlineSales GROUP BY CustomerKey) GROUP BY tier ORDER BY tier
```

```
   ┌─tier──────────────┬─customers─┐
1. │ 已流失 (>12)      │       138 │
2. │ 有流失风险 (7-12) │      1841 │
3. │ 活跃 (<=6)        │     16890 │
   └───────────────────┴───────────┘
```

## 38. 约定 13：有多少客户在线上销售里一次都没出现过

```sql
SELECT (SELECT count() FROM retail.DimCustomer) AS customers_total, (SELECT uniqExact(CustomerKey) FROM retail.FactOnlineSales) AS customers_with_sales
```

```
   ┌─customers_total─┬─customers_with_sales─┐
1. │           18869 │                18869 │
   └─────────────────┴──────────────────────┘
```

## 39. 约定 14：新客：首次购买日的分布（按年看）

```sql
SELECT toYear(first_buy) AS y, count() AS customers FROM ( SELECT CustomerKey, min(DateKey) AS first_buy FROM retail.FactOnlineSales GROUP BY CustomerKey) GROUP BY y ORDER BY y
```

```
   ┌────y─┬─customers─┐
1. │ 2007 │     18868 │
2. │ 2009 │         1 │
   └──────┴───────────┘
```

## 40. 约定 15：同店口径：2008 与 2009 都有全渠道销售的门店数

```sql
SELECT countIf(y2008 > 0 AND y2009 > 0) AS both_years, countIf(y2008 > 0) AS in_2008, countIf(y2009 > 0) AS in_2009, count() AS stores FROM (SELECT StoreKey, countIf(toYear(DateKey) = 2008) AS y2008, countIf(toYear(DateKey) = 2009) AS y2009 FROM retail.FactSales GROUP BY StoreKey)
```

```
   ┌─both_years─┬─in_2008─┬─in_2009─┬─stores─┐
1. │        301 │     301 │     306 │    306 │
   └────────────┴─────────┴─────────┴────────┘
```

## 41. 约定 —：产品维度缺行：事实表里引用了 DimProduct 没有的 ProductKey

```sql
SELECT 'DimProduct rows' AS what, count() AS n FROM retail.DimProduct UNION ALL SELECT 'DimProduct key range', max(ProductKey) - min(ProductKey) + 1 FROM retail.DimProduct UNION ALL SELECT 'ProductKeys used by FactSales', uniqExact(ProductKey) FROM retail.FactSales UNION ALL SELECT 'of which missing from DimProduct', uniqExact(ProductKey) FROM retail.FactSales WHERE ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)
```

```
   ┌─what─────────────────────────────┬─n────┐
1. │ DimProduct key range             │ 2517 │
2. │ ProductKeys used by FactSales    │ 2516 │
3. │ DimProduct rows                  │ 2233 │
4. │ of which missing from DimProduct │ 284  │
   └──────────────────────────────────┴──────┘
```

## 42. 约定 —：产品维度缺行的影响：内连接产品表会丢掉多少销售额

```sql
SELECT 'FactSales' AS t, count() AS rows, round(sum(SalesAmount), 2) AS sales, countIf(ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)) AS orphan_rows, round(sumIf(SalesAmount, ProductKey NOT IN ( SELECT ProductKey FROM retail.DimProduct)), 2) AS orphan_sales FROM retail.FactSales UNION ALL SELECT 'FactOnlineSales', count(), round(sum(SalesAmount), 2), countIf(ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)), round(sumIf(SalesAmount, ProductKey NOT IN ( SELECT ProductKey FROM retail.DimProduct)), 2) FROM retail.FactOnlineSales
```

```
   ┌─t───────────────┬─────rows─┬──────────sales─┬─orphan_rows─┬─orphan_sales─┐
1. │ FactSales       │  3406089 │ 12413657608.89 │      338898 │ 726129808.32 │ -- 726.13 million
2. │ FactOnlineSales │ 12627608 │  2718202629.81 │     1715380 │ 152121858.08 │ -- 152.12 million
   └─────────────────┴──────────┴────────────────┴─────────────┴──────────────┘
```

## 43. 约定 —：门店经理：DimStore.StoreManager 存的是名字还是员工号

```sql
SELECT s.StoreKey, s.StoreName, s.StoreManager, s.EmployeeKey, e.FirstName, e.LastName, e.Title FROM retail.DimStore s LEFT JOIN retail.DimEmployee e ON s.EmployeeKey = e.EmployeeKey ORDER BY s.StoreKey LIMIT 5
```

```
   ┌─StoreKey─┬─StoreName──────────────────┬─StoreManager─┬─EmployeeKey─┬─FirstName─┬─LastName───────┬─Title───────────────┐
1. │        1 │ Contoso Seattle No.1 Store │ 35           │          35 │ Roy       │ Antebi         │ Sales Store Manager │
2. │        2 │ Contoso Seattle No.2 Store │ 35           │          35 │ Roy       │ Antebi         │ Sales Store Manager │
3. │        3 │ Contoso Kennewick Store    │ 36           │          36 │ Prithvi   │ Raj            │ Sales Store Manager │
4. │        4 │ Contoso Bellevue Store     │ 37           │          37 │ Luca      │ Argentiero     │ Sales Store Manager │
5. │        5 │ Contoso Redmond Store      │ 38           │          38 │ Suriya    │ Sajjateerakool │ Sales Store Manager │
   └──────────┴────────────────────────────┴──────────────┴─────────────┴───────────┴────────────────┴─────────────────────┘
```

## 44. 约定 —：StoreManager 是不是就等于 EmployeeKey

```sql
SELECT count() AS rows, countIf(toString(toInt64(EmployeeKey)) = StoreManager) AS manager_equals_employeekey, countIf(EmployeeKey IS NULL) AS employeekey_null FROM retail.DimStore
```

```
   ┌─rows─┬─manager_equals_employeekey─┬─employeekey_null─┐
1. │  306 │                        306 │                0 │
   └──────┴────────────────────────────┴──────────────────┘
```

## 45. 约定 —：DimStore.EmployeeKey 的那 1 个孤儿是哪家店

```sql
SELECT StoreKey, StoreName, EmployeeKey FROM retail.DimStore WHERE EmployeeKey IS NOT NULL AND toInt64(EmployeeKey) NOT IN (SELECT EmployeeKey FROM retail.DimEmployee)
```

```
   ┌─StoreKey─┬─StoreName────────────┬─EmployeeKey─┐
1. │      227 │ Contoso Naples Store │         245 │
   └──────────┴──────────────────────┴─────────────┘
```

