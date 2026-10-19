# 通用交付检查（b）：覆盖表

- 生成：`uv run python render/check_conventions.py`（只读 `build/contexts/` 与 `semantic/`，不读题库，不开 chDB，不调模型）。引用检查（a）见 `render/check_references.py`。
- 依据：`decisions/2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md` 第一节第 3 条、第三节第 3 条。

## 1. 约定 × 档位

每格：判定 · 锚点（约定的 `applies_to_datasets` 在本单元有落点的个数）· 点名它的表 / 视图 / 指标个数。
判定：**对象** = 有可见的表或视图在自己的说明里点名这条约定，或（L1.5S 以外）它的锚点全部可见；**仅指标** = 只有指标文字点名；**仅条文** = 只有条文本身。L1.5S 的锚点按血缘算：维度表 → 建在它上面的 `ads.dim_*`，事实表 → 由它汇总出的 `ads` 表。

| 约定 | 组 | SQL-L1 | SQL-L1.5W | SQL-L1.5S | SQL-L2 |
|---|---|---|---|---|---|
| 1 | 渠道与事实表 | ✅ 对象 · 锚 1/1 · 表 1·指标 2 | ✅ 对象 · 锚 1/1 · 表 1·视图 1·指标 2 | ✅ 对象 · 锚 1/1 · 表 12·指标 1 | ✅ 对象 · 锚 1/1 · 表 1·指标 2（可调用 2） |
| 2 | 渠道与事实表 | ✅ 对象 · 锚 1/1 · 表 4·指标 3 | ✅ 对象 · 锚 1/1 · 表 4·视图 1·指标 3 | ✅ 对象 · 锚 1/1 · 表 8·指标 2 | ✅ 对象 · 锚 1/1 · 表 4·指标 3（可调用 3） |
| 3 | 时间 | ✅ 对象 · 锚 3/3 · 表 0·指标 2 | ✅ 对象 · 锚 3/3 · 表 0·视图 1·指标 2 | ✅ 对象 · 锚 3/3 · 表 16·指标 1 | ✅ 对象 · 锚 3/3 · 表 0·指标 2（可调用 2） |
| 4 | 时间 | ✅ 对象 · 锚 1/1 · 表 1·指标 2 | ✅ 对象 · 锚 1/1 · 表 1·视图 0·指标 2 | ✅ 对象 · 锚 1/1 · 表 8·指标 1 | ✅ 对象 · 锚 1/1 · 表 1·指标 2（可调用 2） |
| 5 | 地理与币种 | ✅ 对象 · 锚 3/3 · 表 4·指标 0 | ✅ 对象 · 锚 3/3 · 表 4·视图 1·指标 0 | ✅ 对象 · 锚 2/3 · 表 5·指标 0 | ✅ 对象 · 锚 3/3 · 表 4·指标 0（可调用 0） |
| 6 | 地理与币种 | ✅ 对象 · 锚 6/6 · 表 4·指标 0 | ✅ 对象 · 锚 6/6 · 表 4·视图 0·指标 0 | ❌ 仅条文 · 锚 5/6 · 表 0·指标 0 | ✅ 对象 · 锚 6/6 · 表 4·指标 0（可调用 0） |
| 7 | 口径与业务词 | ✅ 对象 · 锚 0/0 · 表 2·指标 6 | ✅ 对象 · 锚 0/0 · 表 2·视图 2·指标 6 | ✅ 对象 · 锚 0/0 · 表 12·指标 5 | ✅ 对象 · 锚 0/0 · 表 2·指标 6（可调用 6） |
| 8 | 口径与业务词 | ✅ 对象 · 锚 1/1 · 表 1·指标 2 | ✅ 对象 · 锚 1/1 · 表 1·视图 1·指标 2 | ✅ 对象 · 锚 1/1 · 表 4·指标 2 | ✅ 对象 · 锚 1/1 · 表 1·指标 2（可调用 2） |
| 9 | 口径与业务词 | ✅ 对象 · 锚 1/1 · 表 2·指标 3 | ✅ 对象 · 锚 1/1 · 表 2·视图 1·指标 3 | ✅ 对象 · 锚 1/1 · 表 1·指标 3 | ✅ 对象 · 锚 1/1 · 表 2·指标 3（可调用 3） |
| 10 | 口径与业务词 | ✅ 对象 · 锚 1/1 · 表 3·指标 5 | ✅ 对象 · 锚 1/1 · 表 3·视图 2·指标 5 | ✅ 对象 · 锚 1/1 · 表 5·指标 4 | ✅ 对象 · 锚 1/1 · 表 3·指标 5（可调用 5） |
| 11 | 库存、计划与销售目标 | ✅ 对象 · 锚 1/1 · 表 1·指标 11 | ✅ 对象 · 锚 1/1 · 表 1·视图 1·指标 11 | ✅ 对象 · 锚 1/1 · 表 2·指标 2 | ✅ 对象 · 锚 1/1 · 表 1·指标 11（可调用 11） |
| 12 | 库存、计划与销售目标 | ✅ 对象 · 锚 4/4 · 表 6·指标 7 | ✅ 对象 · 锚 4/4 · 表 6·视图 2·指标 7 | ✅ 对象 · 锚 4/4 · 表 5·指标 5 | ✅ 对象 · 锚 4/4 · 表 6·指标 7（可调用 7） |
| 13 | 客户 | ✅ 对象 · 锚 2/2 · 表 1·指标 4 | ✅ 对象 · 锚 2/2 · 表 1·视图 0·指标 4 | ✅ 对象 · 锚 2/2 · 表 1·指标 4 | ✅ 对象 · 锚 2/2 · 表 1·指标 4（可调用 4） |
| 14 | 客户 | ✅ 对象 · 锚 2/2 · 表 1·指标 3 | ✅ 对象 · 锚 2/2 · 表 1·视图 0·指标 3 | ✅ 对象 · 锚 2/2 · 表 1·指标 2 | ✅ 对象 · 锚 2/2 · 表 1·指标 3（可调用 3） |
| 15 | 客户 | ✅ 对象 · 锚 2/2 · 表 0·指标 2 | ✅ 对象 · 锚 2/2 · 表 0·视图 0·指标 2 | ✅ 对象 · 锚 2/2 · 表 1·指标 2 | ✅ 对象 · 锚 2/2 · 表 0·指标 2（可调用 2） |

DAX 与 JSON 单元：逐格与对应的 SQL 单元相同的有 3/3 个（DAX-L1 = SQL-L1、DAX-L2 = SQL-L2、JSON-L2 = SQL-L2）。

### L1 的配套说明在各档位是否还在

L1 的 data_quality、多路径默认、关系用途里点名某条约定的条目，在本单元出现的条数。

| 约定 | SQL-L1 | SQL-L1.5W | SQL-L1.5S | SQL-L2 |
|---|---|---|---|---|
| 1 | 1 | 1 | 0 | 1 |
| 2 | 5 | 5 | 0 | 5 |
| 4 | 1 | 1 | 0 | 1 |
| 5 | 5 | 5 | 0 | 5 |
| 6 | 2 | 2 | 0 | 2 |
| 10 | 3 | 3 | 0 | 3 |
| 11 | 1 | 1 | 0 | 1 |
| 12 | 2 | 2 | 0 | 2 |
| 14 | 1 | 1 | 0 | 1 |

### L1.5S：点名约定的汇总表

| 约定 | 锚点的落点 | 点名它的汇总表 / 维度视图 | 点名它的指标 |
|---|---|---|---|
| 1 | FactOnlineSales → `ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 | `ads_online_customer_month_tier`、`ads_online_customer_profile_quarter`、`ads_online_week_store` 等 12 个 | `销售额` |
| 2 | FactSales → `ads_promotion_month_channel`、`ads_quota_month_channel_store_category` 等 8 个 | `ads_promotion_month_channel`、`ads_quota_month_channel_store_category`、`ads_sales_day_store` 等 8 个 | `销售额`、`同店销售额` |
| 3 | DimDate → `dim_date`；FactSales → `ads_promotion_month_channel`、`ads_quota_month_channel_store_category` 等 8 个；FactOnlineSales → `ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 | `ads_inventory_week_store_category`、`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 16 个 | `销售额同比增长率` |
| 4 | DimDate → `dim_date` | `ads_online_week_store`、`ads_online_week_total`、`ads_sales_day_store` 等 8 个 | `日均销售额` |
| 5 | DimGeography → —；DimCustomer → `dim_customer`；DimStore → `dim_store` | `ads_online_customer_profile_quarter`、`ads_sales_month_store`、`ads_sales_week_channel_country` 等 5 个 | — |
| 6 | FactOnlineSales → `ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个；FactSales → `ads_promotion_month_channel`、`ads_quota_month_channel_store_category` 等 8 个；FactInventory → `ads_inventory_current_store_category`、`ads_inventory_week_store_category`；FactSalesQuota → `ads_quota_month_channel_store_category`；FactStrategyPlan → `ads_plan_month_category_account`、`ads_plan_month_store_account`；DimCurrency → — | — | — |
| 7 | —（无 applies_to） | `ads_online_customer_month_tier`、`ads_online_customer_profile_quarter`、`ads_online_week_store` 等 12 个 | `销售额`、`净销售额`、`退货率` 等 5 个 |
| 8 | FactOnlineSales → `ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 | `ads_online_customer_month_tier`、`ads_online_customer_profile_quarter`、`ads_online_week_store` 等 4 个 | `订单数`、`客单价` |
| 9 | DimProduct → `dim_product` | `dim_product` | `产品标价`、`产品单位成本`、`产品利润率` |
| 10 | DimPromotion → `dim_promotion` | `ads_online_week_store`、`ads_promotion_month_channel`、`ads_sales_month_channel` 等 5 个 | `折扣金额`、`折扣数量`、`折扣率` 等 4 个 |
| 11 | FactInventory → `ads_inventory_current_store_category`、`ads_inventory_week_store_category` | `ads_inventory_current_store_category`、`ads_inventory_week_store_category` | `当前在手库存数量`、`当前在手库存金额` |
| 12 | FactStrategyPlan → `ads_plan_month_category_account`、`ads_plan_month_store_account`；FactSalesQuota → `ads_quota_month_channel_store_category`；DimScenario → `dim_scenario`；DimAccount → `dim_account` | `ads_plan_month_category_account`、`ads_plan_month_store_account`、`ads_quota_month_channel_store_category` 等 5 个 | `目标销售额`、`目标销量`、`目标达成率` 等 5 个 |
| 13 | DimCustomer → `dim_customer`；FactOnlineSales → `ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 | `ads_online_customer_month_tier` | `客户最近购买月数`、`活跃客户数`、`有流失风险客户数` 等 4 个 |
| 14 | DimCustomer → `dim_customer`；FactOnlineSales → `ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 | `ads_online_customer_month_tier` | `新客数`、`新客销售额` |
| 15 | FactSales → `ads_promotion_month_channel`、`ads_quota_month_channel_store_category` 等 8 个；DimStore → `dim_store` | `ads_sales_year_store` | `同店销售额`、`同店销售额增长率` |

### L1.5S：选表约定（1、2）在每张销售汇总表上

由线上销售（FactOnlineSales）汇总的表要点名约定 1，由全渠道销售（FactSales）汇总的表要点名约定 2，模型才能从表本身看出这是哪一种「销售」。

| 汇总表 | 应点名 | 已点名 |
|---|---|---|
| `ads_online_customer_month_tier` | 约定 1 | ✅ |
| `ads_online_customer_profile_quarter` | 约定 1 | ✅ |
| `ads_online_week_store` | 约定 1 | ✅ |
| `ads_online_week_total` | 约定 1 | ✅ |
| `ads_promotion_month_channel` | 约定 2 | ✅ |
| `ads_quota_month_channel_store_category` | 约定 2 | ✅ |
| `ads_sales_day_store` | 约定 2 | ✅ |
| `ads_sales_month_channel` | 约定 2 | ✅ |
| `ads_sales_month_product` | 约定 2 | ✅ |
| `ads_sales_month_store` | 约定 2 | ✅ |
| `ads_sales_week_channel_country` | 约定 2 | ✅ |
| `ads_sales_year_store` | 约定 2 | ✅ |

## 2. 汇总表 × 指标层

L2 的 92 个可调用对象（指标 × 数据集），对照由同一数据集汇总出的 `ads` 表：直接存有 43 个，可由一张表里的分子分母现算 22 个，维度指标落在维度视图上 3 个，未自动匹配 24 个。
「现算」按名字匹配分子分母（指标名或列名），是启发式。**「未自动匹配」不等于汇总层答不了**：其中有靠筛选列得到的（如客户分层、是否新客，表说明里写了「不另设列」），也有跨期、跨行才能算的（同比、环比、占比、同店），还有汇总层确实没有的数据（IT 成本、停机）。逐个能否回答要人工看，覆盖内外以 T06 的覆盖标注为准。

| 指标 | 数据集 | 可加性 | Cube | DAX | 汇总层 |
|---|---|---|---|---|---|
| 销售额 | FactOnlineSales | 可加 | `online_sales.sales_amount` | `[Sales Amount]` | 直接：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 销售额 | FactSales | 可加 | `sales.sales_amount` | `[All Channel Sales Amount]` | 直接：`ads_promotion_month_channel`、`ads_quota_month_channel_store_category` 等 8 个 |
| 销售数量 | FactOnlineSales | 可加 | `online_sales.sales_quantity` | `[Sales Quantity]` | 直接：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 销售数量 | FactSales | 可加 | `sales.sales_quantity` | `[All Channel Sales Quantity]` | 直接：`ads_promotion_month_channel`、`ads_quota_month_channel_store_category` 等 8 个 |
| 总成本 | FactOnlineSales | 可加 | `online_sales.total_cost` | `[Total Cost]` | 直接：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 总成本 | FactSales | 可加 | `sales.total_cost` | `[All Channel Total Cost]` | 直接：`ads_promotion_month_channel`、`ads_quota_month_channel_store_category` 等 8 个 |
| 平均单价 | FactOnlineSales | 比率 | `online_sales.average_unit_price` | `[Average Unit Price]` | 现算：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 平均单价 | FactSales | 比率 | `sales.average_unit_price` | `[All Channel Average Unit Price]` | 现算：`ads_promotion_month_channel`、`ads_quota_month_channel_store_category` 等 8 个 |
| 退货金额 | FactOnlineSales | 可加 | `online_sales.return_amount` | `[Return Amount]` | 直接：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 退货金额 | FactSales | 可加 | `sales.return_amount` | `[All Channel Return Amount]` | 直接：`ads_sales_day_store`、`ads_sales_month_channel` 等 6 个 |
| 退货数量 | FactOnlineSales | 可加 | `online_sales.return_quantity` | `[Return Quantity]` | 直接：`ads_online_week_store`、`ads_online_week_total` |
| 退货数量 | FactSales | 可加 | `sales.return_quantity` | `[All Channel Return Quantity]` | 直接：`ads_sales_day_store`、`ads_sales_month_channel` 等 5 个 |
| 净销售额 | FactOnlineSales | 可加 | `online_sales.net_sales_amount` | `[Net Sales Amount]` | 直接：`ads_online_customer_month_tier`、`ads_online_week_store` 等 3 个 |
| 净销售额 | FactSales | 可加 | `sales.net_sales_amount` | `[All Channel Net Sales Amount]` | 直接：`ads_sales_day_store`、`ads_sales_month_channel` 等 4 个 |
| 退货率 | FactOnlineSales | 比率 | `online_sales.return_rate` | `[Return Rate]` | 现算：`ads_online_week_store`、`ads_online_week_total` |
| 退货率 | FactSales | 比率 | `sales.return_rate` | `[All Channel Return Rate]` | 现算：`ads_sales_day_store`、`ads_sales_month_channel` 等 5 个 |
| 折扣金额 | FactOnlineSales | 可加 | `online_sales.discount_amount` | `[Discount Amount]` | 直接：`ads_online_week_store`、`ads_online_week_total` |
| 折扣金额 | FactSales | 可加 | `sales.discount_amount` | `[All Channel Discount Amount]` | 直接：`ads_promotion_month_channel`、`ads_sales_day_store` 等 5 个 |
| 折扣数量 | FactOnlineSales | 可加 | `online_sales.discount_quantity` | `[Discount Quantity]` | 未自动匹配 |
| 折扣数量 | FactSales | 可加 | `sales.discount_quantity` | `[All Channel Discount Quantity]` | 直接：`ads_promotion_month_channel` |
| 折扣前原价 | FactOnlineSales | 可加 | `online_sales.list_amount_before_discount` | `[List Amount Before Discount]` | 直接：`ads_online_week_store` |
| 折扣前原价 | FactSales | 可加 | `sales.list_amount_before_discount` | `[All Channel List Amount Before Discount]` | 直接：`ads_promotion_month_channel`、`ads_sales_month_channel` 等 3 个 |
| 折扣率 | FactOnlineSales | 比率 | `online_sales.discount_rate` | `[Discount Rate]` | 现算：`ads_online_week_store` |
| 折扣率 | FactSales | 比率 | `sales.discount_rate` | `[All Channel Discount Rate]` | 现算：`ads_promotion_month_channel`、`ads_sales_month_channel` 等 3 个 |
| 打折销售额 | FactOnlineSales | 可加 | `online_sales.discounted_sales_amount` | `[Discounted Sales Amount]` | 直接：`ads_online_week_store` |
| 打折销售额 | FactSales | 可加 | `sales.discounted_sales_amount` | `[All Channel Discounted Sales Amount]` | 直接：`ads_sales_month_channel`、`ads_sales_month_product` |
| 打折销售额占比 | FactOnlineSales | 比率 | `online_sales.discounted_sales_share` | `[Discounted Sales Share]` | 现算：`ads_online_week_store` |
| 打折销售额占比 | FactSales | 比率 | `sales.discounted_sales_share` | `[All Channel Discounted Sales Share]` | 现算：`ads_sales_month_channel`、`ads_sales_month_product` |
| 毛利 | FactOnlineSales | 可加 | `online_sales.gross_margin` | `[Gross Margin]` | 直接：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 毛利 | FactSales | 可加 | `sales.gross_margin` | `[All Channel Gross Margin]` | 直接：`ads_promotion_month_channel`、`ads_sales_day_store` 等 7 个 |
| 毛利率 | FactOnlineSales | 比率 | `online_sales.gross_margin_pct` | `[Gross Margin %]` | 现算：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 毛利率 | FactSales | 比率 | `sales.gross_margin_pct` | `[All Channel Gross Margin %]` | 现算：`ads_promotion_month_channel`、`ads_sales_day_store` 等 7 个 |
| 订单数 | FactOnlineSales | 去重 | `online_sales.order_count` | `[Order Count]` | 直接：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 订单行数 | FactOnlineSales | 可加 | `online_sales.order_line_count` | `[Order Line Count]` | 直接：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 每单行数 | FactOnlineSales | 比率 | `online_sales.lines_per_order` | `[Lines per Order]` | 现算：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 客单价 | FactOnlineSales | 比率 | `online_sales.average_order_value` | `[Average Order Value]` | 现算：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 客户数 | FactOnlineSales | 去重 | `online_sales.customer_count` | `[Customer Count]` | 直接：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 客均销售额 | FactOnlineSales | 比率 | `online_sales.sales_per_customer` | `[Sales per Customer]` | 现算：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 客均订单数 | FactOnlineSales | 比率 | `online_sales.orders_per_customer` | `[Orders per Customer]` | 现算：`ads_online_customer_month_tier`、`ads_online_customer_profile_quarter` 等 4 个 |
| 客户最近购买月数 | FactOnlineSales | 比率 | `online_sales.customer_recency_months` | `[Customer Recency Months]` | 未自动匹配 |
| 活跃客户数 | FactOnlineSales | 去重 | `online_sales.active_customer_count` | `[Active Customer Count]` | 未自动匹配 |
| 有流失风险客户数 | FactOnlineSales | 去重 | `online_sales.at_risk_customer_count` | `[At Risk Customer Count]` | 未自动匹配 |
| 已流失客户数 | FactOnlineSales | 去重 | `online_sales.churned_customer_count` | `[Churned Customer Count]` | 未自动匹配 |
| 新客数 | FactOnlineSales | 去重 | `online_sales.new_customer_count` | `[New Customer Count]` | 未自动匹配 |
| 新客销售额 | FactOnlineSales | 可加 | `online_sales.new_customer_sales_amount` | `[New Customer Sales Amount]` | 未自动匹配 |
| 新客销售额占比 | FactOnlineSales | 比率 | `online_sales.new_customer_sales_share` | `[New Customer Sales Share]` | 未自动匹配 |
| 有销售天数 | FactSales | 去重 | `sales.selling_day_count` | `[Selling Day Count]` | 直接：`ads_sales_month_channel`、`ads_sales_month_store` 等 4 个 |
| 有销售天数 | FactOnlineSales | 去重 | `online_sales.selling_day_count` | `[Online Selling Day Count]` | 直接：`ads_online_week_store`、`ads_online_week_total` |
| 日均销售额 | FactSales | 比率 | `sales.average_daily_sales_amount` | `[Average Daily Sales Amount]` | 现算：`ads_sales_month_channel`、`ads_sales_month_store` 等 4 个 |
| 日均销售额 | FactOnlineSales | 比率 | `online_sales.average_daily_sales_amount` | `[Online Average Daily Sales Amount]` | 现算：`ads_online_week_store`、`ads_online_week_total` |
| 日均销售数量 | FactSales | 比率 | `sales.average_daily_sales_quantity` | `[Average Daily Sales Quantity]` | 现算：`ads_sales_month_channel`、`ads_sales_month_store` 等 4 个 |
| 日均销售数量 | FactOnlineSales | 比率 | `online_sales.average_daily_sales_quantity` | `[Online Average Daily Sales Quantity]` | 现算：`ads_online_week_store`、`ads_online_week_total` |
| 门店数 | FactSales | 去重 | `sales.store_count` | `[Store Count]` | 直接：`ads_sales_month_channel`、`ads_sales_week_channel_country` |
| 产品数 | FactSales | 去重 | `sales.product_count` | `[Product Count]` | 直接：`ads_sales_month_channel`、`ads_sales_month_product` 等 3 个 |
| 产品数 | FactOnlineSales | 去重 | `online_sales.product_count` | `[Online Product Count]` | 未自动匹配 |
| 店均销售额 | FactSales | 比率 | `sales.sales_per_store` | `[Sales per Store]` | 现算：`ads_sales_month_channel`、`ads_sales_week_channel_country` |
| 坪效 | FactSales | 比率 | `sales.sales_per_selling_area` | `[Sales per Selling Area]` | 现算：`ads_sales_month_store` |
| 门店人均销售额 | FactSales | 比率 | `sales.sales_per_store_employee` | `[Sales per Store Employee]` | 现算：`ads_sales_month_store` |
| 销售额同比增长率 | FactSales | 比率 | `sales.sales_amount_yoy_pct` | `[Sales Amount YoY %]` | 未自动匹配 |
| 销售额同比增长率 | FactOnlineSales | 比率 | `online_sales.sales_amount_yoy_pct` | `[Online Sales Amount YoY %]` | 未自动匹配 |
| 销售额环比增长率 | FactSales | 比率 | `sales.sales_amount_mom_pct` | `[Sales Amount MoM %]` | 未自动匹配 |
| 销售额环比增长率 | FactOnlineSales | 比率 | `online_sales.sales_amount_mom_pct` | `[Online Sales Amount MoM %]` | 未自动匹配 |
| 销售额占比 | FactSales | 比率 | `sales.sales_amount_share` | `[Sales Amount Share]` | 未自动匹配 |
| 销售额占比 | FactOnlineSales | 比率 | `online_sales.sales_amount_share` | `[Online Sales Amount Share]` | 未自动匹配 |
| 同店销售额 | FactSales | 可加 | `sales.same_store_sales_amount` | `[Same Store Sales Amount]` | 未自动匹配 |
| 同店销售额增长率 | FactSales | 比率 | `sales.same_store_sales_growth_pct` | `[Same Store Sales Growth %]` | 未自动匹配 |
| 产品标价 | DimProduct | 比率 | `product.list_price` | `[Product List Price]` | 维度视图：`dim_product` |
| 产品单位成本 | DimProduct | 比率 | `product.unit_cost` | `[Product Unit Cost]` | 维度视图：`dim_product` |
| 产品利润率 | DimProduct | 比率 | `product.margin_pct` | `[Product Margin %]` | 维度视图：`dim_product` |
| 当前在手库存数量 | FactInventory | 半可加 | `inventory.current_on_hand_quantity` | `[Current On Hand Quantity]` | 直接：`ads_inventory_current_store_category` |
| 当前在手库存金额 | FactInventory | 半可加 | `inventory.current_on_hand_value` | `[Current On Hand Value]` | 直接：`ads_inventory_current_store_category` |
| 当前在订库存数量 | FactInventory | 半可加 | `inventory.current_on_order_quantity` | `[Current On Order Quantity]` | 直接：`ads_inventory_current_store_category` |
| 当前安全库存数量 | FactInventory | 半可加 | `inventory.current_safety_stock_quantity` | `[Current Safety Stock Quantity]` | 直接：`ads_inventory_current_store_category` |
| 低于安全库存的门店产品数 | FactInventory | 去重 | `inventory.below_safety_stock_count` | `[Below Safety Stock Count]` | 直接：`ads_inventory_current_store_category` |
| 快照日在手库存数量 | FactInventory | 半可加 | `inventory.snapshot_on_hand_quantity` | `[Snapshot On Hand Quantity]` | 直接：`ads_inventory_week_store_category` |
| 快照日在订库存数量 | FactInventory | 半可加 | `inventory.snapshot_on_order_quantity` | `[Snapshot On Order Quantity]` | 直接：`ads_inventory_week_store_category` |
| 快照日安全库存数量 | FactInventory | 半可加 | `inventory.snapshot_safety_stock_quantity` | `[Snapshot Safety Stock Quantity]` | 直接：`ads_inventory_week_store_category` |
| 快照日低于安全库存的门店产品数 | FactInventory | 去重 | `inventory.snapshot_below_safety_stock_count` | `[Snapshot Below Safety Stock Count]` | 直接：`ads_inventory_week_store_category` |
| 门店产品组合数 | FactInventory | 去重 | `inventory.store_product_pair_count` | `[Store Product Pair Count]` | 直接：`ads_inventory_current_store_category` |
| 快照日在手库存金额 | FactInventory | 半可加 | `inventory.snapshot_on_hand_value` | `[Snapshot On Hand Value]` | 直接：`ads_inventory_week_store_category` |
| 平均在手库存金额 | FactInventory | 比率 | `inventory.average_on_hand_value` | `[Average On Hand Value]` | 未自动匹配 |
| 库存周转率 | FactInventory | 比率 | `inventory.inventory_turnover` | `[Inventory Turnover]` | 未自动匹配 |
| 目标销售额 | FactSalesQuota | 可加 | `sales_quota.sales_amount_quota` | `[Sales Amount Quota]` | 直接：`ads_quota_month_channel_store_category` |
| 目标销量 | FactSalesQuota | 可加 | `sales_quota.sales_quantity_quota` | `[Sales Quantity Quota]` | 直接：`ads_quota_month_channel_store_category` |
| 目标毛利 | FactSalesQuota | 可加 | `sales_quota.gross_margin_quota` | `[Gross Margin Quota]` | 直接：`ads_quota_month_channel_store_category` |
| 目标达成率 | FactSales | 比率 | `sales_quota.quota_attainment_pct` | `[Quota Attainment %]` | 现算：`ads_quota_month_channel_store_category` |
| 目标差异 | FactSales | 可加 | `sales_quota.quota_variance` | `[Quota Variance]` | 未自动匹配 |
| 计划金额 | FactStrategyPlan | 可加 | `strategy_plan.plan_amount` | `[Plan Amount]` | 直接：`ads_plan_month_category_account`、`ads_plan_month_store_account` |
| 计划收入 | FactStrategyPlan | 可加 | `strategy_plan.plan_revenue` | `[Plan Revenue]` | 未自动匹配 |
| IT 成本 | FactITMachine | 可加 | `it_machine.it_cost` | `[IT Cost]` | 未自动匹配 |
| 停机时长 | FactITSLA | 可加 | `it_sla.down_time` | `[Down Time]` | 未自动匹配 |
| 故障次数 | FactITSLA | 可加 | `it_sla.outage_count` | `[Outage Count]` | 未自动匹配 |

## 3. DAX × Cube

- 92 个可调用对象，DAX 有表达式的 92 个，Cube 有成员的 92 个；三个 L2 上下文给出的调用写法个数一致的 92 个。
- 实现层面的读法差异来自 `reports/validation/metric-text-vs-impl.md`（人工逐条比对，本脚本只按指标名引用）：A = 两边选了同一种文字没写明的读法；B = 两边不一致或引擎做不到。

| 类 | 可调用对象 |
|---|---|
| A | 15：销售额占比·FactOnlineSales（A3）、销售额占比·FactSales（A3）、坪效·FactSales（A7）、门店人均销售额·FactSales（A7）、同店销售额·FactSales（A4）、产品标价·DimProduct（A6）、产品单位成本·DimProduct（A6）、产品利润率·DimProduct（A5）、当前在手库存数量·FactInventory（A8）、当前在手库存金额·FactInventory（A8）、当前在订库存数量·FactInventory（A8）、当前安全库存数量·FactInventory（A8）、低于安全库存的门店产品数·FactInventory（A8）、平均在手库存金额·FactInventory（A1）、库存周转率·FactInventory（A2） |
| B | 9：销售额环比增长率·FactOnlineSales（B1）、销售额环比增长率·FactSales（B1）、新客数·FactOnlineSales（B2）、新客销售额·FactOnlineSales（B2）、新客销售额占比·FactOnlineSales（B2）、目标销售额·FactSalesQuota（B3）、目标销量·FactSalesQuota（B3）、目标毛利·FactSalesQuota（B3）、计划收入·FactStrategyPlan（B3） |
| 其余 | 68 |
