"""Planning agent (规划 agent, -P cells, T21): the explorer agent plus a plan, a Python
fallback and on-demand retrieval of the semantic context.

    uv run python -m harness.run_plan --cell SQL-L1-P --dry-run
    uv run python -m harness.run_plan --cell SQL-L0-P --cell SQL-L1-P --pilot --reps 1 \\
        --run-id 20261020-T21-pilot-01 --budget 3

Built on ``harness/run_agent.py`` (T15) and reusing everything it has: ``run_sql`` on the
same executor, scope and read-only checks (30 s; final queries 120 s), the 50-row echo,
the log fields, the fingerprint guard, ``--dry-run`` / ``--budget``, the "calls used up"
message before the forced answer (T15-1), one fix of an execution error, scoring in a
child process with a time limit.

What is new (``harness/plan_prompt.py``, frozen as ``harness-plan-v1``):

- the system message carries a catalog of the cell's semantic context instead of the full
  context; ``lookup`` returns entries verbatim from the rendered YAML;
- ``plan(steps)`` must come before any other tool and may be revised (every version is in
  runs-raw, its hash in the log);
- ``python(code)`` runs in the Docker sandbox of ``harness/pysandbox.py`` (no network, no
  files); ``results[n]`` is run_sql result n, up to ``MAX_PY_ROWS`` rows;
- the final answer is one query (as in direct answering) or queries + Python: the harness
  re-runs the queries with the final-query executor and the code in the same sandbox, and
  the ``answer`` DataFrame is scored like a query result. An execution error (of a query
  or of the code) is sent back once.

lookup + run_sql + python share ``MAX_TOOL_CALLS``; plan calls beyond ``MAX_PLANS`` count
too. As a backstop the attempt never makes more than ``MAX_MODEL_CALLS`` tool-calling
model calls (rejected calls before a plan are not counted against the tools).

Log line = -E line (``turns`` = the final answer and its fix; for a Python answer the
turn's ``.exec.json`` holds the ``answer`` rows, so ``harness.rescore`` works unchanged)
plus plans, every lookup / python call and the answer form. Plans and Python code may
paraphrase the question, so the log has only their hashes and sizes; the text is in
runs-raw (``<qid>_r<rep>_t<call>_c<k>.plan.json`` / ``.py.json``).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import plan_prompt as PP  # noqa: E402
from harness import prompt as P  # noqa: E402
from harness import run_agent as AG  # noqa: E402
from harness import run_direct as R  # noqa: E402
from harness.cells import (  # noqa: E402
    CONTEXTS, DEFAULT_CONCURRENCY, DEFAULT_EXEC_TIMEOUT_S, DEFAULT_REPS, PEAK_MULTIPLIER, PLAN_CELLS,
    PRICES_OFFPEAK, REPO, SYNTAX, Cell,
)
from harness.client import APIError, Reply  # noqa: E402
from harness.executors import DEFAULT_MAX_MEMORY_BYTES, DEFAULT_MAX_RESULT_ROWS, ExecResult  # noqa: E402
from harness.questions import Question  # noqa: E402
from harness.scorer import ExecError  # noqa: E402

PLAN_TAG = "harness-plan-v1"
PLAN_FILES = ("harness/plan_prompt.py", "harness/pysandbox.py", "harness/pysandbox_image/runner.py",
              "harness/pysandbox_image/Dockerfile")
MAX_MODEL_CALLS = PP.MAX_TOOL_CALLS + PP.MAX_PLANS + 3


def plan_system_for(cell: Cell) -> str:
    return PP.plan_system_message(R.context_text(cell), (SYNTAX / cell.syntax).read_text(encoding="utf-8"))


def plan_settings() -> dict:
    return {"max_tool_calls": PP.MAX_TOOL_CALLS, "max_plans": PP.MAX_PLANS, "max_model_calls": MAX_MODEL_CALLS,
            "max_lookup_names": PP.MAX_LOOKUP_NAMES, "echo_rows": PP.ECHO_ROWS, "echo_max_chars": PP.ECHO_MAX_CHARS,
            "max_py_rows": PP.MAX_PY_ROWS, "py_timeout_s": PP.PY_TIMEOUT_S,
            "tool_section_sha256": R.sha256(PP.TOOL_SECTION),
            "tools_sha256": R.sha256(json.dumps(PP.TOOLS, ensure_ascii=False, sort_keys=True))}


@dataclass
class PlanContext(R.RunContext):
    sandbox: Any = None             # .run(code, tables, want_answer) -> pysandbox.PyResult
    lookup: PP.Lookup | None = None


# ---------------------------------------------------------------------------
# One attempt


@dataclass
class _State:
    used: int = 0                   # counted tool calls
    plan_calls: int = 0
    n_results: int = 0
    tables: dict | None = None      # result number -> {"columns", "rows"} (<= MAX_PY_ROWS rows)
    tool_time: float = 0.0
    py_time: float = 0.0

    def __post_init__(self) -> None:
        self.tables = {}


def _save_json(ctx: R.RunContext, name: str, obj) -> str:
    payload = json.dumps(obj, ensure_ascii=False, default=str).encode()
    path = ctx.raw_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return R.sha256(payload)


def _run_one(ctx: PlanContext, q: Question, rep: int, call: int, k: int, tc: dict, st: _State) -> tuple[str, dict]:
    name, args = PP.tool_args(tc)
    rec: dict = {"k": k, "id": tc.get("id"), "name": name}
    stem = f"{q.qid}_r{rep}_t{call}_c{k}"
    if name == PP.PLAN:
        steps = args.get("steps") if args else None
        if not isinstance(steps, list) or not steps:
            rec["status"] = "bad_arguments"
            return PP.BAD_ARGUMENTS, rec
        st.plan_calls += 1
        if st.plan_calls > PP.MAX_PLANS:
            if st.used >= PP.MAX_TOOL_CALLS:
                rec["status"] = "limit_reached"
                return PP.LIMIT_REACHED, rec
            st.used += 1
            rec["counted"] = True
        steps = [str(s) for s in steps]
        rec.update(status="recorded", version=st.plan_calls, n_steps=len(steps),
                   plan_raw_sha256=_save_json(ctx, f"{stem}.plan.json", steps))
        return (PP.PLAN_LIMIT if rec.get("counted") else PP.PLAN_RECORDED), rec
    if name in PP.COUNTED_TOOLS and st.plan_calls == 0:
        rec["status"] = "plan_first"
        return PP.PLAN_FIRST, rec
    if st.used >= PP.MAX_TOOL_CALLS:
        rec["status"] = "limit_reached"
        return PP.LIMIT_REACHED, rec
    st.used += 1
    if name not in PP.COUNTED_TOOLS:
        rec["status"] = "unknown_tool"
        return PP.UNKNOWN_TOOL, rec
    field = {PP.LOOKUP: "names", PP.RUN_SQL: "query", PP.PYTHON: "code"}[name]
    value = args.get(field) if args else None
    ok = (isinstance(value, list) and value and all(isinstance(v, str) for v in value)) if name == PP.LOOKUP \
        else (isinstance(value, str) and value.strip())
    if not ok:
        rec["status"] = "bad_arguments"
        rec["arguments"] = ((tc.get("function") or {}).get("arguments") or "")[:500]
        return PP.BAD_ARGUMENTS, rec
    rec["status"] = "executed"
    if name == PP.LOOKUP:
        content, found, missing = ctx.lookup.render(value)
        rec.update(found=found, missing=missing, chars=len(content))
        return content, rec
    if name == PP.RUN_SQL:
        start = time.monotonic()
        result = (ctx.tool_executor or ctx.executor).execute(value)
        st.tool_time += time.monotonic() - start
        n = None
        if result.ok:
            st.n_results += 1
            n = st.n_results
            st.tables[n] = {"columns": result.columns, "rows": (result.rows or [])[:PP.MAX_PY_ROWS]}
        content, shown, char_cut = PP.render_sql_result(n, result, PP.MAX_PY_ROWS)
        rec.update(query=value, result_no=n,
                   exec={**result.summary(), "exec_raw_sha256": AG._save_tool_exec(ctx, q, rep, call, k, result)},
                   echoed_rows=shown, truncated=bool(result.ok and len(result.rows or []) > PP.ECHO_ROWS),
                   char_truncated=char_cut,
                   py_rows_cut=bool(result.ok and len(result.rows or []) > PP.MAX_PY_ROWS))
        return content, rec
    result = ctx.sandbox.run(value, dict(st.tables))
    st.py_time += result.elapsed_s
    content = PP.render_python(result)
    rec.update(code_chars=len(value), py=result.summary(),
               py_raw_sha256=_save_json(ctx, f"{stem}.py.json", {"code": value, "tables": sorted(st.tables),
                                                                 "stdout": result.stdout, "error": result.error,
                                                                 "error_class": result.error_class}))
    return content, rec


def _run_tool_calls(ctx: PlanContext, q: Question, rep: int, call: int, reply: Reply, st: _State):
    messages, records = [], []
    for k, tc in enumerate(reply.tool_calls or []):
        content, rec = _run_one(ctx, q, rep, call, k, tc, st)
        rec["tool_message_sha256"] = R.sha256(content)
        records.append(rec)
        messages.append({"role": "tool", "tool_call_id": tc.get("id") or "", "content": content})
    return messages, records


def execute_final(ctx: PlanContext, final: PP.FinalAnswer) -> tuple[ExecResult | None, dict]:
    """Run a final answer. Returns (the result scored — query rows, the ``answer`` table, or
    the first error — and the per-part summaries). ``None`` for a refusal or no answer."""
    if final.kind == "sql":
        return ctx.executor.execute(final.queries[0]), {}
    if final.kind != "sql+python":
        return None, {}
    parts: dict = {"queries": []}
    tables = {}
    for i, query in enumerate(final.queries, 1):
        result = ctx.executor.execute(query)
        parts["queries"].append(result.summary())
        if not result.ok:
            return replace(result, error=f"查询 {i} 执行报错：\n{result.error}"), parts
        if len(result.rows or []) > PP.MAX_PY_ROWS:
            msg = PP.ANSWER_ROWS_CUT.format(i=i, total=len(result.rows))
            return ExecResult(error=msg, error_class="resource_limit", limit="py_rows",
                              elapsed_s=result.elapsed_s), parts
        tables[i] = {"columns": result.columns, "rows": result.rows or []}
    py = ctx.sandbox.run(final.python, tables, want_answer=True)
    parts["python"] = py.summary()
    if not py.ok:
        msg = PP.PY_ERROR.format(error=py.error or "")
        return ExecResult(error=msg, error_class=py.error_class, elapsed_s=py.elapsed_s,
                          limit="python_timeout" if py.error_class == "timeout" else None,
                          detail=(py.stdout or "")[-2000:] or None), parts
    return ExecResult(rows=py.answer["rows"], columns=py.answer["columns"], elapsed_s=py.elapsed_s), parts


def _final_turn(ctx: PlanContext, q: Question, rep: int, call: int, reply: Reply, final: PP.FinalAnswer,
                result: ExecResult | None, parts: dict, choice: str | None) -> dict:
    if final.kind == "sql+python":
        turn = R._turn_record(ctx, q, rep, call, reply,
                              P.Parsed("(sql+python)", final.assumption, False, final.n_code_blocks), result)
        turn.update(query=None, queries=list(final.queries), python_chars=len(final.python or ""),
                    python_raw_sha256=_save_json(ctx, f"{q.qid}_r{rep}_t{call}.answer.py.json",
                                                 {"queries": list(final.queries), "code": final.python}),
                    parts=parts)
    else:
        turn = R._turn_record(ctx, q, rep, call, reply, final.as_parsed(), result)
    turn["answer_kind"] = final.kind
    turn["tool_choice"] = choice
    if reply.tool_calls:        # only possible if the API ignored tool_choice "none"; never executed
        turn["ignored_tool_calls"] = len(reply.tool_calls)
    return turn


def _candidate(final: PP.FinalAnswer, result: ExecResult | None):
    if final.kind == "sql+python":
        return ExecError(result.error or "execution error") if not result.ok else result.rows
    return R._candidate(final.as_parsed(), result)


def run_attempt(ctx: PlanContext, q: Question, rep: int) -> dict:
    """One independent attempt (fresh conversation); returns its log line."""
    started = datetime.now(R.BEIJING)
    wall = time.monotonic()
    peak = R.is_peak(started)
    messages: list[dict] = P.first_messages(ctx.system, q.text)
    base = {**R._base(ctx, q, rep, started),
            "agent": {**plan_settings(), "tool_timeout_s": getattr(ctx.tool_executor, "timeout_s", ctx.timeout_s)}}
    steps: list[dict] = []
    turns: list[dict] = []
    replies: list[Reply] = []
    st = _State()
    call = 0
    limit_message_sent = False
    try:
        while True:
            exhausted = st.used >= PP.MAX_TOOL_CALLS or call >= MAX_MODEL_CALLS
            choice = "none" if exhausted else None
            reply = ctx.client.chat(messages, tools=PP.TOOLS, tool_choice=choice)
            replies.append(reply)
            if reply.tool_calls and choice != "none":
                tool_msgs, calls = _run_tool_calls(ctx, q, rep, call, reply, st)
                steps.append(AG._step_record(ctx, q, rep, call, reply, choice, calls))
                messages = messages + [AG._assistant(reply)] + tool_msgs
                call += 1
                if st.used >= PP.MAX_TOOL_CALLS or call >= MAX_MODEL_CALLS:   # forced answer next (T15-1)
                    messages.append({"role": "user", "content": PP.TOOLS_EXHAUSTED})
                    limit_message_sent = True
                continue
            break
        final = PP.parse_final(reply.content)
        result, parts = execute_final(ctx, final)
        turns.append(_final_turn(ctx, q, rep, call, reply, final, result, parts, choice))
        first_candidate = final_candidate = _candidate(final, result)
        answer_kinds = [final.kind]
        fixed = False
        if result is not None and not result.ok:
            messages = messages + [AG._assistant(reply), P.fix_message(result.error or "")]
            reply2 = ctx.client.chat(messages, tools=PP.TOOLS, tool_choice="none")
            replies.append(reply2)
            final2 = PP.parse_final(reply2.content)
            result2, parts2 = execute_final(ctx, final2)
            turns.append(_final_turn(ctx, q, rep, call + 1, reply2, final2, result2, parts2, "none"))
            final_candidate = _candidate(final2, result2)
            answer_kinds.append(final2.kind)
            fixed = True
    except APIError as exc:
        return {**base, "status": "api_error", "error": str(exc)[:500], "steps": steps, "turns": turns,
                "n_tool_calls": st.used, "limit_message_sent": limit_message_sent,
                "transport_retries": exc.transport_retries}

    line = R._done_line(ctx, q, base, turns, replies, first_candidate, final_candidate, fixed, peak)
    calls = [c for s in steps for c in s["tool_calls"]]
    by_tool = {t: sum(c["name"] == t and c["status"] == "executed" for c in calls) for t in PP.COUNTED_TOOLS}
    line.update({
        "steps": steps,
        "n_steps": len(steps),
        "n_tool_calls": st.used,
        "n_tool_executed": sum(by_tool.values()),
        "tool_executed": by_tool,
        "n_plans": sum(c["name"] == PP.PLAN and c["status"] == "recorded" for c in calls),
        "plan_first_rejections": sum(c["status"] == "plan_first" for c in calls),
        "hit_tool_limit": st.used >= PP.MAX_TOOL_CALLS,
        "hit_model_call_limit": call >= MAX_MODEL_CALLS,
        "limit_message_sent": limit_message_sent,
        "answer_kind": answer_kinds[-1],
        "answer_kinds": answer_kinds,
        "tool_time_s": round(st.tool_time, 3),
        "python_time_s": round(st.py_time, 3),
        "wall_s": round(time.monotonic() - wall, 3),
    })
    return line


# ---------------------------------------------------------------------------
# Summary


def summarize(path: Path) -> dict:
    """-E summary plus plans, lookup / python use and the answer form."""
    out = AG.summarize(path)
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    done = [r for r in recs if r.get("status") == "done"]
    calls = [c for r in done for s in r.get("steps", []) for c in s["tool_calls"]]
    n = len(done) or 1
    finals = {}
    for r in done:
        kind = r.get("answer_kind")
        finals.setdefault(kind, R._count([]))
    out["plan"] = {
        "answer_kind": R._count(r.get("answer_kind") for r in done),
        "accuracy_by_answer_kind": {k: R._count(r["final"]["outcome"] for r in done if r.get("answer_kind") == k)
                                    for k in finals},
        "attempts_without_plan": sum(r.get("n_plans", 0) == 0 for r in done),
        "mean_plans": sum(r.get("n_plans", 0) for r in done) / n,
        "plan_first_rejections": sum(r.get("plan_first_rejections", 0) for r in done),
        "tool_executed": {t: sum(r.get("tool_executed", {}).get(t, 0) for r in done) for t in PP.COUNTED_TOOLS},
        "attempts_using": {t: sum(r.get("tool_executed", {}).get(t, 0) > 0 for r in done) for t in PP.COUNTED_TOOLS},
        "lookup_missing_names": sum(len(c.get("missing") or []) for c in calls if c["name"] == PP.LOOKUP),
        "python_status": R._count((c.get("py") or {}).get("error_class") or "ok" for c in calls
                                  if c["name"] == PP.PYTHON and c["status"] == "executed"),
        "attempts_hit_model_call_limit": sum(bool(r.get("hit_model_call_limit")) for r in done),
        "mean_python_time_s": sum(r.get("python_time_s", 0) for r in done) / n,
    }
    return out


# ---------------------------------------------------------------------------
# Dry run


def estimated(cell: Cell, calls: float, growth: int, output: int, question_tokens: int) -> dict | None:
    try:
        prefix = R.estimate_tokens_from_text(plan_system_for(cell))
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
        m = AG.measured(name, runs_root) if use_measured else None
        per = m or estimated(PLAN_CELLS[name], calls, growth, output, question_tokens)
        source = f"measured ({m['attempts']} attempts)" if m else ("estimated" if per else "no context")
        attempts = n_questions * reps
        cost = None
        if per:
            cost = attempts * (per["cache_hit_tokens"] * price["hit"] + per["cache_miss_tokens"] * price["miss"]
                               + per["completion_tokens"] * price["output"]) / 1e6
        rows.append({"cell": name, "attempts": attempts, "per_attempt": per, "cost_offpeak": cost, "source": source})
    return rows, sum(r["cost_offpeak"] or 0 for r in rows)


def print_dry_run(rows: list[dict], total: float, model: str, reps: int) -> None:
    print(f"model={model} reps={reps} max_tool_calls={PP.MAX_TOOL_CALLS} max_model_calls={MAX_MODEL_CALLS} "
          f"(off-peak prices; peak = x{PEAK_MULTIPLIER:g})")
    print(f"{'cell':<12}{'attempts':>9}{'hit/att':>10}{'miss/att':>10}{'out/att':>9}{'CNY':>9}  source")
    for r in rows:
        p = r["per_attempt"] or {}
        cost = f"{r['cost_offpeak']:.2f}" if r["cost_offpeak"] is not None else "-"
        print(f"{r['cell']:<12}{r['attempts']:>9}{p.get('cache_hit_tokens', 0):>10.0f}{p.get('cache_miss_tokens', 0):>10.0f}"
              f"{p.get('completion_tokens', 0):>9.0f}{cost:>9}  {r['source']}")
    print(f"{'total':<12}{sum(r['attempts'] for r in rows):>9}{'':>29}{total:>9.2f}  (peak {total * PEAK_MULTIPLIER:.2f})")


# ---------------------------------------------------------------------------
# CLI


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell", action="append", required=True, choices=sorted(PLAN_CELLS), help="repeatable")
    ap.add_argument("--run-id", help="runs/<run-id>/; required unless --dry-run")
    ap.add_argument("--model", default="deepseek-flash", choices=sorted(PRICES_OFFPEAK))
    ap.add_argument("--reps", type=int, default=DEFAULT_REPS)
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--exec-timeout", type=int, default=DEFAULT_EXEC_TIMEOUT_S)
    ap.add_argument("--tool-timeout", type=int, default=AG.TOOL_TIMEOUT_S)
    ap.add_argument("--questions", help="comma-separated question ids (default: all)")
    ap.add_argument("--pilot", action="store_true", help="T06's pilot sample only (questions/pilot.yaml)")
    ap.add_argument("--limit", type=int, help="first N questions only")
    ap.add_argument("--eval-tag", default="eval-v1.1")
    ap.add_argument("--semantic-tag", default="semantic-v1.2")
    ap.add_argument("--agent-tag", default=AG.AGENT_TAG, help="harness/agent_prompt.py must be this tag's")
    ap.add_argument("--plan-tag", default=PLAN_TAG, help="plan_prompt.py and the sandbox files must be this tag's")
    ap.add_argument("--expect-fingerprint", default=AG.G3_FINGERPRINT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget", type=float, help="CNY; refuse to start if the estimate exceeds it")
    ap.add_argument("--allow-peak", action="store_true")
    ap.add_argument("--est-calls", type=float, default=7.0, help="model calls per attempt (no measurement yet)")
    ap.add_argument("--est-growth-tokens", type=int, default=3000)
    ap.add_argument("--est-output-tokens", type=int, default=2000)
    ap.add_argument("--est-question-tokens", type=int, default=60)
    ap.add_argument("--est-from-args", action="store_true", help="ignore committed measurements")
    args = ap.parse_args(argv)
    if not args.dry_run and not args.run_id:
        ap.error("--run-id is required unless --dry-run")
    return args


def check_versions(args) -> list[str]:
    """Refusals (empty = all pinned). The plan tag is only a warning in a dry run."""
    from harness.questions import EvalVersionError, verify_eval_tag
    from harness.semantic_version import SemanticVersionError, verify_semantic_tag

    cells = [PLAN_CELLS[n] for n in args.cell]
    try:
        print(f"question bank: {args.eval_tag} = {verify_eval_tag(args.eval_tag)}")
        built = [c.context.partition(":")[2] for c in cells if c.context.startswith("build:")]
        print(f"semantic layer: {args.semantic_tag} = "
              f"{verify_semantic_tag(args.semantic_tag, built, root=REPO, contexts_dir=CONTEXTS)}")
        print(f"system prompt: {AG.HARNESS_TAG} = {AG.verify_file_at_tag('harness/prompt.py', AG.HARNESS_TAG)}")
        print(f"run_sql echo: {args.agent_tag} = {AG.verify_file_at_tag('harness/agent_prompt.py', args.agent_tag)}")
    except (EvalVersionError, SemanticVersionError, AG.HarnessVersionError) as exc:
        return [str(exc)]
    problems = []
    for path in PLAN_FILES:
        try:
            print(f"{path}: {args.plan_tag} = {AG.verify_file_at_tag(path, args.plan_tag)}")
        except AG.HarnessVersionError as exc:
            problems.append(str(exc))
    if problems and args.dry_run:
        for p in problems:
            print(f"warning (dry run only): {p}")
        return []
    return problems


def main(argv: list[str] | None = None, load=None, sandbox=None) -> int:
    from harness.questions import EvalVersionError, eval_commit, load_questions, pilot_ids

    args = parse_args(argv)
    cells = [PLAN_CELLS[n] for n in args.cell]
    if load is None:
        problems = check_versions(args)
        if problems:
            print(f"refusing to start: {'; '.join(problems)}")
            return 2
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

    if sandbox is None:
        from harness.pysandbox import DockerSandbox

        sandbox = DockerSandbox()
    probe = sandbox.run("print(1 + 1)", {})
    if not probe.ok or probe.stdout.strip() != "2":
        print(f"refusing to start: the Python sandbox does not run ({probe.error_class}: {probe.error})")
        return 2

    from harness.client import DeepSeekClient

    client = DeepSeekClient(args.model)
    commit = eval_commit()
    guard = AG.PinnedFingerprintGuard.from_logs(R.log_path(args.run_id, "x").parent, args.model,
                                                args.expect_fingerprint or None)
    for cell_name, cell in zip(args.cell, cells):
        ctx = PlanContext(run_id=args.run_id, cell=_named(cell, cell_name), client=client,
                          executor=AG.make_executor(cell, args.exec_timeout),
                          tool_executor=AG.make_executor(cell, args.tool_timeout), system=plan_system_for(cell),
                          eval_commit=commit, harness_commit=R.harness_commit(), timeout_s=args.exec_timeout,
                          raw_dir=R.raw_root() / args.run_id / cell_name,
                          limits={"max_result_rows": DEFAULT_MAX_RESULT_ROWS,
                                  "max_memory_bytes": DEFAULT_MAX_MEMORY_BYTES},
                          eval_tag=args.eval_tag, semantic_tag=args.semantic_tag,
                          sandbox=sandbox, lookup=PP.Lookup(R.context_text(cell)))
        path = R.run_cell(ctx, questions, args.reps, args.concurrency, guard=guard, attempt=run_attempt)
        print(json.dumps(summarize(path), ensure_ascii=False, indent=2))
        if guard.conflict:
            print(f"STOP: system_fingerprint {guard.seen} is not only {args.expect_fingerprint or 'one value'}. "
                  "Ask the user before going on (decisions/2026-10-17-model-version-fingerprint.md).")
            return 3
    return 0


def _named(cell: Cell, name: str) -> Cell:
    return replace(cell, name=name, card="T21")


if __name__ == "__main__":
    raise SystemExit(main())
