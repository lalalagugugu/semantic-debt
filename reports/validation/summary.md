# 汇总层（L1.5S）校验报告

由 `render/build_summary.py` 生成，不要手改。重建与重跑：

```sh
uv run python render/build_summary.py
```

建表语句在 `semantic/summary/summary.sql`，物化在 chDB 的独立库 `ads`；
报表需求清单在 `semantic/summary/requirements.md`，列级说明在 `semantic/summary/summary.yaml`。

## `ads` 库里的汇总表

硬规则：`ads` 里不得出现任何明细事实表。脚本的判据是**相对基表有没有真的聚合**：
每张汇总表的行数不得超过它所聚合的事实表的 50%。这一条实测抓到过真问题——原来的
`ads_plan_month_store_category_account` 粒度与 `FactStrategyPlan` 完全相同（实体与门店一一对应），2,750,628 行，是明细表换了个列名，已拆成下面按门店、按品类两张。

| 汇总表 | 行数 | 基表 | 基表行数 | 占基表 |
|---|---:|---|---:|---:|
| `ads.ads_inventory_current_store_category` | 2,754 | `retail.FactInventory` | 8,013,099 | 0.03% |
| `ads.ads_inventory_week_store_category` | 406,232 | `retail.FactInventory` | 8,013,099 | 5.07% |
| `ads.ads_online_customer_month_tier` | 92 | `retail.FactOnlineSales` | 12,627,608 | 0.00% |
| `ads.ads_online_customer_profile_quarter` | 16,966 | `retail.FactOnlineSales` | 12,627,608 | 0.13% |
| `ads.ads_online_week_store` | 477 | `retail.FactOnlineSales` | 12,627,608 | 0.00% |
| `ads.ads_online_week_total` | 159 | `retail.FactOnlineSales` | 12,627,608 | 0.00% |
| `ads.ads_plan_month_category_account` | 9,792 | `retail.FactStrategyPlan` | 2,750,628 | 0.36% |
| `ads.ads_plan_month_store_account` | 345,348 | `retail.FactStrategyPlan` | 2,750,628 | 12.56% |
| `ads.ads_promotion_month_channel` | 324 | `retail.FactSales` | 3,406,089 | 0.01% |
| `ads.ads_quota_month_channel_store_category` | 95,188 | `retail.FactSalesQuota` | 7,465,911 | 1.27% |
| `ads.ads_sales_day_store` | 309,058 | `retail.FactSales` | 3,406,089 | 9.07% |
| `ads.ads_sales_month_channel` | 144 | `retail.FactSales` | 3,406,089 | 0.00% |
| `ads.ads_sales_month_product` | 8,056 | `retail.FactSales` | 3,406,089 | 0.24% |
| `ads.ads_sales_month_store` | 10,825 | `retail.FactSales` | 3,406,089 | 0.32% |
| `ads.ads_sales_week_channel_country` | 6,519 | `retail.FactSales` | 3,406,089 | 0.19% |
| `ads.ads_sales_year_store` | 913 | `retail.FactSales` | 3,406,089 | 0.03% |

## 可加指标合计对账

验收项：**每张汇总表的可加指标在全量范围内的合计，与对应事实表的合计一致。**
比对用 `sum(toDecimal128(列, 6))`，定点数求和与行序无关，可逐位核。

| 汇总表.列 | 汇总表合计 | 事实表合计 | 判定 | 口径说明 |
|---|---:|---:|---|---|
| `ads.ads_sales_month_channel.销售额` | 12413657608.856279 | 12413657608.856279 | 一致 | 全渠道销售额全量 |
| `ads.ads_sales_month_channel.销售数量` | 53320454 | 53320454 | 一致 | 全渠道销售数量全量 |
| `ads.ads_sales_month_channel.退货金额` | 156839375.867239 | 156839375.867239 | 一致 | 全渠道退货金额全量 |
| `ads.ads_sales_month_channel.总成本` | 5364896601.72275 | 5364896601.72275 | 一致 | 全渠道总成本全量 |
| `ads.ads_sales_month_channel.折扣金额` | 204157104.065429 | 204157104.065429 | 一致 | 全渠道折扣金额全量 |
| `ads.ads_sales_month_channel.打折销售额` | 8232819442.44648 | 8232819442.44648 | 一致 | 约定 10：促销键 != 1 的销售额 |
| `ads.ads_sales_week_channel_country.销售额` | 12413657608.856279 | 12413657608.856279 | 一致 | 全渠道销售额全量 |
| `ads.ads_sales_week_channel_country.毛利` | 7048761007.133529 | 7048761007.133529 | 一致 | 毛利 = 销售额 − 总成本（约定 7） |
| `ads.ads_plan_month_store_account.计划金额` | 65893562614.492444 | 65893562614.492444 | 一致 | 战略计划全量（三个场景、17 个科目都留在粒度里，所以等于全表） |
| `ads.ads_plan_month_category_account.计划金额` | 65893562614.492444 | 65893562614.492444 | 一致 | 同上，换成按品类汇总，总额不变 |
| `ads.ads_quota_month_channel_store_category.销售额` | 12413657608.856279 | 12413657608.856279 | 一致 | 全渠道销售额全量（分子） |
| `ads.ads_quota_month_channel_store_category.目标销售额` | 10667465363.630415 | 10667465363.630415 | 一致 | 约定 12：只有预算场景是正式目标（分母） |
| `ads.ads_quota_month_channel_store_category.目标销量` | 44300085 | 44300085 | 一致 | 预算场景的目标销量 |
| `ads.ads_sales_month_store.销售额` | 12413657608.856279 | 12413657608.856279 | 一致 | 全渠道销售额全量 |
| `ads.ads_sales_month_store.净销售额` | 12256818232.98904 | 12256818232.98904 | 一致 | 净销售额 = 销售额 − 退货金额（约定 7） |
| `ads.ads_sales_year_store.销售额` | 12413657608.856279 | 12413657608.856279 | 一致 | 全渠道销售额全量 |
| `ads.ads_sales_day_store.销售额` | 12413657608.856279 | 12413657608.856279 | 一致 | 全渠道销售额全量 |
| `ads.ads_sales_day_store.折扣金额` | 204157104.065429 | 204157104.065429 | 一致 | 全渠道折扣金额全量 |
| `ads.ads_online_week_store.销售额` | 2718202629.650406 | 2718202629.650406 | 一致 | 线上销售额全量 |
| `ads.ads_online_week_store.退货金额` | 29244318.203859 | 29244318.203859 | 一致 | 线上退货金额全量 |
| `ads.ads_online_week_store.订单行数` | 12627608 | 12627608 | 一致 | 线上订单行数全量 |
| `ads.ads_online_week_total.销售额` | 2718202629.650406 | 2718202629.650406 | 一致 | 线上销售额全量 |
| `ads.ads_online_week_total.订单行数` | 12627608 | 12627608 | 一致 | 线上订单行数全量 |
| `ads.ads_online_customer_month_tier.销售额` | 2718202629.650406 | 2718202629.650406 | 一致 | 线上销售额全量 |
| `ads.ads_online_customer_month_tier.订单行数` | 12627608 | 12627608 | 一致 | 线上订单行数全量 |
| `ads.ads_online_customer_profile_quarter.销售额` | 2718202629.650406 | 2718202629.650406 | 一致 | 线上销售额全量 |
| `ads.ads_online_customer_profile_quarter.订单行数` | 12627608 | 12627608 | 一致 | 线上订单行数全量 |
| `ads.ads_sales_month_product.销售额` | 12413657608.856279 | 12413657608.856279 | 一致 | 全渠道销售额全量——这一条专门检验产品维度缺 284 行时「未知（产品维度缺行）」组保住了总额 |
| `ads.ads_sales_month_product.销售数量` | 53320454 | 53320454 | 一致 | 全渠道销售数量全量 |
| `ads.ads_sales_month_product.总成本` | 5364896601.72275 | 5364896601.72275 | 一致 | 全渠道总成本全量 |
| `ads.ads_inventory_week_store_category.在手数量` | 131294094 | 131294094 | 一致 | 库存快照全量。**这是算术完整性核对，不是业务指标**：库存半可加，跨快照日求和在业务上无意义（约定 11） |
| `ads.ads_inventory_week_store_category.在订数量` | 12768868 | 12768868 | 一致 | 同上，算术完整性核对 |
| `ads.ads_inventory_week_store_category.安全库存数量` | 85090734 | 85090734 | 一致 | 同上，算术完整性核对 |
| `ads.ads_inventory_week_store_category.在手库存金额` | 15114568308.604791 | 15114568308.604791 | 一致 | 在手库存金额 = 在手数量 × 单位成本，同上为算术完整性核对 |
| `ads.ads_inventory_current_store_category.在手数量` | 11897661 | 11897661 | 一致 | 约定 11 的当前库存：每个门店 × 产品最近一次快照 |
| `ads.ads_inventory_current_store_category.在手库存金额` | 1291296461.00687 | 1291296461.00687 | 一致 | 约定 11 的当前库存金额 |
| `ads.ads_inventory_current_store_category.门店产品组合数` | 600241 | 600241 | 一致 | 门店 × 产品组合数 |
| `ads.ads_promotion_month_channel.销售额` | 12413657608.856279 | 12413657608.856279 | 一致 | 全渠道销售额全量——无折扣档保留在表里做基线，所以等于全表 |
| `ads.ads_promotion_month_channel.折扣金额` | 204157104.065429 | 204157104.065429 | 一致 | 全渠道折扣金额全量 |

## 去重计数列

这些列**不能跨行相加**（客户数、订单数、门店数、产品数、有销售天数、门店产品组合数）。
所以不对它们做合计对账，只核对一个必要条件：任何一行的值都不能超过全量去重值。
下表的「直接相加会得到」一列就是把它们相加的错误结果，和「全量去重」对比能看出差多少。

| 汇总表.列 | 单行最大 | 全量去重 | 直接相加（错误） |
|---|---:|---:|---:|
| `ads.ads_sales_month_channel.有销售天数` | 31 | 1,096 | 4,384 |
| `ads.ads_sales_month_channel.门店数` | 299 | 306 | 10,825 |
| `ads.ads_sales_month_channel.产品数` | 2,502 | 2,516 | 289,738 |
| `ads.ads_sales_week_channel_country.有销售天数` | 7 | 1,096 | 44,932 |
| `ads.ads_sales_week_channel_country.门店数` | 195 | 306 | 47,474 |
| `ads.ads_sales_month_store.有销售天数` | 31 | 1,096 | 309,058 |
| `ads.ads_sales_month_store.产品数` | 2,254 | 2,516 | 2,488,637 |
| `ads.ads_sales_year_store.有销售天数` | 366 | 1,096 | 309,058 |
| `ads.ads_online_week_store.订单数` | 13,189 | 1,674,320 | 1,674,327 |
| `ads.ads_online_week_store.客户数` | 6,399 | 18,869 | 1,169,556 |
| `ads.ads_online_week_total.订单数` | 27,847 | 1,674,320 | 1,674,320 |
| `ads.ads_online_week_total.客户数` | 12,355 | 18,869 | 1,169,476 |
| `ads.ads_online_customer_month_tier.订单数` | 92,203 | 1,674,320 | 1,676,354 |
| `ads.ads_online_customer_month_tier.客户数` | 16,578 | 18,869 | 547,945 |
| `ads.ads_online_customer_profile_quarter.订单数` | 3,505 | 1,674,320 | 1,676,354 |
| `ads.ads_online_customer_profile_quarter.客户数` | 157 | 18,869 | 214,671 |
| `ads.ads_sales_month_product.产品数` | 284 | 2,516 | 289,738 |

## 结论

全部通过。

