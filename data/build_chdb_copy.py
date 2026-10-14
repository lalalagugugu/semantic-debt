#!/usr/bin/env python
"""Build an independent chDB data directory from the exported Parquet files.

    uv run python data/build_chdb_copy.py "$SEMDEBT_DATA_DIR/chdb-eval"

Why: one chDB data directory must not be open in two processes (hard rule 9), so
the eval side gets its own copy instead of sharing ``$SEMDEBT_DATA_DIR/chdb``.
Tables are created from the same vendored DDL and filled from Parquet, so the copy
has the same schema, not just the same data.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

from ddl import DATABASE, data_dir, tables


def log(msg: str) -> None:
    print(msg, flush=True)


def main(argv: list[str] | None = None) -> int:
    d = data_dir()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", type=Path, help="要建的 chDB 数据目录，例如 $SEMDEBT_DATA_DIR/chdb-eval")
    ap.add_argument("--parquet-dir", type=Path, default=d / "parquet", help="Parquet 来源目录")
    ap.add_argument("--force", action="store_true", help="目标目录已存在时先删掉")
    args = ap.parse_args(argv)

    specs = tables()
    missing = [t.name for t in specs if not (args.parquet_dir / f"{t.name}.parquet").is_file()]
    if missing:
        raise SystemExit(
            f"{args.parquet_dir} 缺 Parquet：{missing}\n先跑 data/export_parquet.py"
        )

    if args.target.exists():
        if not args.force:
            raise SystemExit(f"目标目录已存在：{args.target}（要重建就加 --force）")
        log(f"  删掉旧目录 {args.target}")
        shutil.rmtree(args.target)
    args.target.parent.mkdir(parents=True, exist_ok=True)

    from chdb import session

    sess = session.Session(str(args.target))
    counts: list[tuple[str, int]] = []
    try:
        sess.query(f"CREATE DATABASE IF NOT EXISTS {DATABASE}")
        for t in specs:
            src = args.parquet_dir / f"{t.name}.parquet"
            sess.query(t.create_sql)
            t0 = time.monotonic()
            sess.query(
                f"INSERT INTO {DATABASE}.{t.name} "
                f"SELECT * FROM file('{src}', 'Parquet')"
            )
            n = int(str(sess.query(f"SELECT count() FROM {DATABASE}.{t.name}", "CSV")).strip())
            counts.append((t.name, n))
            log(f"  {t.name:24s} {n:>12,} 行  {time.monotonic() - t0:6.1f}s")
    finally:
        sess.close()

    log(f"完成：{len(counts)} 张表，共 {sum(n for _, n in counts):,} 行，数据目录 {args.target}")
    empty = [t for t, n in counts if n == 0]
    if empty:
        log(f"注意：以下表 0 行，请检查：{empty}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
