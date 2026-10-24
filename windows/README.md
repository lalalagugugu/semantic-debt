# T17 / T18 在 Windows 上怎么跑

Windows 上没有 Claude Code（`tasks/T17-powerbi-dax.md`「开工前」第 3 条）。代码都在 Mac 上写好（T17-mac），这台电脑只做四件事：**探测、dry-run、冒烟、全量**，入口都是 [`t17.ps1`](t17.ps1)。每一步的输出原样贴回给 Mac 上的 agent。

不要用公司的 Power BI 租户或 Fabric；不要在 Desktop 界面里手改模型（所有改动回到 Mac 上的渲染器）。

## 1. 要装的软件

| 软件 | 说明 |
|---|---|
| Power BI Desktop | 安装版或 Microsoft Store 版都行（端口发现两种目录都找）。记下版本号（帮助 → 关于），贴回给 Mac。如果打不开 `.pbip`：选项 → 预览功能，勾选「Power BI 项目 (.pbip) 保存选项」和「以 TMDL 格式存储语义模型」，重启 Desktop。 |
| ADOMD.NET 客户端库 | Microsoft Learn 上「Analysis Services 客户端库」页面的 ADOMD.NET（x64 MSI）。默认装到 `C:\Program Files\Microsoft.NET\ADOMD.NET\<版本号>\`，执行器自动找；装在别处就设 `SEMDEBT_ADOMD_DIR` 指向含 `Microsoft.AnalysisServices.AdomdClient.dll` 的目录。 |
| Git | 克隆时关掉换行转换：`git clone -c core.autocrlf=false …`，让文件与 Mac 逐字节相同。 |
| uv | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"`。Python 由 uv 装：`uv python install 3.12`。 |

Python 依赖：在主仓库目录里 `uv sync --group windows --python 3.12`。`windows` 组装 `pyadomd` 和 `pythonnet`；chDB 没有 Windows 版，`pyproject.toml` 里已限定只在非 Windows 上装（Windows 这边不需要它：参考答案从题库读）。

## 2. 两个仓库和环境变量

目录布局同 Mac（两个仓库是同级目录），例如：

```powershell
mkdir $HOME\semdebt; cd $HOME\semdebt
git clone -c core.autocrlf=false <主仓库地址> semantic-debt
git clone -c core.autocrlf=false <题库地址> semantic-debt-eval
cd semantic-debt; git checkout <Mac 上告诉你的分支或 main>; git fetch --tags
```

用户级环境变量（设置 → 系统 → 高级系统设置 → 环境变量，设完重开 PowerShell）：

| 变量 | 例子 | 说明 |
|---|---|---|
| `SEMDEBT_MAIN_DIR` | `C:\Users\<你>\semdebt\semantic-debt` | 主仓库 |
| `SEMDEBT_EVAL_DIR` | `C:\Users\<你>\semdebt\semantic-debt-eval` | 题库；harness 只认 `eval-v1.2` tag 的干净检出 |
| `SEMDEBT_DATA_DIR` | `C:\Users\<你>\semdebt\data` | 数据目录，在仓库之外 |
| `DEEPSEEK_API_KEY` | — | 只有冒烟和全量需要；只放环境变量，不写进任何文件 |
| `SEMDEBT_ADOMD_DIR` | 可选 | ADOMD.NET 不在默认位置时 |
| `SEMDEBT_PBI_PORT` | 可选 | 端口发现失败时手动指定（一般不需要） |

## 3. 要从 Mac 拷过来的东西

Mac 上 `uv run python scripts/t17_windows_bundle.py` 打出一个压缩包（路径和 sha256 由 Mac 上的 agent 告诉你），里面是：

- `parquet/`：25 个 Parquet（与 Mac 上 `$SEMDEBT_DATA_DIR/parquet/` 相同，探测的对照数字就从它们算出）；
- `pbip/retail-L0|L1|L2/`：三个 Power BI 项目（`build/pbip/`，数据目录参数留空，所以哈希不依赖机器）；
- `MANIFEST.sha256`：上面每个文件的哈希；`BUNDLE.txt`：打包时的提交号。

解压到 **`%SEMDEBT_DATA_DIR%\t17-bundle\`**（解压后应能看到 `t17-bundle\MANIFEST.sha256`）。主仓库要检出 `BUNDLE.txt` 写的那个提交，否则探测第一步会报「与本机仓库渲染出的不一致」。

## 4. 探测（不调模型）

一次只开一个模型。对 L0、L1、L2 各做一遍：

```powershell
cd $env:SEMDEBT_MAIN_DIR
powershell -ExecutionPolicy Bypass -File windows\t17.ps1 probe -Tier L1
```

它依次：

1. 重新渲染（`render/render_all.py`：上下文、PBIP、各项校验）；
2. 按 `MANIFEST.sha256` 校验压缩包，确认压缩包里的 PBIP 就是本机仓库渲染出的那份（只允许数据目录参数和路径分隔符不同）；
3. 第一次运行时把三个项目复制到 `%SEMDEBT_DATA_DIR%\t17-pbip-work\`，把数据目录参数填成 `t17-bundle\parquet` 的实际路径；已存在就不覆盖（要重建先删掉那个目录）；
4. 连接 Desktop 的本地引擎，跑全部检查。

**第一次**它会在第 4 步报「没有找到正在运行的 Power BI Desktop 本地引擎」，并打印要打开的文件。照做：用 Desktop 打开 `t17-pbip-work\retail-L1\retail-L1.pbip` → 主页 → 刷新（可能要确认隐私级别，选「忽略」或「公共」）→ 等刷新完（线上销售 1,262 万行，几分钟）→ 关掉其他 Desktop 窗口 → 再运行同一条命令。

端口怎么找到的：Desktop 为打开的模型在本机起一个 Analysis Services 实例，把端口写进 `%LOCALAPPDATA%\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces\AnalysisServicesWorkspace_*\Data\msmdsrv.port.txt`（Store 版在 `%USERPROFILE%\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces\`）。执行器只认能连上的那一个；能连上的多于一个就拒绝（开了多个模型）。

探测报告（纯文本，同时存到 `%SEMDEBT_DATA_DIR%\t17-probe\probe-<档位>-<时间>.txt`）包括：

| 段 | 内容 | 档位 |
|---|---|---|
| 连接 | 端口、模型核对（表、列、度量值与渲染出的 PBIP 逐一相同，不是就停） | 全部 |
| Desktop 实际载入的模型 | 自动日期表（应为 0）、描述（L1/L2 应有、L0 应无）、同义词、关系数与非激活数 | 全部 |
| 逐表行数 | 25 张表 | 全部 |
| 合计与去重计数 | 20 项（总线上销售额、全渠道销售额、订单数等） | 全部 |
| **孤儿行** | 5 条有孤儿行的关系（`semantic/source.yaml` 的 `orphan_rows`），按值数一遍、按关系的空白成员数一遍，**单独列出**。模型照现状建模，没有加「未知成员」行、没有修数据，这样 DAX 线与 SQL 线可比 | 全部 |
| 度量值 | 35 项：`source.yaml` 记录的全量值与 Cube 交叉核对的同一口径 | L2 |
| v1.4 变体 | 10 个变体度量值各在一个切片上（渠道内、品类内占比，按季环比，同店作基年，按查询场景） | L2 |
| 写法说明 2 级条目 | `render/syntax/dax.md` 里没在真实引擎上验证过的写法，各一条查询看引擎是否如说明所说（`reports/validation/dax-syntax-t2.md`）；外加执行器拒绝 `INFO.` | L1 |
| 对齐清单验收 | 检查清单第 2 项（Codex T16 #156）每一行的通用探针，69 项；不符时报告与哪种其他读法一致（`reports/validation/t17-dax-alignment-acceptance.md`） | L2 |
| 度量值表达式 | Desktop 载入的表达式与渲染器写的是否逐个相同 | L2 |

对照数字在仓库里：`reports/validation/dax_probe_expected.json`，由 Mac 上 `uv run python harness/dax_probe.py expected` 用 chDB 直接读同一批 Parquet 算出。容差 0.5%。

另外请在 Desktop 里打开 Copilot 面板，看 L1、L2 的 AI 指令是否被读到（DMV 读不到它），结果手写在探测报告后面。

## 5. dry-run（不调模型）

```powershell
powershell -ExecutionPolicy Bypass -File windows\t17.ps1 dry-run
```

打印 DAX-L0/L1/L2 冒烟（24 题 × 1 次）和全量（全部题 × 3 次）的调用次数与预计费用。它会先核对题库是 `eval-v1.2` 的干净检出、`semantic/` 与 `render/` 是 `-SemanticTag`（默认 `semantic-v1.5`）的内容；**这个 tag 要由用户在 Mac 上合并本卡的 PR 后打**，没打之前 dry-run 会拒绝开跑，这是预期的。

## 6. 冒烟与全量（调模型，花钱）

先过检查清单（`decisions/2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md` 第三节）和 Mac 上 agent 的放行。在 DeepSeek 错峰时段跑（工作日北京时间 9:00–12:00、14:00–18:00 以外；午休 12:00–14:00 算错峰），harness 在高峰时段会自己拒绝。

```powershell
powershell -ExecutionPolicy Bypass -File windows\t17.ps1 smoke -Tier L0     # T17：24 题 × 1 次，预算默认 5 元
powershell -ExecutionPolicy Bypass -File windows\t17.ps1 full  -Tier L0     # T18：全部题 × 3 次，预算默认 15 元/单元
```

每次只跑一个单元，跑之前在 Desktop 里打开对应档位的 `t17-pbip-work\retail-<档位>\retail-<档位>.pbip`（harness 开跑前核对打开的是哪个模型，不对就拒绝）。三个档位用同一个 run id（默认 `<日期>-T17-dax-smoke-01` / `<日期>-T18-dax-full-01`），依次换模型跑三遍。参数：`-RunId`、`-Budget`（元，超出就不开跑）、`-Concurrency`（默认 4）、`-EvalTag`、`-SemanticTag`。

## 7. 把结果带回 Mac

冒烟和全量跑完会自动打包到 `%SEMDEBT_DATA_DIR%\t17-return\<run-id>.zip`，里面是：

- `runs\<run-id>\`：精简日志（只含题号、哈希，可入库）；
- `runs-raw\<run-id>\`：完整原始响应（不入库）。

拷回 Mac 后：`runs/<run-id>/` 放进主仓库的 `runs/`，`runs-raw/<run-id>/` 放进 `$SEMDEBT_DATA_DIR/runs-raw/`，由 Mac 上的 agent 核对、在 `runs/INDEX.md` 记一行、提交。日志只追加，不改写（硬规则 7）。

探测报告在 `%SEMDEBT_DATA_DIR%\t17-probe\`，直接把文本贴回即可。

## 8. 执行器的行为（给贴回结果时对照）

- 查询必须以 `EVALUATE` 或 `DEFINE` 开头、只含一个 `EVALUATE`；用到 `INFO.` 系列元数据函数或 `$SYSTEM` 系统视图的查询**执行前就拒绝**，记为 `metadata_function`（DAX-L0 的模型里有原始列名，只有这样才读得到，见 T10 交接），与其他执行错误分开统计；拒绝的消息照常发回模型修一次。
- 每条查询单独开一个 ADOMD 连接；超时用 `--exec-timeout`（默认 120 秒），超时与资源上限各自归类。
- 没在真实引擎上验证过、留给本机探测核实的：ADOMD 的超时与取消、`DateTime`/`Decimal` 的取值转换、`TMSCHEMA_*` DMV 的列名、PBIP 能否被 Desktop 打开、`__PBI_TimeIntelligenceEnabled = 0` 是否关掉自动日期表、描述/同义词/AI 指令的落位。探测报告里对应的段不通过，就贴回来，在 Mac 上修。
