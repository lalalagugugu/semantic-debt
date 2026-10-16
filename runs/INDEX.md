# 运行索引

每个 run 目录一行，只追加。重跑必须新开 run 目录并在这里写明原因（硬规则 7）。

| run-id | 日期 | 单元 | 卡 | 题数 | 模型版本 | 题库提交号 | 费用（元） | 原始响应目录 | 原因 / 备注 |
|---|---|---|---|---|---|---|---|---|---|
| 20261016-T11-smoke-01 | 2026-10-16 | SQL-L1 | T11 | 2（Q02、Q101）× 3 次 | deepseek-flash | eval@4f13cb7 | 0.10 | $SEMDEBT_DATA_DIR/runs-raw/20261016-T11-smoke-01 | T11 冒烟测试。Q02 r2 首次落成 `harness_error`（读响应时 SSLError，未进退避），修客户端后用同一 run-id 续跑补齐，原行保留 |
| 20261016-T11-smoke-01-rescore-01 | 2026-10-16 | SQL-L1 | T11 | 同上 6 次作答 | deepseek-flash（源运行） | eval@491ef16（origin/main） | 0 | 沿用 $SEMDEBT_DATA_DIR/runs-raw/20261016-T11-smoke-01 | **离线重评，无模型调用**：题库补齐 `rules`（题库 #10）后，用源运行 runs-raw 里的执行结果按当前题库重评（`uv run python -m harness.rescore --source 20261016-T11-smoke-01 --cell SQL-L1 --run-id 20261016-T11-smoke-01-rescore-01`）。Q02 三次由 `pending: no_rules` 变为 `correct`；Q101 不变。核对过 Q02、Q101 在 4f13cb7 与 491ef16 之间题干、SQL、参考 CSV 都未变。源运行不完整的那行 `harness_error` 不带入 |

<!-- 追加格式：
| 20261101-SQL-L1-01 | 2026-11-01 | SQL-L1 | T13 | 120 | deepseek-… | eval@a1b2c3d | 12.3 | $SEMDEBT_DATA_DIR/runs-raw/20261101-SQL-L1-01 | 首跑 |
-->

字段说明：

- `run-id`：`<日期>-<单元>-<序号>`，与 `runs/<run-id>/` 目录同名。
- 模型版本：接口返回的版本字符串，不是请求里写的名字。
- 题库提交号：运行时 `$SEMDEBT_EVAL_DIR` 的 `git rev-parse --short HEAD`。
- 原始响应目录：只记路径；里面的内容不入库，日志里记哈希。
