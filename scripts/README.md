# scripts

| 文件 | 作用 |
|---|---|
| `start-card.sh <卡号> [调优包]` | 按 `tasks/cards.yaml` 为一张卡准备工作目录和设置，打印启动命令。由**用户在终端**运行，不在 agent 会话里运行 |
| `verify-isolation.md` | 盲模式隔离验证清单，由 T01 第一步执行，结果写进 `decisions/isolation-check.md` |

`start-card.sh` 只通过 `SEMDEBT_MAIN_DIR`、`SEMDEBT_EVAL_DIR`、`SEMDEBT_DATA_DIR` 找路径；卡片目录默认是主工作区的同级 `cards/`，可用 `SEMDEBT_CARDS_DIR` 覆盖。
