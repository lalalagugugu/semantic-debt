# 运行索引

每个 run 目录一行，只追加。重跑必须新开 run 目录并在这里写明原因（硬规则 7）。

| run-id | 日期 | 单元 | 卡 | 题数 | 模型版本 | 题库提交号 | 费用（元） | 原始响应目录 | 原因 / 备注 |
|---|---|---|---|---|---|---|---|---|---|
| 20261016-T11-smoke-01 | 2026-10-16 | SQL-L1 | T11 | 2（Q02、Q101）× 3 次 | deepseek-flash | eval@4f13cb7 | 0.10 | $SEMDEBT_DATA_DIR/runs-raw/20261016-T11-smoke-01 | T11 冒烟测试。Q02 r2 首次落成 `harness_error`（读响应时 SSLError，未进退避），修客户端后用同一 run-id 续跑补齐，原行保留 |
| 20261016-T11-smoke-01-rescore-01 | 2026-10-16 | SQL-L1 | T11 | 同上 6 次作答 | deepseek-flash（源运行） | eval@491ef16（origin/main） | 0 | 沿用 $SEMDEBT_DATA_DIR/runs-raw/20261016-T11-smoke-01 | **离线重评，无模型调用**：题库补齐 `rules`（题库 #10）后，用源运行 runs-raw 里的执行结果按当前题库重评（`uv run python -m harness.rescore --source 20261016-T11-smoke-01 --cell SQL-L1 --run-id 20261016-T11-smoke-01-rescore-01`）。Q02 三次由 `pending: no_rules` 变为 `correct`；Q101 不变。核对过 Q02、Q101 在 4f13cb7 与 491ef16 之间题干、SQL、参考 CSV 都未变。源运行不完整的那行 `harness_error` 不带入 |
| 20261017-T11-smoke-1017-01 | 2026-10-17 | SQL-L1 | T11 | 2（Q02、Q101）× 3 次 | deepseek-flash（接口原样返回别名；`system_fingerprint` e72d3c7f…，旧冒烟为 aeb56401…；官方价格页称当前指向 DeepSeek-V4.1-Flash-1017） | eval@bf8e095（origin/main 只读 worktree） | 0.10 | $SEMDEBT_DATA_DIR/runs-raw/20261017-T11-smoke-1017-01 | deepseek-flash 换为 1017 后的复测。设置与 20261016-T11-smoke-01 相同（同 2 题、每题 3 次、并发 2、系统提示 sha256 相同 b31a67b8…），周六错峰。6/6 正确，8 次调用（Q02 两次首答把中文别名写成未加引号的标识符，报语法错，修一次后正确） |
| 20261018-T12-pilot-flash-01 | 2026-10-18 | SQL-R、SQL-L1 | T12 | 24（`questions/pilot.yaml`）× 3 次 | deepseek-flash（`system_fingerprint` e72d3c7f663d3e1383b00b3884cb4501，163 次调用唯一） | eval-v1 = 07dca9a（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1`，开跑前校验） | 1.29 | $SEMDEBT_DATA_DIR/runs-raw/20261018-T12-pilot-flash-01 | T12 试跑选模型。周日错峰。144/144 done，并发 8，首个调用单独预热。语义层 semantic-v1.1 渲染（上下文与 tag 逐字节一致） |
| 20261018-T12-pilot-pro-01 | 2026-10-18 | SQL-R、SQL-L1 | T12 | 24 × 3 次 | deepseek-v4-pro（`system_fingerprint` a307abda487cd1b463329ccb945ce396，153 次调用唯一） | eval-v1 = 07dca9a | 9.62 | $SEMDEBT_DATA_DIR/runs-raw/20261018-T12-pilot-pro-01 | T12 试跑选模型。同一 run-id 第一次启动后被用户叫停（要求先看 Flash 结果）：日志与 runs-raw 均为空，但 SQL-R 首个调用很可能已发出并计费（第二次启动时 SQL-R 无冷启动，前缀已在缓存里），约 0.02 元未计入本行。第二次启动 144/144 done |
| 20261018-T12-cache-flash-01 | 2026-10-18 | SQL-L1（前缀） | T12 | 0（不含题目；固定测试消息） | deepseek-flash | — | 见报告 | $SEMDEBT_DATA_DIR/runs-raw/20261018-T12-cache-flash-01 | 缓存过期时间窗探测（`harness/cache_probe.py`）：7 个间隔 10 秒～4 小时，每个间隔一份独立前缀，预热一次、隔 d 秒再调一次。日志 `cache-probe.jsonl` |
| 20261018-T12-pilot-flash-01-rescore-01 | 2026-10-18 | SQL-R、SQL-L1 | T12 | 源运行全部 144 条作答 | deepseek-flash（源运行） | eval-v1.1 = 938957f（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.1`，开跑前校验） | 0 | 沿用 $SEMDEBT_DATA_DIR/runs-raw/20261018-T12-pilot-flash-01 | **离线重评，无模型调用**：G3 选模型用的最终重评。`uv run python -m harness.rescore --source 20261018-T12-pilot-flash-01 --cell <单元> --run-id 20261018-T12-pilot-flash-01-rescore-01 --eval-tag eval-v1.1 --allow-changed-question`，harness fd71816，评分器 main ea90587（含 #91）。Q69 题面在 eval-v1.1 改过，它的 6 条用显式开关评分、行内标 `question_changed`（开关只用于 Q69）。报告 `reports/T12-pilot.md` 开头一节 |
| 20261018-T12-pilot-pro-01-rescore-01 | 2026-10-18 | SQL-R、SQL-L1 | T12 | 源运行全部 144 条作答 | deepseek-v4-pro（源运行） | eval-v1.1 = 938957f | 0 | 沿用 $SEMDEBT_DATA_DIR/runs-raw/20261018-T12-pilot-pro-01 | 同上（Pro）。Q69 的 6 条同样标 `question_changed` |
| 20261018-T13-sql-direct-01 | 2026-10-18 | SQL-L0、SQL-R、SQL-L1、SQL-L1c、SQL-L1.5W、SQL-L1.5S | T13 | 122 × 3 次 × 6 单元 = 2,196 | deepseek-flash（`system_fingerprint` e72d3c7f663d3e1383b00b3884cb4501，2,729 次调用唯一，与 G3 一致） | eval-v1.1 = 938957f（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.1`，开跑前校验）；semantic-v1.2 = 4cf56a8 | 24.80 | $SEMDEBT_DATA_DIR/runs-raw/20261018-T13-sql-direct-01 | T13 SQL 直答全量。一个 run-id，三次启动：(1) 18:34 起 6 单元，harness `6516fcc`（harness-v1）；SQL-L0 跑完后应用户要求暂停（停在 SQL-R 首个调用之后：Q01 r1 已记一行；随后并发的至多 8 个调用可能已计费未记，至多约 0.04 元，未计入本行）。(2) 19:21 续跑 SQL-R 起 5 单元，仍为 `6516fcc`；19:39 卡在 SQL-R 的 Q79（冻结评分器的敏感性诊断在 42 家并列上指数级搜索），用户决定停下，确认无在途调用后停进程，chDB 已释放。SQL-R 的 Q79 r1–r3 用 `--backfill-from-raw` 从 runs-raw 补写（不重新调用模型，harness `66b5e7a`，行内 `backfilled_from_raw`）。(3) 21:37 续跑 SQL-L1、SQL-L1c、SQL-L1.5W、SQL-L1.5S，harness `f8da6ab`（PR #100：打分放子进程、限时 10 秒，超时记 pending/score_timeout；系统提示与评分器与 harness-v1 逐字节相同）。各单元提交：SQL-L0 `6516fcc`；SQL-R `6516fcc`（363）+ `66b5e7a`（3）；其余 `f8da6ab`。换单元 5 次，每单元首个调用单独预热。score_timeout 5 条（SQL-R Q79 ×3、SQL-L1 Q79 r2、SQL-L1.5W Q79 r3），待 harness-v1.1 离线重评。日志里的判定是运行时 harness-v1 的当场判定，暂定；最终数字以 harness-v1.1 离线重评为准（decisions/2026-10-18-harness-v1-1-scorer-fixes.md）。报告 `reports/results/sql_direct.md`、`reports/results/T13-L0-failures.md` |

<!-- 追加格式：
| 20261101-SQL-L1-01 | 2026-11-01 | SQL-L1 | T13 | 120 | deepseek-… | eval@a1b2c3d | 12.3 | $SEMDEBT_DATA_DIR/runs-raw/20261101-SQL-L1-01 | 首跑 |
-->

字段说明：

- `run-id`：`<日期>-<单元>-<序号>`，与 `runs/<run-id>/` 目录同名。
- 模型版本：接口返回的版本字符串，不是请求里写的名字。
- 题库提交号：运行时 `$SEMDEBT_EVAL_DIR` 的 `git rev-parse --short HEAD`。
- 原始响应目录：只记路径；里面的内容不入库，日志里记哈希。
