# harness

调用模型、执行查询、评分。

计划中的模块：

| 模块 | 卡 | 作用 |
|---|---|---|
| `client.py` | T11 | DeepSeek 官方 API（OpenAI 兼容，标准库 urllib）。key 只从 `DEEPSEEK_API_KEY` 读；思考模式开启（`reasoning_effort=high`），**不设 temperature**；429/5xx/网络错误指数退避，次数入日志。另有 `MockClient` 供离线测试 |
| `executors.py` | T11 | 统一接口 `execute(query) -> ExecResult`。`ChdbExecutor`：只读、单条 SELECT、**按单元的允许库拒绝越界查询**（`EXPLAIN AST` 解析表名；引擎 `UNKNOWN_TABLE` 提示指向越界库的也算），回传给模型的是 harness 自己的固定消息、原始报错只进 runs-raw；超时 120 秒与全局资源闸（结果 200 万行、内存 16 GiB）；失败分 `timeout` / `resource_limit` / `engine_error` / `scope_violation` / `forbidden_statement`；报错后重新同步 session（T11-2）。裁决见 `decisions/2026-10-16-t11-exec-limits-and-scope-message.md`。Cube SQL / Cube JSON / DAX 留了同名接口的占位 |
| `cells.py` | T11 | 单元清单（与 BOARD 一致）、每单元允许的库、上下文来源、价格表、默认超时 |
| `prompt.py` | T11 | 系统提示（`harness-v1` 冻结范围）、稳定前缀的拼装（系统提示 → 语义上下文 → 语法说明；用户消息只放题目）、响应解析 |
| `questions.py` | T11 | 中文题集读 `$SEMDEBT_EVAL_DIR/questions/*.yaml`，参考结果读 CSV 并按 `refs/MANIFEST.json` 的列类型还原。题级 `rules` 与逐参考 `rules` 原样交给评分器（`reference_rules`），`selection` 等字段不读不改；题目文件与 MANIFEST 的有效 `rules` 不一致时拒绝加载。英文锚点（99 道）按英文原文对应到题库题号，按外部原始参考评分、另记修订后参考的对照列。judge 题 / 无参考 / 无 `rules` 的返回行集记 `pending`，行集存 runs-raw 待离线重评 |
| `anchor_refs.py` | T11 | 英文锚点的原始参考：外部 `expected_sql` 原样在本地完整执行，存 `$SEMDEBT_DATA_DIR/anchor-refs/`（不入库）；`--check` 逐字节复核 |
| `rescore.py` | T11 | 离线重评：从 runs-raw 的执行结果重建候选（核 sha256），按当前题库重评，写进新 run 目录；题干变过的行拒绝 |
| `run_direct.py` | T11 | 直答：一次调用写出查询；执行报错时发回报错、固定修一次。日志、断点续跑、`--dry-run`、并发 |
| `run_agent.py` | T15 | 探查 agent（-E）：多一个只读工具 `run_sql`，最多 8 步 |
| `scorer.py` | T02（Codex 写） | 确定性结果集评分器（纯函数，不执行查询） |
| `exec_dax.py` | T17 | Windows 上经 ADOMD.NET 执行 DAX |

硬规则：任何调用付费模型的命令必须支持 `--dry-run`（先打印调用次数与预计费用）；超出任务卡预算上限就停下问用户；失败、超时、拒答、异常如实记录，不得静默重试。系统提示与评分规则在 `harness-v1` 冻结范围内。

## T02 诊断与复现契约（2026-10-14 裁决落实）

`score` 仍仅返回四种冻结判定；`score_detailed` 的 `sensitivity` 不改变准确率。对 `wrong`：`string_or_label_only` 表示保持完整行数、数值列的联合行匹配、数值 NULL、排序与 Top-N 约束后，数值投影匹配任一参考；`numeric_mismatch` 表示未通过此检查。`structure_mismatch` 与 `no_numeric_reference` 单列，不能当作仅格式差异；执行失败、拒答、正确结果不打此标记。

数值投影只提供敏感性上界：不证明不同标签指向同一实体，不做姓名拼接或枚举翻译，缺少数值列仍失败。T19 应同时报告严格准确率与此上界、分母及排除条件。

`ordered` 由题目元数据提供。验证参考没有最终 `ORDER BY` 时置为 false；嵌套查询与窗口排序不算最终排序。参考并列键按已归一的输出值精确判定，0.5% 是结果值容差，不能用来扩大并列组。验证固定 `max_threads=1`、记录运行版本；Top-N 读取完整排序域，按参考投影排序键建立边界组，用行编码固定同值行序，三次成员哈希一致才继续。浮点聚合后的已有 ROUND 精度按原参考保留，不改候选 SQL；Q88使用参考已输出的两位小数作为并列判据。

## 2026-10-15：量纲绝对容差与跨引擎并列

参考结果的每一列有 `value_kinds`；外部旧题由 `harness/value_units.py` 的全局参考列名称规则自动生成，验证适配器补充参考返回类型及COUNT表达式别名。不依赖题号、候选列名称或数值大小。不能识别的列为other，atol=0；别名必须表达量纲，识别边界在校验报告中公开。未提供value_kinds的旧调用仍按other处理；外部旧题由适配器推断；T05新题显式声明value_kinds，infer_value_kind仅交叉校验、不一致告警。新harness必须同时透传参考返回类型`value_types`（逐列类型字符串），列顺序跟随参考，不跟随候选。

相等判定是 `abs(candidate-reference) <= max(0.005*abs(reference), atol)`：金额0.01、比率小数形式1e-4、百分比先归一到小数（原百分比单位下等价于0.01），其余0。除下述整数计数收紧外保留旧匹配；参考为零时不猜候选是否换了100倍单位。`use_absolute_tolerance=false`只用于诊断旧容差；`exact_counts=true`已按用户#8裁决成为默认正式规则：只有`value_kinds[i]=="count"`且`value_types[i]`为整数返回类型时，候选数值必须`==`参考数值，不用相对容差、atol或百分数换算。类型守卫识别Int/UInt8/16/32/64/128/256及Nullable/LowCardinality包装，不依据Python单元格类型、整数外观、数值大小或候选类型。非整数count仍按0.5%相对容差；旧调用缺少类型时无法证实整数，不启用精确相等，新harness不得遗漏类型。`exact_counts=false`仅用于收紧前的诊断对照。

并列键与atol独立：Decimal(str(value))，ROUND_HALF_EVEN，金额2位、比率小数形式6位、其余数值6位。不得逐题选精度。T05b复现的是量化键和完整成员集合，不是跨引擎原始浮点哈希；单引擎三次原始参考哈希仅为运行稳定性检查。规则版本为2026-10-15，未来更改需统一迁移与重新评分。
