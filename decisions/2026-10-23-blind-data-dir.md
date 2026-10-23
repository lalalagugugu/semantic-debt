# 2026-10-23 盲模式收窄数据目录的放行（隔离缺口）

- 裁决人：用户，2026-10-23（经协调会话：「同意修隔离」）
- 约束：`templates/claude-settings.blind.json`（盲模式与 packet 模式共用）、`scripts/start-card.sh`、`scripts/verify-isolation.md`；T22
- 来源：T22 开工后报告（卡片「偏离与理由」，T22-work 0a33ec6）

## 缺口

盲模式模板把**整个** `$SEMDEBT_DATA_DIR` 放进 `additionalDirectories`，只禁读了 `runs-raw/`。G1 之后，数据目录里陆续放进了盲会话不该看到的东西：题库只读副本 `eval-ro-*`（11 个，含 `eval-ro-eval-v1.2`，等于整个题库）、`handoff-*`、`scorer-corpus`、`anchor-refs`、各卡的收尾与抽检目录、运行输出（`t13-*.out` 等）。

T22 自检时读题库主目录被拒（A 组通过），但 `ls "$SEMDEBT_DATA_DIR"` 列出了上述顶层名字。T22 只列了顶层、未打开任何子目录或文件，看到后即停用数据目录。第 1–2 步的产出只依据本仓库文件，**认定有效**。

## 修复

1. 盲模式只放行 `raw`、`parquet`、`chdb` 三个子目录（盲写卡读数据、用 chDB 查数据需要的全部），不再放行整个数据目录；再点名禁读 `eval-ro-*`、`handoff-*`、`scorer-corpus` 作为第二层。数据目录以后新增的东西默认对盲会话不可见。
2. `start-card.sh`：已有 clone 时，`SEMDEBT_REFRESH_SETTINGS=1` 只按当前模板重写 `.claude/settings.local.json`，不动代码与分支（给 T22 用）。
3. `scripts/verify-isolation.md` 加 A12（数据目录顶层与 `eval-ro-*` 都应被拒），B3、B6 按新放行范围改写。
4. `tests/test_repo_layout.py` 加 `test_blind_template_grants_only_data_subdirs`。

packet 模式（T14-B）本来就去掉数据目录的放行，不受此缺口影响；它的 JSON 渲染错误由 T14（T14-work ab2ab69）另修。

## 待核

- **以前的盲写卡是否受影响**：要看数据目录里这些目录的建立时间是否早于 T08–T10 等盲写卡的工作时间。由用户在终端运行 `ls -ldU -D '%F %T' "$SEMDEBT_DATA_DIR"/*` 列出建立时间后，协调会话比对，结论补记在本文件。
- 修复合并后，T22 用新设置重启，按 `verify-isolation.md` 重做 A 组（含 A12）与 B 组，结果记入 `decisions/isolation-check.md`；全量测试由 T22 在 B4 跑。
