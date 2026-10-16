# 待裁决的问题

agent 发现设计层面的问题（档位定义、评分规则、题目口径、隔离设置）时：**停下**，在这里追加一条，然后问用户。不要自行改设计。

裁决之后：把结论写成 `decisions/YYYY-MM-DD-<主题>.md`，在本表把状态改成「已裁决」并注明那个文件。

**编号用 `<卡号>-<序号>`**（如 `T08-1`、`T05-2`）。早期的 1–9 是全局序号，保持原样不动。改用卡号前缀是因为：两家并行时各自认领下一个全局序号必然撞车——本表就因此冲突过一次（T08 与 T04 同时写了「第 9 条」）。

| # | 日期 | 提出方（卡） | 问题 | 为什么要用户裁决 | 状态 | 裁决记录 |
|---|---|---|---|---|---|---|
| 1 | 2026-10-14 | T00（Claude Code） | 目录布局实际是 `~/dev/semdebt/*`，而 `AGENTS.md`、`START-HERE.md` 写的是 `~/semdebt/*` | 影响所有卡的启动位置说明；代码已改为只认环境变量，但文档与实际不一致会误导下一张卡 | 已裁决（2026-10-14，用户：以环境变量为准） | `decisions/2026-10-14-paths-from-env.md` |
| 2 | 2026-10-14 | T00（Claude Code） | 本机未安装 `gh`，无法按工作方式用 `gh pr create` 开 PR | 每张卡的收尾动作都依赖它 | 已裁决（2026-10-14，用户已装 `gh` 2.102.0 并登录） | 见本表下方「gh 的实际情况」 |
| 3 | 2026-10-14 | T01（Claude Code） | 盲模式的 `Read(./runs/**)` 把本 clone 自己的 `runs/README.md`、`runs/INDEX.md` 也挡住，`uv run pytest` 因此 2 红（`tests/test_repo_layout.py:81`、`tests/test_repo_layout.py:86`）。两条路：(a) 改测试，把 `PermissionError` 当成「存在但盲模式不可读」放行；(b) 放宽 deny，只许读 `runs/README.md` 与 `runs/INDEX.md` | 动的是隔离设置或 T00 冻结的测试，两者都不该由盲模式的卡自己定；而且 B4「测试能跑」是隔离清单的验收项 | 已裁决（2026-10-14，用户选 b 的收窄版：`Read(./runs/*/**)`，测试不动） | `decisions/2026-10-14-blind-mcp-and-runs.md` |
| 4 | 2026-10-14 | T01（Claude Code） | 内置 WebSearch/WebFetch 已被拒，但会话里仍挂着能联网的 MCP server（`mcp__dashscope-websearch__bailian_web_search`、`mcp__chrome-devtools__*`、`mcp__claude-in-chrome__*`、Google Drive、Notion），不受项目 `deny` 约束 | 硬规则 1 要求隔离靠物理手段；MCP 不在项目设置的管辖范围内，只能由用户在客户端层面关掉。T08 之前必须堵上，否则盲写语义层的结果可被质疑 | 已裁决（2026-10-14，用户选三层：`--strict-mcp-config` + 模板 deny + A11 自证） | `decisions/2026-10-14-blind-mcp-and-runs.md` |
| 5 | 2026-10-14 | T02（Codex） | `score(candidate_rows, refs, rules)` 的 `rules` 字段和非结果输入契约未定义：执行失败如何传入；Top-N 边界并列用哪一列（或哪些列）识别；候选用边界外并列项替换第 N 名时，如何提供完整边界集合 | 不同契约会改变公共 API、后续 harness 接入方式和评分结果；仅凭已截断的参考结果无法可靠判断边界外是否并列 | 已裁决（2026-10-14） | `decisions/2026-10-14-scorer-pipeline-contract.md` |
| 6 | 2026-10-14 | T02（Codex） | 外部公开的 strict judge 实际接受缺参考列、额外行、字符串标签改写和接近 1% 的漂移；按冻结规则评分，排除 11 条本项目有意更宽的差异后，一致率仍只有 515/583（88.3%），无法达到 T02 的 95% 验收线 | 不能为追分修改冻结规则；需决定是调整/豁免该验收项，还是另定一个与冻结规则一致的外部判定基线 | 已裁决（2026-10-14，换验收口径，不另定基线；但独立复核推翻了「无 bug」，T02 仍有三条缺陷要修） | `decisions/2026-10-14-scorer-contract-and-acceptance.md` |

| 7 | 2026-10-14 | T02 独立复核（经 T00 会话转记） | 冻结规则第 2 条用的是**相对**误差 0.5%，在近零量上会炸开：实测 S-S Q99 约 17.13%、G-S Q29 约 12.40%，实际只是末位舍入，按现行规则一律判错 | 不只影响与外部基准的对齐率：真跑起来（T13 起）模型在近零量上少一位小数就被判错，而这与语义层质量无关，等于给**所有单元**加一层与被测变量无关的噪声。改的是冻结的比对规则，必须用户裁决 | 已裁决（2026-10-15，用户选 A：加绝对容差下限 `max(0.5%×|参考|, atol)`，比率 1e-4 / 金额 0.01 / 其余 0） | `decisions/2026-10-14-scorer-contract-and-acceptance.md` 第四节 |

| 8 | 2026-10-15 | T00 会话（定第 7 条时顺带发现） | 冻结规则第 2 条的 0.5% **相对**容差同样作用在计数类上：订单数 10000 与 10040 只差 0.4%，按现行规则算相等。计数通常应当精确相等 | 与第 7 条同源但方向相反——第 7 条是容差在近零量上太严，这条是容差在大计数上太松。两者都改的是冻结的比对规则。**不阻塞**：先按第 7 条的裁决实现，这条单独裁 | 已裁决（2026-10-15，计数精确相等，但只在参考列返回类型为整数时生效） | `decisions/2026-10-14-scorer-contract-and-acceptance.md` 第八节；影响估算 1 条 correct→wrong（S-S Q83） |

| 9 | 2026-10-15 | T04（Codex，题库） | 100题复核提出22项待审阅发现：Q17、Q25、Q40、Q42、Q44、Q45、Q65、Q67、Q69、Q70、Q74、Q75、Q76、Q80、Q82、Q83、Q84、Q92、Q94、Q95、Q98、Q100 | 20项来自此前未审计题，2项为既有裁决重审；题目口径不得自行改动。证据和选项只存题库，待用户在题库PR #7逐项裁决并审阅中文，此前不进入T05 | 待裁决 | 题库 PR #7（不在主仓库复制题目、SQL或解法） |
| T08-1 | 2026-10-15 | T08（Claude Code） | 第 3 条裁决的收窄写法 `Read(./runs/*/**)` 没达到目的：Claude Code 把它翻译进沙箱 read-deny 时掉了一层，变成 `./runs/*`，照样挡住本 clone 的 `runs/README.md`、`runs/INDEX.md`。而且从 2 红变成 **3 红**（`rglob` 现在能列到这两个文件，`test_no_api_key_literals` 也跟着炸） | 动的还是隔离设置或 T00 冻结的测试；B4「测试能跑」是隔离清单的验收项。**不阻塞 T08**：A 组全过，本卡的校验脚本不碰 `runs/` | 已裁决（2026-10-15，用户：主仓库 PR #19 从盲模板去掉针对 clone 本地 `runs/` 的 deny；**本 clone 卡进行中不刷新设置**，免得 A 组实测结果失真，T09 起生效） | `decisions/isolation-check.md`「B4 的三条失败，逐条」 |
| T08-2 | 2026-10-15 | T08（Claude Code） | **约定 11 说「库存是每日快照」，数据里是每周一次**：`FactInventory` 只有 156 个快照日，全部落在周六，相邻间隔都是 7 天（2007-01-06 ~ 2009-12-26） | 约定清单已定稿、不得自行修改（AGENTS.md 硬规则 2）。「不能跨日期求和」和「当前库存取每个门店 × 产品最近一次快照」这两句仍然成立，所以按约定做出来的结果不会错；但「每日」的说法会让人以为任意一天都有库存。**不阻塞 T08**：已按约定原文实现（`dwd.wide_current_inventory`），并记进 `source.yaml` 的 data_quality / inventory-weekly | 已裁决（2026-10-15，去掉 clone 本地的 runs deny） | `decisions/isolation-settings.md`，PR #19 |
| T08-3 | 2026-10-15 | T08（Claude Code） | **约定 4 把「节假日与平日」和「周末与工作日」并列成两种比较，数据里是同一个划分**：`DimDate.IsHoliday = Yes` 的 731 天恰好是全部 366 个周六加 365 个周日，没有一个工作日被标成节假日；`IsWorkDay` 是同一划分的另一种写法 | 两种比较会得到同一个结果（2009 年全渠道日均：平日 10,260,907.86、节假日 10,215,251.62），库里没有真正的公共假日字段可用。**不阻塞 T08**：两组字段都照原样描述了，记进 data_quality / holiday-equals-weekend | 待裁决 | — |
| T08-4 | 2026-10-15 | T08（Claude Code） | **约定 14 的「新客」在这个库里几乎恒为空**：18,869 个客户里 18,868 个的首次购买日落在 2007 年，只有 1 个落在 2009 年。按「首次购买日在截止日前 90 天内」，2008 年之后任何窗口的新客数都是 0 或 1 | 口径本身定义清楚、可实现，但在这份数据上没有区分度，新客数 / 新客销售额 / 新客销售额占比三个指标基本恒为 0。**不阻塞 T08**：已按约定原文实现，未因结果为空而改口径；记进 data_quality / new-customer-degenerate | 待裁决 | — |
| T09-1 | 2026-10-15 | T09（Claude Code） | 盲模式下 `uv run pytest` 有 4 红：`tests/test_repo_layout.py` 里调 `scripts/start-card.sh` 的 4 个用例（`test_bash_and_python_parsers_agree`、`test_start_card_refuses_unknown_id`、`test_start_card_refuses_open_mode_before_g1`、`test_start_card_dry_run_touches_nothing`），都报「找不到 `$SEMDEBT_MAIN_DIR/tasks/cards.yaml`」——脚本读主工作区，主工作区在卡的 clone 之外，被沙箱拒读 | 与 T08-1 同类：要么改 T00 的测试（盲模式下读不到主工作区时跳过，或让脚本可指向 clone 自己的 cards.yaml），要么放宽隔离，都不该由盲模式的卡自己定。B4「测试能跑」是隔离清单的验收项。**不阻塞 T09**：本卡的测试全绿 | 待裁决 | — |
| T08-5 | 2026-10-15 | T08（Claude Code） | **两张销售表的线上口径对不上**（不是约定与数据矛盾，是数据自身不一致，但直接影响约定 1 与 2 的选表）：`FactSales` 里 `ChannelName = Online` 的销售额 2,677,599,035.07 / 退货 32,983,261.29，而 `FactOnlineSales` 合计销售额 2,718,202,629.81 / 退货 29,244,318.20。销售额差 40,603,594.74（1.5%），退货差 3,738,943.09（12.8%） | 同一个「线上销售额」问题，按约定 1（用线上明细）和按约定 2（用全渠道的 Online 渠道）会得到不同答案；两张表既不能相加也不能互相替代。这会影响参考答案的口径和评分容差。**不阻塞 T08**：按约定 1 / 2 选表的规则已写进 `source.yaml`，并记进 data_quality / online-sales-mismatch | 已裁决（2026-10-15，线上 = FactOnlineSales，全渠道 = FactSales，混用场景整题落 FactSales） | `decisions/2026-10-15-online-vs-omnichannel-tables.md` |
| T10-1 | 2026-10-15 | T10（Claude Code） | **`metrics.yaml` 里「两张表都能算」的 23 个指标只有一个调用名，而且指错了表**：如「销售额」`dataset: FactOnlineSales`、`alternate_dataset: FactSales`，但 `cube_member: sales.sales_amount`，而 `sales` cube 按 `naming.cubes` 是**全渠道**（FactSales）；`online_sales` cube 上没有销售额、毛利、退货等成员。DAX 同理：度量值名全模型唯一，`[Sales Amount]` 只能挂在一张表上。照现状渲染，L2 的 agent 回答「未说明渠道的销售额」（约定 1）只能调到全渠道口径，必错；回答门店类问题又没有对应调用名 | 改的是 T08 产出的指标清单结构（每个指标一个还是两个调用名），直接决定 L2 三个单元能不能答对约定 1 的题；而且 `validate.py` 第 4 项按名字集合校验，不能由渲染器私下补 | 已裁决（2026-10-15，用户：每表一个调用名） | `decisions/2026-10-15-dual-dataset-metric-callables.md` |
| T10-2 | 2026-10-16 | T10（Claude Code） | **L1 上下文约 4 万 token，是设计费用估算假设（直答每次输入约 1 万 token）的 4 倍**：SQL-L1 约 40,600、L1.5W 约 46,800、L2 约 41,500、L1.5S 约 27,300（按 DeepSeek 官方经验比例估算，见 `reports/validation/context_sizes.md`）。R / L0 约 3,700 ~ 4,000 | 费用估算和预算上限是设计层面的；而且压缩上下文（删数据探查数字、改呈现）会改变 L1 的内容，本卡不得自行改。**不阻塞 T10**：上下文照 `source.yaml` 原样渲染；T11 / T12 用 API 的实际用量重估预算，届时由用户决定 | 已转为 T11/T12 的硬要求（2026-10-16，不另行裁决） | `tasks/T11-sql-harness.md`「来自前面卡片的硬要求」第二条：上下文放稳定前缀、记录 cache hit/miss、T12 用实测重估预算后才开 T13 |
| T11-1 | 2026-10-16 | T11（Claude Code） | **执行超时取多少秒**（卡片硬要求三：写成参数、记进决策）。已实现为 `--exec-timeout`，超时单独归类为 `error_class=timeout`（评分仍是 `exec_error`，报告单列，不算 `wrong`）。**暂定默认 120 秒**：外部基准 Q33 本地 89.457 秒，60 秒会让它在所有单元必然失败、且与语义层无关；120 秒的代价只落在失控查询上（每次最多多等 60 秒） | 超时值影响所有单元的可比性，卡片要求写进决策 | 已裁决（2026-10-16，用户：120 秒，另加全局内存与结果行数闸，三类失败分开归类） | `decisions/2026-10-16-t11-exec-limits-and-scope-message.md` 第一、二节 |
| T11-2 | 2026-10-16 | T11（Claude Code） | **chDB 会把失败查询的残留输出交给下一条查询**：查询在流式执行中报错（超时、结果行数超限、`throwIf` 等）后，同一 session 的**下一条**查询返回的是上一条的半截输出而不是自己的结果（实测 chdb 3.x；语法错、未知列不会）。harness 已在每次执行报错后用哨兵查询重新同步，并有回归测试。**可能影响已有产出**：`scripts/validate_scorer.py`（T02）在同一 session 里连续执行 600 条候选，若某条在流式阶段报错，紧随其后的一条拿到的可能是错的结果；题库侧生成参考答案的脚本（T03/T05）若同样复用 session 也有此风险 | 涉及 Codex 的 T02 与题库侧参考答案，需要跨厂商复核，不由本卡改 | 已裁决（2026-10-16，用户：harness 的修复保留；连带影响派给 Codex 重跑、T05b 跨引擎确认） | `decisions/2026-10-16-t11-exec-limits-and-scope-message.md` 第四节 |

<!-- 追加格式：
| 7 | YYYY-MM-DD | Txx（Claude Code / Codex） | 一句话问题 | 为什么不能自己定 | 待裁决 | — |
-->

## gh 的实际情况（2026-10-14，T00 实测）

`gh` 已装（2.102.0）并已登录账号 `lalalagugugu`，但 **agent 会话里用不了**：会话跑在沙箱里，读不到 macOS keyring，`gh auth status` 报 `The token in keyring is invalid`。这不是登录坏了，是沙箱不给访问钥匙串。

所以每张卡的收尾按这个来：agent 推分支 → 把 `gh pr create` 命令给用户 → 用户在自己的终端（或 Claude Code 里用 `!` 前缀）运行。不要为了让 `gh` 能用而放宽沙箱设置。
