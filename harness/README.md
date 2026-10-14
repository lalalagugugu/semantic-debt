# harness

调用模型、执行查询、评分。

计划中的模块：

| 模块 | 卡 | 作用 |
|---|---|---|
| `client.py` | T11 | DeepSeek 官方 API（OpenAI 兼容）。key 只从 `DEEPSEEK_API_KEY` 读；思考模式开启，**不要设 temperature** |
| `exec_sql.py` | T11 | chDB 只读执行 |
| `run_direct.py` | T11 | 直答：一次调用写出查询；执行报错时发回报错、固定修一次 |
| `run_agent.py` | T15 | 探查 agent（-E）：多一个只读工具 `run_sql`，最多 8 步 |
| `scorer.py` | T02（Codex 写） | 确定性结果集评分器（纯函数，不执行查询） |
| `exec_dax.py` | T17 | Windows 上经 ADOMD.NET 执行 DAX |

硬规则：任何调用付费模型的命令必须支持 `--dry-run`（先打印调用次数与预计费用）；超出任务卡预算上限就停下问用户；失败、超时、拒答、异常如实记录，不得静默重试。系统提示与评分规则在 `harness-v1` 冻结范围内。

## T02 诊断与复现契约（2026-10-14 裁决落实）

`score` 仍仅返回四种冻结判定；`score_detailed` 的 `sensitivity` 不改变准确率。对 `wrong`：`string_or_label_only` 表示保持完整行数、数值列的联合行匹配、数值 NULL、排序与 Top-N 约束后，数值投影匹配任一参考；`numeric_mismatch` 表示未通过此检查。`structure_mismatch` 与 `no_numeric_reference` 单列，不能当作仅格式差异；执行失败、拒答、正确结果不打此标记。

数值投影只提供敏感性上界：不证明不同标签指向同一实体，不做姓名拼接或枚举翻译，缺少数值列仍失败。T19 应同时报告严格准确率与此上界、分母及排除条件。

`ordered` 由题目元数据提供。验证参考没有最终 `ORDER BY` 时置为 false；嵌套查询与窗口排序不算最终排序。参考并列键按已归一的输出值精确判定，0.5% 是结果值容差，不能用来扩大并列组。验证固定 `max_threads=1`、记录运行版本；Top-N 读取完整排序域，按参考投影排序键建立边界组，用行编码固定同值行序，三次成员哈希一致才继续。浮点聚合后的已有 ROUND 精度按原参考保留，不改候选 SQL；Q88使用参考已输出的两位小数作为并列判据。
