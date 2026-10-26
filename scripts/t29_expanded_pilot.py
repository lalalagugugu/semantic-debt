"""Fixed T29 v2 pilot: dry-run first, no paid calls before harness-sel-v2."""
from __future__ import annotations

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
from harness.cells import SELECTIVE_V2_CELLS, PRICES_OFFPEAK
from harness.questions import load_questions, verify_eval_tag
from harness.semantic_version import verify_semantic_tag

TAG = "harness-sel-v2"
SEMANTIC = "semantic-v1.6-l1plus"
SOURCE = "20261025-T29-pilot-01"
AB = tuple(n for n in SELECTIVE_V2_CELLS if n != "SQL-L1plus-confidence")
CONFIDENCE = "SQL-L1plus-confidence"
B = tuple(n for n in AB if "-front-" in n)
A = tuple(n for n in AB if n not in B)
BUDGET = 3


def scopes(questions):
    old = json.loads((ROOT / "reports/validation/t29-pilot-preflight.json").read_text())["pilot_qids"]
    by_id = {q.qid: q for q in questions}
    if len(old) != 20 or any(q not in by_id or by_id[q].meta.get("split") != "tuning" for q in old):
        raise ValueError("original tuning sample differs")
    confidence = R.questions_for(SELECTIVE_V2_CELLS[CONFIDENCE], questions)
    if len(confidence) != 49 or len(set(old) | {q.qid for q in confidence}) != 50:
        raise ValueError("authorized 20/49/50 question scopes differ")
    return old, [q.qid for q in confidence]


def estimate(data, counts):
    ledger = data / "runs-raw" / SOURCE / "spend-ledger.jsonl"
    charges = [json.loads(s) for s in ledger.read_text().splitlines() if json.loads(s)["event"] == "charge"]
    if len(charges) != 54:
        raise ValueError("source pilot ledger differs")
    usage = [r["usage"] for r in charges]
    output = math.ceil(sum(u["completion_tokens"] for u in usage) / len(usage))
    hit = sum(u["cache_hit_tokens"] for u in usage) / sum(u["prompt_tokens"] for u in usage)
    parameters = dict(fix_rate=14/40, output_tokens=output, hit_ratio=hit, question_tokens=60)
    rows, total = R.dry_run(list(SELECTIVE_V2_CELLS.values()), counts, 1, "deepseek-flash",
                            use_measured=False, **parameters)
    if any(r["cost_offpeak"] is None for r in rows):
        raise ValueError("missing rendered context")
    price = PRICES_OFFPEAK["deepseek-flash"]
    # A/C share the original prefix; the two front-loaded B rules each start a new prefix.
    cold = 3 * max(r["prompt_tokens"] for r in rows) * hit * (price["miss"] - price["hit"]) / 1e6
    max_output = max(u["completion_tokens"] for u in usage)
    max_input = max(max(u["prompt_tokens"] for u in usage), max(r["prompt_tokens"] for r in rows))
    # Include a previous maximum response and the bounded execution-error message in a fix.
    max_input += max_output + 2000
    maximum = (max_input * price["miss"] + max_output * price["output"]) / 1e6
    return dict(source_run=SOURCE, source_ledger_sha256=hashlib.sha256(ledger.read_bytes()).hexdigest(),
                parameters=parameters, rows=rows, cold_prefix_allowance_cny=cold,
                expected_cost_cny=total+cold, max_input_tokens_estimate=max_input,
                max_output_tokens_observed=max_output, max_call_cost_cny=maximum,
                note="Admission reserves in-flight costs. Total cost stays within the budget if each actual call cost does not exceed the maximum estimate. A call exceeding the estimate is fully charged and stops new requests.")


def verify_harness():
    subprocess.run(["git", "rev-parse", "--verify", f"{TAG}^{{commit}}"], cwd=ROOT, check=True, capture_output=True)
    paths = ["harness", "scripts/t29_expanded_pilot.py", "reports/validation/t29-pilot-preflight.json",
             "reports/validation/t29-expanded-preflight.json"]
    subprocess.run(["git", "diff", "--exit-code", TAG, "--", *paths], cwd=ROOT, check=True)
    extra = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--", *paths], cwd=ROOT)
    if extra.strip():
        raise ValueError("untracked harness source")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run-id")
    args = ap.parse_args(argv)
    if not args.dry_run and not args.run_id:
        ap.error("--run-id required")
    verify_eval_tag("eval-v1.2")
    verify_semantic_tag(SEMANTIC, ["SQL-L1plus.yaml"], root=ROOT, contexts_dir=R.CONTEXTS)
    questions = load_questions(lang="zh")
    old, confidence = scopes(questions)
    data = Path(os.environ["SEMDEBT_DATA_DIR"])
    info = estimate(data, {**dict.fromkeys(AB, 20), CONFIDENCE: 49})
    preflight = dict(harness_tag=TAG, concurrency=8, budget_cny=BUDGET, attempts=169,
                     execution_order=[CONFIDENCE, *B, *A],
                     authorized_qids=sorted(set(old+confidence)),
                     system_sha256={name: R.sha256(R.system_for(cell)) for name, cell in SELECTIVE_V2_CELLS.items()},
                     **info)
    print(json.dumps(preflight, ensure_ascii=False, indent=2))
    if info["expected_cost_cny"] > BUDGET:
        print(f"STOP: combined estimate exceeds {BUDGET} CNY; ask user")
        return 2
    if args.dry_run:
        return 0
    verify_harness()
    if preflight != json.loads((ROOT / "reports/validation/t29-expanded-preflight.json").read_text()):
        raise ValueError("preflight differs from the reviewed estimate, scopes or system hashes")
    copy = data / "chdb-t29"
    if not copy.is_dir():
        raise ValueError("missing private chDB copy")
    executors.default_chdb_path = lambda: str(copy)
    p = info["parameters"]
    common = ["--run-id", args.run_id, "--model", "deepseek-flash", "--reps", "1", "--concurrency", "8",
              "--budget", str(BUDGET), "--max-call-cost", str(info["max_call_cost_cny"]),
              "--semantic-tag", SEMANTIC, "--skip-judge", "--est-from-args",
              "--est-fix-rate", str(p["fix_rate"]), "--est-output-tokens", str(p["output_tokens"]),
              "--est-hit-ratio", str(p["hit_ratio"]), "--expected-fingerprint", "e72d3c7f663d3e1383b00b3884cb4501"]
    for cells, ids in (((CONFIDENCE,), confidence), (B, old), (A, old)):
        command = common + ["--questions", ",".join(ids)]
        for cell in cells:
            command += ["--cell", cell]
        result = R.main(command)
        if result:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
