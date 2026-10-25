# T25 立刻要修的流程缺口

- 状态：已完成，待协调验收（2026-10-25）
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


## 执行记录（2026-10-25）

### 产出

- `templates/claude-settings.blind.json`：卡自身 clone 的 `semantic/tuning/`、`reports/tuning/` 同时加入 permissions 与 sandbox 禁读。
- `scripts/verify-isolation.md`：新增 A13，要求 Read 工具和 shell 均验证调优目录不可读。
- `tests/test_repo_layout.py`：检查两个调优目录的双层规则。
- `tests/test_harness.py`、`tests/test_harness_e2e_bank.py`：指定四个测试对 PermissionError / FileNotFoundError 使用固定文本跳过，不输出异常内容；阶梯文本比较只断言布尔结果，避免失败输出题面。补访问失败回归测试。
- `harness/run_direct.py`、`harness/run_agent.py`、`harness/run_plan.py`：预算检查移到 dry-run 返回之前，超限退出 2；阶梯、DAX 共用直答入口。预算回归覆盖直答、阶梯、探查、规划，以及无预算、超限、相等、充足四种边界。
- `tasks/BOARD.md`、本卡：登记状态与验收事项。

### 验证

- 可复现命令：`UV_CACHE_DIR="$TMPDIR/uvcache" uv run pytest`。
- 最终代码串行全量：1070 passed、6 skipped、109 warnings，148.20 秒；无失败。
- `git diff --check` 通过；模板变量替换后的 JSON 自检确认两个目录双层禁读。该自检不代替协调会话独立验收或真实盲模式隔离实测。
- 未调用付费模型，费用 0；未改系统提示、评分器、语义层或 `.claude/settings.json`。

### 偏离与理由

- clone 无虚拟环境，临时缓存缺依赖且沙箱内 DNS 不通；获执行环境放行后按锁文件安装既有依赖，未新增依赖或修改锁文件。
- 曾误将相关测试与全量测试重叠启动，导致共享 chDB 数据目录锁冲突，出现 22 failed。该次不作为验收依据；后续串行完成全量验证，不修改数据或执行器来掩盖此错误。

### 用户确认

- [ ] 协调会话审 diff，并独立渲染盲模式模板核对。
- [ ] 用户审阅并合并 PR。

### 工时

- 本会话完成，未精确计时；单次全量测试约 2–3 分钟。
