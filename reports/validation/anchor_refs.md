# 英文锚点的参考与 `rules`（T11 遗留项，2026-10-16）

依据：`decisions/2026-10-16-q79-release-and-anchor-refs.md` 第二节。本文件只含题号与列类型，不含题目、SQL 或参考值。

## 怎么接的

- **原始参考**：外部基准 `vendor/cube/text_to_sql_benchmark.json` 的 `expected_sql` 原样，在本地 chDB 上完整执行一次（`max_threads = 1`、不限时，同题库参考的运行条件），结果存在 `$SEMDEBT_DATA_DIR/anchor-refs/paper-2026-04-22/`（不入库）。命令：`uv run python -m harness.anchor_refs`；`--check` 重跑逐字节比对（2026-10-16：99/99 一致）。
- **对应关系**：按英文原文匹配——外部第 n 题对应题库里 `text_en` 与它逐字相同的那一道（要求恰好一道），不按序号推算。锚点题号 `EN<n>` 用外部原题号；q33 按外部公布口径排除，共 99 道。测试：`tests/test_harness.py::test_anchor_mapping_follows_the_english_text_not_the_numbering`。
- **`rules`**：原始参考的列数与逐列返回类型，和当前同号题某一份参考的有效 `rules`（逐参考覆盖后）的 `value_types` **完全相同**时，沿用那份 `rules`（原样，不改写），并要求评分器接受原始参考自比为 `correct`；否则记 `pending: anchor_structure_differs`。
- **对照列**：同一次作答另用当前修订后的参考与 `rules` 评一遍，记在日志 `final.revised`；`summarize` 给出 `outcomes_on_revised_refs`。

## 结果（题库 491ef16）

99 道锚点：**78 道可评**；**12 道 judge**（与中文同号题的 `scoring` 一致，返回行集记待定）；**9 道列结构不同**记待定。列结构不同的共 12 道，其中 3 道（EN39、EN44、EN97）本来就是 judge。

| 锚点 | 当前同号题 | 评分方式 | 原始参考 | 当前参考的有效 `value_types` |
|---|---|---|---|---|
| EN13 | Q13 | deterministic | 4 列 String, Float64, Float64, UInt64；306 行 | 5 列 Int32, String, Float64, Float64, UInt64 |
| EN14 | Q14 | deterministic | 3 列 String, String, Float64；18,869 行 | 4 列 Int32, String, String, Float64 |
| EN20 | Q20 | deterministic | 3 列 String, Int32, Int32；3,969 行 | 6 列 Int32, String, Int32, String, Int32, Int32；4 列 Int32, String, Int64, Int64 |
| EN39 | Q39 | judge | 3 列 String, Nullable(Float64), Nullable(Float64)；**0 行** | 6 列 Nullable(Int32), String, Nullable(Date), Nullable(Int64), Nullable(Float64), Nullable(Float64) |
| EN44 | Q44 | judge | 3 列 UInt16, Float64, Float64；3 行 | 3 列 UInt16, Float64, Nullable(Float64)；2 列 Date, Float64 |
| EN49 | Q49 | deterministic | 2 列 String, Float64；**0 行** | 3 列 Int32, String, Float64（两份） |
| EN74 | Q74 | deterministic | 4 列 String, String, Float64, Nullable(Float64)；9 行 | 5 列 String, Nullable(String), Float64, Nullable(Float64), Int32 |
| EN83 | Q83 | deterministic | 5 列 Nullable(UInt64), UInt64, Nullable(Float64), UInt64, Nullable(Float64)；1 行 | 3 列 UInt64, UInt64, UInt64 |
| EN84 | Q84 | deterministic | 4 列 String, UInt64, Float64, **Nullable(Float64)**；3 行 | 4 列 String, UInt64, Float64, **Float64** |
| EN87 | Q87 | deterministic | 4 列 String, Int64, Float64, Float64；20 行 | 5 列 Nullable(String), Int64, Float64, Float64, Int32 |
| EN97 | Q97 | judge | 4 列 String, Float64, Float64, Nullable(Float64)；15 行 | 5 列 Nullable(String), Float64, Float64, Nullable(Float64), Int32；5 列 Int32, Nullable(String), Float64, Float64, Float64 |
| EN100 | Q100 | deterministic | 4 列 String, UInt64, **Nullable(Float64), Nullable(Float64)**；30 行 | 4 列 String, UInt64, **Float64, Float64** |

**交 Codex 补 `rules`（裁决第 4 条）**。两点请一并定：

1. **EN84、EN100 只差 `Nullable(...)` 包装**，列数与基础类型相同。按「完全相同」的口径它们记为待定；「列结构相同」是否忽略 `Nullable`，不由 harness 自定。
2. **EN39、EN49 的原始参考是 0 行**（外部原始 SQL 在本数据上返回空结果；Q49 的原因见题库 `audit/T03-report.md`）。补 `rules` 之外，空参考在锚点里怎么评，需要明确。
