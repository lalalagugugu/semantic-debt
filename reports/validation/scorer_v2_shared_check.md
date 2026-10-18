# T02 v2 第十二节共用用例验证

仅运行只读的 T05b 数据文件，未导入或读取独立检查器代码。eval-v1.2 正式复验已完成，见 `scorer_v2_check.md`。

- 共 193 条；判定 / 原因差异 0 条。
- 任一侧 unscored 单列 1 条；不计入分歧（第十二节第 7 条）。
- 输入 SHA256：`a49b5deb557db4dbfc94b4c881132ca6e7328c79b313039155d4779e93a6a576`；验证前后文件哈希一致。
- 评分器 SHA256：`d2e85ef14d4d5e9c3f153794c08941e32f907cd49ed194c2721297885e25a305`。
- 逐条耗时及预期 / 实际结果：`scorer_v2_independent.jsonl`。

## 最慢 10 条

| 用例 | 秒 | 上限 | 判定 |
|---|---:|---:|---|
| t05b/stress/rows200000-one-value-wrong | 15.174905 | 30 | wrong |
| t05b/stress/rows200000-all-values-wrong | 12.364258 | 30 | wrong |
| t05b/stress/rows50000-one-value-wrong | 3.368055 | 30 | wrong |
| t05b/stress/rows50000-all-values-wrong | 2.601515 | 30 | wrong |
| t05b/stress/rows200000-correct-shuffled | 1.016776 | 30 | correct |
| t05b/stress/identical-columns-wrong-cap | 0.656476 | 2 | unscored |
| t05b/stress/wide24-shuffled-correct | 0.515580 | 2 | correct |
| t05b/stress/wide24-one-cell-wrong | 0.507454 | 2 | wrong |
| t05b/stress/rows5000-one-value-wrong | 0.256331 | 2 | wrong |
| t05b/stress/rows50000-correct-shuffled | 0.225393 | 30 | correct |

## 判定 / 原因差异

| 用例 | 预期 | 实际 |
|---|---|---|

## unscored 单列

| 用例 | 预期 | 实际 |
|---|---|---|
| t05b/stress/identical-columns-wrong-cap | unscored | unscored |

## 回归与复现

- 第十二节全量回归：556 passed，109 条旧评分器兼容 warning，67.92 秒。覆盖作者合成、万行 / 二百万行耗时、193 条共用用例及旧评分器回归。
- 追加报告脱敏回归后：`tests/test_scorer_v2.py` 171 passed（0.57 秒）；上表的 193 条共用用例再由 CLI 完整运行，零差异。
- 二百万行作者测试的 pytest 整项耗时（含数据构造）为正确 5.66 秒、错误 21.73 秒；测试内部对判分本身分别断言 ≤30 秒。
- 旧 `harness/scorer.py` 未改，`harness/prompt.py` 与 `harness-v1` 逐字节一致的测试通过。

```sh
SEMDEBT_DATA_DIR=<数据目录> .venv/bin/python -m pytest \
  tests/test_scorer_v2.py tests/test_scorer_v2_performance.py \
  tests/test_scorer_v2_shared.py tests/test_scorer.py \
  tests/test_scorer_presentation.py tests/test_selection.py --durations=15

.venv/bin/python scripts/validate_scorer_v2.py \
  --shared "$SEMDEBT_DATA_DIR/scorer-corpus/t05b-cases.jsonl" \
  --output reports/validation/scorer_v2_independent.jsonl \
  --report reports/validation/scorer_v2_shared_check.md
```

真实对账命令默认要求 eval-v1.2 的 `bank`；正式三份语料结果见 `scorer_v2_check.md`。独立检查器在真实语料上的最终一致性验收仍由 T05b 执行。

## 第十二节覆盖

| 条款 | 正反例覆盖 |
|---|---|
| 12.1–2 换算范围与整数精确 | `test_v12_percentage_scope_and_integer_guard`、`test_v12_amount_and_count_never_scale`、`test_v12_integer_types_exact_in_all_units`，含两个换算方向 |
| 12.3 必填和未知字段 | `test_v12_additional_required_fields`、`test_v12_unknown_rules_rejected` |
| 12.4 where 必答与身份精确 | `test_v12_where_columns_required_and_literal_membership`、`test_v12_selection_float_identity_never_uses_tolerance` |
| 12.5 Top-N 完整边界与短域 | `test_v12_top_n_short_domain_and_malformed_boundary`、共用 `top-n-not-prefix-boundary` / `domain-smaller-than-n` |
| 12.6 原因码 | `test_v12_reason_first_reference_and_farthest_correspondence`、共用名次及 selection 反例 |
| 12.7 unscored 对账 | 作者 cap 正反例；共用数据及报告均按任一侧 cap 单列，不计分歧 |
| 12.8 身份拼接、NULL 与排除角色 | `test_v12_selection_names_merge_as_exact_identity_in_both_orders`、`test_v12_names_never_merge_exact_roles`、共用成对列拼接反例及 NULL 用例 |
| 12.9–10 空标签与日期 | `test_v12_only_string_empty_labels_and_empty_to_null`、`test_v12_empty_string_label_accepts_date_spelling_but_not_native_date`、`test_zero_fractional_midnight_and_timezone_rejection`、`test_v12_date_equivalence_survives_optional_top_n_matching` |
| 12.11 多计数与任意位置零行 | `test_v12_multiple_zero_counts_and_nonzero_rank_exception`、`test_v12_ordered_zero_rows_at_any_position` |
| 12.12 名次 | `test_v12_nonprefix_position_ranks_allow_gaps_but_not_duplicates`、整份 / 分组统一模式测试及共用数据 |
| 12.13 成对投影 | `test_v12_pair_projection_swaps_only_both_required_positions`、共用 `swapped-some-rows` |
| 12.14 边角输入、Array / Tuple | `test_v12_empty_reference_bool_and_structured_cells`、共用数组及不等宽反例 |
| 12.15 精确身份 | `test_v12_selection_float_identity_never_uses_tolerance`、原有编码和分组身份正反例 |

另有 `test_v12_overlapping_numeric_windows_keep_optional_boundary_edges`、`test_v12_real_reconciliation_requires_the_reexported_bank`、`test_v12_report_does_not_commit_execution_error_sql` 分别保护数值建边、正式语料版本和报告脱敏。

## 本轮修改文件

- 实现 / 验证：`harness/scorer_v2.py`、`scripts/validate_scorer_v2.py`。
- 测试：`tests/test_scorer_v2.py`、`tests/test_scorer_v2_shared.py`。
- 结果：`reports/validation/scorer_v2_shared_check.md`、`scorer_v2_independent.jsonl`、`scorer_v2_blockers.md`。
- 历史报告标识 / 脱敏：`reports/validation/scorer_v2_check.md`、`scorer_v2_cases.jsonl`。
- 状态：`decisions/open-questions.md`、`tasks/BOARD.md`、`tasks/T02-scorer.md`。

历史执行错误诊断已从最新工作树改为状态及 SHA256，当前报告不存原文；原始错误由库外语料保留。用户已授权并完成草稿分支历史清理，审计范围及继承基线说明见 `scorer_v2_check.md`。

本轮复跑：193 条共用用例及 8 项作者压力测试合计 201 passed（70.49 秒）；最新作者测试 173 passed。此前单独 CLI 逐条耗时保留于上表，评分核心未变。
