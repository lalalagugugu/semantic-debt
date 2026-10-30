"""T29 continuation U2: fixed 98 x 3 x 2 cells x 2 arms, approval-gated paid entry."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness import executors, run_direct as R
from harness.cells import CELLS, U2_CELLS, PRICES_OFFPEAK
from harness.questions import load_questions, verify_eval_tag
from harness.semantic_version import verify_semantic_tag
from harness.spend import ConcurrentSpendGuard

TAG = "harness-u2-v1"
SEMANTIC = "semantic-v1.2"
EVAL = "eval-v1.3"
BASELINE_RUN = "20261018-T13-sql-direct-01"
BUDGET = 30
MODEL = "deepseek-flash"
FINGERPRINT = "e72d3c7f663d3e1383b00b3884cb4501"
PREFLIGHT = Path("reports/validation/t29-u2-preflight.json")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def scope(questions):
    selected = R.questions_for(U2_CELLS["SQL-L0-u2"], questions)
    assert len(selected) == 98 and len({q.qid for q in selected}) == 98
    assert {q.meta["split"]: sum(v.meta["split"] == q.meta["split"] for v in selected)
            for q in selected} == {"tuning": 49, "heldout": 49}
    return sorted(selected, key=lambda q: int(q.qid[1:]))


def build_preflight(questions):
    selected = scope(questions)
    by_id = {q.qid: q for q in selected}
    confidence_source = ROOT / "reports/validation/t29-expanded-audit.json"
    previous_confidence_mean = json.loads(confidence_source.read_text())["mean_output_tokens"]
    sources = {str(confidence_source.relative_to(ROOT)): sha(confidence_source.read_bytes())}
    rows, baseline_hashes, treatment_hashes = [], {}, {}
    max_prompt, max_output, max_delta = 0, 0, 0
    price = PRICES_OFFPEAK[MODEL]
    for name, cell in U2_CELLS.items():
        base = name.rsplit("-", 1)[0]
        source = ROOT / "runs" / BASELINE_RUN / f"{base}.jsonl"
        content = source.read_bytes()
        sources[str(source.relative_to(ROOT))] = sha(content)
        records = [r for r in map(json.loads, content.splitlines())
                   if r.get("status") == "done" and r.get("qid") in by_id]
        assert len(records) == 294 and {(r["qid"], r["rep"]) for r in records} == {
            (q, rep) for q in by_id for rep in (1, 2, 3)}
        base_system, system = R.system_for(CELLS[base]), R.system_for(cell)
        baseline_hashes[base], treatment_hashes[name] = sha(base_system.encode()), sha(system.encode())
        assert all(r["system_sha256"] == baseline_hashes[base] and r["semantic_tag"] == SEMANTIC
                   and r["question_sha256"] == sha(by_id[r["qid"]].text.encode()) for r in records)
        turns = [t for r in records for t in r["turns"]]
        assert all(len(r["turns"]) in (1, 2) for r in records)
        prompt_mean = sum(t["usage"]["prompt_tokens"] for t in turns)/len(turns)
        output_mean = sum(t["usage"]["completion_tokens"] for t in turns)/len(turns)
        hit_ratio = sum(t["usage"]["cache_hit_tokens"] for t in turns)/sum(t["usage"]["prompt_tokens"] for t in turns)
        delta = max(0, R.estimate_tokens_from_text(system)-R.estimate_tokens_from_text(base_system))
        # Historical answer complexity plus observed T29 confidence complexity;
        # 64 output tokens explicitly reserve the extra confidence line.
        output = math.ceil(max(output_mean, previous_confidence_mean))+64
        prompt = max(math.ceil(prompt_mean)+delta, R.estimate_tokens_from_text(system)+60)
        estimated_calls = len(turns)
        per_call = (prompt*(hit_ratio*price["hit"]+(1-hit_ratio)*price["miss"])+output*price["output"])/1e6
        cold = prompt*hit_ratio*(price["miss"]-price["hit"])/1e6
        rows.append(dict(cell=name, baseline_cell=base, arm="penalty_k10" if cell.selective_k == 10 else "no_penalty",
                         questions=98, reps=3, first_calls=294,
                         estimated_calls=estimated_calls, maximum_calls_one_fix_each=588,
                         observed_fix_rate=(len(turns)-294)/294,
                         observed_mean_output_tokens=output_mean, estimated_output_tokens=output,
                         estimated_prompt_tokens=prompt, observed_cache_hit_ratio=hit_ratio,
                         extra_cold_prefix_allowance_cny=cold,
                         estimated_cost_cny=per_call*estimated_calls+cold,
                         all_fixed_once_cost_cny=per_call*588+cold))
        max_prompt = max(max_prompt, max(t["usage"]["prompt_tokens"] for t in turns))
        max_output = max(max_output, max(t["usage"]["completion_tokens"] for t in turns))
        max_delta = max(max_delta, delta)
    maximum_output = max_output+64
    maximum_input = max_prompt+maximum_output+2000+max_delta
    max_cost = (maximum_input*price["miss"]+maximum_output*price["output"])/1e6
    return dict(task="T29 continuation U2", status="dry-run; user approved 30 CNY and outbound; awaiting merge and user harness tag",
                model=MODEL, expected_fingerprint=FINGERPRINT, proposed_harness_tag=TAG,
                semantic_tag=SEMANTIC, eval_tag=EVAL, baseline_run=BASELINE_RUN,
                qids=[q.qid for q in selected], questions=98, reps=3, cells=list(U2_CELLS),
                first_calls=1176, estimated_calls=sum(r["estimated_calls"] for r in rows),
                maximum_calls_one_fix_each=2352, budget_ceiling_cny=BUDGET, concurrency=8,
                estimated_cost_cny=sum(r["estimated_cost_cny"] for r in rows),
                all_fixed_once_cost_cny=sum(r["all_fixed_once_cost_cny"] for r in rows),
                prices_offpeak_cny_per_million=price,
                estimate_method="Both arms use each base cell's original 98x3 usage/fix rate, with no assumed penalty savings; output=max(baseline mean,T29 C mean)+64; include each arm's prompt delta and one extra cold prefix per cell.",
                max_input_tokens_estimate=maximum_input, max_output_tokens_estimate=maximum_output,
                max_call_cost_cny=max_cost,
                spend_note="Admission reserves each in-flight request; total stays within 30 CNY if individual actual costs do not exceed the estimate. An over-estimate or unknown bill stops new requests; admitted calls settle and raw responses are retained.",
                d4_free_baselines=["SQL-L0", "SQL-L1"], d4_extra_api_calls=0,
                d1_dependency="Collection may precede D1; analysis requires completed D1 full baseline labels and treatment content labels, never v2 or sampled extrapolation.",
                baseline_system_sha256=baseline_hashes, treatment_system_sha256=treatment_hashes,
                source_sha256=sources, rows=rows)


def verify_harness():
    tagged = subprocess.run(["git", "rev-parse", "--verify", f"{TAG}^{{commit}}"], cwd=ROOT, check=True, capture_output=True, text=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != tagged.stdout.strip():
        raise ValueError("paid collection must use a checkout of the user-tagged harness commit")
    paths = ["harness", "scripts/t29_u2.py", str(PREFLIGHT)]
    subprocess.run(["git", "diff", "--exit-code", TAG, "--", *paths], cwd=ROOT, check=True)
    extra = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--", *paths], cwd=ROOT)
    if extra.strip():
        raise ValueError("untracked harness source")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run-id")
    ap.add_argument("--execute-approved", action="store_true", help="only after explicit user budget/outbound approval")
    ap.add_argument("--approved-preflight-sha256")
    args = ap.parse_args(argv)
    if not args.dry_run and not (args.execute_approved and args.run_id and args.approved_preflight_sha256):
        ap.error("paid collection needs user approval, --execute-approved, --run-id and --approved-preflight-sha256")
    if args.run_id and (Path(args.run_id).name != args.run_id or args.run_id in (".", "..")):
        ap.error("invalid run id")
    verify_eval_tag(EVAL)
    verify_semantic_tag(SEMANTIC, ["SQL-L0.yaml", "SQL-L1.yaml"], root=ROOT, contexts_dir=R.CONTEXTS)
    questions = load_questions(lang="zh")
    pre = build_preflight(questions)
    print(json.dumps(pre, ensure_ascii=False, indent=2))
    if pre["estimated_cost_cny"] > BUDGET:
        print(f"STOP: combined estimate exceeds the {BUDGET} CNY design ceiling; ask user")
        return 2
    if args.dry_run:
        return 0
    verify_harness()
    reviewed = (ROOT / PREFLIGHT).read_bytes()
    if sha(reviewed) != args.approved_preflight_sha256 or json.loads(reviewed) != pre:
        raise ValueError("current preflight differs from the user-reviewed file")
    if R.is_peak():
        print("STOP: peak hours; no new API requests")
        return 2
    data = Path(os.environ["SEMDEBT_DATA_DIR"])
    if not ROOT.resolve().is_relative_to(data.resolve()):
        raise ValueError("paid U2 collection requires a tagged runtime checkout under SEMDEBT_DATA_DIR so detailed logs stay private")
    guard = ConcurrentSpendGuard(data / "runs-raw" / args.run_id / "spend-ledger.jsonl", BUDGET, MODEL, pre["max_call_cost_cny"])
    if guard.reached:
        print("STOP: saved admission ledger is closed")
        return 3
    copy = data / "chdb-t29"
    if not copy.is_dir():
        raise ValueError("missing independent T29 chDB copy")
    executors.default_chdb_path = lambda: str(copy)
    # Both prechecks and collection use the existing one-session-per-path registry.
    for name, table in (("SQL-L0-u2", "l0.fct_ol_sls"), ("SQL-L1-u2", "retail.FactOnlineSales")):
        result = R.make_executor(U2_CELLS[name], R.DEFAULT_EXEC_TIMEOUT_S).execute(f"SELECT 1 FROM {table} LIMIT 1")
        if not result.ok:
            raise ValueError("database precheck failed; build the frozen L0 views on the private copy before paid collection")
    common = ["--run-id", args.run_id, "--model", MODEL, "--reps", "3", "--concurrency", "8",
              "--budget", str(BUDGET), "--max-call-cost", str(pre["max_call_cost_cny"]),
              "--semantic-tag", SEMANTIC, "--eval-tag", EVAL, "--skip-judge", "--est-from-args",
              "--questions", ",".join(pre["qids"]), "--expected-fingerprint", FINGERPRINT]
    for row in pre["rows"]:
        result = R.main(common+["--cell", row["cell"], "--est-fix-rate", str(row["observed_fix_rate"]),
                               "--est-output-tokens", str(row["estimated_output_tokens"]),
                               "--est-hit-ratio", str(row["observed_cache_hit_ratio"])])
        if result:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
