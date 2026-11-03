# L3a-full 逐条对应核对（T34）

复现：`uv run python -m render.l3a_full`（写 `build/contexts/SQL-L3a-full.yaml` 与本报告）；测试：`uv run pytest tests/test_l3a_full.py`。

## 怎么核对

- 输入只有 `semantic/source.yaml`（经 `render.context.render_l1`，即 SQL-L1 的上下文）与 `semantic/l1plus.yaml`（`render.l1plus.overlay`，与 SQL-L1plus 的 `l1plus` 节相同）。
- 核对器解析生成的 Turtle（本模块自带的、保留文档顺序的解析器，只认生成器用到的 Turtle 子集：前缀名、字面量、`[ ]` 空白节点、`( )` 列表），再从图里**反解**出 SQL-L1 的整份上下文和 L1+ 的整份 overlay，要求与源**逐字段相等**（含列表顺序、标量类型）。所以下表的「源」与「本体」两列相等不是数出来凑的：少一个字段、改一个字、挂错节点，反解就不相等，渲染直接失败。
- 另查：本体自己命名空间里用到的每个节点都有定义（不悬空）；生成结果可重现。
- 通用解析器复核：`uv run --with rdflib pytest tests/test_l3a_full.py` 用 rdflib 解析同一份 Turtle，三元组数与本模块解析器一致（rdflib 不是项目依赖，未安装时该测试跳过）。
- 不运行 OWL 推理机或 SHACL 引擎，不编译查询。

## L1

| 项 | 源 | 本体 | 形式化 | 注解 |
|---|---|---|---|---|
| 表 | 25 | 25 | 25（OWL 类） | 0 |
| 字段 | 228 | 228 | 228（数据属性，rdfs:domain / rdfs:range） | 0 |
| 枚举值 | 568 | 568 | 568（个体：code + meaning） | 0 |
| 关系 | 48 | 48 | 48（对象属性，Functional / InverseFunctional） | 0 |
| 指标 | 69 | 69 | 13（比率：分子、分母都链接到指标） | 56（其中 34 个有 SQL 表达式） |
| 约定 | 15 | 15 | 0 | 15（适用表、字段、指标是链接） |
| 同义词 | 56 | 56 | 56（说法 → 指标 / 字段的链接） | 0 |
| 多路径默认 | 4 | 4 | 2（全部路径解析成有序关系链） | 2（至少一条路径只有原文） |
| 数据质量 | 15 | 15 | 0 | 15 |

形式化与注解的判定：表、字段、关系、枚举值、同义词本身就是结构（类、属性、个体、链接），计形式化；比率指标的分子、分母恰好是另一个指标名时，链接到该指标（`:numeratorMetric` / `:denominatorMetric`），计形式化；约定、其余指标、数据质量的核心是文字口径，计注解（指标的 SQL 表达式按卡片允许的「注解里的 SQL 片段」保留）。所有原文（描述、口径、理由……）都同时以注解保留。

枚举值以个体表达（`:enumValue [ :code … ; :meaning … ]`），**没有**写成闭合的 `sh:in`：L1 没有声明哪些取值清单是完整的，本卡不从数据推。

## L1+（109 条）

共 109 条：形式化 77 条（71%）；注解 32 条（29%），其中 11 条带 SQL 片段。

判定：该条（含它名下的类、关系、科目节点）除了自身类型、`:ref` 链接和注解之外，还有至少一条 OWL / SHACL 公理、个体或带类型的取值，计形式化；否则计注解。形式化的条目原文仍完整保留，不代表该条每一句都已形式化。

## 三元组

共 8,404 个三元组（列表按 rdf:first / rdf:rest 展开计）：注解 3,082（37%），形式化 5,322（63%）。注解 = 谓词是 rdfs:label、rdfs:comment、skos:altLabel 或本体声明的注解属性。

## 系统消息的 token 数

方法：`harness.run_direct.system_for` 拼出完整系统消息（系统提示 + 语义上下文 + 语法说明），用 harness 的 `estimate_tokens_from_text` 估算（DeepSeek 官方经验比例：中文字符 ≈ 0.6 token，其他字符 ≈ 0.3 token）。是估算，不是分词器的实数；正式运行以 API 返回的用量为准。

「语义上下文」只算 `build/contexts/<单元>.yaml` 的文本；「系统消息」是实际发给模型的整条系统消息。四个单元的系统提示与语法说明逐字节相同（测试核对），差别只在语义上下文。

| 单元 | 系统消息字符数 | 语义上下文（估算 token） | 系统消息（估算 token） | 系统消息对 SQL-L1plus |
|---|---|---|---|---|
| SQL-L1 | 112,842 | 40,254 | 41,084 | 0.62× |
| SQL-L1plus | 180,005 | 65,868 | 66,698 | 1.00× |
| SQL-L3a | 464,859 | 155,639 | 156,469 | 2.35× |
| SQL-L3a-full | 270,305 | 93,879 | 94,709 | 1.42× |

## 逐条

| 节 | 编号 | 表达方式 | SQL 片段 |
|---|---|---|---|
| general_rules | G01 | 注解 |  |
| clarifications | A01 | 形式化 |  |
| clarifications | A02 | 注解 |  |
| clarifications | A03 | 注解 |  |
| clarifications | A04 | 注解 |  |
| clarifications | A05 | 注解 |  |
| clarifications | A06 | 形式化 |  |
| clarifications | A07 | 形式化 | 有 |
| clarifications | A08 | 形式化 |  |
| clarifications | A09 | 注解 | 有 |
| clarifications | A10 | 形式化 | 有 |
| clarifications | A11 | 形式化 |  |
| clarifications | A12 | 形式化 |  |
| clarifications | A13 | 注解 | 有 |
| clarifications | A14 | 注解 |  |
| clarifications | A15 | 形式化 |  |
| clarifications | A16 | 形式化 |  |
| clarifications | A17 | 形式化 |  |
| clarifications | A18 | 形式化 |  |
| clarifications | A19 | 形式化 |  |
| clarifications | A20 | 形式化 |  |
| clarifications | A21 | 注解 | 有 |
| clarifications | A22 | 注解 | 有 |
| clarifications | A23 | 注解 |  |
| clarifications | A24 | 形式化 |  |
| clarifications | A25 | 注解 |  |
| clarifications | A26 | 注解 |  |
| clarifications | A27 | 形式化 |  |
| clarifications | A28 | 注解 |  |
| clarifications | A29 | 注解 |  |
| clarifications | A30 | 注解 | 有 |
| clarifications | A31 | 形式化 |  |
| clarifications | A32 | 形式化 |  |
| clarifications | A33 | 形式化 | 有 |
| clarifications | A34 | 形式化 |  |
| clarifications | A35 | 形式化 |  |
| clarifications | A36 | 注解 |  |
| clarifications | A37 | 形式化 |  |
| clarifications | A38 | 注解 |  |
| clarifications | A39 | 形式化 |  |
| clarifications | A40 | 形式化 |  |
| clarifications | A41 | 形式化 |  |
| concepts | D01 | 形式化 | 有 |
| concepts | D02 | 形式化 | 有 |
| concepts | D03 | 形式化 | 有 |
| concepts | D04 | 注解 | 有 |
| concepts | D05 | 形式化 | 有 |
| concepts | D05b | 形式化 | 有 |
| concepts | D06 | 形式化 | 有 |
| concepts | D06b | 注解 | 有 |
| concepts | D06c | 形式化 |  |
| concepts | D07 | 形式化 |  |
| concepts | D07b | 形式化 |  |
| concepts | D08 | 注解 |  |
| concepts | D09 | 注解 |  |
| concepts | D10 | 形式化 | 有 |
| concepts | D11 | 形式化 | 有 |
| concepts | D12 | 注解 | 有 |
| concepts | D13 | 注解 |  |
| concepts | D14 | 注解 |  |
| concepts | D15 | 注解 | 有 |
| concepts | D16 | 形式化 | 有 |
| concepts | D17 | 形式化 |  |
| concepts | D18 | 注解 | 有 |
| concepts | D19 | 形式化 | 有 |
| concepts | D20 | 形式化 | 有 |
| concepts | D21 | 形式化 |  |
| concepts | D22 | 形式化 |  |
| concepts | D23 | 形式化 |  |
| concepts | D24 | 注解 |  |
| concepts | D25 | 注解 |  |
| concepts | D26 | 注解 | 有 |
| concepts | D27 | 形式化 |  |
| concepts | D28 | 注解 |  |
| concepts | D29 | 形式化 | 有 |
| concepts | D30 | 形式化 |  |
| concepts | D31 | 注解 |  |
| concepts | D32 | 形式化 | 有 |
| concepts | D33 | 形式化 |  |
| aliases | E01 | 形式化 |  |
| aliases | E02 | 形式化 |  |
| aliases | E03 | 形式化 |  |
| aliases | E04 | 形式化 |  |
| aliases | E05 | 形式化 |  |
| aliases | E06 | 形式化 |  |
| aliases | E07 | 形式化 |  |
| aliases | E08 | 形式化 |  |
| aliases | E09 | 形式化 |  |
| aliases | E10 | 形式化 |  |
| aliases | E11 | 形式化 |  |
| aliases | E12 | 形式化 |  |
| aliases | E13 | 形式化 |  |
| aliases | E14 | 形式化 |  |
| aliases | E15 | 形式化 |  |
| aliases | E16 | 形式化 |  |
| aliases | E17 | 形式化 |  |
| hierarchies | H01 | 形式化 |  |
| hierarchies | H02 | 形式化 |  |
| hierarchies | H03 | 形式化 |  |
| hierarchies | H04 | 形式化 |  |
| hierarchies | H05 | 形式化 |  |
| hierarchies | H06 | 形式化 |  |
| hierarchies | H07 | 形式化 |  |
| hierarchies | H08 | 形式化 |  |
| hierarchies | H09 | 形式化 |  |
| hierarchies | H10 | 形式化 |  |
| hierarchies | H11 | 形式化 |  |
| hierarchies | H12 | 形式化 |  |
| hierarchies | H13 | 形式化 |  |
