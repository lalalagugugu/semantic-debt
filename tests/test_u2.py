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
    assert U.TAG == "harness-u2-v2"
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


def test_six_cells_dispatch_in_order_against_budget_net_of_prior_spend(tmp_path, monkeypatch):
    import hashlib
    from harness.executors import ExecResult

    pre = json.loads((U.ROOT / U.PREFLIGHT).read_text())
    assert len(pre["rows"]) == 6 and pre["first_calls"] == 1764 and pre["budget_ceiling_cny"] == 40
    runtime = tmp_path / "runtime"
    stored = runtime / U.PREFLIGHT
    stored.parent.mkdir(parents=True)
    stored.write_text(json.dumps(pre))
    (tmp_path / "chdb-t29").mkdir()
    monkeypatch.setenv("SEMDEBT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(U, "ROOT", runtime)
    monkeypatch.setattr(U, "verify_eval_tag", lambda *a: None)
    monkeypatch.setattr(U, "verify_semantic_tag", lambda *a, **kw: None)
    monkeypatch.setattr(U, "load_questions", lambda **kw: [])
    monkeypatch.setattr(U, "build_preflight", lambda q: pre)
    monkeypatch.setattr(U, "verify_harness", lambda: None)
    monkeypatch.setattr(U, "verify_prior_spend", lambda data: None)
    monkeypatch.setattr(R, "is_peak", lambda *a: False)
    monkeypatch.setattr(U.executors, "default_chdb_path", lambda: "unused")
    monkeypatch.setattr(R, "make_executor", lambda *a: SimpleNamespace(execute=lambda q: ExecResult(rows=[[1]])))
    dispatched = []
    monkeypatch.setattr(R, "main", lambda argv: dispatched.append(R.parse_args(argv)) or 0)
    assert U.main(["--execute-approved", "--run-id", "synthetic", "--approved-preflight-sha256",
                   hashlib.sha256(stored.read_bytes()).hexdigest()]) == 0
    assert [a.cell for a in dispatched] == [[c] for c in U.COLLECTION_CELLS]
    assert all(a.budget == 39.993728 and a.reps == 3 and a.concurrency == 8 and a.run_id == "synthetic" and a.stop_on_error and a.expected_fingerprint == U.FINGERPRINT for a in dispatched)


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


def test_prior_spend_is_settled_verified_and_not_reset(tmp_path, monkeypatch):
    import hashlib
    from harness.spend import ConcurrentSpendGuard, SpendLimit
    ledger = tmp_path / "runs-raw" / U.PRIOR_RUN / "spend-ledger.jsonl"
    prior = ConcurrentSpendGuard(ledger, 30, U.MODEL, .120675)
    ticket = prior.begin("SQL-L0-u2", "Q01", 1, 0)
    usage = dict(prompt_tokens=10, cache_hit_tokens=0, cache_miss_tokens=10, completion_tokens=10)
    prior.charge(ticket, .006272, usage)
    evidence = tmp_path / "reports/validation/t29-u2-collection-stop.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(json.dumps(dict(actual_cost_cny="0.006272",
                                       spend_ledger_sha256=hashlib.sha256(ledger.read_bytes()).hexdigest())))
    monkeypatch.setattr(U, "ROOT", tmp_path)
    U.verify_prior_spend(tmp_path)
    from decimal import Decimal
    assert Decimal(str(U.RUN_BUDGET))+U.PRIOR_COST == Decimal(40)
    remaining = ConcurrentSpendGuard(tmp_path / "new-ledger.jsonl", U.RUN_BUDGET, U.MODEL, .120675)
    remaining.total = U.PRIOR_COST + remaining.limit - remaining.max_call_cost
    with pytest.raises(SpendLimit):
        remaining.begin("SQL-L0", "Q01", 1, 0)
    ledger.write_text(ledger.read_text()+"\n")
    with pytest.raises(ValueError, match="ledger changed"):
        U.verify_prior_spend(tmp_path)
    ledger.write_text(ledger.read_text().rstrip()+"\n")
    prior.begin("SQL-L0-u2", "Q01", 2, 0)
    evidence.write_text(json.dumps(dict(actual_cost_cny="0.006272",
                                       spend_ledger_sha256=hashlib.sha256(ledger.read_bytes()).hexdigest())))
    with pytest.raises(ValueError, match="unresolved"):
        U.verify_prior_spend(tmp_path)


def test_u2_v2_refuses_reusing_old_run_ids():
    for run_id in (U.PRIOR_RUN, U.ESTIMATE_BASELINE_RUN):
        with pytest.raises(SystemExit):
            U.main(["--dry-run", "--run-id", run_id])
