# T16 指标层（Cube Core：SQL-L2 与 JSON-L2）

- 状态：v1.3冒烟及无模型L2交付审查完成；SQL四条执行失败均为说明缺口（Q80已定位，诊断均过v2参考），JSON十条拒答为当前冻结交付接口限制。只增补建议待审定，不改冻结材料；全量不估算、不启动，等待用户裁决。PR #114待Claude Code审。
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
- 用户确认：G3、T13 已满足；用户先批准冒烟，随后明确不先选保留或第二期，要求先无模型核验两份语法说明及重新归因。实测报告已交付，说明更正归 Claude Code、需用户裁决；JSON冒烟与全量继续暂停。后续正式运行固定 eval-v1.2；PR 须经 Claude Code 审核后才合并。

### 实验进度（2026-10-19）

- 运行 `20261019-T16-pilot-01`：SQL-L2 24/24 条、35 次调用、0.54510072 元；JSON-L2 0/24，未启动。日志 `runs/20261019-T16-pilot-01/SQL-L2.jsonl`，报告 `reports/results/metric_layer.md`。
- 本地运行提交 `cf7d3b5b6040affc014c5969267cb006d2cae516`；main 基线 `84f5e045dc9d3456c11c4453515c746047a69c74`（含 PR #100）；题库只读副本与 `eval-v1.1` = `938957f` 一致，语义层 `semantic-v1.2` = `4cf56a8`。35 次调用指纹均为 `e72d3c7f663d3e1383b00b3884cb4501`，全部错峰。
- 运行前复验四类指标：7 个成员 × 双接口，14/14 通过，明确接口限制 0；题集查询的能力限制单独记录，不以部署核验替代。
- 7 条最终执行失败中接口限制 4 条（Q100、Q117、Q73、Q74），57.1% > 20%。已按验收停止，未修改冻结内容或绕开失败；见 `decisions/open-questions.md` T16-1。
- 完整性：24 个题次无缺失、重复或非 done 行；35 份响应、35 份执行结果哈希全部核对，17 份成功执行的完整行数与日志一致。完整行集保存在外部 `runs-raw`，不入库。judge 题不查阅作答、不进准确率分母；低区分度单列。当前分数仅作进度参考，最终等待 v2（`harness-v1.1`）离线重评。
- 测试：相关离线测试 100 passed、25 skipped、1 deselected；题库环境下单独执行 dry-run 单元测试 1 passed。新增逐字节回归测试证明 `harness/prompt.py`、`harness/scorer.py` 与上述 main 基线完全一致；`git diff --check` 通过。
- PR 准备：冒烟结束后合并 main `88fd81c` 的 T15 接线，不改运行提交或日志。直答、Cube、agent 兼容复测 152 passed、3 skipped、1 deselected；针对 `84f5e04` 与 `88fd81c` 的四项冻结文件字节检查加 dry-run 单元测试共 5 passed。冻结文件对两个 main 版本都逐字节一致。
- 偏离与理由：冒烟估算按 10% 修正率为每单元 26 次调用；SQL-L2 实际 11 条触发一次修正，共 35 次。按任务卡接口限制门槛，在 SQL 冒烟结束后暂停，整卡未完成。
- 后续准备：按用户要求 rebase 到最新 main `88fd81c`（含 #112），文件树与 rebase 前一致，13 项针对性检查通过；原运行提交和日志不改。全量 dry-run 共 732 条作答：默认 10% 修正率 806 次调用、12.27 元；两单元按 SQL 冒烟 45.8% 修正率估算为 1,068 次、16.26 元；100% 修正情景为 1,464 次、22.29 元（超预算）。SQL token 用量实测、JSON 未测，最终仍须根据 JSON 冒烟复估；用户明确不启动全量。
- 接口诊断：新增 `scripts/probe_cube_interfaces_t16.py` 和独立报告/审计脚本；180条通用探针（不读题库或模型响应）、逐条语法说明覆盖、原始错误和类型证据在 `reports/validation/t16_cube_capabilities.{md,json}` 及4个清单/结果目录。80项独立数值核验含3个“成功但错值”的反例。18次错误重新归因为说明/条件缺失14、函数/类型不支持3、明确写法违反1，含中等置信度复杂组合，详见 `t16_sql_pilot_error_audit.{md,json}`。
- 本轮模型调用0；原日志哈希不变，不执行原候选查询作探针，不改 render/、语义层、提示或评分器。原4/7是字符串自动分类，不再作为已证实的接口能力结论；不自动恢复运行，下一正式版本为 eval-v1.2。
- 工时：本轮搭建与验证约 1 小时（估算）；实验未开始。

## 2026-10-19 v1.3 冒烟追加记录

- 用户单次批准高峰冒烟、总预算3元，使用--allow-peak；运行提交22b6100。eval-v1.2=90e13b3、semantic-v1.3=d2801b1；pilot跳过judge Q40，两单元各23×1，单并发，SQL后JSON。
- SQL：30调用、0.98173872元，13对6错4执行失败；主表10/19，低区分度3/4。JSON：25调用、0.43279032元，6对6错10拒答1执行失败；主表5/19，低区分度1/4。55次指纹一致；55响应、45执行文件哈希及完整行数核对通过。
- 采用rescore-02的v2离线结果；rescore-01因Cube number注解数值未恢复而误降4条，保留但不用。c709ca5仅修harness/rescore.py反序列化，并加现有测试；6项rescore测试及harness/Cube测试通过。prompt.py、scorer.py、scorer_v2.py、score_guard.py与main逐字节一致；不改semantic/render。
- SQL最终失败：1条明确列名规则违反并伴随别名缺口，2条有通用正反例的说明条件缺失，1条未定位；已证实硬能力限制0/4、1/4待定，不能作确定0%，敏感范围0–25%可能跨20%门槛。JSON最终失败是不必要的sales时间筛选，已证实硬能力限制0/1。16条通用控制不调用模型，逐轮原文、置信度见reports/validation/t16_pilot_v13_results.md。
- 尚不判冒烟通过。三组全量（SQL v1.3/v1.2、JSON各109×3）未估算、未启动；按用户顺序等冒烟归因/裁决后再估，并等待批准、只在错峰执行。报告和全部日志已交PR #114，由Claude Code审后用户合并。

## 2026-10-19 L2交付审查追加

- 用户明确先审交付、不估全量、不调用模型。JSON十条拒答逐题核对338个既定义成员（含隐藏成员）；在一条JSON直接答对的口径下均不可表达，列当前交付接口限制。缺失能力及既有相关成员见reports/validation/t16_l2_delivery_audit.md。
- SQL四条均复现报错，单改英文输出别名即可执行；前三条通过v2，另一条用两侧分别聚合的CTE后通过v2。均归说明缺口，Q80待定消除，硬能力限制0/4；不改源模型作答或分数。
- 25条通用探针、6项独立数值基线断言验证；原查询及仅改别名对照做字节检查。只增补建议在reports/validation/t16_l2_delivery_additions.md，未直接修改render/、模型或tag。模型调用0、费用0；全量仍待用户审定后再估算与批准。
