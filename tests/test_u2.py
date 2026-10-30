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
from harness.selective_v2 import U2_CONFIDENCE_RULE, NEW_FOUR, OLD_FOUR, scoring_rule, u2_confidence_record
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
        penalty = U2_CELLS[f"{base}-u2p"]
        assert R.system_for(penalty) == scoring_rule(10)+"\n\n"+treatment
        assert penalty.selective_k == 10 and penalty.context == cell.context
        assert penalty.allowed == cell.allowed and penalty.name not in CELLS
    assert U.BUDGET == 40 and len(U2_CELLS) == 4
    assert list(U.COLLECTION_CELLS) == ["SQL-L0", "SQL-L1", "SQL-L0-u2", "SQL-L1-u2", "SQL-L0-u2p", "SQL-L1-u2p"]
    assert U.TAG == "harness-u2-v4"
    assert all(U.COLLECTION_CELLS[base] is CELLS[base] for base in ("SQL-L0", "SQL-L1"))


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
    result = A.analyze_cell(rows, baseline, baseline_fingerprint=U.FINGERPRINT, treatment_fingerprint=U.FINGERPRINT, baseline_run_id="synthetic", treatment_run_id="synthetic", d1_complete=True, expected_questions=4, draws=100)
    assert result["refusal_conclusion"] == "该单元未见取舍"
    assert result["refusal_error_difference"] is None and result["refusal_error_difference_ci"] is None
    assert result["confidence_success"] and not result["refusal_success"]
    rows = [dict(qid=q, rep=rep, refused=i < 2, correct=i == 2, confidence=None if i < 2 else 70)
            for i, q in enumerate(baseline) for rep in (1, 2, 3)]
    result = A.analyze_cell(rows, baseline, baseline_fingerprint=U.FINGERPRINT, treatment_fingerprint=U.FINGERPRINT, baseline_run_id="synthetic", treatment_run_id="synthetic", d1_complete=True, expected_questions=4, draws=100)
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
    result = A.analyze_cell(rows, baseline, baseline_fingerprint=U.FINGERPRINT, treatment_fingerprint=U.FINGERPRINT, baseline_run_id="synthetic", treatment_run_id="synthetic", d1_complete=True, expected_questions=2, draws=50)
    assert result["refusal_error_difference"] == pytest.approx(.2)
    assert result["bootstrap"]["unit"] == "question"


def test_auc_uses_treatment_content_labels_and_missing_is_not_zero():
    baseline = {"Q1": [False]*3, "Q2": [True]*3}
    rows = [dict(qid=q, rep=rep, refused=False, correct=q == "Q1",
                 confidence=None if rep == 3 else 95 if q == "Q1" else 50)
            for q in baseline for rep in (1, 2, 3)]
    result = A.analyze_cell(rows, baseline, baseline_fingerprint=U.FINGERPRINT, treatment_fingerprint=U.FINGERPRINT, baseline_run_id="synthetic", treatment_run_id="synthetic", d1_complete=True, expected_questions=2, draws=100)
    assert result["auc"] == 1 and result["confidence_missing"] == 2
    assert result["gate90"]["coverage"] == pytest.approx(2/6)
    assert result["gate90"]["accuracy_answered"] == 1
    with pytest.raises(ValueError, match="D1"):
        A.analyze_cell(rows, baseline, baseline_fingerprint=U.FINGERPRINT, treatment_fingerprint=U.FINGERPRINT, baseline_run_id="synthetic", treatment_run_id="synthetic", expected_questions=2)
    with pytest.raises(ValueError, match="scope incomplete"):
        A.analyze_cell(rows[:-1], baseline, baseline_fingerprint=U.FINGERPRINT, treatment_fingerprint=U.FINGERPRINT, baseline_run_id="synthetic", treatment_run_id="synthetic", d1_complete=True, expected_questions=2)


@pytest.mark.parametrize("cell", [U2_CELLS["SQL-L0-u2"], CELLS["SQL-L0"]])
def test_u2_unexpected_warmup_error_stops_before_other_attempts(tmp_path, cell):
    ctx = SimpleNamespace(run_id="synthetic", cell=cell, boundary=R.CallBoundary(None, allow_peak=True))
    calls = []
    def fail(ctx, q, rep):
        calls.append(q.qid)
        raise TypeError("synthetic startup failure")
    qs = [Question(f"Q{i}", "synthetic", None, None) for i in range(3)]
    path = R.run_cell(ctx, qs, 1, 8, runs_root=tmp_path, progress=lambda *a: None, attempt=fail, stop_on_error=True)
    assert calls == ["Q0"] and ctx.boundary.stopped.is_set()
    assert json.loads(path.read_text())["status"] == "harness_error"


def test_five_percent_boundary_and_all_refused_are_not_misinterpreted():
    baseline = {f"Q{i}": [i != 0]*3 for i in range(20)}
    rows = [dict(qid=q, rep=rep, refused=q == "Q0", correct=rep != 1, confidence=80)
            for q in baseline for rep in (1, 2, 3)]
    exactly = A.analyze_cell(rows, baseline, baseline_fingerprint=U.FINGERPRINT, treatment_fingerprint=U.FINGERPRINT, baseline_run_id="synthetic", treatment_run_id="synthetic", d1_complete=True, expected_questions=20, draws=40)
    assert exactly["refusal_rate"] == .05 and exactly["refusal_error_difference"] == 1
    rows[2] = {**rows[2], "refused": False}
    below = A.analyze_cell(rows, baseline, baseline_fingerprint=U.FINGERPRINT, treatment_fingerprint=U.FINGERPRINT, baseline_run_id="synthetic", treatment_run_id="synthetic", d1_complete=True, expected_questions=20, draws=40)
    assert below["refusal_rate"] < .05 and below["refusal_error_difference"] is None
    rows = [{**r, "refused": True, "confidence": None, "correct": None} for r in rows]
    all_refused = A.analyze_cell(rows, baseline, baseline_fingerprint=U.FINGERPRINT, treatment_fingerprint=U.FINGERPRINT, baseline_run_id="synthetic", treatment_run_id="synthetic", d1_complete=True, expected_questions=20, draws=40)
    assert all_refused["refusal_conclusion"] == "无法比较" and all_refused["auc"] is None


def test_equal_baseline_error_rates_do_not_succeed_due_to_roundoff():
    baseline = {f"Q{i}": [True, True, False] for i in range(20)}
    rows = [dict(qid=q, rep=rep, refused=q == "Q0", correct=rep != 1, confidence=80)
            for q in baseline for rep in (1, 2, 3)]
    result = A.analyze_cell(rows, baseline, baseline_fingerprint=U.FINGERPRINT, treatment_fingerprint=U.FINGERPRINT, baseline_run_id="synthetic", treatment_run_id="synthetic", d1_complete=True, expected_questions=20, draws=100)
    assert result["refusal_error_difference_ci"] == [0, 0] and not result["refusal_success"]


def test_paired_penalty_contrast_keeps_matching_clusters_and_direction():
    unpenalized = [dict(qid=f"Q{i}", rep=rep, refused=i < 2)
                   for i in range(4) for rep in (1, 2, 3)]
    # Same per-question refusal pattern produces exactly zero paired variance.
    same = A.compare_refusal_arms(unpenalized, list(reversed(unpenalized)), d1_complete=True,
                                 expected_questions=4, draws=100)
    assert same["ci95"] == [0, 0] and same["penalty_minus_unpenalized"] == 0
    no_refusals = [{**r, "refused": False} for r in unpenalized]
    all_refusals = [{**r, "refused": True} for r in unpenalized]
    increased = A.compare_refusal_arms(no_refusals, all_refusals, d1_complete=True, expected_questions=4, draws=100)
    assert increased["penalty_minus_unpenalized"] == 1 and increased["ci95"] == [1, 1]
    zero = A.compare_refusal_arms(no_refusals, no_refusals, d1_complete=True, expected_questions=4, draws=100)
    assert zero["ci95"] == [0, 0]  # Still reported when both rates are <5%.
    with pytest.raises(ValueError, match="D1"):
        A.compare_refusal_arms(no_refusals, all_refusals, expected_questions=4)
    with pytest.raises(ValueError, match="scope incomplete"):
        A.compare_refusal_arms(no_refusals, all_refusals[:-1], d1_complete=True, expected_questions=4)
    renamed = [{**r, "qid": "OTHER" if r["qid"] == "Q0" else r["qid"]} for r in all_refusals]
    with pytest.raises(ValueError, match="identical"):
        A.compare_refusal_arms(no_refusals, renamed, d1_complete=True, expected_questions=4)


def test_paid_u2_requires_explicit_approval_flags_and_a_user_tag(monkeypatch):
    with pytest.raises(SystemExit):
        U.main(["--run-id", "synthetic"])
    def missing_tag(*a, **kw):
        raise subprocess.CalledProcessError(128, "git rev-parse")
    import subprocess
    monkeypatch.setattr(U.subprocess, "run", missing_tag)
    with pytest.raises(subprocess.CalledProcessError):
        U.verify_harness()


def test_u2_rejects_old_or_mixed_baseline_provenance():
    for base_fp, treatment_fp, base_run, treatment_run in (
        (None, None, None, None),
        ("e72d3c7f663d3e1383b00b3884cb4501", U.FINGERPRINT, "new", "new"),
        (U.FINGERPRINT, "other", "new", "new"),
        (U.FINGERPRINT, U.FINGERPRINT, "old", "new"),
        (U.FINGERPRINT, U.FINGERPRINT, U.PRIOR_RUN, U.PRIOR_RUN),
        (U.FINGERPRINT, U.FINGERPRINT, U.DISCARDED_RUN, U.DISCARDED_RUN),
        (U.FINGERPRINT, U.FINGERPRINT, U.ESTIMATE_BASELINE_RUN, U.ESTIMATE_BASELINE_RUN),
    ):
        with pytest.raises(ValueError, match="same new run"):
            A.analyze_cell([], {}, d1_complete=True, baseline_fingerprint=base_fp,
                           treatment_fingerprint=treatment_fp, baseline_run_id=base_run, treatment_run_id=treatment_run)


def test_new_minus_old_baseline_drift_is_paired_and_descriptive():
    old = {"Q1": [True, False, False], "Q2": [True, True, False]}
    same = A.compare_baseline_accuracy(old, dict(reversed(list(old.items()))), d1_complete=True,
                                       expected_questions=2, draws=100)
    assert same["new_minus_old"] == 0 and same["ci95"] == [0, 0] and same["descriptive_only"]
    assert "success" not in same
    new = {q: [True, True, True] for q in old}
    positive = A.compare_baseline_accuracy(old, new, d1_complete=True, expected_questions=2, draws=100)
    assert positive["new_minus_old"] == .5 and positive["ci95"] == pytest.approx([1/3, 2/3])
    reverse = A.compare_baseline_accuracy(new, old, d1_complete=True, expected_questions=2, draws=100)
    assert reverse["new_minus_old"] == -.5 and reverse["ci95"] == pytest.approx([-2/3, -1/3])
    assert positive["bootstrap"] == dict(unit="paired_question", draws=100, seed=20261019)
    with pytest.raises(ValueError, match="D1"):
        A.compare_baseline_accuracy(old, new, expected_questions=2)
    with pytest.raises(ValueError, match="scope"):
        A.compare_baseline_accuracy(old, {"Q1": [True]*3}, d1_complete=True, expected_questions=2)
    with pytest.raises(ValueError, match="three final"):
        A.compare_baseline_accuracy(old, {q: [True]*2 for q in old}, d1_complete=True, expected_questions=2)


def test_budget_deduction_reserves_unknown_cost_without_claiming_settlement():
    from decimal import Decimal

    assert U.CONSOLE_REPORTED_COST == Decimal("0.28")
    assert U.CONFIRMED_COST == Decimal("0.16352908")
    assert U.UNCONFIRMED_CALLS*U.PRIOR_MAX_CALL_COST == Decimal("0.965400")
    assert U.BUDGET_DEDUCTION == max(Decimal("0.28"), Decimal("1.12892908"))
    assert U.RUN_BUDGET == 38.87107092


@pytest.mark.parametrize("name", list(U.COLLECTION_CELLS))
def test_u2_t13_cells_run_without_a_ledger(tmp_path, monkeypatch, name):
    from harness import client as C, questions as QL

    clients = []
    def client(model, **kwargs):
        assert "max_attempts" not in kwargs  # Keep the T13 client default.
        value = C.MockClient(lambda messages: "CANNOT_ANSWER", model=model)
        clients.append(value)
        return value
    monkeypatch.setattr(C, "DeepSeekClient", client)
    monkeypatch.setattr(R, "REPO", tmp_path)
    monkeypatch.setattr(R, "raw_root", lambda: tmp_path / "raw")
    monkeypatch.setattr(R, "harness_commit", lambda: "synthetic")
    monkeypatch.setattr(QL, "eval_commit", lambda: "synthetic")
    monkeypatch.setattr(R, "system_for", lambda cell: "synthetic system")
    monkeypatch.setattr(R, "make_executor", lambda *a: None)
    q = Question("Q_SYNTH", "synthetic question", None, None, meta=dict(split="tuning"))
    args = ["--cell", name, "--run-id", "synthetic", "--reps", "1", "--allow-peak"]
    assert R.main(args, load=lambda **kw: [q]) == 0
    assert len(clients[0].requests) == 1
    assert not list((tmp_path / "raw").rglob("spend-ledger.jsonl"))
    assert R.done_pairs(tmp_path / "runs/synthetic" / f"{name}.jsonl") == {("Q_SYNTH", 1)}
    assert R.main(["--cell", "SQL-L1plus-sel-front-k3", "--run-id", "other", "--allow-peak"],
                  load=lambda **kw: [q]) == 2  # Other selective cells still require a ledger.


def test_u2_t13_failure_continues_and_rerun_only_fills_missing(tmp_path):
    from harness.client import APIError, MockClient

    counts = Counter()
    def respond(messages):
        text = messages[-1]["content"]
        counts[text] += 1
        if text == "first" and counts[text] == 1:
            raise APIError("synthetic network failure")
        return "CANNOT_ANSWER"
    ctx = R.RunContext("synthetic", U2_CELLS["SQL-L0-u2"], MockClient(respond), None,
                       "synthetic system", "bank", "code", 120, tmp_path / "raw",
                       boundary=R.CallBoundary(None, allow_peak=True))
    questions = [Question("Q1", "first", None, None), Question("Q2", "second", None, None)]
    path = R.run_cell(ctx, questions, 1, 1, runs_root=tmp_path, progress=lambda *a: None)
    assert [r["status"] for r in map(json.loads, path.read_text().splitlines())] == ["api_error", "done"]
    assert not ctx.boundary.stopped.is_set()
    R.run_cell(ctx, questions, 1, 1, runs_root=tmp_path, progress=lambda *a: None)
    R.run_cell(ctx, questions, 1, 1, runs_root=tmp_path, progress=lambda *a: None)
    assert counts == {"first": 2, "second": 1}
    rows = [r for r in map(json.loads, path.read_text().splitlines()) if r["status"] == "done"]
    assert Counter((r["qid"], r["rep"]) for r in rows) == {("Q1", 1): 1, ("Q2", 1): 1}


def test_raw_and_execution_packages_are_numbered_without_overwrite(tmp_path):
    from harness.client import MockClient
    from harness.executors import ExecResult

    q = Question("Q1", "synthetic", None, None)
    client = MockClient(lambda messages: "CANNOT_ANSWER")
    ctx = SimpleNamespace(raw_dir=tmp_path)
    first = client.chat([{"role": "system", "content": "synthetic"}])
    first_hash = R._save_raw(ctx, q, 1, 0, first)
    second = client.chat([{"role": "system", "content": "synthetic"}])
    second_hash = R._save_raw(ctx, q, 1, 0, second)
    assert (tmp_path / "Q1_r1_t0.json").read_bytes() == first.raw
    assert (tmp_path / "Q1_r1_t0.1.json").read_bytes() == second.raw
    assert first_hash == R.sha256(first.raw) and second_hash == R.sha256(second.raw)
    R._save_exec(ctx, q, 1, 0, ExecResult(rows=[[1]]))
    R._save_exec(ctx, q, 1, 0, ExecResult(rows=[[2]]))
    assert json.loads((tmp_path / "Q1_r1_t0.exec.json").read_text())["rows"] == [[1]]
    assert json.loads((tmp_path / "Q1_r1_t0.exec.1.json").read_text())["rows"] == [[2]]
