# T30 叠加单元：L1+ + 调优 + 作答要求

- 状态：正式运行与 v2/v3 报告完成，待协调验收；3 次未返回 usage 的传输失败费用待账单核对
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

## 正式运行与报告交付（2026-10-25）

- `20261025-T30-combo-01`：周日错峰，109 题 × 3 = 327 次作答全部完成；339 次有回包调用，含执行错误后的 12 次固定修正。没有补跑；无 API/harness 失败行、无 pending/unscored、无指纹变化。
- 原始回包逐哈希与 usage 对账：可核算费用 **2.89061402 元**，低于 8 元，费用停止阈值未触发。传输重试 **3 次**（Q49 第 3 次、Q67 第 3 次、Q79 第 2 次各 1）；由既有 harness 自动处理，失败请求未返回 usage，其费用无法从本地确认，未按零计费。严格总账仍待提供商账单核对，没有宣称未知费用已包含在可核算金额中。
- 最终类别（v2/v3 相同）：correct 282、wrong 44、exec_error 1、refused 0。Q84 第 3 次为最终 exec_error，原样保留，不补跑。
- 系统消息 SHA-256：`16f3b0e2cc3b3ae547328c9c918f78be6acffac961c39becb4d54e477a6e6445`，339 次回包对应的指纹均为 `e72d3c7f663d3e1383b00b3884cb4501`。
- `20261025-T30-combo-01-rescore-01`：复用 T23 的冻结题库与原始执行结果哈希核对，对本单元及两个对照单元共 981 次作答离线重评；无额外模型调用、无 SQL 重跑。
- v2/v3 均为：主表 87.4%（257/294）、留出 81.0%（119/147）、调优 93.9%（138/147）；叠加单元 v3 改判 0 次。
- 按题三次稳定性（109 题）：全对 85、有对有错 16、全错 8；主表 98 题为 77/15/6，留出 49 题为 33/11/5。
- 产出：`reports/results/combo.md`、付费原始日志、离线重评日志及 manifest、`scripts/t30_combo_report.py`。报告只列题号、单元、次数、类别与所需汇总统计，不含题面、查询或参考值；按卡注明删除 12 条中 9 条示例 SQL 的下限限制。
- 配对比较按题 5,000 次自助抽样、种子 0：v2 叠加 − SQL-L1plus 主表 +11.9 点 [ +4.4, +19.7 ]、留出 +4.8 点 [ −6.1, +15.6 ]；叠加 − SQL-L1-tuned-instr 主表 −1.0 点 [ −5.1, +3.1 ]、留出 −1.4 点 [ −6.8, +4.8 ]。v3 并列数字见报告。
- 运行复现（会付费，重跑必须另建 run-id 并重新批准）：`uv run python scripts/t30_run_on_chdb_copy.py --cell SQL-L1plus-tuned-instr --model deepseek-flash --reps 3 --concurrency 8 --semantic-tag semantic-combo-v1 --eval-tag eval-v1.2 --budget 8 --expected-fingerprint e72d3c7f663d3e1383b00b3884cb4501 --run-id <新的run编号>`；题库环境使用 `eval-v1.2` 的只读副本。
- 免费复算：`uv run python scripts/t30_combo_report.py --run 20261025-T30-combo-01 --scored-run <新的离线run编号>`。
- 验证：16 项过滤、冻结消息、预算停止、回包保留、统计分母及重复记录检查通过；运行与报告的原始回包、执行结果哈希核对通过。
- 待协调会话独立核对数字、费用、哈希和机械过滤副本；3 次失败请求的提供商账单费用仍待核对。
