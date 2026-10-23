## 查询语言：DAX

- 写一条 DAX 查询，以 `EVALUATE` 开头，返回一张表；可以在前面用 `DEFINE` 定义查询内的 `VAR`、`MEASURE`，在后面用 `ORDER BY` 排序。
- 列写成 `'表名'[列名]`（表名不含空格时引号可省）；度量值写成 `[度量值名]`。字符串用双引号。
- 分组汇总用 `SUMMARIZECOLUMNS(分组列1, 分组列2, 筛选表, "结果列名", 表达式)`；只要一个数时用 `ROW("结果列名", 表达式)`。
- 改变筛选上下文用 `CALCULATE(表达式, 筛选条件…)`；筛选条件可以是 `'表'[列] = 值`，也可以是 `FILTER(表, 条件)`、`ALL(…)`、`REMOVEFILTERS(…)`、`KEEPFILTERS(…)`、`TREATAS(…)`。
- 关系：两张表之间只能有一条激活的关系；要沿非激活的关系计算，在 `CALCULATE` 里加 `USERELATIONSHIP('多端表'[键], '一端表'[键])`。行上下文里沿多对一取值用 `RELATED`，反方向用 `RELATEDTABLE`。语义上下文里关系标了 `model_relationship: inactive` 的，在模型里是非激活关系；标了 `model_relationship: none` 的（同一张表的自连接）在模型里不是关系；没有标的是激活关系。
- 聚合：`SUM`、`AVERAGE`、`MIN`、`MAX`、`COUNTROWS`、`DISTINCTCOUNT`；逐行计算后聚合用 `SUMX`、`AVERAGEX`、`MAXX`。
- 除法用 `DIVIDE(分子, 分母)`，分母为零时返回空值而不是报错。
- 变量：`VAR 名 = 表达式 RETURN 结果`。条件用 `IF`、`SWITCH(TRUE(), 条件1, 值1, …)`。
- 日期：`DATE(2020, 6, 30)`、`YEAR`、`MONTH`、`DATEDIFF(起, 止, MONTH)`；时间智能函数 `SAMEPERIODLASTYEAR`、`DATEADD`、`DATESYTD` 作用于已标记的日期表。
- 取前 N 行用 `TOPN(N, 表, 排序表达式, DESC)`；排名用 `RANKX`。
- 表上的筛选：`FILTER(表, 条件)` 逐行判断；`VALUES(列)` 取当前上下文里的不重复值；`ADDCOLUMNS(表, "新列", 表达式)` 给表加计算列。
- 四舍五入用 `ROUND(值, 位数)`；百分比要自己乘 100。

**使用条件与禁忌**

- `EVALUATE` 后面必须是表。单个数值不能直接写在 `EVALUATE` 后，要包成 `ROW("结果列名", 值)`。
- `DEFINE` 里定义度量值要写明挂在哪张表上：`MEASURE '表'[名] = 表达式`；只写 `MEASURE [名]` 会报错。定义查询内的变量写 `VAR 名 = 表达式`，后面的 `EVALUATE` 可以直接用这个名字。
- 结果列名写成双引号字符串，可以用中文，例如 `"合计"`。`ADDCOLUMNS` 新加的列不能和表里已有的列同名，否则报错；换一个名字。
- `ORDER BY` 只能排结果表里有的列：分组列照原样写 `'表'[列]`，新算的列写 `[结果列名]`。
- `TOPN` 遇到并列会返回多于 N 行；它也不负责结果的顺序，要排序就在 `EVALUATE` 之后另写 `ORDER BY`。
- `SUMMARIZECOLUMNS` 会去掉所有结果表达式都为空值的组合。分组列所在的表要有一条激活关系连到被汇总的事实表，筛选才传得过去；没有激活关系时每一组都得到同一个合计，不报错。这时在表达式里用 `CALCULATE(…, USERELATIONSHIP(…))`，或换用有激活关系的那张表的列。
- `SUMMARIZECOLUMNS` 放在查询的最外层（`EVALUATE` 之后，或 `DEFINE`、`VAR` 里），不要放进 `ADDCOLUMNS`、`FILTER`、`SUMX` 这类逐行函数的内部；那里改用 `SUMMARIZE` 取分组，再用 `ADDCOLUMNS` 加 `CALCULATE(…)` 算值。
- 多端表里的键在一端表找不到时（孤儿行），按一端表的列分组，这些行归入一个值为空白的组；不分组的合计里包括它们。
- `RELATED` 只能在逐行计算的地方用（`FILTER`、`ADDCOLUMNS`、`SUMX` 等的第二个参数里），沿多对一方向取值；在 `SUMMARIZECOLUMNS` 里分组直接写一端表的列，不用 `RELATED`。在模型里不是关系的自连接上 `RELATED` 用不了：按键取值用 `LOOKUPVALUE('表'[要取的列], '表'[键], 键值)`，沿父子层级用 `PATH`、`PATHITEM`。
- `CALCULATE` 里 `'表'[列] = 值` 这种简写只能比较同一张表的列和固定值；条件里用到度量值，或要比较两张表的列时，写成 `FILTER(表, 条件)`。
- 字符串的 `=` 比较不区分大小写。空值 `BLANK()` 用 `=` 和 0、空串比较时算相等；要区分空值，用 `ISBLANK(值)` 或严格相等 `==`。
- `/` 的分母为零时不报错，返回无穷大或非数值；需要空值时用 `DIVIDE`。整数除法用 `QUOTIENT`。
- 日期列与字符串不能直接比较，例如 `'表'[日期列] >= "2020-01-01"` 会报错；写成 `DATE(2020, 1, 1)`。
- 时间智能函数的参数要传日期维度表的日期列，不要传事实表的日期列；结果按当前筛选里的日期移动，所以外面要有年、季或月的筛选或分组。
- `RANKX` 的第一个参数要去掉当前分组的筛选，例如 `RANKX(ALL('表'[列]), [度量值])`；直接写 `VALUES('表'[列])` 时每一行都排第 1。并列默认跳号，要不跳号把第五个参数写成 `DENSE`。
- `DISTINCTCOUNT` 把空值也算作一个值；不想算空值用 `DISTINCTCOUNTNOBLANK`。`COUNTROWS` 数表的行，`COUNT` 只数非空值。
- `FORMAT` 返回文本；数值保持数值，不要用 `FORMAT` 改写。
