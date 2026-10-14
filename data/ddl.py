"""Parse the vendored ClickHouse DDL (``vendor/cube/retail_schema.sql``).

Shared by ``load.py``, ``export_parquet.py`` and ``build_chdb_copy.py`` so all three
agree on the table list, the column order and the column types. The DDL is the
contract: it comes from the external benchmark (see ``vendor/cube/NOTICE.md``) and
is never edited here.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

DATABASE = "retail"

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "vendor" / "cube" / "retail_schema.sql"

_TABLE_RE = re.compile(
    r"CREATE TABLE " + DATABASE + r"\.(?P<name>\w+)\s*\((?P<cols>.*?)\)\s*ENGINE",
    re.S,
)
_STMT_RE = re.compile(r"(CREATE TABLE " + DATABASE + r"\.\w+.*?)\s*;", re.S)
_COL_RE = re.compile(r"^\s*`(?P<name>[^`]+)`\s+(?P<type>.+?),?\s*$")


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[tuple[str, str], ...]  # (name, ClickHouse type), in DDL order
    create_sql: str

    @property
    def column_names(self) -> list[str]:
        return [c for c, _ in self.columns]

    @property
    def structure(self) -> str:
        """Structure string for chDB's ``file(path, 'CSV', <structure>)``."""
        return ", ".join(f"`{c}` {t}" for c, t in self.columns)


def tables() -> list[Table]:
    text = SCHEMA.read_text(encoding="utf-8")
    stmts = {}
    for m in _STMT_RE.finditer(text):
        sql = m.group(1).strip()
        stmts[re.search(r"CREATE TABLE " + DATABASE + r"\.(\w+)", sql).group(1)] = sql

    out: list[Table] = []
    for m in _TABLE_RE.finditer(text):
        name = m.group("name")
        cols = []
        for line in m.group("cols").strip().splitlines():
            cm = _COL_RE.match(line)
            if cm:
                cols.append((cm.group("name"), cm.group("type").rstrip(",")))
        if not cols:
            raise SystemExit(f"{SCHEMA}: {name} 没解析出列")
        out.append(Table(name, tuple(cols), stmts[name]))
    if not out:
        raise SystemExit(f"{SCHEMA}: 没解析出任何 CREATE TABLE")
    return out


def data_dir() -> Path:
    """``SEMDEBT_DATA_DIR`` — all data lives outside the repo (hard rule 4)."""
    raw = os.environ.get("SEMDEBT_DATA_DIR")
    if not raw:
        raise SystemExit("环境变量 SEMDEBT_DATA_DIR 没设，见 AGENTS.md「环境」")
    d = Path(raw).expanduser()
    if not d.is_dir():
        raise SystemExit(f"SEMDEBT_DATA_DIR 不存在：{d}")
    return d
