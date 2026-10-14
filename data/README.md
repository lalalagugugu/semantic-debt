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

## 数据来源与许可（用户提供，T01 的输入）

| 项 | 值 |
|---|---|
| 数据集 | Cleaned Contoso Dataset（微软 ContosoRetailDW 的 CSV 版） |
| 链接 | <https://www.kaggle.com/datasets/bhanuthakurr/cleaned-contoso-dataset> |
| 许可 | **CC0: Public Domain**（用户 2026-10-14 从 Kaggle 页面抄给 T00） |
| 下载日期 | 2026-10-13 |
| 文件 | `$SEMDEBT_DATA_DIR/raw/archive.zip`，487,695,063 字节 |
| sha256 | `d5f2812d104d83330b19ad7ff0a4efd787b3a317dd842bd0ab0ed959396ae642` |
| 内容 | 25 个 CSV，解压后 2,482,140,744 字节；17 张维度表（`DimAccount`…`DimStore`）+ 8 张事实表（`FactOnlineSales`、`FactSales`、`FactSalesQuota`、`FactStrategyPlan`、`FactInventory`、`FactExchangeRate`、`FactITMachine`、`FactITSLA`） |

表名与张数由 `unzip -l` 核对过（25 张，与设计一致）；**列是否与 `vendor/cube/retail_schema.sql` 对得上还没核**，那是 T01 的事。T01 接着写下载与复现步骤。


计划中的文件（T01）：`download.md`（人工下载说明）、`load_chdb.py`、`export_parquet.py`、`rebuild_eval_chdb.py`。
