## 查询语言：DAX

- 写一条 DAX 查询，以 `EVALUATE` 开头，返回一张表；可以在前面用 `DEFINE` 定义查询内的 `VAR`、`MEASURE`，在后面用 `ORDER BY` 排序。
- 列写成 `'表名'[列名]`（表名不含空格时引号可省）；度量值写成 `[度量值名]`。字符串用双引号。
- 分组汇总用 `SUMMARIZECOLUMNS(分组列1, 分组列2, 筛选表, "结果列名", 表达式)`；只要一个数时用 `ROW("结果列名", 表达式)`。
- 改变筛选上下文用 `CALCULATE(表达式, 筛选条件…)`；筛选条件可以是 `'表'[列] = 值`，也可以是 `FILTER(表, 条件)`、`ALL(…)`、`REMOVEFILTERS(…)`、`KEEPFILTERS(…)`、`TREATAS(…)`。
- 关系：两张表之间只能有一条激活的关系；要沿非激活的关系计算，在 `CALCULATE` 里加 `USERELATIONSHIP('多端表'[键], '一端表'[键])`。行上下文里沿多对一取值用 `RELATED`，反方向用 `RELATEDTABLE`。
- 聚合：`SUM`、`AVERAGE`、`MIN`、`MAX`、`COUNTROWS`、`DISTINCTCOUNT`；逐行计算后聚合用 `SUMX`、`AVERAGEX`、`MAXX`。
- 除法用 `DIVIDE(分子, 分母)`，分母为零时返回空值而不是报错。
- 变量：`VAR 名 = 表达式 RETURN 结果`。条件用 `IF`、`SWITCH(TRUE(), 条件1, 值1, …)`。
- 日期：`DATE(2020, 6, 30)`、`YEAR`、`MONTH`、`DATEDIFF(起, 止, MONTH)`；时间智能函数 `SAMEPERIODLASTYEAR`、`DATEADD`、`DATESYTD` 作用于已标记的日期表。
- 取前 N 行用 `TOPN(N, 表, 排序表达式, DESC)`；排名用 `RANKX`。
- 表上的筛选：`FILTER(表, 条件)` 逐行判断；`VALUES(列)` 取当前上下文里的不重复值；`ADDCOLUMNS(表, "新列", 表达式)` 给表加计算列。
- 四舍五入用 `ROUND(值, 位数)`；百分比要自己乘 100。
