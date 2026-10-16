"""Import T01 Parquet into Docker ClickHouse and compare it with the chDB copy.

    uv run python data/clickhouse_t16.py --import-data

An existing nonempty table is never overwritten. Both fresh and existing tables
are checked against chDB using row counts and exact six-decimal numeric sums.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.ddl import DATABASE, REPO, data_dir, tables


def query(sql: str) -> str:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "clickhouse", "clickhouse-client", "--query", sql],
        cwd=REPO, capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"ClickHouse client exited {result.returncode}")
    return result.stdout.strip()


def fingerprint_sql(table) -> tuple[str, list[str]]:
    numeric = [name for name, kind in table.columns if any(t in kind for t in ("Int", "Float", "Decimal"))]
    expressions = ["count()"] + [f"toString(sum(toDecimal128(`{name}`, 6)))" for name in numeric]
    return f"SELECT {', '.join(expressions)} FROM {DATABASE}.{table.name} FORMAT JSONCompact", ["rows", *numeric]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--import-data", action="store_true")
    ap.add_argument("--db-dir", type=Path, help="Independent chDB baseline; defaults to $SEMDEBT_DATA_DIR/chdb-t16")
    args = ap.parse_args()
    root = data_dir()
    baseline = args.db_dir or root / "chdb-t16"
    specs = tables()
    if not baseline.is_dir():
        raise SystemExit("Missing chDB baseline; run data/build_chdb_copy.py with $SEMDEBT_DATA_DIR/chdb-t16")
    for table in specs:
        if not (root / "parquet" / f"{table.name}.parquet").is_file():
            raise SystemExit(f"Missing Parquet: {table.name}")
    if args.import_data:
        query(f"CREATE DATABASE IF NOT EXISTS {DATABASE}")
        for table in specs:
            exists = query(f"EXISTS TABLE {DATABASE}.{table.name}") == "1"
            if not exists:
                query(table.create_sql)
            if query(f"SELECT count() FROM {DATABASE}.{table.name}") == "0":
                query(f"INSERT INTO {DATABASE}.{table.name} SELECT * FROM file('parquet/{table.name}.parquet', 'Parquet')")
                print(f"Imported {table.name}", flush=True)

    from chdb import session

    # chDB itself takes an exclusive lock: never share an open data directory.
    sess = session.Session(str(baseline))
    checks = []
    try:
        baseline_version = str(sess.query("SELECT version()", "TSV")).strip()
        for table in specs:
            sql, columns = fingerprint_sql(table)
            expected = json.loads(str(sess.query(sql, "JSONCompact")))["data"][0]
            actual = json.loads(query(sql))["data"][0]
            # ClickHouse JSON may quote Int64 counts; sums are explicit strings.
            expected, actual = [str(x) for x in expected], [str(x) for x in actual]
            checks.extend((table.name, col, want, got, want == got)
                          for col, want, got in zip(columns, expected, actual, strict=True))
            print(f"Checked {table.name}: {actual[0]} rows", flush=True)
    finally:
        sess.close()
    # Anchor the independent rebuild to the original T01 report as well: sharing
    # a Parquet source alone would not detect an old or wrong export.
    t01 = (REPO / "reports" / "validation" / "data_load.md").read_text(encoding="utf-8")
    original = {(table, "rows"): count.replace(",", "") for table, count in
                re.findall(r"^\| `(\w+)` \| ([\d,]+) \|", t01, re.MULTILINE)}
    original.update({(table, col): value.strip() for table, col, value in
                     re.findall(r"^\| `(\w+)` \| `(\w+)` \| ([^|]+) \|", t01, re.MULTILINE)})
    anchored = [(table, col, original[(table, col)], got,
                 Decimal(original[(table, col)]) == Decimal(got))
                for table, col, _, got, _ in checks if (table, col) in original]
    if len(anchored) != len(original) or sum(col == "rows" for _, col, *_ in anchored) != len(specs):
        raise RuntimeError("T01 baseline report does not cover the expected tables/columns")
    failures = sum(not row[4] for row in [*checks, *anchored])
    out = ["# T16 ClickHouse 数据核对", "",
           "复现：`uv run python data/clickhouse_t16.py --import-data`。已有非空表不覆盖，重新核对。", "",
           f"- ClickHouse：`{query('SELECT version()')}`；chDB 内核：`{baseline_version}`。",
           "- 来源：T01 Parquet；基线：独立 chDB 副本（默认 `$SEMDEBT_DATA_DIR/chdb-t16`）。",
           "- 每表核对行数，以及所有数值列的 `sum(toDecimal128(列, 6))`，逐位比较。",
           f"- {len(specs)} 张表，{len(checks)} 项核对，不一致 {failures} 项。", "",
           f"- 另与 T01 原始主 chDB 报告交叉核对 {len(anchored)} 项（25 个行数 + 事实表主要合计）。", "",
           "| 表 | 核对项 | chDB | ClickHouse | 结果 |", "|---|---|---:|---:|---|"]
    out.extend(f"| {table} | {col} | {want} | {got} | {'通过' if ok else '不通过'} |"
               for table, col, want, got, ok in checks)
    out += ["", "## 与 T01 原始报告比较", "", "| 表 | 核对项 | T01 主 chDB | ClickHouse | 结果 |", "|---|---|---:|---:|---|"]
    out.extend(f"| {table} | {col} | {want} | {got} | {'通过' if ok else '不通过'} |"
               for table, col, want, got, ok in anchored)
    path = REPO / "reports" / "validation" / "clickhouse_t16.md"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit(f"{failures} data checks failed; see {path}")


if __name__ == "__main__":
    main()
