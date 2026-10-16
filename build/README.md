# build

渲染产物。**不入库，可重建**——`.gitignore` 只放行本文件。

重建命令：`uv run python render/render_all.py`，见 `render/README.md`。

子目录：`contexts/`（各单元的语义上下文 YAML）、`cube/model/cubes/`（Cube 模型，T16 用）、`pbip/`（Power BI 的 L0 / L1 / L2 三个 PBIP，T17 用）、`tuning-packet/`（T14 的调优包，`start-card.sh T14-B` 从这里取）。
