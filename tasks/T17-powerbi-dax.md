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

- 产出：
- 偏离与理由：
- 工时：
