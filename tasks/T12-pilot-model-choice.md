# T12 最小样本试跑与选模型

- 状态：试跑与选模型完成（2026-10-18，选 Flash）；离线重评待评分器 `required_columns` 与 `eval-v1.1`，之后才到 G3
- 负责：Claude Code + 用户裁决
- 模式：普通（`scripts/start-card.sh T12`）
- 依赖：G2（题集冻结）、T11
- 预算：20 元

## 目标

在全量之前，用最小样本同时完成三件事：选定第一期唯一的被测模型；修掉 harness 的 bug；确认题目难度不贴边。

## 设置

| 项 | 设置 |
|---|---|
| 题目 | T06 抽好的 24 道最小样本（`questions/pilot.yaml`，全部来自调优题：Q1、Q2、Q3 各 8 道） |
| 单元 | SQL-R、SQL-L1 |
| 模型 | `deepseek-flash`（V4.1 Flash）与 `deepseek-v4-pro`，各跑 3 次 |
| 调用量 | 24 × 2 × 2 × 3 = 288 次 |

## 选择规则

- 默认选 Flash。
- 如果 Flash 在 SQL-L1 上的准确率低于 50%，或 Pro 比 Flash 高 10 个点以上，就选 Pro。
- 贴边检查：SQL-L1 不应高于 95%，SQL-R 不应低于 5%；贴边就停下来，和用户一起检查题集与 harness。

## 来自 T11 的实测（2026-10-16，冒烟 7 次调用，`runs/20261016-T11-smoke-01/SQL-L1.jsonl`）

样本极小（2 道题 × 3 次 + 1 次重试），只能当**下限**用，不能当均值。但有三件事已经确定：

**一、思考模式确实开着，而且 reasoning token 单独记录。** 冒烟六次调用的 `reasoning_tokens` 是 33 / 68 / 207 / 238 / 139 / 40，`completion_tokens` 是 60 / 186 / 321 / 340 / 247 / 100。**不要据此认为思考开销可以忽略**——冒烟用的是最容易的题，思考长度随题目难度上涨，本卡要用覆盖各难度的样本重测。输出 token 是按输出价计费的，低估它会低估全量成本。

**二、费用几乎全部由「缓存未命中的输入」决定。** 同一单元内：

| 情形 | prompt token | 其中未命中 | 费用（元） |
|---|---:|---:|---:|
| 首次调用（冷） | 46,137 | 46,137 | **0.0464** |
| 稳态调用（热） | 46,139 | 187 | **0.0015–0.0025** |

**冷热差约 20–30 倍。** 所以本卡估算全量成本时，关键变量不是 token 总数，而是**会发生多少次冷启动**（单元切换、缓存过期、重试时 prompt 变长导致后缀未命中）。按 token 总量乘单价估会严重高估。

**三、模型是显式参数且已记进日志**：`model_requested` 与 `model_version` 两个字段都有（冒烟用的是 `deepseek-flash`）。选模型实验可以直接对比，不需要改 harness。

**本卡要重测的**：用覆盖各难度的样本测 reasoning token 分布；测缓存过期的时间窗（同一前缀隔多久会掉出缓存）；据此给 T13 一个**按冷启动次数**而不是按 token 总量的预算模型。

## 题库版本（2026-10-16，协调会话）

**harness 只从固定版本读题库，不读共用工作区。** 题库目录（`$SEMDEBT_EVAL_DIR`）是 Codex 原地干活的工作树，可能停在别的分支、带未提交的改动（T11 接锚点时就遇到了，靠逐字节比对 `origin/main` 才确认没读错）。试跑同样必须从 `eval-v1` tag 的内容读题（例如 `git worktree add` 到数据目录下的只读副本，或 `git archive eval-v1` 解出），日志记 tag 与提交号；读到的不是 tag 内容就拒绝开跑。T11 的发现，2026-10-16 协调会话写入。

## 交付物

1. `decisions/model.md`：两个模型在两个单元上的准确率（按 Q 级拆开）、四种结果的占比、实测 token、选择结果与理由。
2. 试跑中修掉的 bug 清单（只修解析、执行、日志类 bug，不改提示措辞去迁就题目）。
3. 冻结系统提示与评分规则，打 tag `harness-v1`。
4. 用实测 token 更新 BOARD 的预算估算。

## 用户确认

- [x] 同意模型选择：Flash（2026-10-18，`decisions/2026-10-18-reference-columns-asked-only.md` 第四节）。
- [ ] 离线重评（评分器支持 `required_columns`、`eval-v1.1` 冻结之后）：两种口径对比补进 `decisions/model.md`。
- [ ] G3：同意冻结（重评之后才打 `harness-v1`）。

## 记录

- 产出：
  - 运行：`runs/20261018-T12-pilot-flash-01/`、`runs/20261018-T12-pilot-pro-01/`（各 144/144 done）、`runs/20261018-T12-cache-flash-01/`（缓存过期探测，10 秒～4 小时）；`runs/INDEX.md` 三行
  - 交付物 1：`decisions/model.md`（准确率含/不含低区分度两列、按 Q 级、四种结果、token 分布、指纹、选择与理由）；完整报告 `reports/T12-pilot.md`（`uv run python scripts/pilot_report.py --run deepseek-flash=20261018-T12-pilot-flash-01 --run deepseek-v4-pro=20261018-T12-pilot-pro-01 --cache-run 20261018-T12-cache-flash-01`）
  - 交付物 2，修掉的 harness bug（只涉及读题、执行与日志，不改提示和评分）：
    1. `eval-v1` 新增的 `questions/pilot.yaml` 是抽样清单，加载器把它当题目文件读，直接崩溃 → 加载器与测试跳过它（`harness/questions.py` 的 `question_files`）
    2. BOARD 第 13 项：harness 只认干净的固定 tag 检出（`verify_eval_tag`，`--eval-tag`，默认 `eval-v1`），dry run 也校验，日志记 `eval_tag`
    3. 指纹守卫：同一模型在一次运行里出现第二个 `system_fingerprint` 就停（`FingerprintGuard`），续跑时从已有日志播种
    4. 每个单元的首个调用单独先跑，写好前缀缓存再开并发（原来并发 8 时每个线程的首个调用都是冷启动）
    5. `runs/INDEX.md` 里 10-17 的一行误写在格式注释里，已挪出
    - 新增：`--pilot`、`--est-from-args`、`harness/cache_probe.py`、`scripts/pilot_report.py`、`scripts/t12_column_diagnostic.py`（列口径诊断，上界，不是评分）
  - 交付物 3（`harness-v1`）：按裁决推迟到离线重评之后
  - 交付物 4（预算）：T13 按冷启动次数的预算模型见 `decisions/model.md`，Flash 约 24 元（上限 80）；冷启动一轮 8 个单元只要 0.16 元，费用几乎全由输出 token 决定
  - 价格表：`harness/cells.py` 与官方价格页逐项一致，未改
  - 语义层：在 `semantic-v1.1` 上重新渲染，SQL-R、SQL-L1 上下文逐字节一致
  - 费用：Flash 1.29 元、Pro 9.62 元、缓存探测 0.33 元（14 次，4 小时仍命中）、Pro 被叫停时很可能已发出的 1 次调用约 0.02 元，合计约 11.3 元（上限 20）
- 偏离与理由：
  - 选择规则字面触发「选 Pro」（Flash SQL-L1 47.6% < 50%），按用户裁决不作数：前提「Pro 更强」不成立，触发来自列口径（open-questions T12-1）
  - Pro 第一次启动后被用户叫停（要先看 Flash 结果），日志为空；第二次用同一 run-id 跑完，见 `runs/INDEX.md`
  - venv 用 Homebrew Python 3.14 建（沙箱读不到 uv 管理的 Python），依赖按 `uv.lock` 锁定
  - 发现评分口径问题后按 AGENTS.md 停下、写进 open-questions，未改评分器、题库或提示
- 工时：约 5 小时（含缓存探测等待）
