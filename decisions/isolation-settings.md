# 隔离设置的改动记录

一行一次改动。改动范围只限：`.claude/settings.json`、`templates/claude-settings.*.json`、`scripts/start-card.sh` 里生成设置的那部分。每次改动之后必须重做 `scripts/verify-isolation.md` 的 A 组。

| 日期 | 卡 | 改了什么 | 为什么 | 谁同意 | 重做 A 组 |
|---|---|---|---|---|---|
| 2026-10-14 | T00 | **没改**。种子里的 `.claude/settings.json` 原样保留 | 当前 Claude Code 2.1.236 下 `uv run pytest` 在既有白名单（`~/.cache/uv`、`~/.local/share/uv`、pypi）里就能跑通，不需要放宽 | — | 不适用 |
| 2026-10-14 | T00（应 T01 发现） | `templates/claude-settings.blind.json`：`Read(./runs/**)` 收窄为 `Read(./runs/*/**)` | 原规则把 clone 自己的 `runs/README.md`、`runs/INDEX.md` 也挡了，B4「测试能跑」固定 2 红。盲模式卡都在 G1 之前，而 run 都在 G1 之后，收窄不损失实际防护 | 用户 2026-10-14 | 下一张盲模式卡（T08）开工时连同 A11 一起做 |
| 2026-10-14 | T00（应 T01 发现） | **收紧**：盲模板 deny 里加 8 个 MCP server；`start-card.sh` 给 blind/packet 的启动命令加 `--strict-mcp-config`；`verify-isolation.md` 加 A11 自证 | MCP 工具不受项目 deny 管辖，能联网的 server 绕过 WebSearch/WebFetch 的禁令，盲模式就只是约定不是物理手段 | 用户 2026-10-14 | 同上 |
| 2026-10-15 | 用户（T08 第一次启动时发现） | **收紧（客户端层）**：把 `~/.claude.json` 的 `claudeInChromeDefaultEnabled` 改为 `false` | `--strict-mcp-config` 只忽略**配置来的** MCP server；`claude-in-chrome` 不在 `mcpServers` 里，是客户端按 feature flag 注入的内置集成，所以标志管不住它。它能打开任意 URL，等于绕过 WebFetch 的禁令 | 用户 2026-10-15 | 已做：T08 第二次启动 A11 **首次通过** |
| 2026-10-15 | T00（应 T08 发现） | **放宽**：盲模板删掉 `Read(./runs/*/**)`，只保留主工作区的 `Read(/${SEMDEBT_MAIN_DIR}/runs/**)` 与沙箱 denyRead | 沙箱层把这条落成 `./runs/*`，连 clone 自己的 `runs/README.md`、`runs/INDEX.md` 一起挡住，B4「测试能跑」固定变红（T01 2 红、T08 3 红）。收窄过一次没解决。而盲模式卡全在 G1 之前、所有 run 都在 G1 之后，盲写期间 clone 的 `runs/` 里只有这两个文档，**这条 deny 没有保护对象** | 用户 2026-10-15 | T09 起的新 clone 自动生效；T08 不动（见下） |

## T00 的版本与生效情况

- `claude --version`：2.1.236
- `uv`：0.11.32；系统 `python3`：3.14.6（`requires-python = ">=3.11"` 满足）
- 已观察到生效：沙箱已开（`sandbox.enabled`）、uv 缓存目录在放行名单内（`uv run pytest` 成功）、写入限制生效（仓库内与 `$TMPDIR` 可写）。
- **未在 T00 实测**：`blockReadsOutsideWorkingDirectories`、`permissions.deny` 里的题库路径与 WebSearch/WebFetch。T00 的卡明令不得读取 `$SEMDEBT_EVAL_DIR`，所以这几项留给 T01 第一步按 `scripts/verify-isolation.md` 实测。

## T01 实测结果（2026-10-14）

A 组 10 项**全部被拒**，没有任何一项让它拿到内容，`decisions/isolation-check.md` 有逐条记录。上面那句「T01 通过之前不要把隔离当成已验证」至此解除——**但只对 A1–A10 成立**。同一次验证暴露了清单之外的 MCP 漏洞（A11 是因此补的），见 `decisions/2026-10-14-blind-mcp-and-runs.md`。

## A11 首次通过（2026-10-15，T08）

T08 第一次启动时 A11 **未通过**：`--strict-mcp-config` 在场，但 `claude-in-chrome` 仍然加载了。原因见上表 2026-10-15 第一行——它不是配置来的 MCP server，那个标志管不住它。T08 当时的处置是正确的：没有调用任何 MCP 工具（连取 schema 都没做）、没有改任何设置、停下来报告。

用户关掉 `claudeInChromeDefaultEnabled` 之后重启，**A 组 11 项全部通过，A11 首次为空**。至此，盲模式的联网禁令第一次被证明是**物理生效**的，而不只是约定。

**还原（G1 打完 tag、T10 结束之后）**：把 `~/.claude.json` 的 `claudeInChromeDefaultEnabled` 改回 `true`，或在 Chrome 里重新启用扩展。还原之前不要做任何盲模式卡。

**方法论教训**：`--strict-mcp-config` 覆盖「配置来的 MCP server」，不覆盖客户端注入的内置集成。所以**第三层的 A11 自证不是冗余，它是唯一发现前两层失效的手段**——这次就是它发现的。以后 Claude Code 新增任何内置集成，都只能靠 A11 兜住。

## T08 为什么不刷新设置

T08 在 runs 规则改掉时正在写 `semantic/source.yaml`。**没有动它**，理由：在一张卡进行中更换隔离设置，会让这张卡的 `isolation-check.md` 不再描述实际运行的会话——而 T08 的全部价值就是「它当时是盲的」，审计链比测试绿重要。那 3 条红只是 stat 两个文档文件，与它的产出无关，由它记进 `isolation-check.md` 即可。T09 起的新 clone 自然是绿的。

`scripts/start-card.sh --refresh-settings` 就是为「模板改了、clone 已存在」加的，但它会在 clone 有未提交改动时**拒绝执行**，正是为了防止上面这种情况。
