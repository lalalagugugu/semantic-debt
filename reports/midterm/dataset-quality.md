# 数据集规模与数据质量

复现：`uv run python reports/midterm/quality.py`。以环境变量SEMDEBT_DATA_DIR定位本地Parquet，使用无持久目录的chDB查询；不打开共享chdb或chdb-eval。
字段数来自vendor/cube/retail_schema.sql的DDL，不含宽表/汇总层/Cube派生成员。输入Parquet逐文件SHA256、查询结果与chDB版本见quality-evidence.json。
执行记录：首轮在CloseDate哨兵探针因String与Date不能比较而停止（Code386）；依据物理字符串类型改为字符串常量后重算，未修改数据。
原始表25张，共244个字段、34,326,191行；字段按每张表相加，同名字段在不同表分别计数。

| 表 | 字段数 | 行数 | 查询编号 |
|---|---|---|---|
| DimAccount | 6 | 24 | 1 |
| DimChannel | 3 | 4 | 2 |
| DimCurrency | 3 | 28 | 3 |
| DimCustomer | 15 | 18869 | 4 |
| DimDate | 20 | 2556 | 5 |
| DimEmployee | 21 | 293 | 6 |
| DimEntity | 8 | 421 | 7 |
| DimGeography | 6 | 674 | 8 |
| DimMachine | 14 | 7816 | 9 |
| DimOutage | 5 | 303 | 10 |
| DimProduct | 22 | 2233 | 11 |
| DimProductCategory | 2 | 8 | 12 |
| DimProductSubcategory | 3 | 44 | 13 |
| DimPromotion | 5 | 28 | 14 |
| DimSalesTerritory | 10 | 265 | 15 |
| DimScenario | 2 | 3 | 16 |
| DimStore | 16 | 306 | 17 |
| FactExchangeRate | 5 | 773 | 18 |
| FactITMachine | 5 | 23283 | 19 |
| FactITSLA | 8 | 4925 | 20 |
| FactInventory | 13 | 8013099 | 21 |
| FactOnlineSales | 18 | 12627608 | 22 |
| FactSales | 16 | 3406089 | 23 |
| FactSalesQuota | 10 | 7465911 | 24 |
| FactStrategyPlan | 8 | 2750628 | 25 |

## 质量清单

按semantic/source.yaml既有质量项和候选关系量化；可疑数据保留，不自动清洗。不同探针可能覆盖同一行，不能相加当作坏行总数。
结构性缺口：没有事实表直接关联员工/辖区，属于模型关系覆盖限制；不存在可量化的受影响员工销售事实行数（不适用，不写成0）。

| 项目 | 受影响行/键数 | 查询编号 | 定义与限制 |
|---|---|---|---|
| 孤儿键 DimAccount.ParentAccountKey → DimAccount.AccountKey | 0 | 26 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 DimCustomer.GeographyKey → DimGeography.GeographyKey | 0 | 27 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 DimEmployee.ParentEmployeeKey → DimEmployee.EmployeeKey | 0 | 28 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 DimEntity.ParentEntityKey → DimEntity.EntityKey | 0 | 29 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 DimMachine.StoreKey → DimStore.StoreKey | 0 | 30 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 DimProduct.ProductSubcategoryKey → DimProductSubcategory.ProductSubcategoryKey | 0 | 31 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 DimProductSubcategory.ProductCategoryKey → DimProductCategory.ProductCategoryKey | 0 | 32 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 DimSalesTerritory.GeographyKey → DimGeography.GeographyKey | 0 | 33 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 DimSalesTerritory.EmployeeKey → DimEmployee.EmployeeKey | 0 | 34 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 DimStore.GeographyKey → DimGeography.GeographyKey | 0 | 35 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 DimStore.EntityKey → DimEntity.EntityKey | 0 | 36 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 DimStore.EmployeeKey → DimEmployee.EmployeeKey | 1 | 37 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactExchangeRate.CurrencyKey → DimCurrency.CurrencyKey | 0 | 38 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactExchangeRate.DateKey → DimDate.DateKey | 0 | 39 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactITMachine.MachineKey → DimMachine.MachineKey | 0 | 40 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactITMachine.DateKey → DimDate.DateKey | 0 | 41 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactITSLA.DateKey → DimDate.DateKey | 0 | 42 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactITSLA.StoreKey → DimStore.StoreKey | 0 | 43 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactITSLA.MachineKey → DimMachine.MachineKey | 0 | 44 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactITSLA.OutageKey → DimOutage.OutageKey | 0 | 45 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactInventory.DateKey → DimDate.DateKey | 0 | 46 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactInventory.StoreKey → DimStore.StoreKey | 0 | 47 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactInventory.ProductKey → DimProduct.ProductKey | 533358 | 48 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactInventory.CurrencyKey → DimCurrency.CurrencyKey | 0 | 49 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactOnlineSales.DateKey → DimDate.DateKey | 0 | 50 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactOnlineSales.StoreKey → DimStore.StoreKey | 0 | 51 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactOnlineSales.ProductKey → DimProduct.ProductKey | 1715380 | 52 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactOnlineSales.PromotionKey → DimPromotion.PromotionKey | 0 | 53 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactOnlineSales.CurrencyKey → DimCurrency.CurrencyKey | 0 | 54 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactOnlineSales.CustomerKey → DimCustomer.CustomerKey | 0 | 55 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactSales.DateKey → DimDate.DateKey | 0 | 56 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactSales.channelKey → DimChannel.ChannelKey | 0 | 57 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactSales.StoreKey → DimStore.StoreKey | 0 | 58 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactSales.ProductKey → DimProduct.ProductKey | 338898 | 59 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactSales.PromotionKey → DimPromotion.PromotionKey | 0 | 60 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactSales.CurrencyKey → DimCurrency.CurrencyKey | 0 | 61 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactSalesQuota.ChannelKey → DimChannel.ChannelKey | 0 | 62 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactSalesQuota.StoreKey → DimStore.StoreKey | 0 | 63 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactSalesQuota.ProductKey → DimProduct.ProductKey | 521121 | 64 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactSalesQuota.DateKey → DimDate.DateKey | 0 | 65 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactSalesQuota.CurrencyKey → DimCurrency.CurrencyKey | 0 | 66 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactSalesQuota.ScenarioKey → DimScenario.ScenarioKey | 0 | 67 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactStrategyPlan.DateKey → DimDate.DateKey | 0 | 68 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactStrategyPlan.EntityKey → DimEntity.EntityKey | 0 | 69 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactStrategyPlan.ScenarioKey → DimScenario.ScenarioKey | 0 | 70 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactStrategyPlan.AccountKey → DimAccount.AccountKey | 0 | 71 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactStrategyPlan.CurrencyKey → DimCurrency.CurrencyKey | 0 | 72 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 孤儿键 FactStrategyPlan.ProductCategoryKey → DimProductCategory.ProductCategoryKey | 0 | 73 | 子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。 |
| 产品编码缺行 | 284 | 74 | 事实中不同缺失产品键数；不是受影响事实行数，上面的孤儿行逐表列出。 |
| 产品蓝色小写 | 2 | 75 | 非规范小写blue；Blue另列，二者不是重复产品。 |
| 产品蓝色大写 | 148 | 76 | 同颜色的另一种拼写。 |
| Silver Grey取值 | 14 | 77 | 混合色名称，不能未经业务裁决合并到Silver或Grey。 |
| 员工部门脏拼写 | 1 | 78 | 包括前导单引号及Contral拼写；不自动清洗。 |
| 促销名称拼写 | 3 | 79 | Scholl拼写的促销维表行。 |
| 国家名为空 | 3 | 80 | 上层地理节点；不将空名称误称为丢行。 |
| 客户收入离群档 | 385 | 81 | 离群值保留，不自行删掉。 |
| 门店面积离群档 | 2 | 82 | 不自行删掉。 |
| 门店员工数离群档 | 1 | 83 | 不自行删掉。 |
| 在营关店日期哨兵 | 294 | 84 | 哨兵值不是实际未来关店安排；该物理列为字符串。 |
| 款式名实为产品编码 | 2233 | 85 | 可疑命名字段；产品编码已存于StyleName，不能把它说成全部编码为空。 |
| 门店经理字段存员工号 | 306 | 86 | 字段语义陷阱；员工号不等于经理姓名。 |
| 销售辖区经理存员工号 | 265 | 87 | 与门店经理相同的字段语义陷阱。 |
| 全渠道挂促销但无折扣金额 | 446677 | 88 | 两种打折定义不等价。 |
| 线上挂促销但无折扣金额 | 0 | 89 | 与全渠道分开量化。 |
| 库存周频覆盖行数 | 8013099 | 90 | 全部库存行受快照频率约束；日期分布另查。 |
| 节假日标记天数 | 731 | 91 | 这是日期行数；本库与周末一致，不是公共假日真实性证明。 |
| 节假日与周末不一致 | 0 | 92 | 0表示本库的两种划分相同。 |
| 日期维度超出销售期间 | 1460 | 93 | 空日期若进均值分母会改变口径。 |
| 不同表国家命名差异 | 22 | 94 | 按已存在地理键比较，不用字符串猜对应关系。 |
| 销售表纯退货行 | 0 | 95 | 购买事件口径须明确是否纳入。 |
| 线上表纯退货行 | 100166 | 96 | 购买事件口径须明确是否纳入。 |

## 周频库存、首购退化与两种线上口径

### 库存日期分布（查询97）

| weekday | snapshot_days | affected_rows | first_day | last_day |
|---|---|---|---|---|
| 6 | 156 | 8013099 | 2007-01-06 | 2009-12-26 |

### 首购年份分布（查询98）

| first_year | customers |
|---|---|
| 2007 | 18868 |
| 2009 | 1 |

### 线上口径分歧（查询99）

| source | affected_rows | sales | returns |
|---|---|---|---|
| FactSales Online | 629223 | 2677599035.069384 | 32983261.287851 |
| FactOnlineSales | 12627608 | 2718202629.650406 | 29244318.203859 |

## 层级成环

沿每个节点的父链遍历，直到空父、缺失父或重复节点。自指根单列，长度≥2的闭环才计环节点；能沿父链进入该环的所有起点计受影响行。
使用下列查询取得完整键对后按quality.py中的遍历算法复算，不能仅用外键存在性推断层级无环。

| 层级表 | 环节点行数 | 可到达环的受影响行 | 自指根数 | 查询编号 |
|---|---|---|---|---|
| DimAccount | 2 | 24 | 0 | 100 |
| DimEmployee | 2 | 293 | 0 | 101 |
| DimEntity | 0 | 0 | 3 | 102 |

## 可复现查询

以下为逻辑SQL；脚本只将retail.表替换成file('$SEMDEBT_DATA_DIR/parquet/表.parquet','Parquet')，无筛选改写。

### Q1

```sql
SELECT count() AS n FROM retail.DimAccount
```

### Q2

```sql
SELECT count() AS n FROM retail.DimChannel
```

### Q3

```sql
SELECT count() AS n FROM retail.DimCurrency
```

### Q4

```sql
SELECT count() AS n FROM retail.DimCustomer
```

### Q5

```sql
SELECT count() AS n FROM retail.DimDate
```

### Q6

```sql
SELECT count() AS n FROM retail.DimEmployee
```

### Q7

```sql
SELECT count() AS n FROM retail.DimEntity
```

### Q8

```sql
SELECT count() AS n FROM retail.DimGeography
```

### Q9

```sql
SELECT count() AS n FROM retail.DimMachine
```

### Q10

```sql
SELECT count() AS n FROM retail.DimOutage
```

### Q11

```sql
SELECT count() AS n FROM retail.DimProduct
```

### Q12

```sql
SELECT count() AS n FROM retail.DimProductCategory
```

### Q13

```sql
SELECT count() AS n FROM retail.DimProductSubcategory
```

### Q14

```sql
SELECT count() AS n FROM retail.DimPromotion
```

### Q15

```sql
SELECT count() AS n FROM retail.DimSalesTerritory
```

### Q16

```sql
SELECT count() AS n FROM retail.DimScenario
```

### Q17

```sql
SELECT count() AS n FROM retail.DimStore
```

### Q18

```sql
SELECT count() AS n FROM retail.FactExchangeRate
```

### Q19

```sql
SELECT count() AS n FROM retail.FactITMachine
```

### Q20

```sql
SELECT count() AS n FROM retail.FactITSLA
```

### Q21

```sql
SELECT count() AS n FROM retail.FactInventory
```

### Q22

```sql
SELECT count() AS n FROM retail.FactOnlineSales
```

### Q23

```sql
SELECT count() AS n FROM retail.FactSales
```

### Q24

```sql
SELECT count() AS n FROM retail.FactSalesQuota
```

### Q25

```sql
SELECT count() AS n FROM retail.FactStrategyPlan
```

### Q26

```sql
SELECT count() AS n FROM retail.DimAccount WHERE ParentAccountKey IS NOT NULL AND ParentAccountKey NOT IN (SELECT AccountKey FROM retail.DimAccount)
```

### Q27

```sql
SELECT count() AS n FROM retail.DimCustomer WHERE GeographyKey IS NOT NULL AND GeographyKey NOT IN (SELECT GeographyKey FROM retail.DimGeography)
```

### Q28

```sql
SELECT count() AS n FROM retail.DimEmployee WHERE ParentEmployeeKey IS NOT NULL AND ParentEmployeeKey NOT IN (SELECT EmployeeKey FROM retail.DimEmployee)
```

### Q29

```sql
SELECT count() AS n FROM retail.DimEntity WHERE ParentEntityKey IS NOT NULL AND ParentEntityKey NOT IN (SELECT EntityKey FROM retail.DimEntity)
```

### Q30

```sql
SELECT count() AS n FROM retail.DimMachine WHERE StoreKey IS NOT NULL AND StoreKey NOT IN (SELECT StoreKey FROM retail.DimStore)
```

### Q31

```sql
SELECT count() AS n FROM retail.DimProduct WHERE ProductSubcategoryKey IS NOT NULL AND ProductSubcategoryKey NOT IN (SELECT ProductSubcategoryKey FROM retail.DimProductSubcategory)
```

### Q32

```sql
SELECT count() AS n FROM retail.DimProductSubcategory WHERE ProductCategoryKey IS NOT NULL AND ProductCategoryKey NOT IN (SELECT ProductCategoryKey FROM retail.DimProductCategory)
```

### Q33

```sql
SELECT count() AS n FROM retail.DimSalesTerritory WHERE GeographyKey IS NOT NULL AND GeographyKey NOT IN (SELECT GeographyKey FROM retail.DimGeography)
```

### Q34

```sql
SELECT count() AS n FROM retail.DimSalesTerritory WHERE EmployeeKey IS NOT NULL AND EmployeeKey NOT IN (SELECT EmployeeKey FROM retail.DimEmployee)
```

### Q35

```sql
SELECT count() AS n FROM retail.DimStore WHERE GeographyKey IS NOT NULL AND GeographyKey NOT IN (SELECT GeographyKey FROM retail.DimGeography)
```

### Q36

```sql
SELECT count() AS n FROM retail.DimStore WHERE EntityKey IS NOT NULL AND EntityKey NOT IN (SELECT EntityKey FROM retail.DimEntity)
```

### Q37

```sql
SELECT count() AS n FROM retail.DimStore WHERE EmployeeKey IS NOT NULL AND EmployeeKey NOT IN (SELECT EmployeeKey FROM retail.DimEmployee)
```

### Q38

```sql
SELECT count() AS n FROM retail.FactExchangeRate WHERE CurrencyKey IS NOT NULL AND CurrencyKey NOT IN (SELECT CurrencyKey FROM retail.DimCurrency)
```

### Q39

```sql
SELECT count() AS n FROM retail.FactExchangeRate WHERE DateKey IS NOT NULL AND DateKey NOT IN (SELECT DateKey FROM retail.DimDate)
```

### Q40

```sql
SELECT count() AS n FROM retail.FactITMachine WHERE MachineKey IS NOT NULL AND MachineKey NOT IN (SELECT MachineKey FROM retail.DimMachine)
```

### Q41

```sql
SELECT count() AS n FROM retail.FactITMachine WHERE DateKey IS NOT NULL AND DateKey NOT IN (SELECT DateKey FROM retail.DimDate)
```

### Q42

```sql
SELECT count() AS n FROM retail.FactITSLA WHERE DateKey IS NOT NULL AND DateKey NOT IN (SELECT DateKey FROM retail.DimDate)
```

### Q43

```sql
SELECT count() AS n FROM retail.FactITSLA WHERE StoreKey IS NOT NULL AND StoreKey NOT IN (SELECT StoreKey FROM retail.DimStore)
```

### Q44

```sql
SELECT count() AS n FROM retail.FactITSLA WHERE MachineKey IS NOT NULL AND MachineKey NOT IN (SELECT MachineKey FROM retail.DimMachine)
```

### Q45

```sql
SELECT count() AS n FROM retail.FactITSLA WHERE OutageKey IS NOT NULL AND OutageKey NOT IN (SELECT OutageKey FROM retail.DimOutage)
```

### Q46

```sql
SELECT count() AS n FROM retail.FactInventory WHERE DateKey IS NOT NULL AND DateKey NOT IN (SELECT DateKey FROM retail.DimDate)
```

### Q47

```sql
SELECT count() AS n FROM retail.FactInventory WHERE StoreKey IS NOT NULL AND StoreKey NOT IN (SELECT StoreKey FROM retail.DimStore)
```

### Q48

```sql
SELECT count() AS n FROM retail.FactInventory WHERE ProductKey IS NOT NULL AND ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)
```

### Q49

```sql
SELECT count() AS n FROM retail.FactInventory WHERE CurrencyKey IS NOT NULL AND CurrencyKey NOT IN (SELECT CurrencyKey FROM retail.DimCurrency)
```

### Q50

```sql
SELECT count() AS n FROM retail.FactOnlineSales WHERE DateKey IS NOT NULL AND DateKey NOT IN (SELECT DateKey FROM retail.DimDate)
```

### Q51

```sql
SELECT count() AS n FROM retail.FactOnlineSales WHERE StoreKey IS NOT NULL AND StoreKey NOT IN (SELECT StoreKey FROM retail.DimStore)
```

### Q52

```sql
SELECT count() AS n FROM retail.FactOnlineSales WHERE ProductKey IS NOT NULL AND ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)
```

### Q53

```sql
SELECT count() AS n FROM retail.FactOnlineSales WHERE PromotionKey IS NOT NULL AND PromotionKey NOT IN (SELECT PromotionKey FROM retail.DimPromotion)
```

### Q54

```sql
SELECT count() AS n FROM retail.FactOnlineSales WHERE CurrencyKey IS NOT NULL AND CurrencyKey NOT IN (SELECT CurrencyKey FROM retail.DimCurrency)
```

### Q55

```sql
SELECT count() AS n FROM retail.FactOnlineSales WHERE CustomerKey IS NOT NULL AND CustomerKey NOT IN (SELECT CustomerKey FROM retail.DimCustomer)
```

### Q56

```sql
SELECT count() AS n FROM retail.FactSales WHERE DateKey IS NOT NULL AND DateKey NOT IN (SELECT DateKey FROM retail.DimDate)
```

### Q57

```sql
SELECT count() AS n FROM retail.FactSales WHERE channelKey IS NOT NULL AND channelKey NOT IN (SELECT ChannelKey FROM retail.DimChannel)
```

### Q58

```sql
SELECT count() AS n FROM retail.FactSales WHERE StoreKey IS NOT NULL AND StoreKey NOT IN (SELECT StoreKey FROM retail.DimStore)
```

### Q59

```sql
SELECT count() AS n FROM retail.FactSales WHERE ProductKey IS NOT NULL AND ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)
```

### Q60

```sql
SELECT count() AS n FROM retail.FactSales WHERE PromotionKey IS NOT NULL AND PromotionKey NOT IN (SELECT PromotionKey FROM retail.DimPromotion)
```

### Q61

```sql
SELECT count() AS n FROM retail.FactSales WHERE CurrencyKey IS NOT NULL AND CurrencyKey NOT IN (SELECT CurrencyKey FROM retail.DimCurrency)
```

### Q62

```sql
SELECT count() AS n FROM retail.FactSalesQuota WHERE ChannelKey IS NOT NULL AND ChannelKey NOT IN (SELECT ChannelKey FROM retail.DimChannel)
```

### Q63

```sql
SELECT count() AS n FROM retail.FactSalesQuota WHERE StoreKey IS NOT NULL AND StoreKey NOT IN (SELECT StoreKey FROM retail.DimStore)
```

### Q64

```sql
SELECT count() AS n FROM retail.FactSalesQuota WHERE ProductKey IS NOT NULL AND ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)
```

### Q65

```sql
SELECT count() AS n FROM retail.FactSalesQuota WHERE DateKey IS NOT NULL AND DateKey NOT IN (SELECT DateKey FROM retail.DimDate)
```

### Q66

```sql
SELECT count() AS n FROM retail.FactSalesQuota WHERE CurrencyKey IS NOT NULL AND CurrencyKey NOT IN (SELECT CurrencyKey FROM retail.DimCurrency)
```

### Q67

```sql
SELECT count() AS n FROM retail.FactSalesQuota WHERE ScenarioKey IS NOT NULL AND ScenarioKey NOT IN (SELECT ScenarioKey FROM retail.DimScenario)
```

### Q68

```sql
SELECT count() AS n FROM retail.FactStrategyPlan WHERE DateKey IS NOT NULL AND DateKey NOT IN (SELECT DateKey FROM retail.DimDate)
```

### Q69

```sql
SELECT count() AS n FROM retail.FactStrategyPlan WHERE EntityKey IS NOT NULL AND EntityKey NOT IN (SELECT EntityKey FROM retail.DimEntity)
```

### Q70

```sql
SELECT count() AS n FROM retail.FactStrategyPlan WHERE ScenarioKey IS NOT NULL AND ScenarioKey NOT IN (SELECT ScenarioKey FROM retail.DimScenario)
```

### Q71

```sql
SELECT count() AS n FROM retail.FactStrategyPlan WHERE AccountKey IS NOT NULL AND AccountKey NOT IN (SELECT AccountKey FROM retail.DimAccount)
```

### Q72

```sql
SELECT count() AS n FROM retail.FactStrategyPlan WHERE CurrencyKey IS NOT NULL AND CurrencyKey NOT IN (SELECT CurrencyKey FROM retail.DimCurrency)
```

### Q73

```sql
SELECT count() AS n FROM retail.FactStrategyPlan WHERE ProductCategoryKey IS NOT NULL AND ProductCategoryKey NOT IN (SELECT ProductCategoryKey FROM retail.DimProductCategory)
```

### Q74

```sql
SELECT count() AS n FROM (SELECT DISTINCT ProductKey FROM retail.FactSales) WHERE ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)
```

### Q75

```sql
SELECT count() AS n FROM retail.DimProduct WHERE ColorName = 'blue'
```

### Q76

```sql
SELECT count() AS n FROM retail.DimProduct WHERE ColorName = 'Blue'
```

### Q77

```sql
SELECT count() AS n FROM retail.DimProduct WHERE ColorName = 'Silver Grey'
```

### Q78

```sql
SELECT count() AS n FROM retail.DimEmployee WHERE position(DepartmentName, 'Contral') > 0
```

### Q79

```sql
SELECT count() AS n FROM retail.DimPromotion WHERE position(PromotionName, 'Scholl') > 0
```

### Q80

```sql
SELECT count() AS n FROM retail.DimGeography WHERE RegionCountryName = ''
```

### Q81

```sql
SELECT count() AS n FROM retail.DimCustomer WHERE YearlyIncome = 10000000
```

### Q82

```sql
SELECT count() AS n FROM retail.DimStore WHERE SellingAreaSize = 93800
```

### Q83

```sql
SELECT count() AS n FROM retail.DimStore WHERE EmployeeCount = 325
```

### Q84

```sql
SELECT count() AS n FROM retail.DimStore WHERE CloseDate = '2090-12-31'
```

### Q85

```sql
SELECT count() AS n FROM retail.DimProduct WHERE startsWith(StyleName, 'Product')
```

### Q86

```sql
SELECT count() AS n FROM retail.DimStore WHERE StoreManager = toString(EmployeeKey)
```

### Q87

```sql
SELECT count() AS n FROM retail.DimSalesTerritory WHERE SalesTerritoryManager = toString(EmployeeKey)
```

### Q88

```sql
SELECT count() AS n FROM retail.FactSales WHERE PromotionKey != 1 AND DiscountAmount = 0
```

### Q89

```sql
SELECT count() AS n FROM retail.FactOnlineSales WHERE PromotionKey != 1 AND DiscountAmount = 0
```

### Q90

```sql
SELECT count() AS n FROM retail.FactInventory
```

### Q91

```sql
SELECT count() AS n FROM retail.DimDate WHERE IsHoliday = 'Yes'
```

### Q92

```sql
SELECT count() AS n FROM retail.DimDate WHERE (IsHoliday = 'Yes') != (toDayOfWeek(DateKey) IN (6,7))
```

### Q93

```sql
SELECT count() AS n FROM retail.DimDate WHERE DateKey < (SELECT min(DateKey) FROM retail.FactOnlineSales) OR DateKey > (SELECT max(DateKey) FROM retail.FactOnlineSales)
```

### Q94

```sql
SELECT count() AS n FROM retail.DimSalesTerritory t INNER JOIN retail.DimGeography g ON t.GeographyKey = g.GeographyKey WHERE t.SalesTerritoryCountry != g.RegionCountryName
```

### Q95

```sql
SELECT count() AS n FROM retail.FactSales WHERE SalesQuantity = 0 AND ReturnQuantity > 0
```

### Q96

```sql
SELECT count() AS n FROM retail.FactOnlineSales WHERE SalesQuantity = 0 AND ReturnQuantity > 0
```

### Q97

```sql
SELECT toDayOfWeek(DateKey) AS weekday, uniqExact(DateKey) AS snapshot_days, count() AS affected_rows, min(DateKey) AS first_day, max(DateKey) AS last_day FROM retail.FactInventory GROUP BY weekday ORDER BY weekday
```

### Q98

```sql
SELECT toYear(first_day) AS first_year, count() AS customers FROM (SELECT CustomerKey, min(DateKey) AS first_day FROM retail.FactOnlineSales GROUP BY CustomerKey) GROUP BY first_year ORDER BY first_year
```

### Q99

```sql
SELECT 'FactSales Online' AS source, count() AS affected_rows, sum(toDecimal128(SalesAmount,6)) AS sales, sum(toDecimal128(ReturnAmount,6)) AS returns FROM retail.FactSales WHERE channelKey = 2 UNION ALL SELECT 'FactOnlineSales', count(), sum(toDecimal128(SalesAmount,6)), sum(toDecimal128(ReturnAmount,6)) FROM retail.FactOnlineSales
```

### Q100

```sql
SELECT AccountKey AS child, ParentAccountKey AS parent FROM retail.DimAccount
```

### Q101

```sql
SELECT EmployeeKey AS child, ParentEmployeeKey AS parent FROM retail.DimEmployee
```

### Q102

```sql
SELECT EntityKey AS child, ParentEntityKey AS parent FROM retail.DimEntity
```
