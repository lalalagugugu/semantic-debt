# 英文锚点的参考与 `rules`（T11 遗留项，2026-10-16）

依据：`decisions/2026-10-16-q79-release-and-anchor-refs.md` 第二节。本文件只含题号与列类型，不含题目、SQL 或参考值。

## 怎么接的

- **原始参考**：外部基准 `vendor/cube/text_to_sql_benchmark.json` 的 `expected_sql` 原样，在本地 chDB 上完整执行一次（`max_threads = 1`、不限时，同题库参考的运行条件），结果存在 `$SEMDEBT_DATA_DIR/anchor-refs/paper-2026-04-22/`（不入库）。命令：`uv run python -m harness.anchor_refs`；`--check` 重跑逐字节比对（2026-10-16：99/99 一致）。
- **对应关系**：按英文原文匹配——外部第 n 题对应题库里 `text_en` 与它逐字相同的那一道（要求恰好一道），不按序号推算。锚点题号 `EN<n>` 用外部原题号；q33 按外部公布口径排除，共 99 道。测试：`tests/test_harness.py::test_anchor_mapping_follows_the_english_text_not_the_numbering`。
- **`rules`**：原始参考的列数与逐列返回类型，和当前同号题某一份参考的有效 `rules`（逐参考覆盖后）的 `value_types` 相同时——**比较前先剥掉 `Nullable(...)`**（裁决第三节第 1 条）——沿用那份 `rules`（原样，不改写），并要求评分器接受原始参考自比为 `correct`；否则记 `pending: anchor_structure_differs`。
- **原始参考为 0 行**（裁决第三节第 2 条）：只有外部公开的参考工件（`vendor/cube/published-runs/paper-2026-04-22/reference/qNN.json`）同样是 0 行且无报错时，才按空结果评分，`rules` 用同号题的题级 `rules` 原样（空结果集没有列可比；评分器对空参考只判候选是否也为空）；工件非空或不可用则记待定、不评。这条判断写在 `harness/questions.py::anchor_rules` 里，有测试。
- **对照列**：同一次作答另用当前修订后的参考与 `rules` 评一遍，记在日志 `final.revised`；`summarize` 给出 `outcomes_on_revised_refs`。

## 结果（题库 491ef16，裁决第三节落实后）

99 道锚点：**81 道可评**；**12 道 judge**（与中文同号题的 `scoring` 一致，返回行集记待定）；**6 道列结构不同**记待定（EN13、EN14、EN20、EN74、EN83、EN87）。列结构不同的共 7 道，另一道 EN97 本来就是 judge。

第三节带来的变化（相对初次接线的 78 / 12 / 9）：

- **剥掉 `Nullable` 后结构相同**：EN84、EN100 改为沿用同号题 `rules`、可评；EN44 同理改为结构相同（它是 judge，仍待定）。
- **空参考**：EN39、EN49 的外部公开参考工件**也是 0 行**（`row_count = 0`、`error = null`，工件里的 SQL 与 `expected_sql` 逐字相同），因此按空结果评分：EN49 可评；EN39 有了 `rules`，但它是 judge，仍待定。修订参考的对照列照常给出这两题与我们更正后参考的差异，T19 披露。

### 仍待 Codex 补 `rules` 的 6 道

| 锚点 | 当前同号题 | 原始参考 | 当前参考的有效 `value_types` |
|---|---|---|---|
| EN13 | Q13 | 4 列 String, Float64, Float64, UInt64；306 行 | 5 列 Int32, String, Float64, Float64, UInt64 |
| EN14 | Q14 | 3 列 String, String, Float64；18,869 行 | 4 列 Int32, String, String, Float64 |
| EN20 | Q20 | 3 列 String, Int32, Int32；3,969 行 | 6 列 Int32, String, Int32, String, Int32, Int32；4 列 Int32, String, Int64, Int64 |
| EN74 | Q74 | 4 列 String, String, Float64, Nullable(Float64)；9 行 | 5 列 String, Nullable(String), Float64, Nullable(Float64), Int32 |
| EN83 | Q83 | 5 列 Nullable(UInt64), UInt64, Nullable(Float64), UInt64, Nullable(Float64)；1 行 | 3 列 UInt64, UInt64, UInt64 |
| EN87 | Q87 | 4 列 String, Int64, Float64, Float64；20 行 | 5 列 Nullable(String), Int64, Float64, Float64, Int32 |

另有 EN97（judge）列结构也不同：原始 4 列 String, Float64, Float64, Nullable(Float64)；当前两份均为 5 列。它是 judge，不影响确定性评分。
