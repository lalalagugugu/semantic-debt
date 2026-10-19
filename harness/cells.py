"""Cells run by the SQL direct-answer harness, with their execution scope.

The list mirrors the BOARD unit list (SQL 直答 rows and the English anchors).
``allowed`` is the set of chDB databases a cell may reference; the first one is
the session's default database (T11 card, carried-forward requirement 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTEXTS = REPO / "build" / "contexts"
SYNTAX = REPO / "render" / "syntax"


@dataclass(frozen=True)
class Cell:
    name: str
    stack: str                      # executor family: chdb / cube_sql / cube_json / dax
    allowed: tuple[str, ...]        # chDB databases; first = default database
    context: str                    # "build:<file>" (rendered) or "external:<key>" (benchmark docs verbatim)
    syntax: str                     # file under render/syntax/
    lang: str = "zh"                # question language
    card: str = "T13"               # card that runs it at full scale
    split: str = "all"              # which questions this cell answers

    @property
    def runnable_here(self) -> bool:
        """T11 implements chDB only; other stacks reuse this harness with their own executor."""
        return self.stack == "chdb"


CELLS: dict[str, Cell] = {c.name: c for c in [
    Cell("SQL-L0", "chdb", ("l0",), "build:SQL-L0.yaml", "clickhouse_sql.md"),
    Cell("SQL-R", "chdb", ("retail",), "build:SQL-R.yaml", "clickhouse_sql.md"),
    Cell("SQL-L1", "chdb", ("retail",), "build:SQL-L1.yaml", "clickhouse_sql.md"),
    Cell("SQL-L1c", "chdb", ("retail",), "external:l1c", "clickhouse_sql.md"),
    Cell("SQL-L1.5W", "chdb", ("dwd", "retail"), "build:SQL-L1.5W.yaml", "clickhouse_sql.md"),
    Cell("SQL-L1.5S", "chdb", ("ads",), "build:SQL-L1.5S.yaml", "clickhouse_sql.md"),
    Cell("SQL-L1-tuned", "chdb", ("retail",), "build:SQL-L1-tuned.yaml", "clickhouse_sql.md", card="T14"),
    Cell("SQL-L2", "cube_sql", (), "build:SQL-L2.yaml", "cube_sql.md", card="T16"),
    Cell("SQL-R-EN", "chdb", ("retail",), "external:r-en", "clickhouse_sql.md", lang="en"),
    Cell("SQL-L1c-EN", "chdb", ("retail",), "external:l1c-en", "clickhouse_sql.md", lang="en"),
]}


# Explorer agent cells (-E, T15): the direct cell's prompt, context and execution scope,
# plus the read-only ``run_sql`` tool on the same backend. Kept apart from CELLS so that
# ``run_direct --cell all`` never picks them up.
AGENT_CELLS: dict[str, Cell] = {f"{base}-E": CELLS[base] for base in ("SQL-L0", "SQL-L1", "SQL-L2")}

# Planning agent cells (-P, T21): the direct cell's execution scope, syntax notes and rendered
# context (as a catalog plus ``lookup``), with plan / run_sql / python tools. L0 and L1 only.
PLAN_CELLS: dict[str, Cell] = {f"{base}-P": CELLS[base] for base in ("SQL-L0", "SQL-L1")}

# DeepSeek official prices, CNY per 1M tokens, off-peak (peak = 2x).
# Source: https://api-docs.deepseek.com/zh-cn/quick_start/pricing, read 2026-10-16.
PRICES_OFFPEAK: dict[str, dict[str, float]] = {
    "deepseek-flash": {"hit": 0.02, "miss": 1.0, "output": 4.0},
    "deepseek-v4-pro": {"hit": 0.15, "miss": 4.5, "output": 13.5},
}
PEAK_MULTIPLIER = 2.0

# Execution timeout (seconds). An explicit parameter, see
# open question T11-1 (default pending the user's ruling). Timeouts are classified on their own.
DEFAULT_EXEC_TIMEOUT_S = 120
DEFAULT_REPS = 3
DEFAULT_CONCURRENCY = 8
