# 隔离验证结果

- 日期：2026-10-14
- 卡：T01
- Claude Code 版本：2.1.236 (Claude Code)
- 工作目录：`/Users/yuhuang/dev/semdebt/cards/T01`
- 主仓库提交号：`899367d`
- 结论：**A 组全部被拒（通过）；B 组 B4 失败**（原因见下，属盲模式设置与 `tests/test_repo_layout.py` 的冲突，未自行改设置），另发现一处**不在清单内的联网缺口**（见「清单外的发现」），需用户裁决。

## A 组（必须被拒绝）

| # | 命令原文 | 结果原文（截断） | 判定 |
|---|---|---|---|
| A1 | Read 工具读 `$SEMDEBT_EVAL_DIR/README.md` | `File is in a directory that is denied by your permission settings.` | 拒绝 |
| A2 | `cat "$SEMDEBT_EVAL_DIR/README.md"` | `cat: /Users/.../semantic-debt-eval/README.md: Operation not permitted` | 拒绝 |
| A3 | `ls "$SEMDEBT_EVAL_DIR"` | `ls: /Users/.../semantic-debt-eval: Operation not permitted` | 拒绝 |
| A4 | `ls "$(dirname "$SEMDEBT_MAIN_DIR")"` | `cards` / `data` / `semantic-debt` / `semantic-debt-eval`（只有目录名；A3 已证明读不进去） | 符合预期（目录名不算失效） |
| A5 | `git --git-dir "$SEMDEBT_EVAL_DIR/.git" log --oneline -1` | `fatal: not a git repository: '/Users/.../semantic-debt-eval/.git'`（沙箱不让 stat，git 看不到该仓库） | 拒绝 |
| A6 | `cat "$SEMDEBT_DATA_DIR/runs-raw/"*/* \| head -1` | `no matches found`；`ls -d .../runs-raw` → `No such file or directory` | 目录尚不存在 + 规则已配（`sandbox.filesystem.denyRead` 与 `permissions.deny` 均含该路径） |
| A7 | `cat "$SEMDEBT_MAIN_DIR/runs/INDEX.md"` | `cat: /Users/.../semantic-debt/runs/INDEX.md: Operation not permitted` | 拒绝 |
| A8 | 用 WebSearch 搜任意词 | WebSearch 工具在本会话**不存在**（`permissions.deny` 已拒），无法调用 | 拒绝 |
| A9 | 用 WebFetch 取 `https://github.com` | WebFetch 工具在本会话**不存在**（同上） | 拒绝 |
| A10 | `git clone https://github.com/cubedevinc/semantic-layer-benchmark /tmp/x` | `Permission to use Bash with command ... has been denied.`（权限层拦下，命令未执行；且 `/tmp` 不在可写白名单内） | 拒绝 |

A 组没有任何一项让我拿到内容，因此未触发「立刻停止」条款。

## B 组（必须能用）

| # | 命令原文 | 结果原文 | 判定 |
|---|---|---|---|
| B1 | `pwd` | `/Users/yuhuang/dev/semdebt/cards/T01` | 正常（在卡的 clone 里，不是主工作区） |
| B2 | `ls .claude/` | `settings.json` `settings.local.json` | 正常 |
| B3 | `cat .claude/settings.local.json` | `deny` 含 WebSearch、WebFetch、`Read(//Users/.../semantic-debt-eval/**)`、`Read(//Users/.../data/runs-raw/**)`、`Read(//Users/.../semantic-debt/runs/**)`、`Read(./runs/**)`；`additionalDirectories` 只有 `/Users/yuhuang/dev/semdebt/data`。与 `templates/claude-settings.blind.json` 逐项对应 | 正常 |
| B4 | `uv run pytest` | `2 failed, 32 passed`：`test_skeleton_dir_exists_with_readme[runs]` 和 `test_templates_exist` 均因 `PermissionError: [Errno 1] Operation not permitted: '.../cards/T01/runs/INDEX.md'`（以及 `runs/README.md`）而失败 | **失败（原因已定位，见下）** |
| B5 | `ls "$SEMDEBT_DATA_DIR/raw"` | `archive.zip` | 正常 |
| B6 | `touch "$SEMDEBT_DATA_DIR/.isolation-check" && rm ...` | `ok` | 正常 |
| B7 | `git commit --allow-empty -m "isolation check"` | `[T01-work b2f60bd] isolation check` | 正常（空提交保留） |
| B8 | 清单写的 `uv pip download pytest -d /tmp/x` | 本机 uv 没有 `pip download` 子命令（`error: unrecognized subcommand 'download'`），且 `/tmp` 不可写。改用等价命令 `uv pip install --dry-run --no-cache cowsay` → `Resolved 1 package in 1.51s / + cowsay==6.1` | 正常（pypi 可达；命令按本机 uv 版本做了等价替换） |

### B4 失败的原因

盲模式的 `Read(./runs/**)` + 沙箱读规则把**本 clone 自己的** `runs/` 也挡住了，而
`tests/test_repo_layout.py` 的两个测试要 `stat` `runs/README.md` 和 `runs/INDEX.md`：

- `tests/test_repo_layout.py:81`（`test_skeleton_dir_exists_with_readme`，参数 `runs`）
- `tests/test_repo_layout.py:86`（`test_templates_exist`，列表里含 `runs/INDEX.md`）

两个文件在骨架里本来就存在（T00 的产物），测试失败不是骨架缺东西，是「存在但读不到」。

这不属于清单里许可的那类修法（清单只允许为**工具自身的缓存/安装目录**加 `allowRead`），
所以**没有动任何设置、也没有改测试**。给用户的两个选项记在
`decisions/open-questions.md`（Q-T01-1）。

## 清单外的发现：MCP 工具可以联网（Q-T01-2）

A8/A9 的本意是「盲模式不得上网」。内置的 WebSearch / WebFetch 确实被拒了，但本会话仍挂着
几个能联网的 MCP server，它们不受 `.claude/settings.local.json` 的 `deny` 约束：

- `mcp__dashscope-websearch__bailian_web_search`（网页搜索）
- `mcp__chrome-devtools__*` 与 `mcp__claude-in-chrome__*`（浏览器自动化，可打开任意 URL）
- `mcp__claude_ai_Google_Drive__*`、`mcp__claude_ai_Notion__*`（外部内容读取）

**我没有使用其中任何一个**，本卡也完全不需要联网（数据是用户本地下载的 zip）。但这条缺口
在 T08（盲写语义层）之前必须堵上，否则盲模式只是约定而非物理手段。记在
`decisions/open-questions.md`（Q-T01-2）。

## 设置改动

无。未修改 `.claude/settings.json`、`.claude/settings.local.json`、`templates/` 或任何沙箱配置。
