# T32：干净 clone 的 README 复现验证

验证日期：2026-11-01（Asia/Singapore）。结论：报告数字逐字节复现；数据导入、Parquet 导出和 SQL-L1 离线重评成功。外部读者仍无法仅凭 README 获取原始回包；离线重评的自动评分也不等于报告的内容判定。未修正文档或代码，未调用模型，未重新执行模型生成的 SQL。

## 边界与环境

按用户指令，新 clone 位于原 `$SEMDEBT_DATA_DIR/publication/repro/`，两仓库均从 README 的 GitHub HTTPS 地址获取，没有使用原工作区或原虚拟环境：

| 仓库 | 验证提交 |
|---|---|
| semantic-debt | `0049705f2e91a8a4c650b64a97021eafb9a6fd93` |
| semantic-debt-eval | `e17a3fa9517c3eb53b9c31dcd11948a3f61f0654` |

以下以 `REPRO` 表示上述新目录，仅为报告中的路径缩写。按 README，在新主仓库中设置：

```sh
export SEMDEBT_MAIN_DIR="$PWD"
export SEMDEBT_EVAL_DIR="$PWD/../semantic-debt-eval"
export SEMDEBT_DATA_DIR="$PWD/../data"
```

新数据库为 `REPRO/data/chdb`，新 Parquet 为 `REPRO/data/parquet`；没有打开、覆盖或复制原 chDB 数据目录。`uv sync` 新建本 clone 的 `.venv`，使用 CPython 3.12.13、uv 0.11.31、chdb 4.4.0 / chdb-core 26.9.0。裸 `python3` 为 3.14.6，用于 README 的纯标准库数字脚本及比较。

沙箱首次 clone 因无法解析 github.com 失败；放开沙箱网络后同一 clone 命令成功。首次 `uv sync` 因默认缓存访问权限失败（`~/.cache/uv/sdists-v9/.git: Operation not permitted`）；沙箱外原命令成功。未修改缓存路径或依赖。依赖缓存可复用，虚拟环境未复用。这些是本次执行环境限制，不作为仓库代码错误。

## 重算报告数字

按 README 执行：

```sh
python3 scripts/t19a_v7_numbers.py
```

退出码 0。捕获标准输出后与 `reports/results/t19a-v7-numbers.md` 用 `cmp` 比较，逐字节相同；标准错误为空。两者 SHA256 均为：

```text
3ec1f2e0a022cd0cccb750ca31c09a592950e5d1d95bcf728fba450847658137
```

包括 19 个单元、覆盖内外统计、配对区间、D3、D4。SQL-L1 为 250/294 = 85.0%，留出题 125/147 = 85.0%。该脚本只输出文本，不重写目标报告。

## 数据

按 README 链接的 `data/README.md` 校验原数据压缩包；按用户授权复制到 `REPRO/data/raw/archive.zip`，复制后再次校验一致：

```text
d5f2812d104d83330b19ad7ff0a4efd787b3a317dd842bd0ab0ed959396ae642
```

未重新下载。依次执行文档命令，均退出 0：

```sh
uv sync
uv run python data/load.py
uv run python data/export_parquet.py
```

导入脚本解压并核对 25 张表的表头、列序，接受文档明确记录的 DimCustomer 首列空表头；导入 `retail` 共 34,326,191 行。导出 25 个 Parquet，共 359,806,244 字节。没有运行会覆盖已有 `reports/validation/data_load.md` 的可选校验报告步骤，也没有为本任务创建不需要的 chdb-eval 副本。

## SQL-L1 离线重评

README 尚无回包下载地址。本次仅按用户授权，将已有 `runs-raw/20261018-T13-sql-direct-01/SQL-L1/` 复制到新数据目录同一路径。没有读取其他单元回包，没有复制旧数据库、渲染产物或旧虚拟环境。

按 README 执行，仅替换明确要求自定的 run-id：

```sh
uv run python -m harness.rescore --source 20261018-T13-sql-direct-01 --cell SQL-L1 --run-id 20261101-T32-clean-repro-SQL-L1-01
```

退出 0；新文件为 `runs/20261101-T32-clean-repro-SQL-L1-01/SQL-L1.jsonl`，366 条（122 题 × 3），零费用。程序核验所用执行回包 SHA256 与源日志一致；未添加 `--allow-changed-question` 或其他未列出的评分选项。新记录 `eval_commit=e17a3fa`、`eval_tag=null`，评分使用当前新 clone 题库。日志中的历史 token、模型指纹和 turns 来自源运行，不代表本次调用模型。

| 日志 | correct | wrong | pending | exec_error |
|---|---:|---:|---:|---:|
| 原始 `20261018-T13-sql-direct-01` | 205 | 119 | 40 | 2 |
| 既有 `20261018-T13-sql-direct-01-rescore-01` | 210 | 115 | 39 | 2 |
| 本次新 run | 213 | 112 | 39 | 2 |

按 `(qid, rep)` 比较，与原始日志的全部 outcome 差异为：

| 变化 | 作答 |
|---|---|
| wrong → correct | Q08 r2/r3，Q35 r1/r2/r3，Q30 r1/r3，Q65 r2/r3 |
| correct → wrong | Q30 r2 |
| pending → wrong | Q79 r2 |

差异证据：`runs/INDEX.md` 中 T13 rescore-01 及 `reports/results/sql_direct.md` 已记录评分器从 harness-v1 到 v1.1/v2 的修正和 Q79 超时消除；与该既有重评相比，本次仅剩 Q30 三条、Q65 两条翻转。题库 `audit/post-freeze.md` 的 2026-10-28 裁决记录及主仓库 `decisions/2026-10-28-reference-rulings-five-questions.md` 解释后者：Q30 修改参考窗口，Q65 增加可接受的汇总解读。因此不是回包变化或重跑模型造成的随机差异。39 条 pending 是 judge 题，README 命令没有执行人工裁决流程。

进一步与 `runs/20261031-T31-v5-rulings-01/SQL-L1.jsonl` 对齐，327 条非 judge 作答的 `v2_outcome` 与本次全部相同。剔除其中低区分度题后，98 题 × 3 的自动评分为 correct 202、wrong 90、exec_error 2，即 202/294 = 68.7%；同一集合 v5 的 `content_correct` 为 250/294 = 85.0%。这是不同判定口径，离线命令没有自动应用 v5 内容裁决，不能把 68.7% 当成报告 85.0% 的复现失败。

新 run SHA256：`0ad16bcb94a513a31c58482aeee6882cc084a9cb529f7f13a9f695a3140c83f6`。

## README 的缺口与外部读者限制

1. 原始回包的下载地址仍是“发布后补”。外部读者无法从两个 clone 独立取得输入；压缩包名称、清单及发布校验值也尚未提供。本次使用现有回包是用户提供的额外条件，不证明公开分发链可用。
2. 完整报告链接仍是“发布后补链接”。
3. 离线重评没有说明默认使用当前题库，未固定与历史结果对应的 tag/commit；本次出现上述可解释翻转。这里仅记录，没有自行选择旧 tag 重跑。
4. README 没说明离线自动评分、judge pending 与 v5 内容准确率的关系，也没有从离线结果走到最终内容裁决的操作步骤。仅运行这条命令不能得到主表 85.0%；数字脚本则能从仓库已有最终标签完整重算。
5. README 未说明数字脚本写到标准输出，亦未给出目标 `t19a-v7-numbers.md` 的比较命令。本次按用户指定目标捕获并比较，没有重写已有报告。
6. 当前 GitHub clone 在已有认证的环境下成功；未测试未登录访问，不能据此证明外部匿名读者能 clone 两仓库。

除上述明确边界外，本次范围内没有发现命令拼写错误或必须靠猜才能继续的数据导入步骤。为遵守“不改现有文件”，本 PR 仅新增此报告及新 run；未修改 README、任务板或既有 runs 索引。命令输出保留在新 clone 的同级目录 `REPRO/`（numbers.stdout/stderr、uv-sync.log、load.log、export.log、rescore.log），不提交原始回包或数据。
