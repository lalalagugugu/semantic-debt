"""建 L0 劣化视图（chDB 的独立库 `l0`），并逐表逐列核对与原表一致。

从 `semantic/l0_map.yaml` 生成 `render/l0_views.sql`（入库，便于审阅），在 chDB 上执行，
然后做任务卡 T09 的验收核对：

  1. 每个 L0 视图的行数与原表一致。
  2. 每个原列：非空个数一致；数值列的合计一致（`sum(toDecimal128(列, 6))`，与行序无关）；
     非数值列的哈希合计一致（`sum(cityHash64(列))`）。所以不只数值列，每一列都逐位对上。
  3. 视图的列序、列类型与原表一致，技术字段追加在最后。

映射本身的静态校验（可逆、覆盖建表语句、关系恰好分成保留 / 删除两份）在
`tests/test_l0_map.py`，也由本脚本在执行前先跑一遍。

用法：
    uv run python render/build_l0.py              # 生成 SQL + 重建视图 + 核对
    uv run python render/build_l0.py --sql-only   # 只重新生成 render/l0_views.sql
    uv run python render/build_l0.py --check-only # 不重建，只核对

产物：render/l0_views.sql（入库）、reports/validation/l0.md（入库）
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from data.ddl import tables as ddl_tables  # noqa: E402

MAP_FILE = REPO / "semantic" / "l0_map.yaml"
SOURCE_FILE = REPO / "semantic" / "source.yaml"
SQL_FILE = REPO / "render" / "l0_views.sql"
REPORT = REPO / "reports" / "validation" / "l0.md"

L0_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def load_map() -> dict:
    return yaml.safe_load(MAP_FILE.read_text(encoding="utf-8"))


def rel_key(r: dict) -> tuple[str, str]:
    return (r["from"], r["to"])


def check_map(m: dict) -> list[str]:
    """映射的静态校验，返回所有问题（空列表 = 通过）。"""
    problems: list[str] = []
    ddl = {t.name: t for t in ddl_tables()}
    entries = m["tables"]

    src_names = [t["source"] for t in entries]
    l0_names = [t["l0"] for t in entries]
    if sorted(src_names) != sorted(ddl):
        problems.append(f"表不等于建表语句的 25 张：多 {set(src_names) - set(ddl)}，缺 {set(ddl) - set(src_names)}")
    if len(set(l0_names)) != len(l0_names):
        problems.append("L0 表名有重复，不可逆")

    for t in entries:
        name = t["source"]
        if not L0_NAME.match(t["l0"]):
            problems.append(f"{name}: L0 表名 {t['l0']!r} 不合规")
        if name not in ddl:
            continue
        cols = t["columns"]
        if list(cols) != ddl[name].column_names:
            problems.append(f"{name}: 列（或列序）与建表语句不一致")
        l0_cols = list(cols.values()) + [c["name"] for c in t.get("technical_columns", [])]
        if len(set(l0_cols)) != len(l0_cols):
            problems.append(f"{name}: L0 列名有重复，不可逆")
        bad = [c for c in l0_cols if not L0_NAME.match(c)]
        if bad:
            problems.append(f"{name}: L0 列名不合规 {bad}")
        if set(cols) & set(l0_cols):
            problems.append(f"{name}: L0 列名与原列名重名 {set(cols) & set(l0_cols)}")
        tech = t.get("technical_columns", [])
        if name.startswith("Fact") and not 2 <= len(tech) <= 3:
            problems.append(f"{name}: 事实表应有 2–3 个技术字段，现在 {len(tech)} 个")
        if name.startswith("Dim") and tech:
            problems.append(f"{name}: 维度表不加技术字段")
        for c in tech:
            no_literals = re.sub(r"'[^']*'", "", c["expr"])
            refs = set(re.findall(r"\b([A-Z]\w*)\b", no_literals))
            if refs - set(cols):
                problems.append(f"{name}.{c['name']}: 表达式引用了不存在的列 {refs - set(cols)}")

    # 关系：kept + dropped 恰好是 source.yaml 的全部关系，没有重叠
    src_rels = {rel_key(r) for r in yaml.safe_load(SOURCE_FILE.read_text(encoding="utf-8"))["relationships"]}
    kept = [rel_key(r) for r in m["relationships"]["kept"]]
    dropped = [rel_key(r) for r in m["relationships"]["dropped"]]
    if set(kept) & set(dropped):
        problems.append(f"关系同时在保留和删除里：{set(kept) & set(dropped)}")
    if len(set(kept)) != len(kept) or len(set(dropped)) != len(dropped):
        problems.append("关系清单有重复")
    if set(kept) | set(dropped) != src_rels:
        problems.append(
            f"保留 + 删除 ≠ source.yaml 的关系：多 {(set(kept) | set(dropped)) - src_rels}，"
            f"缺 {src_rels - (set(kept) | set(dropped))}"
        )
    if src_rels and not 0.30 <= len(dropped) / len(src_rels) <= 0.37:
        problems.append(f"删掉 {len(dropped)}/{len(src_rels)} 条关系，不是约三分之一")
    return problems


def generate_sql(m: dict) -> str:
    src_db, db = m["source_database"], m["database"]
    out = [
        "-- 由 render/build_l0.py 从 semantic/l0_map.yaml 生成，不要手改。",
        "-- L0 劣化视图：只改名、追加技术字段；底层仍是 retail 原表，不动数据行。",
        "",
        f"DROP DATABASE IF EXISTS {db};",
        f"CREATE DATABASE {db};",
    ]
    for t in m["tables"]:
        cols = [f"    `{src}` AS {l0}" for src, l0 in t["columns"].items()]
        cols += [f"    {c['expr']} AS {c['name']}" for c in t.get("technical_columns", [])]
        out += [
            "",
            f"CREATE VIEW {db}.{t['l0']} AS",
            "SELECT",
            ",\n".join(cols),
            f"FROM {src_db}.{t['source']};",
        ]
    return "\n".join(out) + "\n"


def statements(sql: str) -> list[str]:
    no_comments = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def chdb_dir() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        sys.exit("SEMDEBT_DATA_DIR 未设置（见 AGENTS.md「环境」）")
    d = Path(root).expanduser() / "chdb"
    if not d.is_dir():
        sys.exit(f"chDB 数据目录不存在：{d}（先跑 data/load.py）")
    return d


NUMERIC = re.compile(r"^(U?Int\d+|Float\d+|Decimal)")


def base_type(t: str) -> str:
    while t.startswith(("Nullable(", "LowCardinality(")):
        t = t[t.index("(") + 1 : -1]
    return t


def fingerprint_exprs(cols: list[tuple[str, str]]) -> list[str]:
    """每列两个指纹：非空个数，以及数值合计或哈希合计。"""
    exprs = ["toString(count())"]
    for col, typ in cols:
        exprs.append(f"toString(count(`{col}`))")
        if NUMERIC.match(base_type(typ)):
            exprs.append(f"toString(sum(toDecimal128(`{col}`, 6)))")
        else:
            exprs.append(f"toString(sum(cityHash64(`{col}`)))")
    return exprs


def query_rows(sess, sql: str) -> list[list[str]]:
    text = sess.query(sql, "TabSeparated").bytes().decode("utf-8")
    return [line.split("\t") for line in text.splitlines()]


def verify(sess, m: dict) -> tuple[list[str], list[str]]:
    src_db, db = m["source_database"], m["database"]
    ddl = {t.name: t for t in ddl_tables()}
    lines: list[str] = []
    failures: list[str] = []
    for t in m["tables"]:
        name, l0 = t["source"], t["l0"]
        src_cols = list(ddl[name].columns)
        tech = [c["name"] for c in t.get("technical_columns", [])]

        # 列序与类型
        desc = query_rows(sess, f"DESCRIBE TABLE {db}.{l0}")
        got = [(r[0], r[1]) for r in desc]
        want = [(t["columns"][c], typ) for c, typ in src_cols]
        if got[: len(want)] != want or [g[0] for g in got[len(want):]] != tech:
            failures.append(f"{l0}: 列序或类型与原表不一致：{got}")

        # 行数 + 逐列指纹
        a = query_rows(sess, f"SELECT {', '.join(fingerprint_exprs(src_cols))} FROM {src_db}.{name}")[0]
        renamed = [(t["columns"][c], typ) for c, typ in src_cols]
        b = query_rows(sess, f"SELECT {', '.join(fingerprint_exprs(renamed))} FROM {db}.{l0}")[0]
        bad_cols = []
        for i, (col, _) in enumerate(src_cols):
            if a[1 + 2 * i : 3 + 2 * i] != b[1 + 2 * i : 3 + 2 * i]:
                bad_cols.append(col)
        ok = a[0] == b[0] and not bad_cols
        if a[0] != b[0]:
            failures.append(f"{l0}: 行数 {b[0]} ≠ {name} 的 {a[0]}")
        if bad_cols:
            failures.append(f"{l0}: 这些列的指纹与 {name} 不一致：{bad_cols}")
        n_num = sum(1 for _, typ in src_cols if NUMERIC.match(base_type(typ)))
        lines.append(
            f"| `{name}` | `{l0}` | {int(a[0]):,} | {int(b[0]):,} | {len(src_cols)}（数值 {n_num}） | "
            f"{len(tech)} | {'一致' if ok else '**不一致**'} |"
        )
        print(f"{name} → {l0}: {int(b[0]):,} 行，{len(src_cols)} 列 → {'一致' if ok else '不一致'}", flush=True)
    return lines, failures


def l0_rel(m: dict, ref: str) -> str:
    tname, col = ref.split(".")
    t = next(t for t in m["tables"] if t["source"] == tname)
    return f"{t['l0']}.{t['columns'][col]}"


def write_report(m: dict, table_lines: list[str], failures: list[str]) -> None:
    kept, dropped = m["relationships"]["kept"], m["relationships"]["dropped"]
    total = len(kept) + len(dropped)
    lines = [
        "# L0 劣化视图核对",
        "",
        "由 `render/build_l0.py` 生成，不要手改。映射见 `semantic/l0_map.yaml`，视图 SQL 见 `render/l0_views.sql`。",
        "",
        f"结论：{'**全部一致**' if not failures else '**有不一致**'}。"
        f"25 个视图的行数、每一列的非空个数和合计（数值列用定点数合计，其余列用哈希合计）都与原表逐位比对。",
        "",
        "| 原表 | L0 视图 | 原表行数 | 视图行数 | 原列数 | 技术字段 | 结果 |",
        "|---|---|---:|---:|---:|---:|---|",
        *table_lines,
        "",
    ]
    if failures:
        lines += ["## 不一致", "", *[f"- {f}" for f in failures], ""]
    lines += [
        f"## 删掉的关系（{len(dropped)} / {total}，{len(dropped) / total:.0%}）",
        "",
        "SQL 和 DAX 用同一份清单。",
        "",
        "| # | 原关系 | L0 名 | 为什么删 |",
        "|---:|---|---|---|",
    ]
    for i, r in enumerate(dropped, 1):
        lines.append(
            f"| {i} | `{r['from']}` → `{r['to']}` | `{l0_rel(m, r['from'])}` → `{l0_rel(m, r['to'])}` | {r['why']} |"
        )
    lines += [
        "",
        f"## 保留的关系（{len(kept)} / {total}）",
        "",
        "| # | 原关系 | L0 名 |",
        "|---:|---|---|",
    ]
    for i, r in enumerate(kept, 1):
        lines.append(f"| {i} | `{r['from']}` → `{r['to']}` | `{l0_rel(m, r['from'])}` → `{l0_rel(m, r['to'])}` |")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告：{REPORT.relative_to(REPO)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--sql-only", action="store_true", help="只重新生成 render/l0_views.sql")
    g.add_argument("--check-only", action="store_true", help="不重建视图，只核对")
    args = ap.parse_args()

    m = load_map()
    problems = check_map(m)
    if problems:
        sys.exit("l0_map.yaml 静态校验未通过：\n" + "\n".join(f"- {p}" for p in problems))

    sql = generate_sql(m)
    if not args.check_only:
        SQL_FILE.write_text(sql, encoding="utf-8")
        print(f"已生成 {SQL_FILE.relative_to(REPO)}")
    if args.sql_only:
        return

    from chdb import session

    sess = session.Session(str(chdb_dir()))
    try:
        if not args.check_only:
            for stmt in statements(sql):
                sess.query(stmt)
            print(f"已在 chDB 重建库 {m['database']}（{len(m['tables'])} 个视图）", flush=True)
        table_lines, failures = verify(sess, m)
    finally:
        sess.close()

    write_report(m, table_lines, failures)
    if failures:
        sys.exit("核对未通过：\n" + "\n".join(f"- {f}" for f in failures))
    print("核对全部通过")


if __name__ == "__main__":
    main()
