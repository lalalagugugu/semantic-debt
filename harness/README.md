# harness

调用模型、执行查询、评分。

计划中的模块：

| 模块 | 卡 | 作用 |
|---|---|---|
| `client.py` | T11 | DeepSeek 官方 API（OpenAI 兼容）。key 只从 `DEEPSEEK_API_KEY` 读；思考模式开启，**不要设 temperature** |
| `exec_sql.py` | T11 | chDB 只读执行 |
| `run_direct.py` | T11 | 直答：一次调用写出查询；执行报错时发回报错、固定修一次 |
| `run_agent.py` | T15 | 探查 agent（-E）：多一个只读工具 `run_sql`，最多 8 步 |
| `score.py` | T02（Codex 写） | 评分器 |
| `exec_dax.py` | T17 | Windows 上经 ADOMD.NET 执行 DAX |

硬规则：任何调用付费模型的命令必须支持 `--dry-run`（先打印调用次数与预计费用）；超出任务卡预算上限就停下问用户；失败、超时、拒答、异常如实记录，不得静默重试。系统提示与评分规则在 `harness-v1` 冻结范围内。
