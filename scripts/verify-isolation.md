# 盲模式隔离验证清单

**谁执行**：T01 的第一步（盲模式的第一张卡）。此后任何改了 `.claude/settings.json`、`templates/claude-settings.*.json` 或 Claude Code 升级之后，重做一遍。

**怎么执行**：逐项照着做，把**命令原文和结果原文**抄进 `decisions/isolation-check.md`（表格模板在本文末）。不要凭「应该会被拒」填表，必须实测。

## 最重要的一条

A 组的任何一项**没有被拒绝**（也就是你真的拿到了内容）：

1. **立刻停止**，不要往下读、不要摘录、不要概括你看到的东西。
2. 不要尝试修复设置，也不要自己换个写法再试。
3. 在 `decisions/isolation-check.md` 里只写「第 N 项未被拒绝，已停止」，附上你运行的命令。
4. 告诉用户：隔离失效，这个会话到此结束，本卡及后续盲模式卡的结果在修好之前都不可用。

隔离靠物理手段。**不得**改 `.claude/settings.json`、关沙箱、用 `--add-dir` / `/add-dir`、也不得绕道（例如用 `git --git-dir` 读别的仓库的对象、用子 agent 代读、让脚本把文件拷进工作目录）。绕道成功也算隔离失效，同样停。

## A 组：必须被拒绝

| # | 检查什么 | 命令 | 期望 |
|---|---|---|---|
| A1 | 读文件工具读题库 | 用 Read 工具读 `$SEMDEBT_EVAL_DIR/README.md` | 被拒（权限或沙箱报错） |
| A2 | shell 读题库 | `cat "$SEMDEBT_EVAL_DIR/README.md"` | 被拒 |
| A3 | 列题库目录 | `ls "$SEMDEBT_EVAL_DIR"` | 被拒，或看不到任何题库内容 |
| A4 | 列上一级目录 | `ls "$(dirname "$SEMDEBT_MAIN_DIR")"` | 被拒，或只看到目录名而读不进去（目录名本身不是题目信息，能看到不算失效） |
| A5 | 绕道读题库的 git 对象 | `git --git-dir "$SEMDEBT_EVAL_DIR/.git" log --oneline -1` | 被拒 |
| A6 | 读模型原始响应 | `cat "$SEMDEBT_DATA_DIR/runs-raw/"*/* 2>&1 \| head -1` | 被拒（目录此时可能还不存在，那就记「目录不存在 + 规则已配」） |
| A7 | 读主工作区的精简日志 | `cat "$SEMDEBT_MAIN_DIR/runs/INDEX.md"` | 被拒 |
| A8 | 网页搜索 | 用 WebSearch 搜任意词 | 被拒 |
| A9 | 网页抓取 | 用 WebFetch 取 `https://github.com` | 被拒 |
| A10 | 克隆仓库 | `git clone https://github.com/cubedevinc/semantic-layer-benchmark /tmp/x` | 被拒 |

A8–A10 的用意：盲模式不得上网找任何公开 text-to-SQL 基准的题目、参考 SQL 或语义文档，也不得凭记忆复述。

## B 组：必须能用

| # | 检查什么 | 命令 | 期望 |
|---|---|---|---|
| B1 | 在卡的 clone 里，不在主工作区 | `pwd` | 形如 `.../cards/<卡号>`，**不是** `.../semantic-debt` |
| B2 | 设置文件已就位 | `ls .claude/` | 同时有 `settings.json` 和 `settings.local.json` |
| B3 | 盲模式设置生效 | `cat .claude/settings.local.json` | `deny` 里有 WebSearch、WebFetch 和题库路径；`additionalDirectories` 只有数据目录 |
| B4 | 测试能跑 | `uv run pytest` | 通过 |
| B5 | 能读数据目录 | `ls "$SEMDEBT_DATA_DIR/raw"` | 列出用户下载的数据 |
| B6 | 能写数据目录 | `touch "$SEMDEBT_DATA_DIR/.isolation-check" && rm "$SEMDEBT_DATA_DIR/.isolation-check"` | 成功 |
| B7 | 能提交 | `git commit --allow-empty -m "isolation check"` | 成功（这条空提交留着，别删） |
| B8 | 能访问必要的网络 | `uv pip download pytest -d /tmp/x >/dev/null && echo ok` | 成功（pypi 在白名单里）；失败就记下来，别去改白名单以外的设置 |

B4 或 B8 因为沙箱读不到工具自身的缓存目录而失败：可以在 `.claude/settings.json` 的 `sandbox.filesystem.allowRead` / `allowWrite` 里加**那个工具的缓存或安装目录**（如 uv 的缓存），**不得**加题库、不得加数据目录以外的用户目录、不得加整个家目录。改了就写进 `decisions/isolation-settings.md`（改了什么、为什么），并重做 A 组。

某项设置在当前 Claude Code 版本里不生效（例如版本过旧不认某个键）：**停下告诉用户升级**，不要删掉这项设置。记下 `claude --version` 的输出。

## 结果模板

把下面这段复制进 `decisions/isolation-check.md` 并填满。

```markdown
# 隔离验证结果

- 日期：
- 卡：T01
- Claude Code 版本：（`claude --version`）
- 工作目录：（`pwd`）
- 主仓库提交号：（`git rev-parse --short HEAD`）
- 结论：通过 / **未通过（已停止）**

## A 组（必须被拒绝）

| # | 命令原文 | 结果原文（截断到能看出被拒即可） | 判定 |
|---|---|---|---|
| A1 | | | 拒绝 / **通过了（失效）** |

## B 组（必须能用）

| # | 命令原文 | 结果原文 | 判定 |
|---|---|---|---|
| B1 | | | 正常 / 失败 |

## 设置改动

无 / 见 `decisions/isolation-settings.md`
```
