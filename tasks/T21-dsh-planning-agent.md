# T21 规划 agent（-P）：用 DeepSeek Harness（dsh）接同一份语义层

- 状态：未开始（卡片 2026-10-19 起草）
- 负责：Claude Code
- 模式：普通（`scripts/start-card.sh T21`）
- 依赖：第一步（可行性验证）在 `harness-agent-v1.1` 打 tag 后即可开始；第二步起（冻结与开跑）要等 T15 的 L0-E、L1-E 全量跑完（对照基准）
- 预算：可行性验证 ≤ 1 元；正式单元的上限在第二步按实测估算后由用户定，超了就停
- 依据：`decisions/open-questions.md` 协调-1（用户 2026-10-18 同意方向、排期与三条约束）；`decisions/2026-10-19-t15-1-midreport-dsh.md` 第三节

## 目标

回答「用官方 agent 框架接上同一份语义层，能到多少准确率；其中多少来自框架本身，多少来自规划和 Python」。排在 DAX 线（T17、T18）之前，结果进 SQL 线中期报告。

## 单元

| 单元 | 作答方式 | 档位 | 作用 |
|---|---|---|---|
| SQL-L0-P、SQL-L1-P | dsh 全开（规划、Python、`run_sql`） | L0、L1 | 规划 agent 的主结果 |
| SQL-L0-P0、SQL-L1-P0 | dsh 只开 `run_sql`，其余同 T15 的 -E（工具说明、50 行回显、8 次上限、30 秒 / 120 秒） | L0、L1 | 对照：P0 − E = 框架本身的影响；P − P0 = 规划 + Python 的增益 |

档位先只做 L0、L1（用户约束 ①）。题集与次数同 T15：中文题集全部，每题 3 次；先跑小样本（试跑 24 题 × 1 次）。

## 第一步：可行性验证（一个会话，基本不付费）

逐条实测并写进本卡，**五条有一条不行就停**，报告协调会话，放弃 dsh（DAX 接在 T15 之后，中期报告不含 -P）：

1. **系统提示与工具可替换**：能把系统消息换成与直答单元相同的文本（`harness/prompt.py` 逐字节）+ 一段工具说明；能关掉 dsh 自带的、本实验不允许的工具（联网搜索、读写任意文件、任意 shell）。
2. **结构化交卷**：无界面模式下能用一个交卷工具（或等价的固定格式）给出最终查询，harness 照直答规则执行、修一次、打分。
3. **隔离**（硬规则 1）：dsh 及其 Python 运行在容器或独立目录里，读不到题库、参考、`runs/`、`$SEMDEBT_DATA_DIR/runs-raw/`，不能联网查基准。**数据只能经 `run_sql` 取**（过与直答相同的库范围与只读检查）：Python 不得直接读 Parquet 或 chDB 数据目录，否则 L0 档会经原始表名、列名绕过劣化。
4. **版本锁定**：dsh 锁到确切的提交或版本号，记进日志；依赖锁定。
5. **日志与封顶**：逐步记录 token、`system_fingerprint`、工具调用；步数、token、费用可封顶；不静默重试（硬规则 8：只允许执行报错修一次）。指纹不是 G3 的（`e72d3c7f663d3e1383b00b3884cb4501`）就停。

验证可以用 MockClient 或极少量真实调用（合计 ≤ 1 元，带 `--dry-run` 与 `--budget`）。

## 第二步：冻结与估算

- 把 dsh 版本、系统消息、工具说明、Python 与 `run_sql` 的上限、交卷契约写定，打 tag `harness-dsh-v1`（由协调会话在用户说「打 tag」后打）。
- 小样本实测步数后用 `--dry-run` 估全量费用，交用户定预算上限。

## 第三步：运行

- 小样本 → 用户批准 → 全量；错峰；结果只追加（硬规则 6、7）。
- 打分用当时冻结的评分器（`harness-v1.1` 之后的版本），judge 题不进主分母。

## 交付物

- `runs/<run-id>/` 四个单元的 JSONL，字段与 T15 对齐，另记规划步骤、Python 调用次数与耗时。
- `reports/results/planning.md`：四个单元与直答、-E 的准确率与四种结果占比；P0 − E、P − P0 两个差；每题平均步数、token、耗时与费用（agent 税）。

## 验收

- 第一步五条各有实测证据；不通过时写明哪条、为什么。
- 记录数 = 题数 × 3 × 4，无缺失；`run_sql` 全部只读；Python 没有直接读数据文件的记录。

## 记录（完成后填写）

### 第一步：可行性验证（进行中，2026-10-19）

**锁定版本**：源码 `deepseek-ai/deepseek-harness` 提交 `687f282e8625c6b8d11ff58211a90524be2e4317`（tag `dsh-v0.2.1-rc.2`，2026-10-17），克隆在 `$SEMDEBT_DATA_DIR/vendor/dsh`（用户手动克隆）；容器内装 npm `@deepseek-ai/dsh@0.2.1-rc.2`（integrity `sha512-tvY+yhfKRifthbqPe/OK0AYxM5ZkvqfYq/jMYgJcEUxiRRL1Vwra3Ti5TB6AXgSWQdiPHYh/Vp6SJa9yHwMNuw==`）与 `@deepseek-ai/dsh-llm-pi-ai@0.2.1-rc.2`。用户约束：依赖安装与 dsh 运行全部在 Docker 容器里（`harness/dsh/Dockerfile`）。

**读源码的结论（未实测，实测后逐条改为证据）**

| 前提 | 源码证据 | 初判 |
|---|---|---|
| ① 系统提示与工具可替换 | `packages/bundle/sdk-minimal/cordis.patch.yml` 是完整的显式插件树；`system-prompt.personaPrefix`（环境变量 `DSH_SYSTEM_PROMPT`）替换人设，`includeHarnessIdentity`、`includeRuntimeContext` 为 false；每个工具一行，可 `disabled`（bash、read_image、working_directory；联网工具只在 `dsh-base` 里）；`run_sql` 经 MCP client 接入 | 可行；待实测请求体里的 system 是否逐字节等于 `harness/prompt.py` + 工具说明、有无 `working-directory` 注入的用户上下文 |
| ② 结构化交卷 | SDK `RunResult.final_response` 为最后一条助手文本 → harness 照直答规则解析、执行；修一次 = 同一会话再发一条报错消息。**`plan-mode` 要 `/plan` 进入并由人批准计划**，无人值守跑不了，「规划」可能只能用 todo / workflow 工具 | 可行；「规划」用什么要定 |
| ③ 隔离 | 只能实测（容器无挂载、网络只到 DeepSeek、数据只经 `run_sql`） | 待测 |
| ④ 版本锁定 | npm 精确版本 + 容器内生成的 lock；源码 `pnpm-lock.yaml` 锁 `@earendil-works/pi-ai@1.1.0` 并打补丁（hash `66eaf960…`）；镜像 digest 构建后记 | 可行 |
| ⑤ 日志与封顶 | **官方适配器 `llm-deepseek` 调 `https://api.deepseek.com/anthropic/v1/messages`（`src/config.ts:115`、`src/adapter.ts:138`），不是直答用的 `chat/completions`；全源码不读 `system_fingerprint`**。agent 循环无步数上限（`core/agent-loop/src/agent.ts` `while (true)`）；`llm-retry` 是可删的一行（默认会重试）；`session-log-deepseek` 会把会话日志上传给 DeepSeek，须关 | 有风险。补救：换 `llm-pi-ai` 的 `openai-completions` 接口走同一 `chat/completions` 端点，另在宿主机放一个记录原始响应（token、指纹）并对请求数 / token / 费用封顶的中继 |

**本会话的环境障碍**：沙箱连不上 Docker（无 `/var/run/docker.sock`，`~/.docker` 不可读）；沙箱不能监听本地端口（EPERM，中继与 `run_sql` 代理需要，要 `sandbox.network.allowLocalBinding: true`）；`uv` 读不到 `~/.local/share/uv/python`。克隆与 `git clone`、一次 WebFetch 被权限层拒绝，未绕过。


- 产出：
- 偏离与理由：
- 工时：
