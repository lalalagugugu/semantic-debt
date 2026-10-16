"""Mock end-to-end on 5 real questions from the question bank (T11 deliverable):
real loader → mock model → real chDB → T02 scorer → log.

The mock "model" answers with the bank's own reference SQL (correct), a typo then
the reference SQL (fixed once), a wrong constant, a refusal, and the reference SQL
for a question without ``rules`` (pending). No question text or SQL is written
into this file; everything is read from ``$SEMDEBT_EVAL_DIR`` at run time.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness import run_direct as R  # noqa: E402
from harness.cells import CELLS  # noqa: E402
from harness.client import MockClient  # noqa: E402
from harness.questions import load_questions  # noqa: E402

EVAL = Path(os.environ.get("SEMDEBT_EVAL_DIR", "/nonexistent")).expanduser()
CHDB = Path(os.environ.get("SEMDEBT_DATA_DIR", "/nonexistent")).expanduser() / "chdb"
pytestmark = pytest.mark.skipif(not (EVAL / "questions").is_dir() or not CHDB.exists()
                                or not (REPO / "build/contexts/SQL-L1.yaml").exists(),
                                reason="needs the question bank, chDB and rendered contexts")


def _records() -> dict[str, dict]:
    return {r["id"]: r for p in sorted((EVAL / "questions").glob("*.yaml"))
            for r in yaml.safe_load(p.read_text(encoding="utf-8"))["questions"]}


def _pick() -> dict[str, str]:
    """Deterministic choice: three scorable questions and one without rules, each
    with a single plain reference (no postprocess)."""
    recs = _records()
    plain = [q for q in sorted(recs) if len(recs[q]["refs"]) == 1 and "postprocess" not in recs[q]["refs"][0]
             and recs[q]["scoring"] == "deterministic"]
    scorable = [q for q in plain if recs[q].get("rules")]
    no_rules = [q for q in plain if not recs[q].get("rules")]
    return {"correct": scorable[0], "fixed": scorable[1], "wrong": scorable[2], "refused": scorable[3],
            "pending": no_rules[0]}


def test_mock_end_to_end_five_real_questions(tmp_path):
    recs, pick = _records(), _pick()
    questions = {q.qid: q for q in load_questions(EVAL)}
    chosen = [questions[qid] for qid in pick.values()]
    role = {questions[qid].text: r for r, qid in pick.items()}
    sql = {r: recs[qid]["refs"][0]["sql"].strip().rstrip(";") for r, qid in pick.items()}

    def respond(messages):
        r = role[messages[1]["content"]]
        turn = (len(messages) - 2) // 2
        if r == "refused":
            return "CANNOT_ANSWER"
        if r == "wrong":
            return "```sql\nSELECT -123456789.5 AS x\n```\n假设：无"
        if r == "fixed" and turn == 0:
            return "```sql\nSELECT nope_column FROM retail.DimStore\n```\n假设：无"
        return f"```sql\n{sql[r]}\n```\n假设：无"

    cell = CELLS["SQL-L1"]
    ctx = R.RunContext(run_id="mock-e2e-bank", cell=cell, client=MockClient(respond),
                       executor=R.make_executor(cell, timeout_s=120), system=R.system_for(cell),
                       eval_commit="test", harness_commit=R.harness_commit(), timeout_s=120,
                       raw_dir=tmp_path / "raw")
    path = R.run_cell(ctx, chosen, reps=1, concurrency=2, runs_root=tmp_path / "runs", progress=lambda *_: None)
    log = path.read_text(encoding="utf-8")
    out = {r["qid"]: r for r in map(json.loads, log.splitlines())}
    got = {r: (out[qid]["first"], out[qid]["final"]["outcome"]) for r, qid in pick.items()}
    assert got == {"correct": ("correct", "correct"), "fixed": ("exec_error", "correct"),
                   "wrong": ("wrong", "wrong"), "refused": ("refused", "refused"),
                   "pending": ("pending", "pending")}
    assert out[pick["pending"]]["final"]["pending"] == "no_rules"
    assert out[pick["fixed"]]["n_calls"] == 2
    for q in chosen:                       # no question text in the committed log
        assert q.text not in log
    summary = R.summarize(path)
    assert summary["accuracy"] is None and summary["accuracy_scored"] == 2 / 4
