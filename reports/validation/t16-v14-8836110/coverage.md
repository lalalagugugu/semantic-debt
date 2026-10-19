# JSON-L2 v1.4 标准成员集与静态分类

固定候选 `883611029a65c12d8cc507bc363dda84a4db10b1`；题库 eval-v1.2；登记版本以包含本表的 Git 提交号标识。尚未假设 semantic-v1.4 tag 已打，后续 tag 必须与本候选交付内容相符。

109 个非 judge：主表 98、低区分度 11。能答 39；a 34、b 0、c 27、d 9。仅 Q94 从 b 转能答；Q114 从 b 转已证实接口限制 c，没有伪装成修好。原分数不改，不重评、不估全量。

只计 L2 上下文暴露的成员。标准集含输出、筛选、排序、时间成员，去重比较；执行报错优先，其后分别登记‘成员集不同’与‘成员集相同但结果不同’。这不是对所有等价查询的语义证明；不得在全量结果出来后悄悄修改标准集。

沿用原来已正确的成员组合；新等价调用名不强制替换既有标准。Q94 的时间粒度须为 quarter。Q114 的 main 原成员仍存在且可调用，但不实现完整截止日前90日客户集合，因此不能计为正确覆盖。

a：L1 未写口径；b：L1 承诺但交付未编码；c：已交付对象下的接口表达/实现限制；d：仅展示必答列无法输出。隐藏辅助成员全部不公开，不计能答。

| 题号 | 分层 | 类别 | 能力类别 / 标准成员集 |
|---|---|---|---|
| Q01 | primary | a | dimension_aggregate_not_defined |
| Q02 | primary | covered | online_sales.sales_amount |
| Q03 | primary | covered | online_sales.customer_count |
| Q04 | primary | covered | product.BrandName, product.ProductKey, product.ProductName |
| Q05 | primary | a | dimension_aggregate_not_defined |
| Q06 | primary | covered | online_sales.DateKey, online_sales.sales_amount |
| Q07 | low_discrimination | d | mandatory_rank_column |
| Q08 | primary | covered | employee.EmployeeKey, employee.FirstName, employee.IsSalesPerson, employee.LastName |
| Q09 | primary | covered | product.unit_cost |
| Q10 | primary | a | dimension_aggregate_not_defined |
| Q11 | primary | covered | online_sales.sales_amount, product_category.ProductCategoryName |
| Q12 | primary | covered | calendar.MonthNumber, online_sales.DateKey, online_sales.sales_amount |
| Q13 | primary | covered | sales.average_unit_price, sales.sales_amount, sales.sales_quantity, store.StoreName |
| Q14 | primary | c | aggregate_then_reaggregate |
| Q15 | primary | covered | geography.RegionCountryName, online_sales.sales_amount |
| Q16 | primary | covered | calendar.CalendarYear, online_sales.DateKey, online_sales.sales_amount |
| Q17 | low_discrimination | d | mandatory_denominator_not_exposed |
| Q18 | primary | covered | online_sales.discount_amount, promotion.PromotionType |
| Q19 | primary | covered | customer.Gender, online_sales.average_order_value |
| Q20 | primary | a | stock_gap_not_defined |
| Q21 | primary | covered | inventory.current_on_hand_quantity, store.StoreName |
| Q22 | primary | c | group_top_n_or_nested_selection |
| Q23 | primary | c | dynamic_arithmetic_or_window |
| Q24 | primary | covered | online_sales.return_rate, online_sales.sales_quantity, product_category.ProductCategoryName |
| Q25 | primary | covered | calendar.NorthAmericaSeason, geography.ContinentName, online_sales.average_daily_sales_amount |
| Q26 | primary | a | cohort_metric_not_defined |
| Q27 | primary | d | mandatory_rank_column |
| Q28 | primary | covered | channel.ChannelName, sales.average_unit_price |
| Q29 | low_discrimination | c | dynamic_arithmetic_or_window |
| Q30 | primary | c | dynamic_arithmetic_or_window |
| Q31 | primary | covered | account.AccountName, product_category.ProductCategoryName, scenario.ScenarioName, strategy_plan.DateKey, strategy_plan.plan_amount |
| Q32 | primary | c | aggregate_then_reaggregate |
| Q34 | primary | covered | inventory.DateKey, inventory.ProductKey, inventory.average_on_hand_value, inventory.inventory_turnover, product.ProductName |
| Q35 | primary | c | self_join_or_recursive_rollup |
| Q36 | primary | c | wide_metrics_cannot_return_labeled_rows |
| Q37 | primary | a | quantile_metric_not_defined |
| Q38 | primary | a | business_formula_not_defined |
| Q41 | primary | covered | online_sales.DateKey, online_sales.sales_amount |
| Q43 | primary | covered | geography.ContinentName, online_sales.gross_margin |
| Q47 | primary | a | dimension_aggregate_not_defined |
| Q49 | primary | c | self_join_or_recursive_rollup |
| Q50 | primary | d | mandatory_growth_amount_column |
| Q51 | primary | a | dimension_aggregate_not_defined |
| Q52 | primary | covered | product.UnitPrice |
| Q53 | primary | covered | online_sales.DateKey, online_sales.order_count |
| Q54 | primary | covered | online_sales.return_amount |
| Q55 | primary | a | dimension_aggregate_not_defined |
| Q56 | primary | a | dimension_aggregate_not_defined |
| Q57 | primary | a | dimension_aggregate_not_defined |
| Q58 | primary | covered | online_sales.SalesAmount |
| Q59 | low_discrimination | a | dimension_aggregate_not_defined |
| Q60 | primary | a | dimension_aggregate_not_defined |
| Q61 | primary | covered | online_sales.sales_amount, product_subcategory.ProductSubcategoryName |
| Q62 | primary | covered | online_sales.sales_amount, online_sales.sales_quantity, product.BrandName |
| Q63 | primary | covered | customer.Occupation, online_sales.average_order_value |
| Q64 | primary | covered | calendar.MonthNumber, online_sales.DateKey, online_sales.gross_margin, online_sales.gross_margin_pct, online_sales.sales_amount |
| Q65 | primary | covered | employee.FirstName, employee.LastName, sales.sales_amount, store.EmployeeKey, store.StoreName |
| Q66 | primary | covered | calendar.CalendarQuarterLabel, online_sales.DateKey, online_sales.discount_amount |
| Q67 | primary | d | mandatory_rank_column |
| Q68 | low_discrimination | covered | calendar.IsHoliday, online_sales.DateKey, online_sales.order_count, online_sales.sales_amount |
| Q69 | low_discrimination | covered | online_sales.discount_rate, online_sales.discounted_sales_amount, online_sales.list_amount_before_discount, promotion.PromotionCategory, promotion.PromotionKey |
| Q70 | primary | a | dimension_aggregate_not_defined |
| Q71 | primary | c | group_top_n_or_nested_selection |
| Q72 | primary | c | dynamic_arithmetic_or_window |
| Q73 | primary | a | stock_gap_not_defined |
| Q74 | primary | c | group_top_n_or_nested_selection |
| Q75 | primary | covered | customer.FirstName, customer.LastName, online_sales.CustomerKey, online_sales.DateKey, online_sales.sales_amount_yoy_pct |
| Q76 | low_discrimination | a | cohort_metric_not_defined |
| Q77 | primary | d | mandatory_growth_amount_column |
| Q78 | primary | a | business_formula_not_defined |
| Q79 | low_discrimination | d | mandatory_rank_column |
| Q80 | primary | a | span_metric_not_defined |
| Q81 | primary | a | cohort_metric_not_defined |
| Q82 | primary | a | hr_metric_not_defined |
| Q83 | low_discrimination | a | cohort_metric_not_defined |
| Q84 | primary | a | business_formula_not_defined |
| Q85 | low_discrimination | c | group_top_n_or_nested_selection |
| Q87 | primary | a | business_formula_not_defined |
| Q88 | primary | c | group_top_n_or_nested_selection |
| Q89 | primary | a | cohort_metric_not_defined |
| Q90 | primary | c | dynamic_arithmetic_or_window |
| Q92 | primary | d | mandatory_rank_column |
| Q94 | primary | covered | sales.DateKey, sales.sales_amount_qoq_pct, store.StoreName |
| Q96 | primary | a | cohort_metric_not_defined |
| Q98 | primary | c | group_top_n_or_nested_selection |
| Q99 | low_discrimination | c | dynamic_arithmetic_or_window |
| Q100 | primary | a | quantile_metric_not_defined |
| Q101 | primary | covered | online_sales.DateKey, online_sales.sales_amount |
| Q102 | primary | covered | online_sales.DateKey, online_sales.net_sales_amount, product_category.ProductCategoryName |
| Q103 | primary | c | aggregate_then_reaggregate |
| Q104 | primary | c | dynamic_arithmetic_or_window |
| Q105 | primary | covered | sales.sales_amount, store.StoreName |
| Q106 | primary | d | mandatory_growth_amount_column |
| Q107 | primary | a | business_formula_not_defined |
| Q108 | primary | covered | geography.RegionCountryName, online_sales.DateKey, online_sales.order_count, online_sales.sales_amount |
| Q109 | primary | c | dynamic_arithmetic_or_window |
| Q110 | primary | c | dynamic_arithmetic_or_window |
| Q111 | primary | c | dynamic_arithmetic_or_window |
| Q112 | primary | a | business_formula_not_defined |
| Q113 | primary | c | dynamic_arithmetic_or_window |
| Q114 | primary | c | engine_limit_full_90_day_cohort_not_delivered |
| Q115 | primary | a | cohort_metric_not_defined |
| Q116 | primary | a | cohort_metric_not_defined |
| Q117 | primary | c | multi_stage_attribution |
| Q118 | primary | c | group_top_n_or_nested_selection |
| Q119 | primary | c | group_top_n_or_nested_selection |
| Q120 | primary | a | business_formula_not_defined |
| Q121 | primary | a | business_formula_not_defined |
| Q122 | primary | a | business_formula_not_defined |

## 隐藏成员

15 个辅助度量、8 个技术键维度均不公开。

| 成员 | 类型 | 公开状态 | 计覆盖 |
|---|---|---|---|
| exchange_rate.ExchangeRateKey | dimensions | 不公开 | 否 |
| inventory.InventoryKey | dimensions | 不公开 | 否 |
| it_machine.ITMachinekey | dimensions | 不公开 | 否 |
| it_sla.ITSLAkey | dimensions | 不公开 | 否 |
| online_sales.discounted_list_amount | measures | 不公开 | 否 |
| online_sales.sales_amount_prior_year | measures | 不公开 | 否 |
| online_sales.sales_amount_prior_month | measures | 不公开 | 否 |
| online_sales.sales_amount_prior_quarter | measures | 不公开 | 否 |
| online_sales.sales_amount_in_scope | measures | 不公开 | 否 |
| online_sales.sales_amount_in_category | measures | 不公开 | 否 |
| online_sales.OnlineSalesKey | dimensions | 不公开 | 否 |
| sales.discounted_list_amount | measures | 不公开 | 否 |
| sales.sales_amount_prior_year | measures | 不公开 | 否 |
| sales.sales_amount_prior_month | measures | 不公开 | 否 |
| sales.sales_amount_prior_quarter | measures | 不公开 | 否 |
| sales.sales_amount_in_scope | measures | 不公开 | 否 |
| sales.sales_amount_in_channel | measures | 不公开 | 否 |
| sales.sales_amount_in_category | measures | 不公开 | 否 |
| sales.same_store_base | measures | 不公开 | 否 |
| sales.same_store_base_prior_year | measures | 不公开 | 否 |
| sales.SalesKey | dimensions | 不公开 | 否 |
| sales_quota.SalesQuotaKey | dimensions | 不公开 | 否 |
| strategy_plan.StrategyPlanKey | dimensions | 不公开 | 否 |
