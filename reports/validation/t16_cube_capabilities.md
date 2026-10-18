# T16 Cube 1.8.6 接口能力实测

本轮无模型调用，未执行任何题目查询；180 条探针全部来自语法说明、部署模型及通用控制。首批105条清单在读取18次冒烟报错前冻结；后续只隔离首批发现的类型、连接树、投影与数值问题。未改 render/、语义层、提示或评分器。

- 版本：Cube `1.8.6`；ClickHouse `25.8.20.4`；Tesseract 已开启，配置未变。
- 共 180 个探针，SQL 146 / JSON 34；接受 104、报错 76。接受不是正确性的同义词，独立数值对照见下文。
- SQL 原始错误直接由 psycopg 捕获，保留完整 str(exception) 与 SQLSTATE，未使用运行器错误分类来决定能力；JSON 沿用现有执行器，其 error/detail 为收到的服务端错误。每个原始查询、结果及 OID 见四个目录的 manifest.json/results.jsonl。
- 所有“成立”均限定为所列探针与条件，不是 SQL 语法全集证明；JSON 时间桶、日期边界、过滤、排序及双事实结果已对独立物理聚合核验。REST 列序按注解成员名对齐，不把列重排误判为错值。

## 逐条说明核验

| 条目 | 写法 | 判定 | 条件与证据 |
|---|---|---|---|
| SQL-1 | 只读单条 SELECT | **成立** | 探针只发送只读 SELECT/WITH；写操作未执行，执行器边界另有既有测试。 证据：`S01` |
| SQL-2 | cube/成员对象 | **成立** | 已定义成员可查询；不能据此推断任意物理 SQL 也支持。 证据：`S01,S02` |
| SQL-3 | MEASURE 与 GROUP BY | **成立** | 直接粒度的指标查询成立；SUM(MEASURE()) 同层嵌套反例失败，与说明一致。 证据：`S01,S02,S03` |
| SQL-4 | 多个 cube 的 CROSS JOIN | **有条件成立** | 必须有可用模型路径，且 SQL 的树形括号/顺序影响路径；两个维度 6 种平铺仅2种成功；三个维度24种平铺均失败，右嵌套 F32 数值正确。双事实直接平铺失败，但分别聚合 CTE 后 B01/B02 可且数值正确。普通 ON 原始 cube 失败。 证据：`S50_*,F30_*,F32,F33,S52_*,B01,B02,J03,J04` |
| SQL-5 | Postgres 标识符与大小写 | **有条件成立** | 双引号大写成员和普通中文别名成立；大小写成员混合重复投影可失败。中文输出别名+窗口后处理 T05 生成空标识符，不能承诺全部遵循 Postgres。 证据：`S01,S04,F24,T03,T04,T05,T06,T07` |
| SQL-6 | DATE/DATE_TRUNC/EXTRACT | **有条件成立** | 五粒度 DATE_TRUNC 与 DATE 字面量成立；EXTRACT 常量/外层桶成立，与 MEASURE 直接分组 S11 却触发引擎生成的未分组列错误。 证据：`S100,S101,S102,S103,S104,S11,F21,F22,F23` |
| SQL-7 | 维度筛选/HAVING | **成立** | 列举的维度运算、AND/OR、HAVING 在独立案例成立；组合到有缺陷的 CTE 不在此保证。 证据：`S20_*,S21` |
| SQL-8 | ORDER BY 别名/LIMIT | **成立** | 按指标别名排序及 LIMIT 成立。 证据：`S01,S21` |
| SQL-9 | 子查询/CTE 后算术、再聚合、排名、累计 | **有条件成立** | 简单再聚合/累计成立；双 CTE 必须核对输出别名及数值，S34_inner/left 执行成功却把数量列替换为金额，cross_filter 数值正确；F05 再聚合得到每组总和而不是组内值。UInt64 窗口输出需 BIGINT；仅筛选不输出可成立。不能无限外推普通 SQL 组合。 证据：`S30,S31,S32_*,S33_*,S34_*,F01,F02_*,F03,F04,F05,F06,S35_*,F10_*,F11_*,S37,B01,B02,B24,T05` |
| SQL-10 | 整数除法、DOUBLE、NULLIF | **成立** | 5/2=2，显式 DOUBLE=2.5，NULLIF 零分母得到 NULL。 证据：`S38,S40,S42_double` |
| SQL-11 | CASE/COALESCE | **有条件成立** | CASE 和 COALESCE(v,0) 成立；COALESCE(NULL,v) 即使 NULL 显式类型也触发数组长度错误，纯 VALUES 亦复现。 证据：`S38,F20_coalesce,F20_coalesce_cast,B22,B23` |
| SQL-12 | ROUND 与乘100 | **成立** | 数值舍入与百分比运算独立核验通过；S41 联合失败来自 COALESCE，而不是 ROUND。 证据：`F20_round,F20_pct` |
| JSON-1 | 一个对象及已有成员 | **成立** | 模型成员正例通过，未知成员反例报错。 证据：`J01,J02` |
| JSON-2 | 列举的查询键 | **成立** | 列举键均接受；额外 join/expression 键被拒绝。 证据：`J01,J10_*,J20_*,J23` |
| JSON-3 | 示例对象结构 | **成立** | 使用部署中真实通用成员替代甲乙占位符，结构成立。 证据：`J01,J20_equals,J23` |
| JSON-4 | 分组及多 cube 自动连接 | **有条件成立** | 已有可连路径的维度星形与双事实成功；不能写任意 join 条件。多成员允许不等于所有无路径 cube 都可连接。 证据：`J01,J03,J04,J05` |
| JSON-5 | 时间维度、五粒度、不写粒度 | **成立** | 五粒度及只区间过滤均对独立每日事实聚合重新分桶核验，含周/季度/年起始桶越出筛选区间的部分桶。 证据：`J10_*` |
| JSON-6 | 13个过滤运算、字符串 values、AND/OR | **成立** | 全部运算正例和分组值对独立基线核验；contains 的 o 也匹配 Online，按本次观测不区分大小写。日期前/后边界对严格与含边界两份物理聚合独立辨别。服务端还接受数值 values 数组，不影响文档的更严格客户端规范。 证据：`J20_*,J21_*,J24` |
| JSON-7 | 指标 filters/HAVING | **成立** | 指标正数过滤与独立汇总一致。 证据：`J22` |
| JSON-8 | 对象/数组 order | **成立** | 两种排序实际行序均与独立基线一致。 证据：`J01,J23` |
| JSON-9 | 不能临时表达式；只能定义好的计算 | **成立** | 临时指标表达式、临时维度、额外窗口表达式键均拒绝；预定义计算指标可执行。 证据：`J30,J31,J32,J33` |
| PERCENTILE_CONT | 用户追加核验 | **不成立** | 整数参数先被类型守卫拒绝；Float64 参数在纯 VALUES 中仍明确 execution is not implemented。仅指该函数实现，不证明分位数业务完全不可表达。 证据：`S60,S61,S62,F40,F41` |
| CAST | 用户追加核验 | **有条件成立** | 数字/文本及窗口 UInt64->BIGINT 成立；Interval(MonthDayNano)->Float64 明确不支持。 证据：`S42_*,S35_*_bigint,F11_*,S64,T01,T02` |
| AVG(interval) | 审计类型对照 | **不成立** | 时间戳列之差的 AVG、转 Float64 不成立；DATE 常量被优化为天数时成立，不能以常量正例替代列类型测试。 证据：`T01,T02,F42,F43` |

## 执行成功但数值错误的反例

独立基线为 ClickHouse 原始事实表的通用聚合（2007-02，渠道分组），不是题库参考。容差 rel_tol=1e-8、abs_tol=1e-6，仅用于部署能力核验，不改实验评分。
- `S34_inner/left`：两个 CTE 都把不同指标叫 v，且输出两个同名 v 时，第二列应为数量，却重复金额；cross_filter 数值正确，`F02_same_alias` 显式区分输出名后数值正确，`F02_distinct_alias` 也正确。因此不是“一概不能互连”。
- `F05`：聚合 CTE 与其按键派生 CTE 互连后再 SUM，每组误得全部渠道合计；等价 IN 半连接 `F06` 数值正确。不能把执行成功当成有效 SQL 后处理。
- `B01/B02` 跨事实的独立聚合 CTE 可互连且数值与物理事实表一致，故不得把直接多事实 CROSS JOIN 的失败外推为“两个事实永远无法同查”。

| 独立数值检查 | 通过 | 依据 |
|---|---|---|
| `S01` | 是 | ClickHouse channel_month |
| `S30` | 是 | ClickHouse channel_month |
| `S31` | 是 | ClickHouse channel_month |
| `F06` | 是 | ClickHouse channel_month |
| `B23` | 是 | ClickHouse channel_month |
| `S02` | 是 | ClickHouse channel_month totals |
| `S32_cte` | 是 | sum of complete grouped baseline |
| `S32_subquery` | 是 | sum of complete grouped baseline |
| `S33_cte` | 是 | regroup baseline keys |
| `S33_subquery` | 是 | regroup baseline keys |
| `S34_inner` | **否** | ClickHouse channel_month: amount and quantity must remain distinct |
| `S34_left` | **否** | ClickHouse channel_month: amount and quantity must remain distinct |
| `S34_cross_filter` | 是 | ClickHouse channel_month: amount and quantity must remain distinct |
| `F01` | 是 | ClickHouse channel_month: amount and quantity must remain distinct |
| `F02_same_alias` | 是 | ClickHouse channel_month: amount and quantity must remain distinct |
| `F02_distinct_alias` | 是 | ClickHouse channel_month: amount and quantity must remain distinct |
| `F03` | 是 | ClickHouse channel_month: amount and quantity must remain distinct |
| `F04` | 是 | ClickHouse channel_month: amount and quantity must remain distinct |
| `F05` | **否** | one row per key in both inputs: join + group must preserve per-key totals |
| `S35_ROW_NUMBER_bigint` | 是 | descending metric baseline has no ties; pg_oid=20 |
| `S35_RANK_bigint` | 是 | descending metric baseline has no ties; pg_oid=20 |
| `F10_ROW_NUMBER` | 是 | top two baseline values; window used only as filter |
| `F11_ROW_NUMBER` | 是 | top two with cast rank |
| `F10_RANK` | 是 | top two baseline values; window used only as filter |
| `F11_RANK` | 是 | top two with cast rank |
| `S40` | 是 | constant arithmetic |
| `S20_eq` | 是 | independent grouped predicate |
| `S20_ne` | 是 | independent grouped predicate |
| `S20_in` | 是 | independent grouped predicate |
| `S20_between` | 是 | independent grouped predicate |
| `S20_null` | 是 | independent grouped predicate |
| `S20_and_or` | 是 | independent grouped predicate |
| `S21` | 是 | HAVING all positive + alias DESC + LIMIT2 |
| `S37` | 是 | cumulative sum over independent ordered groups |
| `S38` | 是 | division, NULLIF, CASE and COALESCE(v,0) |
| `F20_round` | 是 | numeric ROUND |
| `F20_pct` | 是 | metric divided by itself times 100 |
| `F22` | 是 | EXTRACT in outer materialized time bucket |
| `F23` | 是 | calendar dimension alternative |
| `F32` | 是 | independent physical star join |
| `T03` | 是 | ASCII/non-ASCII aliases do not change baseline values without window projection |
| `T04` | 是 | ASCII/non-ASCII aliases do not change baseline values without window projection |
| `T06` | 是 | ASCII/non-ASCII aliases do not change baseline values without window projection |
| `T07` | 是 | ASCII/non-ASCII aliases do not change baseline values without window projection |
| `B01` | 是 | two separately aggregated fact baselines, FULL OUTER JOIN |
| `B02` | 是 | two separately aggregated fact baselines, INNER JOIN |
| `B25` | 是 | self CTE projection join |
| `B26` | 是 | self CTE filtered branch join |
| `B27` | 是 | conditional SUM partitions |
| `J01` | 是 | REST grouping and order vs independent physical aggregate |
| `J04` | 是 | independent fact totals, aligned by REST member annotation |
| `J20_equals` | 是 | independent channel totals and Python predicate |
| `J20_notEquals` | 是 | independent channel totals and Python predicate |
| `J20_contains` | 是 | independent channel totals and Python predicate |
| `J20_notContains` | 是 | independent channel totals and Python predicate |
| `J20_set` | 是 | independent channel totals and Python predicate |
| `J20_notSet` | 是 | independent channel totals and Python predicate |
| `J20_gt` | 是 | independent numeric predicate |
| `J20_gte` | 是 | independent numeric predicate |
| `J20_lt` | 是 | independent numeric predicate |
| `J20_lte` | 是 | independent numeric predicate |
| `J21_or` | 是 | OR of two disjoint equality filters |
| `J21_and` | 是 | AND of two disjoint equality filters |
| `J21_default` | 是 | default conjunction |
| `J22` | 是 | measure HAVING > 0 |
| `J23` | 是 | array order semantics |
| `J20_inDateRange` | 是 | inclusive date interval vs independent physical aggregate |
| `J20_beforeDate` | 是 | compare strict and inclusive boundary independently |
| `J20_afterDate` | 是 | compare strict and inclusive boundary independently |
| `J10_day` | 是 | independent daily fact totals, Python buckets, including partial boundary bucket |
| `S100` | 是 | DATE_TRUNC grouping independently reconstructed from daily fact totals |
| `J10_week` | 是 | independent daily fact totals, Python buckets, including partial boundary bucket |
| `S101` | 是 | DATE_TRUNC grouping independently reconstructed from daily fact totals |
| `J10_month` | 是 | independent daily fact totals, Python buckets, including partial boundary bucket |
| `S102` | 是 | DATE_TRUNC grouping independently reconstructed from daily fact totals |
| `J10_quarter` | 是 | independent daily fact totals, Python buckets, including partial boundary bucket |
| `S103` | 是 | DATE_TRUNC grouping independently reconstructed from daily fact totals |
| `J10_year` | 是 | independent daily fact totals, Python buckets, including partial boundary bucket |
| `S104` | 是 | DATE_TRUNC grouping independently reconstructed from daily fact totals |
| `J10_None` | 是 | independent daily fact totals, Python buckets, including partial boundary bucket |

## 清单冻结与复现

探针脚本不导入 questions、client 或任何 runs/ 输入。清单与源码哈希、冻结语法文档哈希、模型文件哈希见各目录 metadata.json。脚本在本轮工作区分阶段扩展，metadata.commit 是仓库基线而不是新增脚本的提交号；各次源码哈希分别记录。最终脚本已逐个精确再生成四份冻结清单，报告 JSON 另记最终两份脚本哈希。逐轮审计由另一个脚本读取既有错误文件，绝不把模型查询作为探针执行。

```sh
uv run python scripts/probe_cube_interfaces_t16.py --run-id <新的目录名> --suite base
# 同法分别以 --suite followup / boundary / types 执行到不同的新目录
uv run python scripts/report_cube_capabilities_t16.py
```

报告脚本默认读取本次四个固定目录，并只执行固定 ClickHouse SELECT 基线。新的探针 run-id 不得覆盖旧目录。原始基线行集另存数据目录 interface-probes，不入库。

## 逐条报错原文

成功查询无错误。以下为每个失败探针的完整错误文本，未按长度截断；成功结果、列 OID 和 Python 类型在 results.jsonl。

### S03

SQLSTATE：`58000`。

```text
Database Execution Error: Query failed: Error: Aggregate function sum(sales.SalesAmount) is found inside another aggregate function in query. ; query id: e9c1bf76-ddd9-444e-b419-3cc0af5c42d5-54798450-6719-403b-9e87-78ca5896f661
```

### S11

SQLSTATE：`22000`。

```text
Post-Processing Error: Database Execution Error: Query failed: Error: Column 'fk_aggregate.saleskey' is not under aggregate function and not in GROUP BY keys. In query cte_7 AS (SELECT fk_aggregate.saleskey AS saleskey, fk_aggregate.datekey AS datekey, fk_aggregate.channelkey AS channelkey, fk_aggregate.storekey AS storekey, fk_aggregate.productkey AS productkey, fk_aggregate.promotionkey AS promotionkey, fk_aggregate.currencykey AS currencykey, fk_aggregate.unitcost AS unitcost, fk_aggregate.unitprice AS unitprice, fk_aggregate.salesquantity AS salesquantity, fk_aggregate.returnquantity AS returnquantity, fk_aggregate.returnamount AS returnamount, fk_aggregate.discountquantity AS discountquantity, fk_aggregate.discountamount AS discountamount, fk_aggregate.totalcost AS totalcost, fk_aggregate.salesamount AS salesamount, fk_aggregate.__user AS __user, fk_aggregate.__cubejoinfield AS __cubejoinfield, sum(sum(fk_aggregate.sales__sales_amount)) OVER () AS sales__sales_amount_in_scope FROM cte_0 AS fk_aggregate). ; query id: 2092275a-e3e5-492a-af66-b6156fbc265a-b44eb48e-655b-44e4-9ba1-cc895388a676
```

### S35_ROW_NUMBER_native

SQLSTATE：`58000`。

```text
Database Execution Error: Type UInt64 is not supported in response transformation from Cube
```

### S36_ROW_NUMBER

SQLSTATE：`58000`。

```text
Database Execution Error: Type UInt64 is not supported in response transformation from Cube
```

### S35_RANK_native

SQLSTATE：`58000`。

```text
Database Execution Error: Type UInt64 is not supported in response transformation from Cube
```

### S36_RANK

SQLSTATE：`58000`。

```text
Database Execution Error: Type UInt64 is not supported in response transformation from Cube
```

### S41

SQLSTATE：`22000`。

```text
Post-Processing Error: Compute error: Cannot perform bitwise operation on arrays of different length
```

### S50_sales_store_channel

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,store', 'store,channel', 'store', 'channel', 'store', 'channel', 'sales'
```

### S50_sales_channel_store

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,channel', 'channel,store', 'channel', 'store', 'channel', 'sales'
```

### S50_store_channel_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'store,channel', 'channel,sales', 'store', 'channel', 'store', 'channel', 'sales'
```

### S50_channel_store_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'channel,store', 'store,sales', 'store', 'channel', 'store', 'channel', 'sales'
```

### S50_sales_store_channel_calendar

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,store', 'store,channel', 'channel,calendar', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### S50_sales_store_calendar_channel

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,store', 'store,calendar', 'calendar,channel', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### S50_sales_channel_store_calendar

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,channel', 'channel,store', 'store,calendar', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### S50_sales_channel_calendar_store

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,channel', 'channel,calendar', 'calendar,store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### S50_sales_calendar_store_channel

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,calendar', 'calendar,store', 'store,channel', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### S50_sales_calendar_channel_store

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,calendar', 'calendar,channel', 'channel,store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### S50_store_sales_channel_calendar

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'store,sales', 'sales,channel', 'channel,calendar', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### S50_store_channel_sales_calendar

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'store,channel', 'channel,sales', 'sales,calendar', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### S50_store_channel_calendar_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'store,channel', 'channel,calendar', 'calendar,sales', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### S51

SQLSTATE：`42000`。

```text
Planning Error: Initial planning error: Error during planning: Schema contains duplicate qualified field name 'sales.sales_amount'
QUERY: SELECT store."StoreKey", channel."ChannelName", MEASURE(sales.sales_amount) AS v FROM sales CROSS JOIN store CROSS JOIN sales CROSS JOIN channel WHERE sales."DateKey" >= DATE '2007-02-01' AND sales."DateKey" < DATE '2007-03-01' GROUP BY 1, 2 ORDER BY 1, 2 LIMIT 4
```

### S52_sales_online_sales_calendar

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,online_sales', 'online_sales,calendar', 'sales'
```

### S52_sales_calendar_online_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,calendar', 'calendar,online_sales', 'calendar', 'sales'
```

### S52_online_sales_sales_calendar

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'online_sales,sales', 'sales,calendar', 'sales'
```

### S52_online_sales_calendar_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'online_sales,calendar', 'calendar,sales', 'calendar', 'sales'
```

### S52_calendar_sales_online_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'calendar,sales', 'sales,online_sales', 'calendar', 'sales'
```

### S52_calendar_online_sales_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'calendar,online_sales', 'online_sales,sales', 'calendar', 'sales'
```

### S53

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,online_sales', 'sales'
```

### S60

SQLSTATE：`0A000`。

```text
Unsupported Error: percentile_cont(...) execution is not implemented
```

### S61

SQLSTATE：`0A000`。

```text
Unsupported Error: percentile_cont(...) execution is not implemented
```

### S62

SQLSTATE：`58000`。

```text
Database Execution Error: Query failed: Error: Column 'fk_aggregate.saleskey' is not under aggregate function and not in GROUP BY keys. In query cte_7 AS (SELECT fk_aggregate.saleskey AS saleskey, fk_aggregate.datekey AS datekey, fk_aggregate.channelkey AS channelkey, fk_aggregate.storekey AS storekey, fk_aggregate.productkey AS productkey, fk_aggregate.promotionkey AS promotionkey, fk_aggregate.currencykey AS currencykey, fk_aggregate.unitcost AS unitcost, fk_aggregate.unitprice AS unitprice, fk_aggregate.salesquantity AS salesquantity, fk_aggregate.returnquantity AS returnquantity, fk_aggregate.returnamount AS returnamount, fk_aggregate.discountquantity AS discountquantity, fk_aggregate.discountamount AS discountamount, fk_aggregate.totalcost AS totalcost, fk_aggregate.salesamount AS salesamount, fk_aggregate.__user AS __user, fk_aggregate.__cubejoinfield AS __cubejoinfield, sum(sum(fk_aggregate.sales__sales_amount)) OVER () AS sales__sales_amount_in_scope FROM cte_0 AS fk_aggregate). ; query id: 581f7c34-43c0-4571-98e4-1d26623e2e3f-9df68a26-6be7-4f7c-8cb7-90446f480e03
```

### J02

SQLSTATE：`None`。

```text
'not_a_member' not found for path 'sales.not_a_member'
```

### J05

SQLSTATE：`None`。

```text
Invalid query format: "join" is not allowed
```

### J30

SQLSTATE：`None`。

```text
Invalid query format: "measures[0]" with value "sales.sales_amount + sales.sales_quantity" fails to match the required pattern: /^[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+$/
```

### J31

SQLSTATE：`None`。

```text
Invalid query format: "dimensions[0]" with value "CAST(sales.channelKey AS TEXT)" fails to match the required pattern: /^[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)?$/
```

### J32

SQLSTATE：`None`。

```text
Invalid query format: "expression" is not allowed
```

### F20_coalesce

SQLSTATE：`22000`。

```text
Post-Processing Error: Compute error: Cannot perform bitwise operation on arrays of different length
```

### F20_coalesce_cast

SQLSTATE：`22000`。

```text
Post-Processing Error: Compute error: Cannot perform bitwise operation on arrays of different length
```

### F24

SQLSTATE：`XX000`。

```text
Rewrite Error: Can't detect Cube query and it may be not supported yet. Please check logs for additional information
QUERY: SELECT sales.channelkey, sales."channelKey", MEASURE(sales.sales_amount) FROM sales GROUP BY 1, 2 LIMIT 1
```

### F30_sales_store_channel_calendar

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,store', 'store,channel', 'channel,calendar', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_sales_store_calendar_channel

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,store', 'store,calendar', 'calendar,channel', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_sales_channel_store_calendar

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,channel', 'channel,store', 'store,calendar', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_sales_channel_calendar_store

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,channel', 'channel,calendar', 'calendar,store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_sales_calendar_store_channel

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,calendar', 'calendar,store', 'store,channel', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_sales_calendar_channel_store

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'sales,calendar', 'calendar,channel', 'channel,store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_store_sales_channel_calendar

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'store,sales', 'sales,channel', 'channel,calendar', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_store_sales_calendar_channel

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'store,sales', 'sales,calendar', 'calendar,channel', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_store_channel_sales_calendar

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'store,channel', 'channel,sales', 'sales,calendar', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_store_channel_calendar_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'store,channel', 'channel,calendar', 'calendar,sales', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_store_calendar_sales_channel

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'store,calendar', 'calendar,sales', 'sales,channel', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_store_calendar_channel_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'store,calendar', 'calendar,channel', 'channel,sales', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_channel_sales_store_calendar

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'channel,sales', 'sales,store', 'store,calendar', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_channel_sales_calendar_store

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'channel,sales', 'sales,calendar', 'calendar,store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_channel_store_sales_calendar

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'channel,store', 'store,sales', 'sales,calendar', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_channel_store_calendar_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'channel,store', 'store,calendar', 'calendar,sales', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_channel_calendar_sales_store

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'channel,calendar', 'calendar,sales', 'sales,store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_channel_calendar_store_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'channel,calendar', 'calendar,store', 'store,sales', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_calendar_sales_store_channel

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'calendar,sales', 'sales,store', 'store,channel', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_calendar_sales_channel_store

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'calendar,sales', 'sales,channel', 'channel,store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_calendar_store_sales_channel

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'calendar,store', 'store,sales', 'sales,channel', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_calendar_store_channel_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'calendar,store', 'store,channel', 'channel,sales', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_calendar_channel_sales_store

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'calendar,channel', 'channel,sales', 'sales,store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F30_calendar_channel_store_sales

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'calendar,channel', 'channel,store', 'store,sales', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F31

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'store,sales', 'channel,calendar', 'sales,channel', 'store', 'channel', 'calendar', 'store', 'channel', 'calendar', 'sales'
```

### F33

SQLSTATE：`XX000`。

```text
Rewrite Error: Can't detect Cube query and it may be not supported yet. Please check logs for additional information
QUERY: SELECT store."StoreKey", MEASURE(sales.sales_amount) FROM sales JOIN store ON sales."StoreKey" = store."StoreKey" WHERE sales."DateKey" >= DATE '2007-02-01' AND sales."DateKey" < DATE '2007-03-01' GROUP BY 1 LIMIT 4
```

### F34

SQLSTATE：`XX000`。

```text
Rewrite Error: Can't detect Cube query and it may be not supported yet. Please check logs for additional information
QUERY: WITH a AS (SELECT sales."channelKey" AS k, MEASURE(sales.sales_amount) AS v FROM sales WHERE sales."DateKey" >= DATE '2007-02-01' AND sales."DateKey" < DATE '2007-03-01' GROUP BY 1) SELECT a.k, a.v, channel."ChannelName" FROM a LEFT JOIN channel ON a.k = channel."ChannelKey" ORDER BY a.k
```

### F40

SQLSTATE：`42000`。

```text
Planning Error: WITHIN GROUP (ORDER BY ...) must be Float64 or Interval, got Int64
```

### F41

SQLSTATE：`0A000`。

```text
Unsupported Error: percentile_cont(...) execution is not implemented
```

### B03

SQLSTATE：`58000`。

```text
Database Execution Error: Can't find join path to join 'calendar,online_sales', 'sales,calendar', 'sales'
```

### B11

SQLSTATE：`58000`。

```text
Database Execution Error: Type UInt64 is not supported in response transformation from Cube
```

### B20

SQLSTATE：`42000`。

```text
Planning Error: Initial planning error: This feature is not implemented: Unsupported value TypedString(TypedString { data_type: Timestamp(None, None), value: ValueWithSpan { value: SingleQuotedString("2007-02-01 00:00:00"), span: Span(Location(1,41)..Location(1,62)) }, uses_odbc_syntax: false }) in a values list expression
QUERY: SELECT AVG(b - a) FROM (VALUES (TIMESTAMP '2007-02-01 00:00:00', TIMESTAMP '2007-02-03 00:00:00'), (TIMESTAMP '2007-02-02 00:00:00', TIMESTAMP '2007-02-03 00:00:00')) t (a, b)
```

### B21

SQLSTATE：`42000`。

```text
Planning Error: Initial planning error: This feature is not implemented: Unsupported value TypedString(TypedString { data_type: Timestamp(None, None), value: ValueWithSpan { value: SingleQuotedString("2007-02-01 00:00:00"), span: Span(Location(1,67)..Location(1,88)) }, uses_odbc_syntax: false }) in a values list expression
QUERY: SELECT AVG(CAST(b - a AS DOUBLE PRECISION)) FROM (VALUES (TIMESTAMP '2007-02-01 00:00:00', TIMESTAMP '2007-02-03 00:00:00'), (TIMESTAMP '2007-02-02 00:00:00', TIMESTAMP '2007-02-03 00:00:00')) t (a, b)
```

### B22

SQLSTATE：`22000`。

```text
Post-Processing Error: Compute error: Cannot perform bitwise operation on arrays of different length
```

### T01

SQLSTATE：`42000`。

```text
Planning Error: Initial planning error: Error during planning: The function Avg does not support inputs of type Interval(MonthDayNano).
QUERY: SELECT AVG(CAST(b AS TIMESTAMP) - CAST(a AS TIMESTAMP)) FROM (VALUES ('2007-02-01', '2007-02-03'), ('2007-02-02', '2007-02-03')) t (a, b)
```

### T02

SQLSTATE：`XX000`。

```text
Internal Error: Unsupported CAST from Interval(MonthDayNano) to Float64
```

### T05

SQLSTATE：`58000`。

```text
Database Execution Error: Query failed: Error: Syntax error: failed at position 16 (``) (line 1, col 16): ``, `a`.`v` `_1`, CAST(`a`.`row_number_order` AS BIGINT) `_2` 
FROM (
  SELECT ROW_NUMBER() OVER (ORDER BY `sales`.`measure_sales_sa` DESC NULLS FIRST) `row_numbe... Expected one of: ParserArrayOfJSONIdentifierDelimiter, token sequence, OpeningSquareBracket, Dot, token, OR, AND, IS NOT DISTINCT FROM, IS NULL, IS NOT NULL, BETWEEN, NOT BETWEEN, LIKE, ILIKE, NOT LIKE, NOT ILIKE, REGEXP, IN, NOT IN, GLOBAL IN, GLOBAL NOT IN, MOD, DIV, alias, AS, identifier, Comma, FROM, PREWHERE, WHERE, GROUP BY, WITH, HAVING, WINDOW, QUALIFY, ORDER BY, LIMIT, OFFSET, FETCH, SETTINGS, UNION, EXCEPT, INTERSECT, INTO OUTFILE, FORMAT, ParallelWithClause, PARALLEL WITH, end of query. ; query id: 84a457ad-e596-4cd5-b271-fbbf9ce6fa32-dc7a995e-fe99-4159-879f-8eccbb914167
```

