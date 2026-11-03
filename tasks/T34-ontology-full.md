# T34 全部语义换成本体（L3a-full）与 L1+ 对比

- 状态：第 3 步已复核，暂不通过，待盲写修订后再核（Codex，2026-11-04）
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
   - 能形式化的都形式化（OWL 类、对象属性、数据属性、实例与别名、SHACL 约束；指标口径可用 SHACL-SPARQL 或注解里的 SQL 片段）。表达不了的放注解，原文完整保留。
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
