# 待裁决的问题

agent 发现设计层面的问题（档位定义、评分规则、题目口径、隔离设置）时：**停下**，在这里追加一条，然后问用户。不要自行改设计。

裁决之后：把结论写成 `decisions/YYYY-MM-DD-<主题>.md`，在本表把状态改成「已裁决」并注明那个文件。

| # | 日期 | 提出方（卡） | 问题 | 为什么要用户裁决 | 状态 | 裁决记录 |
|---|---|---|---|---|---|---|
| 1 | 2026-10-14 | T00（Claude Code） | 目录布局实际是 `~/dev/semdebt/*`，而 `AGENTS.md`、`START-HERE.md` 写的是 `~/semdebt/*` | 影响所有卡的启动位置说明；代码已改为只认环境变量，但文档与实际不一致会误导下一张卡 | 已裁决（2026-10-14，用户：以环境变量为准） | `decisions/2026-10-14-paths-from-env.md` |
| 2 | 2026-10-14 | T00（Claude Code） | 本机未安装 `gh`，无法按工作方式用 `gh pr create` 开 PR | 每张卡的收尾动作都依赖它 | 已裁决（2026-10-14，用户已装 `gh` 2.102.0 并登录） | 见本表下方「gh 的实际情况」 |
| 3 | 2026-10-14 | T01（Claude Code） | 盲模式的 `Read(./runs/**)` 把本 clone 自己的 `runs/README.md`、`runs/INDEX.md` 也挡住，`uv run pytest` 因此 2 红（`tests/test_repo_layout.py:81`、`tests/test_repo_layout.py:86`）。两条路：(a) 改测试，把 `PermissionError` 当成「存在但盲模式不可读」放行；(b) 放宽 deny，只许读 `runs/README.md` 与 `runs/INDEX.md` | 动的是隔离设置或 T00 冻结的测试，两者都不该由盲模式的卡自己定；而且 B4「测试能跑」是隔离清单的验收项 | 已裁决（2026-10-14，用户选 b 的收窄版：`Read(./runs/*/**)`，测试不动） | `decisions/2026-10-14-blind-mcp-and-runs.md` |
| 4 | 2026-10-14 | T01（Claude Code） | 内置 WebSearch/WebFetch 已被拒，但会话里仍挂着能联网的 MCP server（`mcp__dashscope-websearch__bailian_web_search`、`mcp__chrome-devtools__*`、`mcp__claude-in-chrome__*`、Google Drive、Notion），不受项目 `deny` 约束 | 硬规则 1 要求隔离靠物理手段；MCP 不在项目设置的管辖范围内，只能由用户在客户端层面关掉。T08 之前必须堵上，否则盲写语义层的结果可被质疑 | 已裁决（2026-10-14，用户选三层：`--strict-mcp-config` + 模板 deny + A11 自证） | `decisions/2026-10-14-blind-mcp-and-runs.md` |
| 5 | 2026-10-14 | T02（Codex） | `score(candidate_rows, refs, rules)` 的 `rules` 字段和非结果输入契约未定义：执行失败如何传入；Top-N 边界并列用哪一列（或哪些列）识别；候选用边界外并列项替换第 N 名时，如何提供完整边界集合 | 不同契约会改变公共 API、后续 harness 接入方式和评分结果；仅凭已截断的参考结果无法可靠判断边界外是否并列 | 已裁决（2026-10-14） | `decisions/2026-10-14-scorer-pipeline-contract.md` |
| 6 | 2026-10-14 | T02（Codex） | 外部公开的 strict judge 实际接受缺参考列、额外行、字符串标签改写和接近 1% 的漂移；按冻结规则评分，排除 11 条本项目有意更宽的差异后，一致率仍只有 515/583（88.3%），无法达到 T02 的 95% 验收线 | 不能为追分修改冻结规则；需决定是调整/豁免该验收项，还是另定一个与冻结规则一致的外部判定基线 | 已裁决（2026-10-14，换验收口径，不另定基线；但独立复核推翻了「无 bug」，T02 仍有三条缺陷要修） | `decisions/2026-10-14-scorer-contract-and-acceptance.md` |

| 7 | 2026-10-14 | T02 独立复核（经 T00 会话转记） | 冻结规则第 2 条用的是**相对**误差 0.5%，在近零量上会炸开：实测 S-S Q99 约 17.13%、G-S Q29 约 12.40%，实际只是末位舍入，按现行规则一律判错 | 不只影响与外部基准的对齐率：真跑起来（T13 起）模型在近零量上少一位小数就被判错，而这与语义层质量无关，等于给**所有单元**加一层与被测变量无关的噪声。改的是冻结的比对规则，必须用户裁决 | 待裁决 | — |

<!-- 追加格式：
| 7 | YYYY-MM-DD | Txx（Claude Code / Codex） | 一句话问题 | 为什么不能自己定 | 待裁决 | — |
-->

## gh 的实际情况（2026-10-14，T00 实测）

`gh` 已装（2.102.0）并已登录账号 `lalalagugugu`，但 **agent 会话里用不了**：会话跑在沙箱里，读不到 macOS keyring，`gh auth status` 报 `The token in keyring is invalid`。这不是登录坏了，是沙箱不给访问钥匙串。

所以每张卡的收尾按这个来：agent 推分支 → 把 `gh pr create` 命令给用户 → 用户在自己的终端（或 Claude Code 里用 `!` 前缀）运行。不要为了让 `gh` 能用而放宽沙箱设置。
