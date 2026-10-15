## 查询语言：Cube SQL 接口（Postgres 方言）

- 只写一条 SELECT 查询，不写任何修改数据的语句。
- 查询对象是 cube：在 `FROM` 里把 cube 名当作表名，把它的成员（维度和指标）当作列。成员写成「cube名.成员名」。
- 调用指标必须写 `MEASURE(cube名.指标名)`，不要对指标再套 `SUM`、`COUNT`；指标由引擎按定义计算。其余选出的维度列都要写进 `GROUP BY`。
- 多个 cube 一起查询时写 `FROM 甲 CROSS JOIN 乙`，不写 `ON` 条件：连接路径由数据模型预先定义，引擎自动套用。
- 标识符遵循 Postgres 规则：不加引号的名字会被转成小写；成员名里有大写字母时要用双引号，例如 `cube名."OrderDate"`。
- 字符串用单引号。日期字面量写 `DATE '2020-06-30'`；按时间粒度分组用 `DATE_TRUNC('month', 时间维度)`（粒度可选 day、week、month、quarter、year）；取年份用 `EXTRACT(YEAR FROM 时间维度)`。
- 筛选写在 `WHERE` 里，作用于维度，可以用 `=`、`<>`、`IN (…)`、`BETWEEN … AND …`、`LIKE`、`IS NULL`；多个条件用 `AND`、`OR` 组合。按指标筛选写在 `HAVING MEASURE(…) > 值` 里。
- 排序用 `ORDER BY`，可以按指标的别名排；取前 N 行用 `LIMIT N`。
- 需要在指标结果上再算一步（相除、排名、累计）时，把含 `MEASURE()` 的查询写成子查询或 CTE（`WITH 名 AS (…)`），在外层用普通 SQL 表达式、`CASE WHEN` 和窗口函数（`OVER (PARTITION BY … ORDER BY …)`）继续计算。
- 除法：整数相除会截断，需要小数时先 `CAST(… AS DOUBLE PRECISION)`；防止除以零用 `NULLIF(分母, 0)`。
- 条件表达式用 `CASE WHEN … THEN … ELSE … END`，空值处理用 `COALESCE(值, 替代值)`。
- 四舍五入用 `ROUND(值, 位数)`；百分比要自己乘 100。
