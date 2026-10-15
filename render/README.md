# render

把 `semantic/` 的源文件渲染成各单元的上下文和各栈的模型定义。产物写到 `build/`（不入库，可重建）。

一条原则：所有自建单元读**同一种结构**的语义上下文 YAML，档位之间只差内容，不差格式。

脚本（`build_l0.py` 已由 T09 完成，其余计划在 T10）：

| 脚本 | 输入 | 输出 |
|---|---|---|
| `build_l0.py`（T09，已有） | `semantic/l0_map.yaml` | `render/l0_views.sql`（入库）、chDB 库 `l0` 的 25 个视图、`reports/validation/l0.md` |
| `render_context.py` | `semantic/source.yaml`、`semantic/l0_map.yaml`、`semantic/conventions.md` | `build/context/<单元>.yaml`（L0、R、L1、L1.5W、L1.5S、L2、各调优档） |
| `render_cube.py` | `semantic/metrics.yaml` | `build/cube/`（Cube 模型，T16 用） |
| `render_tmdl.py` | `semantic/metrics.yaml` | `build/tmdl/`（Power BI，T17 用） |

渲染器在 `semantic-v1` 冻结范围内：tag 打上后不得再改（硬规则 2）。
