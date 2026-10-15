"""Snapshot the column types of the four chDB databases the contexts describe.

The renderers need a type for every column (R and L0 show only names and types).
``retail`` types come from the vendored DDL, but ``dwd`` (wide tables), ``ads``
(summary layer) and ``l0`` (degraded views) only exist as built objects in chDB.
This script reads them once and writes ``render/physical_schema.json`` (committed),
so rendering does not need the data directory and the frozen tag pins the types.

    uv run python render/snapshot_schema.py

Rerun after ``render/build_widetables.py``, ``render/build_summary.py`` or
``render/build_l0.py`` changes a view; ``tests/test_render.py`` checks the snapshot
against the DDL and the source files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "render" / "physical_schema.json"
DATABASES = ("retail", "dwd", "ads", "l0")


def chdb_dir() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        raise SystemExit("SEMDEBT_DATA_DIR 未设置")
    return Path(root).expanduser() / "chdb"


def main() -> None:
    from chdb import session

    sess = session.Session(str(chdb_dir()))
    try:
        snap: dict[str, dict[str, list[list[str]]]] = {}
        for db in DATABASES:
            tables = sess.query(
                f"SELECT name FROM system.tables WHERE database = '{db}' ORDER BY name", "TSV"
            ).bytes().decode().split()
            snap[db] = {}
            for t in tables:
                rows = sess.query(
                    f"SELECT name, type FROM system.columns WHERE database = '{db}' AND table = '{t}' "
                    "ORDER BY position",
                    "TSV",
                ).bytes().decode().splitlines()
                snap[db][t] = [r.replace("\\'", "'").split("\t") for r in rows]
    finally:
        sess.close()
    OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"写入 {OUT.relative_to(REPO)}：" + "，".join(f"{db} {len(v)} 张" for db, v in snap.items()))


if __name__ == "__main__":
    main()
