from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import t29_consistency_report as D
from scripts.t29_assumption_report import verdict


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
