## 查询语言：Cube SQL 接口（Postgres 方言）

下面只写经实测成立的写法，并写明成立的条件；「不要这样写」里的写法，有的会报错，有的能执行但算出错误的数。

**基本形式**

- 只写一条 SELECT 查询（可以带 `WITH`），不写任何修改数据的语句。
- 查询对象是 cube：在 `FROM` 里把 cube 名当作表名，把它的成员（维度和指标）当作列。成员写成「cube名.成员名」。
- 调用指标必须写 `MEASURE(cube名.指标名)`，不要对指标再套 `SUM`、`COUNT`；指标由引擎按定义计算。其余选出的维度列都要写进 `GROUP BY`。
- 成员名里有大写字母时用双引号，例如 `cube名."OrderDate"`。同一个成员在一条查询里只写一种写法，不要加引号和不加引号混用。
- 字符串用单引号，日期字面量写 `DATE '2020-06-30'`。
- 输出列的别名可以用英文，也可以用双引号括起来的中文（例如 `AS "金额"`）；例外见下文「排名」一条：输出里有窗口函数的结果时只用英文别名。
- 补充别名条件：对 CTE 的结果再聚合并排序，或把两个聚合 CTE 互连后选出结果时，输出别名使用以英文字母开头、只含英文字母、数字、下划线的名称。这些已测组合的中文别名即使用双引号也可能被重写为空标识符；改为按中文别名排序不能解决。未排序的单 CTE 聚合和某些多层聚合可以使用中文别名，不能据此推断加排序或互连之后仍可用。

**多个 cube 一起查询**

- 写 `CROSS JOIN`，不写 `ON` 条件：连接路径由数据模型预先定义，引擎自动套用。
- 连接的写法和顺序会影响引擎能不能找到路径：
  - 一个事实 cube 加一个维度 cube：`事实 CROSS JOIN 维度`。
  - 一个事实 cube 加两个维度 cube：把事实 cube 放在两个维度中间，`维度甲 CROSS JOIN 事实 CROSS JOIN 维度乙`。
  - 一个事实 cube 加三个维度 cube：用括号向右嵌套，事实 cube 放在最里层，`维度甲 CROSS JOIN (维度乙 CROSS JOIN (事实 CROSS JOIN 维度丙))`。
- 同一个事实 cube 的多个指标可以放在同一层，例如同时选出 `MEASURE(甲.指标一)` 和 `MEASURE(甲.指标二)`。
- 两个事实 cube 的指标不能放在同一层查询里。先各写一个 CTE、分别按同一个键聚合，再在外层用普通 `JOIN … ON` 或 `FULL OUTER JOIN … ON` 把两个 CTE 按键连起来。
- 需要维度的属性（名称等）时，在含 `MEASURE()` 的那一层用 `CROSS JOIN` 把维度 cube 带进来，直接选出属性。
- 同一个 cube 不能仅靠起两个不同表别名就当作两个独立扫描进行跨行关联：已测的直接多别名写法可能不报错却返回空集。需要关联两侧结果时，先在两个 CTE 中分别按各自连接键聚合；属性在键内唯一时，可以用 MIN 或 MAX 将属性一起取出。两侧输出键和属性使用不同列名，再在外层用普通 JOIN … ON 连接，并使用英文输出别名。这个做法也适用于不调用 MEASURE 的维度 cube。
- 分子分母来自不同事实表的指标，已经在它所属的 cube 里对齐好事实来源。按时间筛选或分组时，用这个 cube 自己的日期成员写条件；数据模型里这个 cube 连着公共日历时，也可以用日历 cube 的日期成员。不要因为指标的公式里用到了另一张事实表，就再 `CROSS JOIN` 那张事实表、加它的日期条件：会找不到连接路径而报错。`CROSS JOIN` 只能走数据模型里已定义的连接，不能在事实表之间造出新路径。
- 月粒度的目标与日粒度的实绩放在一起比较时，用同一段完整月份的区间（已验证的是完整月份；月目标不会按天摊分）。

**时间**

- 按时间粒度分组用 `DATE_TRUNC('month', 时间维度)`，粒度可选 day、week、month、quarter、year，可以和 `MEASURE()` 一起分组。
- 要按年份数字分组时，二选一：
  - 在含 `MEASURE()` 的那一层用日期维度 cube 里的年份成员分组；
  - 或者先在一个 CTE 里按 `DATE_TRUNC('year', 时间维度)` 分组，到外层再 `EXTRACT(YEAR FROM …)`。

**筛选、排序**

- 按时间区间筛选写在 `WHERE` 里，例如 `时间维度 >= DATE '…' AND 时间维度 < DATE '…'`。
- 维度筛选写在 `WHERE` 里，可以用 `=`、`<>`、`IN (…)`、`BETWEEN … AND …`、`LIKE`、`IS NULL`，多个条件用 `AND`、`OR` 组合。
- 按指标筛选写在 `HAVING MEASURE(…) > 值` 里。
- 排序用 `ORDER BY`，可以按指标的别名排；取前 N 行用 `ORDER BY … LIMIT N`。
- 每组取前 N 行：在外层用 `RANK()` 或 `ROW_NUMBER()` 加 `OVER (PARTITION BY 分组列 ORDER BY 值 DESC)` 算出组内名次，再在更外一层 `WHERE 名次 <= N` 筛选（名次列要输出时按下面「排名」一条转 `BIGINT`）。

**在指标结果上再算一步**

把含 `MEASURE()` 的查询写成子查询或 CTE（`WITH 名 AS (…)`），在外层继续计算。下列写法成立：

- 算术、`CASE WHEN … THEN … ELSE … END`、`ROUND(值, 位数)`（百分比要自己乘 100）。
- 比率：把分子、分母放在同一个 CTE 的两列里（同一事实 cube 的两个指标可在同一层选出），到外层相除，除法规则见下文。
- 外层再聚合：`SUM`、`AVG`、`MIN`、`MAX`、`COUNT`，也可以按 `CASE` 表达式重新分组，或写成 `SUM(CASE WHEN … THEN 值 ELSE 0 END)`。
- 累计：`SUM(值) OVER (ORDER BY … ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`。
- 排名：`ROW_NUMBER()`、`RANK()` 作为输出列时，必须写成 `CAST(ROW_NUMBER() OVER (…) AS BIGINT)`；在内层 CTE 里算、到外层才选出（包括外层改名）也一样要转。只用来筛选（例如 `WHERE n <= 3`）、不输出时，可以不转换。带不带 `PARTITION BY` 都适用这条。输出里有窗口函数的结果时，输出列的别名只用英文字母、数字和下划线。
- 两个含 `MEASURE()` 的 CTE 按键互连：两个 CTE 的输出列名要彼此不同（不要两边都叫同一个名字），外层选出时也用不同的别名。
- 按另一个 CTE 的结果筛选时，写成 `WHERE 键 IN (SELECT 键 FROM 另一个CTE)`。
- 两个时期对比（同比、环比）：二选一，都要遵守上面「两个 CTE 互连」的列名规则。
  - 先按「时间」一节的写法得到带期间列的 CTE，在外层用 `SUM(CASE WHEN 期间 = … THEN 值 ELSE 0 END)` 把两个时期拆成两列，再相除；
  - 或者写两个 CTE、各自在 `WHERE` 里筛一个时期并按同一个键聚合，外层用 `JOIN … ON 键` 连起来。
- 除法：整数相除会截断，需要小数时先 `CAST(… AS DOUBLE PRECISION)`；防止除以零用 `NULLIF(分母, 0)`。
- 空值补零写 `COALESCE(值, 0)`，或者 `CASE WHEN 值 IS NULL THEN 0 ELSE 值 END`。
- 类型转换：`CAST(值 AS BIGINT | INTEGER | NUMERIC | DECIMAL(p, s) | DOUBLE PRECISION | TEXT)`。

**不要这样写**

- 会报错：
  - 对指标再套聚合，例如 `SUM(MEASURE(…))`。
  - cube 之间写 `JOIN … ON` 条件；或者把一个已聚合的 CTE 和原始 cube 用 `JOIN … ON` 连起来。
  - 两个事实 cube 的指标放在同一层查询里（任何连接顺序都不行）。
  - `EXTRACT(…)` 和 `MEASURE()` 在同一层一起分组。
  - 输出里有窗口函数结果时用中文别名。
  - `COALESCE(NULL, 值)`、`COALESCE(CAST(NULL AS …), 值)` 这种第一个参数是空值常量的写法。
  - `PERCENTILE_CONT(…) WITHIN GROUP (…)`：引擎没有实现。
  - 对两个时间戳之差求 `AVG`，或把它转成 `DOUBLE PRECISION`：引擎不支持这种类型。
