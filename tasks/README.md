# tasks

| 文件 | 给谁看 |
|---|---|
| `BOARD.md` | 人。总览：负责方、模式、依赖、预算上限、状态 |
| `cards.yaml` | 机器。`scripts/start-card.sh` 和 agent 的开工自检读它；**与 BOARD 不一致时以它为准**，并修正 BOARD |
| `Txx-*.md` | 做这张卡的 agent 或用户。目标、交付物、验收、不能做、用户确认、记录 |

题库侧的卡（T01a、T03–T06、T05b）在题库仓库的 `tasks/`，本仓库没有副本。

每完成一张卡：在卡末尾填「状态 / 产出 / 偏离与理由 / 工时」，更新 `BOARD.md` 的状态列，推分支开 PR。只做卡里写的事；发现设计层面的问题先记进 `decisions/open-questions.md` 再问用户。
