"""L0 劣化映射的静态校验（T09）。

不连数据库。视图的行数、逐列合计由

    uv run python render/build_l0.py

单独核对（chDB 的同一个数据目录不能被两个进程同时打开，硬规则 9）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from render.build_l0 import MAP_FILE, SQL_FILE, check_map, generate_sql, load_map  # noqa: E402

pytestmark = pytest.mark.skipif(not MAP_FILE.is_file(), reason="semantic/l0_map.yaml 还没写")


def test_map_passes_static_checks() -> None:
    assert check_map(load_map()) == []


def test_map_is_reversible() -> None:
    """由（L0 表名, L0 列名）能唯一还原（原表名, 原列名）。"""
    m = load_map()
    inverse: dict[tuple[str, str], tuple[str, str]] = {}
    for t in m["tables"]:
        for src, l0 in t["columns"].items():
            key = (t["l0"], l0)
            assert key not in inverse, f"{key} 对应不止一个原列"
            inverse[key] = (t["source"], src)
    forward = {(t["source"], s): (t["l0"], l) for t in m["tables"] for s, l in t["columns"].items()}
    assert {v: k for k, v in inverse.items()} == forward


def test_no_descriptions_or_semantics() -> None:
    """L0 没有任何描述、同义词、约定和指标口径。"""
    m = load_map()
    assert set(m) == {"version", "source_database", "database", "tables", "relationships"}
    for t in m["tables"]:
        assert set(t) <= {"source", "l0", "columns", "technical_columns"}, t["source"]
        for c in t.get("technical_columns", []):
            assert set(c) == {"name", "expr"}, (t["source"], c)


def test_about_a_third_of_relationships_dropped() -> None:
    rels = load_map()["relationships"]
    total = len(rels["kept"]) + len(rels["dropped"])
    assert round(total / 3) == len(rels["dropped"])


def test_committed_sql_is_up_to_date() -> None:
    assert SQL_FILE.is_file(), "缺 render/l0_views.sql，跑 render/build_l0.py --sql-only"
    assert SQL_FILE.read_text(encoding="utf-8") == generate_sql(load_map()), (
        "render/l0_views.sql 与 l0_map.yaml 不同步，跑 render/build_l0.py --sql-only"
    )
