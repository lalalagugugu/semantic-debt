# T16 指标层实验进度：SQL-L2 冒烟

2026-10-19：SQL-L2 冒烟完成，触发接口限制停止门槛；JSON-L2 冒烟及两个全量单元未启动，T16 尚未完成。最终分数等待评分器 v2（`harness-v1.1`）离线重评，本报告的当场判定仅作进度参考，不作为实验结论。

## 版本与运行

- 运行：`20261019-T16-pilot-01`；SQL-L2，`questions/pilot.yaml` 24 题 × 1 次，单并发。
- 本地运行提交：`cf7d3b5b6040affc014c5969267cb006d2cae516`；每条日志的 `harness_commit` 为 `cf7d3b5`，没有 dirty 标记。
- main 基线：`84f5e045dc9d3456c11c4453515c746047a69c74`，含 PR #100 的评分子进程 10 秒超时；超时记 pending，不改评分器。
- 题库：外部只读副本 `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.1`，与 `eval-v1.1` = `938957f4281ddc63ba699bf15d91dcde6b71ddf0` 内容一致，启动前由 runner 校验。
- 语义层：`semantic-v1.2` = `4cf56a8ea388a62140f4554df2b1dd745e9e7bc4`；语义源、渲染器与 tag 一致，两个 L2 上下文从冻结源重新生成并校验。
- 模型：`deepseek-flash`；35 次调用的 `system_fingerprint` 全为 `e72d3c7f663d3e1383b00b3884cb4501`，缺失指纹 0。
- 2026-10-19 07:13:16–07:24:40（UTC+8）运行，全部错峰；每个实际请求（含传输重试）前检查时间，每个响应后检查指定指纹。
- dry-run：两个冒烟单元共 48 条作答，按 10% 修正率预计 52 次调用、0.77 元，用户已批准。SQL 实际 11 条触发一次修正，共 35 次调用，费用 **0.54510072 元**。JSON 未调用；全量尚未 dry-run 或获批。

复现 SQL 冒烟命令（已有运行不可覆盖；若重跑须换新的 run-id 并先 dry-run，经用户批准且处于错峰）：

```sh
export SEMDEBT_EVAL_DIR="$SEMDEBT_DATA_DIR/eval-ro-eval-v1.1"
uv run python -m harness.run_direct --cell SQL-L2 --pilot --reps 1 \
  --concurrency 1 --run-id 20261019-T16-pilot-01 --model deepseek-flash \
  --eval-tag eval-v1.1 --semantic-tag semantic-v1.2 \
  --expected-fingerprint e72d3c7f663d3e1383b00b3884cb4501 --budget 20
```

## 完整性与原始结果

- SQL-L2：24/24 个 `(qid, rep)`，无缺失、重复、非 done 行。JSON-L2：0/24，按停止门槛未启动。
- 35 份响应及35份执行结果的 SHA-256 与日志逐项一致；17 份成功执行的完整行数与日志一致，所有轮次（包括修正前的错误）均保留。
- 完整响应、完整行集或未截断错误位于 `$SEMDEBT_DATA_DIR/runs-raw/20261019-T16-pilot-01/SQL-L2/`，不入库。
- 提交日志：`runs/20261019-T16-pilot-01/SQL-L2.jsonl`，SHA-256 为 `60f2566162dcc895567a3eb5e445563027ccee03a9e76c1f5a6ff07822f28355`。
- judge 题只作完整性和状态统计，不查阅作答内容，等待既定评审流程。

## 当场判定（暂定，待 v2 离线重评）

judge 全部排除于准确率分母；低区分度另列。以下四类比例仅复述当前运行日志，pending 不作为四类判定。

| 分层 | 作答 | 正确 | 错答 | 执行失败 | 拒答 | pending |
|---|---:|---:|---:|---:|---:|---:|
| 非 judge、非低区分度 | 19 | 9（47.4%） | 3（15.8%） | 7（36.8%） | 0 | 0 |
| 低区分度（非 judge） | 4 | 4（100%） | 0 | 0 | 0 | 0 |
| 非 judge 合计（含低区分度） | 23 | 13（56.5%） | 3（13.0%） | 7（30.4%） | 0 | 0 |
| judge，单列且不进上述分母 | 1 | 0 | 0 | 0 | 0 | 1 |

本次评分超时 `score_timeout` 为 0。不得使用本表当场分数替代 v2 最终重评结果。

## 接口能力限制与停止门槛

部署前置复验：Cube Core 1.8.6、ClickHouse 25.8.20.4；同比、环比、占比、同店增长共 7 个成员 × 双接口，**14/14 通过，明确接口限制 0**。详见 `reports/validation/metric_layer_t16.{md,json}`。该核验只证明固定验证查询能算出指标，不表示任意题集查询均支持。

SQL-L2 冒烟最终执行失败中：

| 分类 | 条数 | 题号 |
|---|---:|---|
| 明确接口限制 | 4 | Q100、Q117、Q73、Q74 |
| 普通引擎错误 | 3 | Q34、Q50、Q75 |
| 总计 | 7 | — |

所有执行轮次共 18 次错误，其中接口限制 5 次、普通引擎错误 13 次；此处单独记录，不与最终失败条数混用。最终拒答 0，因此本次拒答中的接口限制计数为 0。

**门槛：4/7 = 57.1% > 20%。** 7 条最终执行失败均为非 judge 题，去除 judge 不改变门槛。按卡片停止，JSON 冒烟和全量未继续；等待用户选择保留 SQL-L2 并如实报告，或将其移至第二期。没有修改语义层、提示、评分器，没有改写或过滤失败结果。

## Harness 改动与冻结证明

- `harness/cells.py`：登记已有渲染器支持的 JSON-L2 单元，并将已有 Cube 执行器标为本机可运行。
- `harness/client.py`：添加可选请求前回调；每次 HTTP 尝试（包括已有传输重试）都可检查错峰和停止标记；请求体、提示、模型参数和重试策略未改。
- `harness/run_direct.py`：接通两个现有 Cube 执行器；添加指定指纹检查及共享停止边界；指纹不符时先存原始响应，再停止且不执行查询。沿用现有一次执行报错修正与评分 10 秒超时，完整行集沿用现有 runs-raw 保存流程。
- `tests/test_harness.py`：覆盖首轮/修正轮错误指纹、缺失指纹、跨入高峰阻止修正、传输重试前边界、JSON 流程、单元清单及冻结文件字节比较。

`test_t16_frozen_files_match_main_byte_for_byte` 从固定 main 基线 `84f5e045dc9d3456c11c4453515c746047a69c74` 读取 Git blob，与工作区 `read_bytes()` 直接比较，两项通过：

| 文件 | SHA-256（工作区与 main 相同） |
|---|---|
| `harness/prompt.py` | `86fefce2157ff4fc09819fe8c8c5ad4fe7e6e064850f9ce9c8b1b67e97919e5e` |
| `harness/scorer.py` | `3be6d29f5a11fafa5843c086362b6ddcfd3b2391413e82e3a98c09f09de50efd` |

PR 准备时远端 main 已更新为 `88fd81c9d743ef93d1e00f65c7f5f8faa95d72ec`（包含 T15 agent 接线）。该 main 的两个冻结文件仍与上述哈希相同；回归测试已扩展为两个 main 提交 × 两个文件，四项逐字节比较全部通过。冒烟结束后合并该 main，保留 `tool_executor`、agent 的 `attempt` 回调与步骤指纹统计，没有重新调用模型或重写日志。合并后兼容复测 `tests/test_harness.py tests/test_cube_executors.py tests/test_agent.py -k 'not dry_run_matches_board_unit_list'` 为 **152 passed、3 skipped、1 deselected**（此次环境已提供数据目录，chDB 相关测试也通过）；独立执行四项字节检查与 dry-run 清单测试为 **5 passed**。

验证（运行提交 `cf7d3b5`）：相关离线测试 100 passed、25 skipped、1 deselected；设置只读题库环境后单独 dry-run 清单测试 1 passed。跳过项需要外部 chDB/题库，未以访问共享主 chDB 来补跑。测试早期曾因缺少环境变量触发外部题库/锚点依赖失败，后将离线测试与只读题库 dry-run 检查分开执行，未改测试断言绕过失败。`git diff --check` 通过。

```sh
uv run pytest tests/test_harness.py tests/test_cube_executors.py \
  -k 'not dry_run_matches_board_unit_list' -o addopts= -q
SEMDEBT_EVAL_DIR="$SEMDEBT_DATA_DIR/eval-ro-eval-v1.1" \
  uv run pytest tests/test_harness.py::test_dry_run_matches_board_unit_list -o addopts= -q
uv run pytest tests/test_harness.py::test_t16_frozen_files_match_main_byte_for_byte -o addopts= -q
```

PR 须经 Claude Code 审核后才合并；本卡未完成，不自动合并。全量费用上限 Flash 20 元，仍须先 dry-run 并另获用户确认。
