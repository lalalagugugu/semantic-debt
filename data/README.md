# data

下载、导入、导出的**脚本**放这里；**数据本身不入库**（硬规则 4）。

数据一律落在仓库之外的 `$SEMDEBT_DATA_DIR`（默认 `~/semdebt/data`，本机实际为 `~/dev/semdebt/data`，以环境变量为准）：

| 路径 | 内容 | 谁建 |
|---|---|---|
| `$SEMDEBT_DATA_DIR/raw/` | Kaggle 下载的 Contoso zip 或解压目录 | 用户（START-HERE 第 3 步） |
| `$SEMDEBT_DATA_DIR/parquet/` | 导入后导出的 Parquet | T01 |
| `$SEMDEBT_DATA_DIR/chdb/` | chDB 数据目录（主用） | T01 |
| `$SEMDEBT_DATA_DIR/chdb-eval/` | chDB 数据目录（题库侧副本，从 Parquet 重建） | T01 的脚本，题库侧用 |
| `$SEMDEBT_DATA_DIR/runs-raw/<run-id>/` | 模型原始响应（含思考内容） | T11 起 |

脚本只通过 `SEMDEBT_DATA_DIR` 找路径，不得写死路径。同一个 chDB 数据目录不要被两个进程同时打开（硬规则 9）。

计划中的文件（T01）：`download.md`（人工下载说明）、`load_chdb.py`、`export_parquet.py`、`rebuild_eval_chdb.py`。
