# T00 仓库骨架、隔离设置、启动脚本

- 状态：已完成（PR 待合并）
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
- [ ] 裁决 `decisions/open-questions.md` 第 1 条：目录实际在 `~/dev/semdebt/`，而 `AGENTS.md`、`START-HERE.md` 写的是 `~/semdebt/`。代码已只认环境变量，不受影响；要不要把两份文档改成「以环境变量为准」？
- [ ] 裁决 `decisions/open-questions.md` 第 2 条：本机没有 `gh`。装一个（`brew install gh && gh auth login`），还是以后每张卡都由 agent 推分支、你在 GitHub 网页上开 PR？

## 记录（完成后填写）

- 产出：
  - 骨架：`data/`、`vendor/`、`render/`、`build/`、`harness/`、`runs/`、`reports/`、`tests/` 新建，各带 `README.md`（写明用途、计划中的文件、相关硬规则）；`docs/`、`tasks/`、`semantic/` 补上 `README.md`。
  - `pyproject.toml`（uv 管理，`requires-python = ">=3.11"`，`package = false`，dev 组只有 pytest）。
  - `tests/test_repo_layout.py`：34 个用例。测骨架完整、`cards.yaml` 与 `BOARD.md` 覆盖同一批卡号、卡片文件存在、`cards.yaml` 用到的模式都已实现、盲模式卡只归 Claude Code、普通模式卡都有前置检查点、两份模板渲染后是合法 JSON 且盲模板确实禁掉题库与上网、提交的 `.claude/settings.json` 仍开着沙箱与禁读、`.gitignore` 仍把数据与 build 挡在外面、代码里没有写死的绝对路径、没有疑似 API key。另有一条跨实现校验：`cards.yaml` 的 bash 解析器（脚本内）与 Python 解析器（测试内）输出必须逐行一致。
  - `scripts/start-card.sh`：实现 `cards.yaml` 里全部 10 种模式；另有 `--list` 和 `--dry-run`。
  - `scripts/verify-isolation.md`：A 组 10 项（必须被拒绝，含绕道读 git 对象、WebSearch/WebFetch、`git clone`）、B 组 8 项（必须能用），以及「A 组有一项没被拒就立刻停止、不要看内容」的处置流程和结果表模板。
  - `decisions/open-questions.md`、`runs/INDEX.md`、`decisions/isolation-settings.md` 三个模板/记录。
  - `tasks/BOARD.md` 的 T00 状态已更新。
- 偏离与理由：
  1. **目录布局**：实际是 `~/dev/semdebt/*`，不是文档里的 `~/semdebt/*`。脚本不写死路径，一律从 `SEMDEBT_MAIN_DIR` / `SEMDEBT_EVAL_DIR` / `SEMDEBT_DATA_DIR` 来；卡片目录取主工作区的同级 `cards/`（可用 `SEMDEBT_CARDS_DIR` 覆盖），外部基准目录取同级 `_vendor/`（可用 `SEMDEBT_VENDOR_DIR` 覆盖）。文档没动，等用户裁决（open-questions 第 1 条）。
  2. **新增 `tests/` 目录**：不在 `AGENTS.md` 的目录清单里，但验收要求 `uv run pytest`。测试内容限于仓库自身的约定，不碰数据与模型。
  3. **`.gitignore` 的 `build/`** 改成 `build/*` 加 `!build/README.md`：原写法会让 `build/README.md` 也被忽略，而验收要求每个目录都有 README。产物照旧全部被忽略。
  4. **`--dry-run` 是额外加的**：卡片没要求。加它是因为这张卡自己不能 `git clone`、也不得读题库，而验收要求「用户运行 `start-card.sh T01` 能得到正确的 clone 和设置」——`--dry-run` 让这些路径可以在不触碰题库、不建目录的前提下被检验。`--dry-run` 下所有 git 写操作只打印；对主仓库以外的仓库连读都不做（`origin_url`、`branch_in_place` 都有 dry-run 短路）。
  5. **`packet` 模式额外复制 `.claude/settings.json`**：卡片只说「复制 `semantic/` 和调优包、写盲模式设置」。但 packet 目录不是 clone，拿不到仓库里提交的那份项目设置（沙箱、禁读工作目录以外），不复制的话 B 角就没有沙箱。去掉数据目录放行的做法是删掉 `additionalDirectories` 一行。
  6. **没有用 `gh pr create`**：本机没装 `gh`。分支已推送，PR 由用户在 GitHub 网页上开（open-questions 第 2 条）。
  7. **隔离只做了可做的部分**：卡片禁止本卡读取 `$SEMDEBT_EVAL_DIR`，所以 `blockReadsOutsideWorkingDirectories` 和题库 deny 规则没有在 T00 实测，留给 T01 第一步。已在 `decisions/isolation-settings.md` 写明「T01 通过之前不要把隔离当成已验证」。`.claude/settings.json` 一个字没改。
- 工时：约 1 小时（一个会话）。
