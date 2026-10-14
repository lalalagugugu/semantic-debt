# AGENTS.md — semantic-debt（主仓库）

本仓库做一个可复现的实验：在中文智能问数（自然语言 → 查询）场景下，测量**语义层质量**（L0 / R / L1 / L1.5W / L1.5S / L2）、**查询语言与接口**（SQL、DAX、指标层 JSON）以及**会探查数据的 agent** 对准确率的影响。被测的是 DeepSeek 模型，不是你。你的角色是搭建实验、运行实验、如实记录。

题目、参考答案和含题目示例的完整设计在**另一个私有仓库** `semantic-debt-eval`（下称「题库」），位于环境变量 `SEMDEBT_EVAL_DIR` 指向的目录。很多任务**不允许**你看到它，见下文「隔离」。不含题目的设计摘要在本仓库 `docs/design-v5-public.md`。

## 开工自检（每个会话开始时先做，不要跳过）

1. 读本文件、`tasks/BOARD.md`、`tasks/cards.yaml` 和分配给你的任务卡（`tasks/Txx-*.md`；题库侧的卡在题库仓库的 `tasks/`）。
2. **核对负责方**：卡片的「负责」一行写的是 Claude Code 还是 Codex。不是你，就停下，告诉用户这张卡归谁。
3. **核对依赖和检查点**（BOARD 的「依赖」列）：未满足就停下，告诉用户缺什么。
4. **核对启动位置和模式**（模式定义见 `tasks/cards.yaml` 顶部）：
   - Claude Code：除 T00 外，每张卡都在 `~/semdebt/cards/<卡号>/`（由 `scripts/start-card.sh` 建的独立 clone）里启动，不在主工作区 `~/semdebt/semantic-debt/` 里改代码。
   - 盲模式：`.claude/settings.local.json` 应由 `templates/claude-settings.blind.json` 生成。先试读 `$SEMDEBT_EVAL_DIR/README.md`：**应当被拒绝**。如果读到了，立即停止，不要看内容，告诉用户隔离失效。
   - 普通模式（G1 之后的 Claude Code 卡）：`.claude/settings.local.json` 应由 `templates/claude-settings.open.json` 生成。
   - Codex：题库侧的卡在 `~/semdebt/semantic-debt-eval/` 里（T01a 例外，在上一级 `~/semdebt` 启动），主仓库的卡在 `~/semdebt/cards/<卡号>/` 里。
5. 任何一条不对，停下，告诉用户正确的启动命令：`~/semdebt/semantic-debt/scripts/start-card.sh <卡号>`（T00 完成后才有这个脚本）。

只做任务卡里写的事。发现设计层面的问题（档位定义、评分规则、题目口径），**停下，写进 `decisions/open-questions.md`，然后问用户**，不要自行改设计。

## 分工

按「谁在什么时候能看到题」分，结果大致是一家管一个仓库。BOARD 和每张卡的「负责」一行是准绳。

| 负责 | 管什么 | 能不能看题 |
|---|---|---|
| Codex | 题库全部（T01a、T03–T06），以及需要「另一家」来做的独立工作：评分器（T02）、指标层（T16）、报告数字复核（T20） | 从一开始就能看 |
| Claude Code | 仓库骨架与隔离（T00）、数据导入（T01）、语义层与渲染器（T08–T10）、harness 与全部运行（T11–T15、T17–T19）、参考答案的独立重算（T05b） | **G1（tag `semantic-v1`）之前不能看**；G1 之后才打开题库 |
| 用户 | 约定清单（T07）、所有检查点（G0–G4）、合并 PR、抽检 | — |

规则：

1. **独立核对必须跨厂商**：参考答案由 Codex 写 SQL、Claude Code 用 pandas 重算（T05b）；评分器由 Codex 写、harness 由 Claude Code 写；报告数字由 Codex 从原始日志重算（T20）。不得由同一家的另一个会话或子 agent 代替。
2. **盲任务只给 Claude Code**：它的项目设置打开了沙箱并禁止读取工作目录以外的文件，隔离可以强制；T01 的第一步会实测这套设置。
3. 题库侧（Codex）在 G1 之前不得读取本仓库 `semantic/` 下除 `conventions.md` 以外的文件（避免对着 L1 文档出题）。

## 子 agent

- 可以用，前提是你所用的工具支持。适合卡内可以拆开并行的活：分批改写题目、分表做数据探查、并行写测试。
- 子 agent 与你在同一个工作目录、同一套权限下工作；不得给它指向工作目录以外的路径，不得让它改权限设置。
- 以下工作**不能**交给子 agent，必须是另一家工具的新会话（见「分工」）或用户：独立重算、独立复核、调优的 B 角。原因：子 agent 的指令是你写的，会把你的理解带过去，就不独立了。
- 子 agent 不得直接调用 DeepSeek。付费调用只能通过 harness 的命令（带 `--dry-run` 和预算检查）。
- 你对子 agent 的产出负责，验收照卡片。

## 硬规则（违反任何一条，相关结果作废）

1. **隔离**
   - 盲模式的卡不得以任何方式获取题目、参考答案、题库里的任何文件、`runs/` 和 `$SEMDEBT_DATA_DIR/runs-raw/` 里的模型输出；不得上网查找任何公开 text-to-SQL 基准（包括外部基准仓库、其论文和博客）的题目、参考 SQL 或语义文档；不得凭记忆复述此类内容。
   - 调优的 B 角只读调优包（见 T14）。
   - 隔离靠物理手段：题库在工作目录之外，项目设置禁止读取工作目录以外的文件。**不得**修改 `.claude/settings.json`、关闭沙箱、用 `--add-dir` 或 `/add-dir` 加入题库目录，也不得绕道（如用 git 命令读取其他仓库的对象）。普通模式由 `start-card.sh` 设置，不由你设置。
   - 不得把任何内容写入用户级的全局配置或记忆文件（如 `~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md`），以免跨会话带出题目信息。
2. **冻结**：以下 tag 打上之后，对应内容不得再改：`semantic-v1`（L1、明细宽表、汇总层、指标清单、L0、渲染器）、`eval-v1`（题集、参考答案、划分、覆盖标注；在题库仓库）、`harness-v1`（系统提示与评分规则）、`harness-agent-v1`（探查 agent 的工具说明）。发现问题 → 记到 `decisions/`，停下来问用户。
3. **不按题调**：不得为了某几道题修改系统提示、渲染器、语义层或评分器。唯一例外是调优任务，且只能用调优包。
4. **数据不入库**：原始数据、Parquet、chDB 与 ClickHouse 的数据目录、模型的原始响应（含思考内容）都放在 `SEMDEBT_DATA_DIR`（仓库之外）。只提交下载、导入、重建的脚本。
5. **密钥**：DeepSeek API key 只从环境变量 `DEEPSEEK_API_KEY` 读取，不得写入任何文件、日志或提交。
6. **花钱前先估算**：任何调用付费模型的命令必须支持 `--dry-run`，先输出调用次数和预计费用；超过任务卡写的预算上限就停下问用户。批量任务放在错峰时段（工作日北京时间 9:00–12:00、14:00–18:00 以外）。
7. **结果只追加**：`runs/` 下的日志只追加、不改写。重跑写进新的 run 目录，并在 `runs/INDEX.md` 记一行原因。提交的日志只含题号、不含题目原文；完整原始响应放 `$SEMDEBT_DATA_DIR/runs-raw/<run-id>/`，日志里记它的哈希。
8. **如实记录**：失败、超时、拒答、异常都要记录，不得过滤或静默重试。重试规则只有一条：执行报错时把报错发回模型修正一次。
9. **chDB**：同一个数据目录不要被两个进程同时打开。题库侧用自己的副本（`$SEMDEBT_DATA_DIR/chdb-eval`，由 T01 的脚本从 Parquet 重建）。

## 名词速查

| 名词 | 含义 |
|---|---|
| 单元（cell） | 一个「栈 × 档位 × 作答方式」组合，例如 SQL-L1、DAX-L2、SQL-L1-E |
| 直答 | 一次调用写出查询；执行报错时由 harness 发回报错、固定修一次。它不是 agent |
| 探查 agent（-E） | 在直答之外多一个只读工具 `run_sql`，由模型决定查不查、查什么、何时交卷，最多 8 步 |
| 规划 agent（-P） | 第二期：拆步骤、Python 退路、按需检索、MCP 工具 |
| L0 | 坏交付：晦涩命名、无描述、约三分之二的关系、暴露技术字段 |
| R | 只给表结构（原始业务名，无描述、无关系） |
| L1 | 业务名、全部关系、描述、枚举含义、同义词与企业约定、文字指标口径 |
| L1 调优 / L2 调优 | 在 L1 / L2 基础上，用调优包里的 bad case 补充说明和示例 |
| L1.5W 明细宽表 | L1 加按主题预关联的视图（只含行级派生列，不聚合）；原始表仍可见 |
| L1.5S 汇总层 | 只暴露按主题、固定粒度预先汇总的表和维度表；明细事实表不可见 |
| L2 | L1 的指标口径做成可调用对象（DAX 度量值、Cube 指标） |
| L1c | 外部基准自带的语义文档原样（仅用于对照） |
| 语义上下文 | 由 `semantic/` 源文件渲染出的 YAML，所有自建单元读同一种结构 |
| 盲模式 / 普通模式 | Claude Code 的两种启动设置，见 `tasks/cards.yaml` |
| G0–G4 | 五个检查点，见 BOARD |

## 目录

```
.claude/     Claude Code 项目设置（沙箱、禁读工作目录以外）；不得修改
data/        下载、导入、导出脚本；数据本身不入库
docs/        不含题目的设计摘要
vendor/      第三方文件（只放建表 DDL 和许可）
semantic/    语义内容源文件：conventions.md、source.yaml（L1）、widetables.sql（L1.5W）、summary/（L1.5S）、metrics.yaml（L2）、l0_map.yaml、tuning/
render/      把 semantic/ 渲染成各单元上下文、Cube 模型、TMDL 的脚本
build/       渲染产物（不入库，可重建）
harness/     调用模型、执行查询、评分
runs/        每次运行的精简日志（JSONL，只追加）
reports/     校验报告、结果表、图
decisions/   用户裁决与设计偏离记录
scripts/     start-card.sh 等辅助脚本
tasks/       任务卡、总览、cards.yaml
templates/   Claude Code 的盲模式与普通模式设置模板
```

## 环境

- 目录布局固定：`~/semdebt/semantic-debt`（主工作区）、`~/semdebt/semantic-debt-eval`（题库）、`~/semdebt/cards/<卡号>`（每张卡的 clone）、`~/semdebt/data`（数据）。
- 环境变量：`SEMDEBT_DATA_DIR=~/semdebt/data`、`SEMDEBT_EVAL_DIR=~/semdebt/semantic-debt-eval`、`SEMDEBT_MAIN_DIR=~/semdebt/semantic-debt`、`DEEPSEEK_API_KEY`（T11 起需要）。代码只通过这些变量找路径，不得写死路径。
- Mac：Python 3.11+、uv、chDB；指标层阶段另需 Docker（ClickHouse 服务、Cube Core）。
- Windows：Power BI Desktop、Python、ADOMD.NET（例如 pyadomd）；DAX 在 Desktop 打开 PBIP 后的本地 Analysis Services 端口上执行。
- 模型：DeepSeek 官方 API（OpenAI 兼容格式）。思考模式开启（默认 high）；思考模式下 temperature 无效，不要设置。日志里记录接口返回的模型版本和题库的提交号。

## 工作方式

- 一张卡、一个分支、一个 clone。分支名 `<卡号>-<简短英文>`，如 `T08-blind-l1`。
- 代码和提交信息用英文；文档、任务卡用中文。
- 每完成一张卡：在卡末尾更新「状态」「产出」「偏离与理由」「工时」；更新 `tasks/BOARD.md` 的状态列；推送分支并开 PR（`gh pr create`），由用户合并。推送失败就告诉用户在卡的目录里运行 `git push -u origin HEAD`。
- 需要用户做的事（审定、裁决、提供账号）写成卡里的「用户确认」清单，完成前不要进入下一张有依赖的卡。
- 设计改动不改 `docs/`，写进 `decisions/`（日期、改了什么、为什么、谁同意的）。

## 完成的定义

卡上的验收项全部满足；有一条可复现的命令；测试通过；BOARD 已更新；任何偏离都写明理由。
