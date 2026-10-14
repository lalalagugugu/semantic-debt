# 隔离设置的改动记录

一行一次改动。改动范围只限：`.claude/settings.json`、`templates/claude-settings.*.json`、`scripts/start-card.sh` 里生成设置的那部分。每次改动之后必须重做 `scripts/verify-isolation.md` 的 A 组。

| 日期 | 卡 | 改了什么 | 为什么 | 谁同意 | 重做 A 组 |
|---|---|---|---|---|---|
| 2026-10-14 | T00 | **没改**。种子里的 `.claude/settings.json` 原样保留 | 当前 Claude Code 2.1.236 下 `uv run pytest` 在既有白名单（`~/.cache/uv`、`~/.local/share/uv`、pypi）里就能跑通，不需要放宽 | — | 不适用 |

## T00 的版本与生效情况

- `claude --version`：2.1.236
- `uv`：0.11.32；系统 `python3`：3.14.6（`requires-python = ">=3.11"` 满足）
- 已观察到生效：沙箱已开（`sandbox.enabled`）、uv 缓存目录在放行名单内（`uv run pytest` 成功）、写入限制生效（仓库内与 `$TMPDIR` 可写）。
- **未在 T00 实测**：`blockReadsOutsideWorkingDirectories`、`permissions.deny` 里的题库路径与 WebSearch/WebFetch。T00 的卡明令不得读取 `$SEMDEBT_EVAL_DIR`，所以这几项留给 T01 第一步按 `scripts/verify-isolation.md` 实测。**T01 通过之前，不要把隔离当成已验证。**
