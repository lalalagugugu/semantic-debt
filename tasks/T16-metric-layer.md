# T16 指标层（Cube Core：SQL-L2 与 JSON-L2）

- 状态：搭建完成；2026-10-19 SQL-L2 冒烟 24/24 完成，接口限制占执行失败 4/7（57.1%），按验收门槛停止，待用户裁决；JSON 冒烟与全量未启动
- 负责：Codex
- 模式：主仓库 clone（`scripts/start-card.sh T16`）
- 依赖：搭建在 G1 之后（需要 `build/cube/`，T10）；跑单元在 G3 之后、T13 跑完之后（避免抢 API 并发）
- 预算：Flash 20 元 / Pro 60 元

## 目标

用开源指标层 Cube Core 承载 L2 指标，测两种调用接口：SQL（Postgres 方言，用 `MEASURE()` 调用指标）和 JSON（REST 查询）；并为 T15 的 L2-E 提供只读的 `cube_sql` 执行器。

## 做法

1. 起一个本地 ClickHouse 服务（Docker），从 `$SEMDEBT_DATA_DIR/parquet/` 导入与 chDB 相同的数据，逐表核对行数与合计。
2. 用 Docker 起 Cube Core，连接该 ClickHouse，加载 `build/cube/model/`；同时开启 SQL 接口和 REST 接口。先确认开源版本确实提供 SQL 接口，并记录版本号。
3. 在 `harness/executors/` 加两个执行器：`cube_sql`（Postgres 协议，只读）和 `cube_json`（`/load` 接口），接口与 T11 的执行器一致。语法说明用 T10 生成的两段。不得改动 harness 的系统提示与评分（已冻结为 `harness-v1`）。
4. 所有单元都允许输出 `CANNOT_ANSWER`；JSON 的接口能力决定它会更常拒答，这是要测的现象，不要通过放宽提示去减少拒答。
5. 先用最小样本 24 题 × 1 次冒烟；再用 harness 跑全量：SQL-L2、JSON-L2，中文题集全部，每题 3 次。

## 来自 T10 的交接（2026-10-16）

**4 个 Cube 指标 T10 验证不了，必须在本卡验**：同比、环比、占比、同店增长。它们依赖较新的查询计划器，T10 的环境跑不起来。**这 4 个指标若在本卡的 Cube 版本上仍不可用，不要悄悄绕开**——记成接口能力限制并单独计数（本卡验收已有这一项），T19 要能看见。

T10 已把每个 Cube 指标背后的 SQL 在 chDB 上跑过并与 `source.yaml` 的合计核对一致（26 项）；本卡要验的是 **Cube 这个接口能不能算出来**，不是口径对不对。

T10-1 的裁决（23 个双表指标各有两个调用名，`online_sales.<成员>` 与 `sales.<成员>`）见 `decisions/2026-10-15-dual-dataset-metric-callables.md`。

## 交付物

- 数据核对报告；Cube 版本与配置（`docker-compose.yml` 等，不含数据）；两个执行器及测试。
- `reports/results/metric_layer.md`：两个单元的准确率与四种结果占比；执行失败和拒答里属于接口能力限制的单独计数。

## 验收

- 记录数完整；`cube_sql` 执行器能供 T15 使用。
- 如果 SQL 接口的执行失败中，接口限制造成的超过 20%，停下来交用户决定：保留并如实报告，或把 SQL-L2 移到第二期。

## 不能做

- 不得修改 `semantic/`（已冻结）。Cube 模型有问题，回到渲染器并走 `decisions/` 流程。

## 记录（完成后填写）

- 产出：
  - `docker-compose.yml`、`templates/cube.js`、`templates/cube-clickhouse-init.sql`：Cube Core / Cube SQL / Cube Store 1.8.6 与 ClickHouse 25.8.20.4，SQL、REST 均已启动并实测，端口只绑定本机。镜像 digest 见验证报告。
  - `data/clickhouse_t16.py`：25 表、34,326,191 行导入；与独立 chDB 副本核对 147 项（行数、所有数值列合计），全部一致；另与 T01 主 chDB 原始报告交叉核对 49 项，全部一致。
  - `scripts/verify_metric_layer.py`、`reports/validation/metric_layer_t16.{md,json}`：优先验证同比、环比、占比、同店增长。线上与全渠道共 7 个成员 × SQL/REST 两个接口，14/14 与独立 SQL 基线一致；这些查询的明确接口限制为 0。
  - `harness/executors.py`：两个执行器沿用 `execute(query) -> ExecResult`；SQL 可供 T15 导入使用。只读检查、总时限、行数限制、结果类型转换与错误分类均已实现。
  - `tests/test_cube_executors.py`：49 项 mock 测试通过，不需要 Docker、题库或模型 API。
  - 兼容验证：`uv run pytest tests/test_cube_executors.py tests/test_harness.py -k 'not dry_run_matches_board_unit_list'` 为 73 passed、18 skipped、1 deselected；设置 `SEMDEBT_DATA_DIR` 后 `uv run pytest tests/test_repo_layout.py` 为 39 passed、1 skipped。跳过项依赖主 chDB/题库或 G1 前状态，唯一 deselected 项需要外部题库上下文，本轮未读取。`git diff --check` 通过。
  - `pyproject.toml`、`uv.lock`：按用户批准用 `uv add 'psycopg[binary]'` 加入依赖，锁定 3.3.6；其他既有依赖未升级。
  - 复现命令与配置环境变量见 `harness/README.md` T16 节；数据报告见 `reports/validation/clickhouse_t16.md`。
- 偏离与理由：
  - 用户 2026-10-16 明确本轮只做第 1–3 步；不调用 DeepSeek，不跑 24 题冒烟或全量，不生成实验准确率报告，不将整张卡标为完成。后续实验仍等 G3 与 T13 完成。
  - 卡片原写 `harness/executors/`，现有实现是单文件 `harness/executors.py`；按用户要求沿用单文件，不迁移目录。
  - 主 chDB 目录被另一进程占用，首次核对被锁拒绝；用现有 `data/build_chdb_copy.py` 从 T01 Parquet 建 `chdb-t16` 独立副本，并追加与 T01 原主库报告的比较，未绕过锁或中断其他会话。
  - 配置验证中曾遇到只读 Parquet 挂载被镜像入口脚本递归 chown、`readonly=1` 禁止 Cube 驱动设置 `join_use_nulls`、libpq 需要非空认证响应；均已修正为配置/连接层实现，不计作指标接口能力限制。临时探针曾误用线上表不存在的渠道列，正式验证改用已定义的门店维度。
  - 兼容检查初次有两项因未设 `SEMDEBT_*` 环境变量失败，未改现有测试或 harness 逻辑；本轮不为测试读取题库，题库依赖检查另行记录。
- 用户确认：G3、T13 已满足；用户已批准两个单元的 24 题冒烟。SQL-L2 冒烟触发本卡 20% 门槛，待用户选择保留并如实报告，或将 SQL-L2 移至第二期。全量须另行 dry-run 与费用确认；PR 须经 Claude Code 审核后才合并。

### 实验进度（2026-10-19）

- 运行 `20261019-T16-pilot-01`：SQL-L2 24/24 条、35 次调用、0.54510072 元；JSON-L2 0/24，未启动。日志 `runs/20261019-T16-pilot-01/SQL-L2.jsonl`，报告 `reports/results/metric_layer.md`。
- 本地运行提交 `cf7d3b5b6040affc014c5969267cb006d2cae516`；main 基线 `84f5e045dc9d3456c11c4453515c746047a69c74`（含 PR #100）；题库只读副本与 `eval-v1.1` = `938957f` 一致，语义层 `semantic-v1.2` = `4cf56a8`。35 次调用指纹均为 `e72d3c7f663d3e1383b00b3884cb4501`，全部错峰。
- 运行前复验四类指标：7 个成员 × 双接口，14/14 通过，明确接口限制 0；题集查询的能力限制单独记录，不以部署核验替代。
- 7 条最终执行失败中接口限制 4 条（Q100、Q117、Q73、Q74），57.1% > 20%。已按验收停止，未修改冻结内容或绕开失败；见 `decisions/open-questions.md` T16-1。
- 完整性：24 个题次无缺失、重复或非 done 行；35 份响应、35 份执行结果哈希全部核对，17 份成功执行的完整行数与日志一致。完整行集保存在外部 `runs-raw`，不入库。judge 题不查阅作答、不进准确率分母；低区分度单列。当前分数仅作进度参考，最终等待 v2（`harness-v1.1`）离线重评。
- 测试：相关离线测试 100 passed、25 skipped、1 deselected；题库环境下单独执行 dry-run 单元测试 1 passed。新增逐字节回归测试证明 `harness/prompt.py`、`harness/scorer.py` 与上述 main 基线完全一致；`git diff --check` 通过。
- PR 准备：冒烟结束后合并 main `88fd81c` 的 T15 接线，不改运行提交或日志。直答、Cube、agent 兼容复测 152 passed、3 skipped、1 deselected；针对 `84f5e04` 与 `88fd81c` 的四项冻结文件字节检查加 dry-run 单元测试共 5 passed。冻结文件对两个 main 版本都逐字节一致。
- 偏离与理由：冒烟估算按 10% 修正率为每单元 26 次调用；SQL-L2 实际 11 条触发一次修正，共 35 次。按任务卡接口限制门槛，在 SQL 冒烟结束后暂停，整卡未完成。
- 工时：本轮搭建与验证约 1 小时（估算）；实验未开始。
