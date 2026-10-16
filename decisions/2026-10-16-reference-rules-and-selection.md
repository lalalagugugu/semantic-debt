# 2026-10-16 逐参考规则与分组／嵌套选择契约

- 授权：用户批准逐参考rules覆盖题级rules，缺省沿用题级；BOARD当前待办第3项批准通用确定性选择及四项条件。
- 范围：评分器纯函数与合成测试；harness适配由Claude Code跟进。语义层、量纲词表、容差与judge路径不变。

## 逐参考覆盖

`score(candidate_rows, refs, rules, *, reference_rules=None)`及`score_detailed`增加可选参数。`reference_rules`与`refs`等长，每项为字典或None。每份参考的有效规则为`{**rules, **override}`；字段整体覆盖，不拼接量纲向量或selection的内部列表。None或未传参数沿用题级规则。先解析全部有效规则，然后逐参考匹配，任一正确即可；列宽及返回类型跟随对应参考。

题库ref.rules与题级rules的读取、覆盖字典和reference_rules的原样传递由harness完成；评分器不读取题库、SQL、列名或题号。缺失rules必须在输入校验时显式拒绝，不得用空值跳过保护。旧三参数接口保持可用。

## rules.selection（version 1）

可选selection包含version=1、stages、output_order。声明selection时，扁平top_n必须为null、tie_columns必须为空，且逐列value_kinds/value_types完整。ordered仍取问句要求与最终外层排序的交集；分组选择本身不强制ordered=true。

每个stage完整声明：

- parent：null为独立根步骤，否则为前面某个stage的索引；父对象的完整身份必须包含在子步骤group_columns中。
- where：显式的标量相等条件列表，每项column/equals；空列表表示不筛选。可用两个独立根步骤表达双路排名，不推断bucket语义。
- group_columns：参考列位置列表；空列表表示全局单组。
- object_columns：组内对象的身份列；非空，与分组列不重叠。
- order_by：非空column/descending列表，支持多键及不同方向；排序键禁止NULL和非有限数值。
- n：正整数；域不足N时只允许全部实际对象，空域不补造对象。

output_order是显式column/descending列表；ordered=true时必填非空，false时必须为空。组选择顺序和最后展示顺序分别声明；例如最低N名可以最终按降序展示。

参考保存每步骤的严格前缀及完整边界。父步骤边界中的每个合法父对象都保留自己的完整后续选择域。评分时先核验候选选择的父对象，再只核验那些父对象下的组覆盖；独立根步骤分别满足。最终叶对象不得重复，候选不得漏组、多选、遗漏严格前缀或返回边界N+k冒充N。每个候选行都须落在已声明叶步骤中。

身份按精确标识比较，字符串去首尾空格；身份不享受0.5%或百分数等价。其余单元格继续使用原结果比较规则。列重排和额外候选列仍获支持。输出顺序按已匹配的参考量化值校验，允许同量化键内部任意顺序。选择域不允许使用候选值重算边界。

排序及边界唯一使用harness/value_units.py的quantize_tie：Decimal十进制字符串、ROUND_HALF_EVEN、amount两位、percentage先除100再六位、ratio/其他数值六位。结果atol及相对容差不得扩大边界。`complete_selection`供参考构建器从完整查询域构造边界，不能由其已截断的输入推导完整性。

## 验证与交接

实现前盘点：目标题集7/122题需核查选择契约，其中外部5题，直接涉及历史候选30/600条；这不是翻转数。必须全量复验，保留原始历史数字、6条excluded及其分母。

会话污染修复、评分契约变化、参考修复分别比较；会话污染比较固定参考和评分器。不得把参考修复变化记作模型改善。T02/G0证据随实际变化更新；G0重新确认由用户决定。

T05b由Claude Code用pandas独立实现同样语义，比较量化键、严格前缀及完整边界成员，不能导入本选择器充当独立验证。尚未跨引擎确认的成员差异阻止eval-v1冻结。

选择题暂不提供丢弃身份列后的数值投影敏感性上界，返回保守的structure_mismatch诊断，避免删除分组身份后产生伪正确；正式判定不受影响。
