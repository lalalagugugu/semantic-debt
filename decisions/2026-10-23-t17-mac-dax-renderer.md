# 2026-10-23 T17-mac：DAX 单元的渲染器修正与写法说明 2 级（待用户决定是否打 `semantic-v1.5`）

- 提出：Claude Code（T17-mac，普通模式），2026-10-23
- 状态：**待用户审定**。改动在 PR 里；语义层产物（DAX 的三份上下文、三个 PBIP 的 `model.tmdl`）有变化，是否打 `semantic-v1.5` 由用户决定。DAX 的 dry-run、冒烟、全量都按 `--semantic-tag semantic-v1.5` 校验，tag 打之前会拒绝开跑。
- 依据：`decisions/2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md` 第三节第 1、3 条；`decisions/2026-10-19-self-built-p-and-cube-notes.md` 第五节第 3 条；T10 交接（`tasks/T17-powerbi-dax.md`）；硬规则 2（渲染器在 `semantic-v1` 冻结范围内，修正要记录）。

## 一、为什么改：通用交付检查在 DAX 单元上「跑通」查出两处上下文与模型不符

引用检查、约定覆盖、等价校验三项在本卡开工前就已覆盖 DAX 单元，而且零缺口；但它们只读 YAML 上下文。DAX 的查询跑在 PBIP 上，所以本卡加了 `render/check_pbip.py`：解析渲染出的 TMDL，逐项对照 `DAX-L0/L1/L2.yaml`（表、列与类型、度量值、关系及其激活状态、激活关系有无歧义路径）。第一次运行查出：

1. **非激活关系与自连接在上下文里看不出来。** 模型里 `DimStore.GeographyKey → DimGeography`、`DimMachine.StoreKey → DimStore` 是非激活关系（同一路径只能一条激活，T10 记录在 `render/README.md`），三条父子自连接在模型里不是关系；DAX 上下文却把这 5 条和其他关系写得一模一样。按门店所在地分组时，模型照上下文写 `SUMMARIZECOLUMNS('DimGeography'[…], …)` 不会报错，每组得到同一个合计——静默算错，而且是因为我们没告诉它，不是因为它不会 DAX。
2. **4 个外键的类型不符。** Power Query 把 4 个 Float64 外键转成了 Int64（关系才合法，`KEY_CASTS`），DAX 上下文仍写 `double`。

## 二、改了什么（只改渲染器与 `render/syntax/dax.md`）

| 文件 | 改动 |
|---|---|
| `render/common.py` | 非激活关系集合（`DAX_INACTIVE`）、4 个转型外键（`DAX_KEY_CASTS`）从 `tmdl.py` 移到这里，上下文与 PBIP 共用一份；`dax_model_relationship()`；`Namer.type` 对这 4 列在 DAX 上写 `int64` |
| `render/context.py` | DAX 上下文的关系多一个键 `model_relationship`：`inactive`（2 条）或 `none`（3 条自连接）；激活关系不加。L0 保留的 32 条都是激活关系，L0 上下文只有那 4 列类型变了 |
| `render/tmdl.py` | 改用公共集合（PBIP 内容不变）；`model.tmdl` 加 `annotation __PBI_TimeIntelligenceEnabled = 0`，关掉 Desktop 的「自动日期/时间」——它会给每个日期列加一张隐藏日期表，即上下文没有的模型对象 |
| `render/check_equivalence.py` | 比较前去掉 DAX 专有的 `model_relationship`（它描述引擎，不是信息量；由 `check_pbip.py` 对着模型核对） |
| `render/check_pbip.py`（新）、`render/render_all.py` | DAX 交付检查，接进一条命令重建；结果 `reports/validation/pbip_check.md` |
| `render/syntax/dax.md` | 补到 2 级：关系那条补一句 `model_relationship` 的含义；新增「使用条件与禁忌」18 条。条目、来源与 Windows 上逐条核实的查询见 `reports/validation/dax-syntax-t2.md`。**这 18 条都没在真实引擎上验证过**，Windows 探测不符的，开跑前删掉或改窄 |

渲染后逐文件比对（开工时的 `build/` 对现在）：只有 `build/contexts/DAX-L0.yaml`、`DAX-L1.yaml`、`DAX-L2.yaml` 与三个 `model.tmdl` 变了；其余上下文、Cube 模型、PBIP 其余文件逐字节相同。系统消息哈希：SQL、Cube、C13 阶梯共 10 个单元不变，只有 DAX-L0/L1/L2 变（`222556c0285d → 07321b71f8d1`、`413e3a178101 → d78beba18f06`、`63fc5b3dfe93 → 6e0795dc4704`）。

## 三、对可比性的影响（报告要写）

- `model_relationship` 是 DAX 上下文独有的一点信息。它不是语义内容（SQL 可以沿任意路径连接，没有「非激活」这回事），而是告诉作答者这个模型的机械约束；不给它，DAX 单元在门店地理、机器所在门店两类问题上的错误就来自交付缺陷而不是语言。L0 不受影响（L0 没保留这几条关系）。
- 孤儿行照现状建模（不加未知成员、不修数据），DAX 与 SQL 两条线面对同一份数据。
- DAX 写法说明 2 级的来源是 DAX 通用行为；ClickHouse 2 级（C13）来自调优题上的报错。两者的「2 级」来源不同，跨栈比较时要说明。

## 四、待办

- 用户：审 PR；决定是否在合并后打 `semantic-v1.5`。
- Windows 探测（`windows/README.md`）：三档模型的数据核对、孤儿行、L2 度量值与 10 个变体、L1 的 2 级条目；结果贴回 Mac。
- 检查清单第 2 项（DAX 对齐清单，Codex T16，PR #156）：等用户转交后落进探测的验收。
