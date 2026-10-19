# T16 指标层实验进度

## 最新：#142 / #143 裁决后的静态审查（不调用模型）

main 以 merge 合入（`4659cf1`、`f0c7531`），未 rebase。新审查见 [范围复核](../validation/t16_l2_scope_review.md)、[逐题覆盖](../validation/t16_l2_scope_coverage.md)、[参考读法对齐交接](../validation/t16_cube_reference_alignment.md)。只有上下文可见成员计覆盖；隐藏辅助指标不计交付，由 T12 的 v1.4 范围/变体检查决定。

Q17 数值与分母范围正确，但无可见基数成员，归 d；Q69 已有可见基数成员，归模型未遵循展示约定。原分数不动、不重评。按 #143，四条 SQL 最终错误均是 Cube 生成 SQL 的空标识符语法错误，错误层面的引擎限制为 4/4；存在其他可执行写法不消除这一归因。跨事实表时间筛选 12 个通用探针完成，8 个成功结果与独立物理基线一致。全量未估算、未运行；v1.4 实际上下文交付后还须绑定和固定静态表。

## 以下为此前 L2 交付审查历史（分类已被上述裁决更新）

补充分责：JSON拒答按常用口径应由指标层承担9条，题目特有组合的JSON接口限制1条（Q117）。建议指标、口径、L1文字及未承诺的部分见 [补充分类](../validation/t16_l2_delivery_classification.md)。不把未定义的新口径伪装成原69项漏实现；不修改冻结材料、不估全量。

用户要求先审交付、不估全量。审查完成：JSON的10条拒答在现有成员下一条正确JSON均不可表达，归当前冻结交付的接口限制（不是Cube产品永久限制）；未发现可表达但素材误导的条目。SQL四条执行失败均定位为说明缺口，手写诊断均通过v2参考；Q80不再待定。最终失败中已证实接口硬能力限制为0/4。25条通用探针、6项原始表独立数值核验通过预期断言；仅提供两条通用只增补建议，不直接改冻结说明或语义模型，不改原模型作答/分数。详见 [交付审查](../validation/t16_l2_delivery_audit.md) 与 [只增补建议](../validation/t16_l2_delivery_additions.md)。全量继续等待用户审定后再估算/批准，尚未估算或调用。

## semantic-v1.3 冒烟原始结果（用户批准高峰执行）

两个单元各23题均完成，固定指纹55/55一致，实际运行commit `22b6100`。v2离线重评：SQL-L2主表10/19=52.6%，低区分度3/4；JSON-L2主表5/19=26.3%，低区分度1/4。SQL最终执行失败4、JSON1；总费用1.41452904元，低于3元高峰预算。SQL归因仍有1条待定，不能确认是否跨20%门槛；全量暂停，尚未估算或调用。完整结果、逐轮原文及归因口径见 [本轮报告](../validation/t16_pilot_v13_results.md)。

JSON小数在runs-raw中以字符串无损保存，原rescore未还原数值；已修复harness反序列化并以新目录`20261019-T16-pilot-v13-02-rescore-02`重评，评分器不变。`rescore-01`保留但不能用于最终分数。

## 以下为旧冒烟及诊断历史


2026-10-19：SQL-L2 冒烟完成，曾因自动错误分类触发停止门槛。用户随后要求先做接口能力实测，不先裁决保留或移至第二期。180 个通用探针与18次原始错误审计已完成，原自动分类不能直接作为能力结论；JSON-L2 冒烟及全量继续暂停，T16 尚未完成。最终分数等待评分器 v2（`harness-v1.1`）离线重评，本报告的当场判定仅作进度参考，不作为实验结论。后续正式运行按用户指定改用 `eval-v1.2`，旧冒烟不混入正式结果。

## 接口实测与归因更正

- 独立通用探针180条（SQL146、JSON34），104条接受、76条报错；成功不等于正确，80项独立数值检查中有3个明确反例。说明逐条覆盖、成立条件、全部探针原文、返回类型及报错原文见 `reports/validation/t16_cube_capabilities.{md,json}`。
- 简单 CTE 再聚合、双指标 CTE、跨事实的独立聚合 CTE 都有成功且数值正确的正例；不能笼统判“不能用 CTE”。但重复输出名和某些 CTE 互连再聚合会静默错值。平铺 CROSS JOIN 的顺序/连接树、窗口 UInt64 输出、中文投影别名加窗口、EXTRACT 与 MEASURE 分组都有说明未写出的边界。
- 18次错误的互斥首要归因：写法说明错误/必要条件缺失14次、当前函数/类型组合确实不支持3次、明确违反说明约束1次。逐轮依据、置信度、原始错误及哈希见 `reports/validation/t16_sql_pilot_error_audit.{md,json}`。其中3条复杂组合定位为中等置信度，不能把此归类当成逐题最小复现的证明。
- `PERCENTILE_CONT` 在 Float64 纯 VALUES 控制中仍明确未实现；AVG(interval) 和 interval 转 Float64 有独立类型失败例。只说明这些函数/类型形态不可执行，不证明整个业务不可表达。
- 原日志中的 error_class 不改；**4/7=57.1% 是旧自动分类，不能直接视为已证实的接口能力限制比例。** 不按新归因比例自动放行实验。未改 render/、语义层、提示或评分器；说明修正归 Claude Code，经用户裁决后处理。

## 版本与运行

- 运行：`20261019-T16-pilot-01`；SQL-L2，`questions/pilot.yaml` 24 题 × 1 次，单并发。
- 本地运行提交：`cf7d3b5b6040affc014c5969267cb006d2cae516`；每条日志的 `harness_commit` 为 `cf7d3b5`，没有 dirty 标记。
- main 基线：`84f5e045dc9d3456c11c4453515c746047a69c74`，含 PR #100 的评分子进程 10 秒超时；超时记 pending，不改评分器。
- 题库：外部只读副本 `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.1`，与 `eval-v1.1` = `938957f4281ddc63ba699bf15d91dcde6b71ddf0` 内容一致，启动前由 runner 校验。
- 语义层：`semantic-v1.2` = `4cf56a8ea388a62140f4554df2b1dd745e9e7bc4`；语义源、渲染器与 tag 一致，两个 L2 上下文从冻结源重新生成并校验。
- 模型：`deepseek-flash`；35 次调用的 `system_fingerprint` 全为 `e72d3c7f663d3e1383b00b3884cb4501`，缺失指纹 0。
- 2026-10-19 07:13:16–07:24:40（UTC+8）运行，全部错峰；每个实际请求（含传输重试）前检查时间，每个响应后检查指定指纹。
- dry-run：两个冒烟单元共 48 条作答，按 10% 修正率预计 52 次调用、0.77 元，用户已批准。SQL 实际 11 条触发一次修正，共 35 次调用，费用 **0.54510072 元**。JSON 未调用；全量已 dry-run，未获运行批准，也未启动，估算见下节。

## 全量 dry-run（不调用模型）

以下为先前 `eval-v1.1` 和旧语法说明下的预算准备，不是 `eval-v1.2` 正式运行批准或最终费用估计。语法说明裁决后须重新冒烟、重新估算；本轮用户明确要求 JSON 冒烟与全量均不跑。

2026-10-19 按用户要求，将分支 rebase 到最新 main `88fd81c`（含 #112），rebase 前后文件树逐字节一致；原始实验提交 `cf7d3b5` 通过本地备份分支保留，不改日志的提交号。rebase 后针对 T16 守卫、两个 main 的冻结文件、dry-run 清单与 T15 兼容的 13 项检查通过。

全量仍按两个单元各 122 题 × 3 次，共 732 条作答作估算。SQL 使用本次 35 次冒烟调用的实测 token 均值，JSON 尚无冒烟测量，沿用 runner 的上下文大小与每次 3,000 输出 token 默认估计。均为错峰价格，不是费用保证。

| 假设 | SQL-L2 调用 / 费用 | JSON-L2 调用 / 费用 | 总调用 | 总费用 |
|---|---|---|---:|---:|
| 默认 10% 修正率 | 403 / ¥6.28 | 403 / ¥6.00 | 806 | ¥12.27 |
| 两单元都按 SQL 冒烟 11/24＝45.8% 修正率 | 534 / ¥8.32 | 534 / ¥7.95 | 1,068 | ¥16.26 |
| 每条都修正一次（100%） | 732 / ¥11.40 | 732 / ¥10.89 | 1,464 | ¥22.29 |

费用由 runner 未四舍五入的值相加，可能与表中单元费用相加有一分钱差异。第二、三行是敏感性假设，不代表 JSON 的实测修正率；token 变动或传输重试也可能改变实际费用。已用 0.54510072 元需另计于整卡预算；100% 修正情景已超过 20 元，不能据默认估计宣称一定在预算内。

复现：

```sh
uv run python -m harness.run_direct --cell SQL-L2 --cell JSON-L2 --reps 3 \
  --model deepseek-flash --eval-tag eval-v1.1 --semantic-tag semantic-v1.2 \
  --expected-fingerprint e72d3c7f663d3e1383b00b3884cb4501 --budget 20 --dry-run
# 敏感性：追加 --est-fix-rate 0.4583333333333333 或 --est-fix-rate 1
```

未启动全量；SQL 接口限制门槛待裁决，JSON 冒烟也尚未继续。用户明确本次只估算、不跑全量。

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

## 历史自动错误分类与停止记录（已由实测审计补充）

部署前置复验：Cube Core 1.8.6、ClickHouse 25.8.20.4；同比、环比、占比、同店增长共 7 个成员 × 双接口，**14/14 通过，明确接口限制 0**。详见 `reports/validation/metric_layer_t16.{md,json}`。该核验只证明固定验证查询能算出指标，不表示任意题集查询均支持。

SQL-L2 冒烟最终执行失败中：

| 分类 | 条数 | 题号 |
|---|---:|---|
| 原自动 interface_limitation | 4 | Q100、Q117、Q73、Q74 |
| 原自动 engine_error | 3 | Q34、Q50、Q75 |
| 总计 | 7 | — |

所有执行轮次共 18 次错误，其中接口限制 5 次、普通引擎错误 13 次；此处单独记录，不与最终失败条数混用。最终拒答 0，因此本次拒答中的接口限制计数为 0。

**当时自动分类：4/7 = 57.1% > 20%，因此停止。** 7条最终执行失败均为非 judge 题。用户随后明确不先选择保留或移至第二期，要求先核验语法说明；现已完成上文独立实测与逐轮重新归因。该旧比例保留作运行历史，不作为当前能力结论。JSON 冒烟和全量继续暂停，未修改冻结内容或原始日志。

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
