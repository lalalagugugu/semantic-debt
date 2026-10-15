"""校验 semantic/ 下的语义层源文件。

对应任务卡 T08 的验收项：

  1. 每张表、每列都有描述（而且表和列与建表语句逐一对得上，列序也一致）。
  2. 每个外键样式的列都有关系，关系写明基数。
  3. 每个低基数字符串列（不同取值 < 50）都有取值说明。
  4. metrics.yaml 的每个指标都能在 source.yaml 的文字口径里找到（不多不少）。
  5. 汇总层 summary.yaml 的每个指标列都能在 source.yaml 的文字口径里找到。
  6. 明细宽表的每个视图和每个列都在 source.yaml 的 widetables 节里有描述。
  7. source.yaml 里的实测数字（行数、孤儿行、基数）与数据对得上。

用法：
    uv run python semantic/schema/validate.py             # 全部检查（含连数据库的第 7 项）
    uv run python semantic/schema/validate.py --no-data   # 只做不连数据库的静态检查

退出码非 0 表示有检查未通过。所有未通过项都会打印，不会在第一条就停。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from data.ddl import tables as ddl_tables  # noqa: E402

SEMANTIC = REPO / "semantic"
SOURCE = SEMANTIC / "source.yaml"
METRICS = SEMANTIC / "metrics.yaml"
SUMMARY_YAML = SEMANTIC / "summary" / "summary.yaml"
PROFILE_COLUMNS = SEMANTIC / "profiling" / "out" / "columns.json"

# 低基数的判定线，与 profile_columns.py 保持一致
LOW_CARD_MAX = 50

# 这些列名虽然以 Key 结尾，但它们是所在表自己的主键，不需要关系
# （由「是某张表的主键」自动判定，这里只列出例外）。
NOT_A_FOREIGN_KEY: set[tuple[str, str]] = {
    ("DimCustomer", "RowNum"),
}


class Checker:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def check(self, ok: bool, label: str, detail: str = "") -> None:
        self.checks += 1
        if not ok:
            self.failures.append(f"{label}{(' —— ' + detail) if detail else ''}")

    def report(self, title: str) -> None:
        print(f"\n== {title} ==")


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def has_text(value: object, min_len: int = 4) -> bool:
    return isinstance(value, str) and len(value.strip()) >= min_len


def base_type(ch_type: str) -> str:
    t = ch_type
    while t.startswith("Nullable(") or t.startswith("LowCardinality("):
        t = t[t.index("(") + 1 : -1]
    return t


# ---------------------------------------------------------------------------
# 1. 表与列
# ---------------------------------------------------------------------------
def check_datasets(c: Checker, src: dict) -> None:
    c.report("1. 每张表、每列都有描述，并与建表语句一致")
    ddl = {t.name: t for t in ddl_tables()}
    datasets = {d["name"]: d for d in src.get("datasets", [])}

    c.check(set(datasets) == set(ddl), "表清单与建表语句一致",
            f"只在 YAML 里：{sorted(set(datasets) - set(ddl))}；只在建表语句里：{sorted(set(ddl) - set(datasets))}")

    for name, t in ddl.items():
        d = datasets.get(name)
        if d is None:
            continue
        c.check(has_text(d.get("description"), 10), f"{name} 有表描述")
        c.check(has_text(d.get("grain"), 6), f"{name} 写明粒度（一行是什么）")
        c.check(has_text(d.get("when_to_use"), 6), f"{name} 写明何时使用")
        yaml_cols = [col["name"] for col in d.get("columns", [])]
        c.check(yaml_cols == t.column_names, f"{name} 的列名与列序与建表语句一致",
                f"YAML：{yaml_cols[:3]}…；建表语句：{t.column_names[:3]}…")
        for col in d.get("columns", []):
            c.check(has_text(col.get("description"), 4),
                    f"{name}.{col['name']} 有列描述")

    # 相近表必须写明区别（事实表里有两张销售表，选错表是最常见的错误）
    for name in ("FactOnlineSales", "FactSales"):
        d = datasets.get(name, {})
        c.check(bool(d.get("differs_from")), f"{name} 写明与相近表的区别")


# ---------------------------------------------------------------------------
# 2. 外键与基数
# ---------------------------------------------------------------------------
def primary_keys(src: dict) -> dict[str, str]:
    """每张维度表的主键列名 → 表名。用来判断哪些列长得像外键。"""
    out: dict[str, str] = {}
    for d in src.get("datasets", []):
        for col in d.get("columns", []):
            if col.get("role") == "key":
                out[col["name"]] = d["name"]
    return out


def check_relationships(c: Checker, src: dict) -> None:
    c.report("2. 每个外键样式的列都有关系和基数")
    pk = primary_keys(src)
    rels = src.get("relationships", [])
    valid_cardinalities = {"多对一", "一对一", "一对多", "多对多"}

    declared: set[str] = set()
    for r in rels:
        c.check(has_text(r.get("from"), 5), "关系有 from", str(r)[:60])
        c.check(has_text(r.get("to"), 5), "关系有 to", str(r)[:60])
        c.check(r.get("cardinality") in valid_cardinalities,
                f"关系 {r.get('from')} → {r.get('to')} 写明基数",
                f"实际是 {r.get('cardinality')!r}，可选 {sorted(valid_cardinalities)}")
        c.check(has_text(r.get("use"), 6),
                f"关系 {r.get('from')} → {r.get('to')} 写明用途")
        c.check(isinstance(r.get("orphan_rows"), int),
                f"关系 {r.get('from')} → {r.get('to')} 写明实测孤儿行数")
        declared.add(str(r.get("from")))

    # 列名长得像外键（是某张表的主键名、但不是本表自己的主键）就必须有关系
    for d in src.get("datasets", []):
        tname = d["name"]
        own_pk = {col["name"] for col in d.get("columns", []) if col.get("role") == "key"}
        for col in d.get("columns", []):
            cname = col["name"]
            if (tname, cname) in NOT_A_FOREIGN_KEY or cname in own_pk:
                continue
            is_fk_shaped = cname in pk or (
                cname.startswith("Parent") and cname.endswith("Key")
            ) or (cname.lower().endswith("key") and cname not in own_pk)
            if not is_fk_shaped:
                continue
            # 代理键（本表自己的行键，如 SalesKey / OnlineSalesKey）不算外键
            if col.get("technical") and cname not in pk and not cname.startswith("Parent"):
                continue
            c.check(f"{tname}.{cname}" in declared,
                    f"{tname}.{cname} 长得像外键，必须有关系")

    # 同一对表有多条路径时必须写明默认走哪条
    c.check(bool(src.get("multi_path_defaults")), "写明了多路径时的默认选择")
    for mp in src.get("multi_path_defaults", []):
        c.check(has_text(mp.get("default"), 5), f"多路径 {mp.get('pair')} 指明默认路径")
        c.check(has_text(mp.get("why"), 6), f"多路径 {mp.get('pair')} 说明为什么")


# ---------------------------------------------------------------------------
# 3. 低基数字符串列的取值说明
# ---------------------------------------------------------------------------
def check_low_cardinality(c: Checker, src: dict) -> None:
    c.report(f"3. 每个低基数字符串列（不同取值 < {LOW_CARD_MAX}）都有取值说明")
    if not PROFILE_COLUMNS.is_file():
        c.check(False, "探查结果存在", f"缺 {PROFILE_COLUMNS}，先跑 semantic/profiling/profile_columns.py")
        return
    profile = yaml.safe_load(PROFILE_COLUMNS.read_text(encoding="utf-8"))
    datasets = {d["name"]: d for d in src.get("datasets", [])}

    for tname, tinfo in profile["tables"].items():
        d = datasets.get(tname, {})
        cols = {col["name"]: col for col in d.get("columns", [])}
        for cname, ci in tinfo["columns"].items():
            if base_type(ci["type"]) != "String":
                continue
            if not (0 < ci["distinct"] < LOW_CARD_MAX):
                continue
            col = cols.get(cname, {})
            vals = col.get("values")
            if col.get("technical"):
                # 技术字段不进 L1 上下文，有描述就够，不强制逐值列出
                continue
            if col.get("value_semantics"):
                # 唯一的替代写法：取值是连续域（日期、度量）而不是枚举类别，逐个列出
                # 不增加业务信息。必须写一段说明为什么，而且不能同时给 values。
                c.check(has_text(col["value_semantics"], 20),
                        f"{tname}.{cname} 用 value_semantics 代替逐值列出，说明要写清为什么")
                c.check(vals is None,
                        f"{tname}.{cname} 不应同时给 values 和 value_semantics")
                print(f"   注：{tname}.{cname}（{ci['distinct']} 个取值）用 value_semantics 说明连续域，未逐值列出")
                continue
            c.check(isinstance(vals, list) and len(vals) > 0,
                    f"{tname}.{cname} 低基数字符串列（{ci['distinct']} 个取值）要列出取值及含义")
            if isinstance(vals, list):
                actual = {str(v["value"]) for v in ci.get("values", [])}
                listed = {str(v.get("value")) for v in vals}
                c.check(listed <= actual or not actual,
                        f"{tname}.{cname} 列出的取值都真实存在",
                        f"YAML 里有而数据里没有：{sorted(listed - actual)}")
                for v in vals:
                    c.check(has_text(v.get("meaning"), 2),
                            f"{tname}.{cname} 的取值 {v.get('value')!r} 有含义说明")


# ---------------------------------------------------------------------------
# 4 / 5. 指标口径的唯一来源
# ---------------------------------------------------------------------------
def source_metric_names(src: dict) -> set[str]:
    return {m["name"] for m in src.get("metrics", [])}


def check_metrics_yaml(c: Checker, src: dict) -> None:
    c.report("4. metrics.yaml 的指标与 source.yaml 的文字口径一一对应")
    mfile = load_yaml(METRICS)
    if not mfile:
        print("   （metrics.yaml 还不存在，跳过）")
        return
    names_src = source_metric_names(src)
    names_l2 = {m["name"] for m in mfile.get("metrics", [])}
    c.check(names_l2 <= names_src, "metrics.yaml 没有 source.yaml 里没定义过的指标",
            f"多出来的：{sorted(names_l2 - names_src)}")
    c.check(names_src <= names_l2, "source.yaml 的每个指标都在 metrics.yaml 里",
            f"漏掉的：{sorted(names_src - names_l2)}")
    by_name = {m["name"]: m for m in src.get("metrics", [])}
    for m in mfile.get("metrics", []):
        name = m["name"]
        c.check(has_text(m.get("definition"), 6), f"metrics.yaml 的「{name}」有文字口径")
        c.check(has_text(m.get("dax_measure"), 3), f"metrics.yaml 的「{name}」有 DAX 度量值名")
        c.check(has_text(m.get("cube_member"), 3), f"metrics.yaml 的「{name}」有 Cube 成员名")
        c.check(m.get("additivity") in {"可加", "比率", "半可加", "去重"},
                f"metrics.yaml 的「{name}」写明可加性")
        if name in by_name:
            c.check(m.get("additivity") == by_name[name].get("additivity"),
                    f"「{name}」的可加性与 source.yaml 一致",
                    f"metrics.yaml：{m.get('additivity')}；source.yaml：{by_name[name].get('additivity')}")


def check_summary_yaml(c: Checker, src: dict) -> None:
    c.report("5. 汇总层的指标列都能在 source.yaml 的文字口径里找到")
    sfile = load_yaml(SUMMARY_YAML)
    if not sfile:
        print("   （summary.yaml 还不存在，跳过）")
        return
    names_src = source_metric_names(src)

    # summary.yaml 必须覆盖 summary.sql 里真实建出来的每张表和每个列，
    # 否则漏掉一列也没人发现（和宽表那一节同样的覆盖检查）。
    import re

    sql_path = SEMANTIC / "summary" / "summary.sql"
    if sql_path.is_file():
        sql = sql_path.read_text(encoding="utf-8")
        in_sql = set(re.findall(r"CREATE TABLE\s+ads\.(\w+)", sql))
        in_yaml = {x["name"] for x in sfile.get("tables", [])}
        c.check(in_sql == in_yaml, "summary 节的汇总表与 summary.sql 一一对应",
                f"只在 SQL：{sorted(in_sql - in_yaml)}；只在 YAML：{sorted(in_yaml - in_sql)}")
        views_sql = set(re.findall(r"CREATE OR REPLACE VIEW\s+ads\.(\w+)", sql))
        c.check(views_sql == set(sfile.get("dimension_views", [])),
                "dimension_views 与 summary.sql 里的维度视图一一对应",
                f"只在 SQL：{sorted(views_sql - set(sfile.get('dimension_views', [])))}")
        for tbl in sfile.get("tables", []):
            m = re.search(
                rf"CREATE TABLE\s+ads\.{tbl['name']}\b.*?(?=DROP TABLE IF EXISTS|CREATE TABLE\s+ads\.|\Z)",
                sql, re.S)
            if not m:
                continue
            aliases = re.findall(r"AS\s+`([^`]+)`", m.group(0))
            described = {col["name"] for col in tbl.get("columns", [])}
            missing = sorted(set(aliases) - described)
            c.check(not missing, f"汇总表 {tbl['name']} 的每个列都有说明",
                    f"没有说明的列：{missing}")

    for t in sfile.get("tables", []):
        # 规矩：比率不存比率本身，只存分子和分母。所以不该有 additivity 为「比率」的列。
        for col in t.get("columns", []):
            c.check(col.get("additivity") != "比率",
                    f"汇总表 {t.get('name')}.{col.get('name')} 不应是比率列"
                    f"（规矩：比率只存分子和分母，比率本身现算）")

    for t in sfile.get("tables", []):
        c.check(has_text(t.get("grain"), 6), f"汇总表 {t.get('name')} 写明粒度")
        c.check(has_text(t.get("description"), 6), f"汇总表 {t.get('name')} 有描述")
        c.check(bool(t.get("serves_reports")), f"汇总表 {t.get('name')} 写明服务哪几份报表")
        for col in t.get("columns", []):
            c.check(has_text(col.get("description"), 4),
                    f"汇总表 {t.get('name')}.{col.get('name')} 有列描述")
            c.check(col.get("additivity") in {"可加", "比率", "半可加", "去重", "维度"},
                    f"汇总表 {t.get('name')}.{col.get('name')} 写明可加性")
            metric = col.get("metric")
            if metric is not None:
                c.check(metric in names_src,
                        f"汇总表 {t.get('name')}.{col.get('name')} 的指标「{metric}」在 source.yaml 里有口径")
            if col.get("additivity") == "去重":
                c.check("不能" in (col.get("description") or ""),
                        f"汇总表 {t.get('name')}.{col.get('name')} 是去重计数，描述里要写明不能跨行相加")


# ---------------------------------------------------------------------------
# 6. 明细宽表的描述完整
# ---------------------------------------------------------------------------
def check_widetables(c: Checker, src: dict) -> None:
    c.report("6. 明细宽表的每个视图与每个列都有描述")
    wt = src.get("widetables") or {}
    sql = (SEMANTIC / "widetables.sql").read_text(encoding="utf-8")
    views = {v["name"]: v for v in wt.get("views", [])}

    import re

    in_sql = set(re.findall(r"CREATE OR REPLACE VIEW\s+\w+\.(\w+)", sql))
    c.check(set(views) == in_sql, "widetables 节的视图与 widetables.sql 一一对应",
            f"只在 YAML：{sorted(set(views) - in_sql)}；只在 SQL：{sorted(in_sql - set(views))}")
    for name, v in views.items():
        c.check(has_text(v.get("description"), 10), f"宽表 {name} 有描述")
        c.check(has_text(v.get("grain"), 6), f"宽表 {name} 写明粒度")
        c.check(isinstance(v.get("row_count_equals_fact"), bool),
                f"宽表 {name} 写明行数是否等于事实表")
        if v.get("row_count_equals_fact") is False:
            c.check(has_text(v.get("row_count_note"), 20),
                    f"宽表 {name} 行数不等于事实表，必须单独说明")
        for col in v.get("columns", []):
            c.check(has_text(col.get("description"), 4),
                    f"宽表 {name}.{col.get('name')} 有列描述")
            c.check(bool(col.get("source") or col.get("derived")),
                    f"宽表 {name}.{col.get('name')} 写明来源（source 或 derived）")

    # 共用维度列的说明必须覆盖所有没有单独描述的列
    shared: set[str] = set()
    for group in wt.get("shared_column_meanings", []):
        c.check(has_text(group.get("description"), 10),
                f"共用列组 {group.get('columns')} 有说明")
        shared |= set(group.get("columns", []))
    for name, v in views.items():
        described = {col["name"] for col in v.get("columns", [])} | shared
        declared_in_sql = _view_columns_from_sql(sql, name)
        missing = sorted(set(declared_in_sql) - described)
        c.check(not missing, f"宽表 {name} 的每个列都有描述（独立描述或共用列组）",
                f"没有描述的列：{missing}")


def _view_columns_from_sql(sql: str, view: str) -> list[str]:
    """从 widetables.sql 里抓出一个视图 SELECT 出来的列别名。"""
    import re

    m = re.search(
        rf"CREATE OR REPLACE VIEW\s+\w+\.{view}\s+AS(.*?)(?=CREATE OR REPLACE VIEW|\Z)",
        sql,
        re.S,
    )
    if not m:
        return []
    return re.findall(r"AS\s+`([^`]+)`", m.group(1))


# ---------------------------------------------------------------------------
# 7. 实测数字与数据一致
# ---------------------------------------------------------------------------
def check_against_data(c: Checker, src: dict) -> None:
    c.report("7. source.yaml 里的实测数字与数据一致")
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        c.check(False, "SEMDEBT_DATA_DIR 已设置")
        return
    d = Path(root).expanduser() / "chdb"
    if not d.is_dir():
        c.check(False, "chDB 数据目录存在", str(d))
        return

    from chdb import session

    sess = session.Session(str(d))
    try:
        def scalar(sql: str) -> str:
            return sess.query(sql, "TabSeparated").bytes().decode("utf-8").strip()

        for ds in src.get("datasets", []):
            if "rows" not in ds:
                continue
            actual = int(scalar(f"SELECT count() FROM retail.{ds['name']}"))
            c.check(actual == ds["rows"], f"{ds['name']} 的 rows 与数据一致",
                    f"YAML 写 {ds['rows']:,}，实际 {actual:,}")

        for r in src.get("relationships", []):
            ct, cc = str(r["from"]).split(".")
            pt, pc = str(r["to"]).split(".")
            cexpr = f"toInt64(`{cc}`)" if pt != "DimDate" else f"`{cc}`"
            pexpr = f"toInt64(`{pc}`)" if pt != "DimDate" else f"`{pc}`"
            orphans = int(scalar(
                f"SELECT count() FROM retail.{ct} WHERE `{cc}` IS NOT NULL "
                f"AND {cexpr} NOT IN (SELECT {pexpr} FROM retail.{pt})"
            ))
            c.check(orphans == r["orphan_rows"],
                    f"{r['from']} → {r['to']} 的孤儿行数与数据一致",
                    f"YAML 写 {r['orphan_rows']:,}，实际 {orphans:,}")

            n = int(scalar(f"SELECT count() FROM retail.{ct} WHERE `{cc}` IS NOT NULL"))
            dk = int(scalar(f"SELECT uniqExact({cexpr}) FROM retail.{ct} WHERE `{cc}` IS NOT NULL"))
            expected = "一对一" if dk == n else "多对一"
            c.check(r["cardinality"] == expected,
                    f"{r['from']} → {r['to']} 的基数与数据一致",
                    f"YAML 写 {r['cardinality']}，实际 {expected}")
    finally:
        sess.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-data", action="store_true", help="跳过需要连 chDB 的第 7 项")
    args = ap.parse_args()

    src = load_yaml(SOURCE)
    if not src:
        sys.exit(f"读不到 {SOURCE}")

    c = Checker()
    check_datasets(c, src)
    check_relationships(c, src)
    check_low_cardinality(c, src)
    check_metrics_yaml(c, src)
    check_summary_yaml(c, src)
    check_widetables(c, src)
    if not args.no_data:
        check_against_data(c, src)

    print(f"\n共 {c.checks} 项检查，{len(c.failures)} 项未通过。")
    if c.failures:
        print("\n未通过的检查：")
        for f in c.failures:
            print(f"  - {f}")
        sys.exit(1)
    print("全部通过。")


if __name__ == "__main__":
    main()
