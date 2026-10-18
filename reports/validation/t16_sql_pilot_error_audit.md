# T16 SQL 冒烟18次执行报错重新归因

用户 2026-10-19 要求先实测，不选择保留或移至第二期。原日志只读、未改；本轮未重跑原题或原候选，也没有模型调用。以下依据冻结的通用探针及原始错误重归因，不改变评分器判定。

## 归因口径与汇总

- **写法说明错误**：包括明确不成立或遗漏必要条件、将有限 SQL 后处理泛化为普通 SQL。底层可以确有 bug 或限制，但如果可用条件/替代形态存在且说明未提示，不能直接计成“业务接口做不到”或模型错。
- **接口确实做不到**：仅限已实测的函数实现或算子/类型组合，不是对整个业务任务的不可表达证明。
- **模型写错**：有明确说明约束且实际输入违反；不因出现 not supported、生成 SQL 语法错误或引擎内部 GROUP BY 错误就归罪模型。
- 首要归因（互斥，仅用于这18次原始错误）：{'接口确实做不到': 3, '写法说明错误': 14, '模型写错': 1}。复杂组合中存在多种潜在问题，表中列出置信度和因果边界。
- 最终失败的7条仍原样保留；其中6条的最终错误首要归因是说明/条件缺失，1条为 PERCENTILE_CONT 实现缺失。**原先自动分类的 4/7=57.1% 不再视为已经证实的能力限制比例，也不据新的主归类比例自动放行实验。** 用户尚未裁决，JSON 冒烟与全量暂停。
- 后续正式运行固定使用用户指定的 eval-v1.2；旧 eval-v1.1 冒烟只作诊断，不能混入新版本正式结果。未修改 render/、语义层、提示或评分器；语法说明的任何更正须由 Claude Code 经用户裁决处理。

## 逐轮审计

| 题号/轮次 | 原自动类 | 首要归因 | 证据 | 依据与边界 | 置信度 |
|---|---|---|---|---|---|
| Q100 / t0 | engine_error | **接口确实做不到** | `F40,F41` | PERCENTILE_CONT 的整数排序输入缺少隐式类型支持；显式 Float64 仍执行未实现。函数不在说明列举项内，不能将该错误归为模型没有遵守说明。 | 高 |
| Q100 / t1 | interface_limitation | **接口确实做不到** | `S60,S61,F41` | 已经显式 Float64，仍报 percentile_cont execution is not implemented；纯 SQL VALUES 同错，排除题目与 Cube 模型口径。 | 高 |
| Q102 / t0 | engine_error | **写法说明错误** | `S50_sales_store_channel,F30_sales_store_channel_calendar,F32` | 说明 SQL-4 直接推荐多个 cube 平铺 CROSS JOIN，但未说明邻接边/连接树限制。该轮是同类 join-path 失败，不能据此指责模型或说业务无解。 | 高 |
| Q117 / t0 | engine_error | **写法说明错误** | `S50_sales_store_channel,F30_sales_calendar_store_channel,F32` | 事实后相邻两个维度的平铺顺序在部署图上不能形成计划；文档未说明须调整树形。 | 高 |
| Q117 / t1 | interface_limitation | **写法说明错误** | `S11,F22,F05,S35_ROW_NUMBER_bigint` | 该轮按说明使用 EXTRACT+MEASURE、多层 CTE 再聚合与窗口，却报不能识别 Cube 查询；独立探针证明这些组合有未说明的边界。不是精确最小复现，不能唯一定位复杂查询中首个失败节点，也不能声称没有合法替代形态。 | 中 |
| Q34 / t0 | engine_error | **写法说明错误** | `B01,B02,F34,F33` | 文档 SQL-9 将聚合 CTE 后处理说成普通 SQL，但聚合 CTE 再接原始维度/维度 CTE 会被重写为 Cube 连接。双事实 CTE 本身在 B01/B02 成立，不能笼统归为多事实接口不支持；该复杂组合的因果定位为中等置信度。 | 中 |
| Q34 / t1 | engine_error | **写法说明错误** | `S52_sales_online_sales_calendar,B03,B01,J04` | 两个事实加维度按 SQL-4 平铺，报 join path；通用控制证实平铺不可据任意顺序自动连接，而先分别聚合或用 REST 存在成功例。说明缺少连接形态条件，不能推出该业务一定不可做。 | 高 |
| Q50 / t0 | engine_error | **写法说明错误** | `F05,F06,F34` | 聚合 CTE 与其派生键集合 JOIN 被规划器当成 Cube 原始连接，要求隐藏 join field；文档 SQL-9 未说明这种不再等价于普通关系 SQL 的重写边界。F05 同类通用连接甚至静默错值。 | 高 |
| Q50 / t1 | engine_error | **写法说明错误** | `S11,F22,F23` | 输入按说明 EXTRACT(year,time) 与 MEASURE 分组，服务端生成 SQL 却引用未分组 saleskey；S11 在通用查询复现同类未分组内部列。输入并未选择该内部键，不是模型漏 GROUP BY 该列。 | 高 |
| Q71 / t0 | engine_error | **写法说明错误** | `T05,T03,T04,F11_RANK` | 原输入的窗口 CTE 与带引号中文输出别名符合 SQL-5/9；错误中的空反引号标识符出现在服务端生成 SQL。T05 用通用中文别名+窗口独立复现同型错误；普通中文别名与 ASCII/CAST 窗口正例可用。 | 高 |
| Q73 / t0 | engine_error | **写法说明错误** | `T05,B11,B12` | 服务端生成窗口投影的空标识符语法错误；通用 T05 复现，不是把模型输入 SQL 的语法错误误当执行器错误。中文别名/窗口组合和 UInt64 是可先后遮蔽的两个限制。 | 高 |
| Q73 / t1 | interface_limitation | **写法说明错误** | `S35_ROW_NUMBER_native,S35_ROW_NUMBER_bigint,B11,B12` | ROW_NUMBER 按说明输出，返回 UInt64 不能转 PostgreSQL 协议；显式 BIGINT 同类查询数值正确、OID20。文档没有要求这个必要转换，不能视为业务不可实现或模型无端写错。 | 高 |
| Q74 / t0 | engine_error | **写法说明错误** | `S50_sales_store_channel,F30_sales_store_channel_calendar,F32` | 相邻维度的平铺 CROSS JOIN 找不到路径，属于 SQL-4 未说明的顺序/括号条件。 | 高 |
| Q74 / t1 | interface_limitation | **写法说明错误** | `S35_ROW_NUMBER_native,S35_ROW_NUMBER_bigint` | 返回排名 UInt64 的响应变换失败，与通用窗口输出复现一致；BIGINT 正例说明不能按一条 unsupported 字符串认定接口整体无法排名。 | 高 |
| Q75 / t0 | engine_error | **写法说明错误** | `S11,F22,F23` | MEASURE 与 EXTRACT 分组触发内部 onlinesaleskey 未分组错误，模型输入没有引用该内部键。通用销售 cube 同样复现，说明 SQL-6/9 过宽。 | 高 |
| Q75 / t1 | engine_error | **写法说明错误** | `F34,B01,B02,F02_distinct_alias` | 双聚合 CTE 再联接维度 CTE 报要求隐藏 __cubeJoinField；单纯双 CTE 并不总失败，问题在与原始维度拼接的混合计划形态。说明缺少此边界，未以题目查询作改写实测，归因机制为中等置信度。 | 中 |
| Q80 / t0 | engine_error | **接口确实做不到** | `T01,T02,F42,F43` | 时间戳列之差形成 Interval(MonthDayNano)，当前 AVG 不接受该类型，转 Float64 也不支持。纯字符串 VALUES 转 timestamp 独立复现；DATE 常量可优化为天数，不能反证列类型支持。仅认定该算子/类型组合做不到，不表示天数业务无其他写法。 | 高 |
| Q82 / t0 | interface_limitation | **模型写错** | `F33,F34` | 该轮对原始 employee cube 写普通 JOIN ... ON（另一侧是 CTE），违反 SQL-4 明示的 cube 连接不写 ON；通用直接 ON 与 CTE 接原始 cube 控制均被拒绝。这个主归类仅针对明确的写法约束违反，并不证明其余日期/聚合表达式没有接口边界。 | 高 |

## 原始错误与哈希

源日志 SHA-256：`60f2566162dcc895567a3eb5e445563027ccee03a9e76c1f5a6ff07822f28355`。以下 error 文本逐字取自 runs-raw 执行文件；JSON 同时保留 detail。未抄题面、参考答案或候选完整 SQL 作为独立探针；错误原文本身若包含 QUERY，则按用户要求保留其原文，不代表该查询被重新执行。

### Q100 t0

原执行文件：`Q100_r1_t0.exec.json`；SHA-256：`01ed9119dcc5e24759e04bd6429cdea41f8faab8b6d1580ec834a4a046e6d979`。

```text
Planning Error: WITHIN GROUP (ORDER BY ...) must be Float64 or Interval, got Int64
```

### Q100 t1

原执行文件：`Q100_r1_t1.exec.json`；SHA-256：`92382883a3d81f6a6bfa031ac796601d9a2b5dd22891280a0e989b1c8d3ee7a4`。

```text
Unsupported Error: percentile_cont(...) execution is not implemented
```

### Q102 t0

原执行文件：`Q102_r1_t0.exec.json`；SHA-256：`ccbe6188345eee6797c8336c770922c8f174fbb1666f1b1ebee36efac6a76312`。

```text
Database Execution Error: Can't find join path to join 'online_sales,product', 'product,product_subcategory', 'product_subcategory,product_category', 'product_category,calendar', 'product_category', 'calendar', 'online_sales'
```

### Q117 t0

原执行文件：`Q117_r1_t0.exec.json`；SHA-256：`ae25b03f6b02decdb4ce85e29e1931aa7dff26086543b15352c0e9207d4cc9fa`。

```text
Internal Error: Can't find join path to join 'sales,calendar', 'calendar,store', 'calendar', 'sales'
QUERY: WITH store_year AS (SELECT st."StoreKey" AS store_key, st."StoreName" AS store_name, c."CalendarYear" AS yr, MEASURE(sales.sales_amount) AS sales_amount FROM sales CROSS JOIN calendar c CROSS JOIN store st WHERE c."CalendarYear" IN (2008, 2009) GROUP BY st."StoreKey", st."StoreName", c."CalendarYear"), store_pivot AS (SELECT store_key, store_name, SUM(CASE WHEN yr = 2008 THEN sales_amount ELSE 0 END) AS sales_2008, SUM(CASE WHEN yr = 2009 THEN sales_amount ELSE 0 END) AS sales_2009 FROM store_year GROUP BY store_key, store_name), store_decline AS (SELECT store_key, store_name, sales_2008, sales_2009, (sales_2008 - sales_2009) AS store_decline_amount, (sales_2008 - sales_2009) / NULLIF(CAST(sales_2008 AS DOUBLE PRECISION), 0) * 100 AS store_decline_pct FROM store_pivot WHERE sales_2008 > 0 AND sales_2009 > 0 AND sales_2009 < sales_2008), top_stores AS (SELECT store_key, store_name, store_decline_amount, store_decline_pct, ROW_NUMBER() OVER (ORDER BY store_decline_pct DESC) AS store_rank FROM store_decline ORDER BY store_decline_pct DESC LIMIT 3), store_category_year AS (SELECT st."StoreKey" AS store_key, st."StoreName" AS store_name, COALESCE(pc."ProductCategoryName", '未知产品') AS category_name, c."CalendarYear" AS yr, MEASURE(sales.sales_amount) AS sales_amount FROM sales CROSS JOIN calendar c CROSS JOIN store st CROSS JOIN product p CROSS JOIN product_subcategory ps CROSS JOIN product_category pc WHERE c."CalendarYear" IN (2008, 2009) GROUP BY st."StoreKey", st."StoreName", COALESCE(pc."ProductCategoryName", '未知产品'), c."CalendarYear"), store_category_pivot AS (SELECT store_key, store_name, category_name, SUM(CASE WHEN yr = 2008 THEN sales_amount ELSE 0 END) AS sales_2008, SUM(CASE WHEN yr = 2009 THEN sales_amount ELSE 0 END) AS sales_2009 FROM store_category_year GROUP BY store_key, store_name, category_name), category_decline AS (SELECT store_key, store_name, category_name, (sales_2008 - sales_2009) AS category_decline_amount, ROW_NUMBER() OVER (PARTITION BY store_key ORDER BY (sales_2008 - sales_2009) DESC) AS rn FROM store_category_pivot) SELECT t.store_rank AS "名次", t.store_name AS "门店", ROUND(t.store_decline_amount, 2) AS "门店销售额减少额", ROUND(t.store_decline_pct, 2) AS "门店降幅百分比", cd.category_name AS "拖累最多的产品品类", ROUND(cd.category_decline_amount, 2) AS "该品类销售减少额", ROUND(cd.category_decline_amount / NULLIF(CAST(t.store_decline_amount AS DOUBLE PRECISION), 0) * 100, 2) AS "占门店总减少额百分比" FROM top_stores t JOIN category_decline cd ON cd.store_key = t.store_key AND cd.rn = 1 ORDER BY t.store_rank
```

### Q117 t1

原执行文件：`Q117_r1_t1.exec.json`；SHA-256：`63b3ed54beb101ad42d865ef823b123d180d0ea1d3f67e1cfe2939960fe3839d`。

```text
Rewrite Error: Can't detect Cube query and it may be not supported yet. Please check logs for additional information
QUERY: WITH store_year AS (SELECT st."StoreKey" AS store_key, st."StoreName" AS store_name, EXTRACT(YEAR FROM sales."DateKey") AS yr, MEASURE(sales.sales_amount) AS sales_amount FROM store st CROSS JOIN sales GROUP BY st."StoreKey", st."StoreName", EXTRACT(YEAR FROM sales."DateKey")), store_pivot AS (SELECT store_key, store_name, SUM(CASE WHEN yr = 2008 THEN sales_amount ELSE 0 END) AS sales_2008, SUM(CASE WHEN yr = 2009 THEN sales_amount ELSE 0 END) AS sales_2009 FROM store_year GROUP BY store_key, store_name), store_decline AS (SELECT store_key, store_name, sales_2008, sales_2009, sales_2008 - sales_2009 AS store_decline_amount, (sales_2008 - sales_2009) / NULLIF(CAST(sales_2008 AS DOUBLE PRECISION), 0) * 100 AS store_decline_pct FROM store_pivot WHERE sales_2008 > 0 AND sales_2009 > 0 AND sales_2009 < sales_2008), top_stores AS (SELECT store_key, store_name, store_decline_amount, store_decline_pct, ROW_NUMBER() OVER (ORDER BY store_decline_pct DESC) AS store_rank FROM store_decline ORDER BY store_decline_pct DESC LIMIT 3), store_category_year AS (SELECT st."StoreKey" AS store_key, st."StoreName" AS store_name, pc."ProductCategoryName" AS category_name, EXTRACT(YEAR FROM sales."DateKey") AS yr, MEASURE(sales.sales_amount) AS sales_amount FROM store st CROSS JOIN sales CROSS JOIN product p CROSS JOIN product_subcategory ps CROSS JOIN product_category pc GROUP BY st."StoreKey", st."StoreName", pc."ProductCategoryName", EXTRACT(YEAR FROM sales."DateKey")), store_category_pivot AS (SELECT store_key, store_name, category_name, SUM(CASE WHEN yr = 2008 THEN sales_amount ELSE 0 END) AS sales_2008, SUM(CASE WHEN yr = 2009 THEN sales_amount ELSE 0 END) AS sales_2009 FROM store_category_year GROUP BY store_key, store_name, category_name), category_decline AS (SELECT store_key, store_name, category_name, sales_2008 - sales_2009 AS category_decline_amount, ROW_NUMBER() OVER (PARTITION BY store_key ORDER BY (sales_2008 - sales_2009) DESC) AS rn FROM store_category_pivot) SELECT t.store_rank AS "名次", t.store_name AS "门店", ROUND(t.store_decline_amount, 2) AS "门店销售额减少额", ROUND(t.store_decline_pct, 2) AS "门店降幅百分比", cd.category_name AS "拖累最多的产品品类", ROUND(cd.category_decline_amount, 2) AS "该品类销售减少额", ROUND(cd.category_decline_amount / NULLIF(CAST(t.store_decline_amount AS DOUBLE PRECISION), 0) * 100, 2) AS "占门店总减少额百分比" FROM top_stores t JOIN category_decline cd ON cd.store_key = t.store_key AND cd.rn = 1 ORDER BY t.store_rank
```

### Q34 t0

原执行文件：`Q34_r1_t0.exec.json`；SHA-256：`d63d845a3935fc5a202f84503802021b7b48b493858c7dd4e2fb37af73d09977`。

```text
Rewrite Error: Can not join Cubes. This is most likely due to one of the following reasons:
• one of the cubes contains a group by
• one of the cubes contains a measure
• the cube on the right contains a filter, sorting or limits
. Please check logs for additional information
QUERY: WITH sales_cost AS (SELECT sales."ProductKey" AS product_key, MEASURE(sales.total_cost) AS total_cost FROM sales WHERE EXTRACT(YEAR FROM sales."DateKey") = 2009 GROUP BY sales."ProductKey"), inventory_value AS (SELECT inventory."ProductKey" AS product_key, MEASURE(inventory.average_on_hand_value) AS avg_on_hand_value FROM inventory WHERE EXTRACT(YEAR FROM inventory."DateKey") = 2009 GROUP BY inventory."ProductKey"), product_list AS (SELECT product."ProductKey" AS product_key, product."ProductName" AS product_name FROM product) SELECT COALESCE(p.product_name, CAST(COALESCE(s.product_key, i.product_key) AS TEXT)) AS product, s.total_cost AS total_cost, i.avg_on_hand_value AS avg_on_hand_inventory_value, ROUND(s.total_cost / NULLIF(i.avg_on_hand_value, 0), 4) AS inventory_turnover FROM sales_cost s FULL JOIN inventory_value i ON s.product_key = i.product_key LEFT JOIN product_list p ON p.product_key = COALESCE(s.product_key, i.product_key) ORDER BY inventory_turnover DESC NULLS LAST, product
```

### Q34 t1

原执行文件：`Q34_r1_t1.exec.json`；SHA-256：`5f82cc08b3702dbc39abd6fbcea441542d5fe44f74092910c2680678fa8e6a50`。

```text
Internal Error: Can't find join path to join 'sales,inventory', 'inventory,product', 'sales', 'inventory', 'sales'
QUERY: WITH agg AS (SELECT product."ProductKey" AS product_key, product."ProductName" AS product_name, MEASURE(sales.total_cost) AS total_cost, MEASURE(inventory.average_on_hand_value) AS avg_on_hand_inventory_value FROM sales CROSS JOIN inventory CROSS JOIN product WHERE EXTRACT(YEAR FROM sales."DateKey") = 2009 AND EXTRACT(YEAR FROM inventory."DateKey") = 2009 GROUP BY product."ProductKey", product."ProductName") SELECT COALESCE(product_name, CAST(product_key AS TEXT)) AS product, total_cost, avg_on_hand_inventory_value, ROUND(total_cost / NULLIF(avg_on_hand_inventory_value, 0), 4) AS inventory_turnover FROM agg ORDER BY inventory_turnover DESC NULLS LAST, product
```

### Q50 t0

原执行文件：`Q50_r1_t0.exec.json`；SHA-256：`561941058dfce486349d4b799e28c83b836ef6ca149d437aa3f2387b0cbbec79`。

```text
Rewrite Error: Use __cubeJoinField to join Cubes. Please check logs for additional information
QUERY: WITH store_year AS (SELECT sales."StoreKey" AS store_key, EXTRACT(YEAR FROM sales."DateKey") AS yr, MEASURE(sales.sales_amount) AS sales_amount FROM sales WHERE sales."DateKey" >= DATE '2008-01-01' AND sales."DateKey" < DATE '2010-01-01' GROUP BY sales."StoreKey", EXTRACT(YEAR FROM sales."DateKey")), same_store_keys AS (SELECT store_key FROM store_year GROUP BY store_key HAVING COUNT(DISTINCT yr) = 2), year_totals AS (SELECT sy.yr, SUM(sy.sales_amount) AS sales_amount FROM store_year sy JOIN same_store_keys k ON sy.store_key = k.store_key GROUP BY sy.yr) SELECT SUM(CASE WHEN yr = 2008 THEN sales_amount END) AS "2008同店销售额", SUM(CASE WHEN yr = 2009 THEN sales_amount END) AS "2009同店销售额", SUM(CASE WHEN yr = 2009 THEN sales_amount END) - SUM(CASE WHEN yr = 2008 THEN sales_amount END) AS "增长额", ROUND((SUM(CASE WHEN yr = 2009 THEN sales_amount END) - SUM(CASE WHEN yr = 2008 THEN sales_amount END)) / NULLIF(SUM(CASE WHEN yr = 2008 THEN sales_amount END), 0) * 100, 2) AS "增长率百分比" FROM year_totals
```

### Q50 t1

原执行文件：`Q50_r1_t1.exec.json`；SHA-256：`0037caa3f8b2833941549d10d447e7d327715fa3dd12f3b3a4608dd1677a376c`。

```text
Post-Processing Error: Database Execution Error: Query failed: Error: Column 'fk_aggregate.saleskey' is not under aggregate function and not in GROUP BY keys. In query cte_7 AS (SELECT fk_aggregate.saleskey AS saleskey, fk_aggregate.datekey AS datekey, fk_aggregate.channelkey AS channelkey, fk_aggregate.storekey AS storekey, fk_aggregate.productkey AS productkey, fk_aggregate.promotionkey AS promotionkey, fk_aggregate.currencykey AS currencykey, fk_aggregate.unitcost AS unitcost, fk_aggregate.unitprice AS unitprice, fk_aggregate.salesquantity AS salesquantity, fk_aggregate.returnquantity AS returnquantity, fk_aggregate.returnamount AS returnamount, fk_aggregate.discountquantity AS discountquantity, fk_aggregate.discountamount AS discountamount, fk_aggregate.totalcost AS totalcost, fk_aggregate.salesamount AS salesamount, fk_aggregate.__user AS __user, fk_aggregate.__cubejoinfield AS __cubejoinfield, sum(sum(fk_aggregate.sales__sales_amount)) OVER () AS sales__sales_amount_in_scope FROM cte_0 AS fk_aggregate). ; query id: 41b86f2f-08ec-4ba3-b0ed-f78b20b767b3-b8c1cdd6-449e-49d9-8ca7-354ef3d78521
```

### Q71 t0

原执行文件：`Q71_r1_t0.exec.json`；SHA-256：`089a0c9bae68163cc5f4d8a0b6d81bd3653942fd0b188dd411f1f6d8f4aa2586`。

```text
Database Execution Error: Query failed: Error: Syntax error: failed at position 33 (``) (line 1, col 33): ``, `ranked`.`subcategory_name` `_1`, `ranked`.`sales_amount` `_2` 
FROM (
  SELECT `subcategory_sales`.`category_name` `category_name`, `subcategory_sales`.`subc... Expected one of: ParserArrayOfJSONIdentifierDelimiter, token sequence, OpeningSquareBracket, Dot, token, OR, AND, IS NOT DISTINCT FROM, IS NULL, IS NOT NULL, BETWEEN, NOT BETWEEN, LIKE, ILIKE, NOT LIKE, NOT ILIKE, REGEXP, IN, NOT IN, GLOBAL IN, GLOBAL NOT IN, MOD, DIV, alias, AS, identifier, Comma, FROM, PREWHERE, WHERE, GROUP BY, WITH, HAVING, WINDOW, QUALIFY, ORDER BY, LIMIT, OFFSET, FETCH, SETTINGS, UNION, EXCEPT, INTERSECT, INTO OUTFILE, FORMAT, ParallelWithClause, PARALLEL WITH, end of query. ; query id: afe0b12a-11e2-4523-9c69-e0cf14bbff39-37eaf097-ede2-49f0-99da-387186e78904
```

### Q73 t0

原执行文件：`Q73_r1_t0.exec.json`；SHA-256：`70e0942a25a38f1135ca1b7f5ff5cca4b6b3784bf04b8a31e80b70545ed12d2f`。

```text
Database Execution Error: Query failed: Error: Syntax error: failed at position 22 (``) (line 1, col 22): ``, `ranked`.`product_key` `_1`, `ranked`.`product_name` `_2`, `ranked`.`current_on_hand` `_3`, `ranked`.`safety_stock` `_4`, `ranked`.`difference` `_5` 
FROM (
 ... Expected one of: ParserArrayOfJSONIdentifierDelimiter, token sequence, OpeningSquareBracket, Dot, token, OR, AND, IS NOT DISTINCT FROM, IS NULL, IS NOT NULL, BETWEEN, NOT BETWEEN, LIKE, ILIKE, NOT LIKE, NOT ILIKE, REGEXP, IN, NOT IN, GLOBAL IN, GLOBAL NOT IN, MOD, DIV, alias, AS, identifier, Comma, FROM, PREWHERE, WHERE, GROUP BY, WITH, HAVING, WINDOW, QUALIFY, ORDER BY, LIMIT, OFFSET, FETCH, SETTINGS, UNION, EXCEPT, INTERSECT, INTO OUTFILE, FORMAT, ParallelWithClause, PARALLEL WITH, end of query. ; query id: 4fede854-525e-42b6-9a8c-823225141f2b-7b9d36c5-a197-484e-b4fd-8087b8f42e9f
```

### Q73 t1

原执行文件：`Q73_r1_t1.exec.json`；SHA-256：`d42635545ff65a18faf162a7779ddb09c38984bcc78c20b92ed9dc1aa65aab9d`。

```text
Database Execution Error: Type UInt64 is not supported in response transformation from Cube
```

### Q74 t0

原执行文件：`Q74_r1_t0.exec.json`；SHA-256：`e6581bf483965714549e918c87d5663ffebae5b3fcb11d894bb38b3488d28265`。

```text
Internal Error: Can't find join path to join 'sales,store', 'store,calendar', 'store', 'sales', 'calendar', 'store', 'sales'
QUERY: WITH product_sales AS (SELECT store.StoreName AS store_name, sales.ProductKey AS product_key, MEASURE(sales.sales_amount) AS product_sales FROM sales CROSS JOIN store CROSS JOIN calendar WHERE calendar.CalendarYear = 2009 AND store.StoreType = 'Store' GROUP BY store.StoreName, sales.ProductKey), product_names AS (SELECT product.ProductKey AS product_key, product.ProductName AS product_name FROM product GROUP BY product.ProductKey, product.ProductName), ranked AS (SELECT ps.store_name, ps.product_key, COALESCE(pn.product_name, 'ProductKey ' || CAST(ps.product_key AS VARCHAR)) AS product_name, ps.product_sales, SUM(ps.product_sales) OVER (PARTITION BY ps.store_name) AS store_sales, ROW_NUMBER() OVER (PARTITION BY ps.store_name ORDER BY ps.product_sales DESC, ps.product_key) AS rn FROM product_sales ps LEFT JOIN product_names pn ON ps.product_key = pn.product_key) SELECT store_name AS "门店", rn AS "名次", product_name AS "产品", product_sales AS "销售额", ROUND(CAST(product_sales AS DOUBLE PRECISION) / NULLIF(store_sales, 0), 4) AS "占门店销售总额比例" FROM ranked WHERE rn <= 3 ORDER BY store_name, rn
```

### Q74 t1

原执行文件：`Q74_r1_t1.exec.json`；SHA-256：`d42635545ff65a18faf162a7779ddb09c38984bcc78c20b92ed9dc1aa65aab9d`。

```text
Database Execution Error: Type UInt64 is not supported in response transformation from Cube
```

### Q75 t0

原执行文件：`Q75_r1_t0.exec.json`；SHA-256：`1066aec761f52656e9304ba80643965de0ea80f6f65cce8b362a871b3b3bb8b4`。

```text
Post-Processing Error: Execution error: Database Execution Error: Query failed: Error: Column 'fk_aggregate.onlinesaleskey' is not under aggregate function and not in GROUP BY keys. In query cte_7 AS (SELECT fk_aggregate.onlinesaleskey AS onlinesaleskey, fk_aggregate.datekey AS datekey, fk_aggregate.storekey AS storekey, fk_aggregate.productkey AS productkey, fk_aggregate.promotionkey AS promotionkey, fk_aggregate.currencykey AS currencykey, fk_aggregate.customerkey AS customerkey, fk_aggregate.salesordernumber AS salesordernumber, fk_aggregate.salesorderlinenu AS salesorderlinenu, fk_aggregate.salesquantity AS salesquantity, fk_aggregate.salesamount AS salesamount, fk_aggregate.returnquantity AS returnquantity, fk_aggregate.returnamount AS returnamount, fk_aggregate.discountquantity AS discountquantity, fk_aggregate.discountamount AS discountamount, fk_aggregate.totalcost AS totalcost, fk_aggregate.unitcost AS unitcost, fk_aggregate.unitprice AS unitprice, fk_aggregate.__user AS __user, fk_aggregate.__cubejoinfield AS __cubejoinfield, fk_aggregate.customerkey_1 AS customerkey_1, fk_aggregate.geographykey AS geographykey, fk_aggregate.firstname AS firstname, fk_aggregate.lastname AS lastname, fk_aggregate.birthdate AS birthdate, fk_aggregate.maritalstatus AS maritalstatus, fk_aggregate.gender AS gender, fk_aggregate.yearlyincome AS yearlyincome, fk_aggregate.totalchildren AS totalchildren, fk_aggregate.numberchildrenat AS numberchildrenat, fk_aggregate.education AS education, fk_aggregate.occupation AS occupation, fk_aggregate.houseownerflag AS houseownerflag, fk_aggregate.numbercarsowned AS numbercarsowned, fk_aggregate.__user_1 AS __user_1, fk_aggregate.__cubejoinfield_1 AS __cubejoinfield_1, sum(sum(fk_aggregate.online_sales__sales_amount)) OVER () AS online_sales__sales_amount_in_scope FROM cte_0 AS fk_aggregate). ; query id: 37c68eb0-d900-4d7c-a636-d947e8322b15-c15f6a93-a86d-4ce1-9fcd-587a798db911
```

### Q75 t1

原执行文件：`Q75_r1_t1.exec.json`；SHA-256：`1466d9c680e3296a2adaf55055751bb6dc9954d6f77a3693371f2a31b3f0e92c`。

```text
Rewrite Error: Use __cubeJoinField to join Cubes. Please check logs for additional information
QUERY: WITH s2008 AS (SELECT online_sales."CustomerKey" AS customer_key, MEASURE(online_sales.sales_amount) AS sales_2008 FROM online_sales WHERE online_sales."DateKey" >= DATE '2008-01-01' AND online_sales."DateKey" <= DATE '2008-12-31' GROUP BY online_sales."CustomerKey"), s2009 AS (SELECT online_sales."CustomerKey" AS customer_key, MEASURE(online_sales.sales_amount) AS sales_2009 FROM online_sales WHERE online_sales."DateKey" >= DATE '2009-01-01' AND online_sales."DateKey" <= DATE '2009-12-31' GROUP BY online_sales."CustomerKey"), cust AS (SELECT customer."CustomerKey" AS customer_key, customer."FirstName" AS first_name, customer."LastName" AS last_name FROM customer) SELECT s2009.customer_key, CASE WHEN NULLIF(cust.first_name, 'Not Provided') IS NULL AND NULLIF(cust.last_name, 'Not Provided') IS NULL THEN 'Customer ' || CAST(s2009.customer_key AS TEXT) WHEN NULLIF(cust.first_name, 'Not Provided') IS NULL THEN cust.last_name || ' (Customer ' || CAST(s2009.customer_key AS TEXT) || ')' WHEN NULLIF(cust.last_name, 'Not Provided') IS NULL THEN cust.first_name || ' (Customer ' || CAST(s2009.customer_key AS TEXT) || ')' ELSE cust.first_name || ' ' || cust.last_name END AS customer_name, s2008.sales_2008 AS sales_2008, s2009.sales_2009 AS sales_2009, s2009.sales_2009 - s2008.sales_2008 AS increase_amount, ROUND((s2009.sales_2009 - s2008.sales_2008) / NULLIF(s2008.sales_2008, 0) * 100, 2) AS growth_pct FROM s2008 JOIN s2009 ON s2008.customer_key = s2009.customer_key LEFT JOIN cust ON cust.customer_key = s2009.customer_key WHERE s2008.sales_2008 > 0 AND s2009.sales_2009 >= s2008.sales_2008 * 1.5 ORDER BY growth_pct DESC, s2009.customer_key
```

### Q80 t0

原执行文件：`Q80_r1_t0.exec.json`；SHA-256：`bf946c26d7a6395df41e16eb52cae00407c7906fc5d11e629466211a6df32fa5`。

```text
Planning Error: Initial planning error: Error during planning: The function Avg does not support inputs of type Interval(MonthDayNano).
QUERY: WITH customer_span AS (SELECT customer."CustomerKey" AS customer_key, geography."RegionCountryName" AS country, MIN(online_sales."DateKey") AS first_purchase_date, MAX(online_sales."DateKey") AS last_purchase_date FROM online_sales CROSS JOIN customer CROSS JOIN geography GROUP BY customer."CustomerKey", geography."RegionCountryName") SELECT country, ROUND(AVG(last_purchase_date - first_purchase_date), 2) AS avg_days FROM customer_span GROUP BY country ORDER BY country
```

### Q82 t0

原执行文件：`Q82_r1_t0.exec.json`；SHA-256：`2af3fc2933e5448fe85047f01abba25d17e55b78529a8c86c198a6948429f26c`。

```text
Rewrite Error: Can't detect Cube query and it may be not supported yet. Please check logs for additional information
QUERY: WITH direct_reports AS (SELECT "ParentEmployeeKey" AS manager_key, COUNT(*) AS direct_report_count, ROUND(AVG(CAST(DATE '2009-12-31' - "HireDate"::DATE AS DOUBLE PRECISION) / 365.25)::DECIMAL, 2) AS avg_tenure_years FROM employee WHERE "ParentEmployeeKey" IS NOT NULL GROUP BY "ParentEmployeeKey") SELECT e."FirstName" || ' ' || e."LastName" AS manager_name, d.direct_report_count, d.avg_tenure_years FROM direct_reports d JOIN employee e ON e."EmployeeKey" = d.manager_key ORDER BY manager_name
```

