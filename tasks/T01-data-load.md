# T01 数据下载、导入 chDB、导出 Parquet

- 状态：已完成（PR 待合并）
- 负责：Claude Code
- 模式：盲（`scripts/start-card.sh T01`）
- 依赖：T00；T01a（`vendor/cube/retail_schema.sql` 已合并）；用户已把数据 zip 放到 `$SEMDEBT_DATA_DIR/raw/`
- 预算：0（不调用 DeepSeek）

## 目标

在 Mac 上用 chDB 复原外部基准使用的 Contoso 零售数仓（25 张表），为后续所有卡提供同一份数据。与外部基准参考结果的一致性校验由 Codex 在 T03 第一步做，本卡不需要、也不能看题目。

## 第 0 步：隔离验证

按 `scripts/verify-isolation.md` 逐项执行，结果写进 `decisions/isolation-check.md`。任何一项不符合预期（尤其是能读到 `$SEMDEBT_EVAL_DIR`），立即停止，告诉用户。

## 数据来源

- 首选：Kaggle「Cleaned Contoso Dataset」，<https://www.kaggle.com/datasets/bhanuthakurr/cleaned-contoso-dataset>。外部基准的论文写明用的是它（微软 ContosoRetailDW 的 CSV 版）。用户手动下载 zip 放到 `$SEMDEBT_DATA_DIR/raw/`。
- 备选：Hugging Face `jocapc/ContosoRetailsDW`（MIT 许可，25 张表，每表一个 zip，竖线分隔）。只在首选与建表语句对不上时，经用户同意、由用户下载后使用（盲模式不能上网抓取）。
- 先核对：首选数据集的表和列能否与 `vendor/cube/retail_schema.sql` 的 25 张表一一对上（建表语句里没有的列，如加载批次、加载时间，可以丢弃）。对不上就停下，把差异列给用户。

## 交付物

1. `data/load.py`：解压、按 `vendor/cube/retail_schema.sql` 建库建表（库名 `retail`，与外部基准一致），导入 chDB，持久化在 `$SEMDEBT_DATA_DIR/chdb/`。
2. `data/export_parquet.py`：25 张表导出为 `$SEMDEBT_DATA_DIR/parquet/<表名>.parquet`。
3. `data/build_chdb_copy.py <目标目录>`：从 Parquet 重建一份独立的 chDB 库（供题库侧使用 `$SEMDEBT_DATA_DIR/chdb-eval`，避免两个进程同时打开同一个目录）。
4. `data/README.md`：数据集名称、链接、下载日期、许可条款（问用户页面上写的是什么）、复现步骤。
5. `reports/validation/data_load.md`：25 张表的行数、每张事实表主要金额列的合计、日期范围。

## 验收

- 一条命令完成导入；在一台干净的机器上按 `data/README.md` 能复现。
- 25 张表全部导入，行数写进报告。

## 不能做

- 不要读取 `$SEMDEBT_EVAL_DIR`，不要克隆外部基准仓库，不要上网查外部基准的题目或结果。
- 不要把原始数据、Parquet、chDB 目录提交进仓库。

## 用户确认

- [x] 数据 zip 已放到 `$SEMDEBT_DATA_DIR/raw/`（`archive.zip`，2026-10-13 下载，25 个 CSV）。
- [x] 告诉 agent 页面上的许可条款：**CC0: Public Domain**（用户 2026-10-14 答，已记在 `data/README.md`「数据来源与许可」，不必再问）。
- [ ] 合并 PR。
- [ ] 裁决 `decisions/open-questions.md` 的 Q3（盲模式 deny 把本 clone 的 `runs/` 也挡住，`uv run pytest` 2 红）与 Q4（MCP server 仍能联网，T08 之前要堵上）。

## 记录（完成后填写）

- 产出：
  - `decisions/isolation-check.md`：第 0 步隔离验证的实测记录（A 组 10 项全部被拒；B 组 B4 失败，原因是盲模式的 `Read(./runs/**)` 连本 clone 自己的 `runs/README.md`、`runs/INDEX.md` 一起挡了，已记 Q3，没动设置）。
  - `data/ddl.py`：解析 `vendor/cube/retail_schema.sql`，三个脚本共用的表清单、列序与列类型。
  - `data/load.py`：解压 → 核对 25 张表的表头与 DDL → 建库建表 → 按位置导入 chDB（`$SEMDEBT_DATA_DIR/chdb`，库名 `retail`）。一条命令，本机约 10 秒。
  - `data/export_parquet.py`：25 张表 → `$SEMDEBT_DATA_DIR/parquet/<表名>.parquet`（共 359,609,041 字节）。
  - `data/build_chdb_copy.py <目标目录>`：从 Parquet 重建独立的 chDB 库；已建 `$SEMDEBT_DATA_DIR/chdb-eval`，行数与主库逐表一致。
  - `data/validation_report.py` + `reports/validation/data_load.md`：25 张表行数（共 34,326,191 行）、8 张事实表 24 个金额/数量列的定点合计、每张带 `DateKey` 的表的日期范围。
  - `data/README.md`：数据来源、许可（CC0）、sha256（已复核一致）、列核对结果、复现步骤。
  - `tests/test_ddl_contract.py`：3 条测试，守住「DDL 解析出 25 张表、structure 能喂给 chDB、`DimCustomer` 的空表头列确实是第 1 列」。
- 偏离与理由：
  - **加了 `data/ddl.py` 和 `data/validation_report.py`**，卡上只列了 3 个脚本。前者是三个脚本共用的 DDL 解析（否则表清单要抄三遍）；后者让校验报告可一条命令重跑，而不是手抄数字。
  - **`pyproject.toml` 加了 `chdb>=3.0` 依赖**（实际装到 4.4.0，内嵌 ClickHouse 26.9.2.1），`uv.lock` 同步更新。
  - **`DimCustomer.csv` 第 1 列表头为空**（Kaggle 导出写出了 pandas 行号索引），DDL 把它叫 `RowNum`。列数、列序完全一致，故按位置导入，并把这处差异写死在 `load.py` 的 `UNNAMED_OK` 里，换数据源会立刻报错。其余 24 张表列名列序与 DDL 逐列一致。详见 `data/README.md`。
  - **B4「测试能跑」未通过**：2 条 T00 的布局测试要 `stat` `runs/` 下的文件，被盲模式的 deny 挡住。按硬规则 1 没有放宽隔离，也没有改 T00 的测试，记成 Q3 等裁决。其余 35 条测试通过。
  - **隔离清单外的发现（Q4）**：内置 WebSearch/WebFetch 确实被拒，但会话里仍挂着能联网的 MCP server（dashscope 网页搜索、两套浏览器自动化、Google Drive、Notion），不受项目 `deny` 管辖。本卡没用它们、也不需要联网，但 T08 之前必须堵上。
  - **B8 换了等价命令**：本机 uv 没有 `pip download` 子命令，改用 `uv pip install --dry-run --no-cache cowsay` 验证 pypi 可达。
  - 没有用备选数据源（Hugging Face `jocapc/ContosoRetailsDW`）：首选数据集与建表语句对得上。
- 工时：约 1.5 小时（含隔离验证与报告）。
