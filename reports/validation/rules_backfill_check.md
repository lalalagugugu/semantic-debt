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
