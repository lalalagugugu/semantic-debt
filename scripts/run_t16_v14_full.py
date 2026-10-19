"""Approved serial T16 batch, with per-response accounting and stop boundaries.

No prompt, scorer, request body, question selection, or correction rule changes.
Every paid response is saved by run_direct before check_reply can stop a run.
"""
import argparse
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import urllib.request

from harness import cells as C
from harness import run_direct as R
from harness.client import DeepSeekClient
from harness.questions import load_questions, verify_eval_tag
from harness.semantic_version import verify_semantic_tag

ROOT = Path(__file__).resolve().parents[1]
FP = "e72d3c7f663d3e1383b00b3884cb4501"
MODEL = "deepseek-flash"


def append_json(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class BudgetBoundary(R.CallBoundary):
    def __init__(self, ledger, limit=Decimal("10")):
        super().__init__(FP)
        self.ledger = Path(ledger)
        self.limit = Decimal(limit)
        self.spent = Decimal("0")
        self.calls = 0
        self.local = threading.local()
        self.account_lock = threading.RLock()

    def wait_offpeak(self):
        paused = False
        while R.is_peak() and not self.stopped.is_set():
            if not paused:
                print("PAUSED: peak window; no requests until off-peak", flush=True)
                append_json(self.ledger.parent / "events.jsonl", {"event": "peak_pause", "at": datetime.now(R.BEIJING).isoformat()})
                paused = True
            time.sleep(30)
        if paused:
            append_json(self.ledger.parent / "events.jsonl", {"event": "offpeak_resume", "at": datetime.now(R.BEIJING).isoformat()})
            print("RESUMED: off-peak", flush=True)

    def before_request(self):
        if self.stopped.is_set():
            raise R.RunStopped(self.reason)
        if self.spent >= self.limit:
            self.stop(f"unit budget exhausted: {self.spent} CNY / {self.limit} CNY")
        self.wait_offpeak()
        super().before_request()  # Also covers every actual transport retry.

    def check_reply(self, reply):
        with self.account_lock:
            self.account_reply(reply)

    def account_reply(self, reply):
        usage = reply.usage
        valid = all(isinstance(usage.get(k), int) and usage[k] >= 0 for k in
                    ("prompt_tokens", "cache_hit_tokens", "cache_miss_tokens", "completion_tokens"))
        valid = valid and usage["prompt_tokens"] + usage["completion_tokens"] > 0
        cost = None
        if valid:
            hit = usage["cache_hit_tokens"]
            miss = max(usage["cache_miss_tokens"], usage["prompt_tokens"] - hit)
            price = C.PRICES_OFFPEAK[MODEL]
            cost = (Decimal(hit) * Decimal(str(price["hit"])) + Decimal(miss) * Decimal(str(price["miss"]))
                    + Decimal(usage["completion_tokens"]) * Decimal(str(price["output"]))) / Decimal(1_000_000)
            self.spent += cost
        self.calls += 1
        append_json(self.ledger, {"qid": getattr(self.local, "qid", None), "rep": getattr(self.local, "rep", None),
                                 "turn": getattr(self.local, "turn", 0), "call": self.calls,
                                 "at": datetime.now(R.BEIJING).isoformat(), "usage": usage,
                                 "system_fingerprint": reply.system_fingerprint,
                                 "raw_sha256": R.sha256(reply.raw), "transport_retries": reply.transport_retries,
                                 "cost_cny": str(cost) if cost is not None else None,
                                 "cumulative_cost_cny": str(self.spent), "limit_cny": str(self.limit),
                                 "pricing": "offpeak; all actual requests gated before sending"})
        self.local.turn = getattr(self.local, "turn", 0) + 1
        super().check_reply(reply)
        if cost is None:
            self.stop("usage missing/invalid: cannot establish spend; stop before further requests")
        if self.spent > self.limit:
            self.stop(f"unit budget exceeded on returned response: {self.spent} CNY > {self.limit} CNY")

    def attempt(self, ctx, question, rep):
        # Wait before run_attempt stamps started_at / its pricing period.
        try:
            self.before_request()
        except R.RunStopped as exc:
            return {"run_id": ctx.run_id, "cell": ctx.cell.name, "qid": question.qid, "rep": rep,
                    "status": "stopped", "error": str(exc), "turns": []}
        self.local.qid, self.local.rep, self.local.turn = question.qid, rep, 0
        result = R.run_attempt(ctx, question, rep)
        if result["status"] != "done" and not self.stopped.is_set():
            self.reason = f"attempt did not finish: {question.qid} r{rep}, {result['status']}"
            self.stopped.set()
        return result


class JsonBoundary(BudgetBoundary):
    """User-approved JSON gate: covered execution errors and infrastructure only."""
    def __init__(self, ledger, covered):
        super().__init__(ledger)
        self.covered = frozenset(covered)
        self.covered_done = 0
        self.covered_errors = 0

    def check_reply(self, reply):
        super().check_reply(reply)
        if self.stopped.is_set():
            raise R.RunStopped(self.reason)

    def check_execution(self, result):
        if result.error_class in ("timeout", "transport_error"):
            with self.account_lock:
                self.reason = f"Cube infrastructure error: {result.error_class}; stop immediately"
                self.stopped.set()
                append_json(self.ledger.parent / "events.jsonl", {"event": "json_infrastructure_stop",
                            "at": datetime.now(R.BEIJING).isoformat(), "reason": self.reason})

    def attempt(self, ctx, question, rep):
        result = super().attempt(ctx, question, rep)
        if result["status"] == "done" and question.qid in self.covered:
            with self.account_lock:
                self.covered_done += 1
                self.covered_errors += result["final"]["outcome"] == "exec_error"
                if self.covered_errors * 5 > self.covered_done:
                    self.reason = f"JSON covered execution error rate exceeds 20%: {self.covered_errors}/{self.covered_done}"
                    self.stopped.set()
                    append_json(self.ledger.parent / "events.jsonl", {"event": "json_covered_stop",
                                "at": datetime.now(R.BEIJING).isoformat(), "reason": self.reason,
                                "covered_done": self.covered_done, "covered_errors": self.covered_errors})
        return result


class JsonExecutionGate:
    def __init__(self, executor, boundary):
        self.executor = executor
        self.boundary = boundary

    def execute(self, query):
        if self.boundary.stopped.is_set():
            raise R.RunStopped(self.boundary.reason)
        result = self.executor.execute(query)
        # Return the outcome so run_direct saves its complete raw error before
        # the stopped call boundary blocks a correction request.
        self.boundary.check_execution(result)
        return result


def configured_cells():
    path = Path(os.environ["SEMDEBT_DATA_DIR"]) / "dry-runs/T16-semantic-v1.4-234ad68/cube_sql.semantic-v1.2.md"
    expected = subprocess.check_output(["git", "show", "semantic-v1.2:render/syntax/cube_sql.md"], cwd=ROOT)
    assert path.read_bytes() == expected
    old = replace(C.CELLS["SQL-L2"], name="SQL-L2-notes-v12", syntax=str(path))
    return [C.CELLS["SQL-L2"], old, C.CELLS["JSON-L2"]]


def preflight(cells):
    assert os.environ.get("DEEPSEEK_API_KEY"), "DEEPSEEK_API_KEY is not available"
    assert verify_eval_tag("eval-v1.2") == "90e13b385a639a9164ac78430c50c11a7859f976"
    assert verify_semantic_tag("semantic-v1.4", ["SQL-L2.yaml", "JSON-L2.yaml"], root=ROOT, contexts_dir=C.CONTEXTS) == "234ad684f69a9a632a78f1ab2079b4ebf5f789d1"
    approved = json.loads((ROOT / "reports/validation/t16-v14-full-dry-run/estimates.json").read_text())
    for cell, spec in zip(cells, approved["cells"]):
        assert cell.name == spec["cell"] and R.sha256(R.system_for(cell)) == spec["system_message_sha256"]
    for file in ("harness/prompt.py", "harness/scorer.py", "harness/scorer_v2.py", "harness/score_guard.py"):
        assert (ROOT / file).read_bytes() == subprocess.check_output(["git", "show", "harness-v1.1:" + file], cwd=ROOT)
    models = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "build/cube/model/cubes").glob("*.yml")}
    assert models == approved["cube"]["model_sha256"]
    container = subprocess.check_output(["docker", "compose", "ps", "-q", "cube"], cwd=ROOT, text=True).strip()
    mounts = json.loads(subprocess.check_output(["docker", "inspect", "--format", "{{json .Mounts}}", container], text=True))
    assert Path(next(m["Source"] for m in mounts if m["Destination"] == "/cube/conf/model")).resolve() == (ROOT / "build/cube/model").resolve()
    with urllib.request.urlopen("http://127.0.0.1:14000/cubejs-api/v1/meta", timeout=60) as response:
        assert response.status == 200 and len(json.load(response)["cubes"]) == 25
    questions = R.questions_for(cells[0], load_questions(), skip_judge=True)
    assert len(questions) == 109 and not R.invalid_rules(questions)
    return questions


def index_row(run_id, cell, started, cost, reason, count=327):
    path = ROOT / "runs/INDEX.md"
    assert f"| {run_id} |" not in path.read_text()
    with path.open("a", encoding="utf-8") as out:
        out.write(f"| {run_id} | {started[:10]} | {cell} | T16 | {count}条作答（跳过judge） | deepseek-flash，指纹e72d3c7f… | eval-v1.2=90e13b3；semantic-v1.4=234ad68 | {cost} | $SEMDEBT_DATA_DIR/runs-raw/{run_id} | {reason} |\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="execute the explicitly approved batch")
    parser.add_argument("--unit", choices=("new", "old", "json"), help="run one unit; review its summary before the next")
    parser.add_argument("--concurrency", type=int, choices=(1, 4), default=1)
    args = parser.parse_args()
    if not args.execute:
        parser.error("actual batch requires --execute; use dry_run_t16_v14 for estimates")
    cells = configured_cells()
    questions = preflight(cells)
    run_ids = ["20261019-T16-full-v14-sql-new-01", "20261019-T16-full-v14-sql-old-01", "20261019-T16-full-v14-json-01"]
    selected = {"new": 0, "old": 1, "json": 2}
    units = list(zip(run_ids, cells))
    if args.unit:
        units = [units[selected[args.unit]]]
    assert all(not (ROOT / "runs" / run).exists() or not any((ROOT / "runs" / run).iterdir()) for run, _ in units)
    run_commit = R.harness_commit()
    assert "dirty" not in run_commit
    C.CELLS[cells[1].name] = cells[1]  # Process-local identity for later offline scoring.
    total = Decimal("0")
    for run_id, cell in units:
        questions = preflight(cells)
        directory = ROOT / "runs" / run_id
        directory.mkdir(parents=True, exist_ok=True)
        started = datetime.now(R.BEIJING).isoformat(timespec="seconds")
        manifest = {"run_id": run_id, "cell": cell.name, "runner_commit": run_commit,
                    "eval_tag": "eval-v1.2", "semantic_tag": "semantic-v1.4", "harness_protocol": "harness-v1.1",
                    "syntax_tag": "semantic-v1.2" if cell.name == cells[1].name else "semantic-v1.4",
                    "syntax_sha256": R.sha256(C.syntax_path(cell.syntax).read_bytes()), "system_sha256": R.sha256(R.system_for(cell)),
                    "context_sha256": R.sha256(R.context_text(cell)), "coverage_commit": "381ed1d",
                    "started_at": started, "questions": 109, "reps": 3, "concurrency": args.concurrency,
                    "authorized_unit_limit_cny": 10, "authorized_batch_limit_cny": 30,
                    "authorization": "用户批准三个单元各10元、合计30元；T15排在本批之后；仅错峰；单元串行；后续单元可并发4",
                    "request_config": "unchanged DeepSeekClient defaults; 3000 tokens was an estimate, not an output cap"}
        with (directory / "manifest.json").open("x") as out:
            json.dump(manifest, out, ensure_ascii=False, indent=2)
        executor = R.make_executor(cell, 120)
        if cell.name == "JSON-L2":
            registry_path = "reports/validation/t16-v14-8836110/coverage.json"
            registry_bytes = (ROOT / registry_path).read_bytes()
            assert registry_bytes == subprocess.check_output(["git", "show", "381ed1d:" + registry_path], cwd=ROOT)
            covered = {r["qid"] for r in json.loads(registry_bytes)["rows"] if r["category"] == "covered"}
            assert len(covered) == 39
            boundary = JsonBoundary(directory / "budget.jsonl", covered)
            executor = JsonExecutionGate(executor, boundary)
            append_json(directory / "events.jsonl", {"event": "json_gate_authorized", "at": started,
                        "covered_questions": 39, "covered_attempts_planned": 117,
                        "rule": "已完成能答题作答的执行失败率>20%停；任何Cube超时/连接错误即停；其余拒答与失败不触发SQL检查点"})
        else:
            boundary = BudgetBoundary(directory / "budget.jsonl")
        client = DeepSeekClient(MODEL, before_request=boundary.before_request)
        context = R.RunContext(run_id=run_id, cell=cell, client=client, executor=executor,
                               system=R.system_for(cell), eval_commit="90e13b385a639a9164ac78430c50c11a7859f976",
                               harness_commit=run_commit, timeout_s=120, raw_dir=R.raw_root() / run_id / cell.name,
                               limits={"max_result_rows": R.DEFAULT_MAX_RESULT_ROWS, "max_memory_bytes": R.DEFAULT_MAX_MEMORY_BYTES},
                               eval_tag="eval-v1.2", semantic_tag="semantic-v1.4", boundary=boundary)
        print(f"START {run_id} cell={cell.name} commit={run_commit} unit_limit=10 CNY", flush=True)
        try:
            path = R.run_cell(context, questions, 3, args.concurrency, guard=R.FingerprintGuard(), attempt=boundary.attempt)
            records = [json.loads(s) for s in path.read_text().splitlines()]
            complete = len(records) == 327 and all(r["status"] == "done" for r in records)
            complete = complete and {(r["qid"], r["rep"]) for r in records} == {(q.qid, n) for q in questions for n in (1, 2, 3)}
            append_json(directory / "events.jsonl", {"event": "complete" if complete else "stopped", "at": datetime.now(R.BEIJING).isoformat(),
                                                      "cost_cny": str(boundary.spent), "response_calls": boundary.calls, "reason": boundary.reason})
        finally:
            index_row(run_id, cell.name, started, str(boundary.spent),
                      f"用户已批准单元10元/总30元；新run；并发{args.concurrency}（用户批准后续单元提至4），错峰，单元串行；运行提交{run_commit}；说明{manifest['syntax_tag']}；逐次计费闸；单元后审查；实际状态见events.jsonl")
        total += boundary.spent
        print(f"END {run_id} complete={complete} calls={boundary.calls} cost={boundary.spent} batch_cost={total}", flush=True)
        if not complete or boundary.stopped.is_set() or boundary.spent > Decimal("10") or total > Decimal("30"):
            print("STOP ALL: " + (boundary.reason or "incomplete unit"), flush=True)
            return 3
    print(f"ALL MODEL UNITS COMPLETE; total_cost={total}; offline rescore and audit still required", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
