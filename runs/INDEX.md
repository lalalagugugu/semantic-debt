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
| 20261019-T15-pilot-01 | 2026-10-19 | SQL-L0-E、SQL-L1-E | T15 | 24（`questions/pilot.yaml`）× 1 次 | deepseek-flash（`system_fingerprint` e72d3c7f663d3e1383b00b3884cb4501，198 次调用唯一，与 G3 一致） | eval-v1.1 = 938957f（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.1`，开跑前校验）；semantic-v1.2 = 4cf56a8 | 0.67 | $SEMDEBT_DATA_DIR/runs-raw/20261019-T15-pilot-01 | T15 小样本，测步数分布（用户批准，整个小样本上限 8 元）。周一 06:50–07:15 错峰。harness `88fd81c`（`harness-agent-v1`；系统提示与 `harness-v1` 逐字节相同），`run_sql` 30 秒、最终查询 120 秒，回显 50 行，最多 8 次。48/48 done。日志里的判定是 harness-v1 评分器的当场判定，暂定；score_timeout 2 条（L1-E Q117、Q74）。发现 L0-E 用满 8 次后强制交卷有 10 条 no_query，见 `decisions/open-questions.md` T15-1 |
| 20261019-T16-pilot-01 | 2026-10-19 | SQL-L2（JSON-L2 未启动） | T16 | pilot 24 × 1，SQL 24/24 | deepseek-flash（35 次调用指纹唯一：e72d3c7f663d3e1383b00b3884cb4501） | eval-v1.1 = 938957f（只读副本校验）；semantic-v1.2 = 4cf56a8 | 0.54510072 | $SEMDEBT_DATA_DIR/runs-raw/20261019-T16-pilot-01 | 用户批准冒烟后执行；本地 harness cf7d3b5b6040affc014c5969267cb006d2cae516（main 基线 84f5e04，含 #100）；单并发、全部错峰；35 份响应及35份执行文件哈希核对通过。SQL 最终执行失败 7 条中接口限制 4 条（57.1%），按卡片 20% 门槛停止，待用户选择保留或移至第二期，JSON/全量未启动。judge 不进分母，低区分度单列；当场分数仅作进度参考，最终待 harness-v1.1 离线重评；报告 reports/results/metric_layer.md |
| 20261019-T15-pilot-l0e-02 | 2026-10-19 | SQL-L0-E | T15 | 24（`questions/pilot.yaml`）× 1 次 | deepseek-flash（`system_fingerprint` e72d3c7f663d3e1383b00b3884cb4501，107 次调用唯一，与 G3 一致） | eval-v1.1 = 938957f（只读 worktree，开跑前校验）；semantic-v1.2 = 4cf56a8 | 0.34 | $SEMDEBT_DATA_DIR/runs-raw/20261019-T15-pilot-l0e-02 | **T15-1 裁决后重跑小样本的 L0-E**（`decisions/2026-10-19-t15-1-midreport-dsh.md` 第一节）：harness `e35131f`（`harness-agent-v1.1`：用满 8 次 `run_sql` 时、强制交卷前发一条固定用户消息）。题、档位、上限与 `20261019-T15-pilot-01` 的 SQL-L0-E 相同，只差这条消息；旧运行保留不动。周一 07:43–07:48 错峰，24/24 done。判定为 harness-v1 评分器当场判定，暂定 |
| 20261019-T15-explorer-01 | 2026-10-19 | SQL-L0-E、SQL-L1-E | T15 | 122 × 3 次 × 2 单元 = 732 | deepseek-flash（`system_fingerprint` e72d3c7f663d3e1383b00b3884cb4501，2,925 次调用唯一，与 G3 一致） | eval-v1.2 = 90e13b3（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`，开跑前校验；与 eval-v1.1 题面、参考结果逐题相同，只有 Q74、Q98、Q117、Q119 的 rules 不同）；semantic-v1.2 = 4cf56a8 | 10.13 | $SEMDEBT_DATA_DIR/runs-raw/20261019-T15-explorer-01 | T15 探查 agent 全量（用户批准，上限 15 元）。周一 07:56–08:27 错峰，一次跑完、无暂停，732/732 done、无 api_error / harness_error。harness `aa7c72c`（`harness/` 与 `harness-agent-v1.1` = e35131f 相同；系统提示与 `harness-v1` 逐字节相同），`run_sql` 30 秒、最终查询 120 秒，回显 50 行，最多 8 次，用满时发「次数已用完」。并发 8，每单元首个调用单独预热。日志里的判定是 harness-v1 评分器的当场判定，暂定，最终以 harness-v1.1 离线重评为准；score_timeout 10 条（L0-E 8、L1-E 2）。SQL-L2-E 等 T16 |
| 20261018-T13-sql-direct-01-rescore-01 | 2026-10-19 | SQL-L0、SQL-R、SQL-L1、SQL-L1c、SQL-L1.5W、SQL-L1.5S | T13 | 源运行全部 2,196 条作答 | deepseek-flash（源运行） | eval-v1.2 = 90e13b3（tag 对象 40cddb0；只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`，开跑前校验） | 0 | 沿用 $SEMDEBT_DATA_DIR/runs-raw/20261018-T13-sql-direct-01 | **离线重评，无模型调用、无查询执行**：用 `harness-v1.1`（tag 对象 92c4d62 → 6a23d3c，评分器 v2）按 `eval-v1.2` 重评 T13 全部 6 单元，作为最终判定；原运行的当场判定是 `harness-v1` 的暂定数，且有 5 条 Q79 打分超时。`uv run python -m harness.rescore --source 20261018-T13-sql-direct-01 --cell <单元> --run-id 20261018-T13-sql-direct-01-rescore-01 --eval-tag eval-v1.2`，工作树干净（日志 `rescored_from.harness_commit` 全为 6a23d3c）。6 × 366 条齐全；score_timeout 0、unscored 0（Q79 五条已出判定，均为错）；judge 题返回行集的 213 条仍 pending（待 `judge-v1`）。相对暂定翻转 49 条（judge 题不计）：错→对 43（Q08、Q22、Q35、Q75），pending→错 5（Q79），对→错 1（SQL-L1.5W Q98 r3，eval-v1.2 改了 Q98 的 `required_columns`）。题面在 eval-v1.1 与 v1.2 之间未变（`question_sha256` 全部一致）。报告 `reports/results/sql_direct.md` |
| 20261019-T15-explorer-01-rescore-01 | 2026-10-19 | SQL-L0-E、SQL-L1-E | T15 | 源运行全部 732 条作答 | deepseek-flash（源运行） | eval-v1.2 = 90e13b3（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`，开跑前校验） | 0 | 沿用 $SEMDEBT_DATA_DIR/runs-raw/20261019-T15-explorer-01 | **离线重评，无模型调用**：`harness-v1.1`（6a23d3c，评分器 v2）。`uv run python -m harness.rescore --source 20261019-T15-explorer-01 --cell <单元> --run-id 20261019-T15-explorer-01-rescore-01 --eval-tag eval-v1.2`。题面与源运行相同（同为 eval-v1.2），无 `question_changed`。源运行的 10 条 score_timeout 全部得到判定；只剩 judge 题 pending（L0-E 38、L1-E 39）。L0-E 对 122→129，L1-E 211→217。rescore.py 补了 -E 单元的查表（只改单元查找，不改评分） |
| 20261019-T21-pilot-01 | 2026-10-19 | SQL-L0-P、SQL-L1-P | T21 | 48（试跑 24 题 × 1 次 × 2） | deepseek-flash（指纹 e72d3c7f…，唯一） | eval-v1.2 = 90e13b3（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`） | 1.18 | $SEMDEBT_DATA_DIR/runs-raw/20261019-T21-pilot-01 | 首跑：`harness-plan-v1`（b10ca1a），scorer v2；错峰 12:00–12:08 |
| 20261019-T16-pilot-v13-02 | 2026-10-19 | SQL-L2、JSON-L2 | T16 | 各23 × 1（pilot跳过judge Q40） | deepseek-flash，固定指纹e72d3c7f… | eval-v1.2 = 90e13b3；semantic-v1.3 = d2801b1 | 预算高峰合计≤3元，结果待追加 | $SEMDEBT_DATA_DIR/runs-raw/20261019-T16-pilot-v13-02 | **用户批准高峰执行**，仅此次冒烟，不含全量；--allow-peak、单并发、按单元依次跑；授权见本目录authorization.json；完整行集存外部runs-raw；指纹不符即停 |
| 20261019-T16-pilot-v13-02 | 2026-10-19 | SQL-L2、JSON-L2 | T16 | 46/46；各23×1，跳过judge | deepseek-flash，55次指纹均e72d3c7f… | eval-v1.2=90e13b3；semantic-v1.3=d2801b1 | 1.41452904（SQL0.98173872，JSON0.43279032） | $SEMDEBT_DATA_DIR/runs-raw/20261019-T16-pilot-v13-02 | （完成记录）**用户批准高峰执行**；本地commit22b6100；--allow-peak、单并发、SQL后JSON；55响应/45执行文件哈希及完整行数验证通过。SQL 13对6错4执行失败，JSON 6对6错10拒答1执行失败；主表/低区分度另列。SQL归因1条待定，尚不判通过，不估全量 |
| 20261019-T16-pilot-v13-02-rescore-01 | 2026-10-19 | SQL-L2、JSON-L2 | T16 | 源运行46条 | 无模型调用 | eval-v1.2=90e13b3 | 0 | 沿用 $SEMDEBT_DATA_DIR/runs-raw/20261019-T16-pilot-v13-02 | 首次v2离线重评；发现JSON Decimal字符串未按number注解恢复，4条误降；日志保留、不可用于最终分数，后续采用rescore-02 |
| 20261019-T16-pilot-v13-02-rescore-02 | 2026-10-19 | SQL-L2、JSON-L2 | T16 | 源运行46条 | 无模型调用 | eval-v1.2=90e13b3 | 0 | 沿用 $SEMDEBT_DATA_DIR/runs-raw/20261019-T16-pilot-v13-02 | commit c709ca5修复harness/rescore.py数值类型恢复，评分器v2不变；结果与运行时一致，无pending、无题面变更；主表SQL10/19、JSON5/19，低区分度SQL3/4、JSON1/4 |
| 20261019-T15-explorer-l2e-01 | 2026-10-19 | SQL-L2-E | T15 | 计划 109 × 3 = 327（跳过 judge 13 题），**中止于 7 条** | deepseek-flash | eval-v1.2 = 90e13b3（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`，开跑前校验）；semantic-v1.4 = 234ad68 | 0.07 | $SEMDEBT_DATA_DIR/runs-raw/20261019-T15-explorer-l2e-01 | **作废，不计入结果**。T15 SQL-L2-E 全量（用户批准，上限 10 元），23:23 错峰开跑，harness `6a76eec`（含 #145 `--skip-judge`），`harness-agent-v1.1`。开跑约 1 分钟后手动停止：7 条作答、22 次 `run_sql` 与全部最终查询都是 `transport_error`「Cube SQL connection failed.」。原因是本会话的沙箱不允许连 127.0.0.1:15432（psycopg：`Operation not permitted`），不是 Cube 服务的问题；模型拿不到任何执行结果，这 7 条不是有效判定。按「Cube 连续报错就停下」处理，没有重试。需要用户放开沙箱对本地 Cube 端口的访问后，另开新 run 目录重跑 |
| 20261019-T13-l15s-v14-01 | 2026-10-19 | SQL-L1.5S | T13 | 109（主表跳过 judge 13 题）× 3 次 | deepseek-flash（`system_fingerprint` e72d3c7f663d3e1383b00b3884cb4501，446 次调用唯一） | eval-v1.2 = 90e13b3（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`，开跑前校验） | 2.70 | $SEMDEBT_DATA_DIR/runs-raw/20261019-T13-l15s-v14-01 | **重跑 SQL-L1.5S**：semantic-v1.4（234ad68）给汇总表说明补了约定 1、2、6，按 #142 的裁决重跑；main 234ad68（harness-v1.1 的评分器 v2，L1.5S 的系统提示与语法文件未变），`--skip-judge --reps 3 --budget 5`，错峰 23:28 起；327 条全部 done，无 pending。修复前后对比见 `reports/results/l15s-covered-analysis.md` |
| 20261019-C13-ladder-01 | 2026-10-19 | SQL-L1-T2 | C13 | 作废的启动：327 作答中记了 13 行（1 done、12 harness_error） | deepseek-flash | eval-v1.2 = 90e13b3（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`） | 约 0.014（6 次调用；harness_error 行未记费用，按 runs-raw 的 usage 估） | $SEMDEBT_DATA_DIR/runs-raw/20261019-C13-ladder-01 | **启动失败，已停**（23:23，约 1 分钟）。T13 当时在跑 L1.5S，占着默认的 `$SEMDEBT_DATA_DIR/chdb`，所以本卡用从 Parquet 另建的 `chdb-c13`（`data/build_chdb_copy.py`），由包装脚本 `scripts/c13_run_on_chdb_copy.py` 改执行器的数据目录，不改 harness。第一版包装脚本没有 `if __name__ == "__main__"`：评分子进程用 spawn 启动，会重新导入主模块，于是每个子进程又启动了一次 `run_direct`，在 `chdb-c13` 上撞锁（`Cannot lock file …/chdb-c13/status`），作答记成 harness_error。T13 的目录没有被打开（子进程同样走了包装脚本里改过的路径）。发现后立即停进程，确认 `chdb-c13` 的锁已释放；这 13 行不计入结果，原样保留 |
| 20261019-C13-ladder-02 | 2026-10-19 | SQL-L1-T2、SQL-L1-T3、SQL-L1-T4 | C13 | T2、T3 各 109 题（judge 除外）、T4 55 道留出题，× 3 次 = 819 | deepseek-flash（`system_fingerprint` e72d3c7f663d3e1383b00b3884cb4501，844 次调用唯一，与 G3 一致） | eval-v1.2 = 90e13b3（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`，开跑前校验）；semantic-v1.4 = 234ad68 | 7.17 | $SEMDEBT_DATA_DIR/runs-raw/20261019-C13-ladder-02 | C13 教学阶梯（协调会话转达用户批准，上限 15 元）。周一 23:25–23:49 错峰，一次跑完，819/819 done，无 api_error / harness_error。harness `234ad68`（`harness/` 与 `harness-ladder-v1` 相同；评分器、系统提示与 `harness-v1.1` 相同），并发 8，每单元首个调用单独预热。chDB 用 `chdb-c13`，原因见上一行；包装脚本已加 `__main__` 保护。各级系统消息 sha256 与冻结时一致：T2 edc7cc85…、T3 6a3b57d8…、T4 5722ea2d…。评分器 v2 当场判定，就是最终判定。第 1 级不重跑，沿用 `20261018-T13-sql-direct-01-rescore-01` 的 SQL-L1（系统消息 sha256 8df43ae0… 与 semantic-v1.4 下相同）。报告 `reports/results/C13-ladder.md` |
| 20261019-T16-full-v14-sql-new-01 | 2026-10-19 | SQL-L2 | T16 | 327条作答（跳过judge） | deepseek-flash，指纹e72d3c7f… | eval-v1.2=90e13b3；semantic-v1.4=234ad68 | 5.28765880 | $SEMDEBT_DATA_DIR/runs-raw/20261019-T16-full-v14-sql-new-01 | 用户已批准单元10元/总30元；新run；单并发错峰，顺序新SQL/旧SQL/JSON；运行提交a8e3777；说明semantic-v1.4；逐次计费闸；实际状态见events.jsonl  完成本单元后按用户新增第3条暂停（Q89三次CTE/CASE派生列解析失败）；后续单元零调用，待协调确认 |
| 20261019-T16-full-v14-sql-new-01-rescore-01 | 2026-10-20 | SQL-L2 | T16 | 327条作答（跳过judge） | deepseek-flash，指纹e72d3c7f… | eval-v1.2=90e13b3；semantic-v1.4=234ad68 | 0 | 沿用 $SEMDEBT_DATA_DIR/runs-raw/20261019-T16-full-v14-sql-new-01 | 冻结harness-v1.1/v2离线重评；不调用模型、不执行查询；源20261019-T16-full-v14-sql-new-01，原始行集与分数不改写 |
| 20261019-T16-full-v14-sql-old-01 | 2026-10-20 | SQL-L2-notes-v12 | T16 | 327条作答（跳过judge） | deepseek-flash，指纹e72d3c7f… | eval-v1.2=90e13b3；semantic-v1.4=234ad68 | 5.45555508 | $SEMDEBT_DATA_DIR/runs-raw/20261019-T16-full-v14-sql-old-01 | 用户已批准单元10元/总30元；新run；并发4（用户批准后续单元提至4），错峰，单元串行；运行提交dd42aba；说明semantic-v1.2；逐次计费闸；单元后审查；实际状态见events.jsonl  并发由新说明单元1调至4；完成后触发检查点1/3，暂停JSON待协调确认；全部既有冒烟核验后检查点2未触发  后获用户确认旧说明高失败率为预期对照，放行JSON；映射表见old-notes-mapping.md；用户先批准，放行事件为补记（开跑01:42:54，事件01:43:17） |
| 20261019-T16-full-v14-sql-old-01-rescore-01 | 2026-10-20 | SQL-L2-notes-v12 | T16 | 327条作答（跳过judge） | deepseek-flash，指纹e72d3c7f… | eval-v1.2=90e13b3；semantic-v1.4=234ad68 | 0 | 沿用 $SEMDEBT_DATA_DIR/runs-raw/20261019-T16-full-v14-sql-old-01 | 冻结harness-v1.1/v2离线重评；不调用模型、不执行查询；源20261019-T16-full-v14-sql-old-01，原始行集与分数不改写 |
| 20261019-T16-full-v14-json-01 | 2026-10-20 | JSON-L2 | T16 | 327条作答（跳过judge） | deepseek-flash，指纹e72d3c7f… | eval-v1.2=90e13b3；semantic-v1.4=234ad68 | 2.58393312 | $SEMDEBT_DATA_DIR/runs-raw/20261019-T16-full-v14-json-01 | 用户已批准单元10元/总30元；新run；并发4（用户批准后续单元提至4），错峰，单元串行；运行提交080e725；说明semantic-v1.4；逐次计费闸；单元后审查；实际状态见events.jsonl  用户重新批准并发4；仅覆盖表39能答题执行失败率>20%或任一Cube超时/连接错误即停；117次能答作答0执行失败、无基础设施错误，完整完成；用户先批准，放行事件为补记（开跑02:24:05，事件02:28:36） |
| 20261019-T16-full-v14-json-01-rescore-01 | 2026-10-20 | JSON-L2 | T16 | 327条作答（跳过judge） | deepseek-flash，指纹e72d3c7f… | eval-v1.2=90e13b3；semantic-v1.4=234ad68 | 0 | 沿用 $SEMDEBT_DATA_DIR/runs-raw/20261019-T16-full-v14-json-01 | 冻结harness-v1.1/v2离线重评；不调用模型、不执行查询；源20261019-T16-full-v14-json-01，原始行集与分数不改写 |
| 20261020-T15-explorer-l2e-02 | 2026-10-20 | SQL-L2-E | T15 | 计划 109 × 3 = 327（跳过 judge 13 题），**中止于 284 条**（93 题 3 次全、3 题部分） | deepseek-flash（`system_fingerprint` e72d3c7f663d3e1383b00b3884cb4501，714 次调用唯一，与 G3 一致） | eval-v1.2 = 90e13b3（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`，`--eval-dir`，开跑前校验）；semantic-v1.4 = 234ad68 | 4.70 | $SEMDEBT_DATA_DIR/runs-raw/20261020-T15-explorer-l2e-02 | T15 SQL-L2-E 重跑（用户批准，上限 10 元；l2e-01 作废后）。周二 02:43–03:10 错峰，harness `f088e04`（含 #145 `--skip-judge`、#148 `--probe-cube` / `--eval-dir`），`harness-agent-v1.1`，并发 4；开跑前 `--probe-cube` 确认 Cube 提供 25 个 cube、353 个成员，与 semantic-v1.4 渲染的模型一致。`run_sql` 30 秒、最终查询 120 秒、最多 8 次。03:10 起 Cube 拒绝连接（`Connection refused`，服务停了，不是沙箱）：Q80 r2、Q81 r1 两条因此 `transport_error`（判 exec_error，**不是有效判定**），随即手动停止；Q79 r2、Q80 r3、Q81 r2 三条在途、runs-raw 里有部分文件但没有日志行。此前 282 条不受影响：correct 191、wrong 90、exec_error 1（no_query）；`run_sql` 782 次执行里 1 次 30 秒超时（Q76 r3，模型写的重查询，同一作答里随后的查询 0.1–0.5 秒正常返回）。判定是 harness-v1.1 评分器 v2 的当场判定。剩余 43 条 + 2 条受影响的待用新 run 目录续跑 |
| 20261020-T15-explorer-l2e-03 | 2026-10-20 | SQL-L2-E | T15 | 45（`--attempts`：l2e-02 缺的 43 条 + 它的 2 条 transport_error 作废行 Q80 r2、Q81 r1；rep 编号沿用原计划） | deepseek-flash（`system_fingerprint` e72d3c7f663d3e1383b00b3884cb4501，136 次调用唯一） | eval-v1.2 = 90e13b3（`--eval-dir` 只读 worktree，开跑前校验）；semantic-v1.4 = 234ad68 | 1.10 | $SEMDEBT_DATA_DIR/runs-raw/20261020-T15-explorer-l2e-03 | T15 SQL-L2-E 续跑（用户批准的 10 元上限的余额 5.30）。周二 07:21–07:27 错峰，harness `c74d5e1`（#150 分支，加 `--attempts`），并发 4；开跑前 `--probe-cube` 确认 25 个 cube、353 个成员一致（T16 03:10 后重启了 Cube）。45/45 done：correct 21、wrong 24；`run_sql` 140 次执行，超时 0、transport_error 0。**SQL-L2-E 的完整结果 = l2e-02 去掉 Q80 r2、Q81 r1 的 282 条 + 本 run 45 条 = 327 条**，每个 (题, 次) 恰好一条：correct 212、wrong 114、exec_error 1（no_query）、拒答 0、pending 0；`run_sql` 922 次执行里超时 1 次（Q76 r3，见 l2e-02 行和卡片偏离第 3 条）、transport_error 0。三个 L2-E run 共花 5.87 元（l2e-01 0.07 作废 + l2e-02 4.70 + 本 run 1.10） |
| 20261020-T19b-attrib-01 | 2026-10-22 | SQL-L1（失败归类，非作答） | T19b | 117 条（源运行 `20261018-T13-sql-direct-01-rescore-01` 里 SQL-L1 的全部非正确作答，judge 题除外）× 1 次 | deepseek-flash（`system_fingerprint` e72d3c7f663d3e1383b00b3884cb4501，117 次调用唯一） | eval-v1.2 = 90e13b3（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`，开跑前校验） | 4.42 | $SEMDEBT_DATA_DIR/runs-raw/20261020-T19b-attrib-01 | **首跑**：`harness/attribute_l1.py`（a9c0a79），Flash 初判，T19b 第 4 步。提示词、编码手册、系统消息的 sha256 在 117 次调用中唯一（2db2825d… / cf523533… / 0f0a438a…）；117 条全部解析成功，无 `unparsed`。**高峰时段运行**（16:29–16:36）：用户明确批准不等错峰，预算上限 5 元，费用按高峰价 ×2 计。预估 3.80 元（高峰），实际 4.42 元，偏高是因为输出约 4.1k token/次（预估 3k）。日志只含题号与标签，`note` 与思考内容只在 runs-raw |
| 20261023-T19c-confidence-01 | 2026-10-23 | SQL-L1（自评把握追问，非作答） | T19c | 327（源运行 `20261018-T13-sql-direct-01-rescore-01` 里 SQL-L1 的全部非 judge 作答 109 × 3）× 1 次 | deepseek-flash（`system_fingerprint` e72d3c7f663d3e1383b00b3884cb4501，327 次调用唯一） | eval-v1.2 = 90e13b3（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`，开跑前校验） | 1.02 | $SEMDEBT_DATA_DIR/runs-raw/20261023-T19c-confidence-01 | **首跑**：`harness/confidence.py`（54793b0），T19c 第二部分，用户批准（上限 5 元）。周五 20:37–20:40 错峰，并发 8，首个调用单独预热。对话 = T13 系统消息（sha256 8df43ae0…，与源日志逐字节核对）+ 原题 + 被评分那一轮的作答原文（不含思考、不含执行结果）+ 固定追问（sha256 2788c73e…，327 条唯一）。原作答与判定不变。done 325、unparsed 2（Q105 r2、Q82 r2，JSON 不合法，未重试）、api_error 0。预估 3.69 元（按输出 2000 token/次），实际输出均值约 455 token、前缀缓存命中约 99%，故实际 1.02 元。日志只含题号、次数、档位；原因句与思考只在 runs-raw。报告 `reports/results/confidence-calibration.md` |

**注（2026-10-19，`eval_tag` 沿用源运行）**：`20261018-T13-sql-direct-01-rescore-01` 的日志行里，`eval_tag` 是源运行的标签（`eval-v1.1`），但实际按 `eval-v1.2` = 90e13b3 评分，以各行的 `eval_commit` 为准。原因是当时的 `harness.rescore` 只替换 `eval_commit`、不替换 `eval_tag`。日志只追加，这个 run 不改写。`20261019-T15-explorer-01-rescore-01` 不受影响：它的源运行本来就是 `eval-v1.2`，732 行的 `eval_tag` 都是 `eval-v1.2`，`eval_commit` 都是 90e13b3。之后的重评由修过的 `harness/rescore.py` 写入实际校验过的标签，源运行的标签另记在 `rescored_from.eval_tag`。

<!-- 追加格式：
| 20261101-SQL-L1-01 | 2026-11-01 | SQL-L1 | T13 | 120 | deepseek-… | eval@a1b2c3d | 12.3 | $SEMDEBT_DATA_DIR/runs-raw/20261101-SQL-L1-01 | 首跑 |
-->

字段说明：

- `run-id`：`<日期>-<单元>-<序号>`，与 `runs/<run-id>/` 目录同名。
- 模型版本：接口返回的版本字符串，不是请求里写的名字。
- 题库提交号：运行时 `$SEMDEBT_EVAL_DIR` 的 `git rev-parse --short HEAD`。
- 原始响应目录：只记路径；里面的内容不入库，日志里记哈希。

| 20261025-T22b-l1plus-l3a-01 | 2026-10-25 | SQL-L1plus、SQL-L3a | T22b | 计划各 109 × 3，合计 654（跳过 judge） | deepseek-flash；预期指纹 e72d3c7f663d3e1383b00b3884cb4501 | eval-v1.2=90e13b3（独立快照）；semantic-v1.6-l1plus=866004b | 运行中，用户批准上限 15 元；归因另限 3 元 | $SEMDEBT_DATA_DIR/runs-raw/20261025-T22b-l1plus-l3a-01 | 首跑，用户明确批准；正式 dry-run 14.19 元，预计 720 次调用；main=34a75dd（含 #166），周日错峰，并发 4。临时 supervisor.py 存于原始目录；逐 API 响应累计费用，费用达到上限或指纹、API、基础设施、评分异常即停止后续请求；SQL 执行报错按冻结规则修正一次，传输失败不自动重试。结束状态与实际费用另行追加，不改写本行 |
| 20261025-T22b-l1plus-l3a-01（中止补记） | 2026-10-25 | SQL-L1plus（SQL-L3a 未开始） | T22b | 0 条完成判分；Q01 r1 一条 harness_error | deepseek-flash，2 次调用指纹均 e72d3c7f663d3e1383b00b3884cb4501 | eval-v1.2=90e13b3；semantic-v1.6-l1plus=866004b | **0.03272164**（原始 usage 与 supervision.jsonl 核算；harness_error 摘要无费用，不能取其 0 元） | $SEMDEBT_DATA_DIR/runs-raw/20261025-T22b-l1plus-l3a-01 | 临时监督脚本缺 __main__ 入口保护，spawn 评分进程重复执行启动断言，触发 run-id 已使用；该异常是 Codex 包装脚本错误。首答及固定一次 SQL 修正共 2 次 API 调用，费用已计入 15 元总上限；按用户要求异常即停，未续跑。出错版本、修复版本与 incident.json 均保留外部原始目录；修复后离线 spawn 评分与预算守卫通过，等待用户确认新 run-id 重跑。无完整准确率或稳定性统计；归因费用 0 |
| 20261025-T22b-l1plus-l3a-01（追加中止说明） | 2026-10-25 | SQL-L1plus | T22b | **中止：监督脚本缺多进程入口保护，0 条判分** | deepseek-flash | eval-v1.2=90e13b3；semantic-v1.6-l1plus=866004b | 沿用前记 0.03272164 元，不重复计费 | $SEMDEBT_DATA_DIR/runs-raw/20261025-T22b-l1plus-l3a-01 | 用户要求的中止说明；旧 run 目录与外部原始目录保持不动 |
| 20261025-T22b-l1plus-l3a-02 | 2026-10-25 | SQL-L1plus、SQL-L3a | T22b | 计划各 109 × 3，合计 654（跳过 judge） | deepseek-flash；预期指纹 e72d3c7f663d3e1383b00b3884cb4501 | eval-v1.2=90e13b3（独立快照）；semantic-v1.6-l1plus=866004b | 运行中；与失败 run 合计上限 15 元（已用 0.03272164 元），归因另限 3 元 | $SEMDEBT_DATA_DIR/runs-raw/20261025-T22b-l1plus-l3a-02 | 用户批准新 run-id 重跑；正式 dry-run 14.19 元。原样运行 python -m harness.run_direct，--semantic-tag semantic-v1.6-l1plus --budget 15，并发 4；外层进程监督不导入或替换 harness，不改提示、执行、评分、重试逻辑。只读响应与日志累计费用、检查异常、管理子进程；累计达到 14.9 元即保守停止。完整系统消息哈希、版本与命令保存在 preflight.json / command.json，旧 run 文件哈希结束复核。结果另行追加 |
| 20261025-T22b-l1plus-l3a-02（中止补记） | 2026-10-25 | SQL-L1plus（SQL-L3a 未开始） | T22b | 1 条完成判分（Q01 r1 correct），其余未完成 | deepseek-flash，已返回响应指纹 e72d3c7f663d3e1383b00b3884cb4501 | eval-v1.2=90e13b3（展开完整提交号与 preflight 一致）；semantic-v1.6-l1plus=866004b；系统消息哈希一致 | 已返回响应 **0.00259616** 元；两次 run 可核算累计 **0.03531780** 元；终止时未返回的在途请求用量无法从本地确认 | $SEMDEBT_DATA_DIR/runs-raw/20261025-T22b-l1plus-l3a-02 | 中止：外层监控把日志短提交号 90e13b3 与完整提交号直接比较，误报版本不一致并终止进程；实际版本与哈希均一致，原样 harness 判分正常。监控未导入、替换或修改 harness；这次错误仍由 Codex 监控校验造成。修复已用真实日志验证长短提交号、故意不一致、系统哈希、状态、费用与子进程终止，未再付费调用。失败 run 01 的所有已有文件哈希不变；两个新目录只追加审计记录。等待用户决定，不把单条作答当成 98 / 109 题成绩 |
| 20261025-T22b-l1plus-l3a-03 | 2026-10-25 | SQL-L1plus、SQL-L3a | T22b | 计划各 109 × 3，合计 654（跳过 judge） | deepseek-flash；预期指纹 e72d3c7f663d3e1383b00b3884cb4501 | eval-v1.2=90e13b3（展开完整提交一致，独立快照）；semantic-v1.6-l1plus=866004b | 运行中；累计上限 15 元，前两次已返回响应费用 0.03531780 元，归因另限 3 元 | $SEMDEBT_DATA_DIR/runs-raw/20261025-T22b-l1plus-l3a-03 | 用户批准第三个新 run，明确要求不套自写监控脚本；直接运行原样 harness.run_direct，--semantic-tag semantic-v1.6-l1plus --budget 15 --est-from-args，并发 4，周日错峰。开跑前正式 dry-run 14.19 元、预计 720 次调用；系统消息 SHA-256 与此前一致，完整版本与哈希保存在外部 preflight.json。前两个 run 不改写；run 02 未返回在途用量若后续可确认则追加补记 |
| 20261025-T22b-l1plus-l3a-03（完成补记） | 2026-10-25 | SQL-L1plus、SQL-L3a | T22b | **654/654 done**（各 109 × 3），811 次已返回响应调用 | deepseek-flash，811 次调用指纹唯一 e72d3c7f663d3e1383b00b3884cb4501 | eval-v1.2=90e13b3；semantic-v1.6-l1plus=866004b；系统消息哈希与 preflight 一致 | **8.05898170**（L1plus 3.21187542；L3a 4.84710628）；加前两次已返回响应费用，已知累计 **8.09429950** 元 | $SEMDEBT_DATA_DIR/runs-raw/20261025-T22b-l1plus-l3a-03 | 原样 harness 正常退出；无自写监督脚本，未改提示、执行、评分或重试逻辑。5 次原生自动传输重试成功并保留；最终 API 异常、未判分、指纹冲突均 0。模型 SQL 修正后仍有 4 / 2 条 engine_error，正常计入执行失败。逐 API 原始响应哈希和 token 费用核对通过；离线重评 0 翻转。主表 98 题 L1plus 75.5%（222/294）、L3a 74.5%（219/294）；109 题 74.9%（245/327）、73.4%（240/327）。稳定性及配对区间见 reports/results/l1plus-l3a.md |
| 20261025-T22b-l1plus-l3a-03-rescore-01 | 2026-10-25 | SQL-L1plus、SQL-L3a | T22b | 654（各 327） | 无模型调用 | eval-v1.2=90e13b3；沿用源运行 semantic-v1.6-l1plus | **0** | 沿用 $SEMDEBT_DATA_DIR/runs-raw/20261025-T22b-l1plus-l3a-03 | 新目录离线重评，不执行 SQL；复用冻结 harness.rescore.rescore_line，逐执行结果哈希核对。原 rescore CLI 的注册表尚无两个新单元，由只读汇总脚本调用同一已有评分函数，不修改 harness。两单元暂定与最终判定均 0 翻转 |
| 20261025-T22b-l1plus-l3a-02（费用后查补记） | 2026-10-25 | SQL-L1plus | T22b | 沿用原中止记录 | deepseek-flash | eval-v1.2=90e13b3；semantic-v1.6-l1plus=866004b | 已确认仍为 **0.00259616** 元，不重复累计 | $SEMDEBT_DATA_DIR/runs-raw/20261025-T22b-l1plus-l3a-02 | 截至第三次运行完成，原目录仍只有一份已返回 API 响应；未发现额外 usage，终止时在途请求费用仍不能从本地确认，不作 0 元断言。以后若可核实再追加；旧日志和记录不改写 |
## T23 v3 敏感性重评：20261025-T23-v3-01

| run-id | 单元 | 来源 | 题库 | 费用 | 原因 |
|---|---|---|---|---:|---|
| 20261025-T23-v3-01 | 全部已发现 T13 / T15 / T16 / C13 / T14 / T22b 单元 | 27 份源日志，6188 条 done；逐份见 manifest.json | eval-v1.2=90e13b3 | 0 | 用户审定的 P1–P4；v2 主数字、v3 敏感性分析；只读原始执行结果，不调用模型、不执行查询；新增判对待 Claude Code 逐条复核 |

## T23 v3 敏感性重评：20261025-T23-v3-02

| run-id | 单元 | 来源 | 题库 | 费用 | 原因 |
|---|---|---|---|---:|---|
| 20261025-T23-v3-02 | 全部已发现 T13 / T15 / T16 / C13 / T14 / T22b 单元 | 27 份源日志，6188 条 done；逐份见 manifest.json | eval-v1.2=90e13b3 | 0 | 用户审定的 P1–P4；v2 主数字、v3 敏感性分析；只读原始执行结果，不调用模型、不执行查询；新增判对待 Claude Code 逐条复核 |

**T23 来源说明（追加，不改写前述运行）**：`20261025-T23-v3-01` 在进程运行期间补了输入防护，代码哈希又在结束时采集，因此该轮不作验收依据。正式结果以 `20261025-T23-v3-02` 为准：启动时固定代码哈希、结束时验证代码与源日志未变；27 份源日志 / 6,188 条 done，最终新增判对 82 条（均 P1），待跨厂商逐条复核。两轮均无模型调用、无查询执行，费用 0。本次没有发现 T22b 作答日志，不能把上述“全部已发现”误读成 T22b 已完成。
| 20261025-T14-tuned-01 | 2026-10-25 | SQL-L1-tuned、SQL-L1-tuned-instr | T14 | 109（跳过 judge 13 题；调优 54、留出 55）× 3 次 × 2 单元 = 654 | deepseek-flash（`system_fingerprint` e72d3c7f663d3e1383b00b3884cb4501，669 次调用唯一，与 G3 一致） | eval-v1.2 = 90e13b3（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`，开跑前校验）；semantic-tuned-v1 = 09f4738（#163 合并提交，开跑前校验） | 4.77 | $SEMDEBT_DATA_DIR/runs-raw/20261025-T14-tuned-01 | T14 第 1 轮调优全量（用户 2026-10-24 批准，两单元合计上限 12 元；dry-run 估 11.18）。周日 09:20 起错峰，一次跑完、无暂停，654/654 done，无 api_error / harness_error。harness 工作树 = `harness-tuned-v1`（09f4738；日志 `harness_commit` b91eccc 是同一棵树）。系统消息 sha256：SQL-L1-tuned 6ce71c76…，SQL-L1-tuned-instr 03ec10aa…（SQL-L1 仍为 8df43ae0…）。chDB 用本卡副本 `$SEMDEBT_DATA_DIR/chdb-t14`（`data/build_chdb_copy.py` 建），经包装脚本 `scripts/t14_run_on_chdb_copy.py` 只改执行器数据目录、不改 harness（硬规则 9）。评分器 v2 当场判定即最终判定。SQL-L1-tuned 269/327（0.823），SQL-L1-tuned-instr 286/327（0.875，含 1 条最终执行报错）。报告待 `reports/results/tuning.md` |


## T22b 归因启动前受阻（2026-10-25）

| 计划 run-id | 单元 | 条目 | 已调用 | 费用 | 状态 |
|---|---|---:|---:|---:|---|
| 20261025-T22b-attrib-01（尚未创建） | SQL-L1plus 残余歧义归因 | 82 / 38 题 | 0 | 0 | 用户批准 3 元及数据质量辅助标记；新 dry-run 约 2.00 元。自动审批在创建进程前要求补充私有材料向 DeepSeek 官方 API 的具体出站授权；没有 run 目录、没有原始响应，未绕过。Codex 82 条独立标签已先行冻结，Flash 尚未初判，归因未完成。 |


## T22b 五类归因正式启动（2026-10-25，追加）

| run-id | 单元 | 条目 | 预算 | 状态 |
|---|---|---:|---:|---|
| 20261025-T22b-attrib-01 | SQL-L1plus 残余歧义归因 | 82 / 38 题 | 3 元 | 用户补充明确出站授权后启动；五类 + 单列疑点，另加数据质量辅助标记；原系统消息与语义 / 题库版本及 82 条材料哈希均核对。Codex 标签先行独立冻结，Flash 串行执行，规则不改，异常即停。实际费用与完成情况待结束后追加。 |


## T22b 五类归因完成：20261025-T22b-attrib-01（追加）

| run-id | 来源 | 条目 / 调用 | 模型及版本 | 费用 | 结果 |
|---|---|---|---|---:|---|
| 20261025-T22b-attrib-01 | SQL-L1plus；20261025-T22b-l1plus-l3a-03-rescore-01 v2 非正确作答；semantic-v1.6-l1plus=866004b；eval-v1.2=90e13b385a639a9164ac78430c50c11a7859f976 | 82/82 条 / 38 题；82 次调用 | deepseek-flash；指纹 e72d3c7f663d3e1383b00b3884cb4501 唯一 | 1.72537972 元 | 用户批准归因上限 3 元并明确出站授权，周日错峰，原生归因命令、串行费用预留；无传输重试、解析失败、指纹冲突、接口异常或待核算请求。五类 + 单列及数据质量辅助标记先写卡后冻结；Codex 82 条独立标签先于 Flash 调用冻结，未改。结果 reports/results/l1plus-error-attribution.md；原始响应在 $SEMDEBT_DATA_DIR/runs-raw/20261025-T22b-attrib-01；逐原始哈希、usage 费用、材料与版本审计通过。前述启动前受阻行保留，不覆盖历史。 |

| 20261025-T28-v3-01 | 2026-10-25 | SQL-L1plus、SQL-L3a | T28 | 654（各109×3） | 无模型调用 | eval-v1.2=90e13b3 | 0 | 沿用源运行 runs-raw | T28 免费补评；复用 scripts/rescore_t23.py，逐执行结果哈希核对；不执行查询；v2 主数字、v3 敏感性；新增判对待跨厂商复核。 |
| 20261025-T30-combo-01 | 2026-10-25 | SQL-L1plus-tuned-instr | T30 | 327（109×3） | deepseek-flash；e72d3c7f663d3e1383b00b3884cb4501 | eval-v1.2=90e13b385a639a9164ac78430c50c11a7859f976 | 可核算 2.89061402；3 次未返 usage 请求费用未知 | $SEMDEBT_DATA_DIR/runs-raw/20261025-T30-combo-01 | 用户批准预算 8 元，combo tags=2f2d644，周日错峰，并发 8；私有 chdb-t30；实际回包费用守卫未触发。327/327 done，339 次有回包调用；3 次传输重试（Q49 r3、Q67 r3、Q79 r2），未把未知费用计作零。correct 282 / wrong 44 / exec_error 1（Q84 r3）；无补跑、无 API/harness 失败行或指纹异常。 |
| 20261025-T30-combo-01-rescore-01 | 2026-10-25 | SQL-L1plus-tuned-instr、SQL-L1plus、SQL-L1-tuned-instr | T30 | 981（3单元各109×3） | 无模型调用 | eval-v1.2=90e13b385a639a9164ac78430c50c11a7859f976 | 0 | 沿用源运行 runs-raw | 冻结题库，逐执行结果哈希离线 v2/v3 重评；没有 SQL 重跑。叠加单元 v2/v3 均为主表 257/294、留出 119/147，改判 0；报告 reports/results/combo.md，manifest 记录来源、代码哈希、费用、分层统计及配对区间；待协调独立验收。 |

## T29 试跑启动前受阻（追加）

| run-id | 单元 | 计划 | 费用 | 状态 |
|---|---|---|---:|---|
| 20261025-T29-pilot-01 | SQL-L1plus-sel-k1、SQL-L1plus-sel-k3 | 20道调优题×1次×两档，40次首轮作答，预计含纠错44调用、0.730892844元 | 0（未启动） | 用户已批准范围、1元停止阈值与错峰；harness-sel-v1=903c767、冻结语义和题库、B1已合并、提示/源码哈希及调优题清单均验证；25表专用chDB已从Parquet重建。自动审批在创建进程前拒绝出站调用，要求明确授权私有题面和语义上下文发送至DeepSeek官方API。没有绕过、重试或付费调用。原始目录仅含预检及受阻记录，无费用账本、响应或运行日志；待用户明确出站授权。 |

## T29 试跑完成（追加）

| run-id | 单元 | 作答 / 调用 | 费用（元） | 状态 |
|---|---|---|---:|---|
| 20261025-T29-pilot-01 | SQL-L1plus-sel-k1 | 20 / 29 | 0.14927536 | 用户补充明确出站授权后启动；周日错峰，拒答0、最终及全部调用格式错0。 |
| 20261025-T29-pilot-01 | SQL-L1plus-sel-k3 | 20 / 25 | 0.15530624 | 同上；拒答0、最终及全部调用格式错0。 |

合计40次唯一作答、54次调用、**0.30458160元**（预计0.730892844元、1元停止阈值）。DeepSeek官方API deepseek-flash，指纹e72d3c7f663d3e1383b00b3884cb4501唯一；无传输重试、API错误、指纹变化、异常状态或待核算费用。参考答案未出站。三个系统消息哈希与批准前preflight一致；harness-sel-v1=903c767，语义semantic-v1.6-l1plus=866004b、题库eval-v1.2=90e13b3均通过校验。日志903c767-dirty仅因隔离检出恢复冻结semantic/render；harness源码与tag一致。日志只追加，原始响应/执行结果/费用账本在外部runs-raw同名目录；报告`reports/validation/t29-pilot.md`，审计脚本`scripts/t29_pilot_report.py`。提示词未改，未作效果分析，正式运行及B2未启动，等用户另批。

| 20261026-T29-expanded-01 | T29 扩展试跑初次启动异常（追加，后续同run-id保留） | 外部早间时间包装器参数不兼容，169条发送前harness_error；API调用0、费用0、未结算0。全部失败日志保留，用户批准午休改用冻结原入口、原preflight续跑。报告`reports/validation/t29-expanded-startup-failure.json`。 |


## T29 扩展试跑完成（2026-10-26追加）

| run-id | 单元 | 首轮 / 含纠错调用 | 费用（元） | 状态 |
|---|---|---:|---:|---|
| 20261026-T29-expanded-01 | SQL-L1plus-confidence | 49 / 60 | 0.58129880 | 原生拒答0；缺把握最终13次，50/75/90门槛拒13/15/28 |
| 20261026-T29-expanded-01 | SQL-L1plus-sel-front-k3 | 20 / 24 | 0.30207980 | 拒答0、格式错0 |
| 20261026-T29-expanded-01 | SQL-L1plus-sel-front-k10 | 20 / 25 | 0.26918308 | 拒答0、格式错0 |
| 20261026-T29-expanded-01 | SQL-L1plus-sel-k5 | 20 / 23 | 0.13256568 | 拒答0、格式错0 |
| 20261026-T29-expanded-01 | SQL-L1plus-sel-k10 | 20 / 25 | 0.15016924 | 拒答0、格式错0 |
| 20261026-T29-expanded-01 | SQL-L1plus-sel-k20 | 20 / 27 | 0.16113680 | 拒答0、格式错0 |
| 20261026-T29-expanded-01 | SQL-L1plus-sel-k100 | 20 / 25 | 0.17213224 | 拒答0、格式错0 |

顺序C→B→A，169次首轮、209调用、合计1.76856564元；3元上限，午休原入口全部完成，账本未结算0。早间169条零调用失败日志保持原样，追加169条完成记录，原包和执行结果在外部runs-raw同名目录；公开日志移除SQL、假设、错误原文与原始把握值，manifest记录哈希。harness-sel-v2=f726f5b；运行f726f5b-dirty仅为恢复冻结semantic/render，harness、入口与preflight逐字一致。报告`reports/validation/t29-expanded.md`及audit/attempts。v2筛选无候选达标，正式仍等内容准确率口径复算、双口径裁决；结果前登记798c44a。免费D/B2已分别提交75e0ac4、23b83d4。

## 20261028-T31-v4-rescore-01：eval-v1.3 全历史离线评分（汇总待定）

只读原始日志与执行包，以 eval-v1.3=5b65e0c 和未改的评分器v2重评，并独立应用已批准R1–R11；7,379次可比deterministic历史作答，含试跑和旧版，不是正式单元分母。模型调用0、查询执行0、费用0；逐次单调性检查通过。183条启动/框架失败事件、18条旧题面不匹配、330条非deterministic记录的来源计数在manifest中保留。正式SQL-L2-E汇总须取后次完成、移除2条重复传输失败身份。本次为不可改写的评分阶段材料；汇总草稿在仓库外，15次框外残余处理待用户裁定，详见decisions/open-questions.md的T31-v4-2。后续从本评分或原日志重新聚合，最终数字仍待Claude Code跨厂商独立核对。

## 20261028-T31-v4-rescore-02：用户审定后的双口径最终汇总（待跨厂商核对）

在eval-v1.3=5b65e0c下，校验全部原日志、执行包和冻结评分代码后复用上一评分阶段，重新聚合7379次历史作答；正式SQL-L2-E按原报告取后次、剔除2条重复传输失败身份，历史记录仍保留。200次样本移入v2判对17次、规则放行3次，保留180次；15次框外已知错误按用户裁定c为0，其余只在主表19个单元内估计。109题不外推，T29不估计c。新增逐次结果、manifest和reports/results/accuracy-v4.md及CSV；单调性检查通过，模型/查询调用0、费用0。新run仅追加，不覆盖01；数字待Claude Code独立重算，通过前不进入正式报告。

| 20261030-T29-u2-01 | 2026-10-30 | SQL-L0-u2（其余三单元未启动） | T29/U2 | 1次请求、0次完成 | deepseek-flash，指纹bc19ba97…（预期e72d3c7f…） | eval-v1.3=5b65e0c | 0.006272 | $SEMDEBT_DATA_DIR/runs-raw/20261030-T29-u2-01 | 首题Q01 r1预热返回指纹不符即停，退出3；SQL未执行；1请求/1结算/0在途；原包保留，等用户裁决，不续跑、不分析 |

## U2 v2计划（2026-10-30，尚未启动）

用户T29-5将首响应指纹变化视为服务端部署变化，接受bc19ba97…但要求同指纹新基线，不与旧指纹混算。原20261030-T29-u2-01停止记录保持不动；计划新run-id `20261030-T29-u2-v2-01`，六单元按基线L0/L1、U2 L0/L1、U2p L0/L1顺序，各98×3。含已花0.006272元总上限40元，等用户审合并并打harness-u2-v2才采集；此段仅说明新run原因，不是执行记录。

| 20261030-T29-u2-v2-01 | 2026-10-30 | SQL-L0（其余五单元未启动） | T29/U2 v2 | 32次已保存作答、33回包 | deepseek-flash，已保存指纹均bc19ba97… | eval-v1.3=5b65e0c | 可核对0.15725708；总费用未决 | $SEMDEBT_DATA_DIR/runs-raw/20261030-T29-u2-v2-01 | 原样基线未接共享运行时预算保护，发现即SIGTERM（143）；最多8个逻辑调用可能在途、确切调用与费用未知，无账本；所有已保存原包完整保留，不自动续跑；分析等D1定稿 |

## U2 v2废弃与v3重采决定（用户2026-10-30）

20261030-T29-u2-v2-01已保存的32次作答因预算保护漏洞**废弃，不续用、不混算**；原始记录、公开元数据与哈希报告保留不动。#213由用户合并。用户控制台累计0.28元不等于已确认本实验结算；扣除额按max(0.28, 0.16352908已确认费用+8×0.120675单次预估)=1.12892908元，新run准入额度38.87107092元，总上限40元不变。未确认部分仍未结算、不补造账本。计划新run `20261030-T29-u2-v3-01`，从头重采六单元各98×3，等协调会话逐单元复审、用户合并和harness-u2-v3后才采集；此段是决定记录，不是已运行记录。

| 20261031-T29-u2-v3-01 | 2026-10-31 | SQL-L0（其余五单元未启动） | T29/U2 v3 | 56完成；60HTTP尝试（57首轮+3纠错） | deepseek-flash，59回包指纹均bc19ba97… | eval-v1.3=5b65e0c | 已知已结算0.63792848；另1请求费用未决 | $SEMDEBT_DATA_DIR/runs-raw/20261031-T29-u2-v3-01 | #215合并/tag ee3f0c0后从头采集；Q01 r2连接重置，按异常规则自动停发并等其余请求结算后退出3；共享账本60request/59charge、最大在途8，禁止未核对续跑；原32废弃作答未用，内容判定/分析等D1定稿 |
## 20261030-T31-v5-census-01：v7 全量判定首轮候选（已由 03 取代）

离线聚合 19 个正式单元、1,411 次主表残余首轮标签；保留候选状态供追溯。后续全表数值核验和用户追加裁决纠正标签，以 03 为最终 Codex 候选；本目录不作为正式报告输入。模型/查询调用 0，不覆盖既有日志。

## 20261030-T31-v5-census-02：v7 核验中间候选（已由 03 取代）

纳入完整明细、空姓名经理裁决和首轮数值纠正；随后补完名称／编码等价全表核验，以 03 为最终候选。保留中间目录，不用于正式报告；模型/查询调用 0。

## 20261030-T31-v5-census-03：v7 全量内容准确率（待九单元跨厂商复核）

固定 eval-v1.3=5b65e0c，沿用 v4 已核对的 v2 与 R1–R11，主表 5,439 次作答的 1,411 次残余全部逐次判定，取代抽样外推。原样本 200 次双向复查，原样本与本轮初判的变更分来源列明；15 次已知错误不放行。逐次断言准确率不低于 v2 交付率；私有标签和 D4 等价判断保存哈希及快照。另附 D4、D6、D8 及 followups-manifest。模型/查询调用 0、费用 0；完整材料仅在仓库外，九个关键单元待 Claude Code 独立复核，用户合并前不作为已验收数字。

## 20261031-T31-v5-rulings-01：PR #214 用户裁定后重算

按 2026-10-31 统一规则复扫 19 单元全部 420 次原判对残余，33 次改错、387 次保留；包含逐次裁定改错 9 次及扩扫新增 24 次，Q110 SQL-L2 第 3 次保留正确。严格核对额外组是否真为零、窗口各期间数值及已给结果是否矛盾；需多步累计不放行。旧样本 Q47 的改对撤销，按约定交付率和 R1–R11 信用不变。该目录更新 accuracy-v5 与 D4／D6：Q26 移出内容一致集合；D6 三类为 3／11／2，D8 不变。原目录及标签快照不改写；本轮完整复查账和哈希留仓库外，新增变更单列。模型 API／SQL 执行 0，费用 0；用户合并 #211 前仍作为待核数字。


## U2 v4续采决定（用户2026-10-31，尚未启动）

同run 20261031-T29-u2-v3-01保留56次done，前tag为harness-u2-v3@ee3f0c0，后tag为harness-u2-v4（待用户审PR后打并记录实际提交）；不是新run。旧日志/账本/回包留档不改，v3未结算不再阻塞续采，未确认费用不报结算。恢复T13默认传输重试、失败继续、同命令只补缺，raw及执行包编号追加不覆盖；六单元无预算账本/预留，改为每单元后日志usage加此前1.12892908元扣除核对，超过40停问用户。网络/进程退出/高峰暂停后nohup+caffeinate后台同命令自动恢复，指纹及401/402停。等协调审阅和用户新tag，本段不代表已经续采；内容判定和分析等D1定稿。

## 20261031-T29-u2-v3-01：harness-u2-v4续采完成（2026-10-31）

harness-u2-v3@ee3f0c0→harness-u2-v4@2163228；同run保留56次、新增1708次，六单元各98×3全部完成，无重复done。累计逻辑调用2114、HTTP尝试2128（完整回包2112、额外传输重试14），已知日志usage费用25.65389048元（v4新增25.01596200）；加此前扣除1.12892908元共26.78281956元，未触40元。2112回包指纹均bc19ba97…；v4一次重试耗尽api_error后包装器自动补齐，历史失败记录保留，最终退出0，未触退出6。旧账本只留档、未确认费用不报结算；原v2废弃32次未用。报告reports/validation/t29-u2-v4-collection.{md,json}；新原包和日志仍在外部原目录，公开只追加去内容元数据，内容全量判定及分析等D1定稿。

## 20261101-T32-clean-repro-SQL-L1-01：README 干净环境复现（2026-11-01）

新 clone 按 README 离线重评 SQL-L1，366 条，费用 0，未调用模型。当时 README 没有固定题库版本，用的是题库 `e17a3fa`，不是 eval-v1.3；和既有日志的差异及解释见 `reports/validation/t32-clean-repro.md`。只是复现验证，不进任何报告数字。

## 20261104-T34-ontology-full-01：预检登记，尚未付费运行

四单元 SQL-L1、SQL-L1-onto、SQL-L1plus、SQL-L3a-full，计划同一 run 各 109×3（主表只报告 98 题），原主表 SQL-L1plus 配置：deepseek-flash、并发 4、执行超时 120 秒、跳过 judge。两个文字单元与历史上下文字节和源系统消息哈希均一致；109 道题面哈希一致。原生估价函数预计 1,440 调用、错峰 23.8252158 元；**模型调用 0、费用 0，未采集、未判定**。正式 CLI dry-run 被缺少 `semantic-v1.7-l3a-full` 标签的版本检查拒绝，尚未通过；待标签发布后重跑正式 dry-run，再交用户批准并错峰启动。预检报告 `reports/validation/t34-run-preflight.md`，结构化证据 `runs/20261104-T34-ontology-full-01/preflight.json`；冻结题库 eval-v1.2=90e13b385a639a9164ac78430c50c11a7859f976。新指纹待首次实际响应，运行中变化即停；原样 harness，无监督脚本。

### 20261104-T34-ontology-full-01：2026-11-05 标签与正式 dry-run 追加

用户明确授权在 #261 合并提交 51247a8c5e4e296093b4260a17db843ff64c06d8 创建并发布附注标签 semantic-v1.7-l3a-full（tag 对象 c3750ae8e5fdecfb3304d7b73a7067d28fe40b39），远端已核实，T34 目录已 fetch。原样四单元正式 dry-run 退出 0，eval-v1.2 与新语义标签检查通过，1,308 次作答、预计 1,440 调用、错峰 23.8252158 元，与此前估价一致；文字上下文哈希复核未变。**待用户批准付费；模型调用 0、费用 0、未采集、未判定、无新指纹。** 此前缺标签的失败记录保留，不作为本次通过结果。

### 20261104-T34-ontology-full-01：2026-11-05 获批采集完成，待独立内容复核

用户明确批准原生 dry-run 参数仅去掉 `--dry-run`，并授权 109 道题面和四份上下文发送 DeepSeek 官方 API（不发参考答案）；按返回用量累计超过 30 元则停止。四单元各 327 次、共 1,308 次作答全完成，1,647 次接口返回、14.25975176 元，均错峰，进程退出 0，无停跑恢复。首条及全部返回指纹 `bc19ba97cbe016479903222bb1578db6`。代码版本全为 948029d；采集期间未提交。起止报费、实际用量见本 run 的 collection.json、usage-audit.json，原始响应只在环境数据目录。

效果范围为主表同一批 98 题；1,176 次 D1 首轮标签位于 `20261104-T34-ontology-full-01-content-01/codex-verdicts.jsonl`，均标记 `final=false`。报告 `reports/results/l3a-full.md` 暂待跨厂商复核。全部 1,013 条判对项（含自动规则项）已生成本机匿名包；清单 `reports/validation/t34-claude-review-manifest.md` 及 JSON，包位于 `$SEMDEBT_DATA_DIR/t34-run-20261104/claude-review/`，由用户本机普通模式 Claude Code 独立复核并写回 results.json。私有题面、参考及理由不入仓库；回收前不将分歧计为 0。
