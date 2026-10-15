# 数据探查

写 L1 之前把这个库查清楚。`semantic/source.yaml` 里的**每一条事实陈述**（粒度、基数、
取值、孤儿行、金额对账）都来自这里的输出，不是凭对 schema 的印象写的。

盲模式下这是唯一的信息来源：建表语句（`vendor/cube/retail_schema.sql`）、
企业约定（`semantic/conventions.md`）、加上这几个脚本跑出来的数据探查。

## 脚本

| 脚本 | 查什么 | 产物 |
|---|---|---|
| `profile_columns.py` | 244 个列逐列：不同取值数、空值率、低基数字符串列的全部取值、数值与日期范围 | `out/columns.md`、`out/columns.json` |
| `profile_keys.py` | 48 个外键候选：指向哪张表、孤儿行、基数（一对一还是多对一）、维度覆盖率；25 张表的粒度是否唯一 | `out/keys.md`、`out/keys.json` |
| `check_conventions.py` | 把约定清单 15 条里能被数据证实或证伪的断言逐条跑一遍（45 条查询） | `out/conventions_check.md` |
| `profile_measures.py` | 金额列之间的算术关系、退货行的形态、打折的两种判定、三表对账、当前库存的规模（22 条查询） | `out/measures.md` |

## 重跑

```sh
uv run python semantic/profiling/profile_columns.py
uv run python semantic/profiling/profile_keys.py
uv run python semantic/profiling/check_conventions.py
uv run python semantic/profiling/profile_measures.py
```

四个脚本都只读 `$SEMDEBT_DATA_DIR/chdb`，用完即关会话（硬规则 9：一个数据目录不能被
两个进程同时打开，所以不要并行跑）。`out/` 下的文件是生成物，不要手改。

跑完之后用

```sh
uv run python semantic/schema/validate.py
```

核对 `source.yaml` 里写的数字还和数据一致（第 7 项检查会逐表核行数、逐关系核孤儿行和基数）。

## 一开始踩过的坑

`q()` 最初用 ClickHouse 的 `TabSeparated` 格式取结果，它会把取值里的 `'`、制表符、
反斜杠转义掉。`DimEmployee.DepartmentName` 的脏取值 `'Human Resources Contral`
因此变成了 `\'Human Resources Contral`，直接抄进 `source.yaml` 就是错的。
现在两个脚本都改用 `JSONCompact` 取结果。校验脚本的第 3 项会核对
「YAML 里列出的取值都真实存在」，就是为了挡住这类错误。

## 主要发现（细节见各份报告）

- **产品维度缺 284 行**，而四张事实表都引用了缺失的键：内连接产品表会让
  `FactSales` 少 338,898 行、726,129,808.32 销售额，而查询不会报错。
- **两张销售表的线上口径对不上**：差 4,060 万（1.5%）。
- **库存快照是每周六一次**（156 个日期），不是约定 11 说的每日。
- **「节假日」就是周末**：`IsHoliday = Yes` 恰好是全部周六周日。
- **约定 14 的「新客」几乎恒为空**：18,868/18,869 个客户首次购买都在 2007 年。
- **三方对账成立**：全渠道销售额合计 = 战略计划 Actual/Sale Revenue = 销售目标表
  Actual 场景 = 12,413,657,608.89。
- **渠道由门店唯一决定**：306 家门店没有一家跨渠道，渠道对比等价于门店类型对比。
- `DimStore.StoreManager`、`DimSalesTerritory.SalesTerritoryManager` 存的是**员工号**，
  不是姓名；`DimProduct.StyleName` 存的是**产品编码**，不是款式名。

与约定清单矛盾的四条已记进 `decisions/open-questions.md`（第 10 ~ 13 条），
全部数据质量问题记在 `semantic/source.yaml` 的 `data_quality` 节。
