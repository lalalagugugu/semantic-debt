# T34 全部语义换成本体（L3a-full）与 L1+ 对比

- 状态：第 3 步通过（#265）；第 4–6 步预检中，待 semantic-v1.7-l3a-full 标签发布与正式 dry-run 后用户批准（2026-11-04）
- 负责：第 1–2 步 Claude Code（盲模式）；第 3 步 Codex 复核；第 4–6 步 Codex（codex-main）
- 依据：`tasks/T19a-v10-plan.md` 第一节；`decisions/2026-10-23-l1plus-l3a.md`；`decisions/2026-10-25-t22b-l3a-presentation.md`；`reports/validation/l3a-ontology-validation.md`（T26）
- 依赖：`semantic-v1.6-l1plus`；`harness-v1.1`；`eval-v1.2`
- 预算：以正式 dry-run 为准，用户批准后才跑；粗估 ≤ 25 元（Flash，错峰，四个单元）。不含 L3b。

## 要回答的问题

假设、来源和预测见 `tasks/T19a-v10-plan.md` 第六节。每组比较内容逐条相同、只换写法：

1. 语义写得好（L1：完整，但有歧义）时，本体写法有没有帮助。
2. 语义已经写得很详尽（L1+：逐条消歧）时，还值不值得换成本体。

旧 L3a 是混合写法（L1 原文是文字、109 条是本体），两个问题都答不干净，不复用。

## 单元（用户 2026-11-03 定）

同一个 run、同一个指纹，四个单元，题集、次数和运行参数与主表的 SQL-L1plus 一致（每题 3 次；结果只报 98 题，测试集 49 题只在和调优单元比时用，不报 109 题）：

| 组 | 单元 | 内容 | 写法 |
|---|---|---|---|
| 1 | SQL-L1 | L1 全部 | 文字（与主表同一份上下文，逐字节不变） |
| 1 | SQL-L1-onto | L1 全部 | 全部本体 |
| 2 | SQL-L1plus | L1 全部 + 109 条 | 文字（与主表同一份上下文，逐字节不变） |
| 2 | SQL-L3a-full | L1 全部 + 109 条 | 全部本体 |

新跑的两个文字单元同时用来量指纹变化：和主表的 L1、L1+ 比，差多少照实报告。

## 第 1–2 步（Claude Code，盲模式）

开工自检按 AGENTS.md：试读 `$SEMDEBT_EVAL_DIR/README.md` 应被拒绝；可用的 `mcp__` 工具应为空。不读 `reports/`、`runs/`、`decisions/open-questions.md`、`harness/syntax_ladder/`。

1. **写两份本体的渲染**（扩展 `render/l1plus.py` 或新文件）：SQL-L1-onto 只含 L1；SQL-L3a-full 含 L1 和 109 条。两份里 L1 部分的本体逐字节相同，SQL-L3a-full 只多出 109 条。输入只有 `semantic/source.yaml`、`semantic/l1plus.yaml` 和现有 L1 上下文的渲染代码。
   - L1 的表、字段、类型、关系、枚举及含义、同义词、约定、69 个指标口径，109 条的澄清、概念、别名、层级、通则，全部进本体。
   - 能形式化的都形式化（OWL 类、对象属性、数据属性、实例与别名、SHACL 约束；只用 OWL 2 和 SHACL Core 的标准构造，不用 SHACL-SPARQL、SHACL-AF 规则或其他查询式规则；指标口径放注解里的 SQL 片段）。表达不了的放注解，原文完整保留。
   - 109 条复用旧 L3a 的来源和生成器，不另起炉灶：内容仍从 `semantic/l1plus.yaml` 生成，在 `render/l1plus.py` 的基础上改，不手抄旧 Turtle。改的只有写法质量，下面几处：
     - 修掉 E07：不区分大小写的筛选不能丢。
     - 有现成 OWL / SHACL 写法却只放注解的条目，这次要形式化（不看 T26 的清单，自己逐条判断；第 3 步由 Codex 对照）。
     - 层级里写了互斥或覆盖的，写成不相交 / 覆盖公理；属性写定义域和值域；「成员定义开头的字面等式转 hasValue」这类规则要对所有条目生效（T26 发现 H04、H05 没生效）。
     - 同一套标准用于 L1 部分，两份本体的写法质量一致。
   - 改动逐条记在 `reports/validation/l3a-full-correspondence.md`：109 条里哪些和旧 L3a 一样、哪些改了、为什么改。
   - 写法：Turtle，用 `@prefix` 和 `;` 合并同一主语，不再每个三元组一行、URI 全写。系统提示与写法说明和 SQL-L1plus 逐字节相同，只差语义上下文。
2. **核对和量**：
   - 脚本逐条核对：L1 每个表、字段、关系、枚举值、指标在两份本体里都出现且数量相同；109 条的每个编号在 SQL-L3a-full 里出现、在 SQL-L1-onto 里不出现。结果写 `reports/validation/l3a-full-correspondence.md`，两份各报形式化和注解多少条、比例。
   - 量 token：SQL-L1、SQL-L1-onto、SQL-L1plus、SQL-L3a-full 四份系统消息各多少 token（用 harness 的估算方法，写明方法）。
   - 查 DeepSeek 当前模型的上下文上限（官方文档，写明网址和日期）。任何一份超过上限的 80% 就停下报告，不自行删内容。
   - 已有单元的上下文逐文件不变（测试）。

不得调用付费模型。完成后推分支、开 PR。

## 第 3 步（Codex 复核）

逐条判：(a) 本体和文字含义是否一致，有无丢失或新歧义；(b) 旧 L3a 已知问题（E07、E09、H05 的编码）是否修好；(c) T26 找到的 16 条是否已形式化。只回条目编号与结论。有问题由盲写会话按编号修。通过后用户打 tag（建议 `semantic-v1.7-l3a-full`）。

## 第 4–6 步（Codex）

4. **查指纹**：主表是 `e72d3c7f…`，10 月 31 日是 `bc19ba97…`。开跑时以第一条响应为准，记录下来；运行中指纹变了就停。
5. **dry-run → 用户批准 → 错峰运行**。用原样 `harness.run_direct`，不套监督脚本；新 run-id，`runs/INDEX.md` 记一行。
6. **判定与报告**：
   - 判定同主表（D1 规则和流程，`runs/20261031-T31-v5-rulings-01/` 的做法），全量逐次判定；判对的部分跨厂商复核。规则不改。
   - `reports/results/l3a-full.md`：四个单元 98 题的准确率；两组各自的同题配对差和区间（本体减文字，按题 5,000 次自助法，seed 0，同主表）；新 L1、新 L1+ 对主表的差（指纹变化）；三次全对 / 全错 / 时对时错题数；首轮报错率；token 和费用。不对两组的差再做比较。
   - 错因按主表的三类（怎么算、是什么或属于谁、SQL），四个单元各报一次。

## 不能做

- 盲写阶段不得读题库、参考答案、运行结果或任何含题号的报告；不得用子 agent 代替 Codex 复核。
- 不改 `semantic/source.yaml`、`semantic/l1plus.yaml` 和已有单元的上下文。
- 不改系统提示、评分器、判定规则。

## 记录（完成后填写）

### 第 1–2 步（Claude Code，盲模式，2026-11-04）

开工自检：试读 `$SEMDEBT_EVAL_DIR/README.md` 被拒（Operation not permitted）；会话里没有任何 `mcp__` 工具。未读 `runs/`、`decisions/open-questions.md`、`harness/syntax_ladder/`、T26 的清单；`reports/` 只写本卡的核对报告。第一轮按合并前的卡（只有 SQL-L3a-full）做，合入 main（#258–#260）后按协调会话 2026-11-04 的补充要求补做；两者冲突处以补充要求为准，见「偏离与理由」。

- 产出：
  - `render/l3a_full.py`：同一个生成器（`build`）只喂 L1 得到 SQL-L1-onto，喂 L1 和 109 条得到 SQL-L3a-full。复现 `uv run python -m render.l3a_full`，写 `build/contexts/SQL-L1-onto.yaml`、`build/contexts/SQL-L3a-full.yaml`（都只有一个键 `ontology_turtle`）和 `reports/validation/l3a-full-correspondence.md`。
  - `render/context.py` 加单元 `SQL-L1-onto`、`SQL-L3a-full`；`harness/cells.py` 在 `L1PLUS_CELLS` 里注册两者（与 SQL-L1 / SQL-L1plus 同执行器、同语法说明；`card="T34"`；不进 `CELLS`，`--cell all` 范围不变）。
  - `tests/test_l3a_full.py`（17 项）：两份的反向重建；SQL-L1-onto 里 109 条编号一个都不出现；子图与差额逐条追溯；篡改必被拒；不同 `PYTHONHASHSEED` 下序列化逐字节相同；三档表覆盖 109 条；E07 / H04 / H05 / E09 / 划分 / 键 / 科目树的形式化含义；两份本体的系统提示与语法说明分别与 SQL-L1plus、SQL-L1 逐字节相同；`run_direct --dry-run` 能解析两个新单元；T34 之前的全部单元上下文逐字节不变（对 `96abbed` 的 `render/context.py`）；rdflib 复核两份文本（`uv run --with rdflib pytest tests/test_l3a_full.py`）。
- 核对结果：
  - L1 的表 25、字段 228、枚举值 568、关系 48、指标 69、约定 15、同义词 56、多路径默认 4、数据质量 15，两份本体里都出现且数量相同；两份都能反向重建出与 SQL-L1 上下文逐字段相同的内容，SQL-L3a-full 另能重建出 L1+ overlay。
  - 子图：SQL-L1-onto 4,975 个三元组全部在 SQL-L3a-full 的 8,404 个里；差 3,429 个 = 109 条各自生成的 3,420 个 + L1+ 文件头 `:L1plus` 的 9 个（`l1plus.yaml` 顶层的 version、base、title、as_of_date 与两个词汇声明，不属于任何一条，保留是为了能逐字段重建 SQL-L1plus 的 `l1plus` 节）。另外文本上 SQL-L1-onto 恰好是 SQL-L3a-full 的前缀（109 条的三元组写在各自的块里，没有并进 L1 主语的块）。
  - 三档（与 T26 对齐，逐条判断，理由与所用构造见报告「逐条」表）：
    - 109 条：旧 SQL-L3a (1) 12 / (2) 18 / (3) 79；SQL-L3a-full (1) 58（53%） / (2) 36（33%） / (3) 15（14%）。27 条与旧版同档，82 条档位提高，没有降档。
    - L1：约定 15 条都是 (2)；指标 12 个 (1)（纯比率，分子分母都链接到指标）、57 个 (2)，没有 (3)。
    - 没有用 SHACL-SPARQL 或其他查询式规则；指标口径用注解里的 SQL 片段。
    - 上一版报的「77 条 / 71%」是宽口径（任何非注解、非 `:ref` 的三元组都算形式化），保留作参考。
  - H04：城市的「GeographyType = 'City' 的行，517 个」已转 hasValue（旧版不生效），身份写成 owl:hasKey；H05 同样已生效。
  - token（harness 的 `estimate_tokens_from_text`，整条系统消息）：SQL-L1 41,084；SQL-L1-onto 58,115；SQL-L1plus 66,698；SQL-L3a-full 94,716；参考：旧 SQL-L3a 156,469。
  - 上下文上限：DeepSeek 官方文档 https://api-docs.deepseek.com/quick_start/pricing ，2026-11-04 由协调会话查（盲写会话访问被拒），deepseek-flash（DeepSeek-V4.1-Flash-1017）上下文 1M token，最大输出 384K。四份最大 94,716，占 9.5%，都远低于 80%。
- 偏离与理由：
  - **两份的一致性按图核对，不要求文本逐字节相同**（卡写「L1 部分的本体逐字节相同」；按协调会话补充要求改为子图 + 差额逐条追溯）。实际文本也是前缀关系，测试一并检查。
  - **没有在 `render/l1plus.py` 上改**（卡写复用旧生成器）：内容来源相同（`render.l1plus.overlay()`，即 `semantic/l1plus.yaml`），但旧生成器是逐行全 URI 三元组 + 通用注解树，新的写法要求 `@prefix` / `;`、字段级谓词和能反向重建的编码，序列化和编码都得重写；另起 `render/l3a_full.py` 也让旧 SQL-L3a 保持逐字节不变。没有手抄旧 Turtle。
  - **形式化计数改用三档**（协调会话补充要求），上一版的「77 / 71%」标为宽口径保留。
  - 上下文文件沿用旧 SQL-L3a 的做法，是只有一个键 `ontology_turtle` 的 YAML（harness 对 `build:` 上下文一律用 yaml 代码块），不改 harness 的拼接逻辑。
  - 逐条手写的形式化放在 `render/l3a_full.py` 的 `EXTRA`，只写原文明说的内容。故意不形式化：H12「零库存 ⊂ 低于安全库存」（原文说不是规则）、D31 的默认科目（只在落到战略计划表时成立）、枚举清单不写成闭合 `sh:in`（L1 没说清单完整）。
  - 旧 L3a 的 E07、E09、H05 问题按我读旧 `render/l1plus.py` 的输出理解修，是否就是 T26 指的问题由第 3 步对照。
  - 盲模式下 `semantic/tuning/` 和 `scorer-corpus` 不可读：`tests/test_combo.py` 两项失败、`tests/test_scorer_v2_shared.py` 无法收集，与本卡无关；其余 1,108 项通过、23 项跳过。`render/render_all.py` 在盲模式下会把 `reports/validation/context_sizes.md` 的调优单元写成「未渲染」，所以没有提交它的改动。
  - uv 在沙箱里读不到自带的 Python，本会话用 `UV_PYTHON=/opt/homebrew/bin/python3.14 UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR=$TMPDIR/uvcache`；`uv.lock` 未变。会话内 `git fetch` / `gh` 读不到凭据，fetch 由用户运行，PR #261 由协调会话开。
- 工时：约 5 小时（Claude Code 会话，两轮）。

### 第 3 步（Codex 独立复核，2026-11-04）

- 基线：`0072999`（`origin/T34-work`）；复核分支 `T34-review`，未向 T34-work 推送。
- 报告：`reports/validation/t34-codex-review.md`，含 109 条新旧档位、15 条 L1 约定、69 项 L1 指标、T26 的 16 条对照及按编号的盲写修改清单。
- 结论：暂不通过。E10 增加了日期行断言含义；部分核心条件仍在注解，档位需修订或补齐。原报第 (1) 档 58 条中，按报告定义有 39 条依赖项目自定义谓词表达核心。
- 工程：独立 RDFlib 子图与差集核对通过，3,429 = 3,420 + 9；三种 PYTHONHASHSEED 字节一致；旧上下文渲染、两个新单元显式选择、系统提示和语法回归通过（外部文件不可用的边界见报告）。
- 测试：T34 17 passed；全套 1 failed / 1321 passed / 23 skipped。唯一失败为外部上下文缺 SEMDEBT_EVAL_DIR，不作为通过。未修改实现、未打 tag、未启动第 4–6 步，付费模型调用 0。

### 第 3 步修订（Claude Code，盲模式，2026-11-04）

在 `049ee04`（`origin/T34-review`，fast-forward）上修订。按协调会话的批准只读了 `reports/validation/t34-codex-review.md`，没有读它引用的 T26 报告。付费调用 0。

- 改了哪些条目：
  - **E10（必须修）**：取值节点不再用物理列属性作谓词。每个说法按大洲拆成节点：`:continent`、`:onColumn`（字段只作宾语）、`:value`，另有 `:selects [ sh:path 季节字段 ; sh:hasValue 取值 ]` 与 `:whenContinent [ sh:path DimGeography.ContinentName ; sh:hasValue 大洲 ]`。全图扫过：没有其他三元组用 `retail:` / `rel:` 属性作谓词（测试）。
  - **D10、D11、D19**：每档改成 `sh:NodeShape` + `sh:property [ sh:path … ; 边界 ]`，分别绑到 `:D10`（年龄）、`DimCustomer.YearlyIncome`、新声明的 `:D19.累计占比`；`:bandOf` 保留。
  - **D23**：哨兵值节点加 `:selects [ sh:path DimStore.CloseDate ; sh:not [ sh:pattern "^2090-12-31" ] ]`（CloseDate 是字符串列，用前缀匹配）。
  - **A19**：加 `retail:DimPromotion owl:hasKey ( PromotionKey )`。
  - **A33**：加 FactStrategyPlan 的形状（AccountKey `sh:in` 17 个叶子、Amount `sh:minExclusive 0`）。
  - **H07**：加 `:H07.上级科目闭包`（owl:TransitiveProperty），`:parentAccount rdfs:subPropertyOf` 它。
  - **A24**：去掉挂在原始数量列上的比较形状，改为链接到 H12 的门店 × 产品组合类（比较在那里是形状）。
  - 其余清单与 T26 条目没有标准写法的，在报告「第 3 步复核清单的处理」表里逐条标「未做」和原因（问题措辞触发的例外、参数化窗口、聚合、按订单去重计数、无环约束、除法等）。
- 档位（1S / 1C / 2 / 3，按复核档；三条与复核不同，各附证据）：
  - 109 条：旧 SQL-L3a 1 / 11 / 18 / 79；SQL-L3a-full **19 / 21 / 54 / 15**。与复核（16 / 22 / 56 / 15）不同的：E10（复核 2 → 1S，修了编码，语义探针通过）、D11（复核 1C → 1S，分档已是绑定字段的标准形状，正反例通过）、D23（复核 2 → 1S，补了哨兵排除形状，正反例通过；按期间筛选是问题参数）。D10 补了绑定，但年龄派生式只在注解，仍按复核归 (2)。
  - L1：约定 0 / 0 / 15 / 0；指标 0 / 0 / 69 / 0。12 个纯比率（加折扣率共 13 个链接分子分母的）都归 (2)；D16、D17 同理归 (2)。
  - 宽口径 77 / 71% 保留在报告里作参考，不用于结论。
- 测试（`tests/test_l3a_full.py`，22 项）：新增语义探针（owlrl 的 RDFS 与 OWL-RL 闭包后，两份本体都没有任何节点成为 `retail:` 表或 `class:` 类的实例，并确认探针能抓到旧 E10 写法）、物理列谓词扫描、pyshacl 正反例（D10、D11、D19 的分档，D23 哨兵，A33 计划表形状，E10 的季节与大洲形状）、档位规则（1S 必须有标准构造、1C 必须有自定义谓词、没有降档、没有查询式谓词）。`uv run --with rdflib --with owlrl --with pyshacl pytest tests/test_l3a_full.py`：22 passed。全套（不装这三个可选依赖）：1,109 passed、27 skipped、2 failed（`test_combo` 两项读不到盲模式拒读的 `semantic/tuning/`，与上一轮相同）；`test_scorer_v2_shared.py` 仍因 `scorer-corpus` 不可读无法收集。
- token（整条系统消息，估算）：SQL-L1 41,084、SQL-L1-onto 58,115、SQL-L1plus 66,698 不变；SQL-L3a-full 94,716 → **96,006**（E10、分档、A33 等新增结构）。旧 SQL-L3a 156,469 不变。最大占上下文上限 9.6%。
- 子图：SQL-L1-onto 4,975 个三元组不变；SQL-L3a-full 8,404 → 8,609，差额仍逐条追溯到 109 条与 L1+ 文件头。
- 偏离与理由：
  - 卡上「指标口径可用 SHACL-SPARQL」改为「只用 OWL 2 和 SHACL Core 的标准构造」（协调会话 2026-11-04 要求）：SHACL-SPARQL、SHACL-AF 规则等查询式规则属于 L3b，混进来就不是只换写法。
  - E10、D11、D23 三条与复核档不同，理由见上与报告逐条表，交 Codex 再核。
  - 自定义谓词一个未删，已有事实保留；A24 去掉的是本卡上一轮自己加的、挂在原始列上的比较形状（复核指出会被当成聚合后的筛选），原文不变。
- 工时：约 2 小时。

### 第 3 步第二轮修订（Claude Code，盲模式，2026-11-04）

在 `origin/T34-review2`（PR #264）上 fast-forward 后修订；只读了 `reports/validation/t34-codex-review.md` 的「第二轮」一节，没有读 T26 报告。付费调用 0。只改复核点名的 6 条：

- **D19**：三个分档的阈值改成与 `:D19.累计占比`（xsd:double）一致的 `"0.8"^^xsd:double`、`"0.95"^^xsd:double`。新增探针：每个阈值的等于、略小、略大各一个 double 值，恰好只入原文规定的一档（0.8 → A、0.95 → B）。
- **A40**：在 `:A40 :axiom` 加 SHACL Core 条件形状：targetClass DimProductSubcategory，`sh:or ( [ sh:not [ 子类键 hasValue 19 ] ] [ 路径 ( 子类 → 品类外键关系 , ProductCategoryName ) hasValue "Computers" ] )`。只用原文给的子类键，不猜父品类键，不新建描述节点。正反例：键 19 + Computers 通过，键 19 + 其他品类不通过，其他键不受约束。
- **D05**：`:D05` 加 `sh:property [ sh:path ( [ sh:inversePath rel:FactOnlineSales.CustomerKey-DimCustomer ] retail:FactOnlineSales.SalesOrderNumber ) ; sh:minCount 2 ]`。正反例：同一订单号两行不通过，两个不同订单号通过。窗口留在注解，档位 (2)。
- **A41**：H07 的 24 个科目个体逐个 `sh:targetNode`，`[ sh:oneOrMorePath :parentAccount ]` 的值 `sh:not [ sh:in (自身) ]`。正反例：断环后的图通过，加回被断的 1 → 24 父边后不通过。理由改为：对任意未知节点的通用无环检查没有直接写法，已知的有限个体可以逐个检查。档位不变（1C，根与断环仍用自定义谓词记录）。
- **A38、H06**：「未做」理由更正，限制分开写：原文没有列全员工之间的上下级边（输入不足）；对任意未知节点的通用无环检查没有直接写法（SHACL Core 有 sh:oneOrMorePath）；业绩求和是算术，做不了。
- **D05b**：「只能数行」的理由改为：缺的是只取正销量的中间行、同时绑定当前客户和窗口；也不能从订单号反查销售行，因为订单号有跨客户复用。档位 (2)。
- 档位不变：109 条 1S / 1C / 2 / 3 = 19 / 21 / 54 / 15；L1 约定 15 条、指标 69 个都是 (2)。
- 子图：SQL-L1-onto 4,975 不变；SQL-L3a-full 8,609 → 8,877，差额仍逐条追溯到 109 条与文件头；文本仍是前缀关系。
- token：SQL-L3a-full 96,006 → **97,219**；SQL-L1、SQL-L1-onto、SQL-L1plus、旧 SQL-L3a 不变。
- 测试：`uv run --with rdflib --with owlrl --with pyshacl pytest tests/test_l3a_full.py` 26 passed。全套（不装三个可选依赖）1,109 passed、31 skipped、2 failed（`test_combo` 两项读不到盲模式拒读的 `semantic/tuning/`，与前几轮相同）。
- 发现：整数阈值与取值写成了 Turtle 默认的 xsd:integer，而对应字段声明为 xsd:int（与 D19 同类）。协调会话决定统一，见下一节。
- 工时：约 1 小时。

### 形状字面量的数据类型统一（Claude Code，盲模式，2026-11-04，协调会话要求）

- 规则：所有形状里的字面量（sh:hasValue、sh:in、sh:min/maxInclusive、sh:min/maxExclusive）的数据类型一律等于路径属性声明的 rdfs:range；路径是序列时取最后一段，sh:alternativePath 的各分支 range 必须相同。生成器用 `typed(值, range)` 写这些字面量；成员定义的形状按所在字段的 range 自动取类型。
- 全图扫描后改了 **40 个字面量**（按路径属性计 48 处：H09、H10 的路径是两张事实表的 sh:alternativePath，一个字面量对应两个属性），涉及 8 条：A33（AccountKey 的 sh:in 17 个 → xsd:int，Amount 的下界 → xsd:double）、A40（子类键 19 → xsd:int）、D11（7 个收入边界 → xsd:double）、E09（PromotionKey 1 的两处 → xsd:int）、H01（SalesQuantity 的 0 两处、channelKey 2 → xsd:int）、H09（PromotionKey 1 两处 → xsd:int）、H10（三个场景的 hasValue 与「恰好一个场景」的 sh:in (1 2 3) → xsd:int）、H12（OnHandQuantity 0 → xsd:int）。值域为 xsd:integer 的派生属性（D10 年龄、H08 月数）和字符串值本来就一致，没有改。SQL-L1-onto 里没有形状，0 处。档位不变。
- 解析器把带类型的数值字面量读成数值，并按 Turtle 规则区分 xsd:integer / xsd:decimal / xsd:double。
- 测试：新增通用测试，两份本体里形状约束的每个字面量（共 155 个），类型都等于对应路径属性的 range；另按 D19 的做法补 xsd:int / xsd:double 数据的 pyshacl 正反例（H09 无折扣交易、A33 计划表、D11 收入档边界）。原有正反例的数据改成按字段声明的类型（xsd:int / xsd:double）。`uv run --with rdflib --with owlrl --with pyshacl pytest tests/test_l3a_full.py`：28 passed。全套（不装三个可选依赖）：1,110 passed、32 skipped、2 failed（同前，`test_combo` 读不到盲模式拒读的 `semantic/tuning/`）。
- 子图：SQL-L1-onto 4,975、SQL-L3a-full 8,877，三元组数不变（只改字面量类型），差额归属与前缀关系仍成立。
- token：SQL-L3a-full 97,219 → **97,358**；其余三份不变。

### 第 4–6 步预检（Codex，2026-11-04，未付费）

- 计划 run-id：`20261104-T34-ontology-full-01`；分支 `T34-run`。
- 文字上下文与历史渲染逐字节相同，完整系统消息哈希与主表源日志相同；四单元 109 题与原 SQL-L1plus 题面哈希一致，均每题 3 次、并发 4、执行超时 120 秒。
- 原生估价函数：1,308 次作答、预计 1,440 调用、错峰 23.8252158 元；按原 `--est-from-args` 参数。
- 正式 CLI dry-run 尚未通过：已 fetch --tags 并核对远端，未见 `semantic-v1.7-l3a-full`，原生语义版本检查退出 2。没有造标签或绕过；待发布后重跑并交用户批准。
- 预检：`reports/validation/t34-run-preflight.md`；结构化记录 `runs/20261104-T34-ontology-full-01/preflight.json`，INDEX 已登记为计划/未启动。
- API 调用 0、费用 0；尚无新指纹、作答、判定或准确率。原样 harness，不套监督脚本；后续判定与报告按卡片和本次用户指示。
