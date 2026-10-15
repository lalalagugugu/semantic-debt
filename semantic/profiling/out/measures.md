# 度量与行级派生逻辑探查

由 `semantic/profiling/profile_measures.py` 生成，不要手改。

`source.yaml` 的 metrics 节与 `widetables.sql` 的每个派生列都要在这里找到依据。

## 1. 线上销售：退货行（SalesQuantity = 0）上其余金额列是什么样

```sql
SELECT SalesQuantity = 0 AS is_return_row, count() AS rows, round(sum(SalesAmount), 2) AS sales, round(sum(ReturnAmount), 2) AS returns, round(sum(DiscountAmount), 2) AS discount, round(sum(TotalCost), 2) AS cost, round(min(UnitPrice), 2) AS min_unit_price, round(max(UnitPrice), 2) AS max_unit_price FROM retail.FactOnlineSales GROUP BY is_return_row ORDER BY is_return_row
```

```
   ┌─is_return_row─┬─────rows─┬─────────sales─┬────returns─┬────discount─┬──────────cost─┬─min_unit_price─┬─max_unit_price─┐
1. │             0 │ 12527442 │ 2718202629.81 │          0 │ 265996291.3 │ 1330551751.48 │           0.95 │        3199.99 │
2. │             1 │   100166 │             0 │ 29244318.2 │   2907826.1 │   13703156.24 │           0.95 │        3199.99 │
   └───────────────┴──────────┴───────────────┴────────────┴─────────────┴───────────────┴────────────────┴────────────────┘
```

## 2. 线上销售：SalesAmount 与 UnitPrice × SalesQuantity − DiscountAmount 是否相等

```sql
SELECT count() AS rows, countIf(abs(SalesAmount - (UnitPrice * SalesQuantity - DiscountAmount)) < 0.005) AS matches, round(max(abs(SalesAmount - (UnitPrice * SalesQuantity - DiscountAmount))), 4) AS max_gap FROM retail.FactOnlineSales
```

```
   ┌─────rows─┬──matches─┬─max_gap─┐
1. │ 12627608 │ 12559130 │ 639.998 │
   └──────────┴──────────┴─────────┘
```

## 3. 全渠道销售：SalesAmount 与 UnitPrice × SalesQuantity − DiscountAmount 是否相等

```sql
SELECT count() AS rows, countIf(abs(SalesAmount - (UnitPrice * SalesQuantity - DiscountAmount)) < 0.005) AS matches, round(max(abs(SalesAmount - (UnitPrice * SalesQuantity - DiscountAmount))), 4) AS max_gap FROM retail.FactSales
```

```
   ┌────rows─┬─matches─┬─max_gap─┐
1. │ 3406089 │ 3406089 │       0 │
   └─────────┴─────────┴─────────┘
```

## 4. 线上销售：TotalCost 与 UnitCost × SalesQuantity 是否相等（退货行会不等）

```sql
SELECT SalesQuantity = 0 AS is_return_row, count() AS rows, countIf(abs(TotalCost - UnitCost * SalesQuantity) < 0.005) AS matches FROM retail.FactOnlineSales GROUP BY is_return_row ORDER BY is_return_row
```

```
   ┌─is_return_row─┬─────rows─┬──matches─┐
1. │             0 │ 12527442 │ 12258258 │ -- 12.26 million
2. │             1 │   100166 │        0 │
   └───────────────┴──────────┴──────────┘
```

## 5. 全渠道销售：TotalCost 与 UnitCost × SalesQuantity 是否相等

```sql
SELECT count() AS rows, countIf(abs(TotalCost - UnitCost * SalesQuantity) < 0.005) AS matches, round(max(abs(TotalCost - UnitCost * SalesQuantity)), 4) AS max_gap FROM retail.FactSales
```

```
   ┌────rows─┬─matches─┬─max_gap─┐
1. │ 3406089 │ 3087009 │ 3311.88 │
   └─────────┴─────────┴─────────┘
```

## 6. 「是否打折」两种判定是否一致：PromotionKey != 1 与 DiscountAmount > 0

```sql
SELECT 'FactOnlineSales' AS t, count() AS rows, countIf(PromotionKey != 1) AS promo_not_1, countIf(DiscountAmount > 0) AS discount_gt_0, countIf((PromotionKey != 1) != (DiscountAmount > 0)) AS disagree FROM retail.FactOnlineSales UNION ALL SELECT 'FactSales', count(), countIf(PromotionKey != 1), countIf(DiscountAmount > 0), countIf((PromotionKey != 1) != (DiscountAmount > 0)) FROM retail.FactSales
```

```
   ┌─t───────────────┬─────rows─┬─promo_not_1─┬─discount_gt_0─┬─disagree─┐
1. │ FactOnlineSales │ 12627608 │     8727716 │       8727716 │        0 │
2. │ FactSales       │  3406089 │     2239789 │       1793112 │   446677 │
   └─────────────────┴──────────┴─────────────┴───────────────┴──────────┘
```

## 7. 折扣金额为 0 却挂了促销的行，是哪些促销

```sql
SELECT p.PromotionName, p.DiscountPercent, count() AS rows FROM retail.FactSales f JOIN retail.DimPromotion p ON f.PromotionKey = p.PromotionKey WHERE f.PromotionKey != 1 AND f.DiscountAmount = 0 GROUP BY p.PromotionName, p.DiscountPercent ORDER BY rows DESC LIMIT 10
```

```
   ┌─PromotionName──────────────────────────┬─DiscountPercent─┬──rows─┐
1. │ North America Back-to-School Promotion │             0.1 │ 85541 │
2. │ North America Spring Promotion         │            0.05 │ 83622 │
3. │ European Spring Promotion              │            0.07 │ 74877 │
4. │ North America Holiday Promotion        │             0.2 │ 57320 │
5. │ European Holiday Promotion             │             0.2 │ 43318 │
6. │ Asian Holiday Promotion                │            0.15 │ 30301 │
7. │ Asian Spring Promotion                 │             0.2 │ 29431 │
8. │ European Back-to-Scholl Promotion      │             0.1 │ 22369 │
9. │ Asian Summer Promotion                 │             0.1 │ 19898 │
   └────────────────────────────────────────┴─────────────────┴───────┘
```

## 8. 毛利：销售额 − 总成本，按渠道看合计与毛利率

```sql
SELECT c.ChannelName, round(sum(f.SalesAmount), 2) AS sales, round(sum(f.TotalCost), 2) AS cost, round(sum(f.SalesAmount) - sum(f.TotalCost), 2) AS gross_margin, round((sum(f.SalesAmount) - sum(f.TotalCost)) / sum(f.SalesAmount), 4) AS gm_pct FROM retail.FactSales f JOIN retail.DimChannel c ON f.channelKey = c.ChannelKey GROUP BY c.ChannelName ORDER BY sales DESC
```

```
   ┌─ChannelName─┬─────────sales─┬──────────cost─┬──gross_margin─┬─gm_pct─┐
1. │ Store       │ 6942853195.14 │ 2992579668.63 │ 3950273526.51 │  0.569 │
2. │ Online      │ 2677599035.07 │ 1163294363.13 │ 1514304671.94 │ 0.5655 │
3. │ Reseller    │ 1715197831.44 │  743558867.34 │   971638964.1 │ 0.5665 │
4. │ Catalog     │ 1078007547.23 │  465463702.68 │  612543844.55 │ 0.5682 │
   └─────────────┴───────────────┴───────────────┴───────────────┴────────┘
```

## 9. 退货率：退货数量 ÷ 销售数量，两张事实表各自的全量值

```sql
SELECT 'FactOnlineSales' AS t, sum(SalesQuantity) AS sales_qty, sum(ReturnQuantity) AS return_qty, round(sum(ReturnQuantity) / sum(SalesQuantity), 6) AS return_rate FROM retail.FactOnlineSales UNION ALL SELECT 'FactSales', sum(SalesQuantity), sum(ReturnQuantity), round(sum(ReturnQuantity) / sum(SalesQuantity), 6) FROM retail.FactSales
```

```
   ┌─t───────────────┬─sales_qty─┬─return_qty─┬─return_rate─┐
1. │ FactOnlineSales │  12527442 │     100166 │    0.007996 │
2. │ FactSales       │  53320454 │     493587 │    0.009257 │
   └─────────────────┴───────────┴────────────┴─────────────┘
```

## 10. 客单价：线上销售的销售额 ÷ 去重订单数

```sql
SELECT round(sum(SalesAmount), 2) AS sales, uniqExact(SalesOrderNumber) AS orders, round(sum(SalesAmount) / uniqExact(SalesOrderNumber), 4) AS avg_order_value FROM retail.FactOnlineSales
```

```
   ┌─────────sales─┬──orders─┬─avg_order_value─┐
1. │ 2718202629.81 │ 1674320 │       1623.4666 │
   └───────────────┴─────────┴─────────────────┘
```

## 11. 日均销售（约定 4）：先按天汇总再平均，节假日 vs 平日（2009 年，全渠道）

```sql
SELECT d.IsHoliday, count() AS days, round(sum(day_sales), 2) AS sales, round(avg(day_sales), 2) AS avg_daily_sales FROM (SELECT DateKey, sum(SalesAmount) AS day_sales FROM retail.FactSales WHERE DateKey BETWEEN '2009-01-01' AND '2009-12-31' GROUP BY DateKey) f JOIN retail.DimDate d ON f.DateKey = d.DateKey GROUP BY d.IsHoliday ORDER BY d.IsHoliday
```

```
   ┌─IsHoliday─┬─days─┬─────────sales─┬─avg_daily_sales─┐
1. │ No        │  261 │ 2678096950.77 │     10260907.86 │ -- 10.26 million
2. │ Yes       │  104 │ 1062386168.41 │     10215251.62 │ -- 10.22 million
   └───────────┴──────┴───────────────┴─────────────────┘
```

## 12. 事实表的日期是否连续覆盖（有没有一天都没有销售的日子）

```sql
SELECT 'FactSales' AS t, uniqExact(DateKey) AS fact_days, dateDiff('day', min(DateKey), max(DateKey)) + 1 AS span_days FROM retail.FactSales UNION ALL SELECT 'FactOnlineSales', uniqExact(DateKey), dateDiff('day', min(DateKey), max(DateKey)) + 1 FROM retail.FactOnlineSales
```

```
   ┌─t───────────────┬─fact_days─┬─span_days─┐
1. │ FactSales       │      1096 │      1096 │
2. │ FactOnlineSales │      1096 │      1096 │
   └─────────────────┴───────────┴───────────┘
```

## 13. 维度被用到的程度：各维度表有多少行从没出现在全渠道销售里

```sql
SELECT 'DimProduct' AS dim, count() AS dim_rows, countIf(ProductKey IN (SELECT ProductKey FROM retail.FactSales)) AS used FROM retail.DimProduct UNION ALL SELECT 'DimStore', count(), countIf(StoreKey IN (SELECT StoreKey FROM retail.FactSales)) FROM retail.DimStore UNION ALL SELECT 'DimPromotion', count(), countIf(PromotionKey IN (SELECT PromotionKey FROM retail.FactSales)) FROM retail.DimPromotion UNION ALL SELECT 'DimDate', count(), countIf(DateKey IN (SELECT DateKey FROM retail.FactSales)) FROM retail.DimDate UNION ALL SELECT 'DimProductSubcategory', count(), countIf(ProductSubcategoryKey IN ( SELECT toInt32(ProductSubcategoryKey) FROM retail.DimProduct WHERE ProductSubcategoryKey IS NOT NULL)) FROM retail.DimProductSubcategory
```

```
   ┌─dim───────────────────┬─dim_rows─┬─used─┐
1. │ DimProductSubcategory │       44 │   30 │
2. │ DimDate               │     2556 │ 1096 │
3. │ DimPromotion          │       28 │   28 │
4. │ DimProduct            │     2233 │ 2232 │
5. │ DimStore              │      306 │  306 │
   └───────────────────────┴──────────┴──────┘
```

## 14. 战略计划表能否挂到门店：DimStore.EntityKey 与计划表的 EntityKey 的重合

```sql
SELECT (SELECT uniqExact(EntityKey) FROM retail.FactStrategyPlan) AS plan_entities, (SELECT uniqExact(toInt64(EntityKey)) FROM retail.DimStore) AS store_entities, (SELECT count() FROM retail.FactStrategyPlan WHERE EntityKey NOT IN (SELECT toInt64(EntityKey) FROM retail.DimStore)) AS plan_rows_without_store
```

```
   ┌─plan_entities─┬─store_entities─┬─plan_rows_without_store─┐
1. │           306 │            306 │                       0 │
   └───────────────┴────────────────┴─────────────────────────┘
```

## 15. 三张表的「实际」口径是否互相对得上：全渠道销售额 vs 计划表 Actual/Sale Revenue vs 目标表 Actual

```sql
SELECT (SELECT round(sum(SalesAmount), 2) FROM retail.FactSales) AS factsales_total, (SELECT round(sum(p.Amount), 2) FROM retail.FactStrategyPlan p JOIN retail.DimAccount a ON p.AccountKey = a.AccountKey JOIN retail.DimScenario s ON p.ScenarioKey = s.ScenarioKey WHERE a.AccountName = 'Sale Revenue' AND s.ScenarioName = 'Actual') AS plan_actual_revenue, (SELECT round(sum(q.SalesAmountQuota), 2) FROM retail.FactSalesQuota q JOIN retail.DimScenario s ON q.ScenarioKey = s.ScenarioKey WHERE s.ScenarioName = 'Actual') AS quota_actual_amount
```

```
   ┌─factsales_total─┬─plan_actual_revenue─┬─quota_actual_amount─┐
1. │  12413657608.89 │      12413657608.89 │      12413657608.89 │ -- 12.41 billion
   └─────────────────┴─────────────────────┴─────────────────────┘
```

## 16. 销售目标表各渠道的预算目标（目标达成率按渠道算时要用）

```sql
SELECT c.ChannelName, round(sum(q.SalesAmountQuota), 2) AS budget_quota FROM retail.FactSalesQuota q JOIN retail.DimChannel c ON q.ChannelKey = c.ChannelKey JOIN retail.DimScenario s ON q.ScenarioKey = s.ScenarioKey WHERE s.ScenarioName = 'Budget' GROUP BY c.ChannelName ORDER BY budget_quota DESC
```

```
   ┌─ChannelName─┬──budget_quota─┐
1. │ Store       │ 5965123660.92 │ -- 5.97 billion
2. │ Online      │ 2305357130.68 │ -- 2.31 billion
3. │ Reseller    │ 1482013781.77 │ -- 1.48 billion
4. │ Catalog     │   914970790.3 │ -- 914.97 million
   └─────────────┴───────────────┘
```

## 17. 当前库存：最近一次快照的规模与金额

```sql
WITH latest AS ( SELECT StoreKey, ProductKey, max(DateKey) AS d FROM retail.FactInventory GROUP BY StoreKey, ProductKey) SELECT count() AS rows, sum(i.OnHandQuantity) AS on_hand, round(sum(i.OnHandQuantity * i.UnitCost), 2) AS on_hand_value, sum(i.OnOrderQuantity) AS on_order, countIf(i.OnHandQuantity < i.SafetyStockQuantity) AS below_safety_stock FROM retail.FactInventory i JOIN latest l ON i.StoreKey = l.StoreKey AND i.ProductKey = l.ProductKey AND i.DateKey = l.d
```

```
   ┌───rows─┬──on_hand─┬─on_hand_value─┬─on_order─┬─below_safety_stock─┐
1. │ 600241 │ 11897661 │ 1291296461.45 │   494285 │              89591 │
   └────────┴──────────┴───────────────┴──────────┴────────────────────┘
```

## 18. 库存的 Aging / DaysInStock 这些列是什么含义线索：与数量的关系

```sql
SELECT Aging, count() AS rows, round(avg(OnHandQuantity), 1) AS avg_on_hand, round(avg(DaysInStock), 1) AS avg_days_in_stock, round(min(MinDayInStock), 1) AS min_min, round(max(MaxDayInStock), 1) AS max_max FROM retail.FactInventory GROUP BY Aging ORDER BY Aging
```

```
   ┌─Aging─┬────rows─┬─avg_on_hand─┬─avg_days_in_stock─┬─min_min─┬─max_max─┐
1. │     1 │     121 │         7.3 │              28.1 │       6 │     119 │
2. │     2 │     943 │         8.5 │              29.2 │       5 │     119 │
3. │     3 │   18037 │         2.8 │              28.6 │       5 │     119 │
4. │     4 │    9960 │         9.6 │              28.3 │       5 │     119 │
5. │     5 │  362428 │         6.1 │              28.4 │       5 │     119 │
6. │     6 │ 2357475 │         7.8 │                62 │       5 │     119 │
7. │     7 │ 5264135 │          21 │              44.6 │       5 │     119 │
   └───────┴─────────┴─────────────┴───────────────────┴─────────┴─────────┘
```

## 19. 产品维度缺的那 284 个键是连续的一段还是散落的

```sql
SELECT min(k) AS min_missing, max(k) AS max_missing, count() AS missing_keys FROM ( SELECT DISTINCT ProductKey AS k FROM retail.FactSales WHERE ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct))
```

```
   ┌─min_missing─┬─max_missing─┬─missing_keys─┐
1. │         416 │        2497 │          284 │
   └─────────────┴─────────────┴──────────────┘
```

## 20. 缺行的产品键在各品类上有没有系统性（用线上销售的单价区间间接看）

```sql
SELECT count() AS orphan_rows, round(min(UnitPrice), 2) AS min_price, round(max(UnitPrice), 2) AS max_price, round(avg(UnitPrice), 2) AS avg_price FROM retail.FactOnlineSales WHERE ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)
```

```
   ┌─orphan_rows─┬─min_price─┬─max_price─┬─avg_price─┐
1. │     1715380 │      0.95 │       969 │     98.12 │
   └─────────────┴───────────┴───────────┴───────────┘
```

## 21. 门店类型与全渠道销售的关系：哪些类型的门店真的有销售

```sql
SELECT s.StoreType, count() AS stores, countIf(s.StoreKey IN (SELECT StoreKey FROM retail.FactSales)) AS with_sales, countIf(s.StoreKey IN (SELECT StoreKey FROM retail.FactOnlineSales)) AS with_online_sales FROM retail.DimStore s GROUP BY s.StoreType ORDER BY stores DESC
```

```
   ┌─StoreType─┬─stores─┬─with_sales─┬─with_online_sales─┐
1. │ Store     │    299 │        299 │                 0 │
2. │ Reseller  │      3 │          3 │                 0 │
3. │ Online    │      3 │          3 │                 3 │
4. │ Catalog   │      1 │          1 │                 0 │
   └───────────┴────────┴────────────┴───────────────────┘
```

## 22. 门店的开关店状态：Status 与 CloseDate 的配合

```sql
SELECT Status, CloseDate = '2090-12-31' AS never_closed, count() AS stores FROM retail.DimStore GROUP BY Status, never_closed ORDER BY stores DESC
```

```
   ┌─Status─┬─never_closed─┬─stores─┐
1. │ On     │            1 │    294 │
2. │ Off    │            0 │     12 │
   └────────┴──────────────┴────────┘
```

