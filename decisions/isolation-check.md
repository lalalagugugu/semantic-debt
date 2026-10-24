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

---

# 隔离验证结果（第二次：T08 开工自检）

- 日期：2026-10-15
- 卡：T08（盲模式）
- Claude Code 版本：2.1.236 (Claude Code)
- 工作目录：`/Users/yuhuang/dev/semdebt/cards/T08`
- 启动命令是否带 `--strict-mcp-config`：**否**（见下）
- 主仓库提交号：`7b87fa4`
- 结论：**未通过（已停止）。A11 不为空。**

## A11 未通过

A11 是自证项（见 `scripts/verify-isolation.md`、`decisions/2026-10-14-blind-mcp-and-runs.md`）：
本会话可用的 `mcp__` 开头的工具必须为空。实测**不为空**：

- 会话启动时的系统提示里带着完整的「Claude in Chrome browser automation」一节
  （指示如何调用 `mcp__claude-in-chrome__navigate` 等工具）。
- 会话启动时的 system-reminder 原文：
  「The following MCP servers are still connecting — their tools (typically named
  `mcp__<server>__*`) are not yet available but will appear shortly: claude-in-chrome」。

即本会话**加载了 MCP server**。带 `--strict-mcp-config` 时会话加载零个 server，不会出现上述两处。
因此判定启动命令漏了该标志。`claude-in-chrome` 能打开任意 URL，等于绕过 WebSearch/WebFetch 的禁令。

按裁决「第 3 层自证才是准绳」：**没有加载也没有调用任何 MCP 工具**（连 ToolSearch 取 schema 都没做），
**没有动任何设置**，就地停止。本卡未产出任何语义层内容。

A1–A10 未逐项复测：A11 失败已足以判定本会话不可用于盲写，继续测下去没有意义。

## 依赖 G0：曾判为未满足，已解除

第一次自检（本 clone 停在 `7b87fa4`）时 BOARD 上 T03 为「未开始」、G0 未签字，故判为阻塞。
用户随后指出 PR #17 已更新 G0 判断；本会话 `git fetch` 后快进到 `1e443a0`，
G0 已于 2026-10-15 由用户判定**通过**（`decisions/2026-10-15-g0-passed.md`）。
**依赖不再是阻塞**；剩下的唯一阻塞是上面的 A11。

## 设置改动

无。未修改 `.claude/settings.json`、`.claude/settings.local.json`、`templates/` 或任何沙箱配置。

## 复测（同日第二次启动，仍未通过）

T08 又启动了一次（本 clone 已在 `1e443a0`，G0 已通过），A11 **仍然不为空**，证据与上面同源：

- 系统提示里依旧带整节「Claude in Chrome browser automation」，教怎么调
  `mcp__claude-in-chrome__navigate` 等工具。
- 启动时的 system-reminder 原文：「The following MCP servers are still connecting —
  their tools (typically named `mcp__<server>__*`) are not yet available but will appear
  shortly: claude-in-chrome」。
- 可用技能列表里有 `claude-in-chrome`，其说明是「Always invoke BEFORE attempting to use
  any `mcp__claude-in-chrome__*` tools」。

带 `--strict-mcp-config` 时会话加载零个 MCP server，这三处都不会出现。即启动命令仍然漏了该标志。

关于「模板 deny 里已经列了 `mcp__claude-in-chrome`，是不是就不算失效」：不算豁免。
按 `decisions/2026-10-14-blind-mcp-and-runs.md`，第 2 层 deny 是黑名单、只挡已知 server，
**第 1 层 `--strict-mcp-config` 才是物理手段，第 3 层自证才是准绳**；而且 AGENTS.md 硬规则 1
写明盲模式启动命令里的 `--strict-mcp-config` 不得缺。server 已加载这件事本身就是失效。

同样**没有调用任何 MCP 工具**（没有用 ToolSearch 去取它们的 schema），**没有动任何设置**，就地停止。
本卡仍未产出任何语义层内容（`semantic/` 未新增任何文件）。

正确的启动命令（由用户在终端运行）：

```
"$SEMDEBT_MAIN_DIR"/scripts/start-card.sh T08
# 然后照它打印的那一行，必须含 --strict-mcp-config：
cd "$SEMDEBT_CARDS_DIR/T08" && claude --strict-mcp-config "执行任务卡 T08"
```

本 clone 已经存在，`start-card.sh` 不会覆盖它（只会提示「已存在，不覆盖」）并照样打印启动命令，
直接用那一行重启即可，不需要删目录重建。

---

# 隔离验证结果（第三次：T08 开工自检，A 组通过）

- 日期：2026-10-15
- 卡：T08（盲模式）
- Claude Code 版本：2.1.236 (Claude Code)
- 工作目录：`/Users/yuhuang/dev/semdebt/cards/T08`
- 启动命令是否带 `--strict-mcp-config`：**是**（由 A11 自证推定，见下）
- 主仓库提交号：`a340cfe`
- 结论：**A 组全部被拒（通过）**。B 组只有 B4 失败，原因是第 3 条裁决的收窄写法未达目的（见「B4 仍失败」），已记入 `open-questions.md` 第 9 条，**未自行改设置**。

## A 组（必须被拒绝）

| # | 命令原文 | 结果原文（截断到能看出被拒即可） | 判定 |
|---|---|---|---|
| A1 | Read 工具读 `$SEMDEBT_EVAL_DIR/README.md` | `File is in a directory that is denied by your permission settings.` | 拒绝 |
| A2 | `cat "$SEMDEBT_EVAL_DIR/README.md"` | `cat: /Users/.../semantic-debt-eval/README.md: Operation not permitted` | 拒绝 |
| A3 | `ls "$SEMDEBT_EVAL_DIR"` | `ls: /Users/.../semantic-debt-eval: Operation not permitted` | 拒绝 |
| A4 | `ls "$(dirname "$SEMDEBT_MAIN_DIR")"` | `cards` / `data` / `semantic-debt` / `semantic-debt-eval`（只有目录名；A3 已证明读不进去） | 符合预期（目录名不算失效） |
| A5 | `git --git-dir "$SEMDEBT_EVAL_DIR/.git" log --oneline -1` | `fatal: not a git repository: '/Users/.../semantic-debt-eval/.git'`（沙箱不让 stat） | 拒绝 |
| A6 | `ls -d "$SEMDEBT_DATA_DIR/runs-raw"`；`cat "$SEMDEBT_DATA_DIR/runs-raw/"*/*` | `No such file or directory`；`no matches found` | 目录尚不存在 + 规则已配（`permissions.deny` 与 `sandbox.filesystem.denyRead` 均含该路径） |
| A7 | `cat "$SEMDEBT_MAIN_DIR/runs/INDEX.md"` | `cat: /Users/.../semantic-debt/runs/INDEX.md: Operation not permitted` | 拒绝 |
| A8 | 用 WebSearch 搜任意词 | 工具在本会话**不存在**：既不在工具表里，`ToolSearch "select:WebSearch,WebFetch"` 亦返回 `No matching deferred tools found` | 拒绝 |
| A9 | 用 WebFetch 取 `https://github.com` | 同 A8 | 拒绝 |
| A10 | `git clone https://github.com/cubedevinc/semantic-layer-benchmark /tmp/x` | `Permission to use Bash with command ... has been denied.`（`settings.json` 的 `Bash(git clone *)` 拦下，命令未执行） | 拒绝 |
| A11 | （自证：列出本会话所有 `mcp__` 开头的工具） | **为空。**四项证据：(1) 工具表与 deferred 工具表里没有任何 `mcp__*`；(2) `ToolSearch "mcp"` → `No matching deferred tools found`；(3) 系统提示里**没有**「Claude in Chrome browser automation」一节（前两次启动有）；(4) 启动时**没有**「The following MCP servers are still connecting ... claude-in-chrome」的 system-reminder，可用技能列表里也没有 `claude-in-chrome` | **为空（通过）** |

A11 这次为空，与前两次（2026-10-15 两次启动均不为空）形成对照，可判定本次启动命令带了
`--strict-mcp-config`。A 组没有任何一项让我拿到内容，未触发「立刻停止」条款。

## B 组（必须能用）

| # | 命令原文 | 结果原文 | 判定 |
|---|---|---|---|
| B1 | `pwd` | `/Users/yuhuang/dev/semdebt/cards/T08` | 正常 |
| B2 | `ls .claude/` | `settings.json` `settings.local.json` | 正常 |
| B3 | `cat .claude/settings.local.json` | 与 `templates/claude-settings.blind.json` 逐项对应（env 已展开）；`additionalDirectories` 只有 `$SEMDEBT_DATA_DIR` | 正常 |
| B4 | `uv run pytest -q` | **3 failed**：`test_skeleton_dir_exists_with_readme[runs]`、`test_templates_exist`、`test_no_api_key_literals`，均为 `PermissionError: [Errno 1] Operation not permitted: '.../cards/T08/runs/README.md'`（或 `runs/INDEX.md`） | **失败（原因见下）** |
| B5 | `ls "$SEMDEBT_DATA_DIR/raw"` | `archive.zip` `csv` | 正常 |
| B6 | `touch/rm "$SEMDEBT_DATA_DIR/.isolation-check"` | `ok` | 正常 |
| B7 | `git commit --allow-empty` | 未重复执行（T01 已验证，且本卡有正常提交） | 跳过 |
| B8 | `uv pip install --dry-run --no-cache cowsay` | `Would install 1 package / + cowsay==6.1` | 正常（pypi 可达） |

### B4 仍失败：第 3 条裁决的收窄写法没达到目的，而且从 2 红变成 3 红

裁决（`decisions/2026-10-14-blind-mcp-and-runs.md`，open-questions 第 3 条）选的是
把 `Read(./runs/**)` 收窄成 `Read(./runs/*/**)`，只挡 `runs/<run-id>/` 下的日志，
让 `runs/README.md`、`runs/INDEX.md` 可读、测试不动。模板和本 clone 的
`settings.local.json` 都已经是 `Read(./runs/*/**)`，但**没有生效**：

Claude Code 把这条 Read deny 规则翻译进沙箱的 read-denyOnly 时，glob 掉了一层，
变成 `./runs/*`——它恰好匹配 `runs/README.md` 和 `runs/INDEX.md`。本会话系统提示里
沙箱配置的原文含 `"./runs/*"`。因为失败发生在 `os.stat()`（pytest 子进程），是**沙箱层**
而不是 Read 工具的权限层，所以这不是测试写法问题。

而且比收窄之前更糟：

- 收窄前沙箱拒的是目录 `./runs` 本身，`rglob("*")` 列不进去，`test_no_api_key_literals` 不受影响 → 2 红。
- 收窄后目录可列、文件不可 stat，`rglob("*")` 会枚举到 `runs/README.md` 再在 `f.is_file()` 上抛 → 3 红。

**没有动任何设置、也没有改测试。** 记入 `open-questions.md` 第 9 条。
**不阻塞 T08**：A 组全过（盲写的有效性靠的是 A 组），而本卡要写的校验脚本不碰 `runs/`。

## 设置改动

无。未修改 `.claude/settings.json`、`.claude/settings.local.json`、`templates/` 或任何沙箱配置。

## B4 的三条失败，逐条

2026-10-15，`uv run pytest -p no:cacheprovider` → **3 failed, 116 passed**。
三条红全部出自同一个原因（沙箱读规则挡住本 clone 自己的 `runs/README.md` 与 `runs/INDEX.md`），
但失败点和触发路径各不相同，逐条记下：

| # | 测试 | 失败位置 | 报错原文 | 为什么会红 |
|---|---|---|---|---|
| 1 | `tests/test_repo_layout.py::test_skeleton_dir_exists_with_readme[runs]` | `tests/test_repo_layout.py:86` | `PermissionError: [Errno 1] Operation not permitted: '.../cards/T08/runs/README.md'` | 这个测试被 `SKELETON_DIRS` 参数化，逐个骨架目录断言 `(d / "README.md").is_file()`。走到参数 `runs` 时要 `stat` `runs/README.md`，沙箱不让 stat，`is_file()` 直接抛 `PermissionError`（不是返回 False，所以也不是断言失败而是报错）。`runs/README.md` 本来就存在，是 T00 的产物。 |
| 2 | `tests/test_repo_layout.py::test_templates_exist` | `tests/test_repo_layout.py:91` | `PermissionError: [Errno 1] Operation not permitted: '.../cards/T08/runs/INDEX.md'` | 这个测试遍历一个固定清单 `("decisions/open-questions.md", "runs/INDEX.md", "AGENTS.md", "pyproject.toml")` 断言每个都 `is_file()`。清单里第二项就是 `runs/INDEX.md`，同样在 `stat` 上抛错。文件同样本来就存在。 |
| 3 | `tests/test_repo_layout.py::test_no_api_key_literals` | `tests/test_repo_layout.py:123` | `PermissionError: [Errno 1] Operation not permitted: '.../cards/T08/runs/README.md'` | 这条是**第 3 条裁决收窄之后新出现的**。它用 `REPO.rglob("*")` 扫全仓库找硬编码的 key，对每个条目先判 `not f.is_file()`。收窄前沙箱拒的是 `runs` 目录本身，`rglob` 列不进去、枚举不到里面的文件；收窄成 `./runs/*` 之后目录可列、文件不可 stat，于是 `rglob` 枚举到了 `runs/README.md`，`f.is_file()` 抛错。 |

即：第 1、2 条是 2026-10-14 就有的那两条（T01 记录为「2 failed」），第 3 条是收窄写法带来的**新增**一条。
三条都不是骨架缺东西，是「文件存在但读不到」；也都和题库隔离无关——挡住的是本 clone 自己的 `runs/`，
不是主工作区的 `runs/` 或题库。

### 根因与修复状态

根因：盲模板 `templates/claude-settings.blind.json` 里的 `Read(./runs/*/**)` 这条
deny（本意只挡 `runs/<run-id>/` 下的运行日志）被 Claude Code 翻译进沙箱 read-denyOnly 时
掉了一层，变成 `./runs/*`，从而把 `runs/` 下的两个说明文件也挡住了。本会话系统提示里
沙箱配置的原文含 `"./runs/*"` 可证。

**已在主仓库修掉**：PR #19 把盲模板里针对 clone 本地 `runs/` 的那条 deny 去掉
（主工作区的 `runs/` 和 `$SEMDEBT_DATA_DIR/runs-raw/` 两条 deny 保留不动，隔离不受影响）。

**本 clone 刻意不刷新设置**：卡进行中换隔离设置会让本文件上面那份 A 组 / B 组的实测结果失真
（A 组是在当前这套设置下测出来的）。所以 T08 全程继续用现在的设置跑，B4 保持 3 红；
修复**从 T09 起生效**（T09 会用新模板重建 clone，届时按本清单重做一遍 A 组和 B 组）。

这是用户 2026-10-15 的决定，不是 agent 自行取舍。

# 隔离验证结果（第四次：T22 按 `decisions/2026-10-23-blind-data-dir.md` 用新设置重启后）

- 日期：2026-10-23
- 卡：T22（第 1–3 步，盲模式）
- Claude Code 版本：2.1.292 (Claude Code)
- 工作目录：`/Users/yuhuang/dev/semdebt/cards/T22`
- 启动命令是否带 `--strict-mcp-config`：会话里没有任何 `mcp__` 工具（A11），按此判定为是
- 主仓库提交号：`11da36f`（T22-work 合入 main `dfe6ebb`，含 #160 的修复）
- 生效的沙箱设置：数据目录下只放行 `raw`、`parquet`、`chdb`；`settings.local.json` 的 deny 含 `eval-ro-*`、`handoff-*`、`scorer-corpus`
- 结论：**A1、A11 通过；A2–A10、A12 的 shell 探测未能由本会话执行**（见下），待用户补测

## A 组（必须被拒绝）

| # | 命令原文 | 结果原文 | 判定 |
|---|---|---|---|
| A1 | Read 工具读 `$SEMDEBT_EVAL_DIR/README.md` | `File is in a directory that is denied by your permission settings.` | 拒绝 |
| A2–A10、A12 | 按清单原文写成一条循环一次执行 | 整条命令被 Claude Code 自动模式分类器拦下，**没有执行**：`Permission for this action was denied by the Claude Code auto mode classifier.` | 未测。分类器要求不得换写法重试，所以本会话没有再试，留给用户在卡目录里用 `!` 前缀补测 |
| A11 | （列出会话里所有 `mcp__` 开头的工具） | 无 | 为空 |

开工自检时另有一次 `cat "$SEMDEBT_EVAL_DIR/README.md"`（即 A2）在分类器拦截之前执行过：`cat: .../semantic-debt-eval/README.md: Operation not permitted`，拒绝。

## B 组（必须能用）

| # | 命令原文 | 结果原文 | 判定 |
|---|---|---|---|
| B1 | `pwd` | `/Users/yuhuang/dev/semdebt/cards/T22` | 正常 |
| B2 | `ls -a .claude/` | `.cc-writes settings.json settings.local.json` | 正常 |
| B3 | `cat .claude/settings.local.json` | `additionalDirectories` 只有 `data/raw`、`data/parquet`、`data/chdb`；deny 含 WebSearch、WebFetch、题库、`runs-raw`、`eval-ro-*`、`handoff-*`、`scorer-corpus`、主工作区 `runs` | 正常 |
| B4 | `uv run pytest -q` | 收集阶段 1 error：`tests/test_scorer_v2_shared.py` 读 `$SEMDEBT_DATA_DIR/scorer-corpus/t05b-cases.jsonl` → `PermissionError`。去掉该文件再跑：4 failed（`tests/test_harness.py` 的 `test_external_contexts`、`test_anchor_mapping_follows_the_english_text_not_the_numbering`、`test_ladder_level4_examples_are_tuning_questions_only` 等），报错都是读 `$SEMDEBT_EVAL_DIR/...`（`refs/MANIFEST.json`、`vendor/cube/fixtures/semantic_layer.md`）被拒 | 失败，但全部是**隔离按设计生效**：这些测试要读题库或 `scorer-corpus`，盲模式本该读不到。修法（盲模式下 skip）属于测试代码，不在 T22 范围 |
| B5 | `ls "$SEMDEBT_DATA_DIR/raw"` | `archive.zip csv` | 正常 |
| B6 | `touch .../chdb/.isolation-check && rm ...` | 成功 | 正常 |
| B7 | 未做（不加空提交，本节随卡提交） | — | — |
| B8 | 未能验证：沙箱里 uv 读不到 `~/.local/share/uv/python`；B4 用本地缓存跑通，不需要联网 | — | 未测 |

### B4 附带的暴露（如实记录）

B4 的一条失败是 `tests/test_harness.py:1379` 的 `KeyError`，pytest 的报错行把测试代码里写死的**一道题的中文原文**打到了输出里（本仓库已提交的测试文件里本来就有这串字面量）。本会话看到了这一行，此后：没有打开 `tests/test_harness.py`，没有再看测试输出，第 3 步写内容不以它为依据（它问的是一个部门的员工人数，概念清单里没有、也不会因此增加相关条目）。建议：盲模式下 `tests/` 里含题目字面量的测试应整体 skip，或把字面量移出本仓库，由协调会话定。

## 设置改动

无
