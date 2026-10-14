# T01 数据下载、导入 chDB、导出 Parquet

- 状态：未开始
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

- [ ] 数据 zip 已放到 `$SEMDEBT_DATA_DIR/raw/`。
- [ ] 告诉 agent 页面上的许可条款。
- [ ] 合并 PR。

## 记录（完成后填写）

- 产出：
- 偏离与理由：
- 工时：
