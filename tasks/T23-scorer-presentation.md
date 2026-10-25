# T23 评分器呈现容错（v3）与全部单元离线重评

- 状态：v3 实现及现有单元离线重评完成（2026-10-25）；待 Claude Code 逐条复核 82 条新增判对，T22b 完成后补评
- 负责：Codex（评分器本来归 Codex，T02）
- 模式：codex-main
- 依据：`decisions/2026-10-25-no-full-rerun-l1plus-last.md`；T19b 复核发现 L1 错答里约 16/117 只是呈现形态不同（`reports/results/l1-error-attribution.md`）
- 依赖：`harness-v1.1`（scorer v2）、`eval-v1.2`
- 预算：0（只离线重评，不调模型）

## 要做的事

1. 从 T19b 的「呈现形态不同、答案本身对」条目归纳**通用**的呈现容错规则（例如多余的维度列、宽表 vs 长表、标签列与键列互换一类）。规则必须按类别写，不得针对某道题；每条规则写明为什么不会把真错判对。规则清单交用户审定后再实现。
2. 实现为 scorer v3，v2 原样保留。两版评分器在同一份作答上都能跑。
3. 离线重评**全部已跑单元**（T13 六个单元、T15、T16、C13、T14 调优、T22b 跑完后也算），写新的 rescore run 目录，`runs/INDEX.md` 记原因。
4. `reports/results/scorer-v3.md`：每个单元 v2 与 v3 的主表准确率并排、变化的作答条数；单元之间的相对排序是否改变。
5. 审定和合并后由用户打新的 harness tag（拟 `harness-v1.2`）。

## 不能做

- 不改 v2 的判定；不按题加规则；不改参考答案（参考答案的问题写进题库 `decisions/`，问用户）。

## 验收（协调会话 + 另一家）

v3 新判对的作答由 Claude Code 会话逐条抽查（跨厂商），确认没有把真错判对。

## 执行记录（2026-10-25）

- 产出：`decisions/2026-10-25-t23-presentation-rules-proposal.md`，归纳期间等价、长宽表、保留编码时的名称替代、冗余展示列四类候选规则及反例。
- 开工核对：Codex / codex-main / T23-work；harness-v1.1 与 eval-v1.2 均存在，eval-v1.2 提交为 90e13b3。
- 证据边界：T19b Codex 说明中有 36 条“呈现差异”，不等于全部应转正；尚未逐条读取原始执行结果验证，不能把卡片约 16 条当作预设结果。
- 偏离与理由：无；按第 1 步要求，在规则审定前暂停实现。未改代码、参考、冻结内容及运行日志，未调用模型。
- 验证：本阶段仅文档整理，未执行测试或重评。
- 工时：本轮完成开工核对、既有评分路径与归因材料阅读、规则提案整理；未精确计时。

### 用户确认

- [x] 审定提案 P1–P4 及其防误判条件（P3 仅 NULL/空字符串；保守列证据；v3 仅敏感性分析）。
- [x] 确认保持必答列、排序、Top-N 和数值评分边界；如需扩大范围，另作明确裁决。
- [ ] 实现及离线重评后安排 Claude Code 逐条抽查新增判对。

## 实现与重评记录（2026-10-25）

- 裁决：`decisions/2026-10-25-t23-presentation-rules-approved.md`。P3 不接受任何文字占位；不翻译业务标签、不增加题号映射；主数字继续用 v2。
- 实现：新增 `harness/scorer_v3.py` 与 `scripts/rescore_t23.py`；v2、旧评分器、系统提示均未改。P4 的额外列映射已由 v2 支持，没有补充判分代码；P1/P2/P3 的保守实现边界见裁决记录。
- 正式产物：`runs/20261025-T23-v3-02/`、`reports/results/scorer-v3.md`；27 份源日志、6,188 条 done 全部重评，另记录 C13 历史试跑 12 条 harness_error。包括 T13 六单元及 L1.5S 重跑、T15、T16、C13、T14 两单元与历史试跑；T22b 目前无作答日志，不能声称已重评。
- 结果：最终 wrong→correct 82 条，全部为 P1；correct→wrong 0；首次判定改判 69 条，均在最终改判清单中。主表 SQL-L1：v2 67.7%（199/294）、v3 70.7%（208/294）；完整 98 题单元的排序及并列关系未变。C13 T4 仅 49 题，单列实际分母，不纳入完整单元排序。
- 验证：`UV_CACHE_DIR="$TMPDIR/uvcache" uv run --offline pytest tests/test_scorer_v3.py tests/test_rescore_t23.py tests/test_scorer_v2.py tests/test_scorer_v2_shared.py tests/test_scorer_v2_performance.py` → **451 passed**；当前对照所用 5,672 条作答的 v2 结果与既有定稿/原 v2 日志逐条比较，**0 分歧**。正式 run 的代码哈希复验通过，v2 与 harness-v1.1 中的文件一致。
- 复现：在命令环境设置用户指定的 `SEMDEBT_EVAL_DIR`、`SEMDEBT_DATA_DIR`、`SEMDEBT_CARDS_DIR` 后，`UV_CACHE_DIR="$TMPDIR/uvcache" uv run --offline python scripts/rescore_t23.py --run-id <全新run-id>`；结果拒绝覆盖旧目录，输入题面/执行结果哈希异常时拒绝评分。
- 复核包：`$SEMDEBT_DATA_DIR/t23-v3-review/20261025-T23-v3-02/`，82 条，每条含题面、候选、参考、规则、列证据及版本结果；不入库。`cases.jsonl` SHA-256：`adda75cdc0dfdb7fd0d60a445e36ea518622bac6fb4c4647ac778da1f89b3f52`。
- 偏离：首轮 `20261025-T23-v3-01` 的代码哈希采集时机不严格，保留原样但不作验收依据；第二轮固定代码及源日志哈希，见裁决记录。预算 0；无模型调用、无查询执行、无配置写入。
- 工时：本轮完成实现、合成反例与既有契约/性能验证、两轮全量离线比较、来源核验及复核包整理；未精确计时。

### 剩余验收

- [ ] Claude Code 跨厂商逐条复核正式 run 中 82 条新增判对，记录 accept/reject/uncertain；不以同厂商子 agent 代替。
- [ ] T22b 完成后新开 run 补评并更新比较报告。
- [ ] 用户审定、合并后自行打新的 harness tag（拟 harness-v1.2）。
