# 键的覆盖率与基数

由 `semantic/profiling/profile_keys.py` 生成，不要手改。

建表语句里**没有任何外键声明**，下表的关系是按列名提出候选、再用数据实测的结果。
「孤儿行」= 子表里该键非空、但父表里找不到对应行的行数；`0` 才能写成可信赖的关系。
「覆盖率」= 子表用到的键个数 ÷ 父表行数，用来说明维度表有多少行从没被这张事实表用到。

| 子表.列 | 父表.列 | 子表行数 | 空值 | 用到的键 | 父表行数 | 孤儿行 | 基数 | 覆盖率 |
|---|---|---:|---:|---:|---:|---:|---|---:|
| `DimAccount.ParentAccountKey` | `DimAccount.AccountKey` | 24 | 0 | 7 | 24 | 0 | 多对一 | 29.2% |
| `DimCustomer.GeographyKey` | `DimGeography.GeographyKey` | 18,869 | 0 | 476 | 674 | 0 | 多对一 | 70.6% |
| `DimEmployee.ParentEmployeeKey` | `DimEmployee.EmployeeKey` | 293 | 0 | 11 | 293 | 0 | 多对一 | 3.8% |
| `DimEntity.ParentEntityKey` | `DimEntity.EntityKey` | 421 | 0 | 114 | 421 | 0 | 多对一 | 27.1% |
| `DimMachine.StoreKey` | `DimStore.StoreKey` | 7,816 | 0 | 303 | 306 | 0 | 多对一 | 99.0% |
| `DimProduct.ProductSubcategoryKey` | `DimProductSubcategory.ProductSubcategoryKey` | 2,233 | 0 | 30 | 44 | 0 | 多对一 | 68.2% |
| `DimProductSubcategory.ProductCategoryKey` | `DimProductCategory.ProductCategoryKey` | 44 | 0 | 8 | 8 | 0 | 多对一 | 100.0% |
| `DimSalesTerritory.GeographyKey` | `DimGeography.GeographyKey` | 265 | 0 | 265 | 674 | 0 | 一对一 | 39.3% |
| `DimSalesTerritory.EmployeeKey` | `DimEmployee.EmployeeKey` | 265 | 0 | 264 | 293 | 0 | 多对一 | 90.1% |
| `DimStore.GeographyKey` | `DimGeography.GeographyKey` | 306 | 0 | 263 | 674 | 0 | 多对一 | 39.0% |
| `DimStore.EntityKey` | `DimEntity.EntityKey` | 306 | 0 | 306 | 421 | 0 | 一对一 | 72.7% |
| `DimStore.EmployeeKey` | `DimEmployee.EmployeeKey` | 306 | 0 | 262 | 293 | 1 ⚠️ | 多对一 | 89.4% |
| `FactExchangeRate.CurrencyKey` | `DimCurrency.CurrencyKey` | 773 | 0 | 25 | 28 | 0 | 多对一 | 89.3% |
| `FactExchangeRate.DateKey` | `DimDate.DateKey` | 773 | 0 | 31 | 2,556 | 0 | 多对一 | 1.2% |
| `FactITMachine.MachineKey` | `DimMachine.MachineKey` | 23,283 | 0 | 7,816 | 7,816 | 0 | 多对一 | 100.0% |
| `FactITMachine.DateKey` | `DimDate.DateKey` | 23,283 | 0 | 3 | 2,556 | 0 | 多对一 | 0.1% |
| `FactITSLA.DateKey` | `DimDate.DateKey` | 4,925 | 0 | 1,046 | 2,556 | 0 | 多对一 | 40.9% |
| `FactITSLA.StoreKey` | `DimStore.StoreKey` | 4,925 | 0 | 299 | 306 | 0 | 多对一 | 97.7% |
| `FactITSLA.MachineKey` | `DimMachine.MachineKey` | 4,925 | 0 | 2,553 | 7,816 | 0 | 多对一 | 32.7% |
| `FactITSLA.OutageKey` | `DimOutage.OutageKey` | 4,925 | 0 | 294 | 303 | 0 | 多对一 | 97.0% |
| `FactInventory.DateKey` | `DimDate.DateKey` | 8,013,099 | 0 | 156 | 2,556 | 0 | 多对一 | 6.1% |
| `FactInventory.StoreKey` | `DimStore.StoreKey` | 8,013,099 | 0 | 306 | 306 | 0 | 多对一 | 100.0% |
| `FactInventory.ProductKey` | `DimProduct.ProductKey` | 8,013,099 | 0 | 2,516 | 2,233 | 533,358 ⚠️ | 多对一 | 112.7% |
| `FactInventory.CurrencyKey` | `DimCurrency.CurrencyKey` | 8,013,099 | 0 | 1 | 28 | 0 | 多对一 | 3.6% |
| `FactOnlineSales.DateKey` | `DimDate.DateKey` | 12,627,608 | 0 | 1,096 | 2,556 | 0 | 多对一 | 42.9% |
| `FactOnlineSales.StoreKey` | `DimStore.StoreKey` | 12,627,608 | 0 | 3 | 306 | 0 | 多对一 | 1.0% |
| `FactOnlineSales.ProductKey` | `DimProduct.ProductKey` | 12,627,608 | 0 | 2,516 | 2,233 | 1,715,380 ⚠️ | 多对一 | 112.7% |
| `FactOnlineSales.PromotionKey` | `DimPromotion.PromotionKey` | 12,627,608 | 0 | 28 | 28 | 0 | 多对一 | 100.0% |
| `FactOnlineSales.CurrencyKey` | `DimCurrency.CurrencyKey` | 12,627,608 | 0 | 1 | 28 | 0 | 多对一 | 3.6% |
| `FactOnlineSales.CustomerKey` | `DimCustomer.CustomerKey` | 12,627,608 | 0 | 18,869 | 18,869 | 0 | 多对一 | 100.0% |
| `FactSales.DateKey` | `DimDate.DateKey` | 3,406,089 | 0 | 1,096 | 2,556 | 0 | 多对一 | 42.9% |
| `FactSales.channelKey` | `DimChannel.ChannelKey` | 3,406,089 | 0 | 4 | 4 | 0 | 多对一 | 100.0% |
| `FactSales.StoreKey` | `DimStore.StoreKey` | 3,406,089 | 0 | 306 | 306 | 0 | 多对一 | 100.0% |
| `FactSales.ProductKey` | `DimProduct.ProductKey` | 3,406,089 | 0 | 2,516 | 2,233 | 338,898 ⚠️ | 多对一 | 112.7% |
| `FactSales.PromotionKey` | `DimPromotion.PromotionKey` | 3,406,089 | 0 | 28 | 28 | 0 | 多对一 | 100.0% |
| `FactSales.CurrencyKey` | `DimCurrency.CurrencyKey` | 3,406,089 | 0 | 1 | 28 | 0 | 多对一 | 3.6% |
| `FactSalesQuota.ChannelKey` | `DimChannel.ChannelKey` | 7,465,911 | 0 | 4 | 4 | 0 | 多对一 | 100.0% |
| `FactSalesQuota.StoreKey` | `DimStore.StoreKey` | 7,465,911 | 0 | 306 | 306 | 0 | 多对一 | 100.0% |
| `FactSalesQuota.ProductKey` | `DimProduct.ProductKey` | 7,465,911 | 0 | 2,516 | 2,233 | 521,121 ⚠️ | 多对一 | 112.7% |
| `FactSalesQuota.DateKey` | `DimDate.DateKey` | 7,465,911 | 0 | 36 | 2,556 | 0 | 多对一 | 1.4% |
| `FactSalesQuota.CurrencyKey` | `DimCurrency.CurrencyKey` | 7,465,911 | 0 | 1 | 28 | 0 | 多对一 | 3.6% |
| `FactSalesQuota.ScenarioKey` | `DimScenario.ScenarioKey` | 7,465,911 | 0 | 3 | 3 | 0 | 多对一 | 100.0% |
| `FactStrategyPlan.DateKey` | `DimDate.DateKey` | 2,750,628 | 0 | 36 | 2,556 | 0 | 多对一 | 1.4% |
| `FactStrategyPlan.EntityKey` | `DimEntity.EntityKey` | 2,750,628 | 0 | 306 | 421 | 0 | 多对一 | 72.7% |
| `FactStrategyPlan.ScenarioKey` | `DimScenario.ScenarioKey` | 2,750,628 | 0 | 3 | 3 | 0 | 多对一 | 100.0% |
| `FactStrategyPlan.AccountKey` | `DimAccount.AccountKey` | 2,750,628 | 0 | 17 | 24 | 0 | 多对一 | 70.8% |
| `FactStrategyPlan.CurrencyKey` | `DimCurrency.CurrencyKey` | 2,750,628 | 0 | 1 | 28 | 0 | 多对一 | 3.6% |
| `FactStrategyPlan.ProductCategoryKey` | `DimProductCategory.ProductCategoryKey` | 2,750,628 | 0 | 8 | 8 | 0 | 多对一 | 100.0% |

## 粒度核对

每张表声称的粒度列组是否唯一。

| 表 | 粒度列 | 行数 | 不同组合 | 唯一 |
|---|---|---:|---:|---|
| `DimAccount` | `AccountKey` | 24 | 24 | 是 |
| `DimChannel` | `ChannelKey` | 4 | 4 | 是 |
| `DimCurrency` | `CurrencyKey` | 28 | 28 | 是 |
| `DimCustomer` | `CustomerKey` | 18,869 | 18,869 | 是 |
| `DimDate` | `DateKey` | 2,556 | 2,556 | 是 |
| `DimEmployee` | `EmployeeKey` | 293 | 293 | 是 |
| `DimEntity` | `EntityKey` | 421 | 421 | 是 |
| `DimGeography` | `GeographyKey` | 674 | 674 | 是 |
| `DimMachine` | `MachineKey` | 7,816 | 7,816 | 是 |
| `DimOutage` | `OutageKey` | 303 | 303 | 是 |
| `DimProduct` | `ProductKey` | 2,233 | 2,233 | 是 |
| `DimProductCategory` | `ProductCategoryKey` | 8 | 8 | 是 |
| `DimProductSubcategory` | `ProductSubcategoryKey` | 44 | 44 | 是 |
| `DimPromotion` | `PromotionKey` | 28 | 28 | 是 |
| `DimSalesTerritory` | `SalesTerritoryKey` | 265 | 265 | 是 |
| `DimScenario` | `ScenarioKey` | 3 | 3 | 是 |
| `DimStore` | `StoreKey` | 306 | 306 | 是 |
| `FactExchangeRate` | `DateKey`、`CurrencyKey` | 773 | 773 | 是 |
| `FactITMachine` | `MachineKey`、`DateKey`、`CostType` | 23,283 | 23,283 | 是 |
| `FactITSLA` | `ITSLAkey` | 4,925 | 4,925 | 是 |
| `FactInventory` | `DateKey`、`StoreKey`、`ProductKey` | 8,013,099 | 8,013,099 | 是 |
| `FactOnlineSales` | `SalesOrderNumber`、`SalesOrderLineNumber` | 12,627,608 | 12,627,608 | 是 |
| `FactSales` | `DateKey`、`channelKey`、`StoreKey`、`ProductKey`、`PromotionKey` | 3,406,089 | 3,406,089 | 是 |
| `FactSalesQuota` | `DateKey`、`ChannelKey`、`StoreKey`、`ProductKey`、`ScenarioKey` | 7,465,911 | 7,465,911 | 是 |
| `FactStrategyPlan` | `DateKey`、`EntityKey`、`ScenarioKey`、`AccountKey`、`ProductCategoryKey` | 2,750,628 | 2,750,628 | 是 |
