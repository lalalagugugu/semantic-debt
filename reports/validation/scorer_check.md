# T02 评分器对齐检查

- 重跑日期：2026-10-15
- 外部 run：`paper-2026-04-22`
- 执行库：`$SEMDEBT_DATA_DIR/chdb-eval`；没有打开主库。
- 已执行 600 条；Q33 六条因公开参考不可用而单列，不进入594条的比率分母。

## 历史数字（G0/G4 必须保留）

修复前 strict 为 **515/594（86.7%）**；排除11条有意更宽差异后为 **515/583（88.3%）**。原68条复核主分类为：参考列缺失28、标签或列组合14、额外候选行9、公开工件/重执行差异7、舍入/相对误差4、行序与验证流程3、执行环境不兼容2、参考度量缺失1。8条改类完整保留于 `scorer_check_review.md`；历史类别账本不能被本次剩余差异数覆盖。

## 本次结果

- strict 一致：**519/594（87.4%）**。
- 排除本次仍存在的 9 条有意更宽差异：**519/585（88.7%）**。
- analytical 一致：479/594（80.6%）。
- 原因不明：0。

| 系统 | 可比较 | strict一致 | 我们更宽 | 我们更严 |
|---|---:|---:|---:|---:|
| O-R | 99 | 91 | 2 | 6 |
| O-S | 99 | 85 | 2 | 12 |
| S-R | 99 | 91 | 2 | 6 |
| S-S | 99 | 85 | 3 | 11 |
| G-R | 99 | 86 | 4 | 9 |
| G-S | 99 | 81 | 3 | 15 |

## 三条缺陷的修复证据

1. `ordered` 要求元数据与最终外层 ORDER BY 同时成立；窗口/子查询的排序不作为最终排序。O-R/O-S Q22现按无序完整行集比较，结果见全量表。
2. 固定单线程运行，Top-N从完整排序域构造参考。使用参考已投影的排序值精确识别并列；Q88沿用其已有两位小数，排除未舍入浮点排序边界的不稳定。行编码固定同值前缀行序，每个参考三次成员哈希必须一致，否则报错停止。0.5%结果容差不再扩大并列组。
3. 舍入差异实测：S-S Q24约0.70%/0.53%；O-S Q90最高约2.10%；G-S Q29约12.40%；S-S Q99最高约17.13%。不能统称小于1%。待裁决问题#7（近零量容差）仍待用户决定，未改冻结第2条。

运行条件：`{'version': '"26.9.2.1"', 'max_threads': 1, 'max_execution_time': 30}`。

| 题号 | 完整边界参考行数 | 三次哈希一致 | SHA256 |
|---|---:|---|---|
| Q07 | 14 | 是（3次） | `07417f2fe7d49e62b9b7fb977b407f438cb255ab4f0a7d68eb0b1e097c2973da` |
| Q25 | 1 | 是（3次） | `f18e76a775d585de932fc656766a310c323a23291eda970e12933f17cd53a412` |
| Q27 | 444 | 是（3次） | `0d239190f53864c7392fbdf73ce1dbc72c1788d532a10722d3232eaf7efb0e59` |
| Q46 | 1 | 是（3次） | `be42f1801bf3f6a4fd6209e657488f38b585061c7d00085ab9708f41053e7f27` |
| Q73 | 10 | 是（3次） | `3112318da77c2784459c4a5ffb5457128c797eb7fb68a2d00552adc6fade8aa5` |
| Q79 | 306 | 是（3次） | `d85441f941694aaf1622697299ef903c6821b124d212c0634bad234036b43bb2` |
| Q87 | 20 | 是（3次） | `6d284f5d7d261dc737ed1f4cfecc88e06dadd9071c3df185512d416bd48f995c` |
| Q88 | 26 | 是（3次） | `1b8a8b82ce90d04bda6efcf14827d944f9329a1d0417ac9e848a1a8406e87c23` |

两次独立会话均重跑600条；全部8个Top-N参考边界哈希跨会话一致。Q88每次均为26行，两次会话内各三次检查一致。首次运行用于复现核对；最终诊断代码的第二次运行作为本报告依据。

修复后的判定变化：O-R/O-S Q22从wrong改为correct；O-S/S-S Q27因不再用0.5%容差合并不同排序值，从correct改为wrong。因此历史11条有意更宽差异在本次只剩9条，历史68条非有意放宽差异在本次只剩66条；不能为维持旧计数而保留已修复的问题。

## 本次剩余主分类与系统性影响

主分类按裁决后的68条逐项账本固定，先记录具名主因，再保留复合次因；不是机械按评分器首个失败码归类。历史Q22问题修复后如已一致，移出本次差异但保留历史账本。

| 类别 | 本次条数 | 系统性影响/规则依据 |
|---|---:|---|
| 参考列缺失 | 28 | 第3条：所有单元缺参考列均判错，包含问句未要求的辅助列；会系统性降低输出较简洁单元的严格准确率。 |
| 标签或列组合 | 14 | 第2/3条：只去字符串首尾空格，不拼姓名、不翻译标签；对所有单元施加格式敏感性。 |
| 额外候选行 | 9 | 第1/4条：完整结果集与Top-N行数约束；输出超集的单元均受罚，缺列等复合次因另记。 |
| 公开工件/重执行差异 | 7 | 属于外部基线的抽样/执行差异，不是全部单元的评分规则变化；六条Q14已由抽样解释，只有G-R Q30根因交T03跟进。 |
| 舍入/相对误差 | 4 | 第2条：0.5%相对误差在近零量放大舍入差异，会给全部单元引入与语义层无关的测量噪声；待裁决，不改判定。 |
| 行序与验证流程 | 1 | 第4条：修掉任意参考物理行序；同值前缀的严格行序仍可能影响所有Top-N单元，边界成员按确定性精确并列组验证。 |
| 执行环境不兼容 | 2 | 按本地执行态记exec_error；特定函数生成风格的单元会受本地能力限制，T11/T19须单列环境不兼容。 |
| 参考度量缺失 | 1 | 第3条：额外派生量不能替代参考度量；各单元必须输出全部参考度量。 |

## 格式敏感性（不改变判定）

严格准确率为 **245/594（41.2%）**；加上数值投影匹配的 14 条判错结果，格式敏感性上界为 **259/594（43.6%）**。这不是与外部judge的一致率。

wrong标记计数：`{'structure_mismatch': 141, 'numeric_mismatch': 151, 'string_or_label_only': 14, 'no_numeric_reference': 4}`。exec_error/refused/excluded不被格式放宽挽回。

数值投影保留联合行匹配、完整行数、NULL、排序、Top-N及每一数值参考列；删除非数值列只产生报告层上界，不证明标签指向同一实体。数字编码的维度（如月份）也视为数值列：改成文字时保守地不算纯格式挽回；没有角色元数据时不猜业务含义。纯文本参考标为no_numeric_reference，结构不符单列，不当作数值计算错。

## 全部strict差异与次因

| 系统 | 题号 | 我们 | strict | 主分类 | 说明/次因 |
|---|---|---|---|---|---|
| O-R | Q14 | correct | fail | 公开工件/重执行差异 | Q14：公开仅100行工件，本地完整18869行匹配；只能确认工件/抽样差异，不能断言底层数据漂移。 |
| O-R | Q32 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| O-R | Q35 | wrong | pass | 参考列缺失 | 候选保留四个分拆姓名列，但用键替代职位列；并非姓名改写。 |
| O-R | Q64 | wrong | pass | 标签或列组合 | 值表示或姓名列组合不同；额外列不会恢复所需的原始参考列。 |
| O-R | Q70 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| O-R | Q80 | wrong | pass | 额外候选行 | 多行之外，同时缺参考计数列；题意与参考截断是否一致属于参考口径问题。 |
| O-R | Q88 | wrong | pass | 标签或列组合 | 值表示或姓名列组合不同；额外列不会恢复所需的原始参考列。 |
| O-R | Q96 | correct | fail | 百分数等价 | 冻结规则第4/5/2条有意更宽（按类别）。 |
| O-S | Q14 | correct | fail | 公开工件/重执行差异 | Q14：公开仅100行工件，本地完整18869行匹配；只能确认工件/抽样差异，不能断言底层数据漂移。 |
| O-S | Q32 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| O-S | Q35 | wrong | pass | 参考列缺失 | 同 O-R：参考职位列未输出。 |
| O-S | Q45 | wrong | pass | 额外候选行 | 候选306行、参考10行；完整结果行数不符。 |
| O-S | Q63 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| O-S | Q66 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| O-S | Q70 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| O-S | Q75 | wrong | pass | 额外候选行 | 候选1470行、参考25行；完整结果行数不符。 |
| O-S | Q81 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| O-S | Q83 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| O-S | Q88 | wrong | pass | 标签或列组合 | 值表示或姓名列组合不同；额外列不会恢复所需的原始参考列。 |
| O-S | Q90 | wrong | pass | 舍入/相对误差 | 所有参考度量均在候选中；小幅 pp 值舍入导致最高约 2.10% 相对差异。 |
| O-S | Q95 | wrong | pass | 参考度量缺失 | 参考比值列未输出，额外差值/增幅列不能替代。 |
| O-S | Q96 | correct | fail | 百分数等价 | 冻结规则第4/5/2条有意更宽（按类别）。 |
| S-R | Q14 | correct | fail | 公开工件/重执行差异 | Q14：公开仅100行工件，本地完整18869行匹配；只能确认工件/抽样差异，不能断言底层数据漂移。 |
| S-R | Q32 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| S-R | Q35 | wrong | pass | 标签或列组合 | 职位仍在；姓名分别合并，参考的四个姓名列不可直接映射。不是丢失业务信息。 |
| S-R | Q37 | correct | fail | 百分数等价 | 冻结规则第4/5/2条有意更宽（按类别）。 |
| S-R | Q45 | wrong | pass | 额外候选行 | 候选306行、参考10行；完整结果行数不符。 |
| S-R | Q70 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| S-R | Q81 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| S-R | Q88 | wrong | pass | 行序与验证流程 | 候选姓名已拼接；严格前缀内同值成员顺序不同，边界成员也可不同；不属于姓名拆分。 |
| S-S | Q14 | correct | fail | 公开工件/重执行差异 | Q14：公开仅100行工件，本地完整18869行匹配；只能确认工件/抽样差异，不能断言底层数据漂移。 |
| S-S | Q24 | wrong | pass | 舍入/相对误差 | 舍入导致两处约0.70%和0.53%差异，超过0.5%。 |
| S-S | Q35 | wrong | pass | 标签或列组合 | 同 S-R：合并姓名导致列数减少，主因应是表示方式。 |
| S-S | Q63 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| S-S | Q64 | correct | fail | 百分数等价 | 冻结规则第4/5/2条有意更宽（按类别）。 |
| S-S | Q66 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| S-S | Q70 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| S-S | Q75 | wrong | pass | 额外候选行 | 候选1470行、参考25行；完整结果行数不符。 |
| S-S | Q80 | wrong | pass | 额外候选行 | 同 O-R Q80，多行与缺列并存。 |
| S-S | Q82 | wrong | pass | 参考列缺失 | 缺职位列，候选用键替代；不是缺度量。 |
| S-S | Q83 | correct | fail | 数值容差 | 冻结规则第4/5/2条有意更宽（按类别）。 |
| S-S | Q88 | wrong | pass | 标签或列组合 | 值表示或姓名列组合不同；额外列不会恢复所需的原始参考列。 |
| S-S | Q92 | wrong | pass | 额外候选行 | 多行之外，缺参考百分比列，用成本列替代；不是单纯超集。 |
| S-S | Q99 | wrong | pass | 舍入/相对误差 | 舍入分类成立，但不能声称均 <1%；近零值相对差异约17.13%。 |
| G-R | Q07 | correct | fail | 边界并列 | 冻结规则第4/5/2条有意更宽（按类别）。 |
| G-R | Q08 | exec_error | pass | 执行环境不兼容 | 独立重执行复现 UNKNOWN_FUNCTION；属于环境差异，不是结果比对器 bug。 |
| G-R | Q14 | correct | fail | 公开工件/重执行差异 | Q14：公开仅100行工件，本地完整18869行匹配；只能确认工件/抽样差异，不能断言底层数据漂移。 |
| G-R | Q22 | wrong | pass | 标签或列组合 | 姓名合并导致列减少；同时参考无最终排序，不能把物理行序作判据。 |
| G-R | Q30 | correct | fail | 公开工件/重执行差异 | Q30：重执行全部31行相符，公开候选窗口值确实不同；根因尚不能仅凭工件断定。 |
| G-R | Q32 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| G-R | Q45 | wrong | pass | 额外候选行 | 候选306行、参考10行；完整结果行数不符。 |
| G-R | Q59 | exec_error | pass | 执行环境不兼容 | 独立重执行复现 UNKNOWN_FUNCTION；属于环境差异，不是结果比对器 bug。 |
| G-R | Q63 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| G-R | Q68 | wrong | pass | 标签或列组合 | 值表示或姓名列组合不同；额外列不会恢复所需的原始参考列。 |
| G-R | Q83 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| G-R | Q88 | wrong | pass | 标签或列组合 | 值表示或姓名列组合不同；额外列不会恢复所需的原始参考列。 |
| G-R | Q96 | correct | fail | 百分数等价 | 冻结规则第4/5/2条有意更宽（按类别）。 |
| G-S | Q14 | correct | fail | 公开工件/重执行差异 | Q14：公开仅100行工件，本地完整18869行匹配；只能确认工件/抽样差异，不能断言底层数据漂移。 |
| G-S | Q23 | wrong | pass | 标签或列组合 | 值表示或姓名列组合不同；额外列不会恢复所需的原始参考列。 |
| G-S | Q26 | wrong | pass | 标签或列组合 | 值表示或姓名列组合不同；额外列不会恢复所需的原始参考列。 |
| G-S | Q29 | wrong | pass | 舍入/相对误差 | 舍入分类成立；相对差异约12.40%，并非 <1%。 |
| G-S | Q63 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| G-S | Q64 | correct | fail | 百分数等价 | 冻结规则第4/5/2条有意更宽（按类别）。 |
| G-S | Q66 | wrong | pass | 参考列缺失 | 缺订单数之外，同时存在季度标签改写。 |
| G-S | Q68 | wrong | pass | 标签或列组合 | 值表示或姓名列组合不同；额外列不会恢复所需的原始参考列。 |
| G-S | Q69 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| G-S | Q72 | wrong | pass | 标签或列组合 | 值表示或姓名列组合不同；额外列不会恢复所需的原始参考列。 |
| G-S | Q77 | wrong | pass | 参考列缺失 | 缺前月金额之外，同时存在日期/月份表示差异。 |
| G-S | Q78 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| G-S | Q81 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| G-S | Q83 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| G-S | Q84 | wrong | pass | 参考列缺失 | 参考至少一列缺失；列数与公开说明、本地输出支持该主因。 |
| G-S | Q88 | wrong | pass | 标签或列组合 | 值表示或姓名列组合不同；额外列不会恢复所需的原始参考列。 |
| G-S | Q92 | wrong | pass | 额外候选行 | 多行之外，缺参考收入列；百分比单位转换本身允许。 |
| G-S | Q96 | correct | fail | 百分数等价 | 冻结规则第4/5/2条有意更宽（按类别）。 |

## 全部600条判定（含analytical与敏感性）

| 系统 | 题号 | 我们 | strict | analytical | 原因 | 敏感性 |
|---|---|---|---|---|---|---|
| O-R | Q01 | correct | pass | pass | matched | — |
| O-R | Q02 | correct | pass | pass | matched | — |
| O-R | Q03 | correct | pass | pass | matched | — |
| O-R | Q04 | correct | pass | pass | matched | — |
| O-R | Q05 | correct | pass | pass | matched | — |
| O-R | Q06 | correct | pass | pass | matched | — |
| O-R | Q07 | correct | pass | pass | matched | — |
| O-R | Q08 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q09 | correct | pass | pass | matched | — |
| O-R | Q10 | correct | pass | pass | matched | — |
| O-R | Q11 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q12 | correct | pass | pass | matched | — |
| O-R | Q13 | wrong | fail | fail | values | string_or_label_only |
| O-R | Q14 | correct | fail | fail | matched | — |
| O-R | Q15 | correct | pass | pass | matched | — |
| O-R | Q16 | correct | pass | pass | matched | — |
| O-R | Q17 | wrong | fail | pass | values | numeric_mismatch |
| O-R | Q18 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q19 | correct | pass | pass | matched | — |
| O-R | Q20 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q21 | correct | pass | pass | matched | — |
| O-R | Q22 | correct | pass | pass | matched | — |
| O-R | Q23 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q24 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q25 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q26 | correct | pass | pass | matched | — |
| O-R | Q27 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q28 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q29 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q30 | correct | pass | pass | matched | — |
| O-R | Q31 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q32 | wrong | pass | pass | missing_columns | numeric_mismatch |
| O-R | Q33 | excluded | fail | fail | published_reference_unavailable | — |
| O-R | Q34 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q35 | wrong | pass | pass | values | no_numeric_reference |
| O-R | Q36 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q37 | wrong | fail | pass | values | numeric_mismatch |
| O-R | Q38 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q39 | exec_error | fail | fail | execution_error | — |
| O-R | Q40 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q41 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q42 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q43 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q44 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q45 | wrong | fail | pass | row_count | structure_mismatch |
| O-R | Q46 | wrong | fail | fail | top_n_row_count | structure_mismatch |
| O-R | Q47 | correct | pass | pass | matched | — |
| O-R | Q48 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q49 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q50 | correct | pass | pass | matched | — |
| O-R | Q51 | correct | pass | pass | matched | — |
| O-R | Q52 | correct | pass | pass | matched | — |
| O-R | Q53 | correct | pass | pass | matched | — |
| O-R | Q54 | correct | pass | pass | matched | — |
| O-R | Q55 | correct | pass | pass | matched | — |
| O-R | Q56 | correct | pass | pass | matched | — |
| O-R | Q57 | correct | pass | pass | matched | — |
| O-R | Q58 | correct | pass | pass | matched | — |
| O-R | Q59 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q60 | correct | pass | pass | matched | — |
| O-R | Q61 | correct | pass | pass | matched | — |
| O-R | Q62 | correct | pass | pass | matched | — |
| O-R | Q63 | wrong | fail | fail | missing_columns | numeric_mismatch |
| O-R | Q64 | wrong | pass | pass | values | numeric_mismatch |
| O-R | Q65 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q66 | wrong | fail | fail | missing_columns | numeric_mismatch |
| O-R | Q67 | correct | pass | pass | matched | — |
| O-R | Q68 | correct | pass | pass | matched | — |
| O-R | Q69 | wrong | fail | pass | missing_columns | numeric_mismatch |
| O-R | Q70 | wrong | pass | pass | missing_columns | numeric_mismatch |
| O-R | Q71 | correct | pass | pass | matched | — |
| O-R | Q72 | wrong | fail | pass | missing_columns | numeric_mismatch |
| O-R | Q73 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q74 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q75 | wrong | fail | pass | row_count | structure_mismatch |
| O-R | Q76 | correct | pass | pass | matched | — |
| O-R | Q77 | exec_error | fail | fail | execution_error | — |
| O-R | Q78 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q79 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q80 | wrong | pass | pass | row_count | structure_mismatch |
| O-R | Q81 | wrong | fail | pass | missing_columns | numeric_mismatch |
| O-R | Q82 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q83 | wrong | fail | pass | missing_columns | numeric_mismatch |
| O-R | Q84 | wrong | fail | fail | missing_columns | numeric_mismatch |
| O-R | Q85 | exec_error | fail | fail | execution_error | — |
| O-R | Q86 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q87 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q88 | wrong | pass | pass | values | string_or_label_only |
| O-R | Q89 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q90 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q91 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q92 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q93 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q94 | wrong | fail | pass | row_count | structure_mismatch |
| O-R | Q95 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q96 | correct | fail | pass | matched | — |
| O-R | Q97 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q98 | wrong | fail | fail | row_count | structure_mismatch |
| O-R | Q99 | wrong | fail | fail | values | numeric_mismatch |
| O-R | Q100 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q01 | correct | pass | pass | matched | — |
| O-S | Q02 | correct | pass | pass | matched | — |
| O-S | Q03 | correct | pass | pass | matched | — |
| O-S | Q04 | correct | pass | pass | matched | — |
| O-S | Q05 | correct | pass | pass | matched | — |
| O-S | Q06 | correct | pass | pass | matched | — |
| O-S | Q07 | correct | pass | pass | matched | — |
| O-S | Q08 | correct | pass | pass | matched | — |
| O-S | Q09 | correct | pass | pass | matched | — |
| O-S | Q10 | wrong | fail | fail | values | numeric_mismatch |
| O-S | Q11 | correct | pass | pass | matched | — |
| O-S | Q12 | correct | pass | pass | matched | — |
| O-S | Q13 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q14 | correct | fail | fail | matched | — |
| O-S | Q15 | correct | pass | pass | matched | — |
| O-S | Q16 | correct | pass | pass | matched | — |
| O-S | Q17 | correct | pass | pass | matched | — |
| O-S | Q18 | correct | pass | pass | matched | — |
| O-S | Q19 | wrong | fail | fail | values | numeric_mismatch |
| O-S | Q20 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q21 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q22 | correct | pass | pass | matched | — |
| O-S | Q23 | correct | pass | pass | matched | — |
| O-S | Q24 | wrong | fail | pass | missing_columns | numeric_mismatch |
| O-S | Q25 | correct | pass | pass | matched | — |
| O-S | Q26 | correct | pass | pass | matched | — |
| O-S | Q27 | wrong | fail | fail | values | string_or_label_only |
| O-S | Q28 | wrong | fail | fail | values | numeric_mismatch |
| O-S | Q29 | wrong | fail | pass | values | numeric_mismatch |
| O-S | Q30 | correct | pass | pass | matched | — |
| O-S | Q31 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q32 | wrong | pass | pass | missing_columns | numeric_mismatch |
| O-S | Q33 | excluded | fail | fail | published_reference_unavailable | — |
| O-S | Q34 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q35 | wrong | pass | pass | values | no_numeric_reference |
| O-S | Q36 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q37 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q38 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q39 | exec_error | fail | fail | execution_error | — |
| O-S | Q40 | wrong | fail | fail | values | numeric_mismatch |
| O-S | Q41 | correct | pass | pass | matched | — |
| O-S | Q42 | wrong | fail | pass | row_count | structure_mismatch |
| O-S | Q43 | wrong | fail | pass | row_count | structure_mismatch |
| O-S | Q44 | wrong | fail | fail | missing_columns | numeric_mismatch |
| O-S | Q45 | wrong | pass | pass | row_count | structure_mismatch |
| O-S | Q46 | wrong | fail | fail | top_n_row_count | structure_mismatch |
| O-S | Q47 | correct | pass | pass | matched | — |
| O-S | Q48 | exec_error | fail | fail | execution_error | — |
| O-S | Q49 | exec_error | fail | fail | execution_error | — |
| O-S | Q50 | wrong | fail | pass | missing_columns | numeric_mismatch |
| O-S | Q51 | correct | pass | pass | matched | — |
| O-S | Q52 | correct | pass | pass | matched | — |
| O-S | Q53 | correct | pass | pass | matched | — |
| O-S | Q54 | correct | pass | pass | matched | — |
| O-S | Q55 | correct | pass | pass | matched | — |
| O-S | Q56 | correct | pass | pass | matched | — |
| O-S | Q57 | correct | pass | pass | matched | — |
| O-S | Q58 | correct | pass | pass | matched | — |
| O-S | Q59 | correct | pass | pass | matched | — |
| O-S | Q60 | correct | pass | pass | matched | — |
| O-S | Q61 | correct | pass | pass | matched | — |
| O-S | Q62 | correct | pass | pass | matched | — |
| O-S | Q63 | wrong | pass | pass | missing_columns | numeric_mismatch |
| O-S | Q64 | correct | pass | pass | matched | — |
| O-S | Q65 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q66 | wrong | pass | pass | missing_columns | numeric_mismatch |
| O-S | Q67 | correct | pass | pass | matched | — |
| O-S | Q68 | correct | pass | pass | matched | — |
| O-S | Q69 | correct | pass | pass | matched | — |
| O-S | Q70 | wrong | pass | pass | missing_columns | numeric_mismatch |
| O-S | Q71 | correct | pass | pass | matched | — |
| O-S | Q72 | correct | pass | pass | matched | — |
| O-S | Q73 | correct | pass | pass | matched | — |
| O-S | Q74 | wrong | fail | fail | values | numeric_mismatch |
| O-S | Q75 | wrong | pass | pass | row_count | structure_mismatch |
| O-S | Q76 | correct | pass | pass | matched | — |
| O-S | Q77 | exec_error | fail | fail | execution_error | — |
| O-S | Q78 | correct | pass | pass | matched | — |
| O-S | Q79 | wrong | fail | fail | values | numeric_mismatch |
| O-S | Q80 | wrong | fail | pass | row_count | structure_mismatch |
| O-S | Q81 | wrong | pass | pass | missing_columns | numeric_mismatch |
| O-S | Q82 | wrong | fail | fail | values | numeric_mismatch |
| O-S | Q83 | wrong | pass | pass | missing_columns | numeric_mismatch |
| O-S | Q84 | wrong | fail | fail | missing_columns | numeric_mismatch |
| O-S | Q85 | wrong | fail | fail | missing_columns | numeric_mismatch |
| O-S | Q86 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q87 | correct | pass | pass | matched | — |
| O-S | Q88 | wrong | pass | pass | values | string_or_label_only |
| O-S | Q89 | correct | pass | pass | matched | — |
| O-S | Q90 | wrong | pass | pass | values | numeric_mismatch |
| O-S | Q91 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q92 | wrong | fail | pass | row_count | structure_mismatch |
| O-S | Q93 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q94 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q95 | wrong | pass | pass | values | numeric_mismatch |
| O-S | Q96 | correct | fail | pass | matched | — |
| O-S | Q97 | wrong | fail | fail | row_count | structure_mismatch |
| O-S | Q98 | wrong | fail | pass | row_count | structure_mismatch |
| O-S | Q99 | exec_error | fail | fail | execution_error | — |
| O-S | Q100 | wrong | fail | pass | row_count | structure_mismatch |
| S-R | Q01 | correct | pass | pass | matched | — |
| S-R | Q02 | correct | pass | pass | matched | — |
| S-R | Q03 | correct | pass | pass | matched | — |
| S-R | Q04 | correct | pass | pass | matched | — |
| S-R | Q05 | correct | pass | pass | matched | — |
| S-R | Q06 | correct | pass | pass | matched | — |
| S-R | Q07 | correct | pass | pass | matched | — |
| S-R | Q08 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q09 | correct | pass | pass | matched | — |
| S-R | Q10 | correct | pass | pass | matched | — |
| S-R | Q11 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q12 | correct | pass | pass | matched | — |
| S-R | Q13 | correct | pass | pass | matched | — |
| S-R | Q14 | correct | fail | fail | matched | — |
| S-R | Q15 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q16 | correct | pass | pass | matched | — |
| S-R | Q17 | wrong | fail | pass | values | numeric_mismatch |
| S-R | Q18 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q19 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q20 | correct | pass | pass | matched | — |
| S-R | Q21 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q22 | exec_error | fail | fail | execution_error | — |
| S-R | Q23 | exec_error | fail | fail | execution_error | — |
| S-R | Q24 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q25 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q26 | correct | pass | pass | matched | — |
| S-R | Q27 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q28 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q29 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q30 | correct | pass | pass | matched | — |
| S-R | Q31 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q32 | wrong | pass | pass | missing_columns | numeric_mismatch |
| S-R | Q33 | excluded | fail | fail | published_reference_unavailable | — |
| S-R | Q34 | exec_error | fail | fail | execution_error | — |
| S-R | Q35 | wrong | pass | pass | missing_columns | no_numeric_reference |
| S-R | Q36 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q37 | correct | fail | pass | matched | — |
| S-R | Q38 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q39 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q40 | correct | pass | pass | matched | — |
| S-R | Q41 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q42 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q43 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q44 | correct | pass | pass | matched | — |
| S-R | Q45 | wrong | pass | pass | row_count | structure_mismatch |
| S-R | Q46 | wrong | fail | fail | top_n_row_count | structure_mismatch |
| S-R | Q47 | correct | pass | pass | matched | — |
| S-R | Q48 | exec_error | fail | fail | execution_error | — |
| S-R | Q49 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q50 | correct | pass | pass | matched | — |
| S-R | Q51 | correct | pass | pass | matched | — |
| S-R | Q52 | correct | pass | pass | matched | — |
| S-R | Q53 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q54 | correct | pass | pass | matched | — |
| S-R | Q55 | correct | pass | pass | matched | — |
| S-R | Q56 | correct | pass | pass | matched | — |
| S-R | Q57 | correct | pass | pass | matched | — |
| S-R | Q58 | correct | pass | pass | matched | — |
| S-R | Q59 | correct | pass | pass | matched | — |
| S-R | Q60 | correct | pass | pass | matched | — |
| S-R | Q61 | correct | pass | pass | matched | — |
| S-R | Q62 | correct | pass | pass | matched | — |
| S-R | Q63 | wrong | fail | fail | missing_columns | numeric_mismatch |
| S-R | Q64 | exec_error | fail | fail | execution_error | — |
| S-R | Q65 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q66 | wrong | fail | fail | missing_columns | numeric_mismatch |
| S-R | Q67 | correct | pass | pass | matched | — |
| S-R | Q68 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q69 | wrong | fail | fail | missing_columns | numeric_mismatch |
| S-R | Q70 | wrong | pass | pass | missing_columns | numeric_mismatch |
| S-R | Q71 | correct | pass | pass | matched | — |
| S-R | Q72 | correct | pass | pass | matched | — |
| S-R | Q73 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q74 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q75 | wrong | fail | pass | row_count | structure_mismatch |
| S-R | Q76 | correct | pass | pass | matched | — |
| S-R | Q77 | exec_error | fail | fail | execution_error | — |
| S-R | Q78 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q79 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q80 | wrong | fail | pass | row_count | structure_mismatch |
| S-R | Q81 | wrong | pass | pass | missing_columns | numeric_mismatch |
| S-R | Q82 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q83 | wrong | fail | pass | missing_columns | numeric_mismatch |
| S-R | Q84 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q85 | exec_error | fail | fail | execution_error | — |
| S-R | Q86 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q87 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q88 | wrong | pass | pass | values | string_or_label_only |
| S-R | Q89 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q90 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q91 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q92 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q93 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q94 | wrong | fail | pass | row_count | structure_mismatch |
| S-R | Q95 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q96 | exec_error | fail | fail | execution_error | — |
| S-R | Q97 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q98 | wrong | fail | fail | row_count | structure_mismatch |
| S-R | Q99 | wrong | fail | fail | values | numeric_mismatch |
| S-R | Q100 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q01 | correct | pass | pass | matched | — |
| S-S | Q02 | correct | pass | pass | matched | — |
| S-S | Q03 | correct | pass | pass | matched | — |
| S-S | Q04 | correct | pass | pass | matched | — |
| S-S | Q05 | correct | pass | pass | matched | — |
| S-S | Q06 | correct | pass | pass | matched | — |
| S-S | Q07 | correct | pass | pass | matched | — |
| S-S | Q08 | correct | pass | pass | matched | — |
| S-S | Q09 | correct | pass | pass | matched | — |
| S-S | Q10 | wrong | fail | fail | values | numeric_mismatch |
| S-S | Q11 | correct | pass | pass | matched | — |
| S-S | Q12 | correct | pass | pass | matched | — |
| S-S | Q13 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q14 | correct | fail | fail | matched | — |
| S-S | Q15 | correct | pass | pass | matched | — |
| S-S | Q16 | correct | pass | pass | matched | — |
| S-S | Q17 | correct | pass | pass | matched | — |
| S-S | Q18 | correct | pass | pass | matched | — |
| S-S | Q19 | wrong | fail | fail | values | numeric_mismatch |
| S-S | Q20 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q21 | correct | pass | pass | matched | — |
| S-S | Q22 | exec_error | fail | fail | execution_error | — |
| S-S | Q23 | correct | pass | pass | matched | — |
| S-S | Q24 | wrong | pass | pass | values | numeric_mismatch |
| S-S | Q25 | correct | pass | pass | matched | — |
| S-S | Q26 | correct | pass | pass | matched | — |
| S-S | Q27 | wrong | fail | fail | values | string_or_label_only |
| S-S | Q28 | wrong | fail | fail | values | numeric_mismatch |
| S-S | Q29 | wrong | fail | pass | values | numeric_mismatch |
| S-S | Q30 | correct | pass | pass | matched | — |
| S-S | Q31 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q32 | wrong | fail | pass | missing_columns | numeric_mismatch |
| S-S | Q33 | excluded | fail | fail | published_reference_unavailable | — |
| S-S | Q34 | correct | pass | pass | matched | — |
| S-S | Q35 | wrong | pass | pass | missing_columns | no_numeric_reference |
| S-S | Q36 | correct | pass | pass | matched | — |
| S-S | Q37 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q38 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q39 | exec_error | fail | fail | execution_error | — |
| S-S | Q40 | correct | pass | pass | matched | — |
| S-S | Q41 | correct | pass | pass | matched | — |
| S-S | Q42 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q43 | wrong | fail | pass | row_count | structure_mismatch |
| S-S | Q44 | correct | pass | pass | matched | — |
| S-S | Q45 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q46 | wrong | fail | fail | top_n_row_count | structure_mismatch |
| S-S | Q47 | correct | pass | pass | matched | — |
| S-S | Q48 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q49 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q50 | correct | pass | pass | matched | — |
| S-S | Q51 | correct | pass | pass | matched | — |
| S-S | Q52 | correct | pass | pass | matched | — |
| S-S | Q53 | correct | pass | pass | matched | — |
| S-S | Q54 | correct | pass | pass | matched | — |
| S-S | Q55 | correct | pass | pass | matched | — |
| S-S | Q56 | correct | pass | pass | matched | — |
| S-S | Q57 | correct | pass | pass | matched | — |
| S-S | Q58 | correct | pass | pass | matched | — |
| S-S | Q59 | correct | pass | pass | matched | — |
| S-S | Q60 | correct | pass | pass | matched | — |
| S-S | Q61 | correct | pass | pass | matched | — |
| S-S | Q62 | correct | pass | pass | matched | — |
| S-S | Q63 | wrong | pass | pass | missing_columns | numeric_mismatch |
| S-S | Q64 | correct | fail | pass | matched | — |
| S-S | Q65 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q66 | wrong | pass | pass | missing_columns | numeric_mismatch |
| S-S | Q67 | correct | pass | pass | matched | — |
| S-S | Q68 | correct | pass | pass | matched | — |
| S-S | Q69 | wrong | fail | fail | missing_columns | numeric_mismatch |
| S-S | Q70 | wrong | pass | pass | missing_columns | numeric_mismatch |
| S-S | Q71 | correct | pass | pass | matched | — |
| S-S | Q72 | correct | pass | pass | matched | — |
| S-S | Q73 | correct | pass | pass | matched | — |
| S-S | Q74 | exec_error | fail | fail | execution_error | — |
| S-S | Q75 | wrong | pass | pass | row_count | structure_mismatch |
| S-S | Q76 | correct | pass | pass | matched | — |
| S-S | Q77 | correct | pass | pass | matched | — |
| S-S | Q78 | wrong | fail | pass | missing_columns | numeric_mismatch |
| S-S | Q79 | wrong | fail | fail | top_n_row_count | structure_mismatch |
| S-S | Q80 | wrong | pass | pass | row_count | structure_mismatch |
| S-S | Q81 | exec_error | fail | fail | execution_error | — |
| S-S | Q82 | wrong | pass | pass | values | string_or_label_only |
| S-S | Q83 | correct | fail | fail | matched | — |
| S-S | Q84 | wrong | fail | fail | missing_columns | numeric_mismatch |
| S-S | Q85 | exec_error | fail | fail | execution_error | — |
| S-S | Q86 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q87 | correct | pass | pass | matched | — |
| S-S | Q88 | wrong | pass | pass | values | string_or_label_only |
| S-S | Q89 | correct | pass | pass | matched | — |
| S-S | Q90 | correct | pass | pass | matched | — |
| S-S | Q91 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q92 | wrong | pass | pass | row_count | structure_mismatch |
| S-S | Q93 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q94 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q95 | wrong | fail | pass | values | numeric_mismatch |
| S-S | Q96 | correct | pass | pass | matched | — |
| S-S | Q97 | wrong | fail | fail | row_count | structure_mismatch |
| S-S | Q98 | exec_error | fail | fail | execution_error | — |
| S-S | Q99 | wrong | pass | pass | values | numeric_mismatch |
| S-S | Q100 | wrong | fail | pass | row_count | structure_mismatch |
| G-R | Q01 | correct | pass | pass | matched | — |
| G-R | Q02 | correct | pass | pass | matched | — |
| G-R | Q03 | correct | pass | pass | matched | — |
| G-R | Q04 | correct | pass | pass | matched | — |
| G-R | Q05 | correct | pass | pass | matched | — |
| G-R | Q06 | correct | pass | pass | matched | — |
| G-R | Q07 | correct | fail | pass | matched | — |
| G-R | Q08 | exec_error | pass | pass | execution_environment_incompatible | — |
| G-R | Q09 | correct | pass | pass | matched | — |
| G-R | Q10 | exec_error | fail | fail | execution_environment_incompatible | — |
| G-R | Q11 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q12 | correct | pass | pass | matched | — |
| G-R | Q13 | correct | pass | pass | matched | — |
| G-R | Q14 | correct | fail | fail | matched | — |
| G-R | Q15 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q16 | correct | pass | pass | matched | — |
| G-R | Q17 | wrong | fail | pass | missing_columns | numeric_mismatch |
| G-R | Q18 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q19 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q20 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q21 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q22 | wrong | pass | pass | missing_columns | string_or_label_only |
| G-R | Q23 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q24 | exec_error | fail | fail | execution_error | — |
| G-R | Q25 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q26 | correct | pass | pass | matched | — |
| G-R | Q27 | wrong | fail | fail | missing_columns | numeric_mismatch |
| G-R | Q28 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q29 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q30 | correct | fail | fail | matched | — |
| G-R | Q31 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q32 | wrong | pass | pass | missing_columns | numeric_mismatch |
| G-R | Q33 | excluded | excluded | excluded | published_reference_unavailable | — |
| G-R | Q34 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q35 | exec_error | fail | fail | execution_error | — |
| G-R | Q36 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q37 | wrong | fail | pass | values | numeric_mismatch |
| G-R | Q38 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q39 | exec_error | fail | fail | execution_error | — |
| G-R | Q40 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q41 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q42 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q43 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q44 | correct | pass | pass | matched | — |
| G-R | Q45 | wrong | pass | pass | row_count | structure_mismatch |
| G-R | Q46 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q47 | correct | pass | pass | matched | — |
| G-R | Q48 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q49 | exec_error | fail | fail | execution_error | — |
| G-R | Q50 | correct | pass | pass | matched | — |
| G-R | Q51 | correct | pass | pass | matched | — |
| G-R | Q52 | correct | pass | pass | matched | — |
| G-R | Q53 | correct | pass | pass | matched | — |
| G-R | Q54 | correct | pass | pass | matched | — |
| G-R | Q55 | correct | pass | pass | matched | — |
| G-R | Q56 | correct | pass | pass | matched | — |
| G-R | Q57 | correct | pass | pass | matched | — |
| G-R | Q58 | correct | pass | pass | matched | — |
| G-R | Q59 | exec_error | pass | pass | execution_environment_incompatible | — |
| G-R | Q60 | correct | pass | pass | matched | — |
| G-R | Q61 | correct | pass | pass | matched | — |
| G-R | Q62 | correct | pass | pass | matched | — |
| G-R | Q63 | wrong | pass | pass | missing_columns | numeric_mismatch |
| G-R | Q64 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q65 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q66 | wrong | fail | fail | missing_columns | numeric_mismatch |
| G-R | Q67 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q68 | wrong | pass | pass | values | string_or_label_only |
| G-R | Q69 | wrong | fail | pass | missing_columns | numeric_mismatch |
| G-R | Q70 | wrong | fail | fail | missing_columns | numeric_mismatch |
| G-R | Q71 | correct | pass | pass | matched | — |
| G-R | Q72 | correct | pass | pass | matched | — |
| G-R | Q73 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q74 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q75 | wrong | fail | pass | row_count | structure_mismatch |
| G-R | Q76 | correct | pass | pass | matched | — |
| G-R | Q77 | wrong | fail | pass | missing_columns | numeric_mismatch |
| G-R | Q78 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q79 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q80 | exec_error | fail | fail | execution_error | — |
| G-R | Q81 | wrong | fail | fail | missing_columns | numeric_mismatch |
| G-R | Q82 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q83 | wrong | pass | pass | missing_columns | numeric_mismatch |
| G-R | Q84 | wrong | fail | fail | missing_columns | numeric_mismatch |
| G-R | Q85 | exec_error | fail | fail | execution_error | — |
| G-R | Q86 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q87 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q88 | wrong | pass | pass | values | string_or_label_only |
| G-R | Q89 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q90 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q91 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q92 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q93 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q94 | wrong | fail | pass | row_count | structure_mismatch |
| G-R | Q95 | exec_error | fail | fail | execution_error | — |
| G-R | Q96 | correct | fail | pass | matched | — |
| G-R | Q97 | wrong | fail | fail | row_count | structure_mismatch |
| G-R | Q98 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q99 | wrong | fail | fail | values | numeric_mismatch |
| G-R | Q100 | wrong | fail | fail | row_count | structure_mismatch |
| G-S | Q01 | correct | pass | pass | matched | — |
| G-S | Q02 | correct | pass | pass | matched | — |
| G-S | Q03 | correct | pass | pass | matched | — |
| G-S | Q04 | correct | pass | pass | matched | — |
| G-S | Q05 | correct | pass | pass | matched | — |
| G-S | Q06 | correct | pass | pass | matched | — |
| G-S | Q07 | correct | pass | pass | matched | — |
| G-S | Q08 | correct | pass | pass | matched | — |
| G-S | Q09 | correct | pass | pass | matched | — |
| G-S | Q10 | correct | pass | pass | matched | — |
| G-S | Q11 | correct | pass | pass | matched | — |
| G-S | Q12 | correct | pass | pass | matched | — |
| G-S | Q13 | wrong | fail | fail | row_count | structure_mismatch |
| G-S | Q14 | correct | fail | fail | matched | — |
| G-S | Q15 | correct | pass | pass | matched | — |
| G-S | Q16 | correct | pass | pass | matched | — |
| G-S | Q17 | wrong | fail | pass | row_count | structure_mismatch |
| G-S | Q18 | wrong | fail | fail | values | string_or_label_only |
| G-S | Q19 | wrong | fail | fail | values | numeric_mismatch |
| G-S | Q20 | wrong | fail | fail | row_count | structure_mismatch |
| G-S | Q21 | correct | pass | pass | matched | — |
| G-S | Q22 | exec_error | fail | fail | execution_error | — |
| G-S | Q23 | wrong | pass | pass | values | numeric_mismatch |
| G-S | Q24 | wrong | fail | pass | missing_columns | numeric_mismatch |
| G-S | Q25 | wrong | fail | fail | values | numeric_mismatch |
| G-S | Q26 | wrong | pass | pass | values | numeric_mismatch |
| G-S | Q27 | wrong | fail | fail | missing_columns | numeric_mismatch |
| G-S | Q28 | wrong | fail | fail | values | numeric_mismatch |
| G-S | Q29 | wrong | pass | pass | values | numeric_mismatch |
| G-S | Q30 | correct | pass | pass | matched | — |
| G-S | Q31 | wrong | fail | fail | row_count | structure_mismatch |
| G-S | Q32 | wrong | fail | pass | missing_columns | numeric_mismatch |
| G-S | Q33 | excluded | excluded | excluded | published_reference_unavailable | — |
| G-S | Q34 | correct | pass | pass | matched | — |
| G-S | Q35 | exec_error | fail | fail | execution_error | — |
| G-S | Q36 | wrong | fail | pass | row_count | structure_mismatch |
| G-S | Q37 | wrong | fail | fail | row_count | structure_mismatch |
| G-S | Q38 | wrong | fail | fail | row_count | structure_mismatch |
| G-S | Q39 | exec_error | fail | fail | execution_error | — |
| G-S | Q40 | wrong | fail | fail | values | numeric_mismatch |
| G-S | Q41 | correct | pass | pass | matched | — |
| G-S | Q42 | wrong | fail | fail | row_count | structure_mismatch |
| G-S | Q43 | wrong | fail | pass | row_count | structure_mismatch |
| G-S | Q44 | correct | pass | pass | matched | — |
| G-S | Q45 | wrong | fail | pass | row_count | structure_mismatch |
| G-S | Q46 | wrong | fail | fail | values | numeric_mismatch |
| G-S | Q47 | correct | pass | pass | matched | — |
| G-S | Q48 | wrong | fail | fail | row_count | structure_mismatch |
| G-S | Q49 | exec_error | fail | fail | execution_error | — |
| G-S | Q50 | wrong | fail | pass | missing_columns | numeric_mismatch |
| G-S | Q51 | correct | pass | pass | matched | — |
| G-S | Q52 | correct | pass | pass | matched | — |
| G-S | Q53 | correct | pass | pass | matched | — |
| G-S | Q54 | correct | pass | pass | matched | — |
| G-S | Q55 | correct | pass | pass | matched | — |
| G-S | Q56 | correct | pass | pass | matched | — |
| G-S | Q57 | correct | pass | pass | matched | — |
| G-S | Q58 | correct | pass | pass | matched | — |
| G-S | Q59 | correct | pass | pass | matched | — |
| G-S | Q60 | correct | pass | pass | matched | — |
| G-S | Q61 | correct | pass | pass | matched | — |
| G-S | Q62 | correct | pass | pass | matched | — |
| G-S | Q63 | wrong | pass | pass | missing_columns | numeric_mismatch |
| G-S | Q64 | correct | fail | pass | matched | — |
| G-S | Q65 | wrong | fail | pass | row_count | structure_mismatch |
| G-S | Q66 | wrong | pass | pass | missing_columns | numeric_mismatch |
| G-S | Q67 | wrong | fail | fail | row_count | structure_mismatch |
| G-S | Q68 | wrong | pass | pass | values | string_or_label_only |
| G-S | Q69 | wrong | pass | pass | missing_columns | numeric_mismatch |
| G-S | Q70 | wrong | fail | fail | missing_columns | numeric_mismatch |
| G-S | Q71 | correct | pass | pass | matched | — |
| G-S | Q72 | wrong | pass | pass | values | numeric_mismatch |
| G-S | Q73 | correct | pass | pass | matched | — |
| G-S | Q74 | exec_error | fail | fail | execution_error | — |
| G-S | Q75 | wrong | fail | pass | row_count | structure_mismatch |
| G-S | Q76 | correct | pass | pass | matched | — |
| G-S | Q77 | wrong | pass | pass | missing_columns | numeric_mismatch |
| G-S | Q78 | wrong | pass | pass | missing_columns | numeric_mismatch |
| G-S | Q79 | wrong | fail | fail | values | numeric_mismatch |
| G-S | Q80 | wrong | fail | pass | row_count | structure_mismatch |
| G-S | Q81 | wrong | pass | pass | missing_columns | numeric_mismatch |
| G-S | Q82 | wrong | fail | fail | values | numeric_mismatch |
| G-S | Q83 | wrong | pass | pass | missing_columns | numeric_mismatch |
| G-S | Q84 | wrong | pass | pass | missing_columns | numeric_mismatch |
| G-S | Q85 | exec_error | fail | fail | execution_error | — |
| G-S | Q86 | wrong | fail | fail | row_count | structure_mismatch |
| G-S | Q87 | correct | pass | pass | matched | — |
| G-S | Q88 | wrong | pass | pass | values | string_or_label_only |
| G-S | Q89 | wrong | fail | pass | missing_columns | numeric_mismatch |
| G-S | Q90 | wrong | fail | pass | row_count | structure_mismatch |
| G-S | Q91 | correct | pass | pass | matched | — |
| G-S | Q92 | wrong | pass | pass | row_count | structure_mismatch |
| G-S | Q93 | exec_error | fail | fail | execution_environment_incompatible | — |
| G-S | Q94 | wrong | fail | fail | row_count | structure_mismatch |
| G-S | Q95 | wrong | fail | pass | values | numeric_mismatch |
| G-S | Q96 | correct | fail | pass | matched | — |
| G-S | Q97 | wrong | fail | fail | row_count | structure_mismatch |
| G-S | Q98 | wrong | fail | fail | values | numeric_mismatch |
| G-S | Q99 | correct | pass | pass | matched | — |
| G-S | Q100 | wrong | fail | fail | row_count | structure_mismatch |

## 复现与验收边界

```bash
uv run pytest
uv run python scripts/validate_scorer.py --output /tmp/t02-scorer-check-ruling.json --report reports/validation/scorer_check.md
```

运行前设置SEMDEBT_EVAL_DIR、SEMDEBT_DATA_DIR；固定本报告的运行版本，单进程独占chdb-eval。所有候选原样执行，重执行或参考失败不静默重试。

T03只跟进G-R Q30；其余Q14不是未解释的数据漂移。T05/T05b/T06落实跨执行器可复现边界组要求，不能用本卡三次SQL重复取代跨厂商独立重算。G0/G4须同时披露历史低一致率、当前数字、系统性影响和敏感性上界，不能声称跨厂商独立核对已完成。
