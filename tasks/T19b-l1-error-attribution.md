# T19b SQL-L1 失败归类（中期报告用）

- 状态：进行中：第 1–6 步完成（Flash 初判、Codex 独立复核 `06f4b43`、报告 `reports/results/l1-error-attribution.md`）；待用户抽检第 7 节的 10 条分歧条目，根因 5 清单待交题库负责方
- 负责：Claude Code（T13 会话）初判；Codex 独立全量复核；用户抽检
- 模式：普通
- 依据：`decisions/2026-10-20-l1-error-attribution.md`
- 依赖：`harness-v1.1`、`eval-v1.2`；源运行 `20261018-T13-sql-direct-01-rescore-01`（SQL-L1 最终判定）
- 预算：3 元（`deepseek-flash`，错峰；先 dry-run，用户批准后跑）

## 目标

回答「SQL-L1 剩下的错误，有多少是模型读错题、多少是文档没写」，给中期报告的「不用等模型」一节提供证据（C8）。

## 范围

SQL-L1 最终判定里所有非 `correct` 的作答（错答、执行失败、拒答），judge 题除外，含低区分度。每次作答单独归类（同一题三次可能错法不同）。条数在 dry-run 里报出（预计约 117 条）。

## 步骤

1. **编码手册**：写 `reports/attribution/codebook.md`，定义设计里的 10 个类别（选错表或字段、路径错、口径错、筛选错、粒度错、语法错、接口表达不了、汇总层未覆盖、读错问题、拒答）、「已声明假设」标记、5 个根因（见裁决第 3 条），每个给判定标准和边界，不举任何真题的例子。
2. **提示词**：一份固定提示词，输入只有题面、L1 上下文（与 SQL-L1 运行时的 `build/contexts/SQL-L1.yaml` 相同）、参考 SQL 与参考结果前若干行、作答的最终 SQL 与结果前若干行（执行失败给报错）、评分器 `reason`。**不给原作答的思考内容。** 输出 JSON：`category`、`declared_assumption`、`root_cause`、`doc_evidence`（L1 上下文中的原文位置，或「未找到」）、`note`（一句话，不复述题面）。不按题调；第一次付费调用之后提示词不再改，sha256 记入日志。
3. **脚本**：`--dry-run` 报条数、调用次数与预计费用；`--budget` 闸；记录接口返回的模型与指纹（应为 e72d3c7f…，不符即停）；思考模式开启、不设 temperature；JSON 解析失败如实记为 `unparsed`，不静默重试。日志写 `runs/20261020-T19b-attrib-01/`（只含题号与标签），原始响应放 `$SEMDEBT_DATA_DIR/runs-raw/20261020-T19b-attrib-01/`，`runs/INDEX.md` 记一行。
4. **运行**：用户批准预算后错峰运行（工作日 12:00–14:00 或 18:00 之后）。
5. **Codex 复核**：把编码手册和条目清单（题号、次数）交给 Codex，由它不看 Flash 结果、独立给全部条目归类，输出同格式的 CSV。
6. **汇总**：`reports/results/l1-error-attribution.md`：
   - 类别 × 根因的交叉表（Flash、Codex 各一张）；
   - 两家一致率（类别、根因各算原始一致率与 Cohen's κ）；
   - 根因 3 的占比：两家都判为 3（下限）、至少一家判为 3（上限）；
   - 按语义依赖、Q 级、用户类型拆根因；
   - 根因 5 的题号清单（交题库负责方，本卡不改分）；
   - 用户抽检约 10 条分歧条目的记录。
   只写题号、次数、标签和 L1 位置，不写题面、参考 SQL 或作答 SQL。

## 验收

- 条目数与源运行的非正确作答数一致，每条都有 Flash 与 Codex 两份标签（或如实标 `unparsed`）。
- 提示词 sha256 在全部调用中唯一；指纹唯一。
- 报告可由一条命令从日志和 Codex 的 CSV 重新生成。
- 偏离（含 Flash 自评偏差这一已知局限）写在报告开头。

## 记录（完成后填写）

- 产出：`reports/attribution/codebook.md`（编码手册）、`reports/attribution/prompt.md`（固定提示词）、`harness/attribute_l1.py`（`--dry-run` / `--budget`、指纹闸、不给思考内容、`unparsed` 不重试）、`tests/test_attribute_l1.py`；`reports/attribution/items.csv`（交 Codex 的条目清单：题号、次数，不含 Flash 结果）；`reports/attribution/codex.csv`（Codex 独立复核）；`scripts/l1_attribution_report.py` → `reports/results/l1-error-attribution.md`；`tasks/cards.yaml` 补登 T19b。
- 偏离与理由：
  - 在 T13 的 clone 里开分支，没有新建 clone（卡片负责方就是 T13 会话，T19b 未列入 cards.yaml），先例是 T13-l15s-analysis 和 C13。
  - 第 4 步在高峰时段运行（2026-10-22 16:29–16:36），没有等错峰：用户明确批准，预算上限由 3 元提到 5 元；实际 4.42 元（高峰价）。
  - 提交的日志只记标签（类别、已声明假设、根因、文档证据位置），`note` 是自由文本，只留在 runs-raw，避免复述题面进库。
- 工时：
