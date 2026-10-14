"""The vendored DDL is the contract between the data scripts and everything after.

These tests do not touch the data (it lives outside the repo); they only check that
``vendor/cube/retail_schema.sql`` still parses into the 25 tables the design assumes
and that ``data/load.py`` keeps deriving its CSV structure from it.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "data"))

import ddl  # noqa: E402
import load  # noqa: E402

EXPECTED_TABLE_COUNT = 25


def test_schema_parses_into_25_tables() -> None:
    names = [t.name for t in ddl.tables()]
    assert len(names) == EXPECTED_TABLE_COUNT, names
    assert len(set(names)) == len(names), "表名重复"
    assert sum(n.startswith("Fact") for n in names) == 8
    assert sum(n.startswith("Dim") for n in names) == 17


def test_every_table_has_columns_and_a_create_statement() -> None:
    for t in ddl.tables():
        assert t.columns, t.name
        assert t.create_sql.startswith(f"CREATE TABLE {ddl.DATABASE}.{t.name}"), t.name
        assert "ENGINE" in t.create_sql, t.name
        # structure 要能直接喂给 chDB 的 file(..., 'CSV', <structure>)
        assert t.structure.count("`") == 2 * len(t.columns), t.name


def test_structure_is_positional_for_the_known_header_quirk() -> None:
    """DimCustomer 的 CSV 第一列表头为空，DDL 叫 RowNum；必须是第一列才不会错位。"""
    for table, col in load.UNNAMED_OK.items():
        spec = next(t for t in ddl.tables() if t.name == table)
        assert spec.column_names[0] == col, (table, spec.column_names[:2])
