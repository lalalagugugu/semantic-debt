# 隔离设置的改动记录

一行一次改动。改动范围只限：`.claude/settings.json`、`templates/claude-settings.*.json`、`scripts/start-card.sh` 里生成设置的那部分。每次改动之后必须重做 `scripts/verify-isolation.md` 的 A 组。

| 日期 | 卡 | 改了什么 | 为什么 | 谁同意 | 重做 A 组 |
|---|---|---|---|---|---|
| 2026-10-14 | T00 | **没改**。种子里的 `.claude/settings.json` 原样保留 | 当前 Claude Code 2.1.236 下 `uv run pytest` 在既有白名单（`~/.cache/uv`、`~/.local/share/uv`、pypi）里就能跑通，不需要放宽 | — | 不适用 |
| 2026-10-14 | T00（应 T01 发现） | `templates/claude-settings.blind.json`：`Read(./runs/**)` 收窄为 `Read(./runs/*/**)` | 原规则把 clone 自己的 `runs/README.md`、`runs/INDEX.md` 也挡了，B4「测试能跑」固定 2 红。盲模式卡都在 G1 之前，而 run 都在 G1 之后，收窄不损失实际防护 | 用户 2026-10-14 | 下一张盲模式卡（T08）开工时连同 A11 一起做 |
| 2026-10-14 | T00（应 T01 发现） | **收紧**：盲模板 deny 里加 8 个 MCP server；`start-card.sh` 给 blind/packet 的启动命令加 `--strict-mcp-config`；`verify-isolation.md` 加 A11 自证 | MCP 工具不受项目 deny 管辖，能联网的 server 绕过 WebSearch/WebFetch 的禁令，盲模式就只是约定不是物理手段 | 用户 2026-10-14 | 同上 |

## T00 的版本与生效情况

- `claude --version`：2.1.236
- `uv`：0.11.32；系统 `python3`：3.14.6（`requires-python = ">=3.11"` 满足）
- 已观察到生效：沙箱已开（`sandbox.enabled`）、uv 缓存目录在放行名单内（`uv run pytest` 成功）、写入限制生效（仓库内与 `$TMPDIR` 可写）。
- **未在 T00 实测**：`blockReadsOutsideWorkingDirectories`、`permissions.deny` 里的题库路径与 WebSearch/WebFetch。T00 的卡明令不得读取 `$SEMDEBT_EVAL_DIR`，所以这几项留给 T01 第一步按 `scripts/verify-isolation.md` 实测。

## T01 实测结果（2026-10-14）

A 组 10 项**全部被拒**，没有任何一项让它拿到内容，`decisions/isolation-check.md` 有逐条记录。上面那句「T01 通过之前不要把隔离当成已验证」至此解除——**但只对 A1–A10 成立**。同一次验证暴露了清单之外的 MCP 漏洞（A11 是因此补的），见 `decisions/2026-10-14-blind-mcp-and-runs.md`：**A11 在 T08 第一次实测通过之前，不要认为盲模式的联网禁令是物理生效的。**
