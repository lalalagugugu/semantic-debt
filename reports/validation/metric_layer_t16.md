# T16 Cube 接口与多阶段指标验证

复现：`uv run python scripts/verify_metric_layer.py`。不读题库、不调用模型。

- Cube Core / Cube SQL / Cube Store：`1.8.6`；ClickHouse：`25.8.20.4`。
- 两种接口查询冻结的 T10 模型，未改语义层或渲染器；Tesseract 已开启。
- 基线独立使用导入事实表的普通 SQL；2009 月同比、月环比、渠道/门店占比、2009 对 2008 同店增长。
- 同比、环比、占比有线上与全渠道两个调用名，故四类指标共 7 个成员、14 项接口核对。
- 比较行数、完整分组键集合及每个数值，容差 `rel_tol=abs_tol=1e-8`；这仅用于部署核验，不改变实验评分。
- 通过 14/14；明确接口限制 0 项。

| 接口 | 指标 | 行数 | 结果 | 错误分类 |
|---|---|---:|---|---|
| cube_sql | `sales.sales_amount_yoy_pct` | 12 | 通过 | — |
| cube_json | `sales.sales_amount_yoy_pct` | 12 | 通过 | — |
| cube_sql | `sales.sales_amount_mom_pct` | 12 | 通过 | — |
| cube_json | `sales.sales_amount_mom_pct` | 12 | 通过 | — |
| cube_sql | `sales.sales_amount_share` | 4 | 通过 | — |
| cube_json | `sales.sales_amount_share` | 4 | 通过 | — |
| cube_sql | `online_sales.sales_amount_yoy_pct` | 12 | 通过 | — |
| cube_json | `online_sales.sales_amount_yoy_pct` | 12 | 通过 | — |
| cube_sql | `online_sales.sales_amount_mom_pct` | 12 | 通过 | — |
| cube_json | `online_sales.sales_amount_mom_pct` | 12 | 通过 | — |
| cube_sql | `online_sales.sales_amount_share` | 3 | 通过 | — |
| cube_json | `online_sales.sales_amount_share` | 3 | 通过 | — |
| cube_sql | `sales.same_store_sales_growth_pct` | 1 | 通过 | — |
| cube_json | `sales.same_store_sales_growth_pct` | 1 | 通过 | — |

完整查询、基线与实际值见同目录 `metric_layer_t16.json`。本报告只证明这些验证查询可执行且结果一致，
不代表任意 SQL/JSON 查询均被支持；未运行题集，未估算或填写实验准确率、拒答率、20% 接口限制门槛。

## 镜像标识

- cube: `cubejs/cube@sha256:69707e09d95aa17a81b9f98edea22b45f77ab2cb6234bc953707aece6f1b0bf6`
- clickhouse: `clickhouse/clickhouse-server@sha256:3124282c0c60bf3c1381a653475e82573d4f9a8dd5a487eb7371dcb91b3080c3`
