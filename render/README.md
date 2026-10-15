# render

把 `semantic/` 的源文件渲染成各单元的上下文和各栈的模型定义。产物写到 `build/`（不入库，可重建）。

一条原则：所有自建单元读**同一种结构**的语义上下文 YAML，档位之间只差内容，栈之间只差物理名的写法和指标的调用写法。

## 一条命令重建

```
uv run python render/render_all.py
```

依次：上下文（含 L0 / R 泄漏校验）→ Cube 模型 → 三个 PBIP → 等价校验 → token 报告，任何一步失败就停。不需要数据目录。

另外两步要读 chDB，单独跑（同一个数据目录不能被两个进程同时打开，硬规则 9）：

```
uv run python render/snapshot_schema.py   # dwd / ads / l0 的视图改动后，重拍类型快照
uv run python render/verify_cube.py       # Cube 指标的 SQL 在 chDB 上核对 → reports/validation/cube_measures.md
```

## 脚本

| 脚本 | 卡 | 输入 | 输出 |
|---|---|---|---|
| `build_l0.py` | T09 | `semantic/l0_map.yaml` | `render/l0_views.sql`、chDB 库 `l0`、`reports/validation/l0.md` |
| `build_widetables.py` / `build_summary.py` | T08 | `semantic/widetables.sql`、`semantic/summary/` | chDB 库 `dwd` / `ads` |
| `snapshot_schema.py` | T10 | chDB 的 retail / dwd / ads / l0 | `render/physical_schema.json`（入库：只有表名、列名、类型，没有数据行） |
| `common.py` | T10 | — | 读源文件；各栈的物理名（`Namer`）；cube 名 |
| `context.py` | T10 | `semantic/source.yaml`、`l0_map.yaml`、`summary/`、`tuning/` | `build/contexts/<单元>.yaml` |
| `syntax/*.md` | T10 | — | 四段语法说明：ClickHouse SQL、Cube SQL 接口、DAX、Cube JSON |
| `measures.py` | T10 | `semantic/metrics.yaml` | 每个调用名的 DAX 表达式与 Cube 指标定义 |
| `cube.py` | T10 | `source.yaml`、`metrics.yaml`、`measures.py` | `build/cube/model/cubes/*.yml`（T16 用） |
| `tmdl.py` | T10 | 同上 | `build/pbip/retail-{L0,L1,L2}/`（T17 用） |
| `check_equivalence.py` | T10 | `build/contexts/` | 等价校验，不通过退出码 1 |
| `context_sizes.py` | T10 | `build/contexts/`、`syntax/` | `reports/validation/context_sizes.md` |
| `verify_cube.py` | T10 | `build_model()`、chDB | `reports/validation/cube_measures.md` |

## 单元与上下文

| 文件 | 栈 | 档位 | 内容 |
|---|---|---|---|
| `SQL-R.yaml` | ClickHouse | R | 表名、列名、类型；无描述、无关系、无技术字段 |
| `SQL-L0.yaml` / `DAX-L0.yaml` | ClickHouse / DAX | L0 | L0 名、类型、保留的 32 条关系、技术字段；其余一概没有 |
| `SQL-L1.yaml` / `DAX-L1.yaml` | ClickHouse / DAX | L1 | `source.yaml` 除 `widetables` 外的全部；隐藏 `technical: true` 的列；`data_quality` 去掉 `open_question`（流程编号） |
| `SQL-L1.5W.yaml` | ClickHouse | L1.5W | L1 加 `widetables` 节（`dwd` 的 5 个视图，列带类型） |
| `SQL-L1.5S.yaml` | ClickHouse | L1.5S | `ads` 的 16 张汇总表与 9 个维度视图、约定（只留条文）、同义词（落点换成 `ads` 的列）、指标文字口径；没有明细事实表 |
| `SQL-L2.yaml` / `JSON-L2.yaml` / `DAX-L2.yaml` | Cube SQL / Cube JSON / DAX | L2 | L1 加每个指标的 `callables`，只出现本栈那一种写法 |
| `SQL-L1-tuned.yaml` / `DAX-L2-tuned.yaml` | — | 调优 | 底档加 `tuning:` 节，内容是 `semantic/tuning/SQL-L1.yaml` / `DAX-L2.yaml` 原样（只做物理名换写）；文件还不存在时跳过 |

探查 agent（-E）用对应直答单元的同一份上下文。L1c 与英文锚点用外部基准原样的文档，不经本渲染器。

**各栈的物理名**：ClickHouse 写 `库名.表名`、`库名.表名.列名`；DAX 写 `表名`、`表名[列名]`（Power BI 表名与 ClickHouse 表名相同，L0 用同一套缩写）；Cube 两种接口写 cube 名（`common.CUBE_NAMES`，例如 `FactSales` → `sales`）与 `cube名.列名`，并把描述文字里提到的表名一起换成 cube 名。类型按栈写：ClickHouse 原样、DAX 的 `int64 / double / string / dateTime / boolean`、Cube 的 `number / string / time / boolean`。

**调优文件的约定**（T14、T18 产出时照此写）：`semantic/tuning/<底档单元>.yaml`，任意 YAML 映射；渲染器只把它整体挂在 `tuning:` 下，不解释内容。

## 校验

- **L0 / R 泄漏校验**（`context.check_l0` / `check_r`，渲染时就跑，失败抛 `LeakError`、不写文件）：L0 上下文里不得出现 retail / dwd / ads 任何一个库的表名或列名，不得有任何中文（即任何描述），键只能是 `datasets / name / columns / type / relationships / from / to`；R 只能出现 retail 的名字，不得有描述与关系。`tests/test_render.py` 另外逐条注入泄漏，确认校验会失败；并检查 DAX-L0 的 PBIP 在 Power Query 改名步骤之外不出现原名。
- **等价校验**（`check_equivalence.py`）：L0、L1 上 SQL 与 DAX，L2 上 SQL（Cube）、JSON、DAX 三者，把物理名换成中性写法、调用名换成占位后逐字段相等；每个调用名的写法与 `metrics.yaml` 对得上；L2 去掉调用名后等于 L1；Cube 单元不残留原表名。它解析的是输出文件，不复用 `Namer`，所以渲染器的错误会表现为差异。
- **Cube 指标 SQL 核对**（`verify_cube.py`）：Cube 本身在 T16 才跑；这里把每个非多阶段指标按 Cube 对普通聚合的编法拼成 SQL，在 chDB 上执行，与 `source.yaml` 记录的全量值以及源表上的直接查询比对。

## 模型里与 YAML 上下文不同的地方（引擎能力，如实记录）

上下文三栈一致；下面这些是**执行端**的差别，来自 Power BI 和 Cube 能表达什么，不是信息量的差别。

| 项 | DAX（PBIP） | Cube |
|---|---|---|
| 地理双路径 | `DimStore.GeographyKey → DimGeography` 与 `DimMachine.StoreKey → DimStore` 设为非激活（同一路径只能一条激活），用 `USERELATIONSHIP` | 两条都定义为连接 |
| 父子自连接（科目、员工、实体） | 不能建成关系，留作普通列 | 不能自连接，留作普通维度 |
| Float64 外键（4 列） | Power Query 里转成 Int64，关系才合法 | 不需要 |
| 默认预算场景（目标销售额、目标销量、目标毛利、计划收入） | 查询没筛场景时取 Budget，筛了就按所筛 | 指标内部看不到查询的筛选，固定取 Budget |
| 销售额环比增长率 | 按上下文里的日期判断是月、季还是年，往前移一期 | `time_shift` 要固定间隔，固定移一个月（成员名本来就是 `*_mom_pct`） |
| 新客数 / 新客销售额 | 截止日 = 查询窗口最后一天（上限 2009-12-31），数窗口前 90 天内首次购买的所有客户 | 截止日相同，但只看得到窗口内有交易的客户 |
| 同比、环比、占比、同店增长率 | 时间智能函数，日期表已标记 | 多阶段指标（`multi_stage`、`time_shift`、`group_by`），需要开 Tesseract 规划器；未在 chDB 上核对，留给 T16 |
| 库存周转率、目标达成率（跨两张事实表） | 两张事实表经共同维度自然对齐 | `inventory`、`sales_quota` 两个 cube 的 SQL 是「本表 + 全渠道销售」的 UNION ALL，用标志列分开；所有库存 / 目标指标都筛标志列，`verify_cube.py` 核对过没有混入 |

另外：DAX-L0 的 PBIP 必须用 Power Query 把 Parquet 的原列名改成 L0 名，所以分区的 M 表达式里有原名。YAML 上下文里没有；但 DAX 查询理论上能用 `INFO.PARTITIONS()` 读到。T17 落地时留意。

## 冻结

渲染器在 `semantic-v1` 冻结范围内：tag 打上后不得再改（硬规则 2）。T16、T17 发现模型问题，回到本目录修，并走 `decisions/` 流程。
