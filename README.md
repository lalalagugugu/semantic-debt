# semantic-debt

语义层欠的账，会让智能问数的准确率掉多少？

本项目在一份公开的零售数仓（Contoso，25 张表）上，用中文问题测量：

- 语义层质量：L0 坏交付 → R 只给表结构 → L1 文档化 → L1.5W 明细宽表 / L1.5S 汇总层 → L2 指标编码
- 查询语言与接口：SQL、DAX、开源指标层（Cube 的 SQL 与 JSON 接口）
- 会自己查数据的 agent 能否替代一部分治理

对每个对比，结论都写成「结果是这样，就做那件事」。

当前状态：搭建中。人看的操作手册见 `START-HERE.md`；给 coding agent 的规则见 `AGENTS.md`；任务见 `tasks/BOARD.md`；不含题目的设计摘要见 `docs/design-v5-public.md`。
