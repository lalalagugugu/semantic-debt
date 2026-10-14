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

表名与张数由 `unzip -l` 核对过（25 张，与设计一致）。sha256 由 T01 复核过一致。

### 列与建表语句的核对结果（T01，2026-10-14）

25 张表的**列名、列数、列序**与 `vendor/cube/retail_schema.sql` 全部一致，只有一处表头差异：

- `DimCustomer.csv` 的第 1 列表头为空（Kaggle 导出把 pandas 的行号索引写了出来），DDL 把这一列叫 `RowNum`。按位置一一对应，取值为 0…18868。

因为列序完全一致，导入走的是**按位置**插入（`file(..., 'CSV', <DDL 推出的 structure>)` + `input_format_csv_skip_first_lines = 1`），空表头不会让任何字段错位。这处差异写死在 `data/load.py` 的 `UNNAMED_OK` 里；换成别的数据源时核对会立刻报错，不会悄悄放过。

没有用到备选数据源（Hugging Face `jocapc/ContosoRetailsDW`）。

## 复现步骤

前置：Python 3.11+、`uv`、约 10 GB 空闲磁盘（CSV 2.5 GB + chDB 两份 + Parquet 0.36 GB）。
`SEMDEBT_DATA_DIR` 必须已设（见 `AGENTS.md`「环境」）。

1. **人工下载**（脚本不下载：Kaggle 要登录，盲模式也不许上网）。
   打开 <https://www.kaggle.com/datasets/bhanuthakurr/cleaned-contoso-dataset>，点 Download，
   把得到的 `archive.zip` 放到 `$SEMDEBT_DATA_DIR/raw/`。校验：

   ```sh
   shasum -a 256 "$SEMDEBT_DATA_DIR/raw/archive.zip"
   # d5f2812d104d83330b19ad7ff0a4efd787b3a317dd842bd0ab0ed959396ae642
   ```

   Kaggle 日后更新数据集会导致哈希变化；对不上就停下问用户，不要自行往下走。

2. **导入**（解压 + 核对表头 + 建库建表 + 导入，一条命令，约 10 秒）：

   ```sh
   uv sync
   uv run python data/load.py           # 加 --force 重新解压并重建；加 --check-only 只核对表头
   ```

   产物：`$SEMDEBT_DATA_DIR/raw/csv/`（25 个 CSV）、`$SEMDEBT_DATA_DIR/chdb/`（库名 `retail`）。

3. **导出 Parquet**：

   ```sh
   uv run python data/export_parquet.py        # → $SEMDEBT_DATA_DIR/parquet/<表名>.parquet
   ```

4. **给题库侧建独立的 chDB 副本**（硬规则 9：一个数据目录不能两个进程同时开）：

   ```sh
   uv run python data/build_chdb_copy.py "$SEMDEBT_DATA_DIR/chdb-eval"   # 已存在时加 --force
   ```

5. **校验报告**（行数、事实表金额合计、日期范围）：

   ```sh
   uv run python data/validation_report.py     # → reports/validation/data_load.md
   ```

本机实测：第 2–5 步合计不到 20 秒（M 系列 Mac），导入 25 张表共 34,326,191 行。

## 怎么查这份数据

```python
from chdb import session
sess = session.Session("<$SEMDEBT_DATA_DIR>/chdb")      # 或 chdb-eval
print(sess.query("SELECT count() FROM retail.FactSales", "CSV"))
sess.close()                                             # 用完必须关，否则别的进程打不开
```

## 本目录的文件

| 文件 | 作用 |
|---|---|
| `ddl.py` | 解析 `vendor/cube/retail_schema.sql`，另外两个脚本共用的表清单与列类型 |
| `load.py` | 解压 → 核对表头 → 建库建表 → 导入 chDB |
| `export_parquet.py` | chDB → Parquet |
| `build_chdb_copy.py` | Parquet → 另一份独立的 chDB 数据目录 |
| `validation_report.py` | 生成 `reports/validation/data_load.md` |
