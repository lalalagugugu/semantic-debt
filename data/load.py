#!/usr/bin/env python
"""Rebuild the Contoso retail warehouse (25 tables) in chDB from the Kaggle CSV zip.

One command does everything:

    uv run python data/load.py

Steps: unzip → compare every CSV header against ``vendor/cube/retail_schema.sql``
→ create ``retail`` → load each table positionally → print row counts.

Nothing is written inside the repo: the CSVs land in ``$SEMDEBT_DATA_DIR/raw/csv/``
and the chDB data directory is ``$SEMDEBT_DATA_DIR/chdb/`` (hard rule 4).
Only one process may hold a chDB data directory open (hard rule 9).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
import time
import zipfile
from pathlib import Path

from ddl import DATABASE, Table, data_dir, tables

# The Kaggle export writes the pandas index as an unnamed leading column; the DDL
# calls that column RowNum. Only this one table is affected, and only in the header.
UNNAMED_OK = {"DimCustomer": "RowNum"}


def log(msg: str) -> None:
    print(msg, flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def unzip(zip_path: Path, csv_dir: Path, force: bool) -> None:
    if not zip_path.is_file():
        raise SystemExit(
            f"找不到数据 zip：{zip_path}\n"
            "按 data/README.md「复现步骤」先把 Kaggle 的 archive.zip 放进 $SEMDEBT_DATA_DIR/raw/"
        )
    csv_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            target = csv_dir / Path(info.filename).name
            if not force and target.is_file() and target.stat().st_size == info.file_size:
                continue
            log(f"  解压 {info.filename} ({info.file_size:,} 字节)")
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)


def check_headers(csv_dir: Path, specs: list[Table]) -> None:
    """Abort unless every CSV lines up column-for-column with the vendored DDL.

    The card requires this comparison before any loading: if the Kaggle export does
    not match the external benchmark's schema, stop and show the user the diff.
    """
    problems: list[str] = []
    for t in specs:
        path = csv_dir / f"{t.name}.csv"
        if not path.is_file():
            problems.append(f"{t.name}: zip 里没有 {t.name}.csv")
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            header = next(csv.reader(fh))
        expected = t.column_names
        if len(header) != len(expected):
            problems.append(
                f"{t.name}: 列数不同，DDL {len(expected)} 列，CSV {len(header)} 列\n"
                f"    DDL: {expected}\n    CSV: {header}"
            )
            continue
        for i, (got, want) in enumerate(zip(header, expected)):
            if got == want:
                continue
            if got == "" and UNNAMED_OK.get(t.name) == want:
                log(f"  {t.name}: 第 {i + 1} 列 CSV 表头为空，按位置对应 DDL 的 {want}")
                continue
            problems.append(
                f"{t.name}: 第 {i + 1} 列名不同，DDL `{want}`，CSV `{got}`"
            )
    if problems:
        raise SystemExit(
            "CSV 与 vendor/cube/retail_schema.sql 对不上，已停止（任务卡：对不上就停下，把差异给用户）：\n"
            + "\n".join(f"  - {p}" for p in problems)
        )
    log(f"  表头核对通过：{len(specs)} 张表，列名与列序与 DDL 一致")


def load(db_dir: Path, csv_dir: Path, specs: list[Table], force: bool) -> list[tuple[str, int]]:
    from chdb import session

    if force and db_dir.exists():
        log(f"  删掉旧的 chDB 目录 {db_dir}")
        shutil.rmtree(db_dir)
    db_dir.parent.mkdir(parents=True, exist_ok=True)

    sess = session.Session(str(db_dir))
    counts: list[tuple[str, int]] = []
    try:
        sess.query(f"CREATE DATABASE IF NOT EXISTS {DATABASE}")
        for t in specs:
            path = csv_dir / f"{t.name}.csv"
            sess.query(f"DROP TABLE IF EXISTS {DATABASE}.{t.name}")
            sess.query(t.create_sql)
            t0 = time.monotonic()
            # Positional insert: the structure comes from the DDL and the CSV header
            # row is skipped, so an unnamed header column cannot shift anything.
            sess.query(
                f"INSERT INTO {DATABASE}.{t.name} "
                f"SELECT * FROM file('{path}', 'CSV', $${t.structure}$$) "
                "SETTINGS input_format_csv_skip_first_lines = 1, "
                "input_format_csv_empty_as_default = 1"
            )
            n = int(str(sess.query(f"SELECT count() FROM {DATABASE}.{t.name}", "CSV")).strip())
            counts.append((t.name, n))
            log(f"  {t.name:24s} {n:>12,} 行  {time.monotonic() - t0:6.1f}s")
    finally:
        sess.close()
    return counts


def main(argv: list[str] | None = None) -> int:
    d = data_dir()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", type=Path, default=d / "raw" / "archive.zip", help="Kaggle zip（默认 $SEMDEBT_DATA_DIR/raw/archive.zip）")
    ap.add_argument("--csv-dir", type=Path, default=d / "raw" / "csv", help="解压目标目录")
    ap.add_argument("--db-dir", type=Path, default=d / "chdb", help="chDB 数据目录")
    ap.add_argument("--force", action="store_true", help="重新解压并重建 chDB 目录")
    ap.add_argument("--check-only", action="store_true", help="只解压并核对表头，不导入")
    ap.add_argument("--sha256", action="store_true", help="另外算一遍 zip 的 sha256（慢）")
    args = ap.parse_args(argv)

    specs = tables()
    log(f"DDL: {len(specs)} 张表（vendor/cube/retail_schema.sql）")

    if args.sha256:
        log(f"zip sha256: {sha256(args.zip)}")

    log(f"1/3 解压 {args.zip} → {args.csv_dir}")
    unzip(args.zip, args.csv_dir, args.force)

    log("2/3 核对 CSV 表头与 DDL")
    check_headers(args.csv_dir, specs)
    if args.check_only:
        log("--check-only：到此为止，没有导入")
        return 0

    log(f"3/3 导入 chDB → {args.db_dir}")
    counts = load(args.db_dir, args.csv_dir, specs, args.force)

    total = sum(n for _, n in counts)
    log(f"完成：{len(counts)} 张表，共 {total:,} 行，库名 {DATABASE}，数据目录 {args.db_dir}")
    empty = [t for t, n in counts if n == 0]
    if empty:
        log(f"注意：以下表 0 行，请检查：{empty}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
