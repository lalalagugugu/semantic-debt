# 明细宽表（L1.5W）校验报告

由 `render/build_widetables.py` 生成，不要手改。重跑：

```sh
uv run python render/build_widetables.py
```

视图定义在 `semantic/widetables.sql`，建在独立库 `dwd`，`retail` 库不动。

## 行数核对

关联和行级派生不应改变行数，所以除「当前库存」外每个视图的行数都必须等于对应事实表。

| 视图 | 对应事实表 / 说明 | 视图行数 | 应为 | 判定 |
|---|---|---:|---:|---|
| `dwd.wide_online_sales` | retail.FactOnlineSales | 12,627,608 | 12,627,608 | 一致 |
| `dwd.wide_all_channel_sales` | retail.FactSales | 3,406,089 | 3,406,089 | 一致 |
| `dwd.wide_sales_quota` | retail.FactSalesQuota | 7,465,911 | 7,465,911 | 一致 |
| `dwd.wide_strategy_plan` | retail.FactStrategyPlan | 2,750,628 | 2,750,628 | 一致 |
| `dwd.wide_current_inventory` | retail.FactInventory 按约定 11 取每个门店 × 产品最近一次快照，所以行数等于门店 × 产品组合数，而不是事实表行数 | 600,241 | 600,241 | 按说明一致 |

## 金额合计核对

宽表只关联、不改金额，所以金额列的合计必须与事实表逐位相同（`sum(toDecimal128(列, 6))`，与行序无关）。

| 视图列 | 事实表列 | 合计 | 判定 |
|---|---|---:|---|
| `dwd.wide_online_sales.销售金额` | `retail.FactOnlineSales.SalesAmount` | 2718202629.650406 | 一致 |
| `dwd.wide_all_channel_sales.销售金额` | `retail.FactSales.SalesAmount` | 12413657608.856279 | 一致 |
| `dwd.wide_all_channel_sales.总成本` | `retail.FactSales.TotalCost` | 5364896601.72275 | 一致 |
| `dwd.wide_sales_quota.目标销售额` | `retail.FactSalesQuota.SalesAmountQuota` | 35998417680.649698 | 一致 |
| `dwd.wide_strategy_plan.计划金额` | `retail.FactStrategyPlan.Amount` | 65893562614.492444 | 一致 |

## 结论

全部通过。

