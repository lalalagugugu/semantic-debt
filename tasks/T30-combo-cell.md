# T30 叠加单元：L1+ + 调优 + 作答要求

- 状态：tag 与 dry-run 已核对，用户已批准 ≤8 元错峰运行，准备正式运行
- 负责：Codex
- 模式：codex-main
- 依据：用户 2026-10-25「叠加单元可以跑」；`tasks/T27-combo-conflict-check.md` 事先登记的处理规则（L1+ 优先，删掉冲突的调优条目）；`reports/validation/combo-conflicts.md`
- 预算：≤ 8 元（Flash；用户 2026-10-25 批准上调，累计回包费用达到上限停止新增调用）

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
- 用户 2026-10-25 确认 V4.1 Flash 并发上限 2500，允许与 T29 同时运行；原「付费运行不要和 T29 同时进行」约束作废。付费前仍须用户审批。
- chDB：用本卡自己的数据目录副本，不与其他进程同时打开同一个目录（AGENTS.md 硬规则 9），做法同 `scripts/t14_run_on_chdb_copy.py`。

## 不能做

- 不改 `semantic/l1plus.yaml`、原调优文件、评分器、其他单元的系统提示；不改 `.claude/settings.json`；不按题调；`runs/` 只追加。
- 报告只写题号、单元、次数、类别。

## 验收（协调会话）

协调会话从日志独立重算全部数字、费用和系统消息哈希；核对过滤后的调优副本只少了那 12 条。

## 执行记录（2026-10-25）

- 已按用户最新裁决撤销与 T29 不同时运行的约束（V4.1 Flash 并发上限 2500）；chDB 隔离要求不变。
- 过滤脚本 `render/combo.py` 按编号删除 12 条，R6 按 T27 的原文件改写顺序定位；副本 `semantic/tuning/SQL-L1.combo.yaml` 保留 17 条口径、6 条改写、5 条示例。原文件未改。
- `uv run pytest tests/test_combo.py tests/test_l1plus_render.py -q`：13 项通过；保留条目字节一致，两个对照单元完整系统消息与本分支起点一致。
- 重建：`uv run python -m render.combo`，然后 `uv run python -m render.context SQL-L1plus SQL-L1-tuned SQL-L1plus-tuned-instr`。
- 系统消息 SHA-256：
  - SQL-L1plus（不变）：`b80107d469e5600f1c7f3150afef18d11734452a25cc9340f1df46bc470073a3`
  - SQL-L1-tuned-instr（不变）：`03ec10aaee61157852ce3bebed699dec5c9df48d02deb1504dfd19663999cb06`
  - SQL-L1plus-tuned-instr：`16f3b0e2cc3b3ae547328c9c918f78be6acffac961c39becb4d54e477a6e6445`
- 运行入口 `scripts/t30_run_on_chdb_copy.py` 仅指向 `$SEMDEBT_DATA_DIR/chdb-t30`，尚未打开数据库；tag 后从 Parquet 重建私有副本，不打开其他卡的目录。
- 用户确认：合并后在合并提交打 `semantic-combo-v1`、`harness-combo-v1`（单元注册涉及 harness）。确认 tag 后才 dry-run，费用批准后才付费。
- 待办：109 题 × 3 次、v2 主评分/v3 并列、配对区间和稳定性报告；报告只含题号、单元、次数、类别，注明删除的 12 条含 9 条示例 SQL，叠加效果为下限。
- 偏离与理由：仅用户授权的 T29 并行约束变更；未改冻结内容、原调优补充或评分器。
- 工时：未精确计时。

## 正式运行批准与预检（2026-10-25）

- 用户确认 `semantic-combo-v1`、`harness-combo-v1` 均已推送，实核都在合并提交 `2f2d6446af17acca1bb15bf7779bb1d859a3e85b`。
- dry-run：109 题 × 3 = 327 次作答，按 10% 修正估计 360 次 API 调用，错峰约 6.12 元；原 6 元预算检查拒绝启动，未付费。
- 用户明确批准预算上调到 8 元并立即错峰运行；运行编号 `20261025-T30-combo-01`。默认并发 8，不改变作答设置。
- 私有副本由 `data/build_chdb_copy.py` 从 Parquet 新建到 `$SEMDEBT_DATA_DIR/chdb-t30`：25 表、34,326,191 行；未打开其他卡的 chDB。
- 因原 harness 的 `--budget` 只查估算，在 T30 包装入口新增实际回包费用检查，逐回包核算，达到 8 元阻止新调用；在途回包完整保留并计费。未改冻结的 harness、语义或渲染内容，系统消息哈希仍为 `16f3b0e2cc3b3ae547328c9c918f78be6acffac961c39becb4d54e477a6e6445`。
- 最小验证：`uv run pytest tests/test_combo.py tests/test_l1plus_render.py -q`，15 项通过；预算检查覆盖停止新增调用、在途响应计费、原始回包保存及恢复时已用费用累计。
- 重新 dry-run `--budget 8` 通过；付费入口使用 `--expected-fingerprint e72d3c7f663d3e1383b00b3884cb4501`，指纹或错峰条件变化立即停止。
