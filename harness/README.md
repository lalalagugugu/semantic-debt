# harness

## T16：Cube 执行器与本地搭建

`harness/executors.py` 提供 `CubeSqlExecutor(timeout_s=120)` 与
`CubeJsonExecutor(timeout_s=120)`，接口均为 `execute(query: str) -> ExecResult`。
可直接供 T15 导入。SQL 使用 PostgreSQL 协议，JSON 使用 REST `/load`；
`CANNOT_ANSWER` 继续由现有 harness 处理，不作为查询发给执行器。

前置：Docker Desktop 已运行，`SEMDEBT_DATA_DIR` 指向 T01 数据目录。
从本卡 clone 根目录依次执行（无 DeepSeek 调用）：

```sh
uv sync --locked
uv run python render/cube.py
uv run python data/build_chdb_copy.py "$SEMDEBT_DATA_DIR/chdb-t16"
docker compose up -d --wait clickhouse
uv run python data/clickhouse_t16.py --import-data
docker compose up -d --wait cube
uv run python scripts/verify_metric_layer.py
uv run pytest tests/test_cube_executors.py
```

独立 chDB 副本只需建一次，已有时跳过第 3 行；不要用 `--force` 覆盖正在使用的目录。
导入脚本保留已有非空表并重新核对。发生部分导入或数据不一致时会失败，不自动删表重导。
核对报告写到 `reports/validation/clickhouse_t16.md`、`metric_layer_t16.md` 与同名 JSON。
主 chDB 目录被其他会话占用时，不会尝试共享；独立副本还与 T01 原始报告交叉核对。

服务固定为 Cube Core 1.8.6、ClickHouse 25.8.20.4，仅供本机实验；REST 开发模式不校验
JWT，SQL 开发模式接受任意非空认证响应。两个接口都绑定 loopback：

| 接口 | 默认地址 | 执行器配置环境变量 |
|---|---|---|
| SQL | `127.0.0.1:15432`，库/用户 `cube` | `CUBE_SQL_HOST`、`CUBE_SQL_PORT`、`CUBE_SQL_USER`、`CUBE_SQL_DATABASE`、`CUBE_SQL_PASSWORD` |
| REST | `http://127.0.0.1:14000/cubejs-api/v1` | `CUBE_REST_URL`、`CUBE_REST_TOKEN`（有认证时） |
| ClickHouse HTTP | `127.0.0.1:18123` | 只用于本地运维，模型不直接访问 |

数据分别位于 `$SEMDEBT_DATA_DIR/clickhouse-t16`、`chdb-t16`、`cubestore-t16`；
模型只读挂载 `build/cube/model`。Cube 的 ClickHouse 用户仅有 `retail.*` 的 SELECT 权限，
`readonly=2` 允许驱动设置 `join_use_nulls`、同时禁止写入。SQL 执行器额外拒绝多语句、写语句与修改会话设置。

两个执行器每次执行有总时限及 2,000,000 行上限。Cube 默认/最大查询行数配置为
2,000,001（探测超限），避免默认 10,000 行静默截断。REST 只轮询协议要求的
`Continue wait`，其他失败不重试；数值依注解转为整数或 Decimal，时间别名不重复输出。
`interface_limitation`、`timeout`、`resource_limit`、`transport_error`、`invalid_response`
与普通 `engine_error` 分开，供 T19 归类；只有明确的“不支持”错误自动标为接口限制。

停服务用 `docker compose stop`，不删除数据。G3 和 T13 尚未完成，本轮不接通直答 runner、
不跑题集；未来接通 SQL-L2 / JSON-L2 时仍须遵循任务卡的检查点与预算规则。

调用模型、执行查询、评分。

计划中的模块：

| 模块 | 卡 | 作用 |
|---|---|---|
| `client.py` | T11 | DeepSeek 官方 API（OpenAI 兼容，标准库 urllib）。key 只从 `DEEPSEEK_API_KEY` 读；思考模式开启（`reasoning_effort=high`），**不设 temperature**；429/5xx/网络错误指数退避，次数入日志。另有 `MockClient` 供离线测试 |
| `executors.py` | T11、T16 | 统一接口 `execute(query) -> ExecResult`。`ChdbExecutor`：只读、单条 SELECT、**按单元的允许库拒绝越界查询**（`EXPLAIN AST` 解析表名；引擎 `UNKNOWN_TABLE` 提示指向越界库的也算），回传给模型的是 harness 自己的固定消息、原始报错只进 runs-raw；超时 120 秒与全局资源闸（结果 200 万行、内存 16 GiB）；失败分 `timeout` / `resource_limit` / `engine_error` / `scope_violation` / `forbidden_statement`；报错后重新同步 session（T11-2）。裁决见 `decisions/2026-10-16-t11-exec-limits-and-scope-message.md`。Cube SQL / Cube JSON 已实现（见上文 T16）；DAX 留占位给 T17 |
| `cells.py` | T11 | 单元清单（与 BOARD 一致）、每单元允许的库、上下文来源、价格表、默认超时 |
| `prompt.py` | T11 | 系统提示（`harness-v1` 冻结范围；第 1–5 条是作答格式，第 6–15 条是结果的展示约定：名称标识（名称缺失或占位时给编码）、不截断、分类值照原值、长表、无合计行、日期与期间写法、金额原始单位、变化率与降幅的写法、变化量同时给绝对值和百分比（百分点除外）、多行排名给名次、比率给基数（均值不算比率），见 `decisions/2026-10-18-names-required-by-system-prompt.md`、`decisions/2026-10-18-ux-conventions-and-annotation-disputes.md` 第一、五、八节）、稳定前缀的拼装（系统提示 → 语义上下文 → 语法说明；用户消息只放题目）、响应解析 |
| `questions.py` | T11 | 中文题集读 `$SEMDEBT_EVAL_DIR/questions/*.yaml`，参考结果读 CSV 并按 `refs/MANIFEST.json` 的列类型还原。题级 `rules` 与逐参考 `rules` 原样交给评分器（`reference_rules`），`selection` 等字段不读不改；题目文件与 MANIFEST 的有效 `rules` 不一致时拒绝加载。英文锚点（99 道）按英文原文对应到题库题号，按外部原始参考评分、另记修订后参考的对照列；锚点继承的中文 `rules` 与 `scoring` 固定取 `--anchor-rules-tag`（默认 `eval-v1`），见下文「英文锚点的规则来源」。judge 题 / 无参考 / 无 `rules` 的返回行集记 `pending`，行集存 runs-raw 待离线重评 |
| `anchor_refs.py` | T11 | 英文锚点的原始参考：外部 `expected_sql` 原样在本地完整执行，存 `$SEMDEBT_DATA_DIR/anchor-refs/`（不入库）；`--check` 逐字节复核 |
| `rescore.py` | T11、T12 | 离线重评：从 runs-raw 的执行结果重建候选（核 sha256），按当前题库重评，写进新 run 目录；`--eval-tag` 校验题库是该 tag 的内容；题干变过的行默认拒绝，只有显式 `--allow-changed-question` 才照评并在行内标 `question_changed`（T12 最终重评只用于 Q69） |
| `run_direct.py` | T11 | 直答：一次调用写出查询；执行报错时发回报错、固定修一次。日志、断点续跑、`--dry-run`、并发 |
| `run_agent.py`、`agent_prompt.py` | T15 | 探查 agent（-E）：直答系统消息逐字节 + 一段工具说明（`agent_prompt.py`，`harness-agent-v1` 冻结）；只读工具 `run_sql` 过与最终查询相同的检查，每次回显至多 50 行（截断时写明总行数），最多 8 次，之后 `tool_choice: "none"` 强制交卷；最终答案照直答规则执行、修一次、限时打分。日志另记 `steps`。见 `tasks/T15-explorer-agent.md` |
| `scorer.py` | T02（Codex 写） | 确定性结果集评分器（纯函数，不执行查询） |
| `exec_dax.py` | T17 | Windows 上经 ADOMD.NET 执行 DAX |

### 英文锚点的规则来源

英文锚点按英文原题与外部原始参考评分（`decisions/2026-10-17-semantic-gaps-and-realistic-questions.md` 第三节第 6 条、`decisions/2026-10-18-ux-conventions-and-annotation-disputes.md` 第四节第 4 条），不受中文题库修订的影响。原始参考没有题库专门写的规则时，锚点照搬对应中文题的有效 `rules`（列数和列类型相同的那份参考）。这份 `rules` 以前读当前题库，于是中文题库的展示修订会被锚点继承。`eval-v1.1` 追加了名次、分母、增长额、客户键等约定列，把季度改写成 `Q1`–`Q4`、宽表改成长表，还加了 `required_columns`。结果 28 个锚点因为列类型对不上而变成 pending（可评分的从 87 个降到 62 个），另外 56 个锚点从「全部列必答」变成只比必答列。

所以继承的中文 `rules` 和 `scoring` 固定取一个 tag：`questions.zh_rules_at` 用 `git show <tag>:questions/…` 从同一个题库仓库读，tag 由 `run_direct.py --anchor-rules-tag` 指定（默认 `eval-v1`）。

- 读不到这个 tag 就拒绝启动，不回退到当前题库。
- 题库专门为原始参考写的规则（`audit/anchor-original-rules-review.md`，已核对哈希）、修订后参考的对照列（`revised`）仍读当前题库。
- 日志每行记 `anchor_rules: {tag, commit}`。
- 效果：题库取 `eval-v1` 或 `eval-v1.1` 时，99 个锚点的规则、pending、边界补全逐个相同，可评分 87 个，没有一个带 `required_columns`（即全部列必答）。快照在 `tests/anchor_rules_eval_v1.json`，由 `test_anchors_score_exactly_as_at_eval_v1_whatever_the_current_bank` 检查。

硬规则：任何调用付费模型的命令必须支持 `--dry-run`（先打印调用次数与预计费用）；超出任务卡预算上限就停下问用户；失败、超时、拒答、异常如实记录，不得静默重试。系统提示与评分规则在 `harness-v1` 冻结范围内。

## T02 诊断与复现契约（2026-10-14 裁决落实）

`score` 仍仅返回四种冻结判定；`score_detailed` 的 `sensitivity` 不改变准确率。对 `wrong`：`string_or_label_only` 表示保持完整行数、数值列的联合行匹配、数值 NULL、排序与 Top-N 约束后，数值投影匹配任一参考；`numeric_mismatch` 表示未通过此检查。`structure_mismatch` 与 `no_numeric_reference` 单列，不能当作仅格式差异；执行失败、拒答、正确结果不打此标记。

数值投影只提供敏感性上界：不证明不同标签指向同一实体，不做姓名拼接或枚举翻译，缺少数值列仍失败。T19 应同时报告严格准确率与此上界、分母及排除条件。

`ordered` 由题目元数据提供。验证参考没有最终 `ORDER BY` 时置为 false；嵌套查询与窗口排序不算最终排序。参考并列键按已归一的输出值精确判定，0.5% 是结果值容差，不能用来扩大并列组。验证固定 `max_threads=1`、记录运行版本；Top-N 读取完整排序域，按参考投影排序键建立边界组，用行编码固定同值行序，三次成员哈希一致才继续。浮点聚合后的已有 ROUND 精度按原参考保留，不改候选 SQL；Q88使用参考已输出的两位小数作为并列判据。

## 2026-10-15：量纲绝对容差与跨引擎并列

参考结果的每一列有 `value_kinds`；外部旧题由 `harness/value_units.py` 的全局参考列名称规则自动生成，验证适配器补充参考返回类型及COUNT表达式别名。不依赖题号、候选列名称或数值大小。不能识别的列为other，atol=0；别名必须表达量纲，识别边界在校验报告中公开。未提供value_kinds的旧调用仍按other处理；外部旧题由适配器推断；T05新题显式声明value_kinds，infer_value_kind仅交叉校验、不一致告警。新harness必须同时透传参考返回类型`value_types`（逐列类型字符串），列顺序跟随参考，不跟随候选。

相等判定是 `abs(candidate-reference) <= max(0.005*abs(reference), atol)`：金额0.01、比率小数形式1e-4、百分比先归一到小数（原百分比单位下等价于0.01），其余0。除下述整数计数收紧外保留旧匹配；参考为零时不猜候选是否换了100倍单位。`use_absolute_tolerance=false`只用于诊断旧容差；`exact_counts=true`已按用户#8裁决成为默认正式规则：只有`value_kinds[i]=="count"`且`value_types[i]`为整数返回类型时，候选数值必须`==`参考数值，不用相对容差、atol或百分数换算。类型守卫识别Int/UInt8/16/32/64/128/256及Nullable/LowCardinality包装，不依据Python单元格类型、整数外观、数值大小或候选类型。非整数count仍按0.5%相对容差；旧调用缺少类型时无法证实整数，不启用精确相等，新harness不得遗漏类型。`exact_counts=false`仅用于收紧前的诊断对照。

并列键与atol独立：Decimal(str(value))，ROUND_HALF_EVEN，金额2位、比率小数形式6位、其余数值6位。不得逐题选精度。T05b复现的是量化键和完整成员集合，不是跨引擎原始浮点哈希；单引擎三次原始参考哈希仅为运行稳定性检查。规则版本为2026-10-15，未来更改需统一迁移与重新评分。
