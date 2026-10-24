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

- **以前的盲写卡不受影响**（用户 2026-10-23 列出数据目录各项的建立时间，协调会话比对）：
  - 盲模式的卡是 T01、T08、T09、T10（G1 之前）和 T22（本次）。G1（`semantic-v1`）在 2026-10-16 01:18。
  - G1 之前数据目录里只有 `raw`（10-14）、`parquet`（10-14）、`chdb`（10-14）、`chdb-eval`（10-15，从 Parquet 重建的数据副本，不含题目）。
  - 含题目或模型输出的最早一批都在 G1 之后：`runs-raw`（10-16 08:52）、`rules-backfill`（10-16 10:40）、`t05-finalize`（10-16 13:13）、`anchor-refs`（10-16 13:15）、第一个 `eval-ro-*`（10-16 19:15）。
  - G1 之后到 T22 之前没有盲模式会话（之后对 `semantic/` 的改动都在普通模式下）。所以缺口只影响 T22，T22 的处置见上。
- 修复合并后，T22 用新设置重启，按 `verify-isolation.md` 重做 A 组（含 A12）与 B 组，结果记入 `decisions/isolation-check.md`；全量测试由 T22 在 B4 跑。

## 补充（2026-10-24）：主仓库里的 C13 第 4 级说明含题面

- **发现**：T22 重做自检时（`decisions/isolation-check.md` 第 4 节），B4 的 `tests/test_harness.py::test_ladder_level4_examples_are_tuning_questions_only` 在题库读不到时没有跳过，而是报 `KeyError`，键是 `harness/syntax_ladder/clickhouse_sql_t4.md` 里第一道示例题的题面，于是一道**调优题**的题面进了 T22 的会话。该文件按 C13 设计含 6 道调优题的题面与参考 SQL（Q60、Q12、Q78、Q82、Q50、Q49），自 2026-10-19 起就在主仓库，盲会话的 clone 里也有。T22 没有打开该文件，也没有使用这道题面。
- **处置**：
  1. 盲模式模板对卡自己的 clone 禁读这个文件，规则和沙箱两层都加；`start-card.sh` 新增占位符 `${SEMDEBT_CARD_DIR}`，渲染成卡的工作目录。
  2. `needs_eval` 改为真去列一次题库目录，读不了就跳过，免得测试报错把题面带进输出。
  3. T22 的产出仍然有效。L1+、L3a 报告时把这道题单列说明（结果给出含与不含的两种口径）。T22 不知道是哪一道，按文件顺序是 Q1 级的第一道。
- **数据查询**：T22 在 A12 实测之前查了 `$SEMDEBT_DATA_DIR/parquet`，这是放行范围内、只有数据的目录，**认可，不重做**。
