"""Scoring with a time limit (T13, decisions/2026-10-18-harness-v1-1-scorer-fixes.md §4).

The frozen scorer (``harness/scorer.py``, ``harness-v1``) can run for hours on some
Top-N tie boundaries (Q79 on SQL-R: a 10-row answer against a 42-member boundary block).
A run must not wait on it: every attempt is scored in a child process, and if the
scorer has not finished within ``SCORE_TIMEOUT_S`` the child is killed and the attempt
is logged as ``pending`` with reason ``score_timeout``; its rows are in runs-raw and it
is scored offline (``harness.rescore``) once the scorer is fixed. A timeout is never a
verdict. The scorer itself and the system prompt are unchanged.

The child is started with ``spawn`` (never ``fork``: the parent holds a chDB session and
worker threads) and imports only the scorer.
"""

from __future__ import annotations

import multiprocessing as mp
from dataclasses import dataclass

SCORE_TIMEOUT_S = 120.0
SCORE_TIMEOUT = "score_timeout"


@dataclass(frozen=True)
class Scored:
    outcome: str
    reason: str | None
    matched_ref: int | None
    sensitivity: str | None


def _work(conn, candidate, refs, rules, reference_rules) -> None:
    try:
        from harness.scorer import score_detailed

        s = score_detailed(candidate, refs, rules, reference_rules=reference_rules)
        conn.send(("ok", (s.outcome, s.reason, s.matched_ref, s.sensitivity)))
    except BaseException as exc:  # noqa: BLE001 — re-raised in the parent
        conn.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        conn.close()


def score_with_timeout(candidate, refs, rules, *, reference_rules=None,
                       timeout_s: float = SCORE_TIMEOUT_S) -> Scored | None:
    """``score_detailed`` in a child process; None if it does not finish within ``timeout_s``.

    An exception inside the scorer is raised here as RuntimeError, as it would have
    propagated in-process.
    """
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_work, args=(child, candidate, refs, rules, reference_rules), daemon=True)
    proc.start()
    child.close()
    try:
        if not parent.poll(timeout_s):
            proc.kill()
            return None
        try:
            status, payload = parent.recv()
        except EOFError:
            raise RuntimeError(f"scorer process exited without a result (exit code {proc.exitcode})") from None
        if status != "ok":
            raise RuntimeError(f"scorer raised in the child process: {payload}")
        return Scored(*payload)
    finally:
        proc.join(5)
        if proc.is_alive():
            proc.kill()
            proc.join()
        parent.close()
