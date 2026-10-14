# 数据导入校验报告（T01）

由 `data/validation_report.py` 生成，不要手改。重跑：

```sh
uv run python data/validation_report.py
```

- 生成日期：2026-10-14
- 仓库提交号：`4536b28`
- chDB 版本：`4.4.0`，内嵌 ClickHouse 内核：`26.9.2.1`
- 库名：`retail`，数据目录：`$SEMDEBT_DATA_DIR/chdb`
- 建表语句：`vendor/cube/retail_schema.sql`（上游提交号见 `vendor/cube/NOTICE.md`）

本报告只记录导入结果。**与外部基准参考结果的一致性校验不在本卡**，由 Codex 在 T03 第一步做。

## 行数与日期范围

共 25 张表，34,326,191 行。
「日期范围」是 `DateKey` 的最小值 ~ 最大值；没有 `DateKey` 的表记 —。

| 表 | 行数 | DateKey 范围 |
|---|---:|---|
| `DimAccount` | 24 | — |
| `DimChannel` | 4 | — |
| `DimCurrency` | 28 | — |
| `DimCustomer` | 18,869 | — |
| `DimDate` | 2,556 | 2005-01-01 ~ 2011-12-31 |
| `DimEmployee` | 293 | — |
| `DimEntity` | 421 | — |
| `DimGeography` | 674 | — |
| `DimMachine` | 7,816 | — |
| `DimOutage` | 303 | — |
| `DimProduct` | 2,233 | — |
| `DimProductCategory` | 8 | — |
| `DimProductSubcategory` | 44 | — |
| `DimPromotion` | 28 | — |
| `DimSalesTerritory` | 265 | — |
| `DimScenario` | 3 | — |
| `DimStore` | 306 | — |
| `FactExchangeRate` | 773 | 2007-01-01 ~ 2009-07-01 |
| `FactITMachine` | 23,283 | 2007-01-01 ~ 2009-01-01 |
| `FactITSLA` | 4,925 | 2007-01-01 ~ 2009-12-31 |
| `FactInventory` | 8,013,099 | 2007-01-06 ~ 2009-12-26 |
| `FactOnlineSales` | 12,627,608 | 2007-01-01 ~ 2009-12-31 |
| `FactSales` | 3,406,089 | 2007-01-01 ~ 2009-12-31 |
| `FactSalesQuota` | 7,465,911 | 2007-01-01 ~ 2009-12-01 |
| `FactStrategyPlan` | 2,750,628 | 2007-01-01 ~ 2009-12-01 |

## 事实表主要金额列的合计

`sum(toDecimal128(列, 6))`，定点数求和，与行序无关，可逐位复核。

| 表 | 列 | 合计 |
|---|---|---:|
| `FactExchangeRate` | `AverageRate` | 346797.807975 |
| `FactExchangeRate` | `EndOfDayRate` | 353878.172704 |
| `FactITMachine` | `CostAmount` | 240765805 |
| `FactITSLA` | `DownTime` | 396699 |
| `FactInventory` | `OnHandQuantity` | 131294094 |
| `FactInventory` | `OnOrderQuantity` | 12768868 |
| `FactInventory` | `SafetyStockQuantity` | 85090734 |
| `FactInventory` | `UnitCost` | 1111890407.352094 |
| `FactOnlineSales` | `SalesAmount` | 2718202629.650406 |
| `FactOnlineSales` | `TotalCost` | 1344254907.141084 |
| `FactOnlineSales` | `DiscountAmount` | 268904117.30563 |
| `FactOnlineSales` | `ReturnAmount` | 29244318.203859 |
| `FactOnlineSales` | `SalesQuantity` | 12527442 |
| `FactOnlineSales` | `ReturnQuantity` | 100166 |
| `FactSales` | `SalesAmount` | 12413657608.856279 |
| `FactSales` | `TotalCost` | 5364896601.72275 |
| `FactSales` | `DiscountAmount` | 204157104.065429 |
| `FactSales` | `ReturnAmount` | 156839375.867239 |
| `FactSales` | `SalesQuantity` | 53320454 |
| `FactSales` | `ReturnQuantity` | 493587 |
| `FactSalesQuota` | `SalesAmountQuota` | 35998417680.649698 |
| `FactSalesQuota` | `SalesQuantityQuota` | 151495713 |
| `FactSalesQuota` | `GrossMarginQuota` | 20011170294.47544 |
| `FactStrategyPlan` | `Amount` | 65893562614.492444 |

## 行数与 CSV 的逐表核对

导入后用 `wc -l` 对每个 CSV 核过一遍：**每个文件的行数都等于表行数 + 1（表头）**，
即没有行被静默丢弃，也没有字段里的换行把一行拆成两行。核对命令：

```sh
cd "$SEMDEBT_DATA_DIR/raw/csv" && for f in *.csv; do printf "%-26s %s\n" "${f%.csv}" "$(wc -l < "$f")"; done
```
