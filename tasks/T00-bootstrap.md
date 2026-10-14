# T00 仓库骨架、隔离设置、启动脚本

- 状态：未开始
- 负责：Claude Code
- 模式：主工作区（只有这张卡在 `~/semdebt/semantic-debt` 里直接启动）
- 依赖：用户已按 `START-HERE.md` 第 1–4 步把种子文件推送到两个仓库
- 预算：0

## 目标

搭好主仓库的骨架，写好每张卡的启动脚本，让之后的每张卡都能在正确的目录和模式下开工。

## 交付物

1. **骨架**：按 `AGENTS.md`「目录」建好空目录（各放一个 `README.md` 说明用途）；`pyproject.toml`（uv 管理，Python 3.11+）；`uv run pytest` 能跑（可以只有一个占位测试）；`decisions/open-questions.md`、`runs/INDEX.md` 两个空模板。
2. **`scripts/start-card.sh <卡号>`**：读 `tasks/cards.yaml`，按卡的 `mode` 准备工作目录并打印启动命令：
   - `blind` / `open`：`git clone` 主仓库（origin）到 `~/semdebt/cards/<卡号>`，新建分支 `<卡号>-work`；把对应模板里的 `${SEMDEBT_DATA_DIR}`、`${SEMDEBT_EVAL_DIR}`、`${SEMDEBT_MAIN_DIR}` 换成绝对路径，写成 `.claude/settings.local.json`；打印 `cd ~/semdebt/cards/<卡号> && claude "执行任务卡 <卡号>"`。
   - `open-eval`：克隆题库仓库到 `~/semdebt/cards/<卡号>`，打印带 `--add-dir "$SEMDEBT_DATA_DIR"` 的启动命令。
   - `packet`：建一个**不是** git clone 的目录 `~/semdebt/cards/<卡号>`，复制主工作区 `semantic/` 的当前内容和 `build/tuning-packet/` 下指定的调优包（参数传入），写入盲模式设置但**去掉**数据目录的放行；打印启动命令。
   - `codex-eval`：在题库仓库新建分支 `<卡号>-work`，打印 `cd ~/semdebt/semantic-debt-eval && codex "执行任务卡 <卡号>"`。
   - `codex-root`（只有 T01a）：把外部基准 `https://github.com/cubedevinc/semantic-layer-benchmark` 克隆到 `~/semdebt/_vendor/semantic-layer-benchmark`；把主仓库克隆到 `~/semdebt/cards/T01a-main` 并建分支 `T01a-vendor-ddl`；在题库仓库建分支 `T01a-work`；打印 `cd ~/semdebt && codex "执行任务卡 T01a，卡片在 semantic-debt-eval/tasks/T01a-vendor-split.md"`。这一步由用户在终端运行，不要在你的会话里执行（会话里禁止 git clone，也不该接触外部基准）。
   - `codex-main`：同 `blind` 的克隆方式，但不写 Claude Code 设置，打印 `codex` 启动命令。
   - `windows`、`user`：打印卡片路径和一句说明。
   - `open`、`open-eval` 模式的卡：检查主仓库是否已有 tag `semantic-v1`，没有就拒绝并提示「G1 之前不能用普通模式」。
   - 目录已存在时不覆盖，提示用户。
3. **`scripts/verify-isolation.md`**：盲模式的隔离验证清单，供 T01 第一步执行。至少包括：用读文件工具读 `$SEMDEBT_EVAL_DIR/README.md` 被拒绝；用 `cat` 读同一文件被拒绝；`ls ~/semdebt` 被拒绝或看不到题库内容；`uv run pytest` 能跑；能读写 `$SEMDEBT_DATA_DIR`；`git commit` 能成功；网页搜索被拒绝。每项记录命令与结果。
4. 更新 `tasks/BOARD.md` 的 T00 状态。

## 关于 `.claude/settings.json`

种子文件里已提交一份项目设置：打开沙箱、禁止读取工作目录以外的文件、限制网络。你的会话本身就在这套设置下运行。

- 如果 `uv`、`pytest` 等在沙箱里因为读不到某个目录而失败，可以在 `sandbox.filesystem.allowRead` / `allowWrite` 里加**工具自身的缓存或安装目录**（如 uv 的缓存），不得加入题库、数据目录以外的用户目录或整个家目录。
- 如果某项设置在当前 Claude Code 版本里不生效（例如版本过旧），停下来告诉用户升级，而不是删掉这项设置。
- 任何改动写进 `decisions/isolation-settings.md`，说明原因。

## 验收

- `uv run pytest` 通过。
- 用户在终端运行 `scripts/start-card.sh T01` 能得到正确的 clone、`.claude/settings.local.json` 和启动命令；运行 `scripts/start-card.sh T11` 在没有 `semantic-v1` 时被拒绝。
- PR 已开。

## 不能做

- 不要读取 `$SEMDEBT_EVAL_DIR` 下的任何内容；本卡不需要它。
- 不要在主仓库提交任何来自外部基准的题目、参考 SQL、语义文档或运行结果。
- 不要克隆外部基准仓库（那是 T01a 的事，由 Codex 做）。

## 用户确认

- [ ] 合并 PR。

## 记录（完成后填写）

- 产出：
- 偏离与理由：
- 工时：
