"""Cells run by the SQL direct-answer harness, with their execution scope.

The list mirrors the BOARD unit list (SQL 直答 rows and the English anchors).
``allowed`` is the set of chDB databases a cell may reference; the first one is
the session's default database (T11 card, carried-forward requirement 1).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTEXTS = REPO / "build" / "contexts"
SYNTAX = REPO / "render" / "syntax"
TUNING = REPO / "semantic" / "tuning"


def instructions_path(name: str) -> Path:
    return TUNING / f"{name}.instructions.yaml"


def syntax_path(name: str) -> Path:
    """A cell's syntax note: a bare file name is under render/syntax/ (the semantic-layer tag);
    a path with a slash is relative to the repository (the C13 ladder notes under
    harness/syntax_ladder/, which belong to the harness tag, not to the semantic layer)."""
    return REPO / name if "/" in name else SYNTAX / name


@dataclass(frozen=True)
class Cell:
    name: str
    stack: str                      # executor family: chdb / cube_sql / cube_json / dax
    allowed: tuple[str, ...]        # chDB databases; first = default database
    context: str                    # "build:<file>" (rendered) or "external:<key>" (benchmark docs verbatim)
    syntax: str                     # file under render/syntax/, or a repo-relative path (syntax_path)
    lang: str = "zh"                # question language
    card: str = "T13"               # card that runs it at full scale
    split: str = "all"              # which questions this cell answers: all / tuning / heldout
    skip_judge: bool = False        # never answer judge questions (phase 1 replan §二)
    instructions: str | None = None # semantic/tuning/<name>.instructions.yaml: tuned answer requirements
                                    # and syntax notes (decisions/2026-10-23-tuning-instructions.md)
    selective_k: int | None = None  # T29: append the fixed +1 / -k / 0 scoring rule
    selective_variant: str | None = None  # T29 v2: front-loaded rule or confidence line

    @property
    def runnable_here(self) -> bool:
        """Executors available to the direct-answer runner on this host (DAX: Windows, T17)."""
        return self.stack in {"chdb", "cube_sql", "cube_json"} or (self.stack == "dax" and sys.platform == "win32")


CELLS: dict[str, Cell] = {c.name: c for c in [
    Cell("SQL-L0", "chdb", ("l0",), "build:SQL-L0.yaml", "clickhouse_sql.md"),
    Cell("SQL-R", "chdb", ("retail",), "build:SQL-R.yaml", "clickhouse_sql.md"),
    Cell("SQL-L1", "chdb", ("retail",), "build:SQL-L1.yaml", "clickhouse_sql.md"),
    Cell("SQL-L1c", "chdb", ("retail",), "external:l1c", "clickhouse_sql.md"),
    Cell("SQL-L1.5W", "chdb", ("dwd", "retail"), "build:SQL-L1.5W.yaml", "clickhouse_sql.md"),
    Cell("SQL-L1.5S", "chdb", ("ads",), "build:SQL-L1.5S.yaml", "clickhouse_sql.md"),
    Cell("SQL-L1-tuned", "chdb", ("retail",), "build:SQL-L1-tuned.yaml", "clickhouse_sql.md", card="T14"),
    Cell("SQL-L1-tuned-instr", "chdb", ("retail",), "build:SQL-L1-tuned.yaml", "clickhouse_sql.md", card="T14",
         instructions="SQL-L1"),
    Cell("SQL-L2", "cube_sql", (), "build:SQL-L2.yaml", "cube_sql.md", card="T16"),
    Cell("JSON-L2", "cube_json", (), "build:JSON-L2.yaml", "cube_json.md", card="T16"),
    Cell("SQL-R-EN", "chdb", ("retail",), "external:r-en", "clickhouse_sql.md", lang="en"),
    Cell("SQL-L1c-EN", "chdb", ("retail",), "external:l1c-en", "clickhouse_sql.md", lang="en"),
]}


# T22b units are explicit opt-ins, like the C13 ladder. Preserve --cell all.
L1PLUS_CELLS: dict[str, Cell] = {c.name: c for c in [
    Cell(name, "chdb", ("retail",), f"build:{name}.yaml", "clickhouse_sql.md", card="T22b", skip_judge=True)
    for name in ("SQL-L1plus", "SQL-L3a")
]}


# T29 is an explicit opt-in: same L1plus context and executor, one extra rule.
# Keep it out of CELLS so existing --cell all runs retain their scope.
SELECTIVE_CELLS: dict[str, Cell] = {
    f"SQL-L1plus-sel-k{k}": replace(L1PLUS_CELLS["SQL-L1plus"], name=f"SQL-L1plus-sel-k{k}",
                                    card="T29", selective_k=k)
    for k in (1, 3)
}

SELECTIVE_V2_CELLS: dict[str, Cell] = {
    **{f"SQL-L1plus-sel-k{k}": replace(L1PLUS_CELLS["SQL-L1plus"], name=f"SQL-L1plus-sel-k{k}",
                                      card="T29", selective_k=k) for k in (5, 10, 20, 100)},
    **{f"SQL-L1plus-sel-front-k{k}": replace(L1PLUS_CELLS["SQL-L1plus"], name=f"SQL-L1plus-sel-front-k{k}",
                                            card="T29", selective_k=k, selective_variant="front") for k in (3, 10)},
    "SQL-L1plus-confidence": replace(L1PLUS_CELLS["SQL-L1plus"], name="SQL-L1plus-confidence", card="T29",
                                     split="tuning", selective_variant="confidence"),
}


# T30 is opt-in; --cell all continues to select only the original cells.
COMBO_CELLS = {
    "SQL-L1plus-tuned-instr": Cell(
        "SQL-L1plus-tuned-instr", "chdb", ("retail",),
        "build:SQL-L1plus-tuned-instr.yaml", "clickhouse_sql.md",
        card="T30", skip_judge=True, instructions="SQL-L1",
    )
}


# C13 syntax-note teaching ladder (decisions/2026-10-19-phase1-replan.md §三): SQL-L1's system
# prompt and semantic context, only the syntax note changes. Depth per
# decisions/2026-10-19-self-built-p-and-cube-notes.md §五: T2 = rules + conditions and pitfalls,
# T3 = T2 + generic examples tied to no question, T4 = T3 + few-shot examples from tuning-split
# questions, so T4 answers held-out questions only. None answers judge questions. Kept apart from
# CELLS so that ``run_direct --cell all`` never picks them up.
LADDER = "harness/syntax_ladder"
LADDER_CELLS: dict[str, Cell] = {c.name: c for c in [
    Cell("SQL-L1-T2", "chdb", ("retail",), "build:SQL-L1.yaml", f"{LADDER}/clickhouse_sql_t2.md", card="C13",
         skip_judge=True),
    Cell("SQL-L1-T3", "chdb", ("retail",), "build:SQL-L1.yaml", f"{LADDER}/clickhouse_sql_t3.md", card="C13",
         skip_judge=True),
    Cell("SQL-L1-T4", "chdb", ("retail",), "build:SQL-L1.yaml", f"{LADDER}/clickhouse_sql_t4.md", card="C13",
         split="heldout", skip_judge=True),
]}

# DAX direct-answer cells (T17 smoke, T18 full run): Power BI Desktop on Windows, one model open
# at a time, so a run takes one DAX cell (run_direct refuses more). Kept apart from CELLS so that
# ``run_direct --cell all`` never picks them up.
DAX_CELLS: dict[str, Cell] = {c.name: c for c in [
    Cell(f"DAX-{tier}", "dax", (), f"build:DAX-{tier}.yaml", "dax.md", card="T18") for tier in ("L0", "L1", "L2")
]}


def dax_tier(cell: Cell) -> str:
    """DAX-L1 → L1 (the PBIP / model the cell runs on)."""
    return cell.name.split("-", 1)[1]


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
