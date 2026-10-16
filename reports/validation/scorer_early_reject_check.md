> 本文件保留等价性能阶段的历史证据。T11 #49已合并；最终同PR追加有序块比较，最新源码和新契约影响见scorer_ordered_ties_check.md，不能把旧零变化结论当作排序语义未改变。

# 评分器等价提前拒绝与数值投影快路

依据2026-10-16空产品属性组与评分器裁决第二、三节。正式判定只加可证明不匹配的必要条件；数值投影诊断只在归一化后的完整行多重集精确相等时通过，不引入容差。实现与验收已完成；按用户顺序，等T11 #49合并后再开独立评分器PR。

## 实现范围

完整平面参考含NULL且候选任一列均无NULL时，不可能在任意列排列下覆盖完整参考，直接返回原values原因。先保留原宽度、行数及规则检查；Top-N可能合法地不选择含NULL的并列成员，故不使用该拒绝；分组选择沿用原路径。仅对已知内置值使用必要条件，自定义标量仍走原比较。

诊断保留原数值列投影、额外候选列、列排列及重复行计数。使用原非数值桶的字符串去空白、类型归一化；bool不与数值0/1混同。不作量化、相对容差或百分数换算；有序题保留行序。只在存在精确匹配映射时返回原string_or_label_only诊断。精确匹配不成立、Top-N、非有限数值或不支持的对象均继续原匹配路径。正式correct判定没有新增快速通过。

## 600条完整输出对照

同一批全新600条候选SQL执行结果，原始候选SHA256：b04e2e006e8eb2518142c621a89a6d9cd05ce72d2f8ff92b283d8c10ebc8dff3。固定原公开参考及契约，新旧代码分别实际调用完整score_detailed；逐条比较outcome、reason、matched_ref、sensitivity。执行错误原因以完整字符串比较的等价SHA256保存，报告不带原始错误SQL或数据行。

- 对照600条（594条评分，历史Q33的6条excluded状态保持）：判定变化0，诊断及其余字段变化0。
- 基线提交d8a4a9422d1291e6c846611d1c345292a4c5b00e；评分器SHA256：3d7fb59b1ac205dce95883d266f35441fbc16f7cd7709189af9fea270a635838。
- 新评分器SHA256：0b693d1a03f1c35961963abb6f2860f51fc9ecc8c4976f71ba7db5ce00a4094d。
- 逐条新旧完整输出及耗时：scorer_early_reject_diagnostics.json。校验脚本同时确认量纲、选择实现依赖与基线完全相同。

这项代码等价验收固定公开参考；当前修订题库的参考影响单独重跑600条，不混作性能改动效果。该轮固定旧148份参考变化0；新增13份可接受参考后，原43条退步中恢复30条。剩余13条为Q76的6条及Q20/Q21/Q34的7条。原43条中36条仅差空属性组，另7条是产品键或明细。当前161份参考已全部从头重算并严格复算；相对原公开参考，仅参考轴43条变化，联合轴44条变化。分组／嵌套Top-N覆盖7/122题，仅契约轴判定变化0，strict521/594、analytical487/594保持。当前Q33参考已完整验证；公开基线excluded不能用来放行未验证的题库参考。

## 隔离进程耗时

仅合成输入，无数据库、模型或真实参考内容。计时覆盖完整score_detailed，输入构造不计时；构造另限30秒，计分限10秒。每个实现单独进程，超时保留为超时，不当作已完成结果。

| 合成情形 | 行数 | 旧版 | 新版 | 新版诊断 |
|---|---:|---:|---:|---|
| NULL不可能匹配、无数值投影 | 600000 | 3.276秒 | 0.602秒 | no_numeric_reference |
| 数值投影精确相等 | 600000 | 计分超过10秒 | 1.782秒 | string_or_label_only |
| 数值投影不等 | 600000 | 计分超过10秒 | 3.582秒 | numeric_mismatch |

三种情形在100行时，新旧判定、原因及诊断均相同；大行集两个旧版超时未取得完成输出，不能声称这两项是实测完成输出对照，等价证据另由600条完整输出与合成测试提供。完整记录见scorer_early_reject_final_performance.json。此前只有提前拒绝、尚未加入投影快速通过的中间测试也保留；其中投影相等大行集的新旧版均超时，不覆盖这段失败证据。

## 检查与复现

评分器、分组选择及校验器测试110项通过；路径检查39项通过、1项跳过；离线harness检查排除15项打开主chdb的集成测试。环境检查初次缺少路径变量而失败，补齐变量后通过，没有为此改动产品代码或测试。所有SQL复验仅打开chdb-eval，无付费调用和新依赖。

设置SEMDEBT_EVAL_DIR、SEMDEBT_DATA_DIR后，在主仓库运行：

```sh
uv run python scripts/validate_scorer_fast_paths.py \
  --baseline-ref d8a4a9422d1291e6c846611d1c345292a4c5b00e \
  --candidate-audit "$SEMDEBT_EVAL_DIR/audit/orphan-group-impact.json" \
  --output /tmp/scorer-fast-path-comparison.json
uv run python scripts/benchmark_scorer_early_reject.py \
  --baseline-ref d8a4a9422d1291e6c846611d1c345292a4c5b00e \
  --sizes 100 600000 --timeout-seconds 10 \
  --output /tmp/scorer-fast-path-performance.json
uv run pytest -q tests/test_scorer.py tests/test_selection.py tests/test_validate_scorer.py
```

题库独立PR #13负责Q79当前边界快照、可选参考及T06 A/B/C任务卡。T05b成员集合与全部新增参考的独立pandas核对仍为冻结前置；本轮不宣告T06标注、eval-v1或harness-v1冻结完成。

补充：600条中的6条excluded全部是Q33在六个公开系统下各1条；因公开原始参考不可用而沿用历史排除，不是性能改动造成的执行失败。当前题库修订Q33参考已完整复算；同口径对齐分母仍为594。
