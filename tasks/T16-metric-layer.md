# T16 指标层（Cube Core：SQL-L2 与 JSON-L2）

- 状态：未开始
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
- 偏离与理由：
- 工时：建指标层 __ 小时
