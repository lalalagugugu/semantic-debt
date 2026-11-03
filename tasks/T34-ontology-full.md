# T34 全部语义换成本体（L3a-full）与 L1+ 对比

- 状态：第 1–2 步完成（Claude Code 盲写，2026-11-04），待第 3 步 Codex 复核；DeepSeek 上下文上限待查（见记录）
- 负责：第 1–2 步 Claude Code（盲模式）；第 3 步 Codex 复核；第 4–6 步 Codex（codex-main）
- 依据：`tasks/T19a-v10-plan.md` 第一节；`decisions/2026-10-23-l1plus-l3a.md`；`decisions/2026-10-25-t22b-l3a-presentation.md`；`reports/validation/l3a-ontology-validation.md`（T26）
- 依赖：`semantic-v1.6-l1plus`；`harness-v1.1`；`eval-v1.2`
- 预算：以正式 dry-run 为准，用户批准后才跑；粗估 ≤ 15 元（Flash，错峰）。不含 L3b。

## 要回答的问题

同一份内容（L1 全文 + L1+ 的 109 条），全部写成文字和全部写成本体，大模型写 SQL 的准确率有没有差别。

旧 L3a 只把 109 条换成本体，L1 原文仍是文字，所以只回答了「补充内容换格式」。本卡回答「整个语义层换成本体」。

## 单元（用户 2026-11-03 定）

同一个 run、同一个指纹，只跑两个单元，各 109 题 × 3（主表报 98 题）：

| 单元 | 内容 | 写法 |
|---|---|---|
| SQL-L1plus | L1 + 109 条 | 文字（与主表同一份上下文，逐字节不变） |
| SQL-L3a-full | L1 + 109 条 | 全部本体 |

不重跑 SQL-L1 和旧 SQL-L3a。理由：L1 到 L1+ 是内容差别，主表已回答；旧 L3a 是中间状态，旧结果（同指纹）保留。新跑的 SQL-L1plus 同时用来量指纹变化：和主表的 L1+ 比，差多少照实报告。

## 第 1–2 步（Claude Code，盲模式）

开工自检按 AGENTS.md：试读 `$SEMDEBT_EVAL_DIR/README.md` 应被拒绝；可用的 `mcp__` 工具应为空。不读 `reports/`、`runs/`、`decisions/open-questions.md`、`harness/syntax_ladder/`。

1. **写 L3a-full 的渲染**（扩展 `render/l1plus.py` 或新文件）。输入只有 `semantic/source.yaml`、`semantic/l1plus.yaml` 和现有 L1 上下文的渲染代码。
   - L1 的表、字段、类型、关系、枚举及含义、同义词、约定、69 个指标口径，109 条的澄清、概念、别名、层级、通则，全部进本体。
   - 能形式化的都形式化（OWL 类、对象属性、数据属性、实例与别名、SHACL 约束；指标口径可用 SHACL-SPARQL 或注解里的 SQL 片段）。表达不了的放注解，原文完整保留。
   - 修掉旧 L3a 的 E07：不区分大小写的筛选不能丢。旧 L3a 里有现成写法却只放注解的条目，这次要形式化（不看 T26 的清单，自己逐条判断；第 3 步由 Codex 对照）。
   - 写法：Turtle，用 `@prefix` 和 `;` 合并同一主语，不再每个三元组一行、URI 全写。系统提示与写法说明和 SQL-L1plus 逐字节相同，只差语义上下文。
2. **核对和量**：
   - 脚本逐条核对：L1 每个表、字段、关系、枚举值、指标，和 109 条的每个编号，在 L3a-full 里都出现且数量相同。结果写 `reports/validation/l3a-full-correspondence.md`，报形式化和注解各多少条、比例。
   - 量 token：SQL-L1plus、旧 SQL-L3a、SQL-L3a-full 三份系统消息各多少 token（用 harness 的估算方法，写明方法）。
   - 查 DeepSeek 当前模型的上下文上限（官方文档，写明网址和日期）。L3a-full 超过上限的 80% 就停下报告，不自行删内容。
   - 已有单元的上下文逐文件不变（测试）。

不得调用付费模型。完成后推分支、开 PR。

## 第 3 步（Codex 复核）

逐条判：(a) 本体和文字含义是否一致，有无丢失或新歧义；(b) 旧 L3a 已知问题（E07、E09、H05 的编码）是否修好；(c) T26 找到的 16 条是否已形式化。只回条目编号与结论。有问题由盲写会话按编号修。通过后用户打 tag（建议 `semantic-v1.7-l3a-full`）。

## 第 4–6 步（Codex）

4. **查指纹**：主表是 `e72d3c7f…`，10 月 31 日是 `bc19ba97…`。开跑时以第一条响应为准，记录下来；运行中指纹变了就停。
5. **dry-run → 用户批准 → 错峰运行**。用原样 `harness.run_direct`，不套监督脚本；新 run-id，`runs/INDEX.md` 记一行。
6. **判定与报告**：
   - 判定同主表（D1 规则和流程，`runs/20261031-T31-v5-rulings-01/` 的做法），全量逐次判定；判对的部分跨厂商复核。规则不改。
   - `reports/results/l3a-full.md`：98 题和测试集 49 题的准确率；L3a-full 对 L1+ 的同题配对差和区间（按题 5,000 次自助法，seed 0，同主表）；新 L1+ 对主表 L1+ 的差（指纹变化）；三次全对 / 全错 / 时对时错题数；首轮报错率；token 和费用。
   - 错因按主表的三类（怎么算、是什么或属于谁、SQL），L3a-full 和 L1+ 各报一次。

## 不能做

- 盲写阶段不得读题库、参考答案、运行结果或任何含题号的报告；不得用子 agent 代替 Codex 复核。
- 不改 `semantic/source.yaml`、`semantic/l1plus.yaml` 和已有单元的上下文。
- 不改系统提示、评分器、判定规则。

## 记录（完成后填写）

### 第 1–2 步（Claude Code，盲模式，2026-11-04）

开工自检：试读 `$SEMDEBT_EVAL_DIR/README.md` 被拒（Operation not permitted）；会话里没有任何 `mcp__` 工具。未读 `reports/`（除本卡产出）、`runs/`、`decisions/open-questions.md`、`harness/syntax_ladder/`；未读 T26 的清单。

- 产出：
  - `render/l3a_full.py`：渲染 + 核对。复现 `uv run python -m render.l3a_full`，写 `build/contexts/SQL-L3a-full.yaml`（唯一的键 `ontology_turtle`）和 `reports/validation/l3a-full-correspondence.md`。
  - `render/context.py` 加单元 `SQL-L3a-full`（档位 `L3a-full`）；`harness/cells.py` 在 `L1PLUS_CELLS` 里加 `SQL-L3a-full`（与 SQL-L1plus 同执行器、同语法说明、同 skip_judge；`card="T34"`，不进 `CELLS`，`--cell all` 范围不变）。
  - `tests/test_l3a_full.py`：反解一致与计数、6 种篡改必被拒、E07 / H05 / E09 / 划分 / 键 / 科目树的形式化含义、系统提示与语法说明与 SQL-L1plus 逐字节相同、`run_direct --dry-run` 能解析新单元、T34 之前的全部单元上下文逐字节不变（对 `96abbed` 的 `render/context.py`）、rdflib 复核（`uv run --with rdflib pytest tests/test_l3a_full.py`）。
  - 核对结果：L1 的表 25、字段 228、枚举值 568、关系 48、指标 69、约定 15、同义词 56、多路径默认 4、数据质量 15，L1+ 109 条，本体里都出现且数量相同；从 Turtle 反解出的 SQL-L1 上下文与 L1+ overlay 与源逐字段相等。L1+ 形式化 77 条（71%）、注解 32 条（29%，其中 11 条带 SQL 片段）；三元组 8,404 个，注解 3,082（37%）、形式化 5,322（63%）。rdflib 7.6.0 解析同一份文本得到同样 8,404 个三元组。
  - token（harness 的 `estimate_tokens_from_text`，整条系统消息）：SQL-L1 41,084；SQL-L1plus 66,698；旧 SQL-L3a 156,469；SQL-L3a-full 94,709（SQL-L1plus 的 1.42×）。
- 偏离与理由：
  - **DeepSeek 上下文上限没查到**：会话里访问 `api-docs.deepseek.com` 的命令被权限拒绝，盲模式也没有 WebFetch。80% 门槛因此未判定，需用户（或 Codex）查官方文档后补记网址、日期与上限，再决定是否进入第 4 步。
  - 上下文文件沿用旧 SQL-L3a 的做法，是只有一个键 `ontology_turtle` 的 YAML（harness 对 `build:` 上下文一律用 yaml 代码块）；这样不改 harness 的拼接逻辑，系统提示与写法说明逐字节同 SQL-L1plus。
  - 逐条判断后手写的形式化放在 `render/l3a_full.py` 的 `EXTRA`（每条只写原文明说的内容）；故意不形式化的：H12「零库存 ⊂ 低于安全库存」（原文说不是规则）、D31 的默认科目（只在落到战略计划表时成立）、枚举值清单不写成闭合 `sh:in`（L1 没说清单完整）。
  - 旧 L3a 的 E07、E09、H05 问题按我读旧 `render/l1plus.py` 的理解修：E07 全部颜色用 `sh:pattern` + `sh:flags "i"`，蓝色另保留 `lower(ColorName) = 'blue'`；E09 的「PromotionKey = 1 / != 1」记为条件（`:condition`）并写成 `sh:hasValue` / `sh:not`，名单写成 `sh:in`；H05「EntityType = 'Group'，3 个」这类带逗号的成员定义也转成 `sh:hasValue`。是否就是 T26 指的问题，由第 3 步 Codex 对照。
  - 盲模式下 `semantic/tuning/` 不可读：`tests/test_combo.py` 两项失败、`tests/test_scorer_v2_shared.py` 无法收集（读不到 `scorer-corpus`），与本卡无关；其余 1,103 项通过、23 项跳过。`render/render_all.py` 在盲模式下会把 `reports/validation/context_sizes.md` 的调优单元写成「未渲染」，所以没有提交它的改动。
  - uv 在沙箱里读不到自带的 Python，本会话用 `UV_PYTHON=/opt/homebrew/bin/python3.14 UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR=$TMPDIR/uvcache`；`uv.lock` 未变。
- 工时：约 3 小时（Claude Code 会话）。
