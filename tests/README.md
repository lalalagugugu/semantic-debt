# tests

`uv run pytest`。测的是仓库自身的约定（目录骨架、`cards.yaml` 与 `BOARD.md` 一致、模板是合法 JSON、`start-card.sh` 语法与解析正确），不测模型输出。

`test_repo_layout.py` 里的 cards.yaml 解析器是 `start-card.sh` 里 bash 解析器的**独立实现**，两者的输出互相比对——改了一边、忘了另一边，测试会红。
