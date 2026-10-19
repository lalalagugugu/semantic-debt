"""Offline-only integrity audit, v2 rescore and ID-only T16 results."""
import argparse
from collections import Counter
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess

from harness import cells as C
from harness import run_direct as R
from harness.questions import load_questions, verify_eval_tag
from harness.rescore import rescore
from scripts.run_t16_v14_full import FP, index_row

ROOT = Path(__file__).resolve().parents[1]
UNITS = [("20261019-T16-full-v14-sql-new-01", "SQL-L2"),
         ("20261019-T16-full-v14-sql-old-01", "SQL-L2-notes-v12"),
         ("20261019-T16-full-v14-json-01", "JSON-L2")]


def read_lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()] if path.exists() else []


def counts(rows):
    result = dict(Counter(r["final"]["outcome"] for r in rows))
    scored = sum(n for key, n in result.items() if key not in ("pending", "unscored"))
    return {"attempts": len(rows), "outcomes": result, "scored_denominator": scored,
            "accuracy_on_scored": result.get("correct", 0) / scored if scored else None}


def query_members(query):
    """Members used as values, filter/time members, or ordering keys."""
    payload = json.loads(query)
    members = set(payload.get("measures", []) + payload.get("dimensions", []) + payload.get("segments", []))

    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("member", "dimension") and isinstance(item, str):
                    members.add(item)
                elif key in ("and", "or"):
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload.get("filters", []))
    visit(payload.get("timeDimensions", []))
    order = payload.get("order", {})
    members.update(order if isinstance(order, dict) else (item[0] for item in order))
    return sorted(members)


def error_family(execution):
    """Describe the observed error layer, without inferring business coverage."""
    kind = execution.get("error_class")
    message = execution.get("detail") or execution.get("error", "")
    if kind in ("timeout", "transport_error", "resource_limit", "no_query", "scope_violation"):
        return kind
    if message.startswith("Rewrite Error:"):
        return "cube_rewrite"
    if "Can't find join path" in message:
        return "cube_join_path"
    if "Type UInt64 is not supported in response transformation" in message:
        return "cube_response_type"
    if "not supported for scalar operation" in message:
        return "cube_postprocessing_type"
    if "Can't generate SQL" in message:
        return "cube_sql_generation"
    if "Query failed: Error: Syntax error" in message:
        return "cube_generated_clickhouse_syntax"
    if message.startswith("Planning Error:"):
        return "cube_planning"
    if "Aggregate function with name" in message and "does not exist" in message:
        return "backend_function_not_supported"
    if "Max query size exceeded" in message:
        return "cube_generated_query_size"
    if "not under aggregate function and not in GROUP BY keys" in message:
        return "cube_generated_group_by"
    if "Invalid member expression format" in message:
        return "cube_member_expression"
    return kind or "unclassified"


def runtime_snapshot(rows):
    done = [r for r in rows if r["status"] == "done"]
    turns = [t["exec"] for r in done for t in r["turns"]]
    final_errors = [r for r in done if r["final"]["outcome"] == "exec_error"]
    return {"done": len(done), "outcomes": dict(Counter(r["final"]["outcome"] for r in done)),
            "mean_model_seconds_per_answer": sum(r["latency_s"] for r in done) / len(done),
            "mean_cube_seconds_per_answer": sum(t.get("elapsed_s", 0) for t in turns) / len(done),
            "final_error_families": dict(Counter(error_family(r["turns"][-1]["exec"]) for r in final_errors)),
            "all_turn_error_families": dict(Counter(error_family(t) for t in turns if t["status"] == "error")),
            "final_error_cases": [{"qid": r["qid"], "rep": r["rep"], "family": error_family(r["turns"][-1]["exec"])} for r in final_errors]}


def progress():
    rows = []
    for run, cell in UNITS:
        directory = ROOT / "runs" / run
        logs = read_lines(directory / (cell + ".jsonl"))
        ledger = read_lines(directory / "budget.jsonl")
        rows.append({"run_id": run, "cell": cell, "logged": len(logs), "done": sum(r["status"] == "done" for r in logs),
                     "responses": len(ledger), "cost_cny": ledger[-1]["cumulative_cost_cny"] if ledger else "0",
                     "fingerprints": sorted({str(r["system_fingerprint"]) for r in ledger}),
                     "events": read_lines(directory / "events.jsonl")[-1:]})
    print(json.dumps(rows, ensure_ascii=False, indent=2), flush=True)


def main():
    assert not os.environ.get("DEEPSEEK_API_KEY"), "remove model key: offline report only"
    parser = argparse.ArgumentParser()
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--rescore", action="store_true", help="after all model units finish, run frozen v2 offline")
    parser.add_argument("--unit", choices=("new", "old", "json"), help="audit one completed unit while the batch is paused")
    args = parser.parse_args()
    if args.progress:
        progress()
        return
    assert args.rescore, "use --progress or --rescore"
    units = [UNITS[{"new": 0, "old": 1, "json": 2}[args.unit]]] if args.unit else UNITS
    eval_commit = verify_eval_tag("eval-v1.2")
    questions = {q.qid: q for q in load_questions() if q.scoring != "judge"}
    expected = {(qid, rep) for qid in questions for rep in (1, 2, 3)}
    registry_file = ROOT / "reports/validation/t16-v14-8836110/coverage.json"
    registry_bytes = registry_file.read_bytes()
    assert registry_bytes == subprocess.check_output(["git", "show", "381ed1d:" + str(registry_file.relative_to(ROOT))], cwd=ROOT)
    registry = {r["qid"]: r for r in json.loads(registry_bytes)["rows"]}
    assert len(questions) == len(registry) == 109
    for path in ("harness/prompt.py", "harness/scorer.py", "harness/scorer_v2.py", "harness/score_guard.py"):
        assert (ROOT / path).read_bytes() == subprocess.check_output(["git", "show", "harness-v1.1:" + path], cwd=ROOT)
    C.CELLS["SQL-L2-notes-v12"] = replace(C.CELLS["SQL-L2"], name="SQL-L2-notes-v12")
    raw_root = Path(os.environ["SEMDEBT_DATA_DIR"]) / "runs-raw"
    sources = {}
    integrity = {}
    # Validate every source before starting any offline work.
    for run, cell in units:
        directory = ROOT / "runs" / run
        rows = read_lines(directory / (cell + ".jsonl"))
        ledger = read_lines(directory / "budget.jsonl")
        assert len(rows) == 327 and {(r["qid"], r["rep"]) for r in rows} == expected
        assert all(r["status"] == "done" and r["scoring"] == "deterministic" and r["peak"] is False for r in rows)
        assert all(r["system_fingerprint"] == FP and r["cost_cny"] is not None for r in ledger)
        assert len(ledger) == sum(len(r["turns"]) for r in rows)
        money = sum(Decimal(r["cost_cny"]) for r in ledger)
        assert money <= 10 and money == Decimal(ledger[-1]["cumulative_cost_cny"])
        billing = {(r["qid"], r["rep"], r["turn"]): r for r in ledger}
        executions = 0
        successes = 0
        for record in rows:
            assert record["question_sha256"] == R.sha256(questions[record["qid"]].text)
            for turn in record["turns"]:
                prefix = f"{record['qid']}_r{record['rep']}_t{turn['turn']}"
                raw = raw_root / run / cell / (prefix + ".json")
                assert R.sha256(raw.read_bytes()) == turn["raw_sha256"] == billing[(record["qid"], record["rep"], turn["turn"])]["raw_sha256"]
                if turn["exec"].get("exec_raw_sha256"):
                    path = raw_root / run / cell / (prefix + ".exec.json")
                    assert R.sha256(path.read_bytes()) == turn["exec"]["exec_raw_sha256"]
                    full = json.loads(path.read_text())
                    executions += 1
                    if turn["exec"]["status"] == "ok":
                        assert len(full["rows"]) == turn["exec"]["row_count"]
                        successes += 1
        sources[cell] = rows
        integrity[cell] = {"run_id": run, "response_calls": len(ledger), "cost_cny": str(money),
                           "transport_retries": sum(r["transport_retries"] for r in ledger),
                           "raw_responses_verified": len(ledger), "exec_files_verified": executions,
                           "successful_full_rowsets_verified": successes,
                           "source_log_sha256": R.sha256((directory / (cell + ".jsonl")).read_bytes()),
                           "manifest": json.loads((directory / "manifest.json").read_text())}
    assert sum(Decimal(r["cost_cny"]) for r in integrity.values()) <= 30
    results = {}
    offline = {}
    for run, cell in units:
        target = run + "-rescore-01"
        destination = R.log_path(target, cell)
        if not destination.exists():
            path = rescore(run, cell, target, questions=questions, commit=eval_commit, eval_tag="eval-v1.2")
            print("RESCORED", target, flush=True)
        rows = read_lines(destination)
        assert len(rows) == 327 and {(r["qid"], r["rep"]) for r in rows} == expected
        assert all(r["rescored_from"]["run_id"] == run and r["cost_cny"] == 0 for r in rows)
        if f"| {target} |" not in (ROOT / "runs/INDEX.md").read_text():
            index_row(target, cell, R.datetime.now(R.BEIJING).isoformat(timespec="seconds"), "0",
                      f"冻结harness-v1.1/v2离线重评；不调用模型、不执行查询；源{run}，原始行集与分数不改写")
        offline[cell] = rows
        primary = [r for r in rows if registry[r["qid"]]["stratum"] == "primary"]
        low = [r for r in rows if registry[r["qid"]]["stratum"] == "low_discrimination"]
        assert len(primary) == 294 and len(low) == 33
        results[cell] = {"source": run, "offline_run": target, "all": counts(rows), "primary": counts(primary), "low_discrimination": counts(low),
                         "runtime_snapshot": runtime_snapshot(sources[cell]),
                         "first_try_correct": sum(r["first"] == "correct" for r in rows),
                         "attempts_repaired_once": sum(r["fixed"] for r in rows),
                         "pending_reasons": dict(Counter(r["final"].get("pending") for r in rows if r["final"]["outcome"] == "pending")),
                         "exec_error_classes": dict(Counter(r["final"].get("error_class") for r in rows if r["final"]["outcome"] == "exec_error"))}
    json_rows = offline.get("JSON-L2", [])
    categories = {}
    cases = []
    for category in ("covered", "a", "b", "c", "d"):
        group = [r for r in json_rows if registry[r["qid"]]["category"] == category]
        categories[category] = counts(group)
        categories[category]["exec_error"] = sum(r["final"]["outcome"] == "exec_error" for r in group)
        categories[category]["refused"] = sum(r["final"]["outcome"] == "refused" for r in group)
        cases.extend({"qid": r["qid"], "rep": r["rep"], "category": category, "outcome": r["final"]["outcome"]}
                     for r in group if r["final"]["outcome"] in ("exec_error", "refused"))
    assert sum(r["attempts"] for r in categories.values()) == len(json_rows)
    paired = {}
    for label, refused in (("json_not_refused_primary", False), ("json_refused_primary", True)):
        pairs = {(r["qid"], r["rep"]) for r in json_rows if registry[r["qid"]]["stratum"] == "primary" and (r["final"]["outcome"] == "refused") == refused}
        paired[label] = {cell: counts([r for r in rows if (r["qid"], r["rep"]) in pairs]) for cell, rows in offline.items()}
    mechanical = []
    for record in json_rows:
        outcome = record["final"]["outcome"]
        if outcome not in ("wrong", "exec_error", "refused"):
            continue
        standard = registry[record["qid"]]["standard_member_set"]
        selected = None
        if outcome == "exec_error":
            cause = "execution_error"
        elif outcome == "refused":
            cause = "refused"
        elif standard is None:
            cause = "outside_static_coverage_no_standard_set"
        else:
            selected = query_members(record["turns"][-1]["query"])
            cause = "different_members" if set(selected) != set(standard) else "same_members_different_result"
        mechanical.append({"qid": record["qid"], "rep": record["rep"], "category": registry[record["qid"]]["category"],
                           "outcome": outcome, "mechanical_cause": cause,
                           "standard_member_set": standard, "selected_member_set": selected})
    output = ROOT / "reports/validation/t16-v14-full-results"
    output.mkdir(exist_ok=True)
    payload = {"eval_tag": "eval-v1.2", "semantic_tag": "semantic-v1.4", "harness_protocol": "harness-v1.1",
               "coverage_commit": "381ed1d", "model_calls_by_this_report": 0,
               "audited_units": [cell for _, cell in units],
               "units_not_in_this_report": [cell for _, cell in UNITS if cell not in offline],
               "not_run_units": [cell for run, cell in UNITS if not read_lines(ROOT / "runs" / run / (cell + ".jsonl"))],
               "integrity": integrity, "results": results, "json_failure_refusal_by_coverage": categories if json_rows else None,
               "json_failure_refusal_cases": cases, "paired": paired if json_rows else None,
               "json_mechanical_error_counts": dict(Counter(r["mechanical_cause"] for r in mechanical)),
               "json_mechanical_error_cases": mechanical,
               "total_cost_cny": str(sum(Decimal(r["cost_cny"]) for r in integrity.values()))}
    filename = f"results-{args.unit}.json" if args.unit else "results.json"
    with (output / filename).open("x") as out:
        json.dump(payload, out, ensure_ascii=False, indent=2)
    print(json.dumps({"results": results, "categories": categories, "total_cost": payload["total_cost_cny"]}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
