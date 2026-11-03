# L1-onto / L3a-full 逐条对应核对（T34）

复现：`uv run python -m render.l3a_full`（写 `build/contexts/SQL-L1-onto.yaml`、`build/contexts/SQL-L3a-full.yaml` 与本报告）；测试：`uv run pytest tests/test_l3a_full.py`（加 `--with rdflib` 另做通用解析器复核）。

## 两份本体

- **SQL-L1-onto**：只含 L1（`semantic/source.yaml` 经 `render.context.render_l1`，即 SQL-L1 的上下文）。
- **SQL-L3a-full**：L1 加 `semantic/l1plus.yaml` 的 109 条（`render.l1plus.overlay`，与 SQL-L1plus 的 `l1plus` 节相同）。
- 同一个生成器（`render.l3a_full.build`）：只喂 L1 得到前者，喂 L1 和 109 条得到后者；不是从后者的文本里删。序列化确定、可复现（测试在不同 `PYTHONHASHSEED` 下各生成一次，逐字节相同）。

## 怎么核对

1. **反向重建**：核对器解析生成的 Turtle（本模块自带的、保留文档顺序的解析器，只认生成器用到的子集），从图里反解出 SQL-L1 的上下文（两份都做）和 L1+ 的 overlay（SQL-L3a-full），要求与源**逐字段相等**（含列表顺序、标量类型）。SQL-L1-onto 另查：109 条的编号（`A01`…`H13`、`G01`、`D05b` 这类）在整份文本里一个都不出现。
2. **子图**（按图比，不比文本）：把三元组规范化（空白节点按内容展开）后按多重集比较。SQL-L1-onto 的 4,975 个三元组全部在 SQL-L3a-full 的 8,404 个里；差 3,429 个，恰好等于按条目分别生成的三元组之和，每个都追到条目编号：109 条共 3,420 个，另 9 个属于 L1+ 的文件头 `:L1plus`（`l1plus.yaml` 顶层的 version、base、title、as_of_date 与两个词汇声明，不属于任何一条；保留它是为了 SQL-L1plus 的 `l1plus` 节能逐字段重建）。109 条里只用到的词汇，声明归第一个用到它的条目。不多不少，否则渲染失败。
3. 本体自己命名空间里用到的每个节点都有定义；生成结果可重现。
4. 通用解析器复核：rdflib 解析两份文本，三元组数与本模块解析器一致（rdflib 不是项目依赖，未安装时该测试跳过）。
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

### L1 的约定与指标，按三档

三档（与 T26 对齐）：(1) 核心口径已形式化：决定 SQL 怎么写的那部分是公理、形状或个体，不只在注解里；(2) 只有声明：类型、定义域值域、链接，核心口径在注解里；(3) 纯注解。两份本体的 L1 部分相同，下表对两份都成立。

| 项 | (1) 核心已形式化 | (2) 只有声明 | (3) 纯注解 | 说明 |
|---|---|---|---|---|
| 约定 | 0 | 15 | 0 | 适用的表、字段、指标是链接；规则是文字 |
| 指标 | 12 | 57 | 0 | (1) 是纯比率、分子分母都链接到指标：平均单价、退货率、打折销售额占比、毛利率、每单行数、客单价、客均销售额、客均订单数、新客销售额占比、日均销售额、日均销售数量、店均销售额；(2) 有表与约定的链接，口径是文字或注解里的 SQL 表达式（折扣率的分子分母虽是链接，但「PromotionKey != 1」的默认筛选在注解，归 (2)） |

## L1+ 109 条，按三档（新旧对照）

| 档 | 旧 SQL-L3a | SQL-L3a-full |
|---|---|---|
| (1) | 12（11%） | 58（53%） |
| (2) | 18（17%） | 36（33%） |
| (3) | 79（72%） | 15（14%） |

和旧 L3a 同档的 27 条：G01、D04、D06b、D08、D09、D12、D13、D14、D15、D18、D24、D25、D26、D28、D31、E01、E02、E03、E06、E08、E11、E12、E13、E14、E15、E17、H10；其余 82 条档位提高，理由逐条见下表。
SHACL-SPARQL 或其他查询式规则：没有用（指标口径都用注解里的 SQL 片段，按卡片允许的写法）。

**宽口径**（上一版报的）：只要条目名下有任何一条非注解、非 `:ref`、非自身类型的三元组就算形式化，这样是 77 条（71%）。它把「只有声明」也算进形式化，比上面的三档宽，保留作参考。

旧 L3a 的档位按旧生成器（`render/l1plus.py`）的实际输出判：A / D / G 条只有原文注解树；E 条有「说法 → 取值」个体，但列表、字典取值和 E07 的筛选写法被丢掉；H 条有类与子类，成员定义只有「开头是字面等式且后面紧跟（、；或结尾」才转 hasValue，没有划分公理和键。

## 三元组

SQL-L1-onto 4,975 个，注解 1,883（38%），其余 3,092（62%）；SQL-L3a-full 8,404 个，注解 3,082（37%），其余 5,322（63%）。列表按 rdf:first / rdf:rest 展开计；注解 = 谓词是 rdfs:label、rdfs:comment、skos:altLabel 或本体声明的注解属性。

## 系统消息的 token 数

方法：`harness.run_direct.system_for` 拼出完整系统消息（系统提示 + 语义上下文 + 语法说明），用 harness 的 `estimate_tokens_from_text` 估算（DeepSeek 官方经验比例：中文字符 ≈ 0.6 token，其他字符 ≈ 0.3 token）。是估算，不是分词器的实数；正式运行以 API 返回的用量为准。各单元的系统提示与语法说明逐字节相同（测试核对），差别只在语义上下文。

| 单元 | 组 | 系统消息字符数 | 语义上下文（估算 token） | 系统消息（估算 token） | 对 SQL-L1plus | 占上下文上限 |
|---|---|---|---|---|---|---|
| SQL-L1 | 1 文字 | 112,842 | 40,254 | 41,084 | 0.62× | 4.1% |
| SQL-L1-onto | 1 本体 | 168,391 | 57,285 | 58,115 | 0.87× | 5.8% |
| SQL-L1plus | 2 文字 | 180,005 | 65,868 | 66,698 | 1.00× | 6.7% |
| SQL-L3a-full | 2 本体 | 270,322 | 93,886 | 94,716 | 1.42× | 9.5% |
| SQL-L3a | 参考（旧，混合写法） | 464,859 | 155,639 | 156,469 | 2.35× | 15.6% |

上下文上限：deepseek-flash（DeepSeek-V4.1-Flash-1017） 上下文 1,000,000 token、最大输出 384,000 token；来源 DeepSeek 官方文档 https://api-docs.deepseek.com/quick_start/pricing，2026-11-04 由协调会话查（盲写会话访问该网址被拒）。四份都远低于上限的 80%。

## 逐条

构造：条目自己生成的三元组里用到的 OWL / SHACL 词汇与本体的自定义属性（`:ref` 是指向 L1 节点的链接）；不含词汇声明。

| 节 | 编号 | 旧档 | 新档 | 同 / 改 | 用到的构造 | 说明 |
|---|---|---|---|---|---|---|
| general_rules | G01 | (3) | (3) | 同 | — | 比率分母为 0 / NULL 的通则是文字规则，无对应公理 |
| clarifications | A01 | (3) | (1) | 改 | `:defaultScope` `:exceptionScope` `:ref` | 默认范围链接到类:门店（≡ DimStore），例外链接到类:实体店（StoreType 的 hasValue） |
| clarifications | A02 | (3) | (2) | 改 | `:ref` | 引用解析成节点链接；按序选表的规则仍在注解 |
| clarifications | A03 | (3) | (2) | 改 | `:ref` | 同上：引用成链接，选表两步规则在注解 |
| clarifications | A04 | (3) | (2) | 改 | `:ref` | 引用成链接，地理路径跟随事实表的规则在注解 |
| clarifications | A05 | (3) | (2) | 改 | `:ref` | 引用成链接，规则在注解 |
| clarifications | A06 | (3) | (1) | 改 | `:dataRange` `:firstDateKey` `:lastDateKey` `:ref` `:table` | 各事实表的最早 / 最晚 DateKey 写成 xsd:date 个体；主数据不截断的说明在注解 |
| clarifications | A07 | (3) | (1) | 改 | `:end` `:ref` `:start` `:timeTerm` | 列出的相对时间词写成带起止日的个体；「近 N 天」「近 N 个月」是参数式，留在注解与 SQL 片段 |
| clarifications | A08 | (3) | (2) | 改 | `:comparisonWindow` `:defaultWindow` `:end` `:ref` `:start` | 只形式化了默认本期 / 对比期；同比、环比怎么取对比期的规则在注解 |
| clarifications | A09 | (3) | (2) | 改 | `:ref` | 引用成链接；交易日日均的定义在注解与 SQL 片段 |
| clarifications | A10 | (3) | (1) | 改 | `:continent` `:onColumn` `:ref` `:seasonColumn` | 大洲 → 季节字段的对应写成个体；按「大洲 × 季节」分组的要求在注解 |
| clarifications | A11 | (3) | (1) | 改 | `:ref` `:rowScope` | 行范围链接到类:线上订单行 与 类:全渠道汇总行（全部行，含退货行） |
| clarifications | A12 | (3) | (1) | 改 | `:ref` `:rowScope` | 行范围链接到类:线上订单行（全部交易行，含只有退货的订单） |
| clarifications | A13 | (3) | (2) | 改 | `:ref` | 引用成链接；利润率的选择与上卷公式在注解与 SQL 片段 |
| clarifications | A14 | (3) | (2) | 改 | `:ref` | 引用成链接；选表顺序交给 A15，本条规则在注解 |
| clarifications | A15 | (3) | (1) | 改 | `:account` `:decisionList` `:ref` `:scenarioTerm` `:table` `:target` | 五条按序规则写成有序列表（说法 → 表 / 科目），说法 → 场景写成个体 |
| clarifications | A16 | (3) | (1) | 改 | `:ref` `:target` `:termTarget` | 说法 → 落点（DimProduct.UnitPrice 或 指标:平均单价） |
| clarifications | A17 | (3) | (1) | 改 | `:ref` `:rowScope` | 分子分母的行范围链接到类:打折交易（PromotionKey 的 sh:not hasValue 1） |
| clarifications | A18 | (3) | (1) | 改 | `:defaultGroupBy` `:defaultMetric` `:ref` `:rowScope` | 默认指标、行范围、默认分组字段都是链接 |
| clarifications | A19 | (3) | (1) | 改 | `:alsoShow` `:defaultGroupBy` `:ref` | 默认分组字段与同时列出的字段是链接；按交易日期分年的说明在注解 |
| clarifications | A20 | (3) | (1) | 改 | `:ref` `:requiresLeftJoin` | 四条「事实表 → DimProduct」关系标为必须左连接；未知组为 NULL 的写法在注解 |
| clarifications | A21 | (3) | (2) | 改 | `:ref` | 引用成链接；占比分母规则在注解与 SQL 片段 |
| clarifications | A22 | (3) | (2) | 改 | `:ref` | 引用成链接；期末 / 平均库存的算法在注解与 SQL 片段 |
| clarifications | A23 | (3) | (2) | 改 | `:ref` | 引用成链接；周转率窗口规则在注解 |
| clarifications | A24 | (3) | (2) | 改 | `sh:hasValue` `sh:lessThan` `:ref` `:selects` `:termTarget` | 两组说法写成比较形状（lessThan / hasValue 0）；本条的核心「按产品先跨店汇总再比较」在注解 |
| clarifications | A25 | (3) | (2) | 改 | `:ref` | 引用成链接；不用宽表的规则在注解 |
| clarifications | A26 | (3) | (2) | 改 | `:ref` | 引用成链接；对齐与全外连接的规则在注解 |
| clarifications | A27 | (3) | (2) | 改 | `owl:DatatypeProperty` `rdfs:domain` `:definedBy` `:ref` | 月数定义成数据属性（定义域 DimCustomer）；客户集合与筛选规则在注解 |
| clarifications | A28 | (3) | (2) | 改 | `:ref` | 引用成链接；新客窗口的读法在注解 |
| clarifications | A29 | (3) | (2) | 改 | `:ref` | 引用成链接；同店判定规则在注解 |
| clarifications | A30 | (3) | (2) | 改 | `:ref` | 引用成链接；坪效分子分母范围在注解与 SQL 片段 |
| clarifications | A31 | (3) | (2) | 改 | `:defines` `:ref` | 在售 / 停售链接到带 hasValue 的类；门店数、产品数的计数规则（本条主体）在注解 |
| clarifications | A32 | (3) | (1) | 改 | `owl:inverseOf` `:geoPath` `:ref` | 地理上卷写成有序关系链（含 owl:inverseOf）；组织树例外在注解 |
| clarifications | A33 | (3) | (1) | 改 | `:planRowAccounts` `:ref` | 计划表有行的叶子科目写成有序列表，父科目的叶子集合见 H07 的 :leafAccounts |
| clarifications | A34 | (3) | (1) | 改 | `:ref` `:target` `:termTarget` | 三组说法 → 落点（CostAmount、类:设备购置费、类:年度维护费） |
| clarifications | A35 | (3) | (1) | 改 | `:notRelationship` `:ref` `:useRelationship` | 使用 / 不使用的关系是链接 |
| clarifications | A36 | (3) | (2) | 改 | `:ref` | 引用成链接；颜色大小写不敏感已在 E07 形式化，本条的平均值规则在注解 |
| clarifications | A37 | (3) | (1) | 改 | `:groupBy` `:ref` | 按周分组的两个字段写成有序列表 |
| clarifications | A38 | (3) | (2) | 改 | `:ref` | 引用成链接；业绩汇总沿员工树的规则在注解（断环在 H06） |
| clarifications | A39 | (3) | (1) | 改 | `:ref` `:target` `:termTarget` | 说法 → 落点（ContinentName、RegionCountryName） |
| clarifications | A40 | (3) | (1) | 改 | `:asserts` `:inCategory` `:ref` `:subcategoryKey` `:subcategoryName` | 子类 19 属于 Computers 写成断言个体 |
| clarifications | A41 | (3) | (1) | 改 | `:breakCycle` `:ignoreParentOf` `:ref` `:root` `:rootAccount` | 根科目与断环写成链接（根 = 科目 1，忽略 1 的上级） |
| concepts | D01 | (3) | (2) | 改 | `owl:DatatypeProperty` `rdfs:domain` | 首购日声明为数据属性（定义域 DimCustomer，值域 xsd:date）；口径在注解与 SQL 片段 |
| concepts | D02 | (3) | (2) | 改 | `owl:DatatypeProperty` `rdfs:domain` | 同 D01 |
| concepts | D03 | (3) | (2) | 改 | `owl:DatatypeProperty` `rdfs:domain` | 同 D01 |
| concepts | D04 | (3) | (3) | 同 | — | 三个留存口径是文字与 SQL 片段 |
| concepts | D05 | (3) | (2) | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `:rowScope` | 声明为类（⊑ DimCustomer，≡ 类:复购客户），行范围链接；「≥ 2 个订单」在注解与 SQL 片段 |
| concepts | D05b | (3) | (2) | 改 | `owl:Class` `rdfs:subClassOf` `:rowScope` | 同 D05，行范围是类:线上销售行 |
| concepts | D06 | (3) | (2) | 改 | `:rowScope` | 行范围链接；比率口径在注解与 SQL 片段 |
| concepts | D06b | (3) | (3) | 同 | — | 文字与 SQL 片段 |
| concepts | D06c | (3) | (2) | 改 | `:rowScope` | 行范围链接到类:线上销售行；比率口径在注解 |
| concepts | D07 | (3) | (2) | 改 | `:rowScope` | 行范围链接；订单数口径在注解 |
| concepts | D07b | (3) | (2) | 改 | `:rowScope` | 行范围链接到类:线上销售行；口径在注解 |
| concepts | D08 | (3) | (3) | 同 | — | 文字 |
| concepts | D09 | (3) | (3) | 同 | — | 文字 |
| concepts | D10 | (3) | (1) | 改 | `owl:DatatypeProperty` `rdfs:domain` `sh:minInclusive` `sh:maxExclusive` `:band` | 年龄声明为数据属性并给出派生式；五个年龄段写成区间个体（sh:minInclusive / maxExclusive） |
| concepts | D11 | (3) | (1) | 改 | `sh:minInclusive` `sh:maxExclusive` `:band` `:bandOf` | 四个收入档写成 YearlyIncome 上的区间个体 |
| concepts | D12 | (3) | (3) | 同 | — | 文字与 SQL 片段 |
| concepts | D13 | (3) | (3) | 同 | — | 文字 |
| concepts | D14 | (3) | (3) | 同 | — | 文字 |
| concepts | D15 | (3) | (3) | 同 | — | 文字与 SQL 片段 |
| concepts | D16 | (3) | (1) | 改 | `:denominatorMetric` `:numeratorMetric` | 分子 = 指标:销售数量，分母 = 指标:订单数 |
| concepts | D17 | (3) | (1) | 改 | `:denominatorMetric` `:numeratorMetric` | 分子 = 指标:退货金额，分母 = 指标:销售额 |
| concepts | D18 | (3) | (3) | 同 | — | 文字与 SQL 片段 |
| concepts | D19 | (3) | (2) | 改 | `sh:maxInclusive` `sh:minExclusive` `:band` | A / B / C 的阈值写成区间个体；累计占比（含同额）的算法在注解与 SQL 片段 |
| concepts | D20 | (3) | (2) | 改 | `owl:Class` `rdfs:subClassOf` `:objectClass` | 动销产品声明为类:在售产品的子类；窗口与分母规则在注解 |
| concepts | D21 | (3) | (2) | 改 | `owl:Class` `rdfs:subClassOf` `:defaultWindow` `:end` `:start` | 声明为类:在售产品的子类，默认窗口是个体；判定规则在注解 |
| concepts | D22 | (3) | (2) | 改 | `owl:Class` `rdfs:subClassOf` | 声明为类:门店的子类；开店日期判定在注解 |
| concepts | D23 | (3) | (1) | 改 | `owl:Class` `owl:equivalentClass` `:onColumn` `:sentinel` `:value` | ≡ 类:已关店门店（Status 的 hasValue 'Off'），CloseDate 哨兵值写成个体 |
| concepts | D24 | (3) | (3) | 同 | — | 文字 |
| concepts | D25 | (3) | (3) | 同 | — | 文字 |
| concepts | D26 | (3) | (3) | 同 | — | 文字与 SQL 片段 |
| concepts | D27 | (3) | (1) | 改 | `owl:Class` `owl:equivalentClass` | ≡ 类:零库存组合（OnHandQuantity 的 hasValue 0） |
| concepts | D28 | (3) | (3) | 同 | — | 文字 |
| concepts | D29 | (3) | (2) | 改 | `:defaultWindow` `:end` `:start` | 默认窗口是个体；渠道范围与日分母规则在注解与 SQL 片段 |
| concepts | D30 | (3) | (1) | 改 | `:defaultAccount` `:denominatorScenario` `:numeratorScenario` | 默认科目 = 科目 4，分子场景 Actual、分母场景 Budget 是链接 |
| concepts | D31 | (3) | (3) | 同 | — | 默认科目只在落到战略计划表时成立，不写成无条件公理 |
| concepts | D32 | (3) | (1) | 改 | `:component` `:defaultScenario` `:derived` `:minus` `:plus` `:result` `:sumOfAccounts` | 收入、费用、税写成叶子科目列表，税前 / 税后利润写成显式减法个体，默认场景链接 |
| concepts | D33 | (3) | (2) | 改 | `:denominatorAccount` | 只形式化了分母科目；分子随问题，在注解 |
| aliases | E01 | (1) | (1) | 同 | `:key` `:map` `:onColumn` `:value` | 同档：说法 → 取值的个体旧版已有；新增作用字段的链接（旧版只是字段原文） |
| aliases | E02 | (1) | (1) | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的个体旧版已有；新增作用字段的链接（旧版只是字段原文） |
| aliases | E03 | (1) | (1) | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的个体旧版已有；新增作用字段的链接（旧版只是字段原文） |
| aliases | E04 | (2) | (1) | 改 | `sh:in` `:map` `:onColumn` `:selects` `:value` | 旧版「大中华区」的取值是列表，被丢掉；新版写成 sh:in |
| aliases | E05 | (2) | (1) | 改 | `sh:in` `:map` `:noExactMapping` `:onColumn` `:selects` `:value` `:within` | 旧版「游戏」的列表取值被丢掉；新版写成 sh:in；分不出的说法写成个体，处理规则在注解 |
| aliases | E06 | (1) | (1) | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的个体旧版已有；新增作用字段的链接（旧版只是字段原文） |
| aliases | E07 | (2) | (1) | 改 | `sh:pattern` `sh:flags` `:map` `:onColumn` `:selects` `:value` | 旧版只有 :value，大小写不敏感只在注解；新版每个颜色写 sh:pattern + sh:flags "i"（E07 已知问题） |
| aliases | E08 | (1) | (1) | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的个体旧版已有；新增作用字段的链接（旧版只是字段原文） |
| aliases | E09 | (2) | (1) | 改 | `sh:hasValue` `sh:in` `sh:not` `:map` `:onColumn` `:selects` `:value` | 旧版把「PromotionKey = 1 / != 1」当取值、名单列表被丢掉；新版写成条件形状（hasValue / sh:not）与 sh:in |
| aliases | E10 | (2) | (1) | 改 | `:map` `:onColumn` `:value` | 旧版字典取值全部丢掉、只剩说法；新版每个说法给出三个季节字段的取值 |
| aliases | E11 | (1) | (1) | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的个体旧版已有；新增作用字段的链接（旧版只是字段原文） |
| aliases | E12 | (1) | (1) | 同 | `:account` `:key` `:map` `:onColumn` `:value` | 同档：说法 → 取值的个体旧版已有；新增作用字段的链接（旧版只是字段原文），E12 另链接科目个体 |
| aliases | E13 | (1) | (1) | 同 | `:map` `:noExactMapping` `:onColumn` `:value` `:within` | 同档：说法 → 取值的个体旧版已有；新增作用字段的链接（旧版只是字段原文） |
| aliases | E14 | (1) | (1) | 同 | `:map` `:onColumn` `:op` `:value` | 同档：说法 → 取值的个体旧版已有；新增作用字段的链接（旧版只是字段原文） |
| aliases | E15 | (1) | (1) | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的个体旧版已有；新增作用字段的链接（旧版只是字段原文） |
| aliases | E16 | (2) | (1) | 改 | `sh:in` `:map` `:onColumn` `:selects` `:value` | 旧版列表取值全部丢掉；新版写成 sh:in |
| aliases | E17 | (1) | (1) | 同 | `:map` `:onColumn` `:value` | 同档：说法 → 取值的个体旧版已有；新增作用字段的链接（旧版只是字段原文） |
| hierarchies | H01 | (2) | (1) | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:disjointUnionOf` `sh:NodeShape` `sh:hasValue` `sh:minExclusive` `:class` | 旧版缺「SalesQuantity > 0」与划分；新版补 sh:minExclusive 与 owl:disjointUnionOf |
| hierarchies | H02 | (2) | (1) | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:disjointUnionOf` `owl:ObjectProperty` `rdfs:domain` `sh:NodeShape` `sh:hasValue` `sh:not` `:channelKey` `:class` `:relation` `:storeType` `:storeTypeChannel` `:viaRelationship` | 旧版缺虚拟门店（!=）与两个划分；新版补 sh:not 与两个 owl:disjointUnionOf |
| hierarchies | H03 | (2) | (1) | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:disjointUnionOf` `owl:ObjectProperty` `rdfs:domain` `sh:NodeShape` `sh:hasValue` `:class` `:relation` `:viaRelationship` | 旧版有在售 / 停售的 hasValue、缺划分；新版补两个 owl:disjointUnionOf（能否连上 DimProduct 的判定在注解，左连接见 A20） |
| hierarchies | H04 | (2) | (1) | 改 | `owl:Class` `owl:hasKey` `owl:ObjectProperty` `rdfs:domain` `sh:NodeShape` `sh:hasValue` `:class` `:relation` `:viaRelationship` | 旧版无形状；新版城市的「GeographyType = 'City' 的行」转 hasValue（旧版的字面等式规则在此不生效），身份写成 owl:hasKey |
| hierarchies | H05 | (2) | (1) | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:AllDisjointClasses` `owl:ObjectProperty` `rdfs:domain` `sh:NodeShape` `sh:hasValue` `:axiom` `:class` `:relation` `:viaRelationship` | 旧版「EntityType = 'Group'，3 个」带逗号，字面等式规则不生效；新版四类都转 hasValue，并加 owl:AllDisjointClasses |
| hierarchies | H06 | (2) | (1) | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:disjointUnionOf` `owl:ObjectProperty` `rdfs:domain` `sh:NodeShape` `sh:hasValue` `:breakCycle` `:class` `:onColumn` `:relation` `:rootKey` `:viaRelationship` | 旧版有职级 hasValue、缺划分与断环；新版补 owl:disjointUnionOf 与断环个体 |
| hierarchies | H07 | (2) | (1) | 改 | `owl:NamedIndividual` `:breakCycle` `:ignoreParentOf` `:leaf` `:leafAccounts` `:node` `:parentAccount` `:root` | 旧版只有科目树；新版加各父科目的叶子集合与断环（利润的显式减法在 D32） |
| hierarchies | H08 | (2) | (1) | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:disjointUnionOf` `owl:disjointWith` `sh:NodeShape` `sh:minInclusive` `sh:maxInclusive` `sh:minExclusive` `:class` `:definedBy` | 旧版只有类与子类；新版把三层客户写成月数区间形状，加划分与 owl:disjointWith（客户集合规则在 A27 的注解） |
| hierarchies | H09 | (2) | (1) | 改 | `owl:Class` `rdfs:subClassOf` `owl:disjointUnionOf` `owl:ObjectProperty` `rdfs:domain` `sh:NodeShape` `sh:hasValue` `sh:not` `sh:alternativePath` `:class` `:relation` | 旧版缺打折交易（!=）与划分；新版补 sh:not 与 owl:disjointUnionOf，路径用 sh:alternativePath |
| hierarchies | H10 | (1) | (1) | 同 | `owl:Class` `owl:AllDisjointClasses` `sh:NodeShape` `sh:hasValue` `sh:in` `sh:alternativePath` `sh:targetClass` `sh:minCount` `sh:maxCount` `:axiom` `:class` | 同档：旧版已有三个场景的 hasValue 与「每行恰好一个场景」的形状；新版加 owl:AllDisjointClasses |
| hierarchies | H11 | (2) | (1) | 改 | `owl:Class` `owl:disjointUnionOf` `sh:NodeShape` `sh:hasValue` `:class` | 旧版缺划分；新版写 DimDate 的 owl:disjointUnionOf |
| hierarchies | H12 | (2) | (1) | 改 | `owl:Class` `rdfs:subClassOf` `sh:NodeShape` `sh:hasValue` `sh:lessThan` `:class` | 旧版缺「OnHand < SafetyStock」；新版补 sh:lessThan。零库存 ⊂ 低于安全库存按原文不是规则，不写 |
| hierarchies | H13 | (2) | (1) | 改 | `owl:Class` `rdfs:subClassOf` `owl:equivalentClass` `owl:disjointUnionOf` `sh:NodeShape` `sh:hasValue` `sh:in` `:class` | 旧版缺两个 IN 条件与划分；新版补 sh:in 与两个 owl:disjointUnionOf |
