# T16 v1.3 冒烟结果与失败复核（2026-10-19）

**用户批准高峰执行**，仅本轮两个冒烟单元；合计预算 3 元。实际运行提交 `22b6100`，main 基线 `d2801b1`；eval-v1.2 `90e13b3`、semantic-v1.3 `d2801b1`。命令用 `--allow-peak --concurrency 1 --budget 1.5 --est-fix-rate 1`：原生 budget 按错峰估算，高峰 x2，1.5 对应 3 元；不是实时扣费闸，本轮持续监看且实际低于上限。SQL 跑完再跑 JSON，指纹逐次检查。

## v2 离线重评结果

采用 `20261019-T16-pilot-v13-02-rescore-02`，修复 commit `c709ca5` 仅还原原始文件中 Cube 的 number 注解，不改评分器。第一次 rescore-01 因 Decimal 字符串未还原，JSON 4 条误降为 wrong，保留但不用于最终分数；第二次结果与运行时相同。

| 单元 | 全部23题（对/错/拒答/执行失败） | 主表19题（对/错/拒答/执行失败） | 主表准确率 | 低区分度4题（对/错/拒答/执行失败） | 调用 | 高峰费用（元） |
|---|---|---|---:|---|---:|---:|
| SQL-L2 | 13/6/0/4 | 10/6/0/3 | 52.6% | 3/0/0/1 | 30 | 0.98173872 |
| JSON-L2 | 6/6/10/1 | 5/4/9/1 | 26.3% | 1/2/1/0 | 25 | 0.43279032 |

合计 46 条作答、55 次调用，费用 **1.41452904 元**；预算剩余 1.58547096 元。55 次指纹全部为 `e72d3c7f663d3e1383b00b3884cb4501`，没有缺失/重复题次、judge 作答、非 done 行、打分 pending。低区分度题 Q17/Q68/Q69/Q76 单列。

## 最终执行失败中的接口能力限制占比

使用“最终执行失败的作答”为分母；修正前错误另外逐轮列示，拒答不放进执行失败分母。沿用上轮审计的区分：模型违反已述条件、说明条件未覆盖、接口硬能力限制分别计数，不能把运行器字符串分类直接当能力结论。

- **SQL-L2：4 条最终失败。** Q50 明确违反两 CTE 列名不同要求，且伴随中文别名条件缺失；Q76、Q82 对应已有通用正反例的说明条件缺失（组合归因中等置信度）；Q80 修正后原因未定位。**已证实硬能力限制 0/4，但 1/4 待定，所以不能把 0% 当作确定最终比例**。仅按剩余待定项的敏感性范围为 0–25%，可能跨越卡片20%门槛；不宣布冒烟通过、不推进全量。若把说明缺失对应的接口实现缺陷也合并计为广义接口故障，则至少 Q76、Q82 为2/4=50%（另有Q50混合因素、Q80待定）；这一口径不得混同“业务确实无法表达”。
- **JSON-L2：1 条最终失败。** Q34 两轮均额外引用 sales.DateKey，触发 inventory/sales 路径失败；冻结 inventory 模型已合并销售成本，通用单cube指标查询可执行，额外事实时间筛选反例失败。因此归为模型不必要的跨cube筛选，已证实硬能力限制 **0/1=0%**。这是对所见失败的归因，不证明所有JSON业务均可表达。10条拒答单列。

对照证据：`t16_pilot_v13_alias_controls.json` 10 条、`t16_pilot_v13_extra_controls.json` 6 条，均为独立通用查询，不读题目、不输入原候选、不额外调用模型。16条控制12成功、4报错；成功仅指可执行，不把没有独立值核验的结果当业务正确证明。

## 逐轮错误（含修正前）

共 SQL 11 次、JSON 3 次。以下报错直接取经哈希核验的原始执行文件，不脱敏，不改写原作答日志。

### SQL-L2 Q50 turn 0：规划器资源上限

10073 AST node limit；只证明该表达式触及重写上限，不证明同店计算不可表达。

```text
Rewrite Error: Can't find rewrite due to 10073 AST node limit reached. Please check logs for additional information
QUERY: WITH store_year AS (SELECT sales.StoreKey AS store_key, calendar.CalendarYear AS calendar_year, MEASURE(sales.sales_amount) AS sales_amount FROM sales CROSS JOIN calendar WHERE calendar.CalendarYear IN (2008, 2009) GROUP BY sales.StoreKey, calendar.CalendarYear), same_store_totals AS (SELECT SUM(CASE WHEN calendar_year = 2008 THEN sales_amount ELSE 0 END) AS sales_2008, SUM(CASE WHEN calendar_year = 2009 THEN sales_amount ELSE 0 END) AS sales_2009 FROM store_year WHERE store_key IN (SELECT store_key FROM store_year WHERE calendar_year = 2008) AND store_key IN (SELECT store_key FROM store_year WHERE calendar_year = 2009)) SELECT sales_2008 AS "2008年同店销售额", sales_2009 AS "2009年同店销售额", sales_2009 - sales_2008 AS "增长额", CAST(sales_2009 - sales_2008 AS DOUBLE PRECISION) / NULLIF(sales_2008, 0) * 100 AS "增长率(%)" FROM same_store_totals
```

### SQL-L2 Q50 turn 1：模型违反明确列名规则（伴随别名条件缺失）

两 CTE 均输出 store_key、sales_amount，违反 v1.3 的彼此不同要求；同时包含中文外层别名，通用 join_*_unicode 也报空标识符；未把任一因素单独宣布为唯一根因。

```text
Database Execution Error: Query failed: Error: Syntax error: failed at position 152 (``) (line 1, col 152): ``, (((CAST(`s2008`.`sum_s2008_sales__1` AS DOUBLE) - `s2008`.`sum_s2008_sales_`) / NULLIF(`s2008`.`sum_s2008_sales_`, 0)) * 100) `_1` 
FROM (
  SELECT SUM(`s2008... Expected one of: OR, AND, IS NOT DISTINCT FROM, IS NULL, IS NOT NULL, BETWEEN, NOT BETWEEN, LIKE, ILIKE, NOT LIKE, NOT ILIKE, REGEXP, IN, NOT IN, GLOBAL IN, GLOBAL NOT IN, MOD, DIV, alias, AS, identifier, token, Comma, FROM, PREWHERE, WHERE, GROUP BY, WITH, HAVING, WINDOW, QUALIFY, ORDER BY, LIMIT, OFFSET, FETCH, SETTINGS, UNION, EXCEPT, INTERSECT, INTO OUTFILE, FORMAT, ParallelWithClause, PARALLEL WITH, end of query. ; query id: acd1ea28-4c8a-4be8-8342-4f8a8eebf398-d8c43dd9-bf28-47dd-8c7a-965bf67948ae
```

### SQL-L2 Q70 turn 0：模型违反列名规则且说明条件未覆盖

两 CTE 均用 store_type；外层中文别名也落入通用 join_plain_unicode 失败族。修正后执行成功。

```text
Database Execution Error: Query failed: Error: Syntax error: failed at position 25 (``) (line 1, col 25): ``, `s`.`total_sales_amou` `_1`, `s`.`avg_selling_area` `_2` 
FROM (
  SELECT `s`.`store_type` `store_type`, `s`.`total_sales_amou` `total_sales_amou`, `a`.`store... Expected one of: ParserArrayOfJSONIdentifierDelimiter, token sequence, OpeningSquareBracket, Dot, token, OR, AND, IS NOT DISTINCT FROM, IS NULL, IS NOT NULL, BETWEEN, NOT BETWEEN, LIKE, ILIKE, NOT LIKE, NOT ILIKE, REGEXP, IN, NOT IN, GLOBAL IN, GLOBAL NOT IN, MOD, DIV, alias, AS, identifier, Comma, FROM, PREWHERE, WHERE, GROUP BY, WITH, HAVING, WINDOW, QUALIFY, ORDER BY, LIMIT, OFFSET, FETCH, SETTINGS, UNION, EXCEPT, INTERSECT, INTO OUTFILE, FORMAT, ParallelWithClause, PARALLEL WITH, end of query. ; query id: aa663c93-2967-439f-90b1-6d9abe387b51-ec8b3469-2e25-4076-82a7-12d803ceb014
```

### SQL-L2 Q71 turn 0：说明条件未覆盖

排名仅用于 WHERE、不输出名次；中文别名仍触发空标识符，改成英文后执行成功。v1.3 仅写输出有窗口结果时的例外；没有对该作答额外重跑。

```text
Database Execution Error: Query failed: Error: Syntax error: failed at position 33 (``) (line 1, col 33): ``, `ranked`.`subcategory_name` `_1`, `ranked`.`sales_amount` `_2` 
FROM (
  SELECT `subcategory_sales`.`category_name` `category_name`, `subcategory_sales`.`subc... Expected one of: ParserArrayOfJSONIdentifierDelimiter, token sequence, OpeningSquareBracket, Dot, token, OR, AND, IS NOT DISTINCT FROM, IS NULL, IS NOT NULL, BETWEEN, NOT BETWEEN, LIKE, ILIKE, NOT LIKE, NOT ILIKE, REGEXP, IN, NOT IN, GLOBAL IN, GLOBAL NOT IN, MOD, DIV, alias, AS, identifier, Comma, FROM, PREWHERE, WHERE, GROUP BY, WITH, HAVING, WINDOW, QUALIFY, ORDER BY, LIMIT, OFFSET, FETCH, SETTINGS, UNION, EXCEPT, INTERSECT, INTO OUTFILE, FORMAT, ParallelWithClause, PARALLEL WITH, end of query. ; query id: a5578042-4db0-4f12-94aa-dfc5fc212ef3-b739453a-1152-4edd-b8a5-bc9ad0d53cdf
```

### SQL-L2 Q73 turn 0：模型采用未聚合 cube 与聚合 CTE 的 ON 互连

prod 只是 product 的未聚合投影，不能据加 CTE 外壳认定变成两个聚合结果。v1.3 要在 MEASURE 层 CROSS JOIN 维度。修正成功。

```text
Rewrite Error: Use __cubeJoinField to join Cubes. Please check logs for additional information
QUERY: WITH inv AS (SELECT inventory.ProductKey AS product_key, MEASURE(inventory.current_on_hand_quantity) AS on_hand_qty, MEASURE(inventory.current_safety_stock_quantity) AS safety_stock_qty FROM inventory GROUP BY inventory.ProductKey), prod AS (SELECT product.ProductKey AS product_key, product.ProductName AS product_name FROM product), gaps AS (SELECT inv.product_key, COALESCE(prod.product_name, CAST(inv.product_key AS TEXT)) AS product_name, inv.on_hand_qty, inv.safety_stock_qty, inv.on_hand_qty - inv.safety_stock_qty AS gap_qty FROM inv LEFT JOIN prod ON inv.product_key = prod.product_key), ranked AS (SELECT product_key, product_name, on_hand_qty, safety_stock_qty, gap_qty, ROW_NUMBER() OVER (ORDER BY gap_qty DESC) AS rn FROM gaps) SELECT CAST(rn AS BIGINT) AS rank_no, product_key, product_name, on_hand_qty, safety_stock_qty, gap_qty FROM ranked WHERE rn <= 10 ORDER BY rn
```

### SQL-L2 Q76 turn 0：说明条件未覆盖（组合归因中等置信度）

不同输出名的聚合 CTE 互连后再聚合，用中文输出别名；join_aggregate_unicode 失败、ascii 成功。该族存在可执行控制，不证明整个业务做不到。

```text
Database Execution Error: Query failed: Error: Syntax error: failed at position 30 (``) (line 1, col 30): ``, `ccs`.`sum_ccs_sales_am` `_1`, `ccs`.`sum_case_when_cc` `_2`, ROUND(((100 * `ccs`.`sum_case_when_cc`) / NULLIF(`ccs`.`sum_ccs_sales_am`, 0)), 2) `_3` 
FROM (
... Expected one of: ParserArrayOfJSONIdentifierDelimiter, token sequence, OpeningSquareBracket, Dot, token, OR, AND, IS NOT DISTINCT FROM, IS NULL, IS NOT NULL, BETWEEN, NOT BETWEEN, LIKE, ILIKE, NOT LIKE, NOT ILIKE, REGEXP, IN, NOT IN, GLOBAL IN, GLOBAL NOT IN, MOD, DIV, alias, AS, identifier, Comma, FROM, PREWHERE, WHERE, GROUP BY, WITH, HAVING, WINDOW, QUALIFY, ORDER BY, LIMIT, OFFSET, FETCH, SETTINGS, UNION, EXCEPT, INTERSECT, INTO OUTFILE, FORMAT, ParallelWithClause, PARALLEL WITH, end of query. ; query id: 44db2818-d43d-4af4-9450-b9006f148693-cfc3d656-116b-4ab4-b104-a195187abe2d
```

### SQL-L2 Q76 turn 1：说明条件未覆盖（组合归因中等置信度）

仍为同一中文别名+聚合 CTE 互连组合；仅调整 CAST 与别名文字未绕开该条件。

```text
Database Execution Error: Query failed: Error: Syntax error: failed at position 30 (``) (line 1, col 30): ``, `ccs`.`sum_ccs_sales_am` `_1`, `ccs`.`sum_case_when_cc` `_2`, ROUND(((CAST(`ccs`.`sum_case_when_cc` AS DOUBLE) * 100) / NULLIF(CAST(`ccs`.`sum_ccs_sales_am`... Expected one of: ParserArrayOfJSONIdentifierDelimiter, token sequence, OpeningSquareBracket, Dot, token, OR, AND, IS NOT DISTINCT FROM, IS NULL, IS NOT NULL, BETWEEN, NOT BETWEEN, LIKE, ILIKE, NOT LIKE, NOT ILIKE, REGEXP, IN, NOT IN, GLOBAL IN, GLOBAL NOT IN, MOD, DIV, alias, AS, identifier, Comma, FROM, PREWHERE, WHERE, GROUP BY, WITH, HAVING, WINDOW, QUALIFY, ORDER BY, LIMIT, OFFSET, FETCH, SETTINGS, UNION, EXCEPT, INTERSECT, INTO OUTFILE, FORMAT, ParallelWithClause, PARALLEL WITH, end of query. ; query id: 7c67cce6-0a73-401d-98da-30eb9eb77634-f709fa11-bb47-4aaa-b81d-d6b6e98afb27
```

### SQL-L2 Q80 turn 0：模型违反明确禁止

AVG(interval) 是 v1.3 不要这样写的明确项。

```text
Planning Error: Initial planning error: Error during planning: The function Avg does not support inputs of type Interval(MonthDayNano).
QUERY: WITH customer_purchase_days AS (SELECT online_sales.CustomerKey AS CustomerKey, geography.RegionCountryName AS Country, online_sales.DateKey AS PurchaseDate FROM customer CROSS JOIN online_sales CROSS JOIN geography WHERE geography.RegionCountryName <> '' GROUP BY online_sales.CustomerKey, geography.RegionCountryName, online_sales.DateKey), customer_first_last AS (SELECT CustomerKey, Country, MIN(PurchaseDate) AS first_purchase_date, MAX(PurchaseDate) AS last_purchase_date FROM customer_purchase_days GROUP BY CustomerKey, Country), customer_days AS (SELECT Country, CustomerKey, last_purchase_date - first_purchase_date AS days_between FROM customer_first_last) SELECT Country AS "国家/地区", ROUND(AVG(days_between), 2) AS "平均相隔天数" FROM customer_days GROUP BY Country ORDER BY Country
```

### SQL-L2 Q80 turn 1：待定：生成 SQL 空标识符

DATE 转换后不再报 AVG(interval)，但仍在生成 SQL 中出现空标识符；date_cte、multi_dim_date、slash_alias、camel_alias 通用控制均成立，不能由此定位原组合原因。未重新执行原查询或按题改写。

```text
Database Execution Error: Query failed: Error: Syntax error: failed at position 34 (``) (line 1, col 34): ``, ROUND(`customer_days`.`avg_customer_day`, 2) `_1` 
FROM (
  SELECT `customer_days`.`country` `country`, AVG(`customer_days`.`days_between`) `avg_customer_day`... Expected one of: ParserArrayOfJSONIdentifierDelimiter, token sequence, OpeningSquareBracket, Dot, token, OR, AND, IS NOT DISTINCT FROM, IS NULL, IS NOT NULL, BETWEEN, NOT BETWEEN, LIKE, ILIKE, NOT LIKE, NOT ILIKE, REGEXP, IN, NOT IN, GLOBAL IN, GLOBAL NOT IN, MOD, DIV, alias, AS, identifier, Comma, FROM, PREWHERE, WHERE, GROUP BY, WITH, HAVING, WINDOW, QUALIFY, ORDER BY, LIMIT, OFFSET, FETCH, SETTINGS, UNION, EXCEPT, INTERSECT, INTO OUTFILE, FORMAT, ParallelWithClause, PARALLEL WITH, end of query. ; query id: d1799dc6-0344-4855-985b-c7ee050e0d6e-08907c65-3597-456f-acb3-c51619cb4160
```

### SQL-L2 Q82 turn 0：未聚合 cube 与聚合 CTE 互连，兼有未定位因素

managers 是 employee 的未聚合投影；ON 互连报 __cubeJoinField。含时间差平均等其他组合，不能把该轮全归一个因素。

```text
Rewrite Error: Use __cubeJoinField to join Cubes. Please check logs for additional information
QUERY: WITH direct_reports AS (SELECT employee."ParentEmployeeKey" AS parent_manager_key, COUNT(employee."EmployeeKey") AS direct_report_count, AVG((DATE '2009-12-31' - CAST(employee."HireDate" AS DATE)) / 365.25) AS avg_tenure_years FROM employee WHERE employee."ParentEmployeeKey" IS NOT NULL GROUP BY employee."ParentEmployeeKey"), managers AS (SELECT employee."EmployeeKey" AS employee_key, employee."LastName" AS manager_last_name, employee."FirstName" AS manager_first_name, employee."Title" AS manager_title FROM employee) SELECT managers.employee_key AS "经理员工号", managers.manager_last_name AS "经理姓", managers.manager_first_name AS "经理名", managers.manager_title AS "经理职级", direct_reports.direct_report_count AS "直属下属人数", direct_reports.avg_tenure_years AS "团队平均入职年限" FROM direct_reports JOIN managers ON managers.employee_key = direct_reports.parent_manager_key ORDER BY direct_reports.direct_report_count DESC, managers.manager_last_name, managers.manager_first_name
```

### SQL-L2 Q82 turn 1：说明条件未覆盖（组合归因中等置信度）

维度自连接+中文别名产生空标识符；self_cube_unicode 失败、ascii 可执行。只验证类型族的可执行性，不验证原业务答案或自连接结果语义。

```text
Database Execution Error: Query failed: Error: Syntax error: failed at position 27 (``) (line 1, col 27): ``, `e1`.`lastname` `_1`, `e1`.`firstname` `_2`, `e1`.`title` `_3`, `e1`.`count_e2_employe` `_4`, `e1`.`avg_datediff_utf` `_5` 
FROM (
  SELECT `employee`.Employe... Expected one of: ParserArrayOfJSONIdentifierDelimiter, token sequence, OpeningSquareBracket, Dot, token, OR, AND, IS NOT DISTINCT FROM, IS NULL, IS NOT NULL, BETWEEN, NOT BETWEEN, LIKE, ILIKE, NOT LIKE, NOT ILIKE, REGEXP, IN, NOT IN, GLOBAL IN, GLOBAL NOT IN, MOD, DIV, alias, AS, identifier, Comma, FROM, PREWHERE, WHERE, GROUP BY, WITH, HAVING, WINDOW, QUALIFY, ORDER BY, LIMIT, OFFSET, FETCH, SETTINGS, UNION, EXCEPT, INTERSECT, INTO OUTFILE, FORMAT, ParallelWithClause, PARALLEL WITH, end of query. ; query id: 11d6984c-1fdd-4d38-b13d-6aadee23425e-f040fa52-53d6-4f1c-907d-0b2906a0cc09
```

### JSON-L2 Q102 turn 0：模型写错成员名

product_category.product_category_name 不存在；v1.3 明确要求照模型成员原样抄写。修正成功。

```text
'product_category_name' not found for path 'product_category.product_category_name'
```

### JSON-L2 Q34 turn 0：模型增加不必要事实 cube 的筛选

inventory_turnover 在 inventory 中已使用合并销售成本，不必再引入 sales.DateKey；该参数要求额外 sales 连接路径而失败。通用 inventory 单 cube 正例成功，增加 sales 时间筛选反例失败。

```text
Can't find join path to join 'product', 'inventory', 'sales', 'inventory'
```

### JSON-L2 Q34 turn 1：模型增加不必要事实 cube 的筛选

把 timeDimensions 换成 filters 仍引用 sales.DateKey；错误连接图未消除。不能把没有该路径说成 JSON 的库存周转指标不可执行。

```text
Can't find join path to join 'product', 'inventory', 'sales', 'inventory'
```

## 完整性与下一步

```json
{
  "SQL-L2": {
    "responses": 30,
    "execution_files": 30,
    "log_sha256": "70a81ed10ea60194f7f4f99c77c665186c96f5e6dd2615f805f3a7ddbb8be959",
    "first_started_at": "2026-10-19T15:29:21+08:00",
    "last_started_at": "2026-10-19T15:40:43+08:00",
    "raw_sha256_verified": true,
    "complete_row_counts_verified": true,
    "low_qids": [
      "Q17",
      "Q68",
      "Q69",
      "Q76"
    ]
  },
  "JSON-L2": {
    "responses": 25,
    "execution_files": 15,
    "log_sha256": "39b45621001d21574265d912c85e257303d4fe5ec074cb5b98c6b459572fab04",
    "first_started_at": "2026-10-19T15:41:30+08:00",
    "last_started_at": "2026-10-19T15:45:50+08:00",
    "raw_sha256_verified": true,
    "complete_row_counts_verified": true,
    "low_qids": [
      "Q17",
      "Q68",
      "Q69",
      "Q76"
    ]
  }
}
```

响应55份、执行文件45份全部通过sha256校验；成功执行完整行集行数与日志一致。原始数据留在 `$SEMDEBT_DATA_DIR/runs-raw/20261019-T16-pilot-v13-02/`，不入库。执行文件中Decimal按字符串无损保存；重评按列注解还原数值，未改变原始文件。

提示/评分器/score_guard 与 main 逐字节一致；`harness/rescore.py` 的类型还原测试6项通过。该修复会在 #114 的说明中单列交 Claude Code 审核，用户合并。

本次不宣布 SQL 冒烟通过。全量仍为待估算、待批准、仅错峰：SQL-L2 v1.3、SQL-L2 v1.2、JSON-L2 各109题×3次。按此前“冒烟通过后再估全量”的顺序，本轮没有启动或估算全量；不修改semantic-v1.3，不创建semantic-v1.4。
