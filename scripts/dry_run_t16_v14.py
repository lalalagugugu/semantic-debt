"""Estimate the three T16 cells. There is deliberately no real-run entry point.

The old-note control changes only an in-memory Cell's syntax source; the
semantic tag, context, system-message template and scorer remain unchanged.
"""
import contextlib
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import urllib.request

from harness import cells as C
from harness import prompt as P
from harness import run_direct as R
from harness.questions import load_questions, verify_eval_tag
from harness.semantic_version import verify_semantic_tag

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/validation/t16-v14-full-dry-run"
FINGERPRINT = "e72d3c7f663d3e1383b00b3884cb4501"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def main():
    assert not os.environ.get("DEEPSEEK_API_KEY"), "unset model key: dry-run only"
    if OUT.exists():
        raise RuntimeError("refusing to overwrite prior estimates")
    sem = verify_semantic_tag("semantic-v1.4", ["SQL-L2.yaml", "JSON-L2.yaml"], root=ROOT, contexts_dir=C.CONTEXTS)
    assert sem == git("rev-parse", "234ad68^{commit}").decode().strip()
    eval_commit = verify_eval_tag("eval-v1.2")
    assert eval_commit == "90e13b385a639a9164ac78430c50c11a7859f976"
    frozen = {}
    for name in ("harness/prompt.py", "harness/scorer.py", "harness/scorer_v2.py", "harness/score_guard.py"):
        actual = (ROOT / name).read_bytes()
        assert actual == git("show", "harness-v1.1:" + name), name
        frozen[name] = digest(actual)
    coverage_name = "reports/validation/t16-v14-8836110/coverage.json"
    coverage_bytes = (ROOT / coverage_name).read_bytes()
    assert coverage_bytes == git("show", "381ed1d:" + coverage_name)
    coverage = json.loads(coverage_bytes)
    model_files = {p.name: digest(p.read_bytes()) for p in (ROOT / "build/cube/model/cubes").glob("*.yml")}
    assert model_files == coverage["model_sha256"]
    assert digest((C.CONTEXTS / "JSON-L2.yaml").read_bytes()) == coverage["context_sha256"]
    container = subprocess.check_output(["docker", "compose", "ps", "-q", "cube"], cwd=ROOT, text=True).strip()
    mounts = json.loads(subprocess.check_output(["docker", "inspect", "--format", "{{json .Mounts}}", container], text=True))
    mounted = Path(next(m["Source"] for m in mounts if m["Destination"] == "/cube/conf/model"))
    assert mounted.resolve() == (ROOT / "build/cube/model").resolve()
    with urllib.request.urlopen("http://127.0.0.1:14000/cubejs-api/v1/meta", timeout=60) as response:
        assert response.status == 200
        meta_bytes = response.read()
    assert len(json.loads(meta_bytes)["cubes"]) == 25
    private = Path(os.environ["SEMDEBT_DATA_DIR"]) / "dry-runs/T16-semantic-v1.4-234ad68"
    private.mkdir(parents=True, exist_ok=False)
    old_note = git("show", "semantic-v1.2:render/syntax/cube_sql.md")
    old_path = private / "cube_sql.semantic-v1.2.md"
    old_path.write_bytes(old_note)
    old_path.chmod(0o444)
    assert old_path.read_bytes() == old_note
    old_cell = replace(C.CELLS["SQL-L2"], name="SQL-L2-notes-v12", syntax=str(old_path))
    cells = [C.CELLS["SQL-L2"], old_cell, C.CELLS["JSON-L2"]]
    assert R.context_text(cells[0]) == R.context_text(old_cell)
    assert R.system_for(old_cell) == P.system_message(R.context_text(cells[0]), old_note.decode(), "yaml")
    assert R.system_for(cells[0]) != R.system_for(old_cell)
    all_questions = load_questions()
    selected = {c.name: R.questions_for(c, all_questions, skip_judge=True) for c in cells}
    assert len(all_questions) == 122 and all(len(qs) == 109 for qs in selected.values())
    assert all({q.qid for q in qs} == {r["qid"] for r in coverage["rows"]} for qs in selected.values())
    OUT.mkdir(parents=True)
    rows = []
    C.LADDER_CELLS[old_cell.name] = old_cell  # Process-local dry-run registration only.
    try:
        for cell in cells:
            args = ["--cell", cell.name, "--eval-tag", "eval-v1.2", "--semantic-tag", "semantic-v1.4",
                    "--skip-judge", "--reps", "3", "--model", "deepseek-flash", "--concurrency", "1",
                    "--expected-fingerprint", FINGERPRINT, "--est-from-args", "--est-fix-rate", "0.10",
                    "--est-output-tokens", "3000", "--est-hit-ratio", "0.95", "--dry-run"]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = R.main(args)
            (OUT / (cell.name + ".txt")).write_text(output.getvalue())
            print(output.getvalue(), end="", flush=True)
            assert status == 0
            estimate, _ = R.dry_run([cell], {cell.name: 109}, 3, "deepseek-flash", fix_rate=0.10,
                                    output_tokens=3000, hit_ratio=0.95, question_tokens=60, use_measured=False)
            row = estimate[0]
            row.update(argv=args, context_sha256=digest(R.context_text(cell).encode()),
                       syntax_sha256=digest(C.syntax_path(cell.syntax).read_bytes()),
                       syntax_tag="semantic-v1.2" if cell is old_cell else "semantic-v1.4",
                       system_message_sha256=digest(R.system_for(cell).encode()))
            rows.append(row)
        sensitivity = {}
        for rate in (0.0, 1.0):
            estimates, total = R.dry_run(cells, {c.name: 109 for c in cells}, 3, "deepseek-flash", fix_rate=rate,
                                        output_tokens=3000, hit_ratio=0.95, question_tokens=60, use_measured=False)
            sensitivity[str(rate)] = {"cells": estimates, "total_cost_offpeak": total}
    finally:
        C.LADDER_CELLS.pop(old_cell.name)
    manifest = {"model_calls": 0, "model": "deepseek-flash", "expected_fingerprint": FINGERPRINT,
                "eval_tag": "eval-v1.2", "eval_commit": eval_commit, "semantic_tag": "semantic-v1.4", "semantic_commit": sem,
                "harness_protocol_tag": "harness-v1.1", "harness_protocol_commit": git("rev-parse", "harness-v1.1^{commit}").decode().strip(),
                "runner_commit": git("rev-parse", "HEAD").decode().strip(), "frozen_harness_sha256": frozen,
                "cube": {"model_mount_verified": True, "meta_status": 200, "cube_count": 25,
                         "meta_sha256": digest(meta_bytes), "model_sha256": model_files,
                         "byte_identical_to_registry_381ed1d": True},
                "coverage_commit": "381ed1d", "coverage_sha256": digest(coverage_bytes),
                "assumptions": {"fix_rate": 0.10, "output_tokens_per_call": 3000, "cache_hit_ratio": 0.95,
                                "question_tokens": 60, "prices_cny_per_million_tokens": C.PRICES_OFFPEAK["deepseek-flash"],
                                "cost_basis": "harness locked off-peak prices; context-aware estimate, not a live price quote"},
                "cells": rows, "total_cost_offpeak": sum(r["cost_offpeak"] for r in rows),
                "total_attempts": sum(r["attempts"] for r in rows), "total_estimated_calls": sum(r["calls"] for r in rows),
                "sensitivity": sensitivity, "execution_authorized": False,
                "coordination": "No model batches started. T15 L2-E and T16 share Cube; coordinator schedules serial execution."}
    (OUT / "estimates.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("Three-cell off-peak total:", format(manifest["total_cost_offpeak"], ".8f"), "CNY")


if __name__ == "__main__":
    main()
