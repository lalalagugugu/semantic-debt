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
