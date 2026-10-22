# T16 JSON-L2 静态覆盖标注（v1.4 交付前）

只计模型上下文暴露的成员。109 个非 judge 题；低区分度单列。零模型调用、零评分调用。

本表按 #142 与用户后续裁决取代旧分类报告中的‘常用指标应补’建议。a/b/c/d 是覆盖分类，不修改原分。

v1.4 尚未交付，M-SHARE 的名称与范围、是否交付分母成员须由 T12 确定；当前标注不能作为已验收 v1.4 的声明。Q17 若获交付基数成员，须在全量前改成 covered 并固定新提交；其余父组占比题仍有嵌套选择障碍。

成员集包含度量、输出维度以及筛选/排序/时间成员；比较时将各位置引用去重为集合，时间粒度、筛选值和输出形状另记。仅对错答拆因：执行错误优先；集合不同归选错成员；集合相同归读法/筛选/形状差异。该归类不声称集合不同就必然语义错误，也不替代评分。全量前冻结版本，不在看答案后补集合。

a：L1 未定义所需口径；b：已有 L1 承诺但当前交付未编码；c：现有调用对象下无法一步组合；d：核心可答，仅必答展示列无可见成员。多障碍时表中记主障碍，不把 a/b 混算为纯接口限制。

维表 COUNT/AVG/MAX 与事实表去重数或平均值不是同一口径；即使当前数据偶然相等，也不当作正确实现。b 的季度和新客读法交 T12 按 L1 复核，不能自行加入新口径。

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
| Q94 | primary | b | quarter_shift_variant_not_encoded |
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
| Q114 | primary | b | new_customer_cohort_reading_mismatch |
| Q115 | primary | a | cohort_metric_not_defined |
| Q116 | primary | a | cohort_metric_not_defined |
| Q117 | primary | c | multi_stage_attribution |
| Q118 | primary | c | group_top_n_or_nested_selection |
| Q119 | primary | c | group_top_n_or_nested_selection |
| Q120 | primary | a | business_formula_not_defined |
| Q121 | primary | a | business_formula_not_defined |
| Q122 | primary | a | business_formula_not_defined |

## 去掉名次列的专项检查

| 题号 | 结论 | 类别 |
|---|---|---|
| Q71 | 仍不能；参考本来没有名次必答列，剩余为组内选择 | c |
| Q73 | 仍不能；缺少可见差额成员及对应选择能力 | a（另有 c） |
| Q74 | 仍不能；即使补父组占比，仍需要组内 Top-N | c |
| Q100 | 仍不能；参考本来没有名次必答列，缺分位筛选及交集能力 | a（另有 c） |

## 未暴露的辅助指标（全部不计能答）

下列成员均服务已有 L1 口径；这不等于 L1 单独承诺过每个辅助成员可调用。无对应 L1 口径的隐藏度量本次目录中为 0；不建议公开不对应的实现细节。

| 隐藏成员 | 对应 L1 口径 | 依据 | 交付处置 |
|---|---|---|---|
| online_sales.discounted_list_amount | 折扣率 | semantic/source.yaml:2478 | T12 范围或变体检查决定 |
| online_sales.sales_amount_prior_year | 销售额同比增长率 | semantic/source.yaml:2734 | T12 范围或变体检查决定 |
| online_sales.sales_amount_prior_month | 销售额环比增长率 | semantic/source.yaml:2743 | T12 范围或变体检查决定 |
| online_sales.sales_amount_in_scope | 销售额占比 | semantic/source.yaml:2751 | T12 范围或变体检查决定 |
| sales.discounted_list_amount | 折扣率 | semantic/source.yaml:2478 | T12 范围或变体检查决定 |
| sales.sales_amount_prior_year | 销售额同比增长率 | semantic/source.yaml:2734 | T12 范围或变体检查决定 |
| sales.sales_amount_prior_month | 销售额环比增长率 | semantic/source.yaml:2743 | T12 范围或变体检查决定 |
| sales.sales_amount_in_scope | 销售额占比 | semantic/source.yaml:2751 | T12 范围或变体检查决定 |
| sales.same_store_base | 同店销售额／同店销售额增长率 | semantic/source.yaml:2759 | T12 范围或变体检查决定 |
| sales.same_store_base_prior_year | 同店销售额／同店销售额增长率 | semantic/source.yaml:2759 | T12 范围或变体检查决定 |
