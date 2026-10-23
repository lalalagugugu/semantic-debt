# T17 Power BI 模型与 DAX 执行器（Windows）

- 状态：未开始
- 负责：Claude Code（在 Windows 上）
- 模式：Windows
- 依赖：G1（`build/pbip/` 与上下文，T10）；DAX 冒烟需要 G3 选定的模型
- 预算：Flash 5 元 / Pro 15 元

## 目标

在 Windows 上把 L0、L1、L2 三个 Power BI 模型建起来，并让 harness 能对 Desktop 的本地引擎执行 DAX 查询。

## 开工前

1. 在 Windows 上克隆两个仓库（目录布局同 Mac，例如 `%USERPROFILE%\semdebt\`），设置同名环境变量；把 Mac 上 `$SEMDEBT_DATA_DIR/parquet/` 复制到 Windows 的数据目录。
2. 如果这台电脑上能用 Claude Code：在仓库里启动，执行本卡。注意 Windows 原生环境没有沙箱，所以这里只做 G1 之后的普通工作，不做任何盲任务。
3. 如果这台电脑上用不了 Claude Code（例如网络限制）：在 Mac 上用普通模式完成本卡的代码部分（执行器、脚本、`windows/README.md`），用户在 Windows 上 `git pull` 后按 README 运行，把输出贴回给 Mac 上的 agent。

## 做法

1. 先在 Desktop 里手动存一个最小 PBIP，核对 T10 生成的 TMDL 结构（尤其是描述、同义词和 AI instructions 的存放位置）；不一致就停下，按 `decisions/` 流程回到 T10 修渲染器（语义层已冻结，渲染器的修正要记录并重新生成 DAX 相关产物）。
2. 用 Parquet 导入数据，打开三个 PBIP 并刷新。逐表核对行数和若干合计（总线上销售额等），与 chDB 相差不超过 0.5%。
3. DAX 执行器：Python 通过 ADOMD.NET（如 pyadomd）连接 Desktop 打开模型后在本机启动的 Analysis Services 端口（端口号从 Desktop 的工作区目录读取）。一次只开一个模型，换单元时切换。
4. 为 harness 加 `dax` 执行器；DAX 语法说明用 T10 生成的那段。
5. 冒烟：最小样本 24 题 × 3 个单元（DAX-L0、DAX-L1、DAX-L2）× 1 次，只修 bug。

## 来自 T10 的交接（2026-10-16）

**一、DAX-L0 有一条残留泄漏路径，执行器必须堵。**

DAX-L0 的模型要在 Power Query 里重命名原始 Parquet 列，**所以原始列名存在于模型内部**。YAML 上下文永远不显示它们，但一条用 `INFO.PARTITIONS()`（以及其他 `INFO.*` 元数据函数）的 DAX 查询能读到——那样 L0「不知道列叫什么」这个前提就没了。

执行器**执行前静态拒绝**包含 `INFO.` 系列元数据函数的查询（拒绝，不是执行后过滤），记为 `exec_error` 并**单独归类**，T19 要能看见有多少次尝试。配一条测试。

**二、PBIP 里描述、同义词、AI 指令的落位未经验证。** T10 没有 Power BI Desktop，只能保证文件写出来了；本卡要在 Desktop 里确认它们真的被模型读到。

**三、DAX 与 Cube 在几处行为不同**（配额场景默认、环比位移、新客口径），已列在 `render/README.md`。这是两个引擎的限制，不是上下文差异——本卡遇到时照实记录，不要为了对齐两边而改任何一边的上下文。

## 交付物

- `windows/README.md`：从零复现的步骤（Desktop 版本、Python 依赖、端口发现方式）。
- 数据核对报告；执行器及测试；冒烟记录。

## 验收

- 三个模型的核对通过。
- 冒烟无执行器类错误（DAX 语法错误属于被测现象，不算）。

## 不能做

- 不要用公司的 Power BI 租户或 Fabric 做这个实验。
- 不要在 Desktop 界面里手改模型；所有改动回到渲染器。

## 记录（完成后填写）

### Mac 侧准备（T17-mac，2026-10-23，普通模式，未调用 DeepSeek）

- 状态：Mac 侧完成，待用户审 PR、决定是否打 `semantic-v1.5`；Windows 上的探测、冒烟待做（用户准备电脑）。
- 产出：
  - DAX 执行器 `harness/executors.py`（`DaxExecutor`）：pyadomd 建连接、`AdomdCommand` 执行，端口从 Desktop 工作区目录自动发现（只认能连上的那一个，多于一个拒绝）；执行前静态拒绝 `INFO.` 系列与 `$SYSTEM`，归类 `metadata_function`；只允许一条以 `EVALUATE`/`DEFINE` 开头的查询；开跑前用 DMV 核对 Desktop 里打开的就是该档位的模型。`harness/cells.py` 注册 DAX-L0/L1/L2（不进 `--cell all`），`run_direct` 一次只许一个 DAX 单元。测试 `tests/test_dax_executor.py`（模拟会话与 .NET 值）。
  - 探测模式 `harness/dax_probe.py`：逐表行数 25、合计与去重 20、孤儿行 5 条关系 × 2 种数法（单独一段）、L2 度量值 35、v1.4 变体 10、L1 的 2 级写法条目 30 条查询、度量值表达式比对；对照数字 `reports/validation/dax_probe_expected.json`，由 chDB 直接读 `$SEMDEBT_DATA_DIR/parquet/` 算出（不打开任何 chDB 数据目录，不会与 T14 冲突），孤儿行数与 `source.yaml` 逐条相等。
  - `windows/README.md`、`windows/t17.ps1`（探测、dry-run、冒烟、全量四个命令；冒烟、全量跑完自动打包 `runs/<id>/` 与 `runs-raw/<id>/`）；`scripts/t17_windows_bundle.py` 打 Windows 压缩包（parquet、占位数据目录的 PBIP、`MANIFEST.sha256`）。`pyproject.toml`：chDB 只在非 Windows 上装，新增 `windows` 依赖组（pyadomd、pythonnet）。
  - 检查清单第 1 项：`render/syntax/dax.md` 补到 2 级（`reports/validation/dax-syntax-t2.md`，18 条均未在真实引擎上验证，留给 Windows 探测）。第 3 项：YAML 上的三项通用检查本来就覆盖 DAX 且零缺口；新增 `render/check_pbip.py` 对照上下文与 PBIP，查出并修正两处（非激活关系与自连接看不出来、4 个外键类型），变体的 DAX 实现由探测在真实引擎上核对。见 `decisions/2026-10-23-t17-mac-dax-renderer.md`。
  - 第 2 项（DAX 对齐清单，Codex T16 #156，用户 2026-10-23 转交）：清单每一行落成通用探针，共 69 项（L2 探测的「对齐清单验收」一段），对照数字按清单写的参考读法由 chDB 算出，并给出其他读法的数字以判断引擎走的哪一种；度量值未改。读代码预判有 5 类会走非参考读法（场景默认值遇事实键分组、新客首购受事实日期列与切片影响、占比主成员去父组、渠道内占比按事实键分组、同店集合随子类重认定），等 Windows 结果后裁决（`decisions/open-questions.md` T17-1，`reports/validation/t17-dax-alignment-acceptance.md`）。
- 复现：`uv run python render/render_all.py`（含 `check_pbip`）；`uv run python harness/dax_probe.py expected`；`uv run pytest`；`uv run python scripts/t17_windows_bundle.py`。
- 偏离与理由：
  - 渲染器改动（关系标记、外键类型、关掉自动日期/时间）超出「只补说明」：是第 3 项检查查出的交付缺陷，不修则 DAX 单元在门店地理问题上会静默算错；只动 DAX 产物，逐文件与系统消息哈希核对过。
  - `tests/test_render.py::test_syntax_note_lengths` 去掉 ClickHouse 与 DAX 的 10% 等长核对：该测试的说明写明 DAX 补到 2 级时去掉（T12-4 已裁决）。
  - 依赖：`uv.lock` 只新增 pyadomd、pythonnet 及其依赖，其余版本不变。
- 工时：约半天。
- 产出（Windows）：
- 偏离与理由（Windows）：
- 工时（Windows）：
