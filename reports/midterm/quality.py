"""T24 dataset inventory and quality probes over local Parquet, in-memory only.

uv run python reports/midterm/quality.py
No persistent chDB data directory is opened. Query errors stop the report.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import chdb

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from data.ddl import SCHEMA, tables
from semantic.profiling.profile_keys import CANDIDATES
from reports.midterm.analyze import table, write

QUERIES = []


def query(sql):
    """Replace only verified physical table names with local Parquet readers."""
    physical = sql
    for spec in sorted(tables(), key=lambda t: -len(t.name)):
        path = Path(os.environ["SEMDEBT_DATA_DIR"]) / "parquet" / f"{spec.name}.parquet"
        if not path.is_file():
            raise FileNotFoundError(path)
        physical = re.sub(r"\bretail\." + spec.name + r"\b",
                          lambda _: "file('" + str(path).replace("'", "''") + "', 'Parquet')", physical)
    rows = json.loads(str(chdb.query(physical, "JSON")))["data"]
    QUERIES.append({"id": len(QUERIES)+1, "sql": sql, "result": rows})
    return rows


def count(title, sql, explanation):
    rows = query(sql)
    assert len(rows) == 1
    return [title, str(rows[0]["n"]), len(QUERIES), explanation]


def main():
    specs = tables()
    inventory, issues = [], []
    total = 0
    for t in specs:
        n = int(query(f"SELECT count() AS n FROM retail.{t.name}")[0]["n"])
        total += n
        inventory.append([t.name, len(t.columns), n, len(QUERIES)])
    assert len(specs) == 25 and total == 34326191
    for child, col, parent, pk in CANDIDATES:
        issues.append(count(f"孤儿键 {child}.{col} → {parent}.{pk}",
                            f"SELECT count() AS n FROM retail.{child} WHERE {col} IS NOT NULL AND {col} NOT IN "
                            f"(SELECT {pk} FROM retail.{parent})", "子表受影响行；0表示该候选关系未发现孤儿，不是全表质量通过。"))
    probes = [
        ("产品编码缺行", "SELECT count() AS n FROM (SELECT DISTINCT ProductKey FROM retail.FactSales) WHERE ProductKey NOT IN (SELECT ProductKey FROM retail.DimProduct)", "事实中不同缺失产品键数；不是受影响事实行数，上面的孤儿行逐表列出。"),
        ("产品蓝色小写", "SELECT count() AS n FROM retail.DimProduct WHERE ColorName = 'blue'", "非规范小写blue；Blue另列，二者不是重复产品。"),
        ("产品蓝色大写", "SELECT count() AS n FROM retail.DimProduct WHERE ColorName = 'Blue'", "同颜色的另一种拼写。"),
        ("Silver Grey取值", "SELECT count() AS n FROM retail.DimProduct WHERE ColorName = 'Silver Grey'", "混合色名称，不能未经业务裁决合并到Silver或Grey。"),
        ("员工部门脏拼写", "SELECT count() AS n FROM retail.DimEmployee WHERE position(DepartmentName, 'Contral') > 0", "包括前导单引号及Contral拼写；不自动清洗。"),
        ("促销名称拼写", "SELECT count() AS n FROM retail.DimPromotion WHERE position(PromotionName, 'Scholl') > 0", "Scholl拼写的促销维表行。"),
        ("国家名为空", "SELECT count() AS n FROM retail.DimGeography WHERE RegionCountryName = ''", "上层地理节点；不将空名称误称为丢行。"),
        ("客户收入离群档", "SELECT count() AS n FROM retail.DimCustomer WHERE YearlyIncome = 10000000", "离群值保留，不自行删掉。"),
        ("门店面积离群档", "SELECT count() AS n FROM retail.DimStore WHERE SellingAreaSize = 93800", "不自行删掉。"),
        ("门店员工数离群档", "SELECT count() AS n FROM retail.DimStore WHERE EmployeeCount = 325", "不自行删掉。"),
        ("在营关店日期哨兵", "SELECT count() AS n FROM retail.DimStore WHERE CloseDate = '2090-12-31'", "哨兵值不是实际未来关店安排；该物理列为字符串。"),
        ("款式名实为产品编码", "SELECT count() AS n FROM retail.DimProduct WHERE startsWith(StyleName, 'Product')", "可疑命名字段；产品编码已存于StyleName，不能把它说成全部编码为空。"),
        ("门店经理字段存员工号", "SELECT count() AS n FROM retail.DimStore WHERE StoreManager = toString(EmployeeKey)", "字段语义陷阱；员工号不等于经理姓名。"),
        ("销售辖区经理存员工号", "SELECT count() AS n FROM retail.DimSalesTerritory WHERE SalesTerritoryManager = toString(EmployeeKey)", "与门店经理相同的字段语义陷阱。"),
        ("全渠道挂促销但无折扣金额", "SELECT count() AS n FROM retail.FactSales WHERE PromotionKey != 1 AND DiscountAmount = 0", "两种打折定义不等价。"),
        ("线上挂促销但无折扣金额", "SELECT count() AS n FROM retail.FactOnlineSales WHERE PromotionKey != 1 AND DiscountAmount = 0", "与全渠道分开量化。"),
        ("库存周频覆盖行数", "SELECT count() AS n FROM retail.FactInventory", "全部库存行受快照频率约束；日期分布另查。"),
        ("节假日标记天数", "SELECT count() AS n FROM retail.DimDate WHERE IsHoliday = 'Yes'", "这是日期行数；本库与周末一致，不是公共假日真实性证明。"),
        ("节假日与周末不一致", "SELECT count() AS n FROM retail.DimDate WHERE (IsHoliday = 'Yes') != (toDayOfWeek(DateKey) IN (6,7))", "0表示本库的两种划分相同。"),
        ("日期维度超出销售期间", "SELECT count() AS n FROM retail.DimDate WHERE DateKey < (SELECT min(DateKey) FROM retail.FactOnlineSales) OR DateKey > (SELECT max(DateKey) FROM retail.FactOnlineSales)", "空日期若进均值分母会改变口径。"),
        ("不同表国家命名差异", "SELECT count() AS n FROM retail.DimSalesTerritory t INNER JOIN retail.DimGeography g ON t.GeographyKey = g.GeographyKey WHERE t.SalesTerritoryCountry != g.RegionCountryName", "按已存在地理键比较，不用字符串猜对应关系。"),
        ("销售表纯退货行", "SELECT count() AS n FROM retail.FactSales WHERE SalesQuantity = 0 AND ReturnQuantity > 0", "购买事件口径须明确是否纳入。"),
        ("线上表纯退货行", "SELECT count() AS n FROM retail.FactOnlineSales WHERE SalesQuantity = 0 AND ReturnQuantity > 0", "购买事件口径须明确是否纳入。"),
    ]
    issues.extend(count(*p) for p in probes)
    query("SELECT toDayOfWeek(DateKey) AS weekday, uniqExact(DateKey) AS snapshot_days, count() AS affected_rows, min(DateKey) AS first_day, max(DateKey) AS last_day FROM retail.FactInventory GROUP BY weekday ORDER BY weekday")
    inventory_days = QUERIES[-1]
    query("SELECT toYear(first_day) AS first_year, count() AS customers FROM (SELECT CustomerKey, min(DateKey) AS first_day FROM retail.FactOnlineSales GROUP BY CustomerKey) GROUP BY first_year ORDER BY first_year")
    new_customers = QUERIES[-1]
    query("SELECT 'FactSales Online' AS source, count() AS affected_rows, sum(toDecimal128(SalesAmount,6)) AS sales, sum(toDecimal128(ReturnAmount,6)) AS returns FROM retail.FactSales WHERE channelKey = 2 UNION ALL SELECT 'FactOnlineSales', count(), sum(toDecimal128(SalesAmount,6)), sum(toDecimal128(ReturnAmount,6)) FROM retail.FactOnlineSales")
    online = QUERIES[-1]
    cycles = []
    for t, key, parent in (("DimAccount", "AccountKey", "ParentAccountKey"),
                           ("DimEmployee", "EmployeeKey", "ParentEmployeeKey"),
                           ("DimEntity", "EntityKey", "ParentEntityKey")):
        rows = query(f"SELECT {key} AS child, {parent} AS parent FROM retail.{t}")
        mapping = {int(r["child"]): int(r["parent"]) if r["parent"] is not None else None for r in rows}
        nodes, affected, self_roots = set(), set(), set()
        for start in mapping:
            path, at, cur = [], {}, start
            while cur in mapping and cur not in at:
                at[cur] = len(path)
                path.append(cur)
                nxt = mapping[cur]
                if cur == nxt:
                    self_roots.add(cur)
                    break
                cur = nxt
            else:
                if cur in at:
                    nodes.update(path[at[cur]:])
                    affected.add(start)
        cycles.append([t, len(nodes), len(affected), len(self_roots), len(QUERIES)])
        # The parent mapping is source data. Commit only aggregate diagnostics.
        QUERIES[-1]["result"] = [{"cycle_nodes": len(nodes), "affected_rows": len(affected),
                                   "self_roots": len(self_roots)}]
    parquet_sources = []
    for t in specs:
        p = Path(os.environ["SEMDEBT_DATA_DIR"]) / "parquet" / f"{t.name}.parquet"
        h = hashlib.sha256()
        with p.open("rb") as f:
            for block in iter(lambda: f.read(1024*1024), b""):
                h.update(block)
        parquet_sources.append({"path": f"$SEMDEBT_DATA_DIR/parquet/{p.name}", "bytes": p.stat().st_size,
                                "sha256": h.hexdigest()})
    evidence = {"ddl_sha256": hashlib.sha256(SCHEMA.read_bytes()).hexdigest(), "chdb_version": chdb.__version__,
                "inputs": parquet_sources, "queries": QUERIES}
    (OUT / "quality-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+"\n")
    lines = ["# 数据集规模与数据质量", "",
             "复现：`uv run python reports/midterm/quality.py`。以环境变量SEMDEBT_DATA_DIR定位本地Parquet，使用无持久目录的chDB查询；不打开共享chdb或chdb-eval。",
             "字段数来自vendor/cube/retail_schema.sql的DDL，不含宽表/汇总层/Cube派生成员。输入Parquet逐文件SHA256、查询结果与chDB版本见quality-evidence.json。",
             "执行记录：首轮在CloseDate哨兵探针因String与Date不能比较而停止（Code386）；依据物理字符串类型改为字符串常量后重算，未修改数据。",
             f"原始表{len(specs)}张，共{sum(len(t.columns) for t in specs)}个字段、{total:,}行；字段按每张表相加，同名字段在不同表分别计数。", "",
             *table(["表", "字段数", "行数", "查询编号"], inventory), "",
             "## 质量清单", "",
             "按semantic/source.yaml既有质量项和候选关系量化；可疑数据保留，不自动清洗。不同探针可能覆盖同一行，不能相加当作坏行总数。",
             "结构性缺口：没有事实表直接关联员工/辖区，属于模型关系覆盖限制；不存在可量化的受影响员工销售事实行数（不适用，不写成0）。", "",
             *table(["项目", "受影响行/键数", "查询编号", "定义与限制"], issues), "",
             "## 周频库存、首购退化与两种线上口径", ""]
    for name, ev in (("库存日期分布", inventory_days), ("首购年份分布", new_customers), ("线上口径分歧", online)):
        lines += [f"### {name}（查询{ev['id']}）", "", *table(list(ev["result"][0]), [list(r.values()) for r in ev["result"]]), ""]
    lines += ["## 层级成环", "",
              "沿每个节点的父链遍历，直到空父、缺失父或重复节点。自指根单列，长度≥2的闭环才计环节点；能沿父链进入该环的所有起点计受影响行。",
              "使用下列查询取得完整键对后按quality.py中的遍历算法复算，不能仅用外键存在性推断层级无环。", "",
              *table(["层级表", "环节点行数", "可到达环的受影响行", "自指根数", "查询编号"], cycles), "",
              "## 可复现查询", "",
              "以下为逻辑SQL；脚本只将retail.表替换成file('$SEMDEBT_DATA_DIR/parquet/表.parquet','Parquet')，无筛选改写。"]
    for ev in QUERIES:
        lines += ["", f"### Q{ev['id']}", "", "```sql", ev["sql"], "```"]
    write("dataset-quality.md", lines)
    print(f"T24 quality: {len(specs)} tables, {sum(len(t.columns) for t in specs)} columns, {total} rows; {len(QUERIES)} queries succeeded.")


if __name__ == "__main__":
    main()
