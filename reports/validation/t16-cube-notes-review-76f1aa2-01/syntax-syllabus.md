# 写法说明大纲对照（教学深度）

- 依据：`decisions/2026-10-19-self-built-p-and-cube-notes.md` 第五节（第一期目标深度 2；ClickHouse 只到 1、第一期不改；DAX 开跑前补到 2；Cube 两份按本表补到 2 后交 T16 复核）。
- 深度：0 不教；1 规则（知识点）；2 使用条件与禁忌；3 通用样例（完整示范查询）。4、5 级本表不涉及。非标准语法的格式骨架（占位名称、不对应任何题、只示范对象结构）算 1 级（格式定义），不算 3 级（裁决第五节第 5 条）。
- 写法项取自裁决列出的清单（筛选、分组、连表、时间分桶、排名与窗口、比率、同比、前 N、空值、除法、标识符与别名引号），外加三项通用项（去重计数、在结果上再算一步、多个事实表）。**写法项不是从题目里统计出来的**：本卡不读题库。
- Cube 两份的事实依据只有 T16 的实测（分支 `T16-work`：`reports/validation/t16_cube_capabilities.md`、`t16_sql_pilot_error_audit.md`，以及四个 `t16-cube-capabilities-20261019-0x/` 目录里的探针原文与结果）。下表「证据」列是探针编号。
- 表中「改后」只针对 `cube_sql.md`、`cube_json.md`；`clickhouse_sql.md`、`dax.md` 本卡不改，只标现状。

## 对照表

| 写法项 | ClickHouse SQL | DAX | Cube SQL 改前 → 改后 | Cube JSON 改前 → 改后 | Cube 证据 |
|---|---|---|---|---|---|
| 筛选 | 1 | 1 | 2 → 2（补时间区间 `>= DATE … AND < DATE …`） | 2 → 2 | S01, S20_*, S20_like, J20_*, J21_* |
| 分组 | 1 | 1 | 2 → 2 | 2 → 2 | S01, S03, J01 |
| 连表 | 2（`LEFT JOIN` 补 0 与 `join_use_nulls`） | 2（一条激活关系、`USERELATIONSHIP`） | 2 → 2 | 2 → 2 | S50_*, F30_*, F32, F33, J03, J04, J05 |
| 时间分桶 | 1 | 1 | 2 → 2 | 2 → 2 | S100–S104, S11, F22, F23, J10_* |
| 排名与窗口 | 2（`lagInFrame` 的窗口框条件） | 1 | 2 → 2（补「内层算、外层选出也要转 `BIGINT`」、带 `PARTITION BY` 同样适用） | 1 → 2（写明不能排名、不能每组取前 N） | S35_*, S36_*, B10_*, B11, B12, T05, J32 |
| 比率 | 1 | 1 | 1 → 2（分子分母放同一 CTE 两列、外层相除） | 1 → 2（只能调用已定义指标，否则表达不了） | F01, S38, F20_pct, J30, J33 |
| 同比 / 环比 | 1（只有日期函数） | 2（时间智能函数要求已标记的日期表） | 0 → 2（两种成立形态：外层条件聚合拆两列；或两个 CTE 各筛一期、按键 `JOIN`，列名不同） | 0 → 2（同「比率」） | B27, F23, F22, F02_distinct_alias, S34_*, J30–J32 |
| 前 N | 1（`LIMIT`、`LIMIT N BY`） | 1（`TOPN`） | 1 → 2（补每组前 N：`PARTITION BY` 名次 + 外层筛选） | 1 → 2（`order` + `limit`；`limit` 不分组） | S21, F10_*, F11_*, B10_*, J01, J23 |
| 空值 | 2（`join_use_nulls`） | 1（`DIVIDE` 返回空） | 2 → 2 | 0 → 2（`set` / `notSet`；补零只能靠已定义指标） | S20_null, S38, B23, F20_coalesce*, B22, J20_set, J20_notSet |
| 除法 | 2（`/` 恒为浮点、`intDiv`、`nullIf`） | 2（`DIVIDE` 分母为零返回空） | 2 → 2 | 0 → 2（不能做算术） | S38, S40, J30 |
| 标识符与别名引号 | 1（**没写中文别名要加反引号**，见裁决第五节第 3 条） | 1 | 2 → 2（补「中文别名用双引号可以，窗口结果在输出里时例外」） | 1 → 2（成员名只能英文字母、数字、下划线；没有列别名） | S04, F24, T03–T07, J30, J31 |
| 去重计数 | 1 | 1 | 0 → 0 | 0 → 0 | 未实测（见「缺口」） |
| 在结果上再算一步 | 1（子查询与 CTE 可多层） | 1（`VAR`、`ADDCOLUMNS`） | 2 → 2 | 2 → 2（不能） | S30–S33, B24–B27, F05, F06, J30–J32 |
| 多个事实表 | 0 | 0 | 2 → 2（补「同一事实 cube 的多个指标可同层」） | 2 → 2 | F01, S53, S52_*, B01, B02, B03, J04 |
| 查询对象的格式骨架 | — | — | — | 1 → 1（保留原有的一行占位骨架 `例：{"measures": …, "limit": 10}`；格式定义，不是样例） | J01, J20_equals, J23 |

## Cube 两份改了什么

`cube_sql.md`（新增 7 处，均为条件或禁忌，没有完整示范查询）：

1. 输出别名：英文或双引号中文都可以（T03、T06），窗口结果在输出里时只用英文（T05）。
2. 同一事实 cube 的多个指标可以放在同一层（F01）。
3. 时间区间筛选写成 `>= DATE … AND < DATE …`（所有带日期的 S 探针都用这个形态）。
4. 每组前 N：`PARTITION BY` 名次在外层算、再到更外一层筛选（B10 四种组合都成立；名次只筛选不输出可不转）。
5. 比率：分子分母放同一 CTE 的两列，外层相除（F01 + S38、F20_pct）。
6. 排名转 `BIGINT` 的范围写全：内层算、外层选出或改名同样要转（B11 报错、B12 成立）；带 `PARTITION BY` 输出同样要转（S36 报错）。
7. 两个时期对比：外层条件聚合（B27 的形态，分组键用 F23 的年份成员或 F22 的外层 `EXTRACT`），或两个 CTE 各筛一期、按键 `JOIN`、列名彼此不同（F02_distinct_alias；同名会静默算错，S34_inner/left）。

`cube_json.md`（新增 6 处）：

1. 成员名只能由英文字母、数字、下划线组成，写表达式会被拒绝（J30、J31 的报错原文给出了成员名的正则）。
2. 各键的元素形状（成员名字符串、`filters` 元素的三个字段）。
3. 没有列别名，结果列以成员名命名（JSON 查询本身没有别名语法）。
4. 前 N 用 `order` + `limit`，`limit` 作用于整个结果（J01、J23；不能每组取前 N 由 J32 推出）。
5. 空值筛选用 `set` / `notSet`（J20_set、J20_notSet）。
6. 比率、同比、除法、补零、组内排名：只能调用已定义指标，否则一条查询表达不了（J30–J33）。
7. 原来那行占位骨架（`例：{"measures": …, "limit": 10}`）**保留**，与 `main` 逐字相同。本卡起初把它当 3 级样例删掉，按裁决第五节第 5 条恢复：占位名称、不对应任何题、只示范一种非标准语法的对象结构，是格式定义（1 级）。

## 由多条探针拼出、需要 T16 单独复核的条目

以下写法的每个部件都有探针成立，但**没有一条探针完整覆盖这个组合**。T16 复核新说明时请逐条补探针；不成立就删掉该条，不改成别的写法：

| 条目 | 由哪些探针拼出 | 建议补的探针 |
|---|---|---|
| 同比 / 环比·外层条件聚合 | B27（`SUM(CASE WHEN 键 … THEN v ELSE 0 END)`）+ F23（年份成员与 `MEASURE` 同层分组） | 年份成员分组的 CTE 上做两年条件聚合并相除，对独立物理聚合核对 |
| 同比 / 环比·两个 CTE 各筛一期 | F02_distinct_alias（两 CTE 按键 `JOIN`、列名不同）；两边 `WHERE` 是同一个区间 | 两边筛不同年份、按同一维度键 `JOIN`，核对两列数值 |
| 比率·同 CTE 两列相除 | F01（两指标同层）+ S38（`CAST(v AS DOUBLE PRECISION)/NULLIF(v,0)`） | 两个不同指标同层选出、外层相除，核对数值 |
| 时间区间与 `DATE_TRUNC` 外层比较 | F22 用外层 `EXTRACT`；未测 `WHERE p = DATE '…'` 形态 | 说明里没写这种形态，不需要补；列在这里提醒不要外推 |

## 缺口（本期不补，只记录）

- **Cube SQL 的 `LAG` / `LEAD`、`DENSE_RANK`、`COUNT(DISTINCT)`、`SUM(…) OVER ()`（占全体的比例）、标量子查询、两个 CTE `CROSS JOIN`**：T16 没有探针，说明里一律不写。同比、占比只写了上面能由探针拼出的形态。要补需先由 T16 加探针。
- **Cube JSON 的多个 `timeDimensions`、相对日期区间（如 `"last year"`）、默认行数上限**：没有探针，说明里不写。
- **ClickHouse 只到 1 级**：没写「中文别名要加反引号」（T13 首轮执行报错 77% 来自中文别名），按裁决第一期不改，报告写明缺口与代价。
- **DAX 多数项只到 1 级**：裁决要求开跑前补到 2 级，不在本卡范围。
- **四份说明长度不再相等**：`tests/test_render.py::test_four_syntax_notes_within_ten_percent` 在本卡开工前就已失败（`ef06279` 后 2,533 / 922 字符），补到 2 级后更长（`cube_sql.md` 3,126，`cube_json.md` 1,427，ClickHouse 953，DAX 922，按去空白字符计）。记在 `decisions/open-questions.md` 的 T12-4，用户已裁决（`decisions/2026-10-19-self-built-p-and-cube-notes.md` 第五节：栈之间篇幅可以不同）。测试改为 `test_syntax_note_lengths`：两份 Cube 说明不受等长约束，ClickHouse 与 DAX 之间仍按 10% 核对（DAX 开跑前补到 2 级时去掉），四份长度都记进测试属性。

## 重渲染与系统消息比对

```sh
uv run python render/render_all.py          # 通过，等价校验通过
```

把 `origin/main` 的四份说明和本分支的四份说明分别接到同一份渲染产物上，用 `harness/prompt.py` 的 `system_message`（探查 agent 再套 `harness/agent_prompt.py` 的 `agent_system_message`）逐单元生成系统消息比哈希（前 12 位）：

| 单元 | 说明文件 | 改前 | 改后 | 结果 |
|---|---|---|---|---|
| DAX-L0 | `dax.md` | 222556c0285d | 222556c0285d | 同 |
| DAX-L1 | `dax.md` | 413e3a178101 | 413e3a178101 | 同 |
| DAX-L2 | `dax.md` | 403b4544c438 | 403b4544c438 | 同 |
| JSON-L2 | `cube_json.md` | 0cfbedfff9d0 | 4ef222a65e1a | **变**（恢复一行骨架后重算） |
| SQL-L0 | `clickhouse_sql.md` | c7d4d21fb562 | c7d4d21fb562 | 同 |
| SQL-L0-E | `clickhouse_sql.md` | fbb4111c70d6 | fbb4111c70d6 | 同 |
| SQL-R | `clickhouse_sql.md` | b7cee8d0f32a | b7cee8d0f32a | 同 |
| SQL-L1 | `clickhouse_sql.md` | 8df43ae0552c | 8df43ae0552c | 同 |
| SQL-L1-E | `clickhouse_sql.md` | b2f84db36481 | b2f84db36481 | 同 |
| SQL-L1.5W | `clickhouse_sql.md` | 23ed4a78009c | 23ed4a78009c | 同 |
| SQL-L1.5S | `clickhouse_sql.md` | c08313c23b9b | c08313c23b9b | 同 |
| SQL-L2 | `cube_sql.md` | 400fd926ce07 | 5722ed6d03f4 | **变** |
| SQL-L2-E | `cube_sql.md` | ec9d4c047cf4 | d802db367737 | **变**（嵌入 SQL-L2 的系统消息，随之变） |
| SQL-L1c | `clickhouse_sql.md` | a61668486bf0 | a61668486bf0 | 同 |
| SQL-R-EN | `clickhouse_sql.md` | 69c11407e717 | 69c11407e717 | 同 |
| SQL-L1c-EN | `clickhouse_sql.md` | a61668486bf0 | a61668486bf0 | 同 |

渲染产物本身（`build/contexts/*.yaml`、Cube 模型、PBIP）不读 `render/syntax/`，改说明不影响它们；`git status` 里唯一的渲染副产物变化是 `reports/validation/context_sizes.md` 中两行 L2 的说明 token 数。

SQL-L1c、SQL-R-EN、SQL-L1c-EN 三行由 T12 在本地用真题库（`eval-v1.2` 只读副本，90e13b3）复跑：这三个单元的上下文从题库读取，本分支 `system_for` 生成的系统消息与 `origin/main` 的说明拼出的逐字节相同；其余各行哈希与上表一致，重渲后 `build/contexts/` 与 `context_sizes.md` 均无变化。
