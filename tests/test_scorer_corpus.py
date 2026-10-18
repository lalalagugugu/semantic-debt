"""Scorer corpus (harness/scorer_corpus.py): what is read back is what rescore hands the scorer."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness import run_direct as R  # noqa: E402
from harness import scorer_corpus as C  # noqa: E402
from harness.client import MockClient  # noqa: E402
from harness.executors import ExecResult  # noqa: E402
from harness.questions import Question, effective_rules  # noqa: E402
from harness.rescore import candidate_of  # noqa: E402
from harness.scorer import REFUSAL, ExecError  # noqa: E402
from tests.test_harness import QTEXT, FakeExecutor, _ctx, _scripted  # noqa: E402

RULES = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["other", "count"],
         "value_types": ["String", "UInt64"]}
OWN = {**RULES, "ordered": True}
QA = Question("Q001", QTEXT, refs=[[["a", 7], ["b", 1.5]], [["a", 7]]], rules=RULES, ref_rules=[None, OWN])
QJ = Question("Q002", "另一道题", refs=[[["x", 1]]], rules=RULES, scoring="judge")


def same(a, b) -> bool:
    """Equal with identical types all the way down (1 != 1.0 != True here; nan == nan)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and math.isnan(a):
        return math.isnan(b)
    return a == b


@pytest.mark.parametrize("v", [None, True, 0, -3, 2**70, 1.0, -0.0, 0.1, "2024-01-01", "",
                               math.nan, math.inf, -math.inf, date(2024, 1, 2),
                               datetime(2024, 1, 2, 3, 4, 5), Decimal("1.230")])
def test_values_round_trip_with_their_types(v):
    back = C.decode_value(json.loads(json.dumps(C.encode_value([[v]]), allow_nan=False)))
    assert same(back, [[v]])


def test_candidate_kinds_round_trip():
    for c in (REFUSAL, ExecError("Code: 47. Unknown identifier"), [["a", 7]], []):
        back = C.decode_candidate(json.loads(json.dumps(C.encode_candidate(c))))
        assert back == c if not isinstance(c, list) else same(back, c)


def _run(tmp_path, cell, q, rep, answers, table):
    respond, _ = _scripted(*answers)
    ctx = replace(_ctx(tmp_path, MockClient(respond), FakeExecutor(table), cell=cell),
                  raw_dir=tmp_path / "raw-root" / "test-run" / cell)
    rec = R.run_attempt(ctx, q, rep)
    log = tmp_path / "runs" / "test-run" / f"{cell}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


@pytest.fixture
def run(tmp_path):
    rows = [["a", 7], ["b", math.nan]]
    _run(tmp_path, "SQL-L1", QA, 1, ["```sql\nSELECT 1\n```"], {"SELECT 1": ExecResult(rows=rows)})
    _run(tmp_path, "SQL-L1", QA, 2, ["```sql\nSELECT nope\n```", "```sql\nSELECT 2\n```"],
         {"SELECT 2": ExecResult(rows=[["a", 7]])})                      # fixed on the second turn
    _run(tmp_path, "SQL-L1", QA, 3, ["CANNOT_ANSWER"], {})
    _run(tmp_path, "SQL-R", QA, 1, ["```sql\nSELECT nope\n```", "```sql\nSELECT still_nope\n```"], {})
    _run(tmp_path, "SQL-R", QA, 2, ["没有代码块"], {})
    _run(tmp_path, "SQL-R", QJ, 1, ["```sql\nSELECT 1\n```"], {"SELECT 1": ExecResult(rows=[["x", 1]])})
    return tmp_path


def test_read_back_equals_what_rescore_builds(run):
    qs = {"Q001": QA, "Q002": QJ}
    cases = C.export_run("test-run", "t", qs, "eval-test@abc1234", runs_root=run / "runs", raw_root=run / "raw-root")
    out = run / "corpus" / "t.jsonl"
    C.write_corpus(cases, out)
    back = C.load_corpus(out)
    assert len(back) == 8          # 6 attempts + the turn 0 of the two that have a fix turn
    assert {c["case_id"] for c in back if c["turn"] == 0 and c["case_id"].endswith("/t0")} == \
        {"t/SQL-L1/Q001/r2/t0", "t/SQL-R/Q001/r1/t0"}
    for log in sorted((run / "runs" / "test-run").glob("*.jsonl")):
        recs = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
        for rec, turn in [(r, t) for r in recs for t in ([-1, 0] if len(r["turns"]) > 1 else [-1])]:
            case = next(c for c in back if c["case_id"] == f"t/{log.stem}/{rec['qid']}/r{rec['rep']}" + ("/t0" if turn == 0 else ""))
            assert case["turn"] == rec["turns"][turn]["turn"]
            q = qs[rec["qid"]]
            want = candidate_of(rec["turns"][turn], run / "raw-root" / "test-run" / log.stem, rec["qid"], rec["rep"])
            got = case["candidate"]
            assert type(got) is type(want)
            assert got == want if isinstance(want, (ExecError, str)) else same(got, want)
            assert same(case["refs"], q.refs)
            assert case["rules"] == effective_rules(q)
            assert case["value_types"] == [r["value_types"] for r in effective_rules(q)]
            assert (case["question_id"], case["cell"], case["round"]) == (rec["qid"], log.stem, rec["rep"])
            assert case["judge"] == (q.scoring == "judge") and case["bank"] == "eval-test@abc1234"
    kinds = {c["case_id"]: c["candidate"] for c in back}
    assert kinds["t/SQL-L1/Q001/r3"] == REFUSAL
    assert isinstance(kinds["t/SQL-R/Q001/r1"], ExecError) and isinstance(kinds["t/SQL-R/Q001/r2"], ExecError)
    assert math.isnan(kinds["t/SQL-L1/Q001/r1"][1][1])
    assert QTEXT not in out.read_text(encoding="utf-8")


@pytest.mark.parametrize("stem", ["Q001_r1_t0", "Q001_r2_t0"])   # a final turn; a turn 0 before a fix
def test_export_checks_runs_raw_hashes_and_reads_only(run, stem):
    raw = run / "raw-root" / "test-run" / "SQL-L1" / f"{stem}.exec.json"
    logs = {p: p.read_bytes() for p in (run / "runs").rglob("*.jsonl")}
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(ValueError, match="sha256"):
        C.export_run("test-run", "t", {"Q001": QA, "Q002": QJ}, "b", runs_root=run / "runs", raw_root=run / "raw-root")
    assert {p: p.read_bytes() for p in logs} == logs


def test_changed_question_and_label_are_marked(run):
    changed = Question("Q001", "改过的题面", refs=QA.refs, rules=RULES, ref_rules=QA.ref_rules)
    cases = C.export_run("test-run", "p", {"Q001": changed, "Q002": QJ}, "b", label="flash",
                         runs_root=run / "runs", raw_root=run / "raw-root")
    q1 = [c for c in cases if c["question_id"] == "Q001"]
    assert all(c.get("question_changed") for c in q1)
    assert not any(c.get("question_changed") for c in cases if c["question_id"] == "Q002")
    assert all(c["case_id"].startswith("p/flash/") and c["model"] == "flash" for c in cases)


def test_corpus_file_is_never_overwritten(tmp_path):
    out = tmp_path / "c.jsonl"
    C.write_corpus([], out)
    with pytest.raises(FileExistsError):
        C.write_corpus([], out)
