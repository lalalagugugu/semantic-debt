# T14 调优（SQL-L1 调优；DAX-L2 调优用同一流程）

- 状态：进行中（2026-10-23：SQL-L1-tuned 第 1 轮调优包已导出，等 B 角）
- 负责：Claude Code，两个**互不相通**的会话
  - A 角：普通模式（`scripts/start-card.sh T14`），可读题库，负责导出调优包、合并补充、跑结果。
  - B 角：调优包模式（`scripts/start-card.sh T14-B <调优包目录>`，例如 `$SEMDEBT_CARDS_DIR/T14/build/tuning-packet/sql-l1`），工作目录里只有调优包和 `semantic/` 的副本，不是 git clone，看不到题库、`runs/` 和数据目录。
- 依赖：T13（SQL-L1 第一次运行的结果）；DAX 部分依赖 T18 的 DAX-L2 第一次运行结果
- 预算：Flash 20 元 / Pro 50 元（只含跑调优后单元的费用；2026-10-23 由 15 元上调，见 `decisions/2026-10-23-tuning-instructions.md`）

## 目标

模拟上线后的运营：用户点踩、分析师核实后，把 bad case 反馈进语义层。检验这样调出来的语义层，对没见过的问题（留出题）是否也更好。

## 流程

1. **A 导出调优包** `build/tuning-packet/<cell>/`：只含**调优题中第一次运行答错的那些**，每题包括问句、模型的查询与假设、执行结果摘要、正确的参考结果（相当于分析师核实后的答案）。不含答对的题，不含任何留出题，不含其他单元的结果。
2. **B 写补充**：可以补充或改写约定、字段描述、同义词，可以写不超过 15 条「问题 → 查询」示例。补充写进工作目录里的 `semantic/tuning/<cell>.yaml`，不得改动其他文件。
3. **A 合并与跑**：把 B 的 `semantic/tuning/<cell>.yaml` 复制回仓库，由渲染器叠加到原档位上；跑调优后的单元（SQL-L1 调优；DAX-L2 调优在 T18 跑），全部题目每题 3 次；分析时只看留出题。
4. 最多迭代两轮：第二轮的调优包由 A 用第一轮补充后的结果重新导出，仍然只含调优题；B 用一个新会话。

## 两个单元（2026-10-23 裁决，`decisions/2026-10-23-tuning-instructions.md`）

- **SQL-L1-tuned（只调语义层）**：上面的流程。
- **SQL-L1-tuned-instr（语义层 + 指令）**：在 SQL-L1-tuned 定稿的语义层补充之上，由**新的 B 角会话**读同一份调优包，只写指令补丁 `semantic/tuning/<cell>.instructions.yaml`：可改写或追加作答要求条目和 ClickHouse 写法说明条目；不得改语义层补充，不得写对应具体题的条文；示例与上一单元合计不超过 15 条。A 角合并、渲染，打 `harness-tuned-v1`（只覆盖调优单元），日志记系统消息 sha256。
- 两单元都跳过 judge 题，各最多两轮；分析只看留出题；`reports/results/tuning.md` 另列两单元之差（指令调优的增益），并与 C13 的 2 级说明对照。

## 交付物

- 调优包清单、补充文件、两轮的变更说明。
- `reports/results/tuning.md`：调优前后在调优题、留出题上的准确率和四种结果占比，分开列。
- 工时（B 写补充花了多少小时）。

## 验收

- 能证明 B 的工作目录里没有留出题：调优包清单与题集划分逐一核对。
- 补充文件里的示例只来自调优包。

## 不能做

- B 不得读取完整题库、留出题、其他单元的结果；不得用子 agent 代替 B。
- 补充内容不得改动原始 `source.yaml`（已冻结），只能叠加。

## 记录（完成后填写）

- 产出：
  - SQL-L1-tuned 第 1 轮调优包：`uv run python -m harness.tuning_packet --packet sql-l1 --eval-tag eval-v1.2`（`SEMDEBT_EVAL_DIR` 指向只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`），导出到 `build/tuning-packet/sql-l1/`（不入库）：23 题、51 次答错的作答。清单与逐题核对见 `reports/tuning/packet-sql-l1-manifest.json`、`reports/tuning/packet-sql-l1-check.md`（只含题号）：没有留出题、没有 judge 题、没有答对的作答，也没有漏掉的错答。
- 偏离与理由（口径说明，2026-10-23 协调会话认可）：
  - **「答错的题」按单次作答算**：调优题（非 judge）3 次里至少有 1 次不是 correct 就进包，只放不是 correct 的那几次，对应「用户对每个错答点踩」；同一题答对的那几次不进包。
  - **不放参考 SQL**：只放核实后的正确结果（口径加前 20 行），对应卡片「正确的参考结果（相当于分析师核实后的答案）」。也不放模型的思考内容。
  - 合并时，B 写的每条示例查询都要在 chDB 上执行，结果与包内参考核对；执行不通或结果不符的退回给 B，A 不自行修改。
  - **第二个单元不另开 B 角**（用户 2026-10-24 裁决，偏离 `decisions/2026-10-23-tuning-instructions.md` 第 2 条）：SQL-L1-tuned-instr 的指令补丁 `semantic/tuning/SQL-L1.instructions.yaml` 直接用 T14-B 第 1 轮写的 8 条输出规矩和 6 条 ClickHouse 写法坑，由 B 只做搬家和格式整理、不改内容，题号不得进文件。理由：这 14 条读的是同一份调优包，写的时候没看过任何单元的结果。SQL-L1.yaml 里不放这 14 条。
  - 示例执行用的 chDB 是从 Parquet 另建的 `$SEMDEBT_DATA_DIR/chdb-t14`（`data/build_chdb_copy.py`）。原因：默认的 `chdb` 当时可能有别的会话在用（硬规则 9）。
  - 第 1 轮核对（2026-10-24）：14 条示例 11 条判对；E02、E07、E14 的结果与参考逐值相同，却判错，原因是调优包把 Top-N 题的参考结果连同全部并列一起展示，而评分要求恰好 N 行。这是 A 导出调优包时的写法错误，已记为待裁决问题 T14-1（`decisions/open-questions.md`）。退回清单：`build/tuning-packet/sql-l1-return-01.md`。
  - **T14-1 裁决（用户 2026-10-24 选 (a)，`decisions/2026-10-24-t14-packet-ties.md`）**：调优包改正为评分器 v2 的实际规则（前 N 名恰好 N 行、分组每组恰好 n 个，并列任取），每种核实结果下按各自的评分规则写一行，涉及 Q27、Q74、Q98、Q117、Q122；重新导出，划分核对仍 PASS。这条规则作为输入进指令补丁，B 据此重写 O7、改 E02/E07/E14 和 S19 的取前 N。验证：用正式评分器，三道并列题的核实结果原样判错、截成恰好 N 行判对。
  - S 条目里夹着的输出句：算什么、怎么算留语义层；取哪些列、什么格式进指令补丁（协调会话 2026-10-24 确认），由 B 拆。退回清单 01 已补全，B 一轮改完后 A 复查、再 dry-run。
  - **第 2 轮复查（2026-10-24，B 按退回清单 01 一轮改完，交回 `semantic/tuning/SQL-L1.yaml`、`SQL-L1.instructions.yaml`、`SQL-L1.notes.md`）**：
    - 题号：渲染后的 SQL-L1-tuned 上下文和指令补丁里只剩季度写法 Q1–Q4，没有题号；出处与对照表在不渲染的 notes 里。`output_rules`、`sql_pitfalls` 已移出 SQL-L1.yaml，不再引用 O 编号；指令补丁和 notes 都不进 SQL-L1-tuned 的上下文。
    - 示例：14 条在 `chdb-t14` 上执行、用正式评分器比对，**14 条全部判对**（E02 10 行、E07 918 行、E14 10 行；E13 改成 row_number() 选行，仍判对）。
    - 其他单元：带调优文件重新渲染，除 SQL-L1-tuned 外全部上下文与不带调优文件时逐字节相同。
    - B 在清单之外多做的两处：S15 的输出列也拆成 S15-out；S19 补了品类自身降幅与占比的公式（与 E13 写法相同）。已报协调会话。
    - 预算估算（harness 的 `dry_run` 估算函数，Flash 错峰价，109 题 × 3 次，跳过 judge）：SQL-L1-tuned 约 5.58 元（按默认每次输出 3000 token 估；SQL-L1 实测 3.19 元、同样估法得 5.34 元，按实测比例约 3.4 元）。SQL-L1-tuned-instr 的系统消息再多约 1,600 token，估法相同约 5.8 元。正式运行前的版本校验要求调优文件在一个冻结 tag 里，待定 tag 名。
- 工时：
