#!/usr/bin/env python
"""Export the 25 ``retail`` tables from chDB to Parquet.

    uv run python data/export_parquet.py

Output: ``$SEMDEBT_DATA_DIR/parquet/<table>.parquet``. The Parquet files are the
hand-off format: ``data/build_chdb_copy.py`` rebuilds an independent chDB data
directory from them, so the eval side never has to open the main one
(hard rule 9).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from ddl import DATABASE, data_dir, tables


def log(msg: str) -> None:
    print(msg, flush=True)


def main(argv: list[str] | None = None) -> int:
    d = data_dir()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db-dir", type=Path, default=d / "chdb", help="chDB 数据目录（读）")
    ap.add_argument("--out-dir", type=Path, default=d / "parquet", help="Parquet 输出目录")
    args = ap.parse_args(argv)

    if not args.db_dir.is_dir():
        raise SystemExit(f"chDB 数据目录不存在，先跑 data/load.py：{args.db_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    from chdb import session

    specs = tables()
    sess = session.Session(str(args.db_dir))
    try:
        for t in specs:
            target = args.out_dir / f"{t.name}.parquet"
            target.unlink(missing_ok=True)
            t0 = time.monotonic()
            sess.query(
                f"INSERT INTO FUNCTION file('{target}', 'Parquet') "
                f"SELECT * FROM {DATABASE}.{t.name}"
            )
            size = target.stat().st_size
            log(f"  {t.name:24s} {size:>14,} 字节  {time.monotonic() - t0:6.1f}s")
    finally:
        sess.close()

    total = sum((args.out_dir / f"{t.name}.parquet").stat().st_size for t in specs)
    log(f"完成：{len(specs)} 个 Parquet，共 {total:,} 字节，目录 {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
