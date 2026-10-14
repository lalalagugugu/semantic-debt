# T10 渲染器

- 状态：未开始
- 负责：Claude Code
- 模式：**盲**（`scripts/start-card.sh T10`；渲染器不需要题目）
- 依赖：T08、T09
- 预算：0

## 目标

把 `semantic/` 的源文件渲染成每个单元的语义上下文，以及 Cube 模型和 Power BI 的 PBIP（TMDL），保证同一档位下不同栈之间信息量完全相同。

## 交付物

1. `render/context.py`：为每个单元输出一份上下文（`build/contexts/<cell>.yaml` 或 `.txt`）：
   - R：只有表名、列名、类型（原始业务名），无描述、无关系。
   - L0：L0 名、类型、保留的关系、技术字段。
   - L1：`source.yaml` 的全部内容（不含 `widetables`、不含调用名）。
   - L1.5W：L1 加 `widetables` 节。
   - L1.5S：`summary.yaml` 的汇总表、`ads` 库里的维度表及其描述、枚举含义、同义词、约定、指标的文字口径；**不含**任何明细事实表。
   - L2：L1 加每个指标的调用名，**只出现本栈那一种**：DAX 写 `[度量值名]`，SQL 写 `MEASURE(数据集.成员)`，JSON 写成员名。
   - 调优档位：在对应档位上叠加 `semantic/tuning/<cell>.yaml`（由 T14、T18 产生，渲染器只负责合并）。
   - 各栈的物理名：SQL 用 ClickHouse 表名，DAX 用 Power BI 表名；两者保持一致，L0 用同一套缩写。
2. `render/syntax/`：ClickHouse SQL、Cube 的 Postgres 方言 + MEASURE()、DAX、Cube JSON 四段语法说明，字数相差不超过 10%。只写语法，不写任何与本数据集有关的提示。
3. `render/cube.py`：由 `metrics.yaml` 和 `source.yaml` 生成 Cube Core 的数据模型文件（`build/cube/model/`）。
4. `render/tmdl.py`：生成 Power BI 的 L0、L1、L2 三个 PBIP 项目（`build/pbip/`）：表和列来自 Parquet；L1 写描述、同义词，约定清单写进 AI instructions 对应的位置（格式以 Desktop 保存出来的 PBIP 为准，由 T17 在 Windows 上核对）；L2 加度量值。
5. `render/check_equivalence.py`：同一档位下 SQL 与 DAX 的上下文除物理名语法和调用名外完全一致。
6. `reports/validation/context_sizes.md`：每份上下文的 token 数。

## 验收

- 等价校验通过。
- 生成的 PBIP 能在 Power BI Desktop 打开（由 T17 确认，发现问题回到本卡修）。
- 用户确认后，在 G1 打 tag `semantic-v1`（覆盖 T08、T09、T10 的全部产出）。

## 不能做

- 渲染器不得包含任何题目相关的逻辑或文字。
- 不得读取 `$SEMDEBT_EVAL_DIR` 或 `runs/`。

## 用户确认

- [ ] G1：同意冻结语义层，打 tag `semantic-v1`。

## 记录（完成后填写）

- 产出：
- 偏离与理由：
- 工时：
