"""Mock end-to-end on real questions from the question bank (T11 deliverable):
real loader → mock model → real chDB → T02 scorer → log.

Questions are chosen at run time by their properties, never by text: plain
scorable ones, a multi-reference question whose second reference carries its own
``rules`` (per-reference rules), grouped / nested Top-N questions (``selection``)
and a judge question. Where a reference is post-processed (its SQL is not the
final answer) the mock "model" returns the reference rows through ClickHouse's
``values()``. No question text, SQL or reference value is written into this file.
"""

from __future__ import annotations

import json
import math
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


def _manifest() -> dict[str, dict]:
    return {r["result_path"]: r for r in json.loads((EVAL / "refs" / "MANIFEST.json").read_text())["records"]}


def _literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        assert not (isinstance(value, float) and not math.isfinite(value))
        return repr(value)
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def values_sql(columns: list[dict], rows: list[list]) -> str:
    structure = ", ".join(f"c{i} {c['type']}" for i, c in enumerate(columns))
    body = ", ".join("(" + ", ".join(_literal(v) for v in row) + ")" for row in rows)
    return f"SELECT * FROM values('{structure}', {body})"


def _pick(recs: dict[str, dict], manifest: dict[str, dict]) -> dict[str, str]:
    def rows(ref):
        return manifest[ref["result_path"]]["row_count"]

    det = [q for q in sorted(recs) if recs[q]["scoring"] == "deterministic"]
    plain = [q for q in det if len(recs[q]["refs"]) == 1 and "postprocess" not in recs[q]["refs"][0]
             and not recs[q]["rules"].get("selection") and recs[q]["rules"]["top_n"] is None]
    multi = [q for q in det if len(recs[q]["refs"]) > 1 and "rules" in recs[q]["refs"][1]
             and len(recs[q]["refs"][1]["rules"]["value_types"]) != len(recs[q]["rules"]["value_types"])
             and rows(recs[q]["refs"][1]) <= 1000]
    grouped = sorted((q for q in det if len(recs[q]["refs"]) == 1 and recs[q]["rules"].get("selection")
                      and rows(recs[q]["refs"][0]) <= 1000), key=lambda q: rows(recs[q]["refs"][0]))
    judge = [q for q in sorted(recs) if recs[q]["scoring"] == "judge" and "postprocess" not in recs[q]["refs"][0]]
    assert multi and len(grouped) >= 2 and judge, "the bank no longer has the shapes this test needs"
    return {"correct": plain[0], "fixed": plain[1], "wrong": plain[2], "refused": plain[3],
            "multi_ref2": multi[0], "grouped": grouped[0], "grouped_missing_row": grouped[1], "judge": judge[0]}


def test_mock_end_to_end_real_questions(tmp_path):
    recs, manifest = _records(), _manifest()
    pick = _pick(recs, manifest)
    questions = {q.qid: q for q in load_questions(EVAL)}
    chosen = [questions[qid] for qid in pick.values()]
    role = {questions[qid].text: r for r, qid in pick.items()}

    def ref_values(qid: str, index: int, drop_last: bool = False) -> str:
        ref = recs[qid]["refs"][index]
        rows = questions[qid].refs[index]
        return values_sql(manifest[ref["result_path"]]["columns"], rows[:-1] if drop_last else rows)

    answers = {
        "correct": recs[pick["correct"]]["refs"][0]["sql"],
        "wrong": "SELECT -123456789.5 AS x",
        "multi_ref2": ref_values(pick["multi_ref2"], 1),
        "grouped": ref_values(pick["grouped"], 0),
        "grouped_missing_row": ref_values(pick["grouped_missing_row"], 0, drop_last=True),
        "judge": recs[pick["judge"]]["refs"][0]["sql"],
    }

    def respond(messages):
        r = role[messages[1]["content"]]
        turn = (len(messages) - 2) // 2
        if r == "refused":
            return "CANNOT_ANSWER"
        if r == "fixed":
            sql = "SELECT nope_column FROM retail.DimStore" if turn == 0 else recs[pick["fixed"]]["refs"][0]["sql"]
        else:
            sql = answers[r]
        return f"```sql\n{sql.strip().rstrip(';')}\n```\n假设：无"

    cell = CELLS["SQL-L1"]
    ctx = R.RunContext(run_id="mock-e2e-bank", cell=cell, client=MockClient(respond),
                       executor=R.make_executor(cell, timeout_s=120), system=R.system_for(cell),
                       eval_commit="test", harness_commit=R.harness_commit(), timeout_s=120,
                       raw_dir=tmp_path / "raw")
    path = R.run_cell(ctx, chosen, reps=1, concurrency=2, runs_root=tmp_path / "runs", progress=lambda *_: None)
    log = path.read_text(encoding="utf-8")
    out = {r["qid"]: r for r in map(json.loads, log.splitlines())}
    assert all(r["status"] == "done" for r in out.values()), [r.get("error") for r in out.values()]
    got = {r: (out[qid]["first"], out[qid]["final"]["outcome"]) for r, qid in pick.items()}
    assert got == {"correct": ("correct", "correct"), "fixed": ("exec_error", "correct"),
                   "wrong": ("wrong", "wrong"), "refused": ("refused", "refused"),
                   "multi_ref2": ("correct", "correct"), "grouped": ("correct", "correct"),
                   "grouped_missing_row": ("wrong", "wrong"), "judge": ("pending", "pending")}
    # the second reference matched under its own rules (question-level rules have a different width)
    assert out[pick["multi_ref2"]]["final"]["matched_ref"] == 1
    assert out[pick["grouped_missing_row"]]["final"]["reason"].startswith("selection_")
    assert out[pick["judge"]]["final"]["pending"] == "judge"
    assert out[pick["fixed"]]["n_calls"] == 2
    for q in chosen:                       # no question text in the committed log
        assert q.text not in log
    summary = R.summarize(path)
    assert summary["accuracy"] is None and summary["accuracy_scored"] == 4 / 7


def test_mock_end_to_end_english_anchors(tmp_path):
    """Anchors: scored on the benchmark's original reference, with the revised column alongside."""
    from harness.anchor_refs import anchor_dir
    from harness.questions import vendor_questions
    if not (anchor_dir() / "MANIFEST.json").exists():
        pytest.skip("anchor references not built: uv run python -m harness.anchor_refs")
    en = load_questions(EVAL, lang="en")
    scorable = next(q for q in en if q.pending is None and q.refs[0])
    empty = next(q for q in en if q.pending is None and q.meta.get("empty_original_ref"))
    differs = next(q for q in en if q.pending == "anchor_structure_differs")
    vendor_sql = {f"EN{int(v['id']):02d}": v["expected_sql"].strip().rstrip(";") for v in vendor_questions(EVAL)}
    by_text = {q.text: q.qid for q in (scorable, empty, differs)}

    def respond(messages):
        return f"```sql\n{vendor_sql[by_text[messages[1]['content']]]}\n```\nAssumption: none"

    cell = CELLS["SQL-R-EN"]
    ctx = R.RunContext(run_id="mock-e2e-anchor", cell=cell, client=MockClient(respond),
                       executor=R.make_executor(cell, timeout_s=120), system=R.system_for(cell),
                       eval_commit="test", harness_commit=R.harness_commit(), timeout_s=120,
                       raw_dir=tmp_path / "raw")
    path = R.run_cell(ctx, [scorable, empty, differs], reps=1, concurrency=1, runs_root=tmp_path / "runs",
                      progress=lambda *_: None)
    out = {r["qid"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())}
    assert out[scorable.qid]["final"]["outcome"] == "correct"
    assert out[empty.qid]["final"]["outcome"] == "correct"      # the original SQL's empty result, scored as empty
    assert out[differs.qid]["final"]["outcome"] == "pending"
    assert out[differs.qid]["final"]["pending"] == "anchor_structure_differs"
    for r in out.values():
        assert r["final"]["revised"]["outcome"] in {"correct", "wrong", "pending"}
