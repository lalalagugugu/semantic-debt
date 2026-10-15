## 查询语言：ClickHouse SQL

- 只写一条 SELECT 查询（可以带 WITH 子句），不写 INSERT、UPDATE、DDL。
- 表名写成「库名.表名」。含中文、空格或特殊字符的标识符用反引号包起来，例如 `` `销售额` ``。标识符区分大小写。
- 字符串用单引号。日期字面量写 `toDate('2020-06-30')`；日期函数有 `toYear`、`toMonth`、`toQuarter`、`toStartOfMonth`、`toStartOfQuarter`、`toStartOfYear`、`toMonday`、`dateDiff('month', 起, 止)`、`addMonths`、`subtractYears`。
- 聚合：`sum`、`avg`、`min`、`max`、`count()`；精确去重计数用 `uniqExact(列)` 或 `count(DISTINCT 列)`；条件聚合用 `sumIf(列, 条件)`、`countIf(条件)`。
- 条件表达式：`if(条件, 甲, 乙)`、`multiIf(条件1, 值1, 条件2, 值2, 否则)`，也支持 `CASE WHEN … THEN … ELSE … END`。
- 连接：`INNER JOIN` / `LEFT JOIN … ON 左.键 = 右.键`。注意：`LEFT JOIN` 右表没有匹配时，非 Nullable 列默认填 0 或空串而不是 NULL；要得到 NULL，在查询末尾加 `SETTINGS join_use_nulls = 1`。
- 除法 `/` 总是返回浮点数；整除用 `intDiv`。防止除以零用 `nullIf(分母, 0)`。
- 窗口函数：`row_number()`、`rank()`、`dense_rank()`、`sum(…) OVER (PARTITION BY … ORDER BY …)`；取上一行用 `lagInFrame(列) OVER (… ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)`。
- 取前 N 行用 `ORDER BY … LIMIT N`；每组前 N 行用 `LIMIT N BY 分组列`。
- 子查询和 CTE（`WITH 名 AS (SELECT …)`）可以多层嵌套，外层可以在聚合结果上继续计算。
- 四舍五入用 `round(值, 位数)`；百分比要自己乘 100。
