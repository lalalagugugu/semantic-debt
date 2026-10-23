# T22 L1+（内容补全与歧义澄清）与 L3a（同内容的形式化 ontology）

- 状态：进行中（2026-10-23：第 1 步歧义自查 `semantic/l1plus-audit.md`、第 2 步概念清单 `semantic/l1plus-concepts.md` 已交，待用户审定清单后写第 3 步）
- 负责：Claude Code（第 1–3 步盲模式；第 4–6 步普通模式，可由另一个会话做）；Codex 复核
- 模式：盲（写内容）→ 普通（渲染、运行）
- 依据：`decisions/2026-10-23-l1plus-l3a.md`
- 依赖：`semantic-v1.4`；`harness-v1.1`、`eval-v1.2`
- 预算：两个单元合计 ≤ 10 元（Flash）

## 第 1–3 步（盲模式）

开工自检按 AGENTS.md：试读 `$SEMDEBT_EVAL_DIR/README.md` 应被拒绝；可用的 `mcp__` 工具应为空。**不读** `reports/`、`runs/`、`decisions/open-questions.md`（含题号）。

1. **歧义自查**：逐条检查 `semantic/source.yaml` 的约定、指标、关系、数据集说明，列出所有「条件没写全、允许两种以上读法」的条文，写进 `semantic/l1plus-audit.md`：位置、可能的读法、拟采用的读法与理由。
2. **常用业务概念清单**：从「常规经营分析需求」出发（参照 `docs/design-v5-public.md` 汇总层第 5 条的做法），列出派生概念（如客户首购、复购、队列一类）、需要别名的实体、类层次。只列名称、一句话用途和拟定义，**交用户审定后**才写正文。
3. **写 `semantic/l1plus.yaml`**：澄清条目（引用 source.yaml 的位置）与新增概念（定义写到能直接写成一条 SQL 的程度，给出适用条件与例外）。规矩：每条只有一种读法；不写「视情况」；不引用任何题目。

## 复核（Codex）

把 `l1plus-audit.md` 与 `l1plus.yaml` 交 Codex：逐条判 (a) 是否只有一种读法、有无新歧义；(b) 与题库参考答案的读法是否冲突。只回条目编号与结论。冲突条目由用户定，盲写会话按条目编号修改。

## 第 4–6 步（普通模式）

4. 渲染：`SQL-L1plus` = L1 + `l1plus.yaml`；`SQL-L3a` = 同内容生成的 Turtle（OWL 类、对象属性、数据属性、实例别名；SHACL 约束与规则）。脚本逐条核对两份内容一一对应；已有单元的上下文逐文件不变。打 tag 由用户决定。
5. dry-run → 用户批准 → 错峰运行，各 109 题 × 3 次。
6. `reports/results/l1plus-l3a.md`：L1+ vs L1、L3a vs L1+ 的同题配对比较与区间。

## 不能做

- 不得读题库、参考答案、运行结果或任何含题号的报告来决定写什么；不得用子 agent 代替 Codex 复核。
- 不改 `semantic/source.yaml` 与已有单元的上下文。

## 记录（完成后填写）

- 产出：
- 偏离与理由：
- 工时：
