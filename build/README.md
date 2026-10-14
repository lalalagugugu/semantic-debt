# build

渲染产物。**不入库，可重建**——`.gitignore` 只放行本文件。

重建命令（T10 之后）：`uv run python -m render.render_context` 等，见 `render/README.md`。

子目录：`context/`（各单元的语义上下文 YAML）、`cube/`、`tmdl/`、`tuning-packet/`（T14 的调优包，`start-card.sh T14-B` 从这里取）。
