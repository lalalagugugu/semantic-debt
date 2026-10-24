# T22 L1+（内容补全与歧义澄清）与 L3a（同内容的形式化 ontology）

- 状态：进行中（2026-10-23：第 1–3 步已交；2026-10-24：Codex 复核完，用户裁决 R1–R10，盲写会话按条目编号修订完 `semantic/l1plus.yaml`（version 2）与 `semantic/l1plus-audit.md`；同日 Codex 第二轮复查 b97cf93，用户裁决 R11、R12，按条目编号再改成 version 3。下一步：交 Codex 再查，通过后第 4–6 步在普通模式）
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

## 复核结论与用户裁决（2026-10-24）

Codex 复核只回条目编号与结论，由协调会话转给本会话（不含题号、题面）。需裁决的十项由用户定，**全部按建议**：

| 裁决 | 内容 | 涉及条目 |
|---|---|---|
| R1 | 门店默认范围 = 全部门店（含虚拟门店），只有明确说「实体店」才筛 | A01、H02、A29、A30、A31、D22、D24 |
| R2 | 「未知」属性组 / 对象保留，用键标识，不删除；占比分母不因此缩小 | A20、A21、A26、D19 |
| R3 | 颜色等文本属性：分组按原值（大小写不合并），筛选不区分大小写 | A36、E07 |
| R4 | 订单数 / 购买次数默认按全部交易订单；正销量版本另起名字；窗口内两单率与首购后限定天数回购率分别定义 | D05、D06、D07 |
| R5 | 活动默认按活动键（实例）；只在明确问「同名活动」时合并成家族 | A19、E09、H09 |
| R6 | 日均销量两种口径（全渠道 ÷ 日历天数、线上 ÷ 有交易日）分别命名 | D29 |
| R7 | 预测拆成偏差（带符号）、误差（绝对值）、准确度（1 − 绝对相对误差） | D31 |
| R8 | 同店维持「对比年份」，写明「有销售」的含义；门店范围随 R1 | A29 |
| R9 | 科目树 1 ↔ 24 成环：以科目 1 为根断环；利润写成显式减法例外；写明符号、停止、去重 | A41、H07、A33、E12、D32 |
| R10 | 员工父链 1 ↔ 18 成环：断环，遇重复即停；根由盲写会话提出并写明理由 | A38、H06 |

| R11 | 裸「可售天数 / 库存覆盖天数」默认 = 线上销量 ÷ 有交易的天数；全渠道销量 ÷ 日历天数须点名才用，两者分别命名 | D29（及 A03、A09） |
| R12 | 裸「相机」默认 = 整个相机品类；只有出现具体单品词时才按子类处理并适用 no_exact_mapping 规则 | E05 |

R11、R12 是第二轮复查（b97cf93）后用户另行裁决的（2026-10-24）。第二轮按复查意见改的条目：A02、A03、A04、A10、A14、A15、A17、A21、A24、A26、D02、D04、D06b、D09、D15、D18、D19、D20、D31、E05、E13，明细见 `semantic/l1plus-audit.md` 文末「第二轮复查」；零 / NULL 分母的通用规则移进会被渲染的 `general_rules.G01`。

R10 的根：**18**（唯一的 Sales Group Manager；其余 292 条上级关系都是低一级职级指向高一级，唯独 18 → 1 反向）。理由写在 `l1plus.yaml` H06。

无需裁决、按复核意见修订的条目与修订内容见 `semantic/l1plus-audit.md` 文末「复核修订（2026-10-24）」与各条的「已改」；
`l1plus.yaml` 里每条改过的条目带 `rev` 字段（R1–R10 或「复核」），渲染时去掉。新增四个概念变体 D05b、D06b、D06c、D07b（R4）。

## 第 4–6 步（普通模式）

4. 渲染：`SQL-L1plus` = L1 + `l1plus.yaml`；`SQL-L3a` = 同内容生成的 Turtle（OWL 类、对象属性、数据属性、实例别名；SHACL 约束与规则）。脚本逐条核对两份内容一一对应；已有单元的上下文逐文件不变。打 tag 由用户决定。
5. dry-run → 用户批准 → 错峰运行，各 109 题 × 3 次。
6. `reports/results/l1plus-l3a.md`：L1+ vs L1、L3a vs L1+ 的同题配对比较与区间。

## 不能做

- 不得读题库、参考答案、运行结果或任何含题号的报告来决定写什么；不得用子 agent 代替 Codex 复核。
- 不改 `semantic/source.yaml` 与已有单元的上下文。

## 记录（完成后填写）

- 产出（第 1–3 步，2026-10-24 按复核修订）：`semantic/l1plus-audit.md`（歧义 A01–A41，A40、A41 为第 3 步核数据时新发现的 L1 事实错误）；`semantic/l1plus-concepts.md`（用户 2026-10-23 审定，⚑ 六项均按建议）；`semantic/l1plus.yaml`。数据事实对 `$SEMDEBT_DATA_DIR/parquet` 实测（隔离修复后，盲模式只放行 raw / parquet / chdb）。
- 偏离与理由：
  - **隔离缺口（2026-10-23，第 1–2 步会话发现并报告）**：盲模式设置（`templates/claude-settings.blind.json` 生成的 `.claude/settings.local.json`）对 `$SEMDEBT_DATA_DIR` 只禁读了 `runs-raw/`，数据目录其余部分可读。本会话为确认 profiling 之外有无可用数据，运行过一次 `ls "$SEMDEBT_DATA_DIR"`（只列顶层、未递归），由此看到了这些目录 / 文件**名**：`eval-ro-41ab616`、`eval-ro-4b6c098`、`eval-ro-56ade6c`、`eval-ro-56c10e9`、`eval-ro-6234d29`、`eval-ro-926acdf`、`eval-ro-bf8e095`、`eval-ro-e3aaed6`、`eval-ro-eval-v1`、`eval-ro-eval-v1.1`、`eval-ro-eval-v1.2`、`handoff-claude`、`handoff-codex`、`handoff-compare`、`scorer-corpus`、`t05-finalize`、`t12-final`、`t19b-spotcheck`、`rules-backfill`、`interface-probes`、`dry-runs`、`anchor-refs`，以及 `t13-*.out`、`t13-L0-*.json/yaml`、`t13-rescore-*.out`、`c13-ladder-*.out`、`t21-pilot-01.out`、`t21-pr-body.md` 等文件名。**没有读取、列出或打开其中任何一个的内容**（没有对任何子目录执行 ls，没有 cat / Read / grep / chDB 查询）。看到这份清单后立即停止使用数据目录，此后本会话未再访问 `$SEMDEBT_DATA_DIR` 的任何路径；第 1–2 步的全部依据只有 `semantic/source.yaml`、`semantic/conventions.md`、`semantic/profiling/out/`、`semantic/summary/requirements.md`、`docs/design-v5-public.md`、`render/context.py` 和本卡、裁决文件。已报告用户与协调会话（sem-debt）；协调会话要求在修复合并、设置重新生成之前不再访问数据目录，因此 A33（科目树）所需的数据查询推迟到修复之后。
  - **新设置下复测（2026-10-23）**：#160 合并后用新盲模板重启，复测记在 `decisions/isolation-check.md` 第四节。A1、A11 通过；A2–A10、A12 的 shell 探测被 Claude Code 自动模式分类器拦下未执行，待用户补测。B4 的失败都是测试读题库 / `scorer-corpus` 被拒（隔离生效）；其中一条失败的报错行把 `tests/test_harness.py` 里写死的一道题原文打到了输出，本会话看到后未再打开该文件，第 3 步不以它为依据。协调会话（2026-10-24）告知：这串题面来自 `harness/syntax_ladder/clickhouse_sql_t4.md`（C13 第 4 级的调优题），本会话不打开该文件和 `harness/syntax_ladder/` 目录；修复在 `coord-blind-ladder`。协调会话裁决：第 3 步只查了 parquet、在放行范围内，A33 / A40 / A41 / D32 / H07 不用重做。
  - **`!` 命令带入目录名（2026-10-24，新会话 new-T22）**：协调会话为测 A12 让用户在本会话里运行 `! ls "$SEMDEBT_DATA_DIR"; ls "$SEMDEBT_DATA_DIR"/eval-ro-eval-v1.2`。`!` 不经沙箱，输出进入了本会话上下文，内容是：数据目录顶层的文件 / 目录名（与上一条相比新增 `chdb-c13`、`chdb-t16`、`clickhouse-t16`、`cubestore-t16`、`t17-windows`、`t19c-confidence-01.out`、`t19c-pr-body.md`、`vendor`），以及 `eval-ro-eval-v1.2` 的顶层名字（`AGENTS.md`、`audit`、`decisions`、`docs`、`pyproject.toml`、`questions`、`README.md`、`refs`、`reports`、`scripts`、`tasks`、`uv.lock`、`vendor`）。只有名字，没有任何文件内容，没有题面、参考答案或模型输出。第 1–3 步的产出在此之前已提交，本会话没有据此改动任何内容。教训：`!` 测不了隔离，盲模式会话里不要用它跑读数据的命令。随后 A12 改用本会话自己的工具实测：Read 和 Bash `cat` 读 `$SEMDEBT_DATA_DIR/t19c-pr-body.md`，两次都被拒（前者被 `blockReadsOutsideWorkingDirectories` 拦下，后者报 `Operation not permitted`），A12 通过。测试（`--ignore=tests/test_scorer_v2_shared.py`，不打印失败详情）：共 837 个，4 个失败、17 个跳过；4 个失败都是读 `semantic-debt-eval` 或 `syntax_ladder` 时报 `PermissionError`（隔离生效），与 T22 的产出无关。
  - **审定后改的两处事实**：D32 利润改为由叶子科目算出（战略计划表没有利润类科目的行）；E04 国家数 34（清单原写 35）。见 `semantic/l1plus-concepts.md` 开头。
- 工时：
