# templates

`scripts/start-card.sh` 用这里的模板生成每张卡 clone 里的 `.claude/settings.local.json`，把 `${...}` 换成绝对路径：

| 占位符 | 含义 |
|---|---|
| `${SEMDEBT_DATA_DIR}` | 数据目录，默认 `~/semdebt/data` |
| `${SEMDEBT_EVAL_DIR}` | 题库仓库，默认 `~/semdebt/semantic-debt-eval` |
| `${SEMDEBT_MAIN_DIR}` | 主工作区，默认 `~/semdebt/semantic-debt` |

- `claude-settings.blind.json`：盲模式。放行数据目录；禁止读题库、`runs-raw/` 和主工作区的 `runs/`；禁止网页搜索和抓取。与仓库提交的 `.claude/settings.json`（打开沙箱、禁止读取工作目录以外的文件）叠加生效。
- `claude-settings.open.json`：普通模式，只能在 G1 之后用。放行数据目录和题库。

权限规则里 `Read(/...)` 的写法：占位符展开后是以 `/` 开头的绝对路径，前面再加一个 `/`，就成了 Claude Code 规则要求的 `//绝对路径`。

改模板要开 PR、写进 `decisions/`，并重新做 T00 的隔离验证。
