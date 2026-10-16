# 评分规则补齐：600条影响复验

本报告仅题号及汇总，不含题干、SQL或结果行。会话污染复验另存；本次固定全局量化与容差。

执行600条；Q33的6条excluded保留，可比较分母594。执行失败即关闭并重建会话，共43次。

原公开参考＋新分组契约：strict一致521/594；analytical一致487/594；排除有意更宽后的描述性分母为521/583。

历史strict一致521/594（87.7%）、排除11条有意更宽后521/583（89.4%）保留，不覆盖。

reference_only固定旧扁平比较，combined为当前题库参考＋新契约；二者只在确定性题记录。judge参考仅是示例，不能用“与例子不同”代替judge结论。参考修复轴同时包含T04既有修订及本次孤儿修复，不将其全部归为Q74或模型改善。

每条四轴判定保存在配套JSON。下表逐条列出任何判定变化；historical_clean差异是复执行稳定性轴，不能直接归为新契约。

| 系统 | 题号 | 干净历史 | 本轮旧契约 | 仅契约 | 仅参考 | 联合 |
|---|---|---|---|---|---|---|
| O-R | Q19 | correct | correct | correct | wrong | wrong |
| O-R | Q83 | wrong | wrong | wrong | correct | correct |
| O-R | Q94 | wrong | wrong | wrong | correct | correct |
| O-S | Q10 | wrong | wrong | wrong | correct | correct |
| O-S | Q19 | wrong | wrong | wrong | correct | correct |
| O-S | Q25 | correct | correct | correct | wrong | wrong |
| O-S | Q28 | wrong | wrong | wrong | correct | correct |
| O-S | Q43 | wrong | wrong | wrong | correct | correct |
| O-S | Q75 | wrong | wrong | wrong | correct | correct |
| O-S | Q83 | wrong | wrong | wrong | correct | correct |
| O-S | Q87 | correct | correct | correct | wrong | wrong |
| S-R | Q13 | correct | correct | correct | wrong | wrong |
| S-R | Q19 | wrong | wrong | wrong | correct | correct |
| S-R | Q20 | correct | correct | correct | wrong | wrong |
| S-R | Q75 | wrong | wrong | wrong | correct | correct |
| S-S | Q10 | wrong | wrong | wrong | correct | correct |
| S-S | Q19 | wrong | wrong | wrong | correct | correct |
| S-S | Q20 | wrong | wrong | wrong | correct | correct |
| S-S | Q25 | correct | correct | correct | wrong | wrong |
| S-S | Q28 | wrong | wrong | wrong | correct | correct |
| S-S | Q43 | wrong | wrong | wrong | correct | correct |
| S-S | Q75 | wrong | wrong | wrong | correct | correct |
| S-S | Q87 | correct | correct | correct | wrong | wrong |
| G-R | Q19 | wrong | wrong | wrong | correct | correct |
| G-R | Q74 | wrong | wrong | wrong | wrong | correct |
| G-R | Q75 | wrong | wrong | wrong | correct | correct |
| G-R | Q83 | wrong | wrong | wrong | correct | correct |
| G-S | Q19 | wrong | wrong | wrong | correct | correct |
| G-S | Q20 | wrong | wrong | wrong | correct | correct |
| G-S | Q25 | wrong | wrong | wrong | correct | correct |
| G-S | Q43 | wrong | wrong | wrong | correct | correct |
| G-S | Q65 | wrong | wrong | wrong | correct | correct |
| G-S | Q75 | wrong | wrong | wrong | correct | correct |
| G-S | Q83 | wrong | wrong | wrong | correct | correct |
| G-S | Q87 | correct | correct | correct | wrong | wrong |

汇总：contract_changed=0；reference_changed=34；combined_changed=35；baseline_reexecution_changed=0

G0已通过的历史事实保留；新的契约／参考影响交用户评估，不能自动撤销或重批G0。T05b跨引擎核对与第二轮新题落地仍是冻结前置。

仅契约翻转0条，基线复执行变化0条；仅参考诊断变化34条、联合变化35条。35条中包括T04既有题意/参考修订与本次修复，不能把它们全部算作本次rules、孤儿修复或语义层增益。

有意更宽的排除沿用T02的具名类别及量纲atol诊断，共11条；其余“我们判对、strict判错”包含公开工件差异，不能一并当有意放宽排除。

本轮T02基准一致率及G0旧证据数字保持不变；当前题库参考的35条差异逐条保留，交后续T19/G0审阅。harness须先支持逐参考整份rules覆盖再使用新版题库，不能只透传题级rules。

## 2026-10-16：合入#35后rebase并重新执行

本轮以main的9fd1e6d为基线，实际验证重放后的代码5075d95。Git自动完成合并；#35的scripts/validate_scorer.py、tests/test_validate_scorer.py及reports/validation/scorer_check.md与该main逐字一致。

- rebase后重新执行scorer、selection、validate_scorer及离线harness测试：126 passed、16 skipped；跳过项依赖数据库或渲染上下文。
- 重新执行官方validate_scorer.py，实际完成600条；按(system, question_id)比较rebase前后，600个键完全一致，判定变化0条。
- 本轮correct251、wrong304、exec_error39、excluded6；strict一致521/594（87.7%）、analytical一致487/594；会话重置43次。
- 同批exact_counts诊断仍仅S-S Q83一条correct→wrong；该诊断不代表rebase前后变化。
- 配套私有题库也在rebase后通过122题／137份参考的严格复算及rules校验。
- 另串行重跑600条规则影响复验；旧契约、仅契约、仅参考、联合判定及具名更宽排除标记，相对rebase前均0变化。分组契约下仍为strict521/594、analytical487/594、排除既定更宽差异后521/583；会话重置43次。
- 同批内部仅契约0条、仅参考34条、联合35条变化，与前文一致；这些不是rebase新增差异。
- 另有O-R Q85及S-R Q34两条执行错误文本变化（别名建议／超时毫秒数），exec_error判定均未变；新错误文本保留在外部完整审计中。
- 官方输出SHA-256：a5cafd9aeba5976d2296879d7796c75876f1e8567a929f839327da7f2829b250；影响输出SHA-256：ecbb3f3315926fbb769b95ec8593684f4fb3c268405e2d323d7667dc3d6c06fb。完整输出及原始候选仍在外部数据目录，未复制题目、SQL或参考行。

本节只记录本次实际执行的结果；前文历史数字不作覆盖。

## 2026-10-16：同步#38并解决BOARD冲突

再次rebase到main的9562d85；保留六列状态表及12项待办，第11、12项与该main逐字一致，补回本PR已实现及已复验的状态。相对前次已验证的0b2dcbb，评分器、选择器、校验脚本、测试及依赖文件均无差异；新上游只涉及文档与任务元数据。

本次实际运行相关离线测试，126 passed、16 skipped，并校验表格列数、待办唯一性及冲突标记。没有再次执行600条；上一节两轮600条的证据对应相同的程序代码，判定变化0的结论保持。

## 2026-10-16：T05正式参考收尾后的最终600条

本轮主分支由已合并#36后的main新建，随后同步main21cacd9；评分器、选择器、全局量纲及validate_scorer与此前main95575fd逐字一致。题库也从最新main新开分支，未复用T05-work。

- 条件(d)：7/122题包含分组／嵌套Top-N（外部Q22、Q71、Q74、Q85、Q98；新题Q117、Q119）。
- 第二轮22题正式SQL落地；122题148份参考从头重算并另一次严格复算通过。外部100题119份，新题22题29份；类型来自实际返回meta，外部逐参考量纲推断表留题库供过目。
- 购买事件全122题扫描，18题21份原参考执行两种算法；9题不同并新增9份去重参考（Q26、Q33、Q36、Q76、Q80、Q89、Q115、Q116、Q122）。全部订单总体保持冻结定义。依据2026-10-16-return-only-rows-and-purchase-events.md；已知冻结层口径选择及双解处理须由T19披露。
- 20题24份INNER／LEFT全部实测；字面21份不同、3份相同。Q73保留事实对象粒度后Top-10相同，因此正确粒度为20份不同、4份无输出影响。包含Q42-1量化差分尾差，不宣称全是业务金额损失。剩余3条INNER路径有无影响证据；Q33当前两份SQL参考已完整离线复算，不是未验证。
- Q79的306成员及量纲策略SHA已存题库，当前重算一致；冻结门槛为T05b独立pandas成员多重集一致，缺证据拒绝放行。T05b已开工，尚未取得独立通过结论。

| 比较轴 | 变化条数 |
|---|---:|
| 基线复执行 vs 干净基线 | 0 |
| 仅契约 vs 原公开参考旧契约 | 0 |
| 仅参考 vs 原公开参考旧契约 | 73 |
| 当前参考＋契约 vs 原公开参考旧契约 | 74 |
| 当前参考＋契约 vs #36当时修订参考 | 43 |

最后43条全部correct→wrong：37条行数不同、6条分组覆盖不全；是本轮参考修复后的增量，不是契约变化。联合74条相对原公开参考为49条correct→wrong、25条wrong→correct。起点不同，不能相加。

仅契约轴correct251／wrong304／exec_error39／excluded6，strict521/594、analytical487/594，排除既定11条有意更宽后521/583，均保持历史数字。修订参考轴不以judge示例作闭集：原Q33六条排除、其他12题72条judge保持；522条确定性结果为correct220／wrong272／exec_error30，不能与594条原公开基线直接比较准确率。600条只覆盖外部100题。

实际执行600条，失败后重置43次。原始候选及逐条四轴保存在外部数据目录／私有题库；主仓库只列题号及汇总。两个未完成轮次各执行121条，在大行集敏感性投影／列排列处中止；正式验收runner省去非判定的投影并加NULL必要条件等价早拒绝，合成对照正式评分器通过后从头执行全600，不改生产评分标准。最新main相关离线检查132 passed、1 skipped、15 deselected，明确排除主chdb集成函数。

| 系统 | 题号 | #36修订参考 | 本轮修订参考 | 原因 |
|---|---|---|---|---|
| O-R | Q21 | correct | wrong | row_count |
| O-R | Q61 | correct | wrong | row_count |
| O-R | Q62 | correct | wrong | row_count |
| O-R | Q67 | correct | wrong | row_count |
| O-R | Q71 | correct | wrong | selection_group_coverage |
| O-R | Q76 | correct | wrong | row_count |
| O-S | Q11 | correct | wrong | row_count |
| O-S | Q61 | correct | wrong | row_count |
| O-S | Q62 | correct | wrong | row_count |
| O-S | Q67 | correct | wrong | row_count |
| O-S | Q71 | correct | wrong | selection_group_coverage |
| O-S | Q76 | correct | wrong | row_count |
| O-S | Q90 | correct | wrong | row_count |
| S-R | Q61 | correct | wrong | row_count |
| S-R | Q62 | correct | wrong | row_count |
| S-R | Q67 | correct | wrong | row_count |
| S-R | Q71 | correct | wrong | selection_group_coverage |
| S-R | Q76 | correct | wrong | row_count |
| S-S | Q11 | correct | wrong | row_count |
| S-S | Q20 | correct | wrong | row_count |
| S-S | Q21 | correct | wrong | row_count |
| S-S | Q24 | correct | wrong | row_count |
| S-S | Q34 | correct | wrong | row_count |
| S-S | Q61 | correct | wrong | row_count |
| S-S | Q62 | correct | wrong | row_count |
| S-S | Q67 | correct | wrong | row_count |
| S-S | Q71 | correct | wrong | selection_group_coverage |
| S-S | Q76 | correct | wrong | row_count |
| S-S | Q90 | correct | wrong | row_count |
| S-S | Q99 | correct | wrong | row_count |
| G-R | Q61 | correct | wrong | row_count |
| G-R | Q62 | correct | wrong | row_count |
| G-R | Q71 | correct | wrong | selection_group_coverage |
| G-R | Q76 | correct | wrong | row_count |
| G-S | Q11 | correct | wrong | row_count |
| G-S | Q20 | correct | wrong | row_count |
| G-S | Q21 | correct | wrong | row_count |
| G-S | Q34 | correct | wrong | row_count |
| G-S | Q61 | correct | wrong | row_count |
| G-S | Q62 | correct | wrong | row_count |
| G-S | Q71 | correct | wrong | selection_group_coverage |
| G-S | Q76 | correct | wrong | row_count |
| G-S | Q99 | correct | wrong | row_count |

最终输出SHA256：5648377e268b201f1d6a55225847dc93c2c5c8550c0c148a06a20506e6236939；完整原始候选SHA256：b6cc390d63452b8c412cc0845dd7631a92e07a8b4b782b43cccde6a100e772fb。G0的历史原公开参考证据保留；修订参考的影响提交用户审阅，不当作模型能力变化或自动重批G0。T05b／T06及英文原始参考rules接线仍按分工推进。
