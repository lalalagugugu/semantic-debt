# DAX 单元的交付检查：上下文与 Power BI 模型

- 生成：`uv run python render/check_pbip.py`（`render/render_all.py` 也会跑）。只读 `build/contexts/DAX-*.yaml` 与 `build/pbip/` 的 TMDL，不读题库，不连 Power BI，不调模型。
- 依据：`decisions/2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md` 第三节第 3 条（T17-mac）。YAML 上的三项通用检查（引用、约定覆盖、等价）已含 DAX 单元；本检查补上「上下文说的就是查询跑的那个模型」。
- 关系标记 `model_relationship`（只在 DAX 上下文）：`inactive` = 模型里是非激活关系，要用 `USERELATIONSHIP`；`none` = 自连接，模型里不是关系。

| 单元 | 表 | 列（隐藏） | 度量值 | 模型关系（非激活） | 上下文关系：激活 / 非激活 / 不是模型关系 | 问题 |
|---|---|---|---|---|---|---|
| DAX-L0 | 25 | 265（0） | 0 | 32（0） | 32 / 0 / 0 | 无 |
| DAX-L1 | 25 | 244（16） | 0 | 45（2） | 43 / 2 / 3 | 无 |
| DAX-L2 | 25 | 245（17） | 102 | 45（2） | 43 / 2 / 3 | 无 |

PBIP 能否被 Power BI Desktop 打开、描述与同义词是否被读到，静态检查管不到，留给 Windows 上的探测（`windows/README.md`）。
