# 从这里开始

这是给人（Yu）看的操作手册：把种子文件放进仓库、下载数据、启动第一张卡，以及之后每张卡怎么启动。给 agent 的规则在 `AGENTS.md`，你不用转述给它们。

**关于路径**：本文里的命令一律用环境变量（`$SEMDEBT_MAIN_DIR` 等），**环境变量是准绳**。本机实际装在 `~/dev/semdebt/` 下，不是早先文档里写的 `~/semdebt/`；想整体搬家，只改第 4 节那一个 `SEMDEBT_BASE`，其余不用动。第 1–4 节是一次性的，已于 2026-10-14 做完，留档备查。

## 0. 先准备好

| 东西 | 什么时候要 | 说明 |
|---|---|---|
| Mac 上的 git、Claude Code、Codex CLI | 现在 | 两个工具都要登录好 |
| GitHub 上的两个私有仓库 | 现在 | `semantic-debt`、`semantic-debt-eval`，你已经建好 |
| Kaggle 账号 | 下载数据时 | 只用来下载 |
| uv（Python 包管理） | T00 | T00 会检查，缺了会告诉你一条安装命令 |
| Docker Desktop | T16 | Codex 搭指标层时用 |
| DeepSeek API key | T11 | 只放在环境变量里 |
| Windows 电脑上的 Power BI Desktop | T17 | 不要用公司的 Power BI 租户 |

## 1. 建目录，克隆两个仓库（一次性）

在 Mac 的终端里逐行运行。`<你的用户名>` 换成你的 GitHub 用户名。

```bash
export SEMDEBT_BASE="$HOME/dev/semdebt"     # 想放别处就改这一行
mkdir -p "$SEMDEBT_BASE/data/raw" "$SEMDEBT_BASE/cards"
cd "$SEMDEBT_BASE"
git clone https://github.com/<你的用户名>/semantic-debt.git
git clone https://github.com/<你的用户名>/semantic-debt-eval.git
```

两个仓库必须是同级目录：T01a 要在它们的上一级同时往两个仓库提交。

如果仓库是空的，git 会提示 `You appear to have cloned an empty repository`，这是正常的。

## 2. 放入种子文件，提交并推送

假设种子包下载到了 `~/Downloads/semantic-debt-seed-v5.zip`。

```bash
cd "$SEMDEBT_BASE"
unzip ~/Downloads/semantic-debt-seed-v5.zip -d "$SEMDEBT_BASE/_seed"
cp -R "$SEMDEBT_BASE/_seed/semantic-debt/." "$SEMDEBT_BASE/semantic-debt/"
cp -R "$SEMDEBT_BASE/_seed/semantic-debt-eval/." "$SEMDEBT_BASE/semantic-debt-eval/"
rm -rf "$SEMDEBT_BASE/_seed"

cd "$SEMDEBT_BASE/semantic-debt"
git add -A && git commit -m "Seed from design v5" && git branch -M main && git push -u origin main

cd "$SEMDEBT_BASE/semantic-debt-eval"
git add -A && git commit -m "Seed from design v5" && git branch -M main && git push -u origin main
```

`cp -R 目录/.` 的写法会连隐藏文件（`.gitignore`、`.claude/`）一起复制，别改成 `*`。

两个仓库为什么分开、为什么不再用子模块：题库仓库里有题目和参考答案，写语义层的 agent 不能看到。两个仓库是并列的文件夹，主仓库的程序通过环境变量找到题库，每次运行把题库的提交号写进日志。

## 3. 下载数据

1. 打开 <https://www.kaggle.com/datasets/bhanuthakurr/cleaned-contoso-dataset>，登录 Kaggle，点 Download，得到一个 zip。这是外部基准（Cube）论文里写明使用的数据集：微软 ContosoRetailDW 的 CSV 版，25 张表。
2. 把 zip 移到 `$SEMDEBT_DATA_DIR/raw/`（本机 `~/dev/semdebt/data/raw/`），不用解压；已经解压了也行，把解压出的文件夹一起放进去（约 2.5 GB）。
3. 看一眼页面上的 License 写的是什么，T01 会问你。

如果页面打不开、或者表不是 25 张，告诉 T01 的 agent。备选来源是 Hugging Face 上的 `jocapc/ContosoRetailsDW`（MIT 许可），T01 会处理。

## 4. 设环境变量（一次性）

```bash
cat >> ~/.zshrc <<'EOF'
export SEMDEBT_BASE="$HOME/dev/semdebt"
export SEMDEBT_DATA_DIR="$SEMDEBT_BASE/data"
export SEMDEBT_EVAL_DIR="$SEMDEBT_BASE/semantic-debt-eval"
export SEMDEBT_MAIN_DIR="$SEMDEBT_BASE/semantic-debt"
# export DEEPSEEK_API_KEY="..."   # 到 T11 再填，去掉行首的 #
EOF
source ~/.zshrc
```

这几个变量就是准绳：所有脚本和 agent 都只认它们。另外两个可选变量有默认值，一般不用设：`SEMDEBT_CARDS_DIR`（每张卡的 clone 放哪，默认是主工作区同级的 `cards/`）、`SEMDEBT_VENDOR_DIR`（外部基准克隆到哪，默认同级的 `_vendor/`）。

## 5. 启动第一张卡：T00

```bash
cd "$SEMDEBT_MAIN_DIR"
claude "执行任务卡 T00"
```

第一次在一个文件夹里启动 Claude Code，它会问是否信任这个文件夹，选「是」。T00 会搭好仓库骨架，写好启动脚本 `scripts/start-card.sh`，最后请你合并它的 PR。

## 6. 之后每张卡怎么启动

```bash
"$SEMDEBT_MAIN_DIR"/scripts/start-card.sh T01
```

先看一眼它要做什么、不想它真动手，加 `--dry-run`；想看所有卡，`--list`。

脚本会按 `tasks/cards.yaml` 准备好这张卡的工作目录和设置，然后打印一条启动命令，复制运行即可。例如：

- Claude Code 的卡：`cd "$SEMDEBT_BASE/cards/T01" && claude "执行任务卡 T01"`
- Codex 的题库卡：`cd "$SEMDEBT_EVAL_DIR" && codex "执行任务卡 T03"`
- Codex 的 T01a：`cd "$SEMDEBT_BASE" && codex "执行任务卡 T01a，卡片在 semantic-debt-eval/tasks/T01a-vendor-split.md"`（它要同时往两个仓库提交，所以在上一级启动）
- Codex 的主仓库卡（T02、T16、T20）：`cd "$SEMDEBT_BASE/cards/T02" && codex "执行任务卡 T02"`

脚本打印的就是展开好绝对路径的那一行，照抄即可，不用自己拼。

几点说明：

- **盲模式、普通模式不用你告诉 agent。** 模式由脚本写进那张卡文件夹里的设置文件决定，你在那个文件夹里启动 Claude Code，设置就自动生效；agent 开工时会自检。你只要别做两件事：在主工作区 `$SEMDEBT_MAIN_DIR` 里启动除 T00 以外的卡；启动时加 `--add-dir` 把题库加进来。
- **Claude Code 第一次在新文件夹启动**会问是否信任这个文件夹，选「是」，否则项目设置不会生效。
- **Codex 可能会请求批准**联网或在工作区外写文件（安装依赖、推送分支）。这些可以批准。G1 之前如果它要读主仓库 `semantic/` 下除 `conventions.md` 以外的文件，拒绝。

顺序看 `tasks/BOARD.md` 和设计文档里的执行图。开头几步是：

1. Claude Code：T00
2. Codex：T01a（把外部基准的文件分到两个仓库；在两个仓库的上一级启动）
3. 你：看一眼约定清单第 12 条（`semantic/conventions.md`），下载数据
4. Claude Code：T01（数据导入；第一步会做隔离验证）
5. Codex：T02、T03 → 你过 G0
6. Claude Code：T08 → T09 → T10，同时 Codex 做 T04、T05 → 你过 G1

## 7. 每张卡做完

1. agent 会推送一个分支并开 PR，或者告诉你分支名。
2. 你在 GitHub 网页上看 PR，没问题就点 Merge。
3. 回到主工作区同步：`cd "$SEMDEBT_MAIN_DIR" && git pull`（题库卡则在 `$SEMDEBT_EVAL_DIR` 里 `git pull`）。
4. 如果 agent 说推送失败，在那张卡的目录里运行 `git push -u origin HEAD`。

## 8. 检查点由你把关

| 检查点 | 你看什么 | 通过后 |
|---|---|---|
| G0 | 数据校验报告和评分器校验报告里，不一致的地方都有解释 | 在 BOARD 里把 G0 标为通过 |
| G1 | 语义层文件齐全；汇总层的报表需求你看过 | T10 的 agent 打 tag `semantic-v1` |
| G2 | 两家核对的参考答案不一致处都已裁决；划分和覆盖标注合理 | Codex 在题库仓库打 tag `eval-v1` |
| G3 | 试跑结果、选哪个模型 | T12 的 agent 打 tag `harness-v1` |
| G4 | 结论 | 准备公开 |

**过目汇总层的报表需求时**（T08 中途）：只看它像不像一家零售公司常规的经营报表，不要按你记得的题目增删。否则汇总层就不是「盲写」的了。

## 9. 出问题时

- agent 说「这张卡不归我」或「启动位置不对」：照它给的命令重新启动。
- 盲模式的 agent 报告「能读到题库」：立刻结束这个会话，不要继续；把情况告诉我或记进 `decisions/`。
- 任何要花钱的命令都会先显示调用次数和预计费用（dry run）；超过 BOARD 里的预算上限，agent 会停下来问你。
- Windows（T17、T18）：在 Windows 上也克隆两个仓库。如果那台电脑上用不了 Claude Code，T17 卡里写了替代做法。
