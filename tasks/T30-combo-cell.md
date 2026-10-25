# T30 叠加单元：L1+ + 调优 + 作答要求

- 状态：未开始
- 负责：Codex
- 模式：codex-main
- 依据：用户 2026-10-25「叠加单元可以跑」；`tasks/T27-combo-conflict-check.md` 事先登记的处理规则（L1+ 优先，删掉冲突的调优条目）；`reports/validation/combo-conflicts.md`
- 预算：≤ 6 元（Flash；先 dry-run，用户批后错峰运行）

## 要回答的问题

两条「写准」路径叠加（L1+ 主动审查 + 复盘调优与作答要求）能把准确率推到多少，尤其是留出题。

## 单元

- `SQL-L1plus-tuned-instr`：SQL-L1plus 的语义上下文 + 调优补充 + 作答要求补丁。
- 调优补充：从 `semantic/tuning/SQL-L1.yaml` **机械地**去掉 T27 列出的 12 个冲突条目（E01、E02、E03、E05、E07、E08、E09、E10、E13、S11、S14，以及改写里对应 S14 的那一条，T27 报告里定位为 R6），其余条目一字不改。生成一份过滤后的副本，不改原文件；过滤脚本只按编号删除，测试证明剩下的条目与原文件逐字节相同。
- 作答要求补丁：`semantic/tuning/SQL-L1.instructions.yaml` 全部 22 条照用（T27 冲突 0 条），渲染方式同 SQL-L1-tuned-instr。
- 模型、评分器（v2 为主，v3 并列）、「执行报错发回修一次」都不变。109 题 × 3 次。

## 步骤

1. 渲染上下文，报系统消息哈希；证明 SQL-L1plus、SQL-L1-tuned-instr 的系统消息哈希不变。
2. 请用户打 tag（建议语义侧 `semantic-combo-v1`；若作答要求补丁走 harness，再加 `harness-combo-v1`），打在合并提交上。
3. dry-run 报调用次数和预计费用 → 用户批 → 错峰运行（工作日 9–12、14–18 点以外）。
4. 报告 `reports/results/combo.md`：主表 98、留出 49、调优 49 三列；与 SQL-L1plus、SQL-L1-tuned-instr 的按题配对比较（自助法区间，同 `reports/results/tuning.md`）；3 次全对 / 有对有错 / 3 次全错的题数。
5. 写明解读限制：删掉的 12 条里 9 条是示例 SQL，叠加单元因此偏吃亏，结果是叠加效果的下限。

## 和同期其他卡的关系

- 与 T29（取舍单元）、T28（补数）互不影响：单元、上下文、tag 都分开，T28 只做离线计算。
- 付费运行不要和 T29 的试跑或正式运行同时进行（共用 API 并发）。
- chDB：用本卡自己的数据目录副本，不与其他进程同时打开同一个目录（AGENTS.md 硬规则 9），做法同 `scripts/t14_run_on_chdb_copy.py`。

## 不能做

- 不改 `semantic/l1plus.yaml`、原调优文件、评分器、其他单元的系统提示；不改 `.claude/settings.json`；不按题调；`runs/` 只追加。
- 报告只写题号、单元、次数、类别。

## 验收（协调会话）

协调会话从日志独立重算全部数字、费用和系统消息哈希；核对过滤后的调优副本只少了那 12 条。
