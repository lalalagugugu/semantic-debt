from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import t29_consistency_report as D
from scripts.t29_assumption_report import verdict
from scripts.t29_expanded_report import audit_ledger, public_record


def test_three_results_require_every_pair(monkeypatch):
    seen = []
    payloads = [{"rep": i} for i in (1, 2, 3)]
    def compare(a, b):
        seen.append((a["rep"], b["rep"]))
        return (a["rep"], b["rep"]) != (1, 3)
    monkeypatch.setattr(D, "result_equivalent", compare)
    assert D.consistent(payloads) == "inconsistent"
    assert seen == [(1, 2), (1, 3), (2, 3)]


def test_errors_refusals_and_unresolved_mapping_never_deliver(monkeypatch):
    assert D.consistent([{}, None, {}]) == "execution_error_or_refusal"
    assert D.consistent([{}, {"error": "synthetic"}, {}]) == "execution_error_or_refusal"
    monkeypatch.setattr(D, "result_equivalent", lambda *a: None)
    assert D.consistent([{}, {}, {}]) == "mapping_cap"
    monkeypatch.setattr(D, "result_equivalent", lambda *a: True)
    assert D.consistent([{}, {}, {}]) == "consistent"


def test_b2_does_not_revoke_absent_or_underspecified_assumptions():
    for category in ("no_assumption_single", "no_assumption_multiple", "underspecified_multiple"):
        assert verdict(True, category, False, False, False) == (True, "retained_primary")
    assert verdict(False, "no_assumption_single", False, False, True) == (True, "newly_recognized")
    for category in ("no_assumption_multiple", "underspecified_multiple"):
        assert verdict(False, category, False, False, True) == (False, "not_recognized")


def test_b2_revocation_requires_manual_contradiction_and_exclusions_are_separate():
    assert verdict(True, "mapped", True, False, False) == (False, "revoked_declared_contradiction")
    assert verdict(True, "excluded_l1plus", False, True, False) == (False, "excluded_reference_l1plus")
    assert verdict(False, "assumption_sql_mismatch", False, False, True) == (False, "not_recognized")


def test_public_expanded_log_omits_answer_and_error_content():
    source = dict(qid="Q1", turns=[dict(query="synthetic query", assumption="synthetic assumption",
                  raw_sha256="hash", exec=dict(status="error", error="sensitive SQL error",
                                               columns=["sensitive"], detail="sensitive", error_class="engine_error"))])
    public = public_record(source)
    assert public == dict(qid="Q1", turns=[dict(raw_sha256="hash", exec=dict(status="error", error_class="engine_error"))])
    assert source["turns"][0]["query"] == "synthetic query"
    assert public_record({"confidence": {"value": 91, "format_error": False}}) == {"confidence": {"format_error": False}}


def test_expanded_ledger_audit_checks_out_of_order_receipts(tmp_path):
    import json
    import pytest
    from harness.spend import ConcurrentSpendGuard

    raw = tmp_path / "raw"
    path = raw / "spend-ledger.jsonl"
    guard = ConcurrentSpendGuard(path, 3, "deepseek-flash", .133522)
    tickets = [guard.begin("cell", f"Q{i}", 1, 0) for i in range(2)]
    (raw / "cell").mkdir()
    u = dict(prompt_tokens=10, prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=10, completion_tokens=10)
    usage = dict(prompt_tokens=10, cache_hit_tokens=0, cache_miss_tokens=10, completion_tokens=10)
    for i in reversed(range(2)):
        (raw / "cell" / f"Q{i}_r1_t0.json").write_text(json.dumps(dict(usage=u)))
        guard.charge(tickets[i], .00005, usage)
    calls, total, maximum = audit_ledger(path, raw)
    assert len(calls) == 2 and float(total) == .0001 and float(maximum) == .133522
    (raw / "cell/Q0_r1_t0.json").write_text(json.dumps(dict(usage={**u, "completion_tokens": 20})))
    with pytest.raises(AssertionError):
        audit_ledger(path, raw)
