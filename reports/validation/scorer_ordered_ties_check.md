# 有序并列块与评分器性能改动验收

按2026-10-16排序并列裁决，在同一个评分器分支交付通用块比较、提前拒绝及精确投影快路。T11 #49已合并，分支已rebase到含新裁决的main；唯一手工冲突为BOARD，已保留T11原始锚点接线及新待办18/19。随后重新执行600条SQL并核对完整ScoreResult。

## 有序比较接口

有效rules显式声明order_by（参考列0起位置＋descending）；多键组成完整排序键。逐参考规则整份覆盖题级。参考连续同键行构成块，块内比较完整行多重集，块间按顺序。键相等使用已有全局量纲量化，不使用0.5%或atol。列排列在全结果上保持同一个映射，重复行数量不丢失。

Top-N严格前缀及参考恰好N行时使用块比较；完整边界组的任选语义不变。缺键时RuntimeWarning告警并保留原逐位置比较；selection已有显式output_order时沿用其声明语义。无题号分支、不读SQL或候选来猜键，不改精度、容差、整数计数守卫或judge路径。

题库PR #14补齐19道有序题的25份当前参考，另有18份原公开验证参考排序键审阅、8份结构不同英文原始规则交接；harness原样透传。Q79仍42成员且门禁数量动态推导。

## 同批600条的排序契约影响

基线为已实现等价性能改动、尚未实施块比较的提交26c45ea842a09a5e1f1996a2b31f8d987fb35088；基线评分器SHA256：0b693d1a03f1c35961963abb6f2860f51fc9ecc8c4976f71ba7db5ce00a4094d；新版SHA256：e751d8b94fbfda6045c3e0f7c10979cb30e59caf80ff48d3a54c2b711447962d。固定原公开参考与相同候选，根order_by来自持久化审阅表，并核对SQL哈希和真实列meta。原始600条候选SQL本轮全部重新执行，失败即重建会话43次。

原始候选SHA256：2068a6c84ba1ad47e00cc2a66bb301c4d3c17a9d1a85e5bec42dc2df66c631bb。这里的6条excluded均为Q33在六个公开系统（O-R、O-S、S-R、S-S、G-R、G-S）下各1条：公开原始参考不可用，无法做同口径评分对齐，故保留记录但不计入594条比较分母；不是本轮候选执行失败，也不是当前题库Q33尚未验证（其修订参考已经完整复算）。对比600条（含这6条历史excluded）：3条wrong→correct，0条反向，0条其他判定变化。其余仍错记录的原因、匹配参考及敏感性诊断均不变；三个转正记录的诊断随correct清空，不能误报为‘本轮诊断全不变’。逐条完整对照见scorer_ordered_ties_600.json。

| 系统 | 题号 | 原判定／诊断 | 新判定 | 原因 |
|---|---|---|---|---|
| O-S | Q27 | wrong / string_or_label_only | correct | 同一排序块中的合法换序 |
| S-R | Q88 | wrong / string_or_label_only | correct | 同一排序块中的合法换序 |
| S-S | Q27 | wrong / string_or_label_only | correct | 同一排序块中的合法换序 |

判定计数从251 correct／304 wrong／39 exec_error／6 excluded变为254／301／39／6。与干净旧基线的复执行变化0。严格准确率从251/594（42.3%）变为254/594（42.8%）；错题label-only从15降为12，格式敏感性上界仍266/594（44.8%）。

与公开strict的一致率从521/594变为520/594（87.5%），analytical从487/594变为486/594（81.8%）。两条Q27属于用户有意允许的并列换序，公开strict原判fail；Q88原strict为pass，修正一个误判。因此一致条数净减1，不是增加判错。旧515/594、519/594、520/594、521/594等各轮口径与已通过G0的历史事实保留，本报告追加新契约证据，不覆盖或自动重批检查点。

## 最终参考／契约分开归因

使用同一SHA匹配的本轮600条执行记录，题库侧重新构造原参考并做四轴复评：仅契约3条变化（全部wrong→correct）；仅参考43条变化（24条wrong→correct、19条correct→wrong）；联合47条变化（28条wrong→correct、19条correct→wrong）；基准复执行0变化。契约与参考有交互，不能把3和43直接相加。当前确定性题522条记录联合为253 correct／239 wrong／30 exec_error，另有6条历史excluded和72条judge示例。

原43条correct→wrong审计队列是相对#36修订参考的另一基线，其中36条仅差空组、新增参考恢复30条、剩余13条按裁决保留；它与“仅参考轴43条变化”不是同一集合。现有分组／嵌套Top-N覆盖7/122题，其独立实现阶段变化0；本轮新增的有序块契约变化3，分开记录。新22题改写不在外部600候选范围内，不能用此600证明新题质量。完整四轴记录在题库PR #14的audit/rules-order-final-impact.json/md。

## 性能改动独立验收与耗时

最终源码又在同一批新执行记录上、固定旧契约（不提供order_by，保留逐位置比较并告警）与main基线比较：600条判定、原因、匹配参考和敏感性诊断全部0变化，见scorer_final_performance_600.json。候选缓存SHA与排序契约复验相同；此独立对照不重复执行SQL，也不把新契约的3条转正算入性能等价。

性能阶段此前已实际比较600条完整判定和诊断，均0变化（scorer_early_reject_diagnostics.json，源码SHA0b693d1a…）。该阶段与本次排序契约变化分别保存，旧证据不冒充新语义的零变化。最终源码的大行集复测见scorer_ordered_ties_performance.json，计时为完整score_detailed，不含输入构造，计分限10秒，构造另限30秒：

| 合成情形 | 行数 | main基线 | 最终实现 |
|---|---:|---:|---:|
| NULL不可能匹配、无数值投影 | 600000 | 4.431秒 | 0.883秒 |
| 投影精确相等 | 600000 | 计分超过10秒 | 2.093秒 |
| 投影不等 | 600000 | 计分超过10秒 | 3.544秒 |

100行的三个情形新旧判定、原因、诊断完全一致；60万行两个旧版超时没有取得完成输出，不把超时当成已完成的等价对照。等价保证另由完整600条字段对照和合成测试提供。旧中间阶段超时记录保留。

## 检查与复现

评分器／选择／校验器123项测试通过；追加离线harness与仓库路径检查通过，排除会打开主chdb的15项集成测试。合成覆盖块内换序、跨块换序、Top-N前缀、恰好N行、重复行、复合键、额外列、固定精度、缺键告警及旧标量匹配保留。题库另用当前Q27/Q87/Q88及EN27/EN88实际参考验证前缀并列换序均判对。所有SQL仅打开chdb-eval，无模型调用和新依赖。

设置SEMDEBT_EVAL_DIR和SEMDEBT_DATA_DIR后：

```sh
uv run python scripts/validate_scorer_fast_paths.py \
  --baseline-ref b8fba71 \
  --candidate-audit "$SEMDEBT_EVAL_DIR/audit/orphan-group-impact.json" \
  --order-registry "$SEMDEBT_EVAL_DIR/audit/ordered-rules-review.json" \
  --allow-tie-improvements --reexecute-candidates \
  --output /tmp/scorer-ordered-ties.json
uv run pytest -q tests/test_scorer.py tests/test_selection.py tests/test_validate_scorer.py
```

五题改写与162份参考的最新交接在题库PR #14；T05b须按新题意独立重算后再比对。未宣告独立核对、T06标注或eval-v1/harness-v1冻结完成。

同步main #51时仅手工合并BOARD状态文档；评分器、selection及量纲源码与本报告复验哈希完全一致，未沿用任何发生代码冲突前的测试结论。

复现命令使用rebase后仍在本分支历史中的b8fba71；其评分器SHA与本次实际基线26c45ea完全相同。JSON保留实际执行时的提交号，不改写历史证据。
