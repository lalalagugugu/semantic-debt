# L1-onto / L3a-full 逐条对应核对（T34）

复现：`uv run python -m render.l3a_full`（写 `build/contexts/SQL-L1-onto.yaml`、`build/contexts/SQL-L3a-full.yaml` 与本报告）；测试：`uv run pytest tests/test_l3a_full.py`（加 `--with rdflib` 另做通用解析器复核）。

## 两份本体

- **SQL-L1-onto**：只含 L1（`semantic/source.yaml` 经 `render.context.render_l1`，即 SQL-L1 的上下文）。
- **SQL-L3a-full**：L1 加 `semantic/l1plus.yaml` 的 109 条（`render.l1plus.overlay`，与 SQL-L1plus 的 `l1plus` 节相同）。
- 同一个生成器（`render.l3a_full.build`）：只喂 L1 得到前者，喂 L1 和 109 条得到后者；不是从后者的文本里删。序列化确定、可复现（测试在不同 `PYTHONHASHSEED` 下各生成一次，逐字节相同）。

## 怎么核对

1. **反向重建**：核对器解析生成的 Turtle（本模块自带的、保留文档顺序的解析器，只认生成器用到的子集），从图里反解出 SQL-L1 的上下文（两份都做）和 L1+ 的 overlay（SQL-L3a-full），要求与源**逐字段相等**（含列表顺序、标量类型）。SQL-L1-onto 另查：109 条的编号（`A01`…`H13`、`G01`、`D05b` 这类）在整份文本里一个都不出现。
2. **子图**（按图比，不比文本）：把三元组规范化（空白节点按内容展开）后按多重集比较。SQL-L1-onto 的 4,975 个三元组全部在 SQL-L3a-full 的 8,877 个里；差 3,902 个，恰好等于按条目分别生成的三元组之和，每个都追到条目编号：109 条共 3,893 个，另 9 个属于 L1+ 的文件头 `:L1plus`（`l1plus.yaml` 顶层的 version、base、title、as_of_date 与两个词汇声明，不属于任何一条；保留它是为了 SQL-L1plus 的 `l1plus` 节能逐字段重建）。109 条里只用到的词汇，声明归第一个用到它的条目。不多不少，否则渲染失败。
3. 本体自己命名空间里用到的每个节点都有定义；生成结果可重现。
4. 通用解析器复核：rdflib 解析两份文本，三元组数与本模块解析器一致；语义探针见下（rdflib、owlrl、pyshacl 不是项目依赖，未安装时这些测试跳过）。
5. 不运行 OWL 推理机或 SHACL 引擎，不编译查询。

## L1：两份本体里都出现且数量相同

| 项 | 源 | SQL-L1-onto | SQL-L3a-full |
|---|---|---|---|
| 表 | 25 | 25 | 25 |
| 字段 | 228 | 228 | 228 |
| 枚举值 | 568 | 568 | 568 |
| 关系 | 48 | 48 | 48 |
| 指标 | 69 | 69 | 69 |
| 约定 | 15 | 15 | 15 |
| 同义词 | 56 | 56 | 56 |
| 多路径默认 | 4 | 4 | 4 |
| 数据质量 | 15 | 15 | 15 |

表是 OWL 类（行是实例），字段是数据属性（rdfs:domain 表、rdfs:range xsd 类型，另保留 ClickHouse 类型原文），外键是对象属性（多对一 = owl:FunctionalProperty，一对一再加 owl:InverseFunctionalProperty），枚举值是个体（`:enumValue [ :code … ; :meaning … ]`，没有写成闭合 `sh:in`：L1 没说哪些清单是完整的），同义词是「说法 → 指标 / 字段」的链接，多路径默认能解析的写成有序关系链。

### L1 的约定与指标，按档位

档位（第 3 步复核定）：**1S** 核心口径已用 OWL 2 / SHACL Core 的标准构造形式化；**1C** 核心已形式化，但含义依赖本体自定义的谓词；**(2)** 只有声明：类型、定义域值域、链接，核心口径在注解里；**(3)** 纯注解。两份本体的 L1 部分相同，下表对两份都成立。

| 项 | 1S | 1C | (2) | (3) | 说明 |
|---|---|---|---|---|---|
| 约定 | 0 | 0 | 15 | 0 | 适用的表、字段、指标是链接；规则是文字 |
| 指标 | 0 | 0 | 69 | 0 | 都有表与约定的链接，口径是文字或注解里的 SQL 表达式。其中 13 个比率的分子分母链接到指标（平均单价、退货率、折扣率、打折销售额占比、毛利率、每单行数、客单价、客均销售额、客均订单数、新客销售额占比、日均销售额、日均销售数量、店均销售额），链接不定义除法、分组作用域和分母为 0 的处理，按复核归 (2)；上一版把其中 12 个报成 (1)，已改 |

## L1+ 109 条，按档位（新旧对照）

| 档 | 旧 SQL-L3a | SQL-L3a-full |
|---|---|---|
| 1S | 1（1%） | 19（17%） |
| 1C | 11（10%） | 21（19%） |
| 2 | 18（17%） | 54（50%） |
| 3 | 79（72%） | 15（14%） |

新档按第 3 步复核（`reports/validation/t34-codex-review.md`）的逐条档位。和第一轮复核不同的 3 条是盲写修订补了标准构造的D11、D23、E10，第二轮复核已接受（均为 1S），证据见逐条表。和旧 L3a 同档的 28 条：G01、D04、D06b、D08、D09、D12、D13、D14、D15、D18、D24、D25、D26、D28、D31、E01、E02、E03、E06、E08、E11、E12、E13、E14、E15、E17、H08、H10；其余 81 条档位提高，没有降档。

只用 OWL 2 与 SHACL Core 的标准构造；没有用 SHACL-SPARQL、SHACL-AF 规则或其他查询式规则（那属于 L3b）。本体里检出的查询式谓词：无。指标口径只放注解里的 SQL 片段。

**宽口径**（第一轮报的）：只要条目名下有任何一条非注解、非 `:ref`、非自身类型的三元组就算形式化，这样是 77 条（71%）。它把「只有声明」也算进形式化，保留作参考，不用于结论。

旧 L3a 的档位按旧生成器（`render/l1plus.py`）的实际输出判，复核接受：A / D / G 条只有原文注解树；E 条有「说法 → 取值」个体（依赖自定义 :value，计 1C），但列表、字典取值和 E07 的筛选写法被丢掉的计 (2)；H 条有类与子类，成员定义只有一部分转 hasValue，没有划分公理和键，计 (2)；H10 已有场景形状，计 1S。

## 第 3 步复核清单的处理

「需要盲写会话处理的清单」与「T26 的 16 条」逐条：本轮补了什么，没有标准写法的标「未做」并写原因。不为升档硬写。

| 编号 | 出处 | 复核档 → 本轮档 | 处理 |
|---|---|---|---|
| A01 | 清单 | 2 | 复核档；默认 / 例外范围链接到类；触发例外的是问题措辞，不是数据条件，不能写成形状（未做） |
| A06 | 清单 | 2 | 复核档；各表端点是个体；「没说时间时取全部」是作答动作，OWL / SHACL 无对应构造（未做） |
| A07 | 清单 | 2 | 复核档；固定时间词的端点是个体；参数化的「近 N 天 / 月」无标准写法（未做） |
| A10 | 清单 | 2 | 复核档；大洲 → 字段对应是个体；逐行选字段与双键分组是查询写法，无标准构造（未做） |
| A16 | 清单 | 2 | 复核档；落点是链接；组内简单平均与兜底条件在注解（聚合无标准构造，未做） |
| A17 | 清单、T26 | 2 | 复核档；默认行范围链接到类:打折交易；「问题明确要全部交易作分母」是问题措辞（未做） |
| A18 | 清单 | 2 | 复核档；默认指标、范围、分组是链接；覆盖条件是问题措辞（未做） |
| A19 | 清单、T26 | 2 | 复核档；本轮补 retail:DimPromotion 的 owl:hasKey（PromotionKey）；按名合并与跨年取年份的条件无标准构造（未做） |
| A20 | 清单 | 2 | 复核档；左连接关系是链接；未知组保留、参与排名是查询写法（未做） |
| A24 | 清单、T26 | 2 | 复核档；本轮改为链接到 H12 的门店 × 产品组合类（比较在那里是形状），不再把原始列比较挂在本条；先跨店汇总再比较是聚合，SHACL Core 无法表达（未做） |
| A27 | T26 | 2 | 月数声明为数据属性；客户集合要按参照日与交易筛选取，是参数化条件（未做） |
| A33 | 清单、T26 | 2 | 复核档；本轮补 FactStrategyPlan 的形状（AccountKey ∈ 17 个叶子、Amount > 0）与传递的上级科目闭包；父科目 = 叶子之和是算术，无标准构造（未做） |
| A34 | 清单、T26 | 2 | 复核档；落点是链接；计划语境改走科目 8 是问题措辞，未绑定到映射（未做） |
| A38 | T26 | 2 | 引用成链接；未做，限制分开说：原文没有列全员工之间的上下级边（输入不足，只给了 18 与 1 的环）；SHACL Core 有 sh:oneOrMorePath，已知有限个体可逐个查无环，但对任意未知节点的通用无环检查没有直接写法；业绩沿树求和是算术，做不了 |
| A39 | 清单 | 2 | 复核档；落点是链接；职级、组织语境的排除是问题措辞（未做） |
| A40 | T26 | 1C | 复核档；归属仍有自定义断言；第二轮补 SHACL Core 条件形状：子类键 = 19 的行，沿 L1 外键关系（sh:path 序列）到的父品类名称 hasValue "Computers"（sh:or / sh:not / sh:hasValue），不猜父品类键、不新建描述节点；正反例通过 |
| A41 | T26 | 1C | 复核档；根与断环是自定义记录；第二轮补 H07 已列的 24 个科目个体逐个 sh:targetNode，[ sh:oneOrMorePath :parentAccount ] 的值 sh:not [ sh:in (自身) ]，断环后的图通过、恢复被断的父边后不通过；对任意未知节点的通用无环检查没有直接写法，已知的有限个体可以逐个检查 |
| D05 | T26 | 2 | 类、等价、行范围；第二轮补门槛：路径 ( [ sh:inversePath 客户关系 ] SalesOrderNumber ) 的 sh:minCount 2，值是集合，同一订单号只算一次（正反例通过）；窗口条件在注解，故仍为 (2) |
| D05b | T26 | 2 | 类与行范围（类:线上销售行）；未做：缺的是只取正销量的中间行、同时绑定当前客户和窗口；也不能从订单号反查销售行，原始数据有订单号被多个客户重复使用，会串入别人的正销量行 |
| D09 | T26 | 3 | 比率是文字；H08 的划分不算本条的口径（未做：比率无标准构造） |
| D10 | 清单、T26 | 2 | 复核档；本轮把五个年龄段写成 sh:NodeShape + sh:property / sh:path :D10；年龄的派生式只在注解，故仍为 (2) |
| D11 | 清单、T26 | 1S | 复核为 1C（band 只有散落的 SHACL 边界）；本轮每档改成 sh:NodeShape + sh:property / sh:path DimCustomer.YearlyIncome，pyshacl 正反例测试通过（tests/test_l3a_full.py），核心分档已是标准形状，故报 1S |
| D16 | 清单 | 2 | 复核档；分子分母链接不定义除法 |
| D17 | 清单 | 2 | 复核档；分子分母链接不定义除法 |
| D23 | 清单、T26 | 1S | 复核为 (2)（哨兵值只是记录）；本轮补哨兵排除形状 sh:not [ sh:pattern "^2090-12-31" ]，关店 = owl:equivalentClass 类:已关店门店（Status 的 hasValue "Off"），pyshacl 正反例通过；按期间筛选关店日是问题的参数，不是本条口径，故报 1S |
| D27 | 清单 | 2 | 复核档；零值类是链接；最近快照与跨店聚合在注解 |
| D30 | 清单 | 2 | 复核档；默认科目与场景是链接；比率在注解 |
| D32 | T26 | 1C | 复核档；叶子集合与显式加减依赖自定义谓词；本轮在 H07 补标准传递闭包，算术本身无标准构造 |
| E10 | 清单 | 1S | 复核不通过（取值节点用了物理列属性，RDFS 闭包推成 DimDate 行）；本轮改为每个大洲一个节点，字段只作 sh:path / :onColumn 的宾语，取值是 sh:hasValue，适用大洲另写 :whenContinent 形状（DimGeography.ContinentName 的 hasValue）；RDFS / OWL-RL 闭包后无表或类的新实例（语义探针测试） |
| H08 | 清单 | 2 | 复核档；划分正确；分层集合资格与月数派生在注解 |
| L1 比率指标 13 个 | 清单 | (2) | 按复核归 (2)；没有补运算结构：OWL 2 / SHACL Core 不表达除法（未做） |

## 语义探针

rdflib 解析两份本体，用 owlrl 的 RDFS 与 OWL-RL 闭包展开，检查闭包后没有任何节点成为 `retail:` 表或 `class:` 类的实例（本体里没有真实数据行，所以应为 0）。另检查：没有任何三元组用物理列属性（`retail:表.字段`，带 rdfs:domain）作谓词。测试：`uv run --with rdflib --with owlrl --with pyshacl pytest tests/test_l3a_full.py`；同一命令还用 pyshacl 对 D10、D11、D23、A33、E10 的形状做正反例校验。依赖未安装时这些测试跳过。

## 三元组

SQL-L1-onto 4,975 个，注解 1,883（38%），其余 3,092（62%）；SQL-L3a-full 8,877 个，注解 3,086（35%），其余 5,791（65%）。列表按 rdf:first / rdf:rest 展开计；注解 = 谓词是 rdfs:label、rdfs:comment、skos:altLabel 或本体声明的注解属性。

## 系统消息的 token 数

方法：`harness.run_direct.system_for` 拼出完整系统消息（系统提示 + 语义上下文 + 语法说明），用 harness 的 `estimate_tokens_from_text` 估算（DeepSeek 官方经验比例：中文字符 ≈ 0.6 token，其他字符 ≈ 0.3 token）。是估算，不是分词器的实数；正式运行以 API 返回的用量为准。各单元的系统提示与语法说明逐字节相同（测试核对），差别只在语义上下文。

| 单元 | 组 | 系统消息字符数 | 语义上下文（估算 token） | 系统消息（估算 token） | 对 SQL-L1plus | 占上下文上限 |
|---|---|---|---|---|---|---|
| SQL-L1 | 1 文字 | 112,842 | 40,254 | 41,084 | 0.62× | 4.1% |
| SQL-L1-onto | 1 本体 | 168,391 | 57,285 | 58,115 | 0.87× | 5.8% |
| SQL-L1plus | 2 文字 | 180,005 | 65,868 | 66,698 | 1.00× | 6.7% |
| SQL-L3a-full | 2 本体 | 278,565 | 96,389 | 97,219 | 1.46× | 9.7% |
| SQL-L3a | 参考（旧，混合写法） | 464,859 | 155,639 | 156,469 | 2.35× | 15.6% |

上下文上限：deepseek-flash（DeepSeek-V4.1-Flash-1017） 上下文 1,000,000 token、最大输出 384,000 token；来源 DeepSeek 官方文档 https://api-docs.deepseek.com/quick_start/pricing，2026-11-04 由协调会话查（盲写会话访问该网址被拒）。四份都远低于上限的 80%。

## 逐条

构造：条目自己生成的三元组里用到的 OWL / SHACL 词汇与本体的自定义属性（`:ref` 是指向 L1 节点的链接）；不含词汇声明。

| 节 | 编号 | 旧档 | 新档 | 同 / 改 | 用到的构造 | 说明 |
|---|---|---|---|---|---|---|
| general_rules | G01 | 3 | 3 | 同 | — | 比率分母为 0 / NULL 的通则是文字规则 |
| clarifications | A01 | 3 | 2 | 改 | `:defaultScope` `:exceptionScope` `:ref` | 复核档；默认 / 例外范围链接到类；触发例外的是问题措辞，不是数据条件，不能写成形状（未做） |
| clarifications | A02 | 3 | 2 | 改 | `:ref` | 引用成链接；按序选表规则在注解 |
| clarifications | A03 | 3 | 2 | 改 | `:ref` | 引用成链接；两步选表规则在注解 |
| clarifications | A04 | 3 | 2 | 改 | `:ref` | 引用成链接；地理路径随事实表的规则在注解 |
| clarifications | A05 | 3 | 2 | 改 | `:ref` | 引用成链接；规则在注解 |
| clarifications | A06 | 3 | 2 | 改 | `:dataRange` `:firstDateKey` `:lastDateKey` `:ref` `:table` | 复核档；各表端点是个体；「没说时间时取全部」是作答动作，OWL / SHACL 无对应构造（未做） |
| clarifications | A07 | 3 | 2 | 改 | `:end` `:ref` `:start` `:timeTerm` | 复核档；固定时间词的端点是个体；参数化的「近 N 天 / 月」无标准写法（未做） |
| clarifications | A08 | 3 | 2 | 改 | `:comparisonWindow` `:defaultWindow` `:end` `:ref` `:start` | 默认窗口是个体；同比环比取窗算法在注解 |
| clarifications | A09 | 3 | 2 | 改 | `:ref` | 引用成链接；交易日日均算法在注解 |
| clarifications | A10 | 3 | 2 | 改 | `:continent` `:onColumn` `:ref` `:seasonColumn` | 复核档；大洲 → 字段对应是个体；逐行选字段与双键分组是查询写法，无标准构造（未做） |
| clarifications | A11 | 3 | 1C | 改 | `:ref` `:rowScope` | 复核档；行范围（全部行，含退货行）用自定义 :rowScope 链接到带形状的类 |
| clarifications | A12 | 3 | 1C | 改 | `:ref` `:rowScope` | 复核档；行范围用自定义 :rowScope；去重算法在注解 |
| clarifications | A13 | 3 | 2 | 改 | `:ref` | 引用成链接；比率选择与上卷在注解 |
| clarifications | A14 | 3 | 2 | 改 | `:ref` | 引用成链接；计划语境识别在注解 |
| clarifications | A15 | 3 | 1C | 改 | `:account` `:decisionList` `:ref` `:scenarioTerm` `:table` `:target` | 复核档；有序决策表依赖自定义 :decisionList 的释义 |
| clarifications | A16 | 3 | 2 | 改 | `:ref` `:target` `:termTarget` | 复核档；落点是链接；组内简单平均与兜底条件在注解（聚合无标准构造，未做） |
| clarifications | A17 | 3 | 2 | 改 | `:ref` `:rowScope` | 复核档；默认行范围链接到类:打折交易；「问题明确要全部交易作分母」是问题措辞（未做） |
| clarifications | A18 | 3 | 2 | 改 | `:defaultGroupBy` `:defaultMetric` `:ref` `:rowScope` | 复核档；默认指标、范围、分组是链接；覆盖条件是问题措辞（未做） |
| clarifications | A19 | 3 | 2 | 改 | `owl:hasKey` `:alsoShow` `:defaultGroupBy` `:ref` | 复核档；本轮补 retail:DimPromotion 的 owl:hasKey（PromotionKey）；按名合并与跨年取年份的条件无标准构造（未做） |
| clarifications | A20 | 3 | 2 | 改 | `:ref` `:requiresLeftJoin` | 复核档；左连接关系是链接；未知组保留、参与排名是查询写法（未做） |
| clarifications | A21 | 3 | 2 | 改 | `:ref` | 引用成链接；分母作用域在注解 |
| clarifications | A22 | 3 | 2 | 改 | `:ref` | 引用成链接；最近快照与平均算法在注解 |
| clarifications | A23 | 3 | 2 | 改 | `:ref` | 引用成链接；周转算法在注解 |
| clarifications | A24 | 3 | 2 | 改 | `:ref` `:target` `:termTarget` | 复核档；本轮改为链接到 H12 的门店 × 产品组合类（比较在那里是形状），不再把原始列比较挂在本条；先跨店汇总再比较是聚合，SHACL Core 无法表达（未做） |
| clarifications | A25 | 3 | 2 | 改 | `:ref` | 引用成链接；规则在注解 |
| clarifications | A26 | 3 | 2 | 改 | `:ref` | 引用成链接；对齐与全外连接在注解 |
| clarifications | A27 | 3 | 2 | 改 | `owl:DatatypeProperty` `rdfs:domain` `:definedBy` `:ref` | 月数声明为数据属性；客户集合要按参照日与交易筛选取，是参数化条件（未做） |
| clarifications | A28 | 3 | 2 | 改 | `:ref` | 引用成链接；新客窗口在注解 |
| clarifications | A29 | 3 | 2 | 改 | `:ref` | 引用成链接；同店判定在注解 |
| clarifications | A30 | 3 | 2 | 改 | `:ref` | 引用成链接；范围与比率在注解 |
| clarifications | A31 | 3 | 2 | 改 | `:defines` `:ref` | 在售 / 停售链接到带形状的类；计数规则在注解 |
| clarifications | A32 | 3 | 1C | 改 | `owl:inverseOf` `:geoPath` `:ref` | 复核档；有序关系链（含 owl:inverseOf）挂在自定义 :geoPath 上 |
| clarifications | A33 | 3 | 2 | 改 | `sh:NodeShape` `sh:in` `sh:minExclusive` `sh:targetClass` `:axiom` `:planRowAccounts` `:ref` | 复核档；本轮补 FactStrategyPlan 的形状（AccountKey ∈ 17 个叶子、Amount > 0）与传递的上级科目闭包；父科目 = 叶子之和是算术，无标准构造（未做） |
| clarifications | A34 | 3 | 2 | 改 | `:ref` `:target` `:termTarget` | 复核档；落点是链接；计划语境改走科目 8 是问题措辞，未绑定到映射（未做） |
| clarifications | A35 | 3 | 1C | 改 | `:notRelationship` `:ref` `:useRelationship` | 复核档；选用 / 不选用的关系用自定义谓词 |
| clarifications | A36 | 3 | 2 | 改 | `:ref` | 引用成链接；平均值规则在注解（颜色见 E07） |
| clarifications | A37 | 3 | 1C | 改 | `:groupBy` `:ref` | 复核档；分组字段的有序列表挂在自定义 :groupBy 上 |
| clarifications | A38 | 3 | 2 | 改 | `:ref` | 引用成链接；未做，限制分开说：原文没有列全员工之间的上下级边（输入不足，只给了 18 与 1 的环）；SHACL Core 有 sh:oneOrMorePath，已知有限个体可逐个查无环，但对任意未知节点的通用无环检查没有直接写法；业绩沿树求和是算术，做不了 |
| clarifications | A39 | 3 | 2 | 改 | `:ref` `:target` `:termTarget` | 复核档；落点是链接；职级、组织语境的排除是问题措辞（未做） |
| clarifications | A40 | 3 | 1C | 改 | `sh:NodeShape` `sh:hasValue` `sh:not` `sh:targetClass` `:asserts` `:axiom` `:inCategory` `:ref` `:subcategoryKey` `:subcategoryName` | 复核档；归属仍有自定义断言；第二轮补 SHACL Core 条件形状：子类键 = 19 的行，沿 L1 外键关系（sh:path 序列）到的父品类名称 hasValue "Computers"（sh:or / sh:not / sh:hasValue），不猜父品类键、不新建描述节点；正反例通过 |
| clarifications | A41 | 3 | 1C | 改 | `sh:NodeShape` `sh:in` `sh:not` `:axiom` `:breakCycle` `:ignoreParentOf` `:ref` `:root` `:rootAccount` | 复核档；根与断环是自定义记录；第二轮补 H07 已列的 24 个科目个体逐个 sh:targetNode，[ sh:oneOrMorePath :parentAccount ] 的值 sh:not [ sh:in (自身) ]，断环后的图通过、恢复被断的父边后不通过；对任意未知节点的通用无环检查没有直接写法，已知的有限个体可以逐个检查 |
| concepts | D01 | 3 | 2 | 改 | `owl:DatatypeProperty` `rdfs:domain` | 数据属性（定义域 DimCustomer、值域 xsd:date）；聚合在注解 |
| concepts | D02 | 3 | 2 | 改 | `owl:DatatypeProperty` `rdfs:domain` | 同 D01 |
| concepts | D03 | 3 | 2 | 改 | `owl:DatatypeProperty` `rdfs:domain` | 同 D01 |
| concepts | D04 | 3 | 3 | 同 | — | 留存算法是文字与 SQL 片段 |
| concepts | D05 | 3 | 2 | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `sh:NodeShape` `sh:minCount` `:rowScope` | 类、等价、行范围；第二轮补门槛：路径 ( [ sh:inversePath 客户关系 ] SalesOrderNumber ) 的 sh:minCount 2，值是集合，同一订单号只算一次（正反例通过）；窗口条件在注解，故仍为 (2) |
| concepts | D05b | 3 | 2 | 改 | `owl:Class` `rdfs:subClassOf` `:rowScope` | 类与行范围（类:线上销售行）；未做：缺的是只取正销量的中间行、同时绑定当前客户和窗口；也不能从订单号反查销售行，原始数据有订单号被多个客户重复使用，会串入别人的正销量行 |
| concepts | D06 | 3 | 2 | 改 | `:rowScope` | 行范围链接；比率在注解 |
| concepts | D06b | 3 | 3 | 同 | — | 文字与 SQL 片段 |
| concepts | D06c | 3 | 2 | 改 | `:rowScope` | 行范围链接；比率在注解 |
| concepts | D07 | 3 | 2 | 改 | `:rowScope` | 行范围链接；去重在注解 |
| concepts | D07b | 3 | 2 | 改 | `:rowScope` | 行范围链接；去重在注解 |
| concepts | D08 | 3 | 3 | 同 | — | 文字 |
| concepts | D09 | 3 | 3 | 同 | — | 比率是文字；H08 的划分不算本条的口径（未做：比率无标准构造） |
| concepts | D10 | 3 | 2 | 改 | `owl:DatatypeProperty` `rdfs:domain` `sh:NodeShape` `sh:minInclusive` `sh:maxExclusive` `:band` | 复核档；本轮把五个年龄段写成 sh:NodeShape + sh:property / sh:path :D10；年龄的派生式只在注解，故仍为 (2) |
| concepts | D11 | 3 | 1S | 改 | `sh:NodeShape` `sh:minInclusive` `sh:maxExclusive` `:band` `:bandOf` | 复核为 1C（band 只有散落的 SHACL 边界）；本轮每档改成 sh:NodeShape + sh:property / sh:path DimCustomer.YearlyIncome，pyshacl 正反例测试通过（tests/test_l3a_full.py），核心分档已是标准形状，故报 1S |
| concepts | D12 | 3 | 3 | 同 | — | 文字与 SQL 片段 |
| concepts | D13 | 3 | 3 | 同 | — | 文字 |
| concepts | D14 | 3 | 3 | 同 | — | 文字 |
| concepts | D15 | 3 | 3 | 同 | — | 文字与 SQL 片段 |
| concepts | D16 | 3 | 2 | 改 | `:denominatorMetric` `:numeratorMetric` | 复核档；分子分母链接不定义除法 |
| concepts | D17 | 3 | 2 | 改 | `:denominatorMetric` `:numeratorMetric` | 复核档；分子分母链接不定义除法 |
| concepts | D18 | 3 | 3 | 同 | — | 文字与 SQL 片段 |
| concepts | D19 | 3 | 2 | 改 | `owl:DatatypeProperty` `sh:NodeShape` `sh:maxInclusive` `sh:minExclusive` `:band` | 阈值是绑定到累计占比属性的形状，第二轮把阈值改成与属性一致的 xsd:double（等于、略小、略大的 double 探针通过）；累计排序与同额处理在注解 |
| concepts | D20 | 3 | 2 | 改 | `owl:Class` `rdfs:subClassOf` `:objectClass` | 父类；窗口与分母在注解 |
| concepts | D21 | 3 | 2 | 改 | `owl:Class` `rdfs:subClassOf` `:defaultWindow` `:end` `:start` | 父类与默认窗口；判定在注解 |
| concepts | D22 | 3 | 2 | 改 | `owl:Class` `rdfs:subClassOf` | 父类；日期判定在注解 |
| concepts | D23 | 3 | 1S | 改 | `owl:Class` `owl:equivalentClass` `sh:not` `sh:pattern` `:onColumn` `:selects` `:sentinel` `:value` | 复核为 (2)（哨兵值只是记录）；本轮补哨兵排除形状 sh:not [ sh:pattern "^2090-12-31" ]，关店 = owl:equivalentClass 类:已关店门店（Status 的 hasValue "Off"），pyshacl 正反例通过；按期间筛选关店日是问题的参数，不是本条口径，故报 1S |
| concepts | D24 | 3 | 3 | 同 | — | 文字 |
| concepts | D25 | 3 | 3 | 同 | — | 文字 |
| concepts | D26 | 3 | 3 | 同 | — | 文字与 SQL 片段 |
| concepts | D27 | 3 | 2 | 改 | `owl:Class` `owl:equivalentClass` | 复核档；零值类是链接；最近快照与跨店聚合在注解 |
| concepts | D28 | 3 | 3 | 同 | — | 文字 |
| concepts | D29 | 3 | 2 | 改 | `:defaultWindow` `:end` `:start` | 默认窗口；渠道与日分母在注解 |
| concepts | D30 | 3 | 2 | 改 | `:defaultAccount` `:denominatorScenario` `:numeratorScenario` | 复核档；默认科目与场景是链接；比率在注解 |
| concepts | D31 | 3 | 3 | 同 | — | 有条件的默认科目，不写成无条件公理 |
| concepts | D32 | 3 | 1C | 改 | `:component` `:defaultScenario` `:derived` `:minus` `:plus` `:result` `:sumOfAccounts` | 复核档；叶子集合与显式加减依赖自定义谓词；本轮在 H07 补标准传递闭包，算术本身无标准构造 |
| concepts | D33 | 3 | 2 | 改 | `:denominatorAccount` | 分母链接；分子随语境 |
| aliases | E01 | 1C | 1C | 同 | `:key` `:map` `:onColumn` `:value` | 同档：说法 → 取值的映射依赖自定义 :value / :map；本轮新增作用字段链接 |
| aliases | E02 | 1C | 1C | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的映射依赖自定义 :value / :map；本轮新增作用字段链接 |
| aliases | E03 | 1C | 1C | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的映射依赖自定义 :value / :map；本轮新增作用字段链接 |
| aliases | E04 | 2 | 1S | 改 | `sh:in` `:map` `:onColumn` `:selects` `:value` | 列表取值写成 sh:in |
| aliases | E05 | 2 | 1S | 改 | `sh:in` `:map` `:noExactMapping` `:onColumn` `:selects` `:value` `:within` | 列表取值写成 sh:in；分不出的说法的处理在注解 |
| aliases | E06 | 1C | 1C | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的映射依赖自定义 :value / :map；本轮新增作用字段链接 |
| aliases | E07 | 2 | 1S | 改 | `sh:pattern` `sh:flags` `:map` `:onColumn` `:selects` `:value` | 每个颜色 sh:pattern + sh:flags "i" |
| aliases | E08 | 1C | 1C | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的映射依赖自定义 :value / :map；本轮新增作用字段链接 |
| aliases | E09 | 2 | 1S | 改 | `sh:hasValue` `sh:in` `sh:not` `:map` `:onColumn` `:selects` `:value` | 条件写成 hasValue / sh:not，名单写成 sh:in |
| aliases | E10 | 2 | 1S | 改 | `sh:hasValue` `:continent` `:map` `:onColumn` `:seasonValue` `:selects` `:value` `:whenContinent` | 复核不通过（取值节点用了物理列属性，RDFS 闭包推成 DimDate 行）；本轮改为每个大洲一个节点，字段只作 sh:path / :onColumn 的宾语，取值是 sh:hasValue，适用大洲另写 :whenContinent 形状（DimGeography.ContinentName 的 hasValue）；RDFS / OWL-RL 闭包后无表或类的新实例（语义探针测试） |
| aliases | E11 | 1C | 1C | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的映射依赖自定义 :value / :map；本轮新增作用字段链接 |
| aliases | E12 | 1C | 1C | 同 | `:account` `:key` `:map` `:onColumn` `:value` | 同档：说法 → 取值的映射依赖自定义 :value / :map；本轮新增作用字段链接 |
| aliases | E13 | 1C | 1C | 同 | `:map` `:noExactMapping` `:onColumn` `:value` `:within` | 同档：说法 → 取值的映射依赖自定义 :value / :map；本轮新增作用字段链接 |
| aliases | E14 | 1C | 1C | 同 | `:map` `:onColumn` `:op` `:value` | 同档：说法 → 取值的映射依赖自定义 :value / :map；本轮新增作用字段链接 |
| aliases | E15 | 1C | 1C | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的映射依赖自定义 :value / :map；本轮新增作用字段链接 |
| aliases | E16 | 2 | 1S | 改 | `sh:in` `:map` `:onColumn` `:selects` `:value` | 列表取值写成 sh:in |
| aliases | E17 | 1C | 1C | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的映射依赖自定义 :value / :map；本轮新增作用字段链接 |
| hierarchies | H01 | 2 | 1S | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:disjointUnionOf` `sh:NodeShape` `sh:hasValue` `sh:minExclusive` `:class` | 形状与划分 |
| hierarchies | H02 | 2 | 1S | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:disjointUnionOf` `owl:ObjectProperty` `rdfs:domain` `sh:NodeShape` `sh:hasValue` `sh:not` `:channelKey` `:class` `:relation` `:storeType` `:storeTypeChannel` `:viaRelationship` | 形状与两套划分 |
| hierarchies | H03 | 2 | 1S | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:disjointUnionOf` `owl:ObjectProperty` `rdfs:domain` `sh:NodeShape` `sh:hasValue` `:class` `:relation` `:viaRelationship` | 形状与划分；能否连上 DimProduct 的判定在注解 |
| hierarchies | H04 | 2 | 1S | 改 | `owl:Class` `owl:hasKey` `owl:ObjectProperty` `rdfs:domain` `sh:NodeShape` `sh:hasValue` `:class` `:relation` `:viaRelationship` | 城市 hasValue、owl:hasKey |
| hierarchies | H05 | 2 | 1S | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:AllDisjointClasses` `owl:ObjectProperty` `rdfs:domain` `sh:NodeShape` `sh:hasValue` `:axiom` `:class` `:relation` `:viaRelationship` | 四类 hasValue、owl:AllDisjointClasses；自指根在注解 |
| hierarchies | H06 | 2 | 1S | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:disjointUnionOf` `owl:ObjectProperty` `rdfs:domain` `sh:NodeShape` `sh:hasValue` `:breakCycle` `:class` `:onColumn` `:relation` `:rootKey` `:viaRelationship` | 职级形状与划分；员工树的无环检查未做：原文没有列全员工上下级边（输入不足），对任意未知节点的通用无环检查没有直接写法（SHACL Core 有 sh:oneOrMorePath，已知有限个体可逐个查，见 A41） |
| hierarchies | H07 | 2 | 1C | 改 | `owl:ObjectProperty` `owl:NamedIndividual` `:breakCycle` `:ignoreParentOf` `:leaf` `:leafAccounts` `:node` `:parentAccount` `:root` | 复核档；科目树用自定义 :parentAccount；本轮补 rdfs:subPropertyOf 到 owl:TransitiveProperty 的闭包属性 |
| hierarchies | H08 | 2 | 2 | 同 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:disjointUnionOf` `owl:disjointWith` `sh:NodeShape` `sh:minInclusive` `sh:maxInclusive` `sh:minExclusive` `:class` `:definedBy` | 复核档；划分正确；分层集合资格与月数派生在注解 |
| hierarchies | H09 | 2 | 1S | 改 | `owl:Class` `rdfs:subClassOf` `owl:disjointUnionOf` `owl:ObjectProperty` `rdfs:domain` `sh:NodeShape` `sh:hasValue` `sh:not` `sh:alternativePath` `:class` `:relation` | 划分、hasValue / sh:not、sh:alternativePath |
| hierarchies | H10 | 1S | 1S | 同 | `owl:Class` `owl:AllDisjointClasses` `sh:NodeShape` `sh:hasValue` `sh:in` `sh:alternativePath` `sh:targetClass` `sh:minCount` `sh:maxCount` `:axiom` `:class` | 同档：场景形状与单值约束 |
| hierarchies | H11 | 2 | 1S | 改 | `owl:Class` `owl:disjointUnionOf` `sh:NodeShape` `sh:hasValue` `:class` | 形状与划分 |
| hierarchies | H12 | 2 | 1S | 改 | `owl:Class` `rdfs:subClassOf` `sh:NodeShape` `sh:hasValue` `sh:lessThan` `:class` | 两种比较形状；不加只在当前数据成立的子类 |
| hierarchies | H13 | 2 | 1S | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:disjointUnionOf` `sh:NodeShape` `sh:hasValue` `sh:in` `:class` | 形状、sh:in 与两套划分 |
