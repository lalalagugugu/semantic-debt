"""Query executors: ``execute(query) -> ExecResult``.

Every stack gets the same interface. Only chDB is implemented here (T11); the
Cube SQL, Cube JSON and DAX executors are placeholders for T16 / T17.

The chDB executor enforces a per-cell *database scope* before execution
(T11 card, carried-forward requirement 1): a query that names a table in a
database outside the cell's allowed set is rejected statically and reported as
an ordinary execution error with ``error_class = "scope_violation"``, so the
harness sends it back to the model like any other error, and the report can
count it separately (decisions/2026-10-16-l1_5s-lineage-and-execution-scope.md).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

# Error classes. Anything not listed here is "engine_error" (the model wrote a
# query the engine rejected or failed on).
SCOPE_VIOLATION = "scope_violation"
FORBIDDEN_STATEMENT = "forbidden_statement"
TIMEOUT = "timeout"
RESULT_TOO_LARGE = "result_too_large"
ENGINE_ERROR = "engine_error"

DEFAULT_MAX_RESULT_ROWS = 100_000
# Table functions that only generate values. Anything else (file, url, s3,
# remote, merge, mysql, ...) reaches outside the cell and is rejected.
ALLOWED_TABLE_FUNCTIONS = frozenset({"numbers", "numbers_mt", "zeros", "zeros_mt", "generateSeries", "generate_series", "values"})
# Session settings the harness pins; a query may not override them.
_PINNED_SETTING = re.compile(r"\b(max_execution_time\w*|timeout_\w+|max_result_\w+|result_overflow_mode|readonly|output_format_\w+|max_estimated_execution_time)\s*=", re.IGNORECASE)


@dataclass(frozen=True)
class ExecResult:
    """Outcome of one execution. Exactly one of ``rows`` / ``error`` is set."""

    rows: list[list[object]] | None = None
    columns: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None
    error_class: str | None = None
    elapsed_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None

    def summary(self, max_error: int = 500) -> dict[str, object]:
        """Log-safe summary: shape, types and a hash — never the rows themselves."""
        if self.ok:
            payload = json.dumps(self.rows, ensure_ascii=False, separators=(",", ":"), default=str)
            return {
                "status": "ok",
                "row_count": len(self.rows or []),
                "columns": self.columns,
                "result_sha256": hashlib.sha256(payload.encode()).hexdigest(),
                "elapsed_s": round(self.elapsed_s, 3),
            }
        return {
            "status": "error",
            "error_class": self.error_class,
            "error": (self.error or "")[:max_error],
            "elapsed_s": round(self.elapsed_s, 3),
        }


class Executor(Protocol):
    name: str

    def execute(self, query: str) -> ExecResult: ...


# ---------------------------------------------------------------------------
# Static checks on ClickHouse SQL


def mask_sql(sql: str) -> str:
    """Blank out comments and string / quoted-identifier contents, keeping offsets."""
    pattern = r"--[^\n]*|/\*.*?\*/|'(?:''|\\.|[^'\\])*'|\"(?:\"\"|[^\"])*\"|`[^`]*`"
    return re.sub(pattern, lambda m: " " * len(m.group()), sql, flags=re.DOTALL)


def strip_trailing_semicolons(sql: str) -> str:
    sql = sql.strip()
    while sql.endswith(";"):
        sql = sql[:-1].rstrip()
    return sql


_AST_LINE = re.compile(r"^(?P<indent> *)(?P<node>\w+)(?: (?P<arg>[^ (]+))?(?: \(alias (?P<alias>[^)]+)\))?")


def ast_references(ast_text: str) -> tuple[list[str], list[str], set[str], list[str]]:
    """Parse ``EXPLAIN AST`` output.

    Returns (table identifiers, table functions, aliases, two-or-more-part
    identifiers). Table identifiers keep their database prefix when written.
    """
    tables: list[str] = []
    functions: list[str] = []
    aliases: set[str] = set()
    identifiers: list[str] = []
    pending_table_expr_indent: int | None = None
    for line in ast_text.splitlines():
        m = _AST_LINE.match(line)
        if not m:
            continue
        indent, node, arg, alias = len(m.group("indent")), m.group("node"), m.group("arg"), m.group("alias")
        if alias:
            aliases.add(alias)
        if node == "TableExpression":
            pending_table_expr_indent = indent
            continue
        if pending_table_expr_indent is not None and indent == pending_table_expr_indent + 1:
            if node == "TableIdentifier" and arg:
                tables.append(arg)
            elif node == "Function" and arg:
                functions.append(arg)
            pending_table_expr_indent = None
            continue
        if node == "TableIdentifier" and arg:
            tables.append(arg)
        elif node == "Identifier" and arg and "." in arg:
            identifiers.append(arg)
    return tables, functions, aliases, identifiers


def scope_violations(ast_text: str, allowed: frozenset[str], known_databases: frozenset[str]) -> list[str]:
    """Names in the query that point outside the allowed databases.

    An unqualified table name resolves to the cell's default database (or a CTE)
    and is allowed. ``db.table`` must use an allowed ``db``. A dotted column
    reference whose first part is a known database that is not allowed (and not
    a query alias) is also rejected, which catches ``x IN otherdb.table``.
    """
    tables, functions, aliases, identifiers = ast_references(ast_text)
    bad: list[str] = []
    for name in tables:
        if "." in name:
            db = name.split(".", 1)[0]
            if db not in allowed:
                bad.append(name)
    for fn in functions:
        if fn not in ALLOWED_TABLE_FUNCTIONS:
            bad.append(f"{fn}()")
    for ident in identifiers:
        first = ident.split(".", 1)[0]
        if first in known_databases and first not in allowed and first not in aliases:
            bad.append(ident)
    return sorted(set(bad))


# ---------------------------------------------------------------------------
# chDB


class _ChdbEngine:
    """One chDB session per data directory per process (hard rule 9), serialised by a lock."""

    _instances: dict[str, "_ChdbEngine"] = {}
    _guard = threading.Lock()

    def __init__(self, path: str) -> None:
        from chdb import session  # imported lazily so offline tests need no chDB

        self.path = path
        self.session = session.Session(path)
        self.lock = threading.Lock()
        self.databases = frozenset(
            line.strip() for line in str(self.session.query("SHOW DATABASES", "TSV")).splitlines() if line.strip()
        )
        self._settings: tuple[int, int] | None = None

    @classmethod
    def get(cls, path: str) -> "_ChdbEngine":
        with cls._guard:
            if path not in cls._instances:
                cls._instances[path] = cls(path)
            return cls._instances[path]

    def resync(self) -> None:
        """Drain stale output. Caller holds ``self.lock``.

        chDB quirk (chdb 3.x, observed 2026-10-16): when a query fails while
        streaming (timeout, result limit, throwIf ...), the *next* query on the
        session returns the failed query's partial output instead of its own.
        Run a sentinel until the session answers with the sentinel itself.
        """
        for n in range(5):
            token = f"semdebt-sync-{time.monotonic_ns()}-{n}"
            try:
                if str(self.session.query(f"SELECT '{token}'", "TSV")).strip() == token:
                    return
            except Exception:
                continue
        raise RuntimeError("chDB session could not be resynchronised after an error")

    def configure(self, timeout_s: int, max_rows: int) -> None:
        """Pin session settings. Caller holds ``self.lock``."""
        if self._settings == (timeout_s, max_rows):
            return
        for statement in (
            f"SET max_execution_time = {int(timeout_s)}",
            "SET timeout_overflow_mode = 'throw'",
            f"SET max_result_rows = {int(max_rows)}",
            "SET result_overflow_mode = 'throw'",
            "SET output_format_json_quote_64bit_integers = 0",
            "SET output_format_json_quote_decimals = 0",
        ):
            self.session.query(statement)
        self._settings = (timeout_s, max_rows)


def default_chdb_path() -> str:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        raise RuntimeError("SEMDEBT_DATA_DIR is not set")
    return str(Path(root).expanduser() / "chdb")


class ChdbExecutor:
    """Read-only ClickHouse SQL on chDB, restricted to a set of databases."""

    def __init__(self, allowed: tuple[str, ...], *, timeout_s: int, path: str | None = None,
                 max_result_rows: int = DEFAULT_MAX_RESULT_ROWS, name: str | None = None) -> None:
        if not allowed:
            raise ValueError("allowed databases must not be empty")
        self.allowed = frozenset(allowed)
        self.default_db = allowed[0]
        self.timeout_s = timeout_s
        self.max_result_rows = max_result_rows
        self.path = path or default_chdb_path()
        self.name = name or f"chdb_{self.default_db}"

    def execute(self, query: str) -> ExecResult:
        engine = _ChdbEngine.get(self.path)
        sql = strip_trailing_semicolons(query)
        start = time.monotonic()
        rejected = self._static_check(sql)
        if rejected:
            return ExecResult(error=rejected[1], error_class=rejected[0], elapsed_s=time.monotonic() - start)
        with engine.lock:
            try:
                ast = str(engine.session.query(f"EXPLAIN AST {sql}", "TSV"))
            except Exception as exc:  # a parse error: report it as if the query itself had been run
                return ExecResult(error=_unprefix_positions(_clean_error(exc)), error_class=_classify(exc),
                                  elapsed_s=time.monotonic() - start)
            root = next((line.strip().split(" ")[0] for line in ast.splitlines() if line.strip()), "")
            if root not in {"SelectWithUnionQuery", "SelectIntersectExceptQuery"}:
                return ExecResult(error="Only a single read-only SELECT query is allowed.",
                                  error_class=FORBIDDEN_STATEMENT, elapsed_s=time.monotonic() - start)
            bad = scope_violations(ast, self.allowed, engine.databases)
            if bad:
                allowed = ", ".join(sorted(self.allowed))
                return ExecResult(
                    error=f"Code: 60. DB::Exception: Unknown table or not accessible here: {', '.join(bad)}. "
                          f"Only these databases can be queried: {allowed}. (UNKNOWN_TABLE)",
                    error_class=SCOPE_VIOLATION, elapsed_s=time.monotonic() - start)
            engine.configure(self.timeout_s, self.max_result_rows)
            try:
                engine.session.query(f"USE `{self.default_db}`")
                payload = json.loads(str(engine.session.query(sql, "JSONCompact")) or "{}")
            except Exception as exc:
                engine.resync()
                return ExecResult(error=_clean_error(exc), error_class=_classify(exc), elapsed_s=time.monotonic() - start)
        if "data" not in payload:
            return ExecResult(error="Query returned no result set.", error_class=ENGINE_ERROR,
                              elapsed_s=time.monotonic() - start)
        return ExecResult(rows=payload["data"], columns=payload.get("meta", []), elapsed_s=time.monotonic() - start)

    def _static_check(self, sql: str) -> tuple[str, str] | None:
        masked = mask_sql(sql)
        if not sql.strip():
            return FORBIDDEN_STATEMENT, "Empty query."
        if ";" in masked:
            return FORBIDDEN_STATEMENT, "Only a single query is allowed (found ';' between statements)."
        if _PINNED_SETTING.search(masked):
            return FORBIDDEN_STATEMENT, "This setting is fixed by the environment and cannot be changed in the query."
        return None


def _clean_error(exc: Exception) -> str:
    text = str(exc).strip()
    # drop the server stack trace if any
    return text.split("\nStack trace", 1)[0][:4000]


_EXPLAIN_PREFIX = len("EXPLAIN AST ")


def _unprefix_positions(text: str) -> str:
    """Shift ``position N`` in parse errors back to offsets in the model's own query."""
    return re.sub(r"(position )(\d+)", lambda m: f"{m.group(1)}{max(1, int(m.group(2)) - _EXPLAIN_PREFIX)}", text)


def _classify(exc: Exception) -> str:
    text = str(exc)
    if "TIMEOUT_EXCEEDED" in text or "Code: 159." in text:
        return TIMEOUT
    if "TOO_MANY_ROWS_OR_BYTES" in text or "Code: 396." in text:
        return RESULT_TOO_LARGE
    return ENGINE_ERROR


# ---------------------------------------------------------------------------
# Reserved for later cards. Same interface; not implemented in T11.


class _Reserved:
    card = "?"

    def __init__(self, *args, **kwargs) -> None:
        self.name = type(self).__name__

    def execute(self, query: str) -> ExecResult:  # pragma: no cover - placeholder
        raise NotImplementedError(f"{self.name} is implemented in {self.card}")


class CubeSqlExecutor(_Reserved):
    card = "T16"


class CubeJsonExecutor(_Reserved):
    card = "T16"


class DaxExecutor(_Reserved):
    card = "T17"
