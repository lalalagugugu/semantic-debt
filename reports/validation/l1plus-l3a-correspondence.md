# L1+ / L3a 逐条对应核对

复现：`uv run python -m render.l1plus`。

共 109 条：形式化 30 条；注解保留 79 条。编号集合、节、全部字段（递归去掉 rev）、标量类型与列表顺序一致。

形式化按条目计：存在 OWL 结构或 SHACL shape 即归此类；不代表该条全部口径均已形式化。所有条目的原始字段仍完整保留为注解树，复杂定义不转成规则。

OWL 表达类、子类、对象属性、数据属性、实例别名和科目实例树；类成员定义开头的明确字面等式用 SHACL hasValue，H10 的单场景要求用 minCount / maxCount / in。未从行数、示例或别名子集推导必填、闭合枚举或范围约束。

L3a 测的是「形式化写法对写 SQL 的模型有没有帮助」，不含可执行规则；不运行 SHACL 引擎，不编译查询。可执行形式化放在第二期 L3b。

核对器解析生成器使用的 Turtle 子集，并逐字段反解比较；同时比较 OWL / SHACL 结构。它不是通用 RDF 或 OWL 推理器。

| 节 | 编号 | 表达方式 |
|---|---|---|
| general_rules | G01 | 注解保留 |
| clarifications | A01 | 注解保留 |
| clarifications | A02 | 注解保留 |
| clarifications | A03 | 注解保留 |
| clarifications | A04 | 注解保留 |
| clarifications | A05 | 注解保留 |
| clarifications | A06 | 注解保留 |
| clarifications | A07 | 注解保留 |
| clarifications | A08 | 注解保留 |
| clarifications | A09 | 注解保留 |
| clarifications | A10 | 注解保留 |
| clarifications | A11 | 注解保留 |
| clarifications | A12 | 注解保留 |
| clarifications | A13 | 注解保留 |
| clarifications | A14 | 注解保留 |
| clarifications | A15 | 注解保留 |
| clarifications | A16 | 注解保留 |
| clarifications | A17 | 注解保留 |
| clarifications | A18 | 注解保留 |
| clarifications | A19 | 注解保留 |
| clarifications | A20 | 注解保留 |
| clarifications | A21 | 注解保留 |
| clarifications | A22 | 注解保留 |
| clarifications | A23 | 注解保留 |
| clarifications | A24 | 注解保留 |
| clarifications | A25 | 注解保留 |
| clarifications | A26 | 注解保留 |
| clarifications | A27 | 注解保留 |
| clarifications | A28 | 注解保留 |
| clarifications | A29 | 注解保留 |
| clarifications | A30 | 注解保留 |
| clarifications | A31 | 注解保留 |
| clarifications | A32 | 注解保留 |
| clarifications | A33 | 注解保留 |
| clarifications | A34 | 注解保留 |
| clarifications | A35 | 注解保留 |
| clarifications | A36 | 注解保留 |
| clarifications | A37 | 注解保留 |
| clarifications | A38 | 注解保留 |
| clarifications | A39 | 注解保留 |
| clarifications | A40 | 注解保留 |
| clarifications | A41 | 注解保留 |
| concepts | D01 | 注解保留 |
| concepts | D02 | 注解保留 |
| concepts | D03 | 注解保留 |
| concepts | D04 | 注解保留 |
| concepts | D05 | 注解保留 |
| concepts | D05b | 注解保留 |
| concepts | D06 | 注解保留 |
| concepts | D06b | 注解保留 |
| concepts | D06c | 注解保留 |
| concepts | D07 | 注解保留 |
| concepts | D07b | 注解保留 |
| concepts | D08 | 注解保留 |
| concepts | D09 | 注解保留 |
| concepts | D10 | 注解保留 |
| concepts | D11 | 注解保留 |
| concepts | D12 | 注解保留 |
| concepts | D13 | 注解保留 |
| concepts | D14 | 注解保留 |
| concepts | D15 | 注解保留 |
| concepts | D16 | 注解保留 |
| concepts | D17 | 注解保留 |
| concepts | D18 | 注解保留 |
| concepts | D19 | 注解保留 |
| concepts | D20 | 注解保留 |
| concepts | D21 | 注解保留 |
| concepts | D22 | 注解保留 |
| concepts | D23 | 注解保留 |
| concepts | D24 | 注解保留 |
| concepts | D25 | 注解保留 |
| concepts | D26 | 注解保留 |
| concepts | D27 | 注解保留 |
| concepts | D28 | 注解保留 |
| concepts | D29 | 注解保留 |
| concepts | D30 | 注解保留 |
| concepts | D31 | 注解保留 |
| concepts | D32 | 注解保留 |
| concepts | D33 | 注解保留 |
| aliases | E01 | 形式化 |
| aliases | E02 | 形式化 |
| aliases | E03 | 形式化 |
| aliases | E04 | 形式化 |
| aliases | E05 | 形式化 |
| aliases | E06 | 形式化 |
| aliases | E07 | 形式化 |
| aliases | E08 | 形式化 |
| aliases | E09 | 形式化 |
| aliases | E10 | 形式化 |
| aliases | E11 | 形式化 |
| aliases | E12 | 形式化 |
| aliases | E13 | 形式化 |
| aliases | E14 | 形式化 |
| aliases | E15 | 形式化 |
| aliases | E16 | 形式化 |
| aliases | E17 | 形式化 |
| hierarchies | H01 | 形式化 |
| hierarchies | H02 | 形式化 |
| hierarchies | H03 | 形式化 |
| hierarchies | H04 | 形式化 |
| hierarchies | H05 | 形式化 |
| hierarchies | H06 | 形式化 |
| hierarchies | H07 | 形式化 |
| hierarchies | H08 | 形式化 |
| hierarchies | H09 | 形式化 |
| hierarchies | H10 | 形式化 |
| hierarchies | H11 | 形式化 |
| hierarchies | H12 | 形式化 |
| hierarchies | H13 | 形式化 |
