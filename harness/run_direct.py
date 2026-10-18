"""Direct answering (直答): one call writes a query; on an execution error the
error is sent back once and the model fixes it. Never retried for a wrong answer.

    uv run python -m harness.run_direct --cell SQL-L1 --dry-run
    uv run python -m harness.run_direct --cell SQL-L1 --run-id 20261101-SQL-L1-01 --model deepseek-flash

Committed log  runs/<run-id>/<cell>.jsonl            one line per attempt, append-only,
                                                     question ids only, no question text
Raw responses  $SEMDEBT_DATA_DIR/runs-raw/<run-id>/<cell>/   full API responses incl. reasoning;
                                                     the log keeps their sha256

The question bank is read only from a fixed tag (``--eval-tag``, default
``eval-v1``): ``$SEMDEBT_EVAL_DIR`` must be a clean checkout of exactly that tag,
otherwise nothing starts (dry run included). ``--pilot`` restricts to T06's pilot
sample. The semantic layer must be the content of a fixed tag too (``--semantic-tag``,
default ``semantic-v1.2``): ``semantic/`` and ``render/`` equal the tag's tree and every
built context the run sends is freshly rendered from them (harness/semantic_version.py).
If one requested model answers with a second ``system_fingerprint`` within
a run, the run stops (decisions/2026-10-17-model-version-fingerprint.md).

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
    PRICES_OFFPEAK, REPO, SYNTAX, Cell,
)
from harness.client import APIError, ModelClient, Reply  # noqa: E402
from harness.executors import (  # noqa: E402
    DEFAULT_MAX_MEMORY_BYTES, DEFAULT_MAX_RESULT_ROWS, ChdbExecutor, ExecResult, Executor,
)
from harness.questions import Question  # noqa: E402
from harness.scorer import REFUSAL, ExecError, score_detailed  # noqa: E402

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
    return P.system_message(context_text(cell), (SYNTAX / cell.syntax).read_text(encoding="utf-8"), lang)


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


def score_question(candidate, q: Question) -> dict:
    """Score with T02's scorer. ``rules`` and per-reference ``reference_rules``
    go to it exactly as the question bank carries them.

    A returned row set for a question that cannot be scored deterministically
    here (judge question, no rules, no refs) gets ``outcome = "pending"`` with the
    reason; its rows are in runs-raw for later scoring. Exec errors and refusals
    need no reference and are scored now."""
    if q.pending and not isinstance(candidate, (ExecError, str)):
        return {"outcome": PENDING, "pending": q.pending, "reason": None, "matched_ref": None, "sensitivity": None}
    if q.refs is None or q.rules is None:      # only exec_error / refusal reach here; rules are not consulted
        s = score_detailed(candidate, [[]], {"ordered": False, "top_n": None})
    else:
        s = score_detailed(candidate, q.refs, q.rules, reference_rules=q.ref_rules)
    return {"outcome": s.outcome, "reason": s.reason if s.outcome != "exec_error" else None,
            "matched_ref": s.matched_ref, "sensitivity": s.sensitivity}


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
                 parsed: P.Parsed, result: ExecResult | None) -> dict:
    if parsed.refused:
        execution = {"status": "refused"}
    elif parsed.query is None:
        execution = {"status": "error", "error_class": NO_QUERY}
    else:
        execution = {**result.summary(), "exec_raw_sha256": _save_exec(ctx, q, rep, turn, result)}
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
        "raw_sha256": _save_raw(ctx, q, rep, turn, reply),
    }


def run_attempt(ctx: RunContext, q: Question, rep: int) -> dict:
    """Run one independent attempt (fresh conversation) and return its log line."""
    started = datetime.now(BEIJING)
    peak = is_peak(started)
    messages = P.first_messages(ctx.system, q.text)
    turns: list[dict] = []
    replies: list[Reply] = []
    base = {
        "run_id": ctx.run_id, "cell": ctx.cell.name, "qid": q.qid, "rep": rep, "question_sha256": sha256(q.text),
        "eval_commit": ctx.eval_commit, **({"eval_tag": ctx.eval_tag} if ctx.eval_tag else {}),
        **({"semantic_tag": ctx.semantic_tag} if ctx.semantic_tag else {}),
        "harness_commit": ctx.harness_commit,
        "model_requested": ctx.client.model, "system_sha256": sha256(ctx.system),
        "exec_timeout_s": ctx.timeout_s, "exec_limits": ctx.limits, "scoring": q.scoring, "started_at": started.isoformat(timespec="seconds"),
    }
    try:
        reply = ctx.client.chat(messages)
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
            reply2 = ctx.client.chat(messages)
            replies.append(reply2)
            parsed2 = P.parse_response(reply2.content)
            result2 = ctx.executor.execute(parsed2.query) if parsed2.query and not parsed2.refused else None
            turns.append(_turn_record(ctx, q, rep, 1, reply2, parsed2, result2))
            final_candidate = _candidate(parsed2, result2)
            fixed = True
    except APIError as exc:
        return {**base, "status": "api_error", "error": str(exc)[:500], "turns": turns,
                "transport_retries": exc.transport_retries}

    usage = {k: sum(r.usage.get(k, 0) for r in replies) for k in replies[0].usage}
    last_exec = turns[-1]["exec"]
    final = final_score(final_candidate, q, last_exec.get("error_class"), last_exec.get("limit"))
    return {
        **base,
        "status": "done",
        "model_version": replies[-1].model_version,
        "n_calls": len(replies),
        "fixed": fixed,
        "first": score_question(first_candidate, q)["outcome"],
        "final": final,
        "turns": turns,
        "usage": usage,
        "latency_s": round(sum(r.latency_s for r in replies), 3),
        "peak": peak,
        "cost_cny": cost_cny(ctx.client.model, usage, peak),
    }


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
            for t in record.get("turns") or []:
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


def run_cell(ctx: RunContext, questions: list[Question], reps: int, concurrency: int,
             runs_root: Path | None = None, progress=print, guard: FingerprintGuard | None = None) -> Path:
    """Run every missing (question, rep) of one cell.

    The first attempt runs alone so that it writes the prefix cache before the
    concurrent ones start (otherwise every worker's first call is a cache miss).
    """
    path = log_path(ctx.run_id, ctx.cell.name, runs_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    done = done_pairs(path)
    todo = [(q, rep) for q in questions for rep in range(1, reps + 1) if (q.qid, rep) not in done]
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
                emit(out, warm.submit(run_attempt, ctx, q0, rep0), q0.qid, rep0)
        else:
            todo_rest = []
        if guard is not None and guard.conflict:
            progress(f"  stop: second system_fingerprint: {guard.seen}")
            return path
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            futures = {pool.submit(run_attempt, ctx, q, rep): (q.qid, rep) for q, rep in todo_rest}
            stopped = False
            for future in as_completed(futures):
                if future.cancelled():
                    continue
                qid, rep = futures[future]
                emit(out, future, qid, rep)
                if guard is not None and guard.conflict and not stopped:
                    stopped = True
                    progress(f"  stop: second system_fingerprint: {guard.seen}; cancelling attempts not yet started")
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
    pending = counts.get(PENDING, 0)
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
        nq = n_questions.get(cell.lang, 0)
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
    ap.add_argument("--cell", action="append", help="cell name (repeatable); 'all' = every cell in harness/cells.py")
    ap.add_argument("--run-id", help="runs/<run-id>/; required unless --dry-run")
    ap.add_argument("--model", default="deepseek-flash", choices=sorted(PRICES_OFFPEAK))
    ap.add_argument("--reps", type=int, default=DEFAULT_REPS)
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--exec-timeout", type=int, default=DEFAULT_EXEC_TIMEOUT_S, help="seconds per query execution")
    ap.add_argument("--questions", help="comma-separated question ids (default: all)")
    ap.add_argument("--pilot", action="store_true", help="T06's pilot sample only (questions/pilot.yaml)")
    ap.add_argument("--eval-tag", default="eval-v1",
                    help="the question bank must be a clean checkout of this tag (BOARD item 13)")
    ap.add_argument("--semantic-tag", default="semantic-v1.2",
                    help="semantic/ and render/ must be this tag's content and build/contexts rendered from them")
    ap.add_argument("--limit", type=int, help="first N questions only")
    ap.add_argument("--dry-run", action="store_true", help="count calls and estimate cost; no API call")
    ap.add_argument("--budget", type=float, help="CNY; refuse to start if the estimate exceeds it")
    ap.add_argument("--allow-peak", action="store_true", help="allow starting in DeepSeek peak hours")
    ap.add_argument("--est-output-tokens", type=int, default=3000)
    ap.add_argument("--est-fix-rate", type=float, default=0.10)
    ap.add_argument("--est-hit-ratio", type=float, default=0.95)
    ap.add_argument("--est-question-tokens", type=int, default=60)
    ap.add_argument("--est-from-args", action="store_true",
                    help="estimate from the --est-* values even where committed logs have measurements")
    args = ap.parse_args(argv)
    if not args.dry_run and not args.run_id:
        ap.error("--run-id is required unless --dry-run")
    return args


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
    cells = list(CELLS.values()) if "all" in names else [CELLS[n] for n in names]
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
    by_lang = {lang: select_questions(load(lang=lang), args, pilot) for lang in sorted({c.lang for c in cells})}

    rows, total = dry_run([c for c in cells], {k: len(v) for k, v in by_lang.items()}, args.reps, args.model,
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

    client = DeepSeekClient(args.model)
    commit = eval_commit()
    guard = FingerprintGuard.from_logs(log_path(args.run_id, "x").parent, args.model)
    for cell in cells:
        ctx = RunContext(run_id=args.run_id, cell=cell, client=client, executor=make_executor(cell, args.exec_timeout),
                         system=system_for(cell), eval_commit=commit, harness_commit=harness_commit(),
                         timeout_s=args.exec_timeout, raw_dir=raw_root() / args.run_id / cell.name,
                         limits={"max_result_rows": DEFAULT_MAX_RESULT_ROWS, "max_memory_bytes": DEFAULT_MAX_MEMORY_BYTES},
                         eval_tag=args.eval_tag, semantic_tag=args.semantic_tag)
        path = run_cell(ctx, by_lang[cell.lang], args.reps, args.concurrency, guard=guard)
        print(json.dumps(summarize(path), ensure_ascii=False, indent=2))
        if guard.conflict:
            print(f"STOP: {args.model} answered with more than one system_fingerprint in this run: {guard.seen}. "
                  "Ask the user before going on (decisions/2026-10-17-model-version-fingerprint.md).")
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
