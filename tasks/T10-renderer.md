# T10 渲染器

- 状态：已完成（2026-10-16，PR 待合并；G1 待用户确认）
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
  - 复现：`uv run python render/render_all.py`（不需要数据目录：上下文 → Cube 模型 → PBIP → 等价校验 → token 报告）；`uv run python render/verify_cube.py`（Cube 指标的 SQL 在 chDB 上核对）；`uv run pytest tests/test_render.py`。
  - `render/context.py` → `build/contexts/` 的 10 份上下文：SQL-R、SQL-L0、SQL-L1、SQL-L1.5W、SQL-L1.5S、SQL-L2（Cube SQL 接口）、JSON-L2、DAX-L0、DAX-L1、DAX-L2；调优档 SQL-L1-tuned、DAX-L2-tuned 在 `semantic/tuning/` 有文件后自动合并（合并规则见 `render/README.md`）。
  - **L0 / R 泄漏校验**（用户 2026-10-16 追加的要求）：渲染时就跑，失败抛错、不写文件。L0 不得出现 retail / dwd / ads 任何表名或列名、不得有中文、键只许 name / type / from / to；R 只许 retail 的名字、无描述无关系。测试逐条注入泄漏确认会失败；DAX-L0 的 PBIP 在 Power Query 改名步骤之外也不出现原名。
  - `render/syntax/` 四段语法说明，去空白后 895 ~ 952 字，相差 6.4%；测试确认不含本数据集的任何表名、列名、指标名和年份。
  - `render/cube.py` → 25 个 cube、92 个公开指标；`render/tmdl.py` → `build/pbip/retail-{L0,L1,L2}`；指标实现集中在 `render/measures.py`。
  - `render/check_equivalence.py`：L0、L1 的 SQL 与 DAX，L2 的 Cube SQL、JSON、DAX 三者，换掉物理名和调用名后逐字段一致；调用名与 `metrics.yaml` 对得上；L2 去掉调用名等于 L1；Cube 单元不残留原表名。**通过。**
  - `reports/validation/context_sizes.md`（token 数）、`reports/validation/cube_measures.md`（26 项与 `source.yaml` 记录的全量值比对、7 项与源表直接查询比对、88 个非多阶段指标全部能执行：**全部通过**）。
  - `render/physical_schema.json`：retail / dwd / ads / l0 的表名、列名、类型快照（没有数据行），由 `render/snapshot_schema.py` 从 chDB 生成，渲染不再依赖数据目录，类型也随 `semantic-v1` 一起冻结。
  - **T10-1 裁决落地**（`decisions/2026-10-15-dual-dataset-metric-callables.md`）：`metrics.yaml` 的 23 个双表指标补了 `alternate_dax_measure` / `alternate_cube_member`，主调用名改指默认表所在的 cube；`validate.py` 第 4 项加了校验（全量 3,053 项通过）。
- 偏离与理由：
  - 文件名按任务卡（`render/context.py`、`build/contexts/`），不按旧 `render/README.md` 里计划的 `render_context.py`、`build/context/`；README 已改。
  - 上下文去掉了两样非内容的东西：`data_quality` 的 `open_question`（指向本仓库的流程编号）；L1.5S 不带 `conventions` 的 note 与落点、指标的 `dataset` / `expression`（都指向 L1.5S 看不到的明细表）。L1.5S 里汇总表与维度视图的列描述直接取自 T08 写的 `summary.yaml` / 宽表描述，其中有几处文字提到明细表名（如「经 DimStore.EmployeeKey → DimEmployee 取得」），属于血缘说明，没有改写。
  - L1.5S 没有「关系」节：汇总表全部反范式化，没有可连接的键，`summary.yaml` 也没有写关系。
  - Cube 的 SQL-L2 / JSON-L2 上下文里表名换成 cube 名（`FactSales` → `sales` 等），描述文字里提到的表名一起换；列名保持 ClickHouse 原样（大小写敏感，语法说明里写了加双引号）。`DimDate` 的 cube 叫 `calendar`（DATE 是 Postgres 关键字）。
  - 执行端与上下文不同的地方（引擎能力，不是信息量差别）全部列在 `render/README.md` 的表里：DAX 两条非激活关系、自连接建不了、默认预算场景 DAX 跟随筛选而 Cube 固定、环比 Cube 固定按月、新客 Cube 只看窗口内有交易的客户、Cube 的同比 / 环比 / 占比 / 同店增长率是多阶段指标（未在 chDB 核对，留给 T16）、库存周转率和目标达成率在 Cube 里用 UNION ALL 拼表实现（已核对没有混入）。
  - PBIP 的描述、同义词、AI instructions 的存放位置按公开文档的 PBIP 格式写（`///` 描述、`cultures/zh-CN.tmdl` 的 linguisticMetadata、`Copilot/Instructions/instructions.md`），**没有在 Desktop 上核对**，按卡片由 T17 核对。第一期 DAX 单元读的是 YAML 上下文，这几处只影响模型自带的元数据，不影响实验输入。
  - DAX-L0 的 PBIP 用 Power Query 把原列名改成 L0 名，分区的 M 表达式里因此有原名；DAX 查询理论上能用 `INFO.PARTITIONS()` 读到。已记入 `render/README.md`，留给 T17。
  - 发现：L1 上下文约 4 万 token，是设计费用假设（1 万）的 4 倍 → `decisions/open-questions.md` T10-2，不阻塞。
  - 本会话因用量上限中断过一次，之后在同一 clone 续做。
- 工时：约 6 小时（agent）
