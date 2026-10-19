# T21 规划 agent（-P）：在探查 agent 上加规划、Python 退路与按需检索

- 状态：小样本完成（2026-10-19）；全量暂停，等用户裁决 T21-1、T21-2（见文末「第二步之后的分析」）；此前：第一步完成（`harness-plan-v1` 已打在 `b10ca1a`）；原：未开始（2026-10-19 改写：dsh 不用，改为自写，见 `decisions/2026-10-19-self-built-p-and-cube-notes.md` 第一节）
- 负责：Claude Code
- 模式：普通（`scripts/start-card.sh T21`）
- 依赖：G3；`harness-agent-v1.1`（复用探查 agent 的运行器）；对照基准是 T15 的 L0-E、L1-E 全量（已完成，`runs/20261019-T15-explorer-01/`）
- 预算：小样本 ≤ 3 元；全量上限在小样本实测后由用户定，超了就停

## 目标

量「规划 + Python + 按需检索」在探查 agent 之上还能补回多少：-P − -E 就是这三样合起来的增益。只做 L0、L1 两档。

## 规格

**底座**：`harness/run_agent.py`。探查 agent 已有的都照用，不另起一套：`run_sql`（同一执行器、库范围、只读检查、50 行回显、30 秒 / 120 秒）、日志字段、指纹守卫、`--dry-run` 与 `--budget`、「次数用完请交卷」、最终查询报错修一次、子进程限时打分。

**新增三样能力**（工具说明写定后冻结为 `harness-plan-v1`，与 `harness-agent-v1.1` 一样只说明工具怎么用，不含任何关于数据的提示）：

1. **规划**：第一步必须先交一份步骤计划（工具 `plan(steps)`），之后可以改计划（每次改动都记日志）。计划不执行任何东西，只是让模型先拆题。
2. **Python 退路**：工具 `python(code)`，可以读前面 `run_sql` 取回的**完整结果**（不只是回显的 50 行；每份上限 20 万行，超了明说），可用 pandas、numpy。
   - **隔离**（硬规则 1）：代码在没有网络、读不到任何文件的环境里跑（优先 Docker `--network none`、不挂载目录；不行就用 macOS `sandbox-exec` 的禁读禁网配置），数据只经 `run_sql` 进来。开跑前在这个环境里实测「读题库目录、读 `runs/`、读 Parquet、访问外网」全部失败，证据写进本卡。
   - 每次执行限时 30 秒、输出截断规则同 `run_sql`。
3. **按需检索语义文档**：系统消息里只放语义上下文的目录（表、指标、约定的名称与一句话摘要），完整内容由工具 `lookup(name)` 按名取回，取回的文字与直答单元渲染出的 YAML 逐字相同。

**交卷**：二选一，都由 harness 重新执行后照直答规则打分。
- 一条 SQL（同直答）；
- 或「若干条 SQL + 一段 Python」：harness 在同一隔离环境里重新执行这些 SQL 和代码，代码输出的表就是答案。执行报错同样只修一次。

**上限**（一个值管所有 -P 单元，不按题、不按单元调）：工具调用合计 12 次（`run_sql`、`python`、`lookup` 都算，`plan` 不算），用完照 T15-1 的做法提示一次再强制交卷。

**单元**：SQL-L0-P、SQL-L1-P，中文题集全部，每题 3 次；先小样本（试跑 24 题 × 1 次）。是否加消融单元（如去掉 Python 或改回整份上下文，用来拆开三样能力各自的贡献），小样本之后由用户定。

## 步骤

1. 实现 + 测试（MockClient，不花钱），隔离实测，工具说明写定 → PR → 用户合并后由协调会话打 `harness-plan-v1`。
2. 小样本（≤ 3 元，错峰）→ 报告与 -E 同题对比、步数分布、Python 与 lookup 的使用情况 → 用 `--dry-run` 按实测估全量，交用户定上限。
3. 全量 → 用 `harness-v1.1`（或当时冻结的评分器）打分 → `reports/results/planning.md`。

## 交付物

- `runs/<run-id>/` 两个单元的 JSONL，字段与 T15 对齐，另记计划（及改动）、每次 `python` 与 `lookup` 调用、交卷形式（SQL / SQL+Python）。
- `reports/results/planning.md`：-P 与直答、-E 的准确率与四种结果占比；-P − -E；Python 交卷占比及其准确率；agent 税（步数、token、耗时、费用）。

## 验收

- 隔离实测四项全部失败（证据在卡里）；`run_sql` 全部只读；Python 没有任何文件或网络访问。
- 记录数 = 题数 × 3 × 2，无缺失；指纹只有 G3 的那一个。

## dsh 可行性验证（2026-10-19，已停止）

只读源码、未运行、0 元。dsh `dsh-v0.2.1-rc.2`（`687f282e8625c6b8d11ff58211a90524be2e4317`）：系统提示与工具可替换（①可行）、能锁版本（④可行）；但规划模式在无界面时需要人工批准（②打折扣）、官方 DeepSeek 适配器不记 `system_fingerprint`、循环没有步数上限、默认上传会话日志（⑤ 不满足，只能靠自写转发层补）。按卡片规则放弃，第二期 dsh 稳定后再评估。

## 记录（完成后填写）

### 第一步：实现、测试、隔离实测（2026-10-19，0 元，未调用模型）

**实现**

- `harness/plan_prompt.py`（冻结为 `harness-plan-v1`）：系统消息 = `SYSTEM_PROMPT`（`harness-v1` 逐字节）+ 语义上下文目录 + 本单元语法说明（逐字节）+ 工具说明 `TOOL_SECTION`；工具定义 `plan`、`lookup`、`run_sql`、`python`；目录与 `lookup`；最终答案解析 `parse_final`。
- 目录：渲染出的 YAML 按顶层节、节内按列表项**按原文切片**；每个数据集、指标、约定、数据质量条目一行「lookup 名称 — 摘要」，摘要取条目自身的 title / definition / rule 的第一句；其余节（relationships、synonyms、multi_path_defaults、model 等）列节名与条数，`lookup` 用节名取回整节。SQL-L1 全文 111,008 字符 → 目录 5,826 字符；L0 只有数据集名与两节。`lookup` 返回的切片与直答单元渲染出的 YAML 逐字相同（测试对 L0、L1 逐条核对：切片拼回原文、逐条解析与原 YAML 相等）。
- `harness/run_plan.py`：在 `run_agent.py` 上加三样工具，`run_sql` 的执行器、库范围、只读检查、50 行回显、30 秒 / 120 秒、指纹守卫、`--dry-run` / `--budget`、T15-1 的「用完请交卷」、修一次、子进程限时打分（scorer v2，`harness-v1.1`）全部照用；版本闸另查 `--plan-tag`（`plan_prompt.py`、`pysandbox.py`、`pysandbox_image/runner.py`、`Dockerfile`）；`invalid_rules` 预检同 T13/T15。开跑前先在沙箱里跑一次 `print(1 + 1)`，不通就拒绝开跑。
- 交卷两种：一条查询（同直答）；或若干 ```sql 块 + 最后一个 ```python 块（harness 用最终查询的执行器重跑这些查询，`results[i]` 依次是其结果，代码给 `answer` 赋 DataFrame）。Python 答案的 `answer` 表写进该轮的 `.exec.json`，`harness.rescore` 不用改即可离线重评（有测试）。
- 日志：-E 的全部字段，另加 `n_plans`、`plan_first_rejections`、`tool_executed`（按工具）、`answer_kind(s)`、`python_time_s`、`hit_model_call_limit`、每次 `lookup` 的取回 / 未找到名称、每次 `python` 的状态与耗时。**计划和 Python 代码可能转述题目，日志只记哈希与长度**，原文在 runs-raw（`*.plan.json`、`*.py.json`、`*.answer.py.json`）。
- 测试 `tests/test_plan.py` 45 条全过（含 4 条真实容器测试）；`tests/test_agent.py`（除真实 chDB 两条）与 `tests/test_repo_layout.py` 通过。未跑全套（T13、T15 共用 `$SEMDEBT_DATA_DIR/chdb`，全套前先与它们确认）。

**Python 沙箱**（`harness/pysandbox.py`、`harness/pysandbox_image/`）

- 镜像：`python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c` + pandas 2.3.3、numpy 2.3.4；本地构建，按镜像 ID 运行：`sha256:90d5c68f2334ccae65a91598834689a02e4dec5b77f1513115ecf314129af10e`（`docker build -t semdebt-pysandbox:1 harness/pysandbox_image`，内容不变则 ID 不变；改了就要更新 `IMAGE_ID`）。
- harness 只会发出一条 docker 命令，`check_command` 拒绝其他一切（有测试：`-v`、`--mount`、`--privileged`、`--network host`、去掉 `--read-only`、换镜像、`docker exec`、`docker kill` 全部拒绝）：

      docker run --rm -i --name semdebt-py-<12 位 hex> --network none --read-only \
        --tmpfs /tmp:rw,noexec,nosuid,size=256m --memory 2g --memory-swap 2g --cpus 2 --pids-limit 256 \
        --cap-drop ALL --security-opt no-new-privileges --user 10001:10001 sha256:<IMAGE_ID>

- 30 秒限时在镜像里（`ENTRYPOINT timeout -s KILL 30 python -I /sandbox/runner.py`），harness 不需要 `docker kill`；每次是全新容器，变量不保留。数据只经 stdin 进入（`run_sql` 返回的行，每份 ≤ 20 万行），列按 ClickHouse 类型转成 pandas 类型。
- **环境要求**：Claude Code 沙箱里 docker CLI 读不到 `~/.docker/config.json`，会去找 `/var/run/docker.sock`；运行与测试前要 `export DOCKER_HOST=unix://$HOME/.docker/run/docker.sock`，且 `.claude/settings.local.json` 的 `sandbox.network.allowUnixSockets` 放行这个 socket（用户 2026-10-19 选 A 后加的）。**本卡完成后提醒用户删掉这一行。**

**隔离实测**（2026-10-19，经 harness 的 `DockerSandbox` 原样执行，`harness/pysandbox_image/isolation_probe.py`；`tests/test_plan.py::test_real_sandbox_isolation_every_probe_is_blocked` 可复现）：

    blocked  read question bank README: FileNotFoundError: [Errno 2] No such file or directory: '<SEMDEBT_EVAL_DIR>/README.md'
    blocked  read question bank dir: FileNotFoundError: [Errno 2] No such file or directory: '<SEMDEBT_EVAL_DIR>'
    blocked  read runs/: FileNotFoundError: [Errno 2] No such file or directory: '<repo>/runs'
    blocked  read runs-raw: FileNotFoundError: [Errno 2] No such file or directory: '<SEMDEBT_DATA_DIR>/runs-raw'
    blocked  read parquet file: FileNotFoundError: [Errno 2] No such file or directory: '<SEMDEBT_DATA_DIR>/parquet/DimAccount.parquet'
    blocked  read chdb dir: FileNotFoundError: [Errno 2] No such file or directory: '<SEMDEBT_DATA_DIR>/chdb'
    blocked  host mounts (other than docker's own /etc files): LookupError: no host mounts; only /etc/hostname, /etc/hosts, /etc/resolv.conf
    blocked  dns api.deepseek.com: gaierror: [Errno -3] Temporary failure in name resolution
    blocked  tcp 1.1.1.1:443: OSError: [Errno 101] Network is unreachable
    blocked  tcp 116.205.40.120:443: OSError: [Errno 101] Network is unreachable
    blocked  write / (read-only root): OSError: [Errno 30] Read-only file system: '/probe.txt'

（路径在实测里是本机绝对路径，这里换成变量名。）验收第一条的四项（读题库、读 `runs/`、读 Parquet、访问外网）全部失败。

**卡片没写死、由本卡定的细节（随 `harness-plan-v1` 一起由用户审定）**

1. `lookup` 一次可取多个名称（`names` 列表，每次最多 10 个），算一次调用。卡片写的是 `lookup(name)`；一次一个的话，L1 的一道题光取表、关系、约定就要五六次，会挤掉 12 次里的 `run_sql` 和 `python`。要改回一次一个只需改 `MAX_LOOKUP_NAMES = 1`。
2. 「第一步必须先交计划」用 harness 强制，不用 `tool_choice` 指定函数（思考模式下是否支持未验证，验证要花钱）：计划之前的其他工具调用不执行、回「请先调用 plan」、不计次数；直接作答不拦，记 `n_plans = 0`。
3. `plan` 前 3 次不计数，之后每次计入 12 次；另设每次作答最多 18 次带工具的模型调用（12 + 3 + 3）作兜底，防止模型一直不交计划时不计数地空转；到兜底同样先发「用完请交卷」再强制作答。
4. 交卷的 Python 不能用探查时的 `run_sql` 结果编号，只能用答案里自己列出的查询（`results[1..n]` 按代码块顺序）；与工具里的编号同名但含义不同，工具说明里分开写了。
5. Python 答案里查询结果超过 20 万行算执行错（`limit = py_rows`），可修一次。

**估算**（`--dry-run`，按默认假设：每题 7 次模型调用、每步新增 3,000 token 全不命中缓存、每次输出 2,000 token）：小样本 24 题 × 1 次 × 2 单元约 3.62 元，超出卡片的 ≤ 3 元。-E 实测每题 0.011–0.017 元，这个假设偏悲观；按卡片，小样本开跑前由用户定是用 `--budget 3` 加较低的估算参数，还是放宽上限。

    export DOCKER_HOST=unix://$HOME/.docker/run/docker.sock SEMDEBT_EVAL_DIR="$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2"
    uv run pytest tests/test_plan.py
    uv run python -m harness.run_plan --cell SQL-L0-P --cell SQL-L1-P --pilot --reps 1 --dry-run

- 产出：见上
- 偏离与理由：本机 `uv` 读不到 `~/.local/share/uv/python`，虚拟环境用 Homebrew 的 Python 3.14（`UV_PYTHON=/opt/homebrew/bin/python3.14`），不影响 harness 行为
- 工时：第一步约 2 小时（含 dsh 源码阅读）

### 第二步：小样本（2026-10-19，`20261019-T21-pilot-01`）

用户定小样本上限 5 元（经协调会话）。`harness-plan-v1`（`b10ca1a`）、`eval-v1.2`（只读检出 `eval-ro-eval-v1.2`）、scorer v2；错峰 12:00:15–12:07:50；**1.18 元**（L0-P 0.60、L1-P 0.59）；287 次模型调用指纹全是 G3 的 `e72d3c7f…`。

| 单元（同 24 题） | 对 / 错 / 其他 | 准确率（对 ÷ 全部） |
|---|---|---|
| SQL-L0 直答（T13 重评，×3） | 27 / 41 / pending 3、拒答 1 | 37.5% |
| SQL-L0-E（T15 重评，×3） | 28 / 38 / 执行错 4、pending 2 | 38.9% |
| **SQL-L0-P（×1）** | 12 / 11 / pending 1 | **50.0%** |
| SQL-L1 直答（×3） | 50 / 19 / pending 3 | 69.4% |
| SQL-L1-E（×3） | 54 / 15 / pending 3 | 75.0% |
| **SQL-L1-P（×1）** | 14 / 9 / pending 1 | **58.3%** |

- 每题只有 1 次，误差大，只作方向参考。
- **python 一次都没用，交卷全是单条 SQL（48/48）**。计划每题都交了（无拒绝）。
- 计数工具调用次数分布：L0-P 4–12 次，7 题用满 12 次；L1-P 多为 2–3 次，1 题用满。lookup 次数：L0-P 34、L1-P 26（**L1-P 平均每题约 1 次 lookup**，大部分语义内容没取回，可能是 L1-P 低于 L1 直答的原因，待全量后归因）；run_sql：L0-P 174、L1-P 63；只读拒绝 1 次（L0-P，`forbidden_statement`）。
- 每题平均 0.025 元、30–35 秒。按实测估全量（366 × 2）约 **18.1 元**（错峰）。

### 第二步之后的分析（2026-10-19，云端会话，0 元；只读已提交的日志，未调用模型、未读题库）

本节由一个 Claude Code 云端会话写，用于交接：本地 T21 会话 resume 后先单独运行 `git pull origin T21-pilot`，再读本节。

**L1-P 为什么低于 L1-E**（同 24 题：L1-P 58.3%（×1），L1-E 75.0%（×3））

1. **-P 相对 -E 改了四样，不只是「加规划 + Python」**：规划、Python、按需检索（系统消息只放目录：L1 全文约 11 万字符 → 目录约 5,800 字符；L1-E 第一次调用的 prompt 约 4.7 万 token，L1-P 约 4,900），以及计数工具上限 12（-E 是 8）。这是按卡片规格做的（设计 v5 第二期第 1 条就把按需检索写进了 -P），但 -P − -E 因此拆不开。
2. **检索只做一次**：L1-P 24 题里 22 题只调 1 次 `lookup`、2 题调 2 次；15 题的 `plan` 和第一次 `lookup` 在同一次模型调用里发出，其余也是交完计划后马上取，之后从不补取。每次取多个名称，每题取回 1–3 万字符。12 次上限不是瓶颈（只有 Q40 用满，用在 `run_sql` 上）。**上一节「L1-P 平均每题约 1 次 lookup，大部分语义内容没取回」更正为**：调用约 1 次，但一次取多个条目；漏掉的是没被点名、跨条目的限定。
3. **回退逐题**（L1-E 3/3 对、L1-P 错的 6 题）：
   - Q80、Q81（**检索造成**）：首次 / 最近购买加了 `SalesQuantity = 1`。取了 `FactOnlineSales`（描述里写「销售行 SalesQuantity = 1，退货是单独的行」），没取约定 13 / 14；约定 14 的 note 写明「购买」指任何一行、含只有退货的行，而它在目录里的摘要只有「新客：…」。
   - Q74：加了 `StoreType = 'Store'`，排除 7 家虚拟门店；-E 看到同样的 `DimStore` 描述却没排除。属于自加的假设。
   - Q66：把「累计」做成季度滚动累加；Q82：入职年限用 `dateDiff('year')` 取整，-E 用天数 ÷ 365.25。都是理解或算法选择，与检索无关；每题只跑 1 次，可能含采样波动。
   - Q34：「平均在手库存金额」的分母取全年 52 个快照日，-E 取每个产品自己的快照日。指标文字有歧义，见下文和 `decisions/open-questions.md` T21-2。
   - 反方向：Q17、Q50、Q76（-E 1/3）和 Q49（-E 2/3）L1-P 都对了。按 -E 的每题正确率折算，-E 在这 24 题上预期约对 18 题，L1-P 实际对 14 题。
4. **L0-P 高于 L0-E**（50.0% 对 38.9%）：L0 的目录和全文差别不大，检索拿掉的东西少；但 L0-E 全量有 216/366 条用满 8 次，-P 上限是 12，这 +11 点可能部分来自上限更高。

**Q34 的口径**：L2 的两个实现（`render/measures.py:217` DAX `AVERAGEX ( VALUES ( DateKey ), … )`；`render/measures.py:445-446` Cube 分组内 `uniqExact(DateKey)`）都按「当前分组里出现过的快照日」算，参考答案也一样；L1.5S 的库存汇总表粒度是「快照日 × 门店 × 品类」，答不了产品级问题。所以口径实际上已定，模糊的是 L1 的文字。这为 C4（L1 → L2）补了一条解释：L2 的增益除了「省掉写计算」，还有「实现消除了文字的歧义」，与设计第 3 条规矩的前提冲突。处理待裁决（T21-2）。

**用户在本会话里的意见（2026-10-19）**

- 是否整份放进上下文，取决于要验证的假设：验证「完整语义层 + 规划 + Python」就必须整份放；「全量 vs 按需检索」是另一个假设。后者作为新增假设 C12 记进 `reports/hypotheses.md`（之前不在计划里）。-P 的单元定义待裁决（`decisions/open-questions.md` T21-1）。
- **不往小样本里加会用到 Python 的题**（用户同意）。理由：小样本要和 T13、T15 同题比；全量 366 题里含 13 道 judge 题（多步和统计类），Python 用不用在全量里就能看到；「有 Python 也不用」本身就是结论（ClickHouse 自带 `corr`、`quantile`、窗口函数）。小样本按 Q1 / Q2 / Q3 各 8 题分层，L0-P 和 L1-P 的 48 次作答里 Python 一次都没用，Q2、Q3 题和 judge 题 Q40 都没有触发。
- 假设全表（C1–C13，含证据与初步结论）在 `reports/hypotheses.md`。

**下一步（等用户裁决 T21-1 之后）**

1. 按裁决定单元：建议主单元为「-P 整份上下文」（C11），现在的检索版保留为对照（C12），次数上限对齐方式由用户选。改单元要改 `harness/plan_prompt.py`，并重新冻结（`harness-plan-v1.1` 或类似）。
2. 新单元先跑同 24 题 × 1 的小样本（L1 约 0.6 元 / 单元），再按实测估全量，交用户定上限。
3. 全量之后的归因：L1-P 的错答里，有多少是「该取的条目没取」（逐题比对取回的名称与错因）。

### 用户裁决与交接（2026-10-19 下午，云端会话）

**T21-1 已部分裁决**（用户）：主单元放整份上下文（C11）；现在的检索版保留为对照单元（C12）；按新定义重跑小样本，≤ 5 元，**18:00 后错峰**。

**次数上限：待用户确认，建议如下**

- 现状：-E 是 `run_sql` ≤ 8 次；-P 是 `lookup` + `run_sql` + `python` 合计 ≤ 12 次（`plan` 不计）。
- 问题：主单元放整份上下文后不需要 `lookup`，如果上限还是 12，它就比 -E 多 4 次查库，C11 的差距里会混进「多查 4 次」。L0-E 全量有 216/366 条作答用满了 8 次，可见上限对 L0 是实际约束。
- 建议：
  - **所有 agent 单元的「干活」次数统一为 8**：`run_sql` + `python` 合计 ≤ 8，与 -E 一样。
  - **检索版另给 `lookup` ≤ 4 次，单独计数**，不占那 8 次。这样两个 -P 单元之间只差「上下文在系统消息里，还是要自己取」，检索不挤占查库次数。小样本里每题最多只调过 2 次 `lookup`，4 次不会成为约束。
  - `plan` 不计数（前 3 次）、18 次模型调用的兜底，照旧。
- 要改的代码：`harness/plan_prompt.py`（两种单元的系统消息与工具说明；计数分开）、`harness/run_plan.py`（单元名，如 SQL-L1-P 与 SQL-L1-PR；计数逻辑）、测试。工具说明变了，要重新冻结（如 `harness-plan-v1.1`），由用户合并后打 tag。
- 小样本：4 个单元 × 24 题 × 1 次（L0-P、L1-P 整份上下文；L0-PR、L1-PR 检索），按上一轮实测约 0.6 元 / 单元，合计约 2.5 元。先 `--dry-run`，≤ 5 元，18:00 后跑。

**T21-2：比对已完成，处理方式待裁决**

- 结果在 `reports/validation/metric-text-vs-impl.md`：69 个指标里 14 个属 A 类（实现选定了文字没写明的读法），8 个属 B 类（DAX 与 Cube 不一致，或引擎做不到文字的全部）。
- 本地会话能读题库，请补一步：按 A、B 类的指标名，列出题集里用到它们的题和各单元在这些题上的对错（只写题号，不写题面），追加到那份报告。

**还要本地会话跑的分析**（这个云端会话读不到题库，`add_repo` 被权限拒绝）

    SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/hypothesis_splits.py --run 20261018-T13-sql-direct-01-rescore-01 --eval-tag eval-v1.2
    # 第一次不带 --user-key：脚本会列出题库里的标注字段名；找出表示「用户类型」的那个，再带上它跑
    SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/hypothesis_splits.py --run 20261018-T13-sql-direct-01-rescore-01 --eval-tag eval-v1.2 --user-key <字段> > reports/results/hypothesis_splits.md

  输出 C2（按 `source` 字段，用来复核云端按题号算的数）、C3（同一批覆盖内题上 L1 vs L1.5S、L1.5W 的配对比较）、C9（按用户类型）。结果更新进 `reports/hypotheses.md` 对应行。

**常设追踪板**：`reports/hypotheses.md`（C1–C13，每条的状态、证据和缺口；「现在能写的结论」一节供阶段报告用）。
