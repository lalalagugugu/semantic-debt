# T21 规划 agent（-P）：在探查 agent 上加规划、Python 退路与按需检索

- 状态：第一步完成（2026-10-19，待 PR 合并后打 `harness-plan-v1`）；原：未开始（2026-10-19 改写：dsh 不用，改为自写，见 `decisions/2026-10-19-self-built-p-and-cube-notes.md` 第一节）
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
