# 英文锚点的参考与 `rules`（T11 遗留项，2026-10-16）

依据：`decisions/2026-10-16-q79-release-and-anchor-refs.md` 第二至四节。本文件只含题号与列类型，不含题目、SQL 或参考值。

## 怎么接的

- **原始参考**：外部基准 `vendor/cube/text_to_sql_benchmark.json` 的 `expected_sql` 原样，在本地 chDB 上完整执行一次（`max_threads = 1`、不限时，同题库参考的运行条件），结果存在 `$SEMDEBT_DATA_DIR/anchor-refs/paper-2026-04-22/`（不入库）。命令：`uv run python -m harness.anchor_refs`；`--check` 重跑逐字节比对（2026-10-16：99/99 一致）。
- **对应关系**：按英文原文匹配——外部第 n 题对应题库里 `text_en` 与它逐字相同的那一道（要求恰好一道），不按序号推算。锚点题号 `EN<n>` 用外部原题号；q33 按外部公布口径排除，共 99 道。测试：`tests/test_harness.py::test_anchor_mapping_follows_the_english_text_not_the_numbering`。
- **`rules`**：原始参考的列数与逐列返回类型，和当前同号题某一份参考的有效 `rules`（逐参考覆盖后）的 `value_types` 相同时——**比较前先剥掉 `Nullable(...)`**（裁决第三节第 1 条）——沿用那份 `rules`（原样，不改写），并要求评分器接受原始参考自比为 `correct`；否则记 `pending: anchor_structure_differs`。
- **原始参考为 0 行**（裁决第三节第 2 条）：只有外部公开的参考工件（`vendor/cube/published-runs/paper-2026-04-22/reference/qNN.json`）同样是 0 行且无报错时，才按空结果评分，`rules` 用同号题的题级 `rules` 原样（空结果集没有列可比；评分器对空参考只判候选是否也为空）；工件非空或不可用则记待定、不评。这条判断写在 `harness/questions.py::anchor_rules` 里，有测试。
- **题库补写的 `rules`**（题库 PR #12）：列结构与当前参考不同的原始参考，`rules` 由 Codex 写在题库 `audit/anchor-original-rules-review.md` 的 `## ENnn` 节里（附原始 SQL 与结果文件的 SHA256）。harness 按外部题号取整份 `rules`，先核对两个哈希都与本地 `anchor-refs/.../MANIFEST.json` 一致，再要求评分器自比为 `correct`；哈希不一致记 `pending: anchor_rules_hash_mismatch`。这些 `rules` 不进中文修订参考。
- **Top-N 补全边界**（裁决第四节第 3 条，以及评分器「Top-N 参考须含完整边界并列组」的既有契约）：原始 SQL 用 `LIMIT n` 或 `row_number()` 截断，可能截掉边界上的并列。`harness/anchor_refs.py` 对每道原始 SQL 另跑一遍「只把截断改为含并列」的版本：`LIMIT n WITH TIES`、`row_number()` 改为 `rank()`，其余不动，所以只在有并列时结果不同。行数多出来时存为 `qNN.boundary.json`，MANIFEST 记它的 SQL 哈希、行数和结果哈希。`rules` 是 Top-N（有 `top_n` 或 `selection`）的锚点改用补全后的参考。自比的候选取补全参考的前 N 行（分组 Top-N 用原始结果），因为整组并列全交按评分器契约是错的。`--check` 同样覆盖这些文件。
- **对照列**：同一次作答另用当前修订后的参考与 `rules` 评一遍，记在日志 `final.revised`；`summarize` 给出 `outcomes_on_revised_refs`。

## 结果（题库 dd5853d，2026-10-16）

题库从 `origin/main` 检出到数据目录下的只读 worktree（`$SEMDEBT_DATA_DIR/eval-ro-dd5853d`），从那里读取，没有动题库工作区。`anchor_refs --check` 重跑：104/104 逐字节一致（99 份原始参考加 5 份补全边界参考）。

99 道锚点：**87 道可评**，**12 道 judge**（与中文同号题的 `scoring` 一致，返回行集记待定），**0 道待定**。

- **题库补写的 8 份 `rules`**：EN13、EN14、EN20、EN21、EN34、EN74、EN83、EN87。两个哈希全部一致，自比全部为 `correct`。其中 EN21、EN34 是因为 T05 保留孤儿产品键后，当前参考的列结构变了。
- **剥掉 `Nullable` 后与当前参考结构相同**：沿用同号题的 `rules`，见下文「历史」。
- **空参考**：EN39、EN49，外部公开工件同样是 0 行，按空结果评分（EN39 是 judge）。

### Top-N 边界核对

| 锚点 | 截断方式 | 原始行数 | 补全后行数 | 说明 |
|---|---|---:|---:|---|
| EN07 | `LIMIT 10` | 10 | 14 | 多出 4 个并列成员 |
| EN27 | `LIMIT 10` | 10 | 444 | 多出 434 个并列成员（前 9 名之后全部并列） |
| EN79 | `LIMIT 10` | 10 | 306 | **全部 306 家店并列**（见下） |
| EN85 | 前 5、后 5 各 `LIMIT 5` | 10 | 97 | 最高档 42 家并列，最低档 55 家并列 |
| EN88 | `LIMIT 20` | 20 | 24 | 多出 4 个并列成员 |
| EN22、EN71、EN74 | `row_number()` | — | 不变 | 组内边界无并列 |
| EN25、EN46、EN73、EN87 | `LIMIT n` | — | 不变 | 边界无并列 |
| EN98 | 无截断 | — | — | — |

**这是对「原样执行」的唯一偏离**：EN07、EN27、EN79、EN85、EN88 的原始参考按「截断改为含并列」补全，口径不变；理由是与评分器的 Top-N 并列规则一致（Top-N 参考须含完整的边界并列组，否则任何选了另一组并列成员的正确答案都会判错）。其余 94 道原始参考仍是原样执行的结果。

EN74、EN87（Codex 交接时要求核对）的原始截断没有丢并列。在补全后的参考上，原始 SQL 自己那 N 行判 `correct`；另选一组并列成员同样判 `correct`；交 N+1 行判 `top_n_row_count` 错；把整组并列全交上来判 `boundary_tie_full_group` 错。

### 低区分度：EN79、EN27、EN85（C 条：排序退化）

依据：`decisions/2026-10-16-low-discrimination-criteria.md` C 条，「Top-N 题的边界并列组不少于 3N」。证据是并列组大小，按补全后的参考，用评分器的并列判定（`_boundary_start`）计算。第 N 名的取值属于参考值，不写进本仓库，可由 `anchor-refs/.../qNN.boundary.json` 复核。

| 锚点 | N | 边界并列组 | 3N | 命中 C 条 |
|---|---:|---:|---:|---|
| EN79 | 10 | 306（全部门店） | 30 | 是 |
| EN27 | 10 | 435（前 9 名之后全部） | 30 | 是 |
| EN85 | 前 5 / 后 5 | 42 / 55（两档各自全部并列，各只有 1 个取值） | 15 / 15 | 是 |
| EN07 | 10 | 14 | 30 | 否 |
| EN88 | 20 | 5 | 60 | 否 |

#### EN79

外部原始 SQL 拿实际销售与 `ScenarioKey = 1`（实际）的配额比，所有门店的达成率都是 100%，306 家店全部并列在第 10 名的边界上（裁决第四节）。按外部口径复现：评分器走 Top-N 并列规则，**306 家里任选 10 家都判对**，不只认原始结果里的那 10 家（测试：`tests/test_harness.py::test_anchor_rules_from_the_bank_and_boundary_on_the_real_bank`，随机抽 10 家判对，交 11 行判错）。**EN79 标为「低区分度」**：它几乎不考排序，只考能否写出可执行的、列结构对的查询，T19 单列报告。对照列（当前修订参考，`ScenarioKey = 2`）的边界是 42 家，同样低区分度（T06 已把 Q79 标为「低区分度」）。

### 评分器的另一个问题（已记 `decisions/open-questions.md` T11-4，待裁决）

Top-N 的严格前缀是按位置逐行比的，前缀内部的并列行必须与参考同序。并列行之间没有确定的顺序，于是写对了的查询也可能判 `wrong / values`。实测受影响的是中文 Q27、Q87、Q88，锚点 EN27、EN88。EN88 的原始参考与补全后的参考，组内姓名顺序本身就不一样，所以 EN88 的自比改用补全参考的前 20 行。这是评分器口径，归 Codex，T11 不改。

## 历史

### 题库 491ef16，裁决第三节落实后

99 道锚点：**81 道可评**；**12 道 judge**（与中文同号题的 `scoring` 一致，返回行集记待定）；**6 道列结构不同**记待定（EN13、EN14、EN20、EN74、EN83、EN87）。列结构不同的共 7 道，另一道 EN97 本来就是 judge。

第三节带来的变化（相对初次接线的 78 / 12 / 9）：

- **剥掉 `Nullable` 后结构相同**：EN84、EN100 改为沿用同号题 `rules`、可评；EN44 同理改为结构相同（它是 judge，仍待定）。
- **空参考**：EN39、EN49 的外部公开参考工件**也是 0 行**（`row_count = 0`、`error = null`，工件里的 SQL 与 `expected_sql` 逐字相同），因此按空结果评分：EN49 可评；EN39 有了 `rules`，但它是 judge，仍待定。修订参考的对照列照常给出这两题与我们更正后参考的差异，T19 披露。

#### 当时待 Codex 补 `rules` 的 6 道（已由题库 PR #12 补齐）

| 锚点 | 当前同号题 | 原始参考 | 当前参考的有效 `value_types` |
|---|---|---|---|
| EN13 | Q13 | 4 列 String, Float64, Float64, UInt64；306 行 | 5 列 Int32, String, Float64, Float64, UInt64 |
| EN14 | Q14 | 3 列 String, String, Float64；18,869 行 | 4 列 Int32, String, String, Float64 |
| EN20 | Q20 | 3 列 String, Int32, Int32；3,969 行 | 6 列 Int32, String, Int32, String, Int32, Int32；4 列 Int32, String, Int64, Int64 |
| EN74 | Q74 | 4 列 String, String, Float64, Nullable(Float64)；9 行 | 5 列 String, Nullable(String), Float64, Nullable(Float64), Int32 |
| EN83 | Q83 | 5 列 Nullable(UInt64), UInt64, Nullable(Float64), UInt64, Nullable(Float64)；1 行 | 3 列 UInt64, UInt64, UInt64 |
| EN87 | Q87 | 4 列 String, Int64, Float64, Float64；20 行 | 5 列 Nullable(String), Int64, Float64, Float64, Int32 |

另有 EN97（judge）列结构也不同：原始 4 列 String, Float64, Float64, Nullable(Float64)；当前两份均为 5 列。它是 judge，不影响确定性评分。

### T05正式参考后的规则交接（2026-10-16，Codex 写）

上述81／12／6属于题库491ef16的历史状态。本轮保留事实对象键后另有EN21、EN34出现列结构差异，因此现行待接的确定性原始参考规则为8份：EN13、14、20、21、34、74、83、87。Codex已在私有题库交付实际原始meta、固定推断量纲、SQL／payload哈希及完整逐参考rules字典，全部原始参考规则自比通过；只核验T11已有payload，不宣称重跑99份SQL。

接线仍由Claude Code在T11完成，当前主仓库不读取该交接表；不能把它加入中文修订参考。接入后预计87道确定性、12道judge；以T11接入后的自比及完整边界核对为准，不在本文提前宣布可评。EN97仍为judge；不以规则交接改变评分路由。
