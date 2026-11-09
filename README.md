# semantic-debt

语义层欠的账，会让智能问数的准确率掉多少？

这个实验在一份公开的零售数仓（Contoso，25 张表）上，用 122 道中文问题测 DeepSeek Flash 写查询的准确率，比较语义层质量、查询接口和会自己查数据的 agent。98 道题计入主表，每题作答 3 次。

## 主要结果

| 做法 | 准确率 |
|---|---:|
| L0：晦涩命名，没有描述，缺一部分表关系 | 48.0%（全部 98 题） |
| L1：业务名、全部关系、描述、企业约定、文字版指标口径 | 85.0%（全部 98 题） |
| L1+：在 L1 上补全内容、逐条消歧 | 93.2%（全部 98 题） |
| L1 加上线后按错答复盘补的语义 | 92.5%（复盘没用过的测试集 49 题） |

主表全部单元的结果在 `reports/results/accuracy-v5.md`。最低的是只给汇总表（39.8%）和只能调指标（41.8%），主要因为覆盖不到一半的题。

把整个语义层换成本体写法（OWL 2 / SHACL，内容不变，模型仍写 SQL），L1 和 L1+ 两组都没有看出提升：本体减文字分别是 +0.3 和 +2.0 个百分点，区间都含 0（`reports/results/l3a-full.md`）。这组是在接口换成新版本模型之后跑的，同样的 L1 配方比主表低 5.4 个百分点，所以不和主表直接比较。

这些结果只来自一个模型和一份数据，换模型或换模型版本后绝对数字会变。准确率按结果内容判定，比较方法和局限见报告。

这套题已经公开，以后不能再当留出题用。

报告分上下两篇：[上篇](reports/midterm-report-part1.md)（语义内容）、[下篇](reports/midterm-report-part2.md)（agent、本体、指标层与上线护栏）。每次作答的原始响应和报告引用的材料：[Release midterm-v1](https://github.com/lalalagugugu/semantic-debt/releases/tag/midterm-v1)。作答对照页：<https://lalalagugugu.github.io/semantic-debt/>（本体对照在 [t34/](https://lalalagugugu.github.io/semantic-debt/t34/)）。结果数字已经在 `reports/results/` 里。

## 两个仓库

| 仓库 | 内容 |
|---|---|
| `semantic-debt`（本仓库） | 代码、语义层、运行日志、结果和决策记录 |
| [`semantic-debt-eval`](https://github.com/lalalagugugu/semantic-debt-eval) | 题目、参考答案、题目划分和审计材料 |

实验期间两个仓库分开，是为了让写语义层的会话看不到题目。

本仓库主要目录：

| 目录 | 内容 |
|---|---|
| `semantic/`、`render/` | 语义层源文件和渲染脚本 |
| `harness/` | 调用模型、执行查询、评分 |
| `runs/` | 每次运行的精简日志，索引见 `runs/INDEX.md` |
| `reports/` | 结果表、校验报告和独立复核（`reports/final/recheck.md`） |
| `decisions/`、`tasks/` | 设计决定、用户裁决和任务记录 |

`AGENTS.md`、`START-HERE.md` 和 `templates/` 是实验期间给 coding agent 和操作者用的，保留下来作为过程记录。

实验记录里的「人工判定」多数指 AI 会话逐条判断，区别于脚本的确定性评分，不是人判的。人做的裁定写作「用户裁决」。分工见报告的实验描述。

## 复现

需要 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。先把两个仓库克隆到同一级目录，并设置环境变量：

```bash
git clone https://github.com/lalalagugugu/semantic-debt.git
git clone https://github.com/lalalagugugu/semantic-debt-eval.git
cd semantic-debt
export SEMDEBT_MAIN_DIR="$PWD"
export SEMDEBT_EVAL_DIR="$PWD/../semantic-debt-eval"
export SEMDEBT_DATA_DIR="$PWD/../data"   # 放在仓库之外
```

**重算报告数字：** 不需要数据，也不调用模型。

```bash
python3 scripts/t19a_v7_numbers.py > "$TMPDIR/numbers.md"
cmp "$TMPDIR/numbers.md" reports/results/t19a-v7-numbers.md
```

脚本把结果写到标准输出。`cmp` 没有输出，就说明和仓库里的结果逐字节一致。

逐次标签在 `runs/20261031-T31-v5-rulings-01/`，总表在 `reports/results/accuracy-v5.md`。独立复核的脚本在 `reports/recheck/`。

**导入数据：** 数据不随仓库分发。按 [data/README.md](data/README.md) 从 Kaggle 下载并核对 sha256，然后导入：

```bash
uv run python data/load.py
uv run python data/export_parquet.py
```

**离线重评：** 需要原始回包，解压到 `$SEMDEBT_DATA_DIR/runs-raw/`。回包在 [Release midterm-v1](https://github.com/lalalagugugu/semantic-debt/releases/tag/midterm-v1)。先把题库切到报告用的版本：

```bash
git -C "$SEMDEBT_EVAL_DIR" checkout eval-v1.3
uv run python -m harness.rescore --source 20261018-T13-sql-direct-01 --cell SQL-L1 --run-id <新的-run-id> --eval-tag eval-v1.3
```

这一步只跑确定性自动评分，得到的不是报告的准确率。主表上 SQL-L1 的自动评分是 202/294 = 68.7%，报告是 250/294 = 85.0%，差额来自后续的规则放行和逐条内容判定，依据见 `decisions/2026-10-31-v7-content-review-rulings.md`。最终标签在 `runs/20261031-T31-v5-rulings-01/`，上面的重算步骤用的就是它们。判 judge 题和内容判定没有一键命令。

**重新调用模型：** 需要付费的 DeepSeek API key，且只从环境变量 `DEEPSEEK_API_KEY` 读取。入口见 [harness/README.md](harness/README.md)。模型服务端会更新，结果不一定相同。

## 许可

代码用 [MIT](LICENSE)。报告、语义层、日志等内容用 CC BY 4.0，范围和例外见 [LICENSE-CONTENT.md](LICENSE-CONTENT.md)。

## 致谢

- 100 道题改写自 [Cube semantic-layer-benchmark](https://github.com/cubedevinc/semantic-layer-benchmark)。来源说明见 [vendor/cube/NOTICE.md](vendor/cube/NOTICE.md)。
- 数据来自 Kaggle 上的 [Cleaned Contoso Dataset](https://www.kaggle.com/datasets/bhanuthakurr/cleaned-contoso-dataset)，底层是微软的 ContosoRetailDW 示例。
