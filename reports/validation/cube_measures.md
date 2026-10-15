# Cube 指标的 SQL 在 chDB 上的核对（T10）

由 `uv run python render/verify_cube.py` 生成。Cube 本身在 T16 才跑；这里核对的是模型交给引擎的
ClickHouse SQL：每个 cube 的 `sql` 与每个指标的聚合表达式（含 filters），按 Cube 对普通聚合的编法
拼成一条查询在 chDB 上执行。

## 一、与 source.yaml 记录的全量值比对

| 指标 | 条件 | 期望 | 实际 | 相对误差 | 出处 | 结果 |
|---|---|---|---|---|---|---|
| `online_sales.sales_amount` | 全量 | 2.7182e+09 | 2.7182e+09 | 6.68e-13 | FactOnlineSales.differs_from | 通过 |
| `sales.sales_amount` | 全量 | 1.24137e+10 | 1.24137e+10 | 2.23e-12 | FactSales.SalesAmount | 通过 |
| `online_sales.return_rate` | 全量 | 0.007996 | 0.00799573 | 3.42e-05 | 退货率.note | 通过 |
| `sales.return_rate` | 全量 | 0.009257 | 0.00925699 | 8.97e-07 | 退货率.note | 通过 |
| `online_sales.order_count` | 全量 | 1.67432e+06 | 1.67432e+06 | 0.00e+00 | 订单数.note | 通过 |
| `online_sales.order_line_count` | 全量 | 1.26276e+07 | 1.26276e+07 | 0.00e+00 | FactOnlineSales.rows | 通过 |
| `online_sales.lines_per_order` | 全量 | 7.542 | 7.54193 | 8.98e-06 | 每单行数.note | 通过 |
| `online_sales.average_order_value` | 全量 | 1,623.47 | 1,623.47 | 1.18e-08 | 客单价.note | 通过 |
| `online_sales.customer_count` | 全量 | 18,869 | 18,869 | 0.00e+00 | 客户数.note | 通过 |
| `online_sales.active_customer_count` | 全量 | 16,890 | 16,890 | 0.00e+00 | 活跃客户数.note | 通过 |
| `online_sales.at_risk_customer_count` | 全量 | 1,841 | 1,841 | 0.00e+00 | 有流失风险客户数.note | 通过 |
| `online_sales.churned_customer_count` | 全量 | 138 | 138 | 0.00e+00 | 已流失客户数.note | 通过 |
| `sales.store_count` | 全量 | 306 | 306 | 0.00e+00 | 门店数.note | 通过 |
| `sales.average_daily_sales_amount` | 2009 平日 | 1.02609e+07 | 1.02609e+07 | 2.58e-10 | 日均销售额.note（2009 平日） | 通过 |
| `inventory.current_on_hand_quantity` | 全量 | 1.18977e+07 | 1.18977e+07 | 0.00e+00 | 当前在手库存数量.note | 通过 |
| `inventory.current_on_hand_value` | 全量 | 1.2913e+09 | 1.2913e+09 | 1.85e-16 | 当前在手库存金额.note | 通过 |
| `inventory.current_on_order_quantity` | 全量 | 494,285 | 494,285 | 0.00e+00 | 当前在订库存数量.note | 通过 |
| `inventory.below_safety_stock_count` | 全量 | 89,591 | 89,591 | 0.00e+00 | 低于安全库存的门店产品数.note | 通过 |
| `inventory.store_product_pair_count` | 全量 | 600,241 | 600,241 | 0.00e+00 | 门店产品组合数.note | 通过 |
| `sales_quota.sales_amount_quota` | 全量 | 1.06675e+10 | 1.06675e+10 | 7.49e-14 | 目标销售额.note | 通过 |
| `sales_quota.sales_quantity_quota` | 全量 | 4.43001e+07 | 4.43001e+07 | 0.00e+00 | 目标销量.note | 通过 |
| `sales_quota.quota_attainment_pct` | 2009 | 1.21256 | 1.21256 | 2.11e-12 | 目标达成率.note（2009） | 通过 |
| `strategy_plan.plan_revenue` | 全量 | 1.15487e+10 | 1.15487e+10 | 6.94e-14 | 计划收入.note | 通过 |
| `it_machine.it_cost` | 全量 | 2.40766e+08 | 2.40766e+08 | 0.00e+00 | IT 成本.note | 通过 |
| `it_sla.down_time` | 全量 | 396,699 | 396,699 | 0.00e+00 | 停机时长.note | 通过 |
| `it_sla.outage_count` | 全量 | 4,925 | 4,925 | 0.00e+00 | 故障次数.note | 通过 |

## 二、与源表上同一口径的直接查询比对

这几项检查 UNION ALL 拼出来的 cube（库存、销售目标）没有让额外的行混进指标，以及同店、新客的写法。

| 指标 | 直接查询 | 实际 | 期望 | 结果 |
|---|---|---|---|---|
| `inventory.snapshot_on_hand_quantity` | `SELECT sum(OnHandQuantity) FROM retail.FactInventory` | 131,294,094 | 131,294,094 | 通过 |
| `inventory.snapshot_on_hand_value` | `SELECT sum(OnHandQuantity * UnitCost) FROM retail.FactInventory` | 1.511456831e+10 | 1.511456831e+10 | 通过 |
| `inventory.snapshot_below_safety_stock_count` | `SELECT countIf(OnHandQuantity < SafetyStockQuantity) FROM retail.FactInventory` | 1,113,941 | 1,113,941 | 通过 |
| `sales_quota.gross_margin_quota` | `SELECT sum(GrossMarginQuota) FROM retail.FactSalesQuota WHERE ScenarioKey = (SELECT ScenarioKey FROM retail.DimScenario WHERE ScenarioName = 'Budget')` | 5,788,481,063 | 5,788,481,063 | 通过 |
| `inventory.inventory_turnover` | `SELECT (SELECT sum(TotalCost) FROM retail.FactSales) / (SELECT sum(OnHandQuantity * UnitCost) / uniqExact(DateKey) FROM retail.FactInventory)` | 55.37199955 | 55.37199955 | 通过 |
| `sales.same_store_sales_amount` | `SELECT sum(SalesAmount) FROM retail.FactSales AS f WHERE (StoreKey, toYear(DateKey) - 1) IN (SELECT DISTINCT StoreKey, toYear(DateKey) FROM retail.FactSales)` | 7,830,394,634 | 7,830,394,634 | 通过 |
| `online_sales.new_customer_count` | `SELECT uniqExactIf(CustomerKey, first >= toDate('2009-12-31') - 89) FROM (SELECT CustomerKey, min(DateKey) AS first FROM retail.FactOnlineSales GROUP BY CustomerKey)` | 1 | 1 | 通过 |

## 三、全部指标能否执行

每个非多阶段指标都编译成一条全量查询执行一次，不报错即通过。

执行 88 个，报错 0 个。

多阶段指标（time_shift / group_by，由 Cube 规划，这里不核对，留给 T16）：14 个

- `online_sales.sales_amount_yoy_pct`
- `online_sales.sales_amount_prior_year`
- `online_sales.sales_amount_mom_pct`
- `online_sales.sales_amount_prior_month`
- `online_sales.sales_amount_share`
- `online_sales.sales_amount_in_scope`
- `sales.sales_amount_yoy_pct`
- `sales.sales_amount_prior_year`
- `sales.sales_amount_mom_pct`
- `sales.sales_amount_prior_month`
- `sales.sales_amount_share`
- `sales.sales_amount_in_scope`
- `sales.same_store_sales_growth_pct`
- `sales.same_store_base_prior_year`

**结论：全部通过**
