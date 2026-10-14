# 2026-10-14 盲模式的两个漏洞：MCP 工具与 runs 规则

T01 第 0 步做隔离验证时发现两条，自己没动设置、没改测试，写进 `decisions/open-questions.md` 停下来问（正确做法）。用户 2026-10-14 裁决如下。

## 一、MCP 工具绕过了联网禁令（原 Q4）

### 问题

盲模式模板 deny 了内置的 `WebSearch` 和 `WebFetch`，实测也确实被拒。但**挂在会话里的 MCP server 不在这个管辖范围内**。T00 的会话当场复现：`claude mcp list` 显示 claude.ai Claude Docs 和 Notion 两个 server 处于已连接状态，而 `mcp__claude_ai_Notion__notion-fetch` 能抓任意 URL——等于 WebFetch 的禁令形同虚设。

这违反硬规则 1 的「隔离靠物理手段」：如果盲模式只是「agent 答应不上网」，那 T08–T10 盲写语义层的结果随时可以被质疑。

### 裁决：三层一起上

| 层 | 做法 | 性质 |
|---|---|---|
| 1 | `scripts/start-card.sh` 给 `blind` 和 `packet` 模式打印的启动命令加 `--strict-mcp-config`（不带 `--mcp-config`，即零个 MCP server） | **物理手段**，主防线 |
| 2 | `templates/claude-settings.blind.json` 的 `deny` 里逐个列出现有的 MCP server | 黑名单，补刀 |
| 3 | `scripts/verify-isolation.md` 新增 A11：agent 开工第一步自己列出可用的 `mcp__` 工具，**必须为空**，不为空就停 | **自证，准绳** |

为什么三层都要：第 2 层是黑名单，你以后装新的 MCP server 它挡不住；第 1 层是启动命令，手敲或改脚本都可能漏掉。**第 3 层是唯一能发现前两层失效的环节**——T00 的会话在沙箱里没法实测那个标志（嵌套的 `claude` 连不上 `api.anthropic.com`），所以不能只靠它。

另外，`claude mcp list --strict-mcp-config` 不认这个标志（它是顶层标志，不是子命令的），别拿它当验证手段；以 A11 的自证为准。

## 二、`Read(./runs/**)` 挡住了自己的文档（原 Q3）

### 问题

盲模板的 `Read(./runs/**)` 连 clone 自己的 `runs/README.md`、`runs/INDEX.md` 一起挡了。T00 的骨架测试要 stat 这两个文件（「每个目录都有 README」），于是盲模式下 `uv run pytest` 固定 2 红，而「测试能跑」正是隔离清单 B4 的验收项。

### 裁决：收窄规则，不改测试

`Read(./runs/**)` → `Read(./runs/*/**)`：只挡 `runs/<run-id>/` 下的日志，放行目录自己的两个文档。

代价几乎为零：**所有盲模式卡（T01、T08–T10）都在 G1 之前，而所有 run 都在 G1 之后（T11 起）**——盲写期间 `runs/` 里除了这两个文档本来就什么都没有。这条 deny 是 belt-and-braces，收窄它不损失任何实际防护。

不选「改测试吞掉 PermissionError」：那会让「README 真的缺了」和「被 deny 挡住」从此长得一样，掩盖真回归——而 T00 加这条测试就是为了防骨架烂掉。

## 影响

- 改了 `templates/claude-settings.blind.json`、`scripts/start-card.sh`、`scripts/verify-isolation.md`、`AGENTS.md` 硬规则 1，加了 4 条测试。
- **T01 的结果不受影响**：A 组 10 项当时全部被拒，它一个 MCP 工具都没用过，本卡也不需要联网（数据在本地、不调模型）。无需重跑。
- T08 之后的每张盲模式卡，启动命令必须带 `--strict-mcp-config`，开工第一步必须过 A11。
