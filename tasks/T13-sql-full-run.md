# T13 SQL 直答全量

- 状态：运行完成（2026-10-18，6 单元 × 366 条齐全，24.80 元）；报告为暂定数，待 `harness-v1.1` 离线重评后定稿
- 负责：Claude Code
- 模式：普通（`scripts/start-card.sh T13`）
- 依赖：G3
- 预算：Flash 80 元 / Pro 250 元

## 目标

用选定的模型（Flash，G3）跑完 SQL 栈的 6 个中文直答单元。英文锚点 R-EN、L1c-EN 第一期不跑（`decisions/2026-10-18-g3-passed.md` 第三节），代码保留。

## 单元

| 单元 | 上下文 | 执行器 | 题目 |
|---|---|---|---|
| SQL-L0 | L0 | `chdb_retail`（库 `l0`） | 中文题集全部 |
| SQL-R | 原始 DDL 的名和类型 | `chdb_retail` | 中文题集全部 |
| SQL-L1 | L1 | `chdb_retail` | 中文题集全部 |
| SQL-L1c | 外部基准的 DDL 与语义文档原样 | `chdb_retail` | 中文题集全部 |
| SQL-L1.5W | L1 + 明细宽表 | `chdb_retail` | 中文题集全部 |
| SQL-L1.5S | 汇总层 | `chdb_ads` | 中文题集全部 |

每题 3 次。按单元顺序跑，先跑完一个单元再跑下一个，以便缓存命中。

## 来自 T11 的交接（2026-10-16，开跑前必须照做）

**一、开跑前先预热一次。** Q33 在**冷缓存**下直接查曾用掉 **285 秒**，超过 120 秒的超时；经 harness 跑两次都只要 33 秒左右。不预热就开跑，第一次碰到重查询会得到一个**假超时**——记成失败，但原因与语义层质量无关。预热跑什么、跑多久，写进本卡记录。

**二、同一单元的题要连续跑完，不要在单元之间来回切。** 费用几乎全部由缓存未命中的输入决定：冷启动约 0.046 元/次，稳态约 0.0015–0.0025 元/次，**差 20–30 倍**。切单元就等于重新冷启动一次。换单元的次数要记进日志，T19 报成本时要能解释。

**三、预算按「冷启动次数」估，不是按 token 总量估。** 按 token 总量乘单价会严重高估（缓存命中的部分便宜一个数量级）。T12 要给出这个模型，本卡照它执行。

**四、错峰时段**：工作日北京时间 9:00–12:00、14:00–18:00 **以外**都算错峰——**午休 12:00–14:00 是错峰**，可以跑。见 AGENTS.md 硬规则 6。

**五、题集必须已冻结**（G3 起为 `eval-v1.1`；语义层 `semantic-v1.2`；harness `harness-v1`）。T05 在重写补题期间不得开跑——依赖链（G2 → T12 → G3 → 本卡）本来就挡住了，这里重申是因为「重跑一次全量」的代价很高。

**六、`rules` 补齐之后可以离线重评。** T11 把完整行集存进了 `$SEMDEBT_DATA_DIR/runs-raw/`，所以题目**元数据**后补不需要重新调模型；只有**题目本身改写**才要重跑那些题。见 `decisions/2026-10-16-rules-backfill-for-vendored-questions.md`。

**七、harness 只从固定版本读题库，不读共用工作区。** 题库目录（`$SEMDEBT_EVAL_DIR`）是 Codex 原地干活的工作树，可能停在别的分支、带未提交的改动（T11 接锚点时就遇到了，靠逐字节比对 `origin/main` 才确认没读错）。正式运行必须从 `eval-v1.1` tag 的内容读题（G3 起；原文写的是 `eval-v1`）（例如 `git worktree add` 到数据目录下的只读副本，或 `git archive eval-v1` 解出），日志记 tag 与提交号；读到的不是 tag 内容就拒绝开跑。T11 的发现，2026-10-16 协调会话写入。

## 交付物

- `runs/<run-id>/` 下每个单元的 JSONL；`runs/INDEX.md` 一行记录。
- `reports/results/sql_direct.md`：每个单元的准确率、首次即对率、三次全对率、错答率、执行失败率、拒答率（四种结果占比合计 100%）；SQL-L1.5S 另按「汇总层能否回答」分开列，并报覆盖外的拒答率和错答率；实际费用。

## 验收

- 每个单元的作答记录数 = 题数 × 3，无缺失。
- 实际费用未超预算；若接近上限先停下问用户。

## 记录（完成后填写）

- 产出：
  - 运行 `runs/20261018-T13-sql-direct-01/`（6 个 JSONL，各 366 行，(题, 次) 无重复、全部 done）；`runs/INDEX.md` 一行；原始响应 `$SEMDEBT_DATA_DIR/runs-raw/20261018-T13-sql-direct-01/`
  - 版本：题库 `eval-v1.1` = `938957f`（只读 worktree `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.1`）；语义层 `semantic-v1.2` = `4cf56a8`（`build/contexts` 由 `render/render_all.py` 重新渲染，等价校验通过）；harness 各单元提交见 INDEX（SQL-L0 与 SQL-R 主体 `6516fcc` = harness-v1，其余 `f8da6ab`）
  - 模型：`deepseek-flash`，全部 2,729 次调用指纹 `e72d3c7f663d3e1383b00b3884cb4501`，与 G3 一致。另起看门进程逐条核对日志指纹，不同即杀进程（未触发）
  - 报告 `reports/results/sql_direct.md`（`uv run python scripts/sql_direct_report.py --run 20261018-T13-sql-direct-01 --eval-tag eval-v1.1`）：六项指标、四种结果合计 100%、SQL-L1.5S 按覆盖分列、judge 与低区分度单列、费用、打分超时逐条、各单元提交。**判定是运行时 harness-v1 的当场判定，暂定**
  - SQL-L0 失败归因 `reports/results/T13-L0-failures.md`（协调会话要求；`scripts/t13_failure_dump.py`、`scripts/t13_failure_report.py`、`scripts/t13_l0_failure_verdicts.yaml`），其中「判不清」引出 `decisions/2026-10-18-harness-v1-1-scorer-fixes.md`
  - 运行器改动 PR #100（`harness/score_guard.py`、`--backfill-from-raw`；系统提示与评分器不动，有逐字节测试）
- 预热（交接第一条）：开跑前在 harness 执行器里把 122 题全部 137 份中文参考 SQL 各跑一遍（0 报错，合计 9.1 秒，最慢 Q76-2 1.4 秒，Q33 0.23 秒），并对 `l0`（25 张）、`dwd`（5 张）、`ads`（25 张）每张表整表扫一遍（`count()`、`sum(cityHash64(*))`）。不调用模型。全量运行 0 条执行超时
- 换单元（交接第二条）：一个进程按单元顺序连续跑，换单元 5 次；每单元首个调用单独先跑写缓存。冷启动：SQL-L1.5W 0 次（前缀与 SQL-L1 相同的部分已在缓存），其余各 1 次
- 费用：日志合计 24.80 元（上限 80）；另有第一次暂停时至多约 0.04 元已计费未记日志
- 偏离与理由：
  1. **两次暂停、三次启动，同一 run-id**。第一次是用户要求 SQL-L0 跑完先看结果；第二次是冻结评分器在 Q79 上卡死（敏感性诊断在 42 家并列第 1 上指数级搜索，判定本身 0.01 秒），整轮停在 SQL-R 约 50 分钟。续跑只补缺的 (题, 次)，无重复行
  2. **运行器改动（用户选方案 1，`decisions/2026-10-18-harness-v1-1-scorer-fixes.md` 第四节）**：打分放子进程限时（先 120 秒，后按用户决定改 10 秒），超时记 pending/score_timeout，不是判定；SQL-R 的 Q79 三条从 runs-raw 补写，不重新调用模型。因此三个单元段落的 harness 提交不同，INDEX 写明
  3. **判定暂定**：用户决定最终数字以 `harness-v1.1`（人名双向、编码字符串、Q119 分组、Q79 搜索）离线重评为准；本卡的报告数字只作进度参考。score_timeout 5 条（全是 Q79）重评前不进任何分母
  4. 英文锚点不跑（G3 第三节），代码保留
- 工时：约 4.5 小时（18:25 开工至 22:50；模型调用实际约 1.5 小时，其余为预热、暂停后的 L0 归因、Q79 诊断与运行器改动）

### 待办（本卡收尾）

- [ ] `harness-v1.1` 合并后：6 单元离线重评（`harness.rescore`，不调用模型），重新生成 `reports/results/sql_direct.md`，同时列 harness-v1 与 v1.1 两套数和逐条判定变化；score_timeout 一条不剩
- [ ] judge 13 题待 `judge-v1` 离线评
