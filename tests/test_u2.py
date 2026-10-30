from collections import Counter
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import run_direct as R, u2_analysis as A
from harness.cells import CELLS, U2_CELLS
from harness.questions import Question
from harness.selective_v2 import U2_CONFIDENCE_RULE, NEW_FOUR, OLD_FOUR, u2_confidence_record
from scripts import t29_u2 as U


def test_u2_combines_only_fourth_instruction_and_confidence(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "CONTEXTS", tmp_path)
    for base in ("SQL-L0", "SQL-L1"):
        (tmp_path / f"{base}.yaml").write_text("synthetic_context: frozen")
        original = R.system_for(CELLS[base])
        cell = U2_CELLS[f"{base}-u2"]
        treatment = R.system_for(cell)
        assert treatment == original.replace(OLD_FOUR, NEW_FOUR)+"\n"+U2_CONFIDENCE_RULE+"\n"
        assert "计分规则" not in treatment and R.system_for(CELLS[base]) == original
        assert cell.name not in CELLS and cell.context == CELLS[base].context
        assert cell.allowed == CELLS[base].allowed


def test_u2_scope_contains_both_halves_and_never_judge_or_low():
    questions = [Question(f"Q{i}", "synthetic", None, None,
                         meta=dict(split="tuning" if i < 49 else "heldout", low_discrimination=False)) for i in range(98)]
    questions += [Question("LOW", "synthetic", None, None, meta=dict(split="tuning", low_discrimination=True)),
                  Question("JUDGE", "synthetic", None, None, scoring="judge", meta=dict(split="heldout"))]
    for cell in U2_CELLS.values():
        assert len(R.questions_for(cell, questions)) == 98
    assert len(U.scope(questions)) == 98
    with pytest.raises(AssertionError):
        U.scope(questions[1:])


@pytest.mark.parametrize("line,status,score,gate", [
    ("把握：90", "valid", 90, True), ("把握：89.9", "valid", 89.9, False),
    ("", "missing", None, False), ("把握：", "missing", None, False), ("把握：101", "out_of_range", None, False),
    ("把握：90%", "invalid_format", None, False),
    ("把握：90\n把握：80", "duplicate", None, False),
])
def test_u2_missing_confidence_is_not_native_refusal(line, status, score, gate):
    result = u2_confidence_record("```sql\nSELECT 1\n```\n"+line, {"outcome": "correct"})
    assert result["status"] == status and result["value"] == score
    assert result["native_refusal"] is False and result["gate90"]["answered"] == gate
    assert "gates" not in result


def test_u2_native_refusal_needs_no_confidence():
    result = u2_confidence_record("CANNOT_ANSWER", {"outcome": "refused"})
    assert result["status"] == "native_refusal" and not result["format_error"]
    assert result["value"] is None and not result["gate90"]["answered"]


def test_collection_records_missing_confidence_without_rejecting_or_sending_refs(tmp_path):
    from harness.client import MockClient
    from harness.executors import ExecResult

    sent = []
    client = MockClient(lambda messages: sent.extend(messages) or "```sql\nSELECT 1\n```")
    rules = dict(ordered=False, top_n=None, tie_columns=[], value_kinds=["count"],
                 value_types=["UInt64"], required_columns=[0])
    q = Question("Q1", "synthetic question", [[[987654321]]], rules)
    executor = SimpleNamespace(execute=lambda query: ExecResult(rows=[[987654321]], columns=[dict(name="n", type="UInt64")]))
    ctx = R.RunContext("synthetic", U2_CELLS["SQL-L0-u2"], client, executor,
                       "synthetic system", "bank", "code", 120, tmp_path / "raw")
    record = R.run_attempt(ctx, q, 1)
    assert record["status"] == "done" and record["final"]["outcome"] == "correct"
    assert record["confidence"]["status"] == "missing" and not record["confidence"]["native_refusal"]
    assert len(client.requests) == 1 and "987654321" not in json.dumps(sent)


def test_refusal_and_confidence_are_independent_conclusions():
    baseline = {f"Q{i}": [i >= 2]*3 for i in range(4)}
    rows = [dict(qid=q, rep=rep, refused=False, correct=i < 2, confidence=95 if i < 2 else 10)
            for i, q in enumerate(baseline) for rep in (1, 2, 3)]
    result = A.analyze_cell(rows, baseline, d1_complete=True, expected_questions=4, draws=100)
    assert result["refusal_conclusion"] == "该单元未见取舍"
    assert result["refusal_error_difference"] is None and result["refusal_error_difference_ci"] is None
    assert result["confidence_success"] and not result["refusal_success"]
    rows = [dict(qid=q, rep=rep, refused=i < 2, correct=i == 2, confidence=None if i < 2 else 70)
            for i, q in enumerate(baseline) for rep in (1, 2, 3)]
    result = A.analyze_cell(rows, baseline, d1_complete=True, expected_questions=4, draws=100)
    assert result["refusal_success"] and not result["confidence_success"]
    assert result["auc"] == .5 and result["refusal_error_difference_ci"] == [1, 1]


def test_refusal_uses_per_question_baseline_mean_and_cluster_bootstrap(monkeypatch):
    baseline = {"Q1": [False, True, True], "Q2": [True, True, True]}
    rows = [dict(qid=q, rep=rep, refused=q == "Q1" and rep == 2,
                 correct=rep != 1, confidence=95 if rep != 1 else 50)
            for q in baseline for rep in (1, 2, 3)]
    original = A._difference
    def check_clusters(sample, errors):
        counts = Counter((r["qid"], r["rep"]) for r in sample)
        assert all(len({counts[q, rep] for rep in (1, 2, 3)}) == 1 for q in baseline)
        return original(sample, errors)
    monkeypatch.setattr(A, "_difference", check_clusters)
    result = A.analyze_cell(rows, baseline, d1_complete=True, expected_questions=2, draws=50)
    assert result["refusal_error_difference"] == pytest.approx(.2)
    assert result["bootstrap"]["unit"] == "question"


def test_auc_uses_treatment_content_labels_and_missing_is_not_zero():
    baseline = {"Q1": [False]*3, "Q2": [True]*3}
    rows = [dict(qid=q, rep=rep, refused=False, correct=q == "Q1",
                 confidence=None if rep == 3 else 95 if q == "Q1" else 50)
            for q in baseline for rep in (1, 2, 3)]
    result = A.analyze_cell(rows, baseline, d1_complete=True, expected_questions=2, draws=100)
    assert result["auc"] == 1 and result["confidence_missing"] == 2
    assert result["gate90"]["coverage"] == pytest.approx(2/6)
    assert result["gate90"]["accuracy_answered"] == 1
    with pytest.raises(ValueError, match="D1"):
        A.analyze_cell(rows, baseline, expected_questions=2)
    with pytest.raises(ValueError, match="scope incomplete"):
        A.analyze_cell(rows[:-1], baseline, d1_complete=True, expected_questions=2)


def test_u2_unexpected_warmup_error_stops_before_other_attempts(tmp_path):
    cell = U2_CELLS["SQL-L0-u2"]
    ctx = SimpleNamespace(run_id="synthetic", cell=cell, boundary=R.CallBoundary(None, allow_peak=True))
    calls = []
    def fail(ctx, q, rep):
        calls.append(q.qid)
        raise TypeError("synthetic startup failure")
    qs = [Question(f"Q{i}", "synthetic", None, None) for i in range(3)]
    path = R.run_cell(ctx, qs, 1, 8, runs_root=tmp_path, progress=lambda *a: None, attempt=fail)
    assert calls == ["Q0"] and ctx.boundary.stopped.is_set()
    assert json.loads(path.read_text())["status"] == "harness_error"


def test_five_percent_boundary_and_all_refused_are_not_misinterpreted():
    baseline = {f"Q{i}": [i != 0]*3 for i in range(20)}
    rows = [dict(qid=q, rep=rep, refused=q == "Q0", correct=rep != 1, confidence=80)
            for q in baseline for rep in (1, 2, 3)]
    exactly = A.analyze_cell(rows, baseline, d1_complete=True, expected_questions=20, draws=40)
    assert exactly["refusal_rate"] == .05 and exactly["refusal_error_difference"] == 1
    rows[2] = {**rows[2], "refused": False}
    below = A.analyze_cell(rows, baseline, d1_complete=True, expected_questions=20, draws=40)
    assert below["refusal_rate"] < .05 and below["refusal_error_difference"] is None
    rows = [{**r, "refused": True, "confidence": None, "correct": None} for r in rows]
    all_refused = A.analyze_cell(rows, baseline, d1_complete=True, expected_questions=20, draws=40)
    assert all_refused["refusal_conclusion"] == "无法比较" and all_refused["auc"] is None


def test_equal_baseline_error_rates_do_not_succeed_due_to_roundoff():
    baseline = {f"Q{i}": [True, True, False] for i in range(20)}
    rows = [dict(qid=q, rep=rep, refused=q == "Q0", correct=rep != 1, confidence=80)
            for q in baseline for rep in (1, 2, 3)]
    result = A.analyze_cell(rows, baseline, d1_complete=True, expected_questions=20, draws=100)
    assert result["refusal_error_difference_ci"] == [0, 0] and not result["refusal_success"]


def test_paid_u2_requires_explicit_approval_flags_and_a_user_tag(monkeypatch):
    with pytest.raises(SystemExit):
        U.main(["--run-id", "synthetic"])
    def missing_tag(*a, **kw):
        raise subprocess.CalledProcessError(128, "git rev-parse")
    import subprocess
    monkeypatch.setattr(U.subprocess, "run", missing_tag)
    with pytest.raises(subprocess.CalledProcessError):
        U.verify_harness()
