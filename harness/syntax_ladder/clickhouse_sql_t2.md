## 查询语言：ClickHouse SQL

- 只写一条 SELECT 查询（可以带 WITH 子句），不写 INSERT、UPDATE、DDL。
- 表名写成「库名.表名」。含中文、空格或特殊字符的标识符用反引号包起来，例如 `` `中文列名` ``。标识符区分大小写。
- 字符串用单引号。日期字面量写 `toDate('2020-06-30')`；日期函数有 `toYear`、`toMonth`、`toQuarter`、`toStartOfMonth`、`toStartOfQuarter`、`toStartOfYear`、`toMonday`、`dateDiff('month', 起, 止)`、`addMonths`、`subtractYears`。
- 聚合：`sum`、`avg`、`min`、`max`、`count()`；精确去重计数用 `uniqExact(列)` 或 `count(DISTINCT 列)`；条件聚合用 `sumIf(列, 条件)`、`countIf(条件)`。
- 条件表达式：`if(条件, 甲, 乙)`、`multiIf(条件1, 值1, 条件2, 值2, 否则)`，也支持 `CASE WHEN … THEN … ELSE … END`。
- 连接：`INNER JOIN` / `LEFT JOIN … ON 左.键 = 右.键`。注意：`LEFT JOIN` 右表没有匹配时，非 Nullable 列默认填 0 或空串而不是 NULL；要得到 NULL，在查询末尾加 `SETTINGS join_use_nulls = 1`。
- 除法 `/` 总是返回浮点数；整除用 `intDiv`。防止除以零用 `nullIf(分母, 0)`。
- 窗口函数：`row_number()`、`rank()`、`dense_rank()`、`sum(…) OVER (PARTITION BY … ORDER BY …)`；取上一行用 `lagInFrame(列) OVER (… ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)`。
- 取前 N 行用 `ORDER BY … LIMIT N`；每组前 N 行用 `LIMIT N BY 分组列`。
- 子查询和 CTE（`WITH 名 AS (SELECT …)`）可以多层嵌套，外层可以在聚合结果上继续计算。
- 四舍五入用 `round(值, 位数)`；百分比要自己乘 100。

**使用条件与禁忌**

- 中文别名必须用反引号或双引号包起来，例如 ``sum(列) AS `合计` ``；不加引号会报语法错误。引用这个别名时也照样加引号。
- 输出别名不要和表里的列同名。别名在整条 SELECT 里都可见：写了 `sum(amount) AS amount` 之后，同一层里再写 `avg(amount)`，引用的是这个聚合结果，会报「聚合函数套聚合函数」。给输出起一个新名字。
- 别名可以在同一层的 `WHERE`、`HAVING`、`ORDER BY` 和后面的表达式里直接引用。
- CTE 和子查询的外层，只能引用它们 SELECT 出来的列，而且要用输出的名字（别名）；里面没有选出的列，在外层不存在。要用就在里面选出来。
- `UNION` 必须写成 `UNION ALL`（保留重复行）或 `UNION DISTINCT`（去重）；只写 `UNION` 会报错。
- 递归 CTE（`WITH RECURSIVE`）最多递归 1000 层。递归部分必须有终止条件，例如层数上限，或排除父键等于自身键的行；否则报错。
- `toInt32OrNull`、`toInt32OrZero` 这类带 `OrNull`、`OrZero` 后缀的函数只接受字符串参数；数值之间的转换用 `toInt32`、`toFloat64` 或 `CAST`。
- `corr`、`covarPop` 这类统计函数的两个参数类型要一致，`Decimal` 和整数混用会报错，先都转成 `toFloat64`。
- 大小写转换用 `lower`、`upper`；没有 `lowerUTF8`。
- 判断空值用 `IS NULL`、`IS NOT NULL`，`= NULL` 永远不成立；补默认值用 `ifNull(值, 0)` 或 `coalesce`。
- `lagInFrame` 在第一行（没有上一行）返回该类型的默认值（数值是 0），不是 NULL；要得到 NULL，把参数写成 `toNullable(列)`。
- `JOIN` 的 `ON` 条件里不能放相关子查询：先把子查询写成 CTE，再按键连接。
- `ASOF JOIN` 的 `ON` 里至少要有一个等值条件（`键 = 键`），再加一个不等式条件。

