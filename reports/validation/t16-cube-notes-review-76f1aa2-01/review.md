# Cube 深度2写法说明逐句复核

复核提交：`76f1aa2477b31c87953b7c4090696f50d58bdf1a`（T12-cube-notes，包含已补回的格式骨架）。**该提交尚未复核通过，不应据此合并或打 semantic-v1.3。**

部署版本：Cube 1.8.6，ClickHouse 25.8.20.4。本轮0模型调用。229个通用探针：180个原探针复跑、49个补充探针；不读题库、不取用任何作答。全文原始错误在results.jsonl，不脱敏、不截断。
逐句88项：{'条件不符': 4, '成立': 78, '不成立': 6}。成立均限于注明模型/类型条件；条件不符用于整体声明尚有未满足前提，不把元声明当单条SQL探针。

## 三个重点组合的直接验证

以下每个探针都直接执行完整组合，不再由单独探针拼接推断。独立基线为原始FactSales的年/月/数量与金额聚合，核对键集合、两列值、比值和增长率；tol=1e-8相对/1e-6绝对仅用于接口核验，不改评分器。
| 探针 | 数值核对 | 依据 |
|---|---|---|
| `R_period_case_year_calendar` | 通过 | independent physical year aggregates; both values, ratio and growth |
| `R_period_case_year_outer_extract` | 通过 | independent physical year aggregates; both values, ratio and growth |
| `R_period_join_year_JOIN` | 通过 | independent physical year aggregates; both values, ratio and growth |
| `R_period_join_year_FULL_OUTER_JOIN` | 通过 | independent physical year aggregates; both values, ratio and growth |
| `R_period_case_month_month_bucket` | 通过 | independent physical month aggregates; both values, ratio and growth |
| `R_period_join_month_JOIN` | 通过 | independent physical month aggregates; both values, ratio and growth |
| `R_period_join_month_FULL_OUTER_JOIN` | 通过 | independent physical month aggregates; both values, ratio and growth |
| `R_ratio_True` | 通过 | two distinct physical aggregates, grouped division |
| `R_ratio_False` | 通过 | global ratio of separate totals, not average of per-group ratios |

## 不成立项与删除方案

1. SQL连接部分“平铺的写法都找不到路径”：三个维度形成链时可平铺，星形图失败不能泛化。
2. SQL同名CTE必然错值：外层明确不同别名后，内层同名仍可得到两列正确值。
3. SQL聚合CTE与派生CTE互连再SUM必然全组误汇总：派生键改名的同类查询数值正确。
4. SQL禁忌中“三维平铺任意顺序都不行、二维相邻且事实在一端不行”：链式图都有直接正例。
5. SQL禁忌中所有窗口输出都要BIGINT：累计SUM的Float64窗口输出无需BIGINT，数值正确；ROW_NUMBER/RANK的已述规则仍成立。
6. JSON“其他键都会拒绝”：offset/timezone被接受。只删除这个概括，不新增或教授额外键。

deletions-only.patch只删除上述内容；同名CTE/派生CTE小组删除后不保留空标题或悬空指代，没有改写成更窄规则。补丁为零上下文格式，先用 git apply --unidiff-zero --check，再用 git apply --unidiff-zero 应用；仅适用所录提交，最新内容有变化须重新核对。两份 *.deletions-only.md 是删除后的候选全文，不是已修改远端分支的证明。应用位置应为PR #130的T12-cube-notes，待并发修改协调。
格式骨架保留原文：文字甲乙占位不是可执行成员；逐字JSON解析成立，替换占位名和值后按同一结构执行及数值核验通过。

## 逐句结论

| 文件:行/句 | 判定 | 原文 | 证据与条件 |
|---|---|---|
| cube_sql.md:3/1 | **条件不符** | 下面只写经实测成立的写法，并写明成立的条件；「不要这样写」里的写法，有的会报错，有的能执行但算出错误的数。 | `S01,S34_inner,R_chain_flat`；整体范围声明尚未满足：下列条目存在反例，不能整体签收。 |
| cube_sql.md:7/1 | **成立** | - 只写一条 SELECT 查询（可以带 `WITH`），不写任何修改数据的语句。 | `S01,S30`；只读约束；没有执行任何修改数据的语句。 |
| cube_sql.md:8/1 | **成立** | - 查询对象是 cube：在 `FROM` 里把 cube 名当作表名，把它的成员（维度和指标）当作列。 | `S01,S02`；当前模型中已有 cube/成员；未把任意物理表当 cube。 |
| cube_sql.md:8/2 | **成立** | 成员写成「cube名.成员名」。 | `S01,S02`；当前模型中已有 cube/成员；未把任意物理表当 cube。 |
| cube_sql.md:9/1 | **成立** | - 调用指标必须写 `MEASURE(cube名.指标名)`，不要对指标再套 `SUM`、`COUNT`；指标由引擎按定义计算。 | `S01,S03,R_count_measure,R_missing_group`；MEASURE 直接聚合正确；SUM/COUNT 嵌套及遗漏GROUP BY反例均报错。 |
| cube_sql.md:9/2 | **成立** | 其余选出的维度列都要写进 `GROUP BY`。 | `S01,S03,R_count_measure,R_missing_group`；MEASURE 直接聚合正确；SUM/COUNT 嵌套及遗漏GROUP BY反例均报错。 |
| cube_sql.md:10/1 | **成立** | - 成员名里有大写字母时用双引号，例如 `cube名."OrderDate"`。 | `S01,F24`；只选一种标识符写法是安全规范；混写反例报错，不宣称所有无引号写法都不能执行。 |
| cube_sql.md:10/2 | **成立** | 同一个成员在一条查询里只写一种写法，不要加引号和不加引号混用。 | `S01,F24`；只选一种标识符写法是安全规范；混写反例报错，不宣称所有无引号写法都不能执行。 |
| cube_sql.md:11/1 | **成立** | - 字符串用单引号，日期字面量写 `DATE '2020-06-30'`。 | `S01,S40`；字符串/DATE 字面量成立。 |
| cube_sql.md:12/1 | **成立** | - 输出列的别名可以用英文，也可以用双引号括起来的中文（例如 `AS "金额"`）；例外见下文「排名」一条：输出里有窗口函数的结果时只用英文别名。 | `T03,T04,T05,R_cumulative_unicode`；普通英文/中文投影成立；窗口输出中文别名的例外实际报错。 |
| cube_sql.md:16/1 | **成立** | - 写 `CROSS JOIN`，不写 `ON` 条件：连接路径由数据模型预先定义，引擎自动套用。 | `F33,F34,R_chain_flat`；有预定义连接路径；原始cube普通ON被拒。 |
| cube_sql.md:17/1 | **成立** | - 连接的写法和顺序会影响引擎能不能找到路径： | `S50_sales_store_channel,F32`；连接树和顺序确实影响路径。 |
| cube_sql.md:18/1 | **成立** |   - 一个事实 cube 加一个维度 cube：`事实 CROSS JOIN 维度`。 | `S20_like,R_one_dim_indirect`；已有路径；中间节点可以由引擎自动补齐。 |
| cube_sql.md:19/1 | **成立** |   - 一个事实 cube 加两个维度 cube：把事实 cube 放在两个维度中间，`维度甲 CROSS JOIN 事实 CROSS JOIN 维度乙`。 | `S50_store_sales_channel,S50_channel_sales_store,R_two_dims_middle`；这是已证实可用的充分写法，不是必要条件；链式图的事实放一端也有成功例。 |
| cube_sql.md:20/1 | **成立** |   - 一个事实 cube 加三个维度 cube：用括号向右嵌套，事实 cube 放在最里层，`维度甲 CROSS JOIN (维度乙 CROSS JOIN (事实 CROSS JOIN 维度丙))`。 | `R_star_right_store_channel_calendar,R_chain_right,R_chain_flat`；右嵌套正例成立；同一行关于平铺的断言另列为不成立。 |
| cube_sql.md:20/2 | **不成立** | 平铺的写法都找不到路径。 | `R_star_right_store_channel_calendar,R_chain_right,R_chain_flat`；链式三维图R_chain_flat平铺成功且数值正确；断言平铺都失败超出星形探针条件。 |
| cube_sql.md:21/1 | **成立** | - 同一个事实 cube 的多个指标可以放在同一层，例如同时选出 `MEASURE(甲.指标一)` 和 `MEASURE(甲.指标二)`。 | `F01,R_ratio_True`；同一事实的两个不同指标同层，数值核验。 |
| cube_sql.md:22/1 | **成立** | - 两个事实 cube 的指标不能放在同一层查询里。 | `S52_sales_calendar_online_sales,S53,B01,B02`；部署中两销售事实的直接同层查询失败；分开聚合后按共有键JOIN/FULL JOIN值正确。仅作已验图形的说明，不是所有自定义模型的不可能性定理。 |
| cube_sql.md:22/2 | **成立** | 先各写一个 CTE、分别按同一个键聚合，再在外层用普通 `JOIN … ON` 或 `FULL OUTER JOIN … ON` 把两个 CTE 按键连起来。 | `S52_sales_calendar_online_sales,S53,B01,B02`；部署中两销售事实的直接同层查询失败；分开聚合后按共有键JOIN/FULL JOIN值正确。仅作已验图形的说明，不是所有自定义模型的不可能性定理。 |
| cube_sql.md:23/1 | **成立** | - 需要维度的属性（名称等）时，在含 `MEASURE()` 的那一层用 `CROSS JOIN` 把维度 cube 带进来，直接选出属性。 | `J03,S50_store_sales_channel,R_chain_flat`；维度属性在MEASURE层带入，符合已验证的连接条件。 |
| cube_sql.md:27/1 | **成立** | - 按时间粒度分组用 `DATE_TRUNC('month', 时间维度)`，粒度可选 day、week、month、quarter、year，可以和 `MEASURE()` 一起分组。 | `S100,S101,S102,S103,S104`；五种时间分桶已复跑。 |
| cube_sql.md:28/1 | **成立** | - 要按年份数字分组时，二选一： | `F22,F23,R_period_case_year_calendar,R_period_case_year_outer_extract`；两种年份来源直接用到完整比较中核验。 |
| cube_sql.md:29/1 | **成立** |   - 在含 `MEASURE()` 的那一层用日期维度 cube 里的年份成员分组； | `F23,R_period_case_year_calendar`；年份维度与MEASURE同层成立。 |
| cube_sql.md:30/1 | **成立** |   - 或者先在一个 CTE 里按 `DATE_TRUNC('year', 时间维度)` 分组，到外层再 `EXTRACT(YEAR FROM …)`。 | `F22,R_period_case_year_outer_extract`；先按年桶聚合再外层EXTRACT，并完成两年比较，数值一致。 |
| cube_sql.md:34/1 | **成立** | - 按时间区间筛选写在 `WHERE` 里，例如 `时间维度 >= DATE '…' AND 时间维度 < DATE '…'`。 | `S01,R_period_join_month_JOIN`；>=起点、<下一起点的过滤值独立核验。 |
| cube_sql.md:35/1 | **成立** | - 维度筛选写在 `WHERE` 里，可以用 `=`、`<>`、`IN (…)`、`BETWEEN … AND …`、`LIKE`、`IS NULL`，多个条件用 `AND`、`OR` 组合。 | `S20_eq,S20_ne,S20_in,S20_between,S20_like,S20_null,S20_and_or`；列举的谓词与布尔组合复跑。 |
| cube_sql.md:36/1 | **成立** | - 按指标筛选写在 `HAVING MEASURE(…) > 值` 里。 | `S21`；HAVING MEASURE正例。 |
| cube_sql.md:37/1 | **成立** | - 排序用 `ORDER BY`，可以按指标的别名排；取前 N 行用 `ORDER BY … LIMIT N`。 | `S21`；别名排序、LIMIT与独立行序一致。 |
| cube_sql.md:38/1 | **成立** | - 每组取前 N 行：在外层用 `RANK()` 或 `ROW_NUMBER()` 加 `OVER (PARTITION BY 分组列 ORDER BY 值 DESC)` 算出组内名次，再在更外一层 `WHERE 名次 <= N` 筛选（名次列要输出时按下面「排名」一条转 `BIGINT`）。 | `R_per_group_ROW_NUMBER_True,R_per_group_ROW_NUMBER_False,R_per_group_RANK_True,R_per_group_RANK_False`；真实多行分组，外层名次筛选；含仅筛选/返回BIGINT两个变体，独立逐组排序核验。 |
| cube_sql.md:42/1 | **成立** | 把含 `MEASURE()` 的查询写成子查询或 CTE（`WITH 名 AS (…)`），在外层继续计算。 | `S30,S31,S32_cte,S32_subquery`；适用后续所列有限形态；不宣称任意普通SQL均可。 |
| cube_sql.md:42/2 | **成立** | 下列写法成立： | `S30,S31,S32_cte,S32_subquery`；适用后续所列有限形态；不宣称任意普通SQL均可。 |
| cube_sql.md:44/1 | **成立** | - 算术、`CASE WHEN … THEN … ELSE … END`、`ROUND(值, 位数)`（百分比要自己乘 100）。 | `S38,F20_round,F20_pct`；算术、CASE、ROUND百分比正例。 |
| cube_sql.md:45/1 | **成立** | - 比率：把分子、分母放在同一个 CTE 的两列里（同一事实 cube 的两个指标可在同一层选出），到外层相除，除法规则见下文。 | `R_ratio_True,R_ratio_False`；补齐直接组合：两个不同指标在一个CTE，再相除；分组及全局均核验。 |
| cube_sql.md:46/1 | **成立** | - 外层再聚合：`SUM`、`AVG`、`MIN`、`MAX`、`COUNT`，也可以按 `CASE` 表达式重新分组，或写成 `SUM(CASE WHEN … THEN 值 ELSE 0 END)`。 | `S32_cte,S33_cte,B24,B27,R_period_case_year_calendar`；SUM/AVG/MIN/MAX/COUNT、CASE重分组、条件聚合均有正例。 |
| cube_sql.md:47/1 | **成立** | - 累计：`SUM(值) OVER (ORDER BY … ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`。 | `S37`；累计窗口有数值正确的正例；无需转BIGINT。 |
| cube_sql.md:48/1 | **成立** | - 排名：`ROW_NUMBER()`、`RANK()` 作为输出列时，必须写成 `CAST(ROW_NUMBER() OVER (…) AS BIGINT)`；在内层 CTE 里算、到外层才选出（包括外层改名）也一样要转。 | `S35_ROW_NUMBER_native,S35_ROW_NUMBER_bigint,S35_RANK_native,S35_RANK_bigint,B11,B12,R_per_group_ROW_NUMBER_True,R_per_group_RANK_True,R_cumulative_unicode`；排名需BIGINT输出，纯筛选可不转；有无PARTITION与外层改名均直接核验，英文别名条件成立。 |
| cube_sql.md:48/2 | **成立** | 只用来筛选（例如 `WHERE n <= 3`）、不输出时，可以不转换。 | `S35_ROW_NUMBER_native,S35_ROW_NUMBER_bigint,S35_RANK_native,S35_RANK_bigint,B11,B12,R_per_group_ROW_NUMBER_True,R_per_group_RANK_True,R_cumulative_unicode`；排名需BIGINT输出，纯筛选可不转；有无PARTITION与外层改名均直接核验，英文别名条件成立。 |
| cube_sql.md:48/3 | **成立** | 带不带 `PARTITION BY` 都适用这条。 | `S35_ROW_NUMBER_native,S35_ROW_NUMBER_bigint,S35_RANK_native,S35_RANK_bigint,B11,B12,R_per_group_ROW_NUMBER_True,R_per_group_RANK_True,R_cumulative_unicode`；排名需BIGINT输出，纯筛选可不转；有无PARTITION与外层改名均直接核验，英文别名条件成立。 |
| cube_sql.md:48/4 | **成立** | 输出里有窗口函数的结果时，输出列的别名只用英文字母、数字和下划线。 | `S35_ROW_NUMBER_native,S35_ROW_NUMBER_bigint,S35_RANK_native,S35_RANK_bigint,B11,B12,R_per_group_ROW_NUMBER_True,R_per_group_RANK_True,R_cumulative_unicode`；排名需BIGINT输出，纯筛选可不转；有无PARTITION与外层改名均直接核验，英文别名条件成立。 |
| cube_sql.md:49/1 | **成立** | - 两个含 `MEASURE()` 的 CTE 按键互连：两个 CTE 的输出列名要彼此不同（不要两边都叫同一个名字），外层选出时也用不同的别名。 | `F02_distinct_alias,R_period_join_year_JOIN`；两边及外层列名不同是足够安全的规范；不是必要条件，不能据此说所有同名都一定错。 |
| cube_sql.md:50/1 | **成立** | - 按另一个 CTE 的结果筛选时，写成 `WHERE 键 IN (SELECT 键 FROM 另一个CTE)`。 | `F06`；IN半连接保留组内汇总值。 |
| cube_sql.md:51/1 | **成立** | - 两个时期对比（同比、环比）：二选一，都要遵守上面「两个 CTE 互连」的列名规则。 | `R_period_case_year_calendar,R_period_case_month_month_bucket,R_period_join_year_JOIN,R_period_join_month_JOIN`；二种组合均完成年、月真实时期比较，遵守独立列名。 |
| cube_sql.md:52/1 | **成立** |   - 先按「时间」一节的写法得到带期间列的 CTE，在外层用 `SUM(CASE WHEN 期间 = … THEN 值 ELSE 0 END)` 把两个时期拆成两列，再相除； | `R_period_case_year_calendar,R_period_case_year_outer_extract,R_period_case_month_month_bucket`；直接完整条件聚合拆列、再相除，两个值及比值/增长率均对独立事实表。 |
| cube_sql.md:53/1 | **成立** |   - 或者写两个 CTE、各自在 `WHERE` 里筛一个时期并按同一个键聚合，外层用 `JOIN … ON 键` 连起来。 | `R_period_join_year_JOIN,R_period_join_month_JOIN,R_period_join_year_FULL_OUTER_JOIN`；两个CTE各取不同期间，按相同含义但不同列名键连接；两列、比值及增长率正确。 |
| cube_sql.md:54/1 | **成立** | - 除法：整数相除会截断，需要小数时先 `CAST(… AS DOUBLE PRECISION)`；防止除以零用 `NULLIF(分母, 0)`。 | `S40,R_ratio_True`；整数截断、DOUBLE、NULLIF零保护与组合除法成立。 |
| cube_sql.md:55/1 | **成立** | - 空值补零写 `COALESCE(值, 0)`，或者 `CASE WHEN 值 IS NULL THEN 0 ELSE 值 END`。 | `R_coalesce_actual_null,R_case_actual_null`；不是只测非NULL输入，实际NULL分支填0正确。 |
| cube_sql.md:56/1 | **成立** | - 类型转换：`CAST(值 AS BIGINT &#124; INTEGER &#124; NUMERIC &#124; DECIMAL(p, s) &#124; DOUBLE PRECISION &#124; TEXT)`。 | `S42_bigint,S42_integer,S42_numeric,S42_decimal,S42_double,S42_text`；所列转换类型的标量形态均可用；不覆盖已明示禁忌的interval转换。 |
| cube_sql.md:60/1 | **条件不符** | - 能执行但算出错误的数（不报错，要特别避开）： | `S34_inner,F05`；该分组的两条禁忌都省略必要条件，有正反例，不可当作无条件断言。 |
| cube_sql.md:61/1 | **不成立** |   - 两个含 `MEASURE()` 的 CTE 用同一个输出列名（例如都叫 `v`），外层再用 `JOIN … ON` 或 `LEFT JOIN … ON` 连起来同时选出这两列：第二列会变成第一列的值。 | `S34_inner,S34_left,R_same_cte_alias_JOIN,R_same_cte_alias_LEFT_JOIN`；内层同名但外层给不同别名时两列都正确；原句没有这个条件，断言第二列必变成第一列不成立。 |
| cube_sql.md:62/1 | **不成立** |   - 一个聚合 CTE，和由它派生出来的 CTE（例如从它取出的键集合）`JOIN` 之后再 `SUM` / `GROUP BY`：每组得到的是全部的合计，不是本组的值。 | `F05,F06,R_derived_key_renamed`；派生键不改名时确有错值，但只把派生键改名后JOIN再SUM可正确；原文无条件归纳不成立。 |
| cube_sql.md:62/2 | **成立** | 要这样筛选时改用上面的 `IN (SELECT …)`。 | `F05,F06,R_derived_key_renamed`；IN写法成立，但为避免删除前句后留下无所指代的句子，删项补丁删除整条，不改写。 |
| cube_sql.md:63/1 | **条件不符** | - 会报错： | `S03,R_chain_flat,S37`；分组中的部分“会报错”断言过宽，须逐条看下列结论。 |
| cube_sql.md:64/1 | **成立** |   - 对指标再套聚合，例如 `SUM(MEASURE(…))`。 | `S03,R_count_measure`；SUM和COUNT包MEASURE均实际报错。 |
| cube_sql.md:65/1 | **成立** |   - cube 之间写 `JOIN … ON` 条件；或者把一个已聚合的 CTE 和原始 cube 用 `JOIN … ON` 连起来。 | `F33,F34`；原始cube的普通ON与聚合CTE接原始cube都报错。 |
| cube_sql.md:66/1 | **不成立** |   - 三个维度 cube 平铺 `CROSS JOIN`（任何顺序都不行）；两个维度 cube 时把它们写在相邻位置、事实 cube 放在一端。 | `R_chain_flat,R_two_dims_end,F30_sales_store_channel_calendar`；三维链式图平铺可成功；两维链式图事实放一端也可成功。星形图失败不可外推全部图形。 |
| cube_sql.md:67/1 | **成立** |   - 两个事实 cube 的指标放在同一层查询里（任何连接顺序都不行）。 | `S52_sales_online_sales_calendar,S52_sales_calendar_online_sales,S52_online_sales_sales_calendar,S52_online_sales_calendar_sales,S52_calendar_sales_online_sales,S52_calendar_online_sales_sales,S53,B03`；当前两销售事实直接同层的所有已列顺序/嵌套均失败；不外推未部署模型。 |
| cube_sql.md:68/1 | **成立** |   - `EXTRACT(…)` 和 `MEASURE()` 在同一层一起分组。 | `S11,F22`；同层EXTRACT+MEASURE失败，外层EXTRACT正例成立。 |
| cube_sql.md:69/1 | **不成立** |   - 窗口函数的结果不转 `BIGINT` 就作为输出列；输出里有窗口函数结果时用中文别名。 | `S37,S35_ROW_NUMBER_native,S35_RANK_native,T05,R_cumulative_unicode`；前半句泛称窗口函数需BIGINT，SUM累计窗口无需转且正确；后半句中文窗口别名禁忌成立，分开记录。 |
| cube_sql.md:70/1 | **成立** |   - `COALESCE(NULL, 值)`、`COALESCE(CAST(NULL AS …), 值)` 这种第一个参数是空值常量的写法。 | `F20_coalesce,F20_coalesce_cast,B22`；NULL常量第一参数反例持续报错。 |
| cube_sql.md:71/1 | **成立** |   - `PERCENTILE_CONT(…) WITHIN GROUP (…)`：引擎没有实现。 | `S61,F41`；Float64纯SQL控制仍明确execution未实现。 |
| cube_sql.md:72/1 | **成立** |   - 对两个时间戳之差求 `AVG`，或把它转成 `DOUBLE PRECISION`：引擎不支持这种类型。 | `T01,T02`；时间戳之差AVG与CAST到Float64均直接失败。 |
| cube_json.md:3/1 | **条件不符** | 下面的写法都经过实测。 | `J01,R_json_extra_offset`；全局实测承诺未满足，存在额外键断言反例。 |
| cube_json.md:5/1 | **成立** | - 输出一个 JSON 对象，发给 Cube 的 `/load` 接口。 | `J01,J02,J30,J31,R_json_skeleton_literal`；这是成员各部分的命名及模型存在性规则，点号是cube/member分隔符；占位骨架须替换名字。 |
| cube_json.md:5/2 | **成立** | 只能引用数据模型里已定义的成员，写成「cube名.成员名」，照数据模型里的写法原样抄写；不存在的成员会报错。 | `J01,J02,J30,J31,R_json_skeleton_literal`；这是成员各部分的命名及模型存在性规则，点号是cube/member分隔符；占位骨架须替换名字。 |
| cube_json.md:5/3 | **成立** | 成员名只能由英文字母、数字和下划线组成，不能写表达式、函数或空格（会被拒绝）。 | `J01,J02,J30,J31,R_json_skeleton_literal`；这是成员各部分的命名及模型存在性规则，点号是cube/member分隔符；占位骨架须替换名字。 |
| cube_json.md:6/1 | **成立** | - 键：`"measures"`（指标数组）、`"dimensions"`（分组维度数组）、`"timeDimensions"`（时间维度数组）、`"filters"`（筛选数组）、`"order"`（排序）、`"limit"`（行数上限，整数）。 | `J01,R_json_limit_float,R_json_limit_string,R_json_extra_offset,R_json_extra_timezone,R_json_extra_join,R_json_extra_expression`；列举键及limit整数规则成立；关于所有其他键的第二句单列为不成立。 |
| cube_json.md:6/2 | **不成立** | 其他键（例如 `"join"`、`"expression"`）会被拒绝。 | `J01,R_json_limit_float,R_json_limit_string,R_json_extra_offset,R_json_extra_timezone,R_json_extra_join,R_json_extra_expression`；offset和timezone都是未列出的键，但实际被接受；join/expression被拒不等于所有其他键都被拒。 |
| cube_json.md:7/1 | **成立** | - 例：`{"measures": ["甲.指标"], "dimensions": ["乙.维度"], "filters": [{"member": "乙.维度", "operator": "equals", "values": ["某值"]}], "order": {"甲.指标": "desc"}, "limit": 10}`。 | `R_json_skeleton,R_json_skeleton_literal`；原文骨架可JSON解析，替换占位名称及占位值后原结构原样通过且值正确；文字占位本身不是模型成员，预期报错不否定格式定义。 |
| cube_json.md:8/1 | **成立** | - `"measures"`、`"dimensions"` 的元素是成员名字符串；`"filters"` 的每个元素写成 `{"member": 成员名, "operator": 运算符, "values": [字符串, …]}`。 | `J01,J21_or,J21_and,R_json_alias_member`；普通过滤元素结构成立；or/and容器由后文单列，不能把本句泛化成禁止那些容器。 |
| cube_json.md:9/1 | **成立** | - 没有列别名：结果的每一列就以成员名命名，不能改名。 | `R_json_extra_aliases,R_json_alias_member,R_json_skeleton`；额外aliases键/成员别名对象被拒；返回以注解成员名命名。 |
| cube_json.md:10/1 | **成立** | - 结果按 `dimensions` 和时间粒度分组，每组返回一行，指标由引擎按定义计算。 | `J01,J10_day,J10_month`；维度及时间桶分组正例。 |
| cube_json.md:11/1 | **成立** | - 多个 cube 的成员可以放在同一个查询里，前提是数据模型里有连接路径：一个事实 cube 的指标配多个维度 cube 的维度可以；两个事实 cube 的指标也可以放在一起，按它们共同连接的维度分组。 | `J03,J04,J05`；以模型已有连接路径为前提，双事实共享维度及多维正例成立；任意join键被拒。 |
| cube_json.md:11/2 | **成立** | 连接条件不需要也不能写。 | `J03,J04,J05`；以模型已有连接路径为前提，双事实共享维度及多维正例成立；任意join键被拒。 |
| cube_json.md:12/1 | **成立** | - 时间维度：`{"dimension": "甲.时间", "granularity": "month", "dateRange": ["2020-01-01", "2020-06-30"]}`；粒度可选 day、week、month、quarter、year；不写粒度就只按区间筛选、不分组。 | `J10_day,J10_week,J10_month,J10_quarter,J10_year,J10_None`；复跑五粒度与无粒度；部分桶用旧独立日级基线核验，结果起点可越出筛选区间但值只来自区间。 |
| cube_json.md:12/2 | **成立** | 区间两端落在半个周、季、年里时，那一组仍按所在周、季、年的起点标注，但只计入 `dateRange` 以内的数据。 | `J10_day,J10_week,J10_month,J10_quarter,J10_year,J10_None`；复跑五粒度与无粒度；部分桶用旧独立日级基线核验，结果起点可越出筛选区间但值只来自区间。 |
| cube_json.md:13/1 | **成立** | - 筛选运算符：`equals`、`notEquals`、`contains`、`notContains`、`gt`、`gte`、`lt`、`lte`、`set`、`notSet`、`inDateRange`、`beforeDate`、`afterDate`。 | `J20_equals,J20_notEquals,J20_contains,J20_notContains,J20_gt,J20_gte,J20_lt,J20_lte,J20_set,J20_notSet,J20_inDateRange,J20_beforeDate,J20_afterDate,R_json_compiled_beforeDate,R_json_compiled_afterDate,R_json_compiled_inDateRange`；13种运算；大小写例、字符串/空数组为安全客户端规范。编译SQL日期参数证明包含区间两端，before/after排除整天（UTC）；服务端也允许set非空数组，不影响此安全规范。 |
| cube_json.md:13/2 | **成立** | `values` 一律写成字符串数组（`set`、`notSet` 写空数组）。 | `J20_equals,J20_notEquals,J20_contains,J20_notContains,J20_gt,J20_gte,J20_lt,J20_lte,J20_set,J20_notSet,J20_inDateRange,J20_beforeDate,J20_afterDate,R_json_compiled_beforeDate,R_json_compiled_afterDate,R_json_compiled_inDateRange`；13种运算；大小写例、字符串/空数组为安全客户端规范。编译SQL日期参数证明包含区间两端，before/after排除整天（UTC）；服务端也允许set非空数组，不影响此安全规范。 |
| cube_json.md:13/3 | **成立** | `contains`、`notContains` 不区分大小写。 | `J20_equals,J20_notEquals,J20_contains,J20_notContains,J20_gt,J20_gte,J20_lt,J20_lte,J20_set,J20_notSet,J20_inDateRange,J20_beforeDate,J20_afterDate,R_json_compiled_beforeDate,R_json_compiled_afterDate,R_json_compiled_inDateRange`；13种运算；大小写例、字符串/空数组为安全客户端规范。编译SQL日期参数证明包含区间两端，before/after排除整天（UTC）；服务端也允许set非空数组，不影响此安全规范。 |
| cube_json.md:13/4 | **成立** | `inDateRange` 两端都包含；`beforeDate`、`afterDate` 不包含所给的那一天。 | `J20_equals,J20_notEquals,J20_contains,J20_notContains,J20_gt,J20_gte,J20_lt,J20_lte,J20_set,J20_notSet,J20_inDateRange,J20_beforeDate,J20_afterDate,R_json_compiled_beforeDate,R_json_compiled_afterDate,R_json_compiled_inDateRange`；13种运算；大小写例、字符串/空数组为安全客户端规范。编译SQL日期参数证明包含区间两端，before/after排除整天（UTC）；服务端也允许set非空数组，不影响此安全规范。 |
| cube_json.md:14/1 | **成立** | - 多个条件默认同时成立；需要「或」时写 `{"or": [条件1, 条件2]}`，「且」写 `{"and": […]}`。 | `J21_or,J21_and,J21_default`；默认AND、显式AND/OR的返回与谓词一致。 |
| cube_json.md:15/1 | **成立** | - 按指标筛选（相当于分组后的 HAVING）也写在 `filters` 里，`member` 填指标名。 | `J22`；指标filters正例。 |
| cube_json.md:16/1 | **成立** | - 排序 `order` 可以是对象 `{"成员": "asc"}`，也可以是数组 `[["成员", "desc"], …]`，按顺序生效。 | `J01,J23`；对象及有序数组的行序正例。 |
| cube_json.md:17/1 | **成立** | - 取前 N 行：按指标写 `order`，再写 `"limit": N`。 | `R_json_limit_group,R_json_limit_per_group`；实际多分组数据只返回全局2行；limitPerGroup被拒，不能用普通limit表达逐组N。 |
| cube_json.md:17/2 | **成立** | `limit` 作用于整个结果，不能「每组各取前 N」。 | `R_json_limit_group,R_json_limit_per_group`；实际多分组数据只返回全局2行；limitPerGroup被拒，不能用普通limit表达逐组N。 |
| cube_json.md:18/1 | **成立** | - 空值：要筛出某个维度有值或为空的行，用 `set`、`notSet`。 | `J20_set,J20_notSet`；有值/无值筛选正例；当前字段非NULL，notSet为空符合基线。 |
| cube_json.md:19/1 | **成立** | - 不能写任意表达式：不能在指标结果上再做加减乘除、排名、累计，也不能对维度临时做计算（这样写会被拒绝）。 | `J30,J31,J32,J33`；临时指标、维度、expression键拒绝，预定义计算指标接受。 |
| cube_json.md:19/2 | **成立** | 这些计算只能由模型里已定义的指标完成。 | `J30,J31,J32,J33`；临时指标、维度、expression键拒绝，预定义计算指标接受。 |
| cube_json.md:20/1 | **成立** | - 因此比率、占比、同比、环比、除法、空值补零、组内排名：数据模型里有对应的指标时直接调用它；没有时，这个接口在一条查询里表达不了。 | `J30,J31,J32,J33,R_json_limit_per_group`；只允许调用已定义成员；这里不是创造缺失的排名指标。表达能力结论限于一条既定成员JSON对象。 |

## 独立数值与类型检查

| 项目 | 结果 | 依据 |
|---|---|---|
| `R_period_case_year_calendar` | 通过 | independent physical year aggregates; both values, ratio and growth |
| `R_period_case_year_outer_extract` | 通过 | independent physical year aggregates; both values, ratio and growth |
| `R_period_join_year_JOIN` | 通过 | independent physical year aggregates; both values, ratio and growth |
| `R_period_join_year_FULL_OUTER_JOIN` | 通过 | independent physical year aggregates; both values, ratio and growth |
| `R_period_case_month_month_bucket` | 通过 | independent physical month aggregates; both values, ratio and growth |
| `R_period_join_month_JOIN` | 通过 | independent physical month aggregates; both values, ratio and growth |
| `R_period_join_month_FULL_OUTER_JOIN` | 通过 | independent physical month aggregates; both values, ratio and growth |
| `R_ratio_True` | 通过 | two distinct physical aggregates, grouped division |
| `R_ratio_False` | 通过 | global ratio of separate totals, not average of per-group ratios |
| `R_star_right_store_channel_calendar` | 通过 | independent physical star, generic quantity metric |
| `R_star_right_store_calendar_channel` | 通过 | independent physical star, generic quantity metric |
| `R_star_right_channel_store_calendar` | 通过 | independent physical star, generic quantity metric |
| `R_star_right_channel_calendar_store` | 通过 | independent physical star, generic quantity metric |
| `R_star_right_calendar_store_channel` | 通过 | independent physical star, generic quantity metric |
| `R_star_right_calendar_channel_store` | 通过 | independent physical star, generic quantity metric |
| `R_chain_flat` | 通过 | independent physical chain |
| `R_chain_right` | 通过 | independent physical chain |
| `R_two_dims_end` | 通过 | same chain with final dimension omitted |
| `R_two_dims_middle` | 通过 | same chain with final dimension omitted |
| `R_same_cte_alias_JOIN` | 通过 | inner duplicate names with distinct outer output names |
| `R_same_cte_alias_LEFT_JOIN` | 通过 | inner duplicate names with distinct outer output names |
| `R_derived_key_renamed` | 通过 | renamed derived key preserves grouped sum |
| `R_coalesce_actual_null` | 通过 | actual NULL branch filled with zero |
| `R_case_actual_null` | 通过 | actual NULL branch filled with zero |
| `R_per_group_ROW_NUMBER_True` | 通过 | independent groups with unique ordering keys, actual top2 + returned rank |
| `R_per_group_ROW_NUMBER_False` | 通过 | same top2 with native rank only used as filter |
| `R_per_group_RANK_True` | 通过 | independent groups with unique ordering keys, actual top2 + returned rank |
| `R_per_group_RANK_False` | 通过 | same top2 with native rank only used as filter |
| `R_json_skeleton` | 通过 | literal skeleton parsed; only placeholder names substituted |
| `R_json_limit_group` | 通过 | two global rows, not two for each channel |
| `R_json_compiled_beforeDate` | 通过 | compiled UTC boundary parameters, preserved SQL in raw result |
| `R_json_compiled_afterDate` | 通过 | compiled UTC boundary parameters, preserved SQL in raw result |
| `R_json_compiled_inDateRange` | 通过 | compiled UTC boundary parameters, preserved SQL in raw result |
| `repeat_S01` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S30` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S31` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F06` | 通过 | repeat persisted independent baseline expectation |
| `repeat_B23` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S02` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S32_cte` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S32_subquery` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S33_cte` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S33_subquery` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S34_inner` | 已复现原有错值反例 | repeat persisted independent baseline expectation |
| `repeat_S34_left` | 已复现原有错值反例 | repeat persisted independent baseline expectation |
| `repeat_S34_cross_filter` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F01` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F02_same_alias` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F02_distinct_alias` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F03` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F04` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F05` | 已复现原有错值反例 | repeat persisted independent baseline expectation |
| `repeat_S35_ROW_NUMBER_bigint` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S35_RANK_bigint` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F10_ROW_NUMBER` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F11_ROW_NUMBER` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F10_RANK` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F11_RANK` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S40` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S20_eq` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S20_ne` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S20_in` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S20_between` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S20_null` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S20_and_or` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S21` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S37` | 通过 | repeat persisted independent baseline expectation |
| `repeat_S38` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F20_round` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F20_pct` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F22` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F23` | 通过 | repeat persisted independent baseline expectation |
| `repeat_F32` | 通过 | repeat persisted independent baseline expectation |
| `repeat_T03` | 通过 | repeat persisted independent baseline expectation |
| `repeat_T04` | 通过 | repeat persisted independent baseline expectation |
| `repeat_T06` | 通过 | repeat persisted independent baseline expectation |
| `repeat_T07` | 通过 | repeat persisted independent baseline expectation |
| `repeat_B01` | 通过 | repeat persisted independent baseline expectation |
| `repeat_B02` | 通过 | repeat persisted independent baseline expectation |
| `repeat_B25` | 通过 | repeat persisted independent baseline expectation |
| `repeat_B26` | 通过 | repeat persisted independent baseline expectation |
| `repeat_B27` | 通过 | repeat persisted independent baseline expectation |
| `repeat_J01` | 通过 | repeat persisted independent baseline expectation |
| `repeat_J04` | 通过 | repeat persisted independent baseline expectation |
| `repeat_J20_gt` | 通过 | repeat persisted independent baseline expectation |
| `repeat_J20_gte` | 通过 | repeat persisted independent baseline expectation |
| `repeat_J20_lt` | 通过 | repeat persisted independent baseline expectation |
| `repeat_J20_lte` | 通过 | repeat persisted independent baseline expectation |
| `repeat_J21_or` | 通过 | repeat persisted independent baseline expectation |
| `repeat_J21_and` | 通过 | repeat persisted independent baseline expectation |
| `repeat_J21_default` | 通过 | repeat persisted independent baseline expectation |
| `repeat_J22` | 通过 | repeat persisted independent baseline expectation |
| `repeat_J23` | 通过 | repeat persisted independent baseline expectation |
| `repeat_J20_inDateRange` | 通过 | repeat persisted independent baseline expectation |

## 固定证据与后续

- metadata.json记被审提交、两份说明及大纲/裁决哈希、部署模型哈希和格式骨架。manifest.json/results.jsonl固定本轮通用查询与完整响应；只读ClickHouse基线在外部数据目录interface-probes下。
- 本脚本有--report-only入口，读取现有固定结果并重做独立物理聚合，绝不执行题目或模型调用。
- 删除后应再核对T12分支最新提交；本报告不等于批准semantic-v1.3。用户合并、打tag之后，才以eval-v1.2+semantic-v1.3先dry-run、等批准、错峰重跑SQL/JSON冒烟。
