# T25 立刻要修的流程缺口

- 状态：未开始
- 负责：Codex
- 模式：codex-main
- 依据：`decisions/2026-10-25-no-full-rerun-l1plus-last.md`；T14 dry-run 报告（2026-10-25）；T22 自检（#164 正文）
- 预算：0

1. **盲模式禁读调优文件**：#163 把 `semantic/tuning/` 与 `reports/tuning/` 带进主线，里面有调优题信息。`templates/claude-settings.blind.json` 对卡自己的 clone 禁读这两个目录（permissions 与 sandbox 两层，写法同 `harness/syntax_ladder/clickhouse_sql_t4.md` 那条）；`tests/test_repo_layout.py` 加模板测试；`scripts/verify-isolation.md` 补一条。
2. **4 个测试缺跳过保护**：题库或 `syntax_ladder` 读不到时应跳过而不是报 `PermissionError`：`test_dry_run_matches_board_unit_list`、`test_mock_end_to_end_real_questions`、`test_ladder_cells_change_only_the_syntax_note_and_nest`、`test_dry_run_counts_each_cells_own_questions`。失败信息不得打印题面。
3. **dry-run 也检查预算**：`harness/run_direct.py` 在 `--dry-run` 时先返回、不检查 `--budget`。改成 dry-run 也比较预估与预算，超出就以非零退出并说明；其他运行入口（探查 agent、阶梯）同样检查。加测试。
4. 全量测试通过；PR 正文写清每项改了什么。

## 不能做

- 不改 `.claude/settings.json`；不改系统提示、评分器、语义层。

## 验收（协调会话）

协调会话审 diff；盲模式模板改动由协调会话渲染一遍核对。
