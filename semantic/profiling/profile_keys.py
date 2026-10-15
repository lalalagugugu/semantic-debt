"""键的覆盖率与基数探查：每个外键样式的列指向哪张表、有没有孤儿行、是多对一还是一对一。

L1 的 relationships 节完全由这个脚本的输出写成，不靠对 schema 的猜测。
产物：semantic/profiling/out/keys.md、semantic/profiling/out/keys.json

重跑：
    uv run python semantic/profiling/profile_keys.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from data.ddl import tables as ddl_tables  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"

# 候选关系：(子表, 子列, 父表, 父列)。按「列名长得像外键」列全，再由脚本实测是否成立。
# 列名大小写不一致的地方（FactSales.channelKey）照数据里的原样写。
CANDIDATES: list[tuple[str, str, str, str]] = [
    # 维度到维度
    ("DimAccount", "ParentAccountKey", "DimAccount", "AccountKey"),
    ("DimCustomer", "GeographyKey", "DimGeography", "GeographyKey"),
    ("DimEmployee", "ParentEmployeeKey", "DimEmployee", "EmployeeKey"),
    ("DimEntity", "ParentEntityKey", "DimEntity", "EntityKey"),
    ("DimMachine", "StoreKey", "DimStore", "StoreKey"),
    ("DimProduct", "ProductSubcategoryKey", "DimProductSubcategory", "ProductSubcategoryKey"),
    ("DimProductSubcategory", "ProductCategoryKey", "DimProductCategory", "ProductCategoryKey"),
    ("DimSalesTerritory", "GeographyKey", "DimGeography", "GeographyKey"),
    ("DimSalesTerritory", "EmployeeKey", "DimEmployee", "EmployeeKey"),
    ("DimStore", "GeographyKey", "DimGeography", "GeographyKey"),
    ("DimStore", "EntityKey", "DimEntity", "EntityKey"),
    ("DimStore", "EmployeeKey", "DimEmployee", "EmployeeKey"),
    # 事实到维度
    ("FactExchangeRate", "CurrencyKey", "DimCurrency", "CurrencyKey"),
    ("FactExchangeRate", "DateKey", "DimDate", "DateKey"),
    ("FactITMachine", "MachineKey", "DimMachine", "MachineKey"),
    ("FactITMachine", "DateKey", "DimDate", "DateKey"),
    ("FactITSLA", "DateKey", "DimDate", "DateKey"),
    ("FactITSLA", "StoreKey", "DimStore", "StoreKey"),
    ("FactITSLA", "MachineKey", "DimMachine", "MachineKey"),
    ("FactITSLA", "OutageKey", "DimOutage", "OutageKey"),
    ("FactInventory", "DateKey", "DimDate", "DateKey"),
    ("FactInventory", "StoreKey", "DimStore", "StoreKey"),
    ("FactInventory", "ProductKey", "DimProduct", "ProductKey"),
    ("FactInventory", "CurrencyKey", "DimCurrency", "CurrencyKey"),
    ("FactOnlineSales", "DateKey", "DimDate", "DateKey"),
    ("FactOnlineSales", "StoreKey", "DimStore", "StoreKey"),
    ("FactOnlineSales", "ProductKey", "DimProduct", "ProductKey"),
    ("FactOnlineSales", "PromotionKey", "DimPromotion", "PromotionKey"),
    ("FactOnlineSales", "CurrencyKey", "DimCurrency", "CurrencyKey"),
    ("FactOnlineSales", "CustomerKey", "DimCustomer", "CustomerKey"),
    ("FactSales", "DateKey", "DimDate", "DateKey"),
    ("FactSales", "channelKey", "DimChannel", "ChannelKey"),
    ("FactSales", "StoreKey", "DimStore", "StoreKey"),
    ("FactSales", "ProductKey", "DimProduct", "ProductKey"),
    ("FactSales", "PromotionKey", "DimPromotion", "PromotionKey"),
    ("FactSales", "CurrencyKey", "DimCurrency", "CurrencyKey"),
    ("FactSalesQuota", "ChannelKey", "DimChannel", "ChannelKey"),
    ("FactSalesQuota", "StoreKey", "DimStore", "StoreKey"),
    ("FactSalesQuota", "ProductKey", "DimProduct", "ProductKey"),
    ("FactSalesQuota", "DateKey", "DimDate", "DateKey"),
    ("FactSalesQuota", "CurrencyKey", "DimCurrency", "CurrencyKey"),
    ("FactSalesQuota", "ScenarioKey", "DimScenario", "ScenarioKey"),
    ("FactStrategyPlan", "DateKey", "DimDate", "DateKey"),
    ("FactStrategyPlan", "EntityKey", "DimEntity", "EntityKey"),
    ("FactStrategyPlan", "ScenarioKey", "DimScenario", "ScenarioKey"),
    ("FactStrategyPlan", "AccountKey", "DimAccount", "AccountKey"),
    ("FactStrategyPlan", "CurrencyKey", "DimCurrency", "CurrencyKey"),
    ("FactStrategyPlan", "ProductCategoryKey", "DimProductCategory", "ProductCategoryKey"),
]

# 每张表声称的粒度：(表, 列清单)。脚本核对这组列是否唯一。
GRAIN_CLAIMS: list[tuple[str, list[str]]] = [
    ("DimAccount", ["AccountKey"]),
    ("DimChannel", ["ChannelKey"]),
    ("DimCurrency", ["CurrencyKey"]),
    ("DimCustomer", ["CustomerKey"]),
    ("DimDate", ["DateKey"]),
    ("DimEmployee", ["EmployeeKey"]),
    ("DimEntity", ["EntityKey"]),
    ("DimGeography", ["GeographyKey"]),
    ("DimMachine", ["MachineKey"]),
    ("DimOutage", ["OutageKey"]),
    ("DimProduct", ["ProductKey"]),
    ("DimProductCategory", ["ProductCategoryKey"]),
    ("DimProductSubcategory", ["ProductSubcategoryKey"]),
    ("DimPromotion", ["PromotionKey"]),
    ("DimSalesTerritory", ["SalesTerritoryKey"]),
    ("DimScenario", ["ScenarioKey"]),
    ("DimStore", ["StoreKey"]),
    ("FactExchangeRate", ["DateKey", "CurrencyKey"]),
    ("FactITMachine", ["MachineKey", "DateKey", "CostType"]),
    ("FactITSLA", ["ITSLAkey"]),
    ("FactInventory", ["DateKey", "StoreKey", "ProductKey"]),
    ("FactOnlineSales", ["SalesOrderNumber", "SalesOrderLineNumber"]),
    ("FactSales", ["DateKey", "channelKey", "StoreKey", "ProductKey", "PromotionKey"]),
    ("FactSalesQuota", ["DateKey", "ChannelKey", "StoreKey", "ProductKey", "ScenarioKey"]),
    ("FactStrategyPlan", ["DateKey", "EntityKey", "ScenarioKey", "AccountKey", "ProductCategoryKey"]),
]


def chdb_dir() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        sys.exit("SEMDEBT_DATA_DIR 未设置（见 AGENTS.md「环境」）")
    d = Path(root).expanduser() / "chdb"
    if not d.is_dir():
        sys.exit(f"chDB 数据目录不存在：{d}（先跑 data/load.py）")
    return d


def q(sess, sql: str) -> list[list[str]]:
    """跑一条查询，返回每行的字段列表（字段一律转成字符串）。

    用 JSONCompact 而不是 TabSeparated：TSV 会把取值里的 `\'`、`\t`、`\\` 转义掉，
    而本脚本的产物要原样进 source.yaml 的取值清单，带着转义符就是错的
    （实际踩过：DimEmployee.DepartmentName 的脏取值 `'Human Resources Contral`
    在 TSV 里成了 `\\'Human Resources Contral`）。
    """
    raw = sess.query(sql, "JSONCompact").bytes().decode("utf-8")
    if not raw.strip():
        return []
    rows = json.loads(raw).get("data", [])
    return [["" if v is None else str(v) for v in row] for row in rows]


def main() -> None:
    from chdb import session

    ddl = {t.name: dict(t.columns) for t in ddl_tables()}
    # 建表语句里没有声明任何外键，所以候选清单必须和列名一一对得上，错了立刻报错
    for child, ccol, parent, pcol in CANDIDATES:
        assert ccol in ddl[child], f"{child}.{ccol} 不在建表语句里"
        assert pcol in ddl[parent], f"{parent}.{pcol} 不在建表语句里"

    OUT.mkdir(parents=True, exist_ok=True)
    sess = session.Session(str(chdb_dir()))
    rels: list[dict] = []
    grains: list[dict] = []
    try:
        for child, ccol, parent, pcol in CANDIDATES:
            # Nullable(Float64) 的键要转成整数再比，否则 1.0 对不上 1
            cexpr = f"toInt64(`{ccol}`)"
            pexpr = f"toInt64(`{pcol}`)" if parent != "DimDate" else f"`{pcol}`"
            if parent == "DimDate":
                cexpr = f"`{ccol}`"
            row = q(
                sess,
                f"""SELECT count() AS n,
                           countIf(`{ccol}` IS NULL) AS nulls,
                           uniqExact({cexpr}) AS d
                    FROM retail.{child}""",
            )[0]
            n, nulls, d = int(row[0]), int(row[1]), int(row[2])
            orphans = int(
                q(
                    sess,
                    f"""SELECT count() FROM retail.{child} c
                        WHERE c.`{ccol}` IS NOT NULL
                          AND {cexpr.replace('`' + ccol + '`', 'c.`' + ccol + '`')} NOT IN (
                              SELECT {pexpr} FROM retail.{parent})""",
                )[0][0]
            )
            parent_rows = int(q(sess, f"SELECT count() FROM retail.{parent}")[0][0])
            # 子表侧是否唯一 → 一对一；否则多对一
            card = "一对一" if d == n - nulls else "多对一"
            rels.append(
                {
                    "child": child, "child_column": ccol,
                    "parent": parent, "parent_column": pcol,
                    "child_rows": n, "child_nulls": nulls,
                    "child_distinct_keys": d,
                    "parent_rows": parent_rows,
                    "orphan_rows": orphans,
                    "cardinality": card,
                    "coverage": round(d / parent_rows, 6) if parent_rows else None,
                }
            )
            print(f"{child}.{ccol} -> {parent}.{pcol}: 孤儿 {orphans}，基数 {card}", flush=True)

        for tname, cols in GRAIN_CLAIMS:
            keys = ", ".join(f"`{c}`" for c in cols)
            row = q(sess, f"SELECT count(), uniqExact(({keys})) FROM retail.{tname}")[0]
            n, d = int(row[0]), int(row[1])
            grains.append({"table": tname, "columns": cols, "rows": n, "distinct": d, "unique": n == d})
            print(f"{tname} 粒度 {cols}: {'唯一' if n == d else f'不唯一（{n} 行 / {d} 组）'}", flush=True)
    finally:
        sess.close()

    data = {"relationships": rels, "grains": grains}
    (OUT / "keys.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 键的覆盖率与基数",
        "",
        "由 `semantic/profiling/profile_keys.py` 生成，不要手改。",
        "",
        "建表语句里**没有任何外键声明**，下表的关系是按列名提出候选、再用数据实测的结果。",
        "「孤儿行」= 子表里该键非空、但父表里找不到对应行的行数；`0` 才能写成可信赖的关系。",
        "「覆盖率」= 子表用到的键个数 ÷ 父表行数，用来说明维度表有多少行从没被这张事实表用到。",
        "",
        "| 子表.列 | 父表.列 | 子表行数 | 空值 | 用到的键 | 父表行数 | 孤儿行 | 基数 | 覆盖率 |",
        "|---|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    for r in rels:
        cov = "—" if r["coverage"] is None else f"{r['coverage']:.1%}"
        flag = "" if r["orphan_rows"] == 0 else " ⚠️"
        lines.append(
            f"| `{r['child']}.{r['child_column']}` | `{r['parent']}.{r['parent_column']}` | "
            f"{r['child_rows']:,} | {r['child_nulls']:,} | {r['child_distinct_keys']:,} | "
            f"{r['parent_rows']:,} | {r['orphan_rows']:,}{flag} | {r['cardinality']} | {cov} |"
        )
    lines += ["", "## 粒度核对", "", "每张表声称的粒度列组是否唯一。", "",
              "| 表 | 粒度列 | 行数 | 不同组合 | 唯一 |", "|---|---|---:|---:|---|"]
    for g in grains:
        lines.append(
            f"| `{g['table']}` | {'、'.join(f'`{c}`' for c in g['columns'])} | "
            f"{g['rows']:,} | {g['distinct']:,} | {'是' if g['unique'] else '**否**'} |"
        )
    (OUT / "keys.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"写出 {OUT / 'keys.md'}")


if __name__ == "__main__":
    main()
