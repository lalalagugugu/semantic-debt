## 查询语言：Cube JSON 查询

- 输出一个 JSON 对象，发给 Cube 的 `/load` 接口。只能引用数据模型里已定义的成员，写成「cube名.成员名」。
- 键：`"measures"`（指标数组）、`"dimensions"`（分组维度数组）、`"timeDimensions"`（时间维度）、`"filters"`（筛选）、`"order"`（排序）、`"limit"`（行数上限）。
- 例：`{"measures": ["甲.指标"], "dimensions": ["乙.维度"], "filters": [{"member": "乙.维度", "operator": "equals", "values": ["某值"]}], "order": {"甲.指标": "desc"}, "limit": 10}`。
- 结果按 `dimensions` 和时间粒度分组，每组返回一行，指标由引擎按定义计算。多个 cube 的成员可以放在同一个查询里，连接路径由数据模型预先定义，不需要也不能写连接条件。
- 时间维度：`{"dimension": "甲.时间", "granularity": "month", "dateRange": ["2020-01-01", "2020-06-30"]}`；粒度可选 day、week、month、quarter、year；不写粒度就只按区间筛选、不分组。
- 筛选运算符：`equals`、`notEquals`、`contains`、`notContains`、`gt`、`gte`、`lt`、`lte`、`set`、`notSet`、`inDateRange`、`beforeDate`、`afterDate`。`values` 一律写成字符串数组。多个条件默认同时成立；需要「或」时写 `{"or": [条件1, 条件2]}`，「且」写 `{"and": […]}`。
- 按指标筛选（相当于分组后的 HAVING）也写在 `filters` 里，`member` 填指标名。
- 排序 `order` 可以是对象 `{"成员": "asc"}`，也可以是数组 `[["成员", "desc"], …]`，按顺序生效。
- 不能写任意表达式：不能在指标结果上再做加减乘除、排名、累计，也不能对维度临时做计算。这些计算只能由模型里已定义的指标完成。
