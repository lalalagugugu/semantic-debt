"""Explorer agent (探查 agent, -E cells, T15): direct answering plus one read-only tool.

    uv run python -m harness.run_agent --cell SQL-L1-E --dry-run
    uv run python -m harness.run_agent --cell SQL-L0-E --cell SQL-L1-E --pilot --reps 1 \\
        --run-id 20261020-T15-pilot-01

The model sees the direct cell's system message byte for byte (``harness-v1``) followed
by the tool section of ``harness/agent_prompt.py`` (``harness-agent-v1``), and may call
``run_sql`` on the same backend and execution scope as the direct cell's final query:
same static checks (single read-only SELECT, pinned settings, database scope) and
resource caps; ``run_sql`` times out after ``--tool-timeout`` (30 s), the final query
after ``--exec-timeout`` (120 s, as in direct answering). At most ``MAX_TOOL_CALLS`` calls; each shows at most
``ECHO_ROWS`` rows and says when it was cut. The tool runs only while ``tool_choice`` is
left to the model; once the calls are used up, one fixed user message ``TOOLS_EXHAUSTED``
is appended and the next request sends ``tool_choice: "none"``, so the model must answer
(T15-1). Calls beyond the limit inside one response are answered with ``LIMIT_REACHED``
and not executed.

The final answer (a reply without tool calls) is handled exactly as in direct answering:
parsed by ``harness.prompt``, executed, and on an execution error sent back once for a
fix (with ``tool_choice: "none"``). Scoring is ``run_direct.final_score`` (child process,
10 s limit, ``pending/score_timeout`` beyond).

In thinking mode the API requires every assistant message of a tool-calling conversation
to be sent back with its ``reasoning_content`` (400 otherwise), so all of them are.

Log line = direct line (``turns`` = the final answer and its fix, so ``harness.rescore``
works unchanged) plus ``steps``: one entry per tool-calling model call, with every tool
call's query, execution summary, rows shown and whether the result was cut. Raw files
in runs-raw: ``<qid>_r<rep>_t<call>.json`` for every model call,
``<qid>_r<rep>_t<call>.exec.json`` for the final answer and fix,
``<qid>_r<rep>_t<call>_c<k>.exec.json`` for tool executions.

The run refuses to start unless the bank is ``--eval-tag``, the semantic layer is
``--semantic-tag``, ``harness/prompt.py`` is ``harness-v1``'s and
``harness/agent_prompt.py`` is ``--agent-tag``'s (a dry run only warns about the last).
Every model call's ``system_fingerprint`` must be ``--expect-fingerprint`` (G3);
otherwise the run stops.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import agent_prompt as A  # noqa: E402
from harness import prompt as P  # noqa: E402
from harness import run_direct as R  # noqa: E402
from harness.cells import (  # noqa: E402
    AGENT_CELLS, CONTEXTS, DEFAULT_CONCURRENCY, DEFAULT_EXEC_TIMEOUT_S, DEFAULT_REPS, PEAK_MULTIPLIER,
    PRICES_OFFPEAK, REPO, Cell,
)
from harness.client import APIError, Reply  # noqa: E402
from harness.executors import DEFAULT_MAX_MEMORY_BYTES, DEFAULT_MAX_RESULT_ROWS, ExecResult, Executor  # noqa: E402
from harness.questions import Question  # noqa: E402

G3_FINGERPRINT = "e72d3c7f663d3e1383b00b3884cb4501"     # decisions/model.md, decisions/2026-10-18-g3-passed.md
HARNESS_TAG = "harness-v1"
TOOL_TIMEOUT_S = 30         # run_sql (user, 2026-10-19); the final query keeps DEFAULT_EXEC_TIMEOUT_S
AGENT_TAG = "harness-agent-v1.1"


def agent_system_for(cell: Cell) -> str:
    return A.agent_system_message(R.system_for(cell))


def agent_settings() -> dict:
    return {"max_tool_calls": A.MAX_TOOL_CALLS, "echo_rows": A.ECHO_ROWS, "echo_max_chars": A.ECHO_MAX_CHARS,
            "tool_section_sha256": R.sha256(A.TOOL_SECTION),
            "tools_sha256": R.sha256(json.dumps(A.TOOLS, ensure_ascii=False, sort_keys=True))}


# ---------------------------------------------------------------------------
# One attempt


def _assistant(reply: Reply) -> dict:
    """The assistant message sent back: content, reasoning (required with tools) and tool calls."""
    msg = {"role": "assistant", "content": reply.content, "reasoning_content": reply.reasoning or ""}
    if reply.tool_calls:
        msg["tool_calls"] = reply.tool_calls
    return msg


def _save_tool_exec(ctx: R.RunContext, q: Question, rep: int, call: int, k: int, result: ExecResult) -> str:
    payload = json.dumps({"columns": result.columns, "rows": result.rows, "error": result.error,
                          "error_class": result.error_class, "limit": result.limit, "detail": result.detail},
                         ensure_ascii=False, default=str).encode()
    path = ctx.raw_dir / f"{q.qid}_r{rep}_t{call}_c{k}.exec.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return R.sha256(payload)


def _tool_query(tc: dict) -> tuple[str | None, str | None]:
    """(query, problem) from one tool call."""
    fn = tc.get("function") or {}
    if fn.get("name") != A.TOOL_NAME:
        return None, "unknown_tool"
    try:
        args = json.loads(fn.get("arguments") or "")
    except (TypeError, ValueError):
        return None, "bad_arguments"
    query = args.get("query") if isinstance(args, dict) else None
    if not isinstance(query, str) or not query.strip():
        return None, "bad_arguments"
    return query, None


def _run_tool_calls(ctx: R.RunContext, q: Question, rep: int, call: int, reply: Reply,
                    used: int) -> tuple[list[dict], list[dict], int, float]:
    """Execute (or decline) every tool call of one reply.

    Returns (tool messages, call records, calls used so far, seconds spent executing)."""
    messages, records, spent = [], [], 0.0
    for k, tc in enumerate(reply.tool_calls or []):
        query, problem = _tool_query(tc)
        rec: dict = {"k": k, "id": tc.get("id"), "name": (tc.get("function") or {}).get("name"), "query": query}
        if used >= A.MAX_TOOL_CALLS:
            rec["status"], content = "limit_reached", A.LIMIT_REACHED
        elif problem:
            used += 1
            rec["status"], content = problem, A.BAD_ARGUMENTS if problem == "bad_arguments" else A.UNKNOWN_TOOL
            rec["arguments"] = ((tc.get("function") or {}).get("arguments") or "")[:500]
        else:
            used += 1
            start = time.monotonic()
            result = (ctx.tool_executor or ctx.executor).execute(query)
            spent += time.monotonic() - start
            content, shown, char_cut = A.render_result(result)
            rec["status"] = "executed"
            rec["exec"] = {**result.summary(), "exec_raw_sha256": _save_tool_exec(ctx, q, rep, call, k, result)}
            rec["echoed_rows"] = shown
            rec["truncated"] = bool(result.ok and len(result.rows or []) > A.ECHO_ROWS)
            rec["char_truncated"] = char_cut
        rec["tool_message_sha256"] = R.sha256(content)
        records.append(rec)
        messages.append({"role": "tool", "tool_call_id": tc.get("id") or "", "content": content})
    return messages, records, used, spent


def _step_record(ctx: R.RunContext, q: Question, rep: int, call: int, reply: Reply, tool_choice: str | None,
                 calls: list[dict]) -> dict:
    return {
        "call": call,
        "tool_choice": tool_choice,
        "tool_calls": calls,
        "content_chars": len(reply.content or ""),
        "finish_reason": reply.finish_reason,
        "system_fingerprint": reply.system_fingerprint,
        "usage": reply.usage,
        "latency_s": round(reply.latency_s, 3),
        "transport_retries": reply.transport_retries,
        "raw_sha256": R._save_raw(ctx, q, rep, call, reply),
    }


def run_attempt(ctx: R.RunContext, q: Question, rep: int) -> dict:
    """One independent attempt (fresh conversation); returns its log line."""
    started = datetime.now(R.BEIJING)
    wall = time.monotonic()
    peak = R.is_peak(started)
    messages: list[dict] = P.first_messages(ctx.system, q.text)
    base = {**R._base(ctx, q, rep, started),
            "agent": {**agent_settings(), "tool_timeout_s": getattr(ctx.tool_executor, "timeout_s", ctx.timeout_s)}}
    steps: list[dict] = []
    turns: list[dict] = []
    replies: list[Reply] = []
    used, tool_time = 0, 0.0
    call = 0
    limit_message_sent = False
    try:
        while True:
            choice = "none" if used >= A.MAX_TOOL_CALLS else None
            reply = ctx.client.chat(messages, tools=A.TOOLS, tool_choice=choice)
            replies.append(reply)
            if reply.tool_calls and choice != "none":
                tool_msgs, calls, used, spent = _run_tool_calls(ctx, q, rep, call, reply, used)
                tool_time += spent
                steps.append(_step_record(ctx, q, rep, call, reply, choice, calls))
                messages = messages + [_assistant(reply)] + tool_msgs
                if used >= A.MAX_TOOL_CALLS:      # the forced answer comes next: say so once (T15-1)
                    messages.append({"role": "user", "content": A.TOOLS_EXHAUSTED})
                    limit_message_sent = True
                call += 1
                continue
            break
        # the final answer: exactly the direct-answer rules from here on
        parsed = P.parse_response(reply.content)
        result = ctx.executor.execute(parsed.query) if parsed.query and not parsed.refused else None
        turn = R._turn_record(ctx, q, rep, call, reply, parsed, result)
        turn["tool_choice"] = choice
        if reply.tool_calls:        # only possible if the API ignored tool_choice "none"; never executed
            turn["ignored_tool_calls"] = len(reply.tool_calls)
        turns.append(turn)
        first_candidate = final_candidate = R._candidate(parsed, result)
        fixed = False
        if result is not None and not result.ok:
            messages = messages + [_assistant(reply), P.fix_message(result.error or "")]
            reply2 = ctx.client.chat(messages, tools=A.TOOLS, tool_choice="none")
            replies.append(reply2)
            parsed2 = P.parse_response(reply2.content)
            result2 = ctx.executor.execute(parsed2.query) if parsed2.query and not parsed2.refused else None
            turn2 = R._turn_record(ctx, q, rep, call + 1, reply2, parsed2, result2)
            turn2["tool_choice"] = "none"
            turns.append(turn2)
            final_candidate = R._candidate(parsed2, result2)
            fixed = True
    except APIError as exc:
        return {**base, "status": "api_error", "error": str(exc)[:500], "steps": steps, "turns": turns,
                "n_tool_calls": used, "limit_message_sent": limit_message_sent,
                "transport_retries": exc.transport_retries}

    line = R._done_line(ctx, q, base, turns, replies, first_candidate, final_candidate, fixed, peak)
    executed = [c for s in steps for c in s["tool_calls"] if c["status"] == "executed"]
    line.update({
        "steps": steps,
        "n_steps": len(steps),                      # model calls that called the tool
        "n_tool_calls": used,                       # run_sql calls counted against the limit
        "n_tool_executed": len(executed),
        "hit_tool_limit": used >= A.MAX_TOOL_CALLS,
        "limit_message_sent": limit_message_sent,
        "tool_time_s": round(tool_time, 3),
        "wall_s": round(time.monotonic() - wall, 3),
    })
    return line


# ---------------------------------------------------------------------------
# Fingerprint: every call must be the G3 model


class PinnedFingerprintGuard(R.FingerprintGuard):
    """``FingerprintGuard`` that also stops on any fingerprint other than the expected one."""

    def __init__(self, expected: str | None, seen: dict[str, int] | None = None) -> None:
        super().__init__(seen)
        self.expected = expected

    @property
    def conflict(self) -> bool:
        return len(self.seen) > 1 or (self.expected is not None and any(fp != self.expected for fp in self.seen))

    @classmethod
    def from_logs(cls, run_dir: Path, model: str, expected: str | None = None) -> "PinnedFingerprintGuard":
        seeded = R.FingerprintGuard.from_logs(run_dir, model)
        return cls(expected, seeded.seen)


# ---------------------------------------------------------------------------
# Summary


def summarize(path: Path) -> dict:
    """Direct summary plus the agent tax: steps, tool calls, tokens and time per attempt."""
    out = R.summarize(path)
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    done = [r for r in recs if r.get("status") == "done"]
    calls = [c for r in done for s in r.get("steps", []) for c in s["tool_calls"]]
    n = len(done) or 1
    out["system_fingerprints"] = R._count(t["system_fingerprint"] for r in done
                                          for t in r.get("steps", []) + r["turns"] if t.get("system_fingerprint"))
    out["agent"] = {
        "tool_calls_per_attempt": R._count(r["n_tool_calls"] for r in done),
        "mean_tool_calls": sum(r["n_tool_calls"] for r in done) / n,
        "mean_model_calls": sum(r["n_calls"] for r in done) / n,
        "attempts_without_tool": sum(r["n_tool_calls"] == 0 for r in done),
        "attempts_hit_limit": sum(r["hit_tool_limit"] for r in done),
        "attempts_limit_message_sent": sum(bool(r.get("limit_message_sent")) for r in done),
        "tool_call_status": R._count(c["status"] for c in calls),
        "tool_exec_status": R._count(c["exec"]["status"] for c in calls if c["status"] == "executed"),
        "tool_exec_error_classes": R._count(c["exec"].get("error_class") for c in calls
                                            if c["status"] == "executed" and c["exec"]["status"] == "error"),
        # read-only check (acceptance 2): an executed call either ran as a single SELECT or was refused
        "tool_forbidden_statements": sum(c["status"] == "executed" and c["exec"].get("error_class") == "forbidden_statement"
                                         for c in calls),
        "tool_results_truncated": sum(bool(c.get("truncated")) for c in calls),
        "tool_results_char_truncated": sum(bool(c.get("char_truncated")) for c in calls),
        "mean_prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in done) / n,
        "mean_completion_tokens": sum(r["usage"]["completion_tokens"] for r in done) / n,
        "mean_wall_s": sum(r["wall_s"] for r in done) / n,
        "mean_tool_time_s": sum(r["tool_time_s"] for r in done) / n,
        "mean_cost_cny": sum(r.get("cost_cny") or 0 for r in done) / n,
    }
    return out


# ---------------------------------------------------------------------------
# Dry run: from the measured step distribution where there is one


def measured(cell: str, runs_root: Path | None = None) -> dict | None:
    """Per-attempt means over every committed log of this -E cell (all model calls)."""
    attempts = []
    for path in sorted((runs_root or REPO / "runs").glob(f"*/{cell}.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line) if line.strip() else {}
            if rec.get("status") == "done" and "steps" in rec and not rec.get("rescored_from"):
                attempts.append(rec["usage"])
    if not attempts:
        return None
    n = len(attempts)
    return {"attempts": n, **{k: sum(a[k] for a in attempts) / n
                              for k in ("cache_hit_tokens", "cache_miss_tokens", "completion_tokens")}}


def estimated(cell: Cell, calls: float, growth: int, output: int, question_tokens: int) -> dict | None:
    """Per-attempt tokens if each attempt makes ``calls`` model calls and each call appends
    ``growth`` tokens (reasoning sent back + tool result) to the conversation.

    Call i re-sends calls 0..i-1 (cached after they were sent) and adds ``growth`` new tokens."""
    try:
        prefix = R.estimate_tokens_from_text(agent_system_for(cell))
    except (FileNotFoundError, NotImplementedError):
        return None
    k = max(1, round(calls))
    hit = miss = 0
    for i in range(k):
        new = question_tokens if i == 0 else growth
        total = prefix + question_tokens + i * growth
        hit += total - new
        miss += new
    return {"cache_hit_tokens": hit, "cache_miss_tokens": miss, "completion_tokens": k * output}


def dry_run(cells: list[str], n_questions: int, reps: int, model: str, *, calls: float, growth: int, output: int,
            question_tokens: int, runs_root: Path | None = None, use_measured: bool = True) -> tuple[list[dict], float]:
    price = PRICES_OFFPEAK[model]
    rows = []
    for name in cells:
        m = measured(name, runs_root) if use_measured else None
        per = m or estimated(AGENT_CELLS[name], calls, growth, output, question_tokens)
        source = f"measured ({m['attempts']} attempts)" if m else ("estimated" if per else "no context")
        attempts = n_questions * reps
        cost = None
        if per:
            cost = attempts * (per["cache_hit_tokens"] * price["hit"] + per["cache_miss_tokens"] * price["miss"]
                               + per["completion_tokens"] * price["output"]) / 1e6
        rows.append({"cell": name, "attempts": attempts, "per_attempt": per, "cost_offpeak": cost, "source": source})
    return rows, sum(r["cost_offpeak"] or 0 for r in rows)


def print_dry_run(rows: list[dict], total: float, model: str, reps: int) -> None:
    print(f"model={model} reps={reps} max_tool_calls={A.MAX_TOOL_CALLS} echo_rows={A.ECHO_ROWS} "
          f"(off-peak prices; peak = x{PEAK_MULTIPLIER:g})")
    print(f"{'cell':<12}{'attempts':>9}{'hit/att':>10}{'miss/att':>10}{'out/att':>9}{'CNY':>9}  source")
    for r in rows:
        p = r["per_attempt"] or {}
        cost = f"{r['cost_offpeak']:.2f}" if r["cost_offpeak"] is not None else "-"
        print(f"{r['cell']:<12}{r['attempts']:>9}{p.get('cache_hit_tokens', 0):>10.0f}{p.get('cache_miss_tokens', 0):>10.0f}"
              f"{p.get('completion_tokens', 0):>9.0f}{cost:>9}  {r['source']}")
    print(f"{'total':<12}{sum(r['attempts'] for r in rows):>9}{'':>29}{total:>9.2f}  (peak {total * PEAK_MULTIPLIER:.2f})")


# ---------------------------------------------------------------------------
# Versions


class HarnessVersionError(RuntimeError):
    pass


def verify_file_at_tag(path: str, tag: str, root: Path = REPO) -> str:
    """Full commit of ``tag`` if the working-tree ``path`` equals the file at that tag."""
    tagged = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}"],
                            capture_output=True, text=True)
    if tagged.returncode != 0:
        raise HarnessVersionError(f"tag {tag!r} not found (git fetch --tags)")
    blob = subprocess.run(["git", "-C", str(root), "show", f"{tag}:{path}"], capture_output=True)
    if blob.returncode != 0:
        raise HarnessVersionError(f"{path} does not exist at {tag}")
    if (root / path).read_bytes() != blob.stdout:
        raise HarnessVersionError(f"{path} differs from {tag}")
    return tagged.stdout.strip()


# ---------------------------------------------------------------------------
# CLI


def make_executor(cell: Cell, timeout_s: int) -> Executor:
    if cell.stack == "cube_sql":
        from harness.executors import CubeSqlExecutor

        return CubeSqlExecutor(timeout_s=timeout_s)
    return R.make_executor(cell, timeout_s)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell", action="append", required=True, choices=sorted(AGENT_CELLS), help="repeatable")
    ap.add_argument("--run-id", help="runs/<run-id>/; required unless --dry-run")
    ap.add_argument("--model", default="deepseek-flash", choices=sorted(PRICES_OFFPEAK))
    ap.add_argument("--reps", type=int, default=DEFAULT_REPS)
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--exec-timeout", type=int, default=DEFAULT_EXEC_TIMEOUT_S,
                    help="seconds per execution of the final query (as in direct answering)")
    ap.add_argument("--tool-timeout", type=int, default=TOOL_TIMEOUT_S, help="seconds per run_sql execution")
    ap.add_argument("--questions", help="comma-separated question ids (default: all)")
    ap.add_argument("--pilot", action="store_true", help="T06's pilot sample only (questions/pilot.yaml)")
    ap.add_argument("--limit", type=int, help="first N questions only")
    ap.add_argument("--eval-tag", default="eval-v1.1")
    ap.add_argument("--semantic-tag", default="semantic-v1.2")
    ap.add_argument("--agent-tag", default=AGENT_TAG, help="harness/agent_prompt.py must be this tag's")
    ap.add_argument("--expect-fingerprint", default=G3_FINGERPRINT,
                    help="stop when a call answers with another system_fingerprint ('' = only one per run)")
    ap.add_argument("--allow-cube", action="store_true",
                    help="SQL-L2-E runs only after T16 has confirmed the Cube metrics")
    ap.add_argument("--dry-run", action="store_true", help="count attempts and estimate cost; no API call")
    ap.add_argument("--budget", type=float, help="CNY; refuse to start if the estimate exceeds it")
    ap.add_argument("--allow-peak", action="store_true", help="allow starting in DeepSeek peak hours")
    ap.add_argument("--est-calls", type=float, default=5.0, help="model calls per attempt (no measurement yet)")
    ap.add_argument("--est-growth-tokens", type=int, default=2500,
                    help="tokens each call appends (reasoning sent back + tool result)")
    ap.add_argument("--est-output-tokens", type=int, default=2000, help="output tokens per call")
    ap.add_argument("--est-question-tokens", type=int, default=60)
    ap.add_argument("--est-from-args", action="store_true", help="ignore committed measurements")
    args = ap.parse_args(argv)
    if not args.dry_run and not args.run_id:
        ap.error("--run-id is required unless --dry-run")
    if "SQL-L2-E" in args.cell and not args.dry_run and not args.allow_cube:
        ap.error("SQL-L2-E waits for T16 to confirm the Cube metrics (pass --allow-cube once it has)")
    return args


def main(argv: list[str] | None = None, load=None) -> int:
    from harness.questions import EvalVersionError, eval_commit, load_questions, pilot_ids, verify_eval_tag
    from harness.semantic_version import SemanticVersionError, verify_semantic_tag

    args = parse_args(argv)
    cells = [AGENT_CELLS[n] for n in args.cell]
    if load is None:
        try:
            print(f"question bank: {args.eval_tag} = {verify_eval_tag(args.eval_tag)}")
            built = [c.context.partition(":")[2] for c in cells if c.context.startswith("build:")]
            print(f"semantic layer: {args.semantic_tag} = "
                  f"{verify_semantic_tag(args.semantic_tag, built, root=REPO, contexts_dir=CONTEXTS)}")
            print(f"system prompt: {HARNESS_TAG} = {verify_file_at_tag('harness/prompt.py', HARNESS_TAG)}")
        except (EvalVersionError, SemanticVersionError, HarnessVersionError) as exc:
            print(f"refusing to start: {exc}")
            return 2
        try:
            print(f"tool section: {args.agent_tag} = {verify_file_at_tag('harness/agent_prompt.py', args.agent_tag)}")
        except HarnessVersionError as exc:
            if not args.dry_run:
                print(f"refusing to start: {exc}")
                return 2
            print(f"warning (dry run only): {exc}")
    load = load or load_questions
    pilot = pilot_ids() if args.pilot else None
    try:
        questions = R.select_questions(load(lang="zh"), args, pilot)
    except EvalVersionError as exc:
        print(f"refusing to start: {exc}")
        return 2

    rows, total = dry_run(args.cell, len(questions), args.reps, args.model, calls=args.est_calls,
                          growth=args.est_growth_tokens, output=args.est_output_tokens,
                          question_tokens=args.est_question_tokens, use_measured=not args.est_from_args)
    print_dry_run(rows, total, args.model, args.reps)
    if args.dry_run:
        return 0
    if args.budget is not None and total > args.budget:
        print(f"estimate {total:.2f} CNY exceeds budget {args.budget:.2f}; stop and ask the user")
        return 2
    if R.is_peak() and not args.allow_peak:
        print("DeepSeek peak hours (weekdays 09-12, 14-18 Beijing): batch runs go off-peak (hard rule 6)")
        return 2

    from harness.client import DeepSeekClient

    client = DeepSeekClient(args.model)
    commit = eval_commit()
    guard = PinnedFingerprintGuard.from_logs(R.log_path(args.run_id, "x").parent, args.model,
                                             args.expect_fingerprint or None)
    for cell_name, cell in zip(args.cell, cells):
        ctx = R.RunContext(run_id=args.run_id, cell=_named(cell, cell_name), client=client,
                           executor=make_executor(cell, args.exec_timeout),
                           tool_executor=make_executor(cell, args.tool_timeout), system=agent_system_for(cell),
                           eval_commit=commit, harness_commit=R.harness_commit(), timeout_s=args.exec_timeout,
                           raw_dir=R.raw_root() / args.run_id / cell_name,
                           limits={"max_result_rows": DEFAULT_MAX_RESULT_ROWS,
                                   "max_memory_bytes": DEFAULT_MAX_MEMORY_BYTES},
                           eval_tag=args.eval_tag, semantic_tag=args.semantic_tag)
        path = R.run_cell(ctx, questions, args.reps, args.concurrency, guard=guard, attempt=run_attempt)
        print(json.dumps(summarize(path), ensure_ascii=False, indent=2))
        if guard.conflict:
            print(f"STOP: system_fingerprint {guard.seen} is not only {args.expect_fingerprint or 'one value'}. "
                  "Ask the user before going on (decisions/2026-10-17-model-version-fingerprint.md).")
            return 3
    return 0


def _named(cell: Cell, name: str) -> Cell:
    """The direct cell's definition under the -E name (log file, ``cell`` field)."""
    from dataclasses import replace

    return replace(cell, name=name, card="T15")


if __name__ == "__main__":
    raise SystemExit(main())
