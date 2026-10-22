# C13 写法说明的教学阶梯（ClickHouse SQL，档位 L1）

- 状态：已运行（`20261019-C13-ladder-02`，2026-10-19 23:25–23:49 错峰，7.17 元）；结果见 `reports/results/C13-ladder.md`
- 负责：Claude Code
- 模式：普通
- 依据：`decisions/2026-10-19-phase1-replan.md` 第三节；教学深度的定义见 `decisions/2026-10-19-self-built-p-and-cube-notes.md` 第五节
- 依赖：`harness-v1.1`、`eval-v1.2`、`semantic-v1.3`；运行前由协调会话打 tag 冻结本卡的三份写法说明
- 预算：合计约 10 元（Flash，错峰；见下文 dry-run）

## 目标

只换写法说明、不动系统提示与语义上下文，测「教语言」能把 SQL-L1 的准确率推到多高。与 T14 调优（补语义层内容）分开报告，分别对应「治理 vs agent」的两边。

## 单元

系统提示（`harness/prompt.py`，与 `harness-v1` 逐字节相同）、语义上下文（`build/contexts/SQL-L1.yaml`）、执行器（`retail` 库）都与 SQL-L1 相同；只有写法说明不同。各级说明逐级累加：每一级都以上一级的全文开头。

| 单元 | 写法说明 | 深度 | 题目 |
|---|---|---|---|
| SQL-L1（T13 已跑） | `render/syntax/clickhouse_sql.md` | 1 | 已有 |
| SQL-L1-T2 | `harness/syntax_ladder/clickhouse_sql_t2.md` | 2：1 级 + 使用条件与禁忌 | 全部 109 道确定性评分题（judge 除外）；报告另列留出题 55 道的子集 |
| SQL-L1-T3 | `harness/syntax_ladder/clickhouse_sql_t3.md` | 3：2 级 + 通用样例（占位名称，不对应任何题） | 同上 |
| SQL-L1-T4 | `harness/syntax_ladder/clickhouse_sql_t4.md` | 4：3 级 + 同类题样例（只取调优题） | **只评留出题** 55 道（judge 除外） |

- 三个单元在 `harness/cells.py` 的 `LADDER_CELLS` 里，不在 `CELLS` 里，所以 `run_direct --cell all` 不会带上它们，必须点名。
- 写法说明放在 `harness/syntax_ladder/`，不放 `render/syntax/`：`render/` 属于语义层 tag（`semantic-v1.3`），往里加文件会让运行前的语义层校验拒绝启动，而本期不出 `semantic-v1.4`。阶梯说明随 harness 的 tag 冻结。
- judge 题：三个单元都 `skip_judge=True`（重新规划第二节）；`run_direct` 另有 `--skip-judge`，给其他单元用。
- 留出题：SQL-L1-T4 的 `split="heldout"`，只回答留出题；`run_direct.questions_for` 按单元筛题，dry-run 也按单元计数。

## 各级说明的来源

- **2 级的禁忌**只来自两处：
  - 通用实测：在临时的内存 chDB 上逐条验证，不碰共享数据目录；
  - **调优题**上的执行失败：T13 全部 6 个 SQL 单元、`eval-v1.2` 的 `split=tuning` 题，共 270 次报错。其中 210 次是中文别名没加引号的语法错，另有引用 CTE 没选出的列、`UNION` 没写 `ALL`/`DISTINCT`、别名与列同名导致聚合套聚合、`OrNull` 函数用在数值上、统计函数参数类型不一致、`JOIN … ON` 里的相关子查询、`ASOF JOIN` 缺等值条件、递归层数上限、没有 `lowerUTF8`。
  - **没有读留出题的任何作答。**
- **3 级的样例**用占位表名、列名（`db.fact_table`、`dim_key`、`amount` 等），不对应任何题；6 条都在临时内存表上执行通过。
- **4 级的同类题样例**只取调优题：确定性评分、只有一份参考、参考不经后处理。取法是通用规则：每个 Q 级按参考 SQL 长度排序（同长按题号），取正中间的两道。结果是 Q60、Q12（Q1），Q78、Q82（Q2），Q50、Q49（Q3）。给出题面和参考 SQL。选法与留出题上的对错无关；`test_ladder_level4_examples_are_tuning_questions_only` 按同一规则复核。

## dry-run（不调用模型）

```sh
uv run python -m harness.run_direct --cell SQL-L1-T2 --cell SQL-L1-T3 --cell SQL-L1-T4 \
    --eval-tag eval-v1.2 --semantic-tag semantic-v1.3 --dry-run \
    --est-output-tokens 1830 --est-hit-ratio 0.987 --est-fix-rate 0.34
```

输出 token、缓存命中率和每次作答的调用数，取 T13 的 SQL-L1 实测：每次调用输出 1,830 token，缓存命中 98.7%，每次作答 1.34 次调用。

| 单元 | 题 | 作答（×3） | 调用 | 每次输入 token | 元（错峰） |
|---|---:|---:|---:|---:|---:|
| SQL-L1-T2 | 109 | 327 | 438 | 41,577 | 3.80 |
| SQL-L1-T3 | 109 | 327 | 438 | 42,095 | 3.81 |
| SQL-L1-T4 | 55 | 165 | 221 | 43,066 | 1.93 |
| 合计 | | 819 | 1,097 | | **9.54**（高峰价 19.08） |

用默认估计（输出 3,000 token、命中 95%、修正率 10%）是 13.44 元。

## 运行（用户批准预算之后）

- 错峰（工作日 18:00 以后，或午休 12:00–14:00）；三个单元依次跑，每个单元先预热、再并发，与 T13 相同；每题 3 次。
- 每个单元的系统消息哈希写进日志（`system_sha256`），运行前与冻结时的哈希核对。
- 报告：每级的主表正确率；T2、T3 另列留出题子集，好与 T4 同口径比较；首轮执行报错率，其中中文别名一类单列，因为它是 2 级说明直接针对的问题。

## 记录

- 产出：
  - 三份写法说明；
  - `harness/cells.py` 的 `LADDER_CELLS` 与 `syntax_path`；
  - `harness/run_direct.py` 的 `questions_for`、`--skip-judge`，dry-run 按单元计数；
  - `reports/validation/syntax-syllabus.md` 的阶梯一节；
  - 测试 `test_ladder_*`、`test_questions_for_*`、`test_dry_run_counts_each_cells_own_questions`。
- 偏离与理由：说明放在 `harness/syntax_ladder/`，原因见「单元」一节。

## 运行记录（2026-10-19）

- 依赖按协调会话的指示改为 `semantic-v1.4`（234ad68）、`harness-ladder-v1`、`harness-v1.1`、`eval-v1.2`。第 1 级沿用 T13 已重评的 SQL-L1：它的系统消息 sha256 与 semantic-v1.4 下的相同（8df43ae0…）。
- 预算：协调会话转达用户批准，上限 15 元；实花 7.17 元，844 次调用（每次作答 1.03 次）。
- chDB：T13 同时在默认目录上跑 L1.5S，所以本卡用从 Parquet 另建的 `chdb-c13`，由 `scripts/c13_run_on_chdb_copy.py` 指定，harness 不改。
- 偏离：第一次启动（`20261019-C13-ladder-01`）包装脚本缺 `__main__` 保护，评分子进程又启动了一次运行，在 `chdb-c13` 上撞锁。约 1 分钟后停下，6 次调用约 0.014 元，日志原样保留、不计入结果；修好后用新 run-id 重跑。详见 `runs/INDEX.md`。
- 结果：
  - 2 级把首轮执行报错从 32% 降到 3%，语法错几乎全部消失；
  - 正确率相对第 1 级：+4.0 个百分点（全部题），95% 区间 [−0.9, +9.2]；
  - 3 级、4 级没有再提高；
  - 各级差距都在抽样误差之内。
