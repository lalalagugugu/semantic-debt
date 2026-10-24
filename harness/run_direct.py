"""Direct answering (直答): one call writes a query; on an execution error the
error is sent back once and the model fixes it. Never retried for a wrong answer.

    uv run python -m harness.run_direct --cell SQL-L1 --dry-run
    uv run python -m harness.run_direct --cell SQL-L1 --run-id 20261101-SQL-L1-01 --model deepseek-flash

Committed log  runs/<run-id>/<cell>.jsonl            one line per attempt, append-only,
                                                     question ids only, no question text
Raw responses  $SEMDEBT_DATA_DIR/runs-raw/<run-id>/<cell>/   full API responses incl. reasoning;
                                                     the log keeps their sha256

The question bank is read only from a fixed tag (``--eval-tag``, default
``eval-v1.2``, the first bank whose rules scorer v2 accepts): ``$SEMDEBT_EVAL_DIR`` must be
a clean checkout of exactly that tag, otherwise nothing starts (dry run included); nor does
a run whose questions carry rules scorer v2 rejects (``invalid_rules``). ``--pilot`` restricts to T06's pilot
sample. The semantic layer must be the content of a fixed tag too (``--semantic-tag``,
default ``semantic-v1.2``): ``semantic/`` and ``render/`` equal the tag's tree and every
built context the run sends is freshly rendered from them (harness/semantic_version.py).
If one requested model answers with a second ``system_fingerprint`` within
a run, the run stops (decisions/2026-10-17-model-version-fingerprint.md).

Scoring is scorer v2 (``harness/scorer_v2.py``, decisions/2026-10-18-scorer-spec-v2.md;
harness-v1.1). It may also answer ``unscored`` (spec §6.5, ``mapping_cap``): not a verdict,
counted apart like ``pending``. Scoring never holds a run up: a returned row set is scored in a
child process with a time limit (harness/score_guard.py, 10 s); a slower one is logged ``pending`` with
reason ``score_timeout`` and rescored offline (harness.rescore). ``--backfill-from-raw``
writes the missing lines of attempts that are complete in runs-raw (no model call).

Resuming: rerunning the same run-id only runs (question, rep) pairs that have no
``status: done`` line. Lines with ``status: api_error`` (transport failure after
backoff) stay in the log and the pair is run again; reports take the ``done`` line.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import prompt as P  # noqa: E402
from harness.cells import (  # noqa: E402
    CELLS, CONTEXTS, DEFAULT_CONCURRENCY, DEFAULT_EXEC_TIMEOUT_S, DEFAULT_REPS, PEAK_MULTIPLIER,
    LADDER_CELLS, PRICES_OFFPEAK, REPO, SYNTAX, Cell, instructions_path, syntax_path,
)
from harness.client import APIError, ModelClient, Reply  # noqa: E402
from harness.executors import (  # noqa: E402
    DEFAULT_MAX_MEMORY_BYTES, DEFAULT_MAX_RESULT_ROWS, ChdbExecutor, CubeSqlExecutor, CubeJsonExecutor, ExecResult, Executor,
)
from harness.questions import Question  # noqa: E402
from harness.score_guard import SCORE_TIMEOUT, SCORE_TIMEOUT_S, score_with_timeout  # noqa: E402
from harness.scorer_v2 import REFUSAL, ExecError, ScoreResult, score_detailed  # noqa: E402

NO_QUERY = "no_query"
BEIJING = ZoneInfo("Asia/Shanghai")


# ---------------------------------------------------------------------------
# Context


# The external benchmark's files, used verbatim (design: L1c and the English
# anchors reproduce the benchmark). Its own harness gives "raw" = DDL and
# "+Sem" = semantic_layer.md prepended to the same DDL.
VENDOR_DDL = REPO / "vendor" / "cube" / "retail_schema.sql"
VENDOR_SEMANTIC_LAYER = Path("vendor") / "cube" / "fixtures" / "semantic_layer.md"   # under $SEMDEBT_EVAL_DIR


def external_context(name: str) -> str:
    from harness.questions import eval_dir

    ddl = f"```sql\n{VENDOR_DDL.read_text(encoding='utf-8').strip()}\n```"
    if name == "r-en":
        return ddl
    if name in {"l1c", "l1c-en"}:
        return (eval_dir() / VENDOR_SEMANTIC_LAYER).read_text(encoding="utf-8").strip() + "\n\n" + ddl
    raise KeyError(f"unknown external context {name!r}")


def context_text(cell: Cell) -> str:
    kind, _, name = cell.context.partition(":")
    if kind == "build":
        path = CONTEXTS / name
        if not path.exists():
            raise FileNotFoundError(f"{path} missing: run `uv run python render/render_all.py`")
        return path.read_text(encoding="utf-8")
    return external_context(name)


def system_for(cell: Cell) -> str:
    lang = "yaml" if cell.context.startswith("build:") else None
    syntax = syntax_path(cell.syntax).read_text(encoding="utf-8")
    if cell.instructions is not None:     # tuned instruction patch (harness/tuned_instructions.py)
        from harness import tuned_instructions as TI

        return TI.system_message(context_text(cell), syntax, lang, TI.load(instructions_path(cell.instructions)))
    return P.system_message(context_text(cell), syntax, lang)


def sha256(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


# ---------------------------------------------------------------------------
# Pricing


def is_peak(moment: datetime | None = None) -> bool:
    """DeepSeek peak = weekdays 09:00–12:00 and 14:00–18:00 Beijing time (holidays not modelled)."""
    t = (moment or datetime.now(BEIJING)).astimezone(BEIJING)
    if t.weekday() >= 5:
        return False
    return 9 <= t.hour < 12 or 14 <= t.hour < 18


def cost_cny(model: str, usage: dict[str, int], peak: bool) -> float | None:
    price = PRICES_OFFPEAK.get(model)
    if price is None:
        return None
    k = PEAK_MULTIPLIER if peak else 1.0
    return k * (usage.get("cache_hit_tokens", 0) * price["hit"] + usage.get("cache_miss_tokens", 0) * price["miss"]
                + usage.get("completion_tokens", 0) * price["output"]) / 1e6


# ---------------------------------------------------------------------------
# One attempt


@dataclass
class RunContext:
    run_id: str
    cell: Cell
    client: ModelClient
    executor: Executor
    system: str
    eval_commit: str
    harness_commit: str
    timeout_s: int
    raw_dir: Path
    limits: dict | None = None      # global resource caps, logged with every attempt
    eval_tag: str | None = None     # the bank tag eval_commit was verified against
    semantic_tag: str | None = None  # the semantic-layer tag the contexts were verified against
    tool_executor: Executor | None = None  # explorer agent (T15): run_sql's own executor (shorter timeout)
    boundary: CallBoundary | None = None


class RunStopped(RuntimeError):
    reply: Reply | None = None


class CallBoundary:
    """Shared by all workers; stop before further calls on a version or time violation."""

    def __init__(self, expected_fingerprint: str | None, allow_peak: bool = False) -> None:
        self.expected_fingerprint = expected_fingerprint
        self.allow_peak = allow_peak
        self.stopped = threading.Event()
        self.reason = ""

    def stop(self, reason: str) -> None:
        self.reason = reason
        self.stopped.set()
        raise RunStopped(reason)

    def before_request(self) -> None:
        if self.stopped.is_set():
            raise RunStopped(self.reason)
        if not self.allow_peak and is_peak():
            self.stop("peak hours reached; resume off-peak")

    def check_reply(self, reply: Reply) -> None:
        if self.expected_fingerprint is not None and reply.system_fingerprint != self.expected_fingerprint:
            self.stop(f"system_fingerprint mismatch: expected {self.expected_fingerprint}, got {reply.system_fingerprint!r}; ask the user")


def _chat(ctx: RunContext, q: Question, rep: int, turn: int, messages: list[dict[str, str]]) -> Reply:
    if ctx.boundary is not None:
        ctx.boundary.before_request()
    reply = ctx.client.chat(messages)
    # Preserve even a mismatching response before stopping; never send its query to the engine.
    _save_raw(ctx, q, rep, turn, reply)
    if ctx.boundary is not None:
        try:
            ctx.boundary.check_reply(reply)
        except RunStopped as exc:
            exc.reply = reply
            raise
    return reply


def _candidate(parsed: P.Parsed, result: ExecResult | None):
    if parsed.refused:
        return REFUSAL
    if parsed.query is None:
        return ExecError("no query code block in the response")
    assert result is not None
    if not result.ok:
        return ExecError(result.error or "execution error")
    return result.rows


PENDING = "pending"
UNSCORED = "unscored"    # scorer v2, spec §6.5: mapping cap reached; not a verdict, reported apart


def score_question(candidate, q: Question, score_timeout_s: float | None = SCORE_TIMEOUT_S) -> dict:
    """Score with scorer v2 (T02, harness/scorer_v2.py). ``rules`` and per-reference
    ``reference_rules`` go to it exactly as the question bank carries them.

    A returned row set for a question that cannot be scored deterministically
    here (judge question, no rules, no refs) gets ``outcome = "pending"`` with the
    reason; its rows are in runs-raw for later scoring. Exec errors and refusals
    need no reference and are scored now.

    A returned row set is scored in a child process with a time limit
    (harness/score_guard.py); if the scorer does not finish, the outcome is
    ``pending`` with reason ``score_timeout`` and the rows wait in runs-raw for
    offline rescoring. ``score_timeout_s=None`` scores in-process without a limit."""
    if q.pending and not isinstance(candidate, (ExecError, str)):
        return {"outcome": PENDING, "pending": q.pending, "reason": None, "matched_ref": None, "sensitivity": None}
    if q.refs is None or q.rules is None:      # only exec_error / refusal reach here; nothing to compare
        s = _without_reference(candidate)
    elif isinstance(candidate, (ExecError, str)) or score_timeout_s is None:
        s = score_detailed(candidate, q.refs, q.rules, reference_rules=q.ref_rules)
    else:
        s = score_with_timeout(candidate, q.refs, q.rules, reference_rules=q.ref_rules, timeout_s=score_timeout_s)
        if s is None:
            return {"outcome": PENDING, "pending": SCORE_TIMEOUT, "score_timeout_s": score_timeout_s,
                    "reason": None, "matched_ref": None, "sensitivity": None}
    return {"outcome": s.outcome, "reason": s.reason if s.outcome != "exec_error" else None,
            "matched_ref": s.matched_ref, "sensitivity": s.sensitivity}


def _without_reference(candidate) -> ScoreResult:
    """An execution error or a refusal needs no reference (v2 validates the rules of every
    reference before looking at the candidate, so it is not called with a placeholder)."""
    if isinstance(candidate, ExecError):
        return ScoreResult("exec_error", candidate.message)
    if isinstance(candidate, str) and candidate.strip() == REFUSAL:
        return ScoreResult("refused")
    raise TypeError("only an execution error or a refusal can be scored without a reference")


def final_score(candidate, q: Question, error_class: str | None, limit: str | None) -> dict:
    """The ``final`` field of a log line; anchors also carry the revised-reference column."""
    final = score_question(candidate, q)
    final["error_class"] = error_class if final["outcome"] == "exec_error" else None
    final["limit"] = limit if final["outcome"] == "exec_error" else None
    if q.revised is not None:
        final["revised"] = score_question(candidate, q.revised)
    return final


def _save_raw(ctx: RunContext, q: Question, rep: int, turn: int, reply: Reply) -> str:
    path = ctx.raw_dir / f"{q.qid}_r{rep}_t{turn}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(reply.raw)
    return sha256(reply.raw)


def _save_exec(ctx: RunContext, q: Question, rep: int, turn: int, result: ExecResult) -> str:
    """Full execution outcome (rows, or the unabridged engine message) for later scoring and audit."""
    payload = json.dumps({"columns": result.columns, "rows": result.rows, "error": result.error,
                          "error_class": result.error_class, "limit": result.limit, "detail": result.detail},
                         ensure_ascii=False, default=str).encode()
    path = ctx.raw_dir / f"{q.qid}_r{rep}_t{turn}.exec.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return sha256(payload)


def _turn_record(ctx: RunContext, q: Question, rep: int, turn: int, reply: Reply,
                 parsed: P.Parsed, result: ExecResult | None, saved: tuple[str, str | None] | None = None) -> dict:
    """One turn of the log line. ``saved`` = (raw_sha256, exec_raw_sha256) of files already in
    runs-raw (backfill): they are hashed, not rewritten."""
    if parsed.refused:
        execution = {"status": "refused"}
    elif parsed.query is None:
        execution = {"status": "error", "error_class": NO_QUERY}
    else:
        execution = {**result.summary(), "exec_raw_sha256": saved[1] if saved else _save_exec(ctx, q, rep, turn, result)}
    return {
        "turn": turn,
        "query": parsed.query,
        "assumption": parsed.assumption,
        "refused": parsed.refused,
        "n_code_blocks": parsed.n_code_blocks,
        "exec": execution,
        "finish_reason": reply.finish_reason,
        "system_fingerprint": reply.system_fingerprint,
        "usage": reply.usage,
        "latency_s": round(reply.latency_s, 3),
        "transport_retries": reply.transport_retries,
        "raw_sha256": saved[0] if saved else _save_raw(ctx, q, rep, turn, reply),
    }


def _base(ctx: RunContext, q: Question, rep: int, started: datetime) -> dict:
    return {
        "run_id": ctx.run_id, "cell": ctx.cell.name, "qid": q.qid, "rep": rep, "question_sha256": sha256(q.text),
        "eval_commit": ctx.eval_commit, **({"eval_tag": ctx.eval_tag} if ctx.eval_tag else {}),
        **({"semantic_tag": ctx.semantic_tag} if ctx.semantic_tag else {}),
        **({"anchor_rules": q.meta["rules_tag"]} if "rules_tag" in q.meta else {}),
        "harness_commit": ctx.harness_commit,
        "model_requested": ctx.client.model, "system_sha256": sha256(ctx.system),
        "exec_timeout_s": ctx.timeout_s, "exec_limits": ctx.limits, "scoring": q.scoring, "started_at": started.isoformat(timespec="seconds"),
    }


def run_attempt(ctx: RunContext, q: Question, rep: int) -> dict:
    """Run one independent attempt (fresh conversation) and return its log line."""
    started = datetime.now(BEIJING)
    peak = is_peak(started)
    messages = P.first_messages(ctx.system, q.text)
    turns: list[dict] = []
    replies: list[Reply] = []
    base = _base(ctx, q, rep, started)
    try:
        reply = _chat(ctx, q, rep, 0, messages)
        replies.append(reply)
        parsed = P.parse_response(reply.content)
        result = ctx.executor.execute(parsed.query) if parsed.query and not parsed.refused else None
        turns.append(_turn_record(ctx, q, rep, 0, reply, parsed, result))
        first_candidate = _candidate(parsed, result)
        final_candidate = first_candidate
        fixed = False
        if result is not None and not result.ok:
            # the one and only fix: send the error back (assistant turn without reasoning_content)
            messages = messages + [{"role": "assistant", "content": reply.content}, P.fix_message(result.error or "")]
            reply2 = _chat(ctx, q, rep, 1, messages)
            replies.append(reply2)
            parsed2 = P.parse_response(reply2.content)
            result2 = ctx.executor.execute(parsed2.query) if parsed2.query and not parsed2.refused else None
            turns.append(_turn_record(ctx, q, rep, 1, reply2, parsed2, result2))
            final_candidate = _candidate(parsed2, result2)
            fixed = True
    except RunStopped as exc:
        reply = getattr(exc, "reply", None)
        if reply is not None:
            turns.append({"turn": len(turns), "system_fingerprint": reply.system_fingerprint,
                          "usage": reply.usage, "raw_sha256": sha256(reply.raw),
                          "exec": {"status": "not_executed"}})
        return {**base, "status": "stopped", "error": str(exc), "turns": turns}
    except APIError as exc:
        return {**base, "status": "api_error", "error": str(exc)[:500], "turns": turns,
                "transport_retries": exc.transport_retries}

    return _done_line(ctx, q, base, turns, replies, first_candidate, final_candidate, fixed, peak)


def _done_line(ctx: RunContext, q: Question, base: dict, turns: list[dict], replies: list[Reply],
               first_candidate, final_candidate, fixed: bool, peak: bool) -> dict:
    usage = {k: sum(r.usage.get(k, 0) for r in replies) for k in replies[0].usage}
    last_exec = turns[-1]["exec"]
    final = final_score(final_candidate, q, last_exec.get("error_class"), last_exec.get("limit"))
    return {
        **base,
        "status": "done",
        "model_version": replies[-1].model_version,
        "n_calls": len(replies),
        "fixed": fixed,
        # without a fix turn the first answer is the final one: score it once (the scorer is deterministic)
        "first": final["outcome"] if not fixed else score_question(first_candidate, q)["outcome"],
        "final": final,
        "turns": turns,
        "usage": usage,
        "latency_s": round(sum(r.latency_s for r in replies), 3),
        "peak": peak,
        "cost_cny": cost_cny(ctx.client.model, usage, peak),
    }


def attempt_from_raw(ctx: RunContext, q: Question, rep: int, note: str) -> dict:
    """Rebuild the ``done`` line of an attempt whose calls and executions are complete in
    runs-raw but whose line was never written (the process was stopped while scoring).

    No model call and no execution: replies come from ``<qid>_r<rep>_t<turn>.json``, rows from
    the ``.exec.json`` files; both are hashed, not rewritten. Wall-clock latency and execution
    time were not saved, so they are logged as 0 and the line carries ``backfilled_from_raw``.
    """
    from harness.client import _reply

    turns: list[dict] = []
    replies: list[Reply] = []
    candidates = []
    for turn in (0, 1):
        raw_path = ctx.raw_dir / f"{q.qid}_r{rep}_t{turn}.json"
        if not raw_path.exists():
            break
        raw = raw_path.read_bytes()
        reply = _reply(raw, 0.0, 0)
        parsed = P.parse_response(reply.content)
        result, exec_sha = None, None
        if parsed.query and not parsed.refused:
            exec_bytes = (ctx.raw_dir / f"{q.qid}_r{rep}_t{turn}.exec.json").read_bytes()
            e = json.loads(exec_bytes)
            result = ExecResult(rows=e["rows"], columns=e["columns"], error=e["error"], error_class=e["error_class"],
                                limit=e["limit"], detail=e["detail"])
            exec_sha = sha256(exec_bytes)
        replies.append(reply)
        turns.append(_turn_record(ctx, q, rep, turn, reply, parsed, result, saved=(sha256(raw), exec_sha)))
        candidates.append(_candidate(parsed, result))
        if result is None or result.ok:
            break
    if not turns:
        raise FileNotFoundError(f"{ctx.raw_dir}: no raw response for {q.qid} r{rep}")
    if len(turns) == 1 and turns[0]["exec"].get("status") == "error" and turns[0]["exec"].get("error_class") != NO_QUERY:
        raise ValueError(f"{q.qid} r{rep}: turn 0 failed but no fix turn in runs-raw; the attempt is incomplete")
    stamp = json.loads(replies[0].raw).get("created")
    source = "response.created" if stamp is not None else "raw file mtime"
    if stamp is None:
        stamp = (ctx.raw_dir / f"{q.qid}_r{rep}_t0.json").stat().st_mtime
    created = datetime.fromtimestamp(stamp, BEIJING)
    base = _base(ctx, q, rep, created)
    line = _done_line(ctx, q, base, turns, replies, candidates[0], candidates[-1], len(turns) == 2, is_peak(created))
    line["backfilled_from_raw"] = {"note": note, "started_at_from": source, "latency_and_exec_time_not_saved": True}
    return line


# ---------------------------------------------------------------------------
# A whole cell


def log_path(run_id: str, cell: str, runs_root: Path | None = None) -> Path:
    return (runs_root or REPO / "runs") / run_id / f"{cell}.jsonl"


def done_pairs(path: Path) -> set[tuple[str, int]]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("status") == "done":
                done.add((str(rec["qid"]), int(rec["rep"])))
    return done


class FingerprintGuard:
    """Tracks the ``system_fingerprint`` values one requested model answers with in a run.

    More than one value means the model behind the name may have changed mid-run:
    ``run_cell`` stops launching attempts and the CLI stops and asks the user
    (decisions/2026-10-17-model-version-fingerprint.md). Attempts already in
    flight finish and are logged as usual.
    """

    def __init__(self, seen: dict[str, int] | None = None) -> None:
        self.seen: dict[str, int] = dict(seen or {})
        self._lock = threading.Lock()

    def observe(self, record: dict) -> None:
        with self._lock:
            # explorer agent lines (T15) also carry their tool-calling model calls in ``steps``
            for t in (record.get("steps") or []) + (record.get("turns") or []):
                fp = t.get("system_fingerprint")
                if fp:
                    self.seen[fp] = self.seen.get(fp, 0) + 1

    @property
    def conflict(self) -> bool:
        return len(self.seen) > 1

    @classmethod
    def from_logs(cls, run_dir: Path, model: str) -> "FingerprintGuard":
        """Seeded from every cell log already in this run (resuming) for the same requested model."""
        guard = cls()
        for path in sorted(run_dir.glob("*.jsonl")) if run_dir.is_dir() else []:
            for line in path.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line) if line.strip() else {}
                if rec.get("model_requested") == model:
                    guard.observe(rec)
        return guard


def backfill_cell(ctx: RunContext, questions: list[Question], pairs: list[tuple[str, int]], note: str,
                  runs_root: Path | None = None, progress=print) -> Path:
    """Append ``attempt_from_raw`` lines for (question, rep) pairs that have no ``done`` line."""
    path = log_path(ctx.run_id, ctx.cell.name, runs_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    done = done_pairs(path)
    by_id = {q.qid: q for q in questions}
    missing = [p for p in pairs if p[0] not in by_id]
    if missing:
        raise SystemExit(f"backfill: not in the question set: {missing}")
    with path.open("a", encoding="utf-8") as out:
        for qid, rep in pairs:
            if (qid, rep) in done:
                progress(f"  backfill {qid} r{rep}: already done, skipped")
                continue
            record = attempt_from_raw(ctx, by_id[qid], rep, note)
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            progress(f"  backfill {qid} r{rep}: {record['final']['outcome']}"
                     f"{' (' + record['final']['pending'] + ')' if record['final'].get('pending') else ''}")
    return path


def run_cell(ctx: RunContext, questions: list[Question], reps: int, concurrency: int,
             runs_root: Path | None = None, progress=print, guard: FingerprintGuard | None = None,
             attempt=None, only: set[tuple[str, int]] | None = None) -> Path:
    """Run every missing (question, rep) of one cell.

    The first attempt runs alone so that it writes the prefix cache before the
    concurrent ones start (otherwise every worker's first call is a cache miss).
    ``attempt(ctx, q, rep) -> line`` defaults to ``run_attempt`` (the explorer agent passes its own).
    ``only``: run just these (qid, rep) pairs, keeping their rep numbers (a continuation run).
    """
    run_attempt_ = attempt or run_attempt
    path = log_path(ctx.run_id, ctx.cell.name, runs_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    done = done_pairs(path)
    todo = [(q, rep) for q in questions for rep in range(1, reps + 1)
            if (q.qid, rep) not in done and (only is None or (q.qid, rep) in only)]
    progress(f"{ctx.cell.name}: {len(done)} done, {len(todo)} to run")
    if guard is not None and guard.conflict:
        progress(f"  stop: more than one system_fingerprint already in this run: {guard.seen}")
        return path
    lock = threading.Lock()
    n = 0

    def emit(out, future_or_record, qid: str, rep: int) -> None:
        nonlocal n
        try:
            record = future_or_record.result() if hasattr(future_or_record, "result") else future_or_record
        except Exception as exc:  # recorded, never swallowed
            record = {"run_id": ctx.run_id, "cell": ctx.cell.name, "qid": qid, "rep": rep,
                      "status": "harness_error", "error": f"{type(exc).__name__}: {exc}"[:500]}
        with lock:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            n += 1
        if guard is not None:
            guard.observe(record)
        outcome = record.get("final", {}).get("outcome", record["status"])
        progress(f"  [{n}/{len(todo)}] {qid} r{rep}: {outcome}")

    with path.open("a", encoding="utf-8") as out:
        if todo:
            (q0, rep0), todo_rest = todo[0], todo[1:]
            with ThreadPoolExecutor(max_workers=1) as warm:
                emit(out, warm.submit(run_attempt_, ctx, q0, rep0), q0.qid, rep0)
        else:
            todo_rest = []
        if (guard is not None and guard.conflict) or (ctx.boundary is not None and ctx.boundary.stopped.is_set()):
            progress("  stop: call boundary or fingerprint guard")
            return path
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            futures = {pool.submit(run_attempt_, ctx, q, rep): (q.qid, rep) for q, rep in todo_rest}
            stopped = False
            for future in as_completed(futures):
                if future.cancelled():
                    continue
                qid, rep = futures[future]
                emit(out, future, qid, rep)
                if ((guard is not None and guard.conflict) or
                        (ctx.boundary is not None and ctx.boundary.stopped.is_set())) and not stopped:
                    stopped = True
                    progress("  stop: call boundary or fingerprint guard; cancelling attempts not yet started")
                    for f in futures:
                        f.cancel()
    return path


def summarize(path: Path) -> dict:
    """Per-cell summary over the ``done`` lines of one cell log.

    Accuracy = correct / attempts (T11 spec 11). While some attempts are still
    ``pending`` (judge / no rules / no refs), ``accuracy`` is None and
    ``accuracy_scored`` covers only the scored attempts. The error counts are the
    splits T19 reports separately: no_query (format failures), scope violations,
    timeouts, resource limits (memory / result rows) and ordinary engine errors.
    ``system_fingerprints`` counts calls per fingerprint; more than one key means
    the model behind the requested name may have changed mid-run. Logs from before
    the fingerprint was recorded count as ``calls_without_fingerprint``.
    """
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    done = [r for r in recs if r.get("status") == "done"]
    counts = _count(r["final"]["outcome"] for r in done)
    pending = counts.get(PENDING, 0) + counts.get(UNSCORED, 0)     # neither is a verdict
    scored = len(done) - pending
    turns = [t for r in done for t in r["turns"]]
    tokens = {k: sum(r["usage"].get(k, 0) for r in done) for k in
              ("prompt_tokens", "cache_hit_tokens", "cache_miss_tokens", "completion_tokens", "reasoning_tokens")}
    return {
        "attempts": len(done),
        "accuracy": counts.get("correct", 0) / len(done) if done and not pending else None,
        "accuracy_scored": counts.get("correct", 0) / scored if scored else None,
        "outcomes": counts,
        "outcomes_on_revised_refs": _count(r["final"]["revised"]["outcome"] for r in done if "revised" in r["final"]) or None,
        "pending_reasons": _count(r["final"].get("pending") for r in done if r["final"]["outcome"] == PENDING),
        "first_try_correct": sum(r["first"] == "correct" for r in done),
        "final_exec_error_classes": _count(r["final"]["error_class"] for r in done if r["final"]["outcome"] == "exec_error"),
        "final_resource_limits": _count(r["final"]["limit"] for r in done if r["final"].get("limit")),
        "turn_error_classes": _count(t["exec"]["error_class"] for t in turns if t["exec"].get("status") == "error"),
        "attempts_with_no_query": sum(any(t["exec"].get("error_class") == NO_QUERY for t in r["turns"]) for r in done),
        "attempts_with_scope_violation": sum(any(t["exec"].get("error_class") == "scope_violation" for t in r["turns"]) for r in done),
        "not_done_lines": len(recs) - len(done),
        "system_fingerprints": _count(t["system_fingerprint"] for t in turns if t.get("system_fingerprint")),
        "calls_without_fingerprint": sum(not t.get("system_fingerprint") for t in turns),
        "tokens": tokens,
        "cache_hit_ratio": tokens["cache_hit_tokens"] / tokens["prompt_tokens"] if tokens["prompt_tokens"] else None,
        "cost_cny": round(sum(r.get("cost_cny") or 0 for r in done), 4),
    }


def _count(items) -> dict:
    out: dict = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return out


# ---------------------------------------------------------------------------
# Dry run


def estimate_tokens_from_text(text: str) -> int:
    """DeepSeek's rule of thumb: CJK char ≈ 0.6 token, other char ≈ 0.3 token."""
    cjk = sum(1 for ch in text if "　" <= ch <= "鿿" or "＀" <= ch <= "￯")
    return int(cjk * 0.6 + (len(text) - cjk) * 0.3)


def measured(cell: str, runs_root: Path | None = None) -> dict | None:
    """Mean per-call input / output tokens over every committed log of this cell."""
    calls = []
    for path in sorted((runs_root or REPO / "runs").glob(f"*/{cell}.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line) if line.strip() else {}
            for t in rec.get("turns", []) if rec.get("status") == "done" else []:
                calls.append(t["usage"])
    if not calls:
        return None
    n = len(calls)
    return {"calls": n,
            "prompt": sum(c["prompt_tokens"] for c in calls) / n,
            "hit_ratio": sum(c["cache_hit_tokens"] for c in calls) / max(1, sum(c["prompt_tokens"] for c in calls)),
            "output": sum(c["completion_tokens"] for c in calls) / n}


def dry_run(cells: list[Cell], n_questions: dict[str, int], reps: int, model: str, *, fix_rate: float,
            output_tokens: int, hit_ratio: float, question_tokens: int, runs_root: Path | None = None,
            use_measured: bool = True) -> tuple[list[dict], float]:
    rows = []
    price = PRICES_OFFPEAK[model]
    for cell in cells:
        nq = n_questions.get(cell.name, n_questions.get(cell.lang, 0))   # per cell, or per language
        attempts = nq * reps
        calls = round(attempts * (1 + fix_rate))
        m = measured(cell.name, runs_root) if use_measured else None
        source = "measured" if m else "estimated"
        if m:
            prompt_tokens, hr, out_tokens = m["prompt"], m["hit_ratio"], m["output"]
        else:
            try:
                prefix = estimate_tokens_from_text(system_for(cell))
            except (FileNotFoundError, NotImplementedError) as exc:
                prefix, source = None, f"no context ({type(exc).__name__})"
            prompt_tokens = None if prefix is None else prefix + question_tokens
            hr, out_tokens = hit_ratio, output_tokens
        cost = None
        if prompt_tokens is not None:
            per_call = (prompt_tokens * (hr * price["hit"] + (1 - hr) * price["miss"]) + out_tokens * price["output"]) / 1e6
            cost = per_call * calls
        rows.append({"cell": cell.name, "card": cell.card, "stack": cell.stack, "questions": nq, "attempts": attempts,
                     "calls": calls, "prompt_tokens": prompt_tokens, "output_tokens": out_tokens,
                     "cost_offpeak": cost, "source": source})
    total = sum(r["cost_offpeak"] or 0 for r in rows)
    return rows, total


def print_dry_run(rows: list[dict], total: float, model: str, reps: int, fix_rate: float) -> None:
    print(f"model={model} reps={reps} fix_rate={fix_rate:.0%} (off-peak prices; peak = x{PEAK_MULTIPLIER:g})")
    print(f"{'cell':<14}{'card':<6}{'stack':<10}{'Q':>5}{'attempts':>10}{'calls':>8}{'in/call':>10}{'out/call':>10}{'CNY':>10}  source")
    for r in rows:
        cost = f"{r['cost_offpeak']:.2f}" if r["cost_offpeak"] is not None else "-"
        tin = f"{r['prompt_tokens']:.0f}" if r["prompt_tokens"] is not None else "-"
        print(f"{r['cell']:<14}{r['card']:<6}{r['stack']:<10}{r['questions']:>5}{r['attempts']:>10}{r['calls']:>8}"
              f"{tin:>10}{r['output_tokens']:>10.0f}{cost:>10}  {r['source']}")
    print(f"{'total':<35}{sum(r['attempts'] for r in rows):>10}{sum(r['calls'] for r in rows):>8}{'':>20}{total:>10.2f}"
          f"  (peak {total * PEAK_MULTIPLIER:.2f})")


# ---------------------------------------------------------------------------
# CLI


def harness_commit() -> str:
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", "harness", "render", "semantic"],
                           capture_output=True, text=True).stdout.strip()
    return f"{head}-dirty" if dirty else head


def make_executor(cell: Cell, timeout_s: int) -> Executor:
    if cell.stack == "cube_sql":
        return CubeSqlExecutor(timeout_s=timeout_s)
    if cell.stack == "cube_json":
        return CubeJsonExecutor(timeout_s=timeout_s)
    if cell.stack != "chdb":
        raise NotImplementedError(f"{cell.name}: the {cell.stack} executor is implemented in {cell.card}")
    return ChdbExecutor(cell.allowed, timeout_s=timeout_s, name=f"chdb_{cell.allowed[0]}")


def raw_root() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        raise RuntimeError("SEMDEBT_DATA_DIR is not set")
    return Path(root).expanduser() / "runs-raw"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell", action="append",
                    help="cell name (repeatable); 'all' = every cell in CELLS (not the C13 ladder cells)")
    ap.add_argument("--skip-judge", action="store_true",
                    help="leave out judge questions (phase 1 replan §二; the C13 ladder cells always do)")
    ap.add_argument("--run-id", help="runs/<run-id>/; required unless --dry-run")
    ap.add_argument("--model", default="deepseek-flash", choices=sorted(PRICES_OFFPEAK))
    ap.add_argument("--reps", type=int, default=DEFAULT_REPS)
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--exec-timeout", type=int, default=DEFAULT_EXEC_TIMEOUT_S, help="seconds per query execution")
    ap.add_argument("--questions", help="comma-separated question ids (default: all)")
    ap.add_argument("--pilot", action="store_true", help="T06's pilot sample only (questions/pilot.yaml)")
    ap.add_argument("--eval-tag", default="eval-v1.2",
                    help="the question bank must be a clean checkout of this tag (BOARD item 13)")
    ap.add_argument("--anchor-rules-tag", default="eval-v1",
                    help="English anchors inherit the Chinese questions' rules from this bank tag, never from the "
                         "current checkout; refuse to start if the tag is missing")
    ap.add_argument("--semantic-tag", default="semantic-v1.2",
                    help="semantic/ and render/ must be this tag's content and build/contexts rendered from them")
    ap.add_argument("--limit", type=int, help="first N questions only")
    ap.add_argument("--dry-run", action="store_true", help="count calls and estimate cost; no API call")
    ap.add_argument("--budget", type=float, help="CNY; refuse to start if the estimate exceeds it")
    ap.add_argument("--allow-peak", action="store_true", help="allow starting in DeepSeek peak hours")
    ap.add_argument("--expected-fingerprint", help="stop on any differing or missing response fingerprint")
    ap.add_argument("--est-output-tokens", type=int, default=3000)
    ap.add_argument("--est-fix-rate", type=float, default=0.10)
    ap.add_argument("--est-hit-ratio", type=float, default=0.95)
    ap.add_argument("--est-question-tokens", type=int, default=60)
    ap.add_argument("--est-from-args", action="store_true",
                    help="estimate from the --est-* values even where committed logs have measurements")
    ap.add_argument("--backfill-from-raw", metavar="QID:REP[,QID:REP...]",
                    help="write the missing done lines of these attempts from runs-raw (no model call, no "
                         "execution) and exit; one cell only")
    ap.add_argument("--backfill-note", default="", help="why the lines are backfilled (logged on each line)")
    args = ap.parse_args(argv)
    if args.backfill_from_raw and (not args.run_id or not args.cell or len(args.cell) != 1 or "all" in args.cell):
        ap.error("--backfill-from-raw needs --run-id and exactly one --cell")
    if not args.dry_run and not args.run_id:
        ap.error("--run-id is required unless --dry-run")
    return args


def invalid_rules(questions: list[Question]) -> list[str]:
    """Questions whose rules scorer v2 rejects (spec §2: missing or unknown fields, identity
    columns not required, ...), as ``"<qid>: <error>"``. Checked before a run starts, so that
    a bank written for the old scorer stops the run instead of failing every attempt.
    Questions without references or rules are pending anyway and not checked."""
    bad = []
    for q in questions:
        if q.refs is None or q.rules is None:
            continue
        try:                                   # v2 validates every reference's rules before the candidate
            score_detailed(REFUSAL, q.refs, q.rules, reference_rules=q.ref_rules)
        except (ValueError, TypeError) as exc:
            bad.append(f"{q.qid}: {exc}")
    return bad


def questions_for(cell: Cell, questions: list[Question], skip_judge: bool = False) -> list[Question]:
    """The questions a cell answers: its split (all / tuning / heldout), and no judge question
    when the cell says so or ``--skip-judge`` is given (phase 1 replan §二)."""
    out = [q for q in questions if cell.split == "all" or q.meta.get("split") == cell.split]
    if skip_judge or cell.skip_judge:
        out = [q for q in out if q.scoring != "judge"]
    return out


def select_questions(questions: list[Question], args: argparse.Namespace, pilot: list[str] | None = None) -> list[Question]:
    if pilot is not None:
        questions = [q for q in questions if q.qid in set(pilot)]
        missing = set(pilot) - {q.qid for q in questions}
        if missing:
            raise SystemExit(f"pilot ids not in the bank: {sorted(missing)}")
    if args.questions:
        wanted = {x.strip() for x in args.questions.split(",") if x.strip()}
        questions = [q for q in questions if q.qid in wanted]
        missing = wanted - {q.qid for q in questions}
        if missing:
            raise SystemExit(f"unknown question ids: {sorted(missing)}")
    return questions[: args.limit] if args.limit else questions


def main(argv: list[str] | None = None, load=None) -> int:
    from harness.questions import EvalVersionError, eval_commit, load_questions, pilot_ids, verify_eval_tag

    args = parse_args(argv)
    names = args.cell or ["all"]
    known = {**CELLS, **LADDER_CELLS}
    cells = list(CELLS.values()) if "all" in names else [known[n] for n in names]
    if load is None:
        try:
            eval_full = verify_eval_tag(args.eval_tag)
        except EvalVersionError as exc:
            print(f"refusing to start: {exc}")
            return 2
        print(f"question bank: {args.eval_tag} = {eval_full}")
        from harness.semantic_version import SemanticVersionError, verify_semantic_tag

        built = [c.context.partition(":")[2] for c in cells if c.context.startswith("build:")]
        try:
            sem_full = verify_semantic_tag(args.semantic_tag, built, root=REPO, contexts_dir=CONTEXTS)
        except SemanticVersionError as exc:
            print(f"refusing to start: {exc}")
            return 2
        print(f"semantic layer: {args.semantic_tag} = {sem_full}")
    load = load or load_questions
    pilot = pilot_ids() if args.pilot else None
    if pilot is not None and any(c.lang != "zh" for c in cells):
        raise SystemExit("--pilot is a sample of the Chinese set")
    try:
        by_lang = {lang: select_questions(load(lang=lang, **({"anchor_rules_tag": args.anchor_rules_tag}
                                                             if lang == "en" else {})), args, pilot)
                   for lang in sorted({c.lang for c in cells})}
    except EvalVersionError as exc:
        print(f"refusing to start: {exc}")
        return 2
    if "en" in by_lang:
        print(f"anchor rules: {args.anchor_rules_tag} = "
              f"{next((q.meta['rules_tag']['commit'] for q in by_lang['en'] if 'rules_tag' in q.meta), '—')}")
    bad = [b for qs in by_lang.values() for b in invalid_rules(qs)]
    if bad:
        print(f"refusing to start: scorer v2 rejects the rules of {len(bad)} question(s) in {args.eval_tag}:")
        for b in bad:
            print(f"  {b}")
        return 2

    if args.backfill_from_raw:
        import types

        cell = cells[0]
        pairs = [(x.split(":")[0].strip(), int(x.split(":")[1])) for x in args.backfill_from_raw.split(",") if x.strip()]
        ctx = RunContext(run_id=args.run_id, cell=cell, client=types.SimpleNamespace(model=args.model),
                         executor=make_executor(cell, args.exec_timeout), system=system_for(cell),
                         eval_commit=eval_commit(), harness_commit=harness_commit(), timeout_s=args.exec_timeout,
                         raw_dir=raw_root() / args.run_id / cell.name,
                         limits={"max_result_rows": DEFAULT_MAX_RESULT_ROWS, "max_memory_bytes": DEFAULT_MAX_MEMORY_BYTES},
                         eval_tag=args.eval_tag, semantic_tag=args.semantic_tag)
        backfill_cell(ctx, questions_for(cell, by_lang[cell.lang], args.skip_judge), pairs, args.backfill_note)
        return 0

    per_cell = {c.name: questions_for(c, by_lang[c.lang], args.skip_judge) for c in cells}
    rows, total = dry_run([c for c in cells], {k: len(v) for k, v in per_cell.items()}, args.reps, args.model,
                          fix_rate=args.est_fix_rate, output_tokens=args.est_output_tokens,
                          hit_ratio=args.est_hit_ratio, question_tokens=args.est_question_tokens,
                          use_measured=not args.est_from_args)
    print_dry_run(rows, total, args.model, args.reps, args.est_fix_rate)
    if args.dry_run:
        return 0
    if args.budget is not None and total > args.budget:
        print(f"estimate {total:.2f} CNY exceeds budget {args.budget:.2f}; stop and ask the user")
        return 2
    if is_peak() and not args.allow_peak:
        print("DeepSeek peak hours (weekdays 09-12, 14-18 Beijing): batch runs go off-peak (hard rule 6); "
              "pass --allow-peak for a deliberate small run")
        return 2

    from harness.client import DeepSeekClient

    boundary = CallBoundary(args.expected_fingerprint, args.allow_peak)
    client = DeepSeekClient(args.model, before_request=boundary.before_request)
    commit = eval_commit()
    guard = FingerprintGuard.from_logs(log_path(args.run_id, "x").parent, args.model)
    for cell in cells:
        ctx = RunContext(run_id=args.run_id, cell=cell, client=client, executor=make_executor(cell, args.exec_timeout),
                         system=system_for(cell), eval_commit=commit, harness_commit=harness_commit(),
                         timeout_s=args.exec_timeout, raw_dir=raw_root() / args.run_id / cell.name,
                         limits={"max_result_rows": DEFAULT_MAX_RESULT_ROWS, "max_memory_bytes": DEFAULT_MAX_MEMORY_BYTES},
                         eval_tag=args.eval_tag, semantic_tag=args.semantic_tag, boundary=boundary)
        path = run_cell(ctx, per_cell[cell.name], args.reps, args.concurrency, guard=guard)
        print(json.dumps(summarize(path), ensure_ascii=False, indent=2))
        if boundary.stopped.is_set():
            print(f"STOP: {boundary.reason}")
            return 3
        if guard.conflict:
            print(f"STOP: {args.model} answered with more than one system_fingerprint in this run: {guard.seen}. "
                  "Ask the user before going on (decisions/2026-10-17-model-version-fingerprint.md).")
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
