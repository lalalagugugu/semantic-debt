from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import prompt as P, run_direct as R
from harness.cells import CELLS, L1PLUS_CELLS, SELECTIVE_CELLS, SELECTIVE_V2_CELLS
from harness.selective_v2 import (
    NEW_FOUR, OLD_FOUR, best_group, confidence_auc, confidence_record,
    result_equivalent, screening, scoring_rule,
)


def test_v1_hashes_and_v2_prompt_differences(tmp_path, monkeypatch):
    from render.context import dump_yaml, render_cell

    monkeypatch.setattr(R, "CONTEXTS", tmp_path)
    (tmp_path / "SQL-L1plus.yaml").write_text(dump_yaml(render_cell("SQL-L1plus")))
    base = R.system_for(L1PLUS_CELLS["SQL-L1plus"])
    expected = {"SQL-L1plus-sel-k1": "8198443926c8afd449a14ee17637bc6551fb55124b7ca24a08cae07ee82dcd36",
                "SQL-L1plus-sel-k3": "91277cca3c7e61581fd323c2cfaefc9cb90d35596977eb341a75c04f11db00a8"}
    assert R.sha256(base) == "b80107d469e5600f1c7f3150afef18d11734452a25cc9340f1df46bc470073a3"
    for name, sha in expected.items():
        assert R.sha256(R.system_for(SELECTIVE_CELLS[name])) == sha
    for name, cell in SELECTIVE_V2_CELLS.items():
        system = R.system_for(cell)
        if cell.selective_variant == "front":
            assert system == scoring_rule(cell.selective_k) + "\n\n" + base.replace(OLD_FOUR, NEW_FOUR)
        elif cell.selective_variant == "confidence":
            assert system.startswith(base) and "计分规则" not in system
        else:
            assert system == base + "\n" + scoring_rule(cell.selective_k) + "\n"
        assert name not in CELLS and cell.context == "build:SQL-L1plus.yaml"


@pytest.mark.parametrize("text,value,error,answered", [
    ("```sql\nSELECT 1\n```\n把握：50", 50, False, [True, False, False]),
    ("```sql\nSELECT 1\n```\n把握：90", 90, False, [True, True, True]),
    ("```sql\nSELECT 1\n```\n把握：74.5", 74.5, False, [True, False, False]),
    ("```sql\nSELECT 1\n```", None, True, [False]*3),
    ("```sql\nSELECT 1\n```\n把握：101", None, True, [False]*3),
    ("```sql\nSELECT 1\n```\n把握：-1", None, True, [False]*3),
    ("```sql\nSELECT 1\n```\n把握：50\n把握：90", None, True, [False]*3),
    ("CANNOT_ANSWER", None, False, [False]*3),
])
def test_confidence_is_parsed_once_and_gated_without_calls(text, value, error, answered):
    result = confidence_record(text, {"outcome": "correct"})
    assert result["value"] == value and result["format_error"] == error
    assert [g["answered"] for g in result["gates"].values()] == answered


def test_screening_requires_all_three_conditions_and_uses_k3_score():
    baseline = {"Q1": 1, "Q2": 2/3, "Q3": 1/3, "Q4": 0}
    rows = [{"qid": q, "answered": i < 2, "correct": True} for i, q in enumerate(baseline)]
    good = screening(rows, baseline)
    assert good["eligible"] and good["score_k3"] == .5
    assert not screening([{**r, "answered": True} for r in rows], baseline)["eligible"]
    assert not screening([{**r, "correct": False} for r in rows], baseline)["eligible"]
    assert best_group({"good": good})["best"] == ["good"]
    assert best_group({"a": good, "b": good})["reason"] == "tie_requires_user"


def test_auc_uses_raw_scores_and_handles_no_class_information():
    assert confidence_auc([(90, True), (10, False)], draws=100)["auc"] == 1
    tied = confidence_auc([(70, True), (70, False)], draws=100)
    assert tied["auc"] == .5 and tied["indistinguishable"]
    assert confidence_auc([(90, True)], draws=100)["auc"] is None


def test_result_consistency_preserves_duplicates_maps_columns_and_uses_tolerance():
    a = {"columns": [{"name": "label", "type": "String"}, {"name": "sales_amount", "type": "Float64"}],
         "rows": [["a", 100.0], ["a", 100.0], ["b", 200.0]]}
    b = {"columns": list(reversed(a["columns"])), "rows": [[200.5, "b"], [100.1, "a"], [100.1, "a"]]}
    assert result_equivalent(a, b) is True
    assert result_equivalent(a, {**b, "rows": [[200.5, "b"], [200.5, "b"], [100.1, "a"]]}) is False
    assert result_equivalent(a, {**b, "rows": b["rows"][:-1]}) is False
    assert result_equivalent(a, {**b, "error": "failed"}) is False


def test_concurrent_reservations_account_out_of_order_and_keep_admission_closed(tmp_path):
    from decimal import Decimal
    from harness.spend import ConcurrentSpendGuard, SpendLimit

    path = tmp_path / "ledger.jsonl"
    guard = ConcurrentSpendGuard(path, 1.5, "deepseek-flash", .2)
    tickets = [guard.begin("cell", f"Q{i}", 1, 0) for i in range(8)]
    assert guard.reached
    with pytest.raises(SpendLimit):
        guard.begin("cell", "Q9", 1, 0)
    usage = {"prompt_tokens": 1, "cache_hit_tokens": 0, "cache_miss_tokens": 1, "completion_tokens": 1}
    for ticket in reversed(tickets):
        guard.charge(ticket, .01, usage)
    restored = ConcurrentSpendGuard(path, 1.5, "deepseek-flash", .2)
    assert restored.total == Decimal(".08") and restored.reached
    assert not restored.outstanding


def test_concurrent_chat_finishes_all_eight_admitted_responses(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import json
    import threading
    from harness.client import MockClient
    from harness.spend import ConcurrentSpendGuard
    from harness.questions import Question

    guard = ConcurrentSpendGuard(tmp_path / "raw" / "ledger.jsonl", 1.5, "deepseek-flash", .2)
    barrier = threading.Barrier(8)
    def respond(messages):
        barrier.wait(timeout=10)
        return "CANNOT_ANSWER"
    client = MockClient(respond, model="deepseek-flash")
    cell = SELECTIVE_V2_CELLS["SQL-L1plus-sel-k5"]
    ctx = R.RunContext("synthetic", cell, client, None, "system", "bank", "code", 1, tmp_path / "raw" / "cell",
                       boundary=R.CallBoundary(None, allow_peak=True, spend=guard))
    monkeypatch.setattr(R, "cost_cny", lambda *a: .01)
    def call(i):
        q = Question(f"Q{i}", "synthetic", None, None)
        return R._chat(ctx, q, 1, 0, P.first_messages("system", q.text))
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(call, range(8)))
    assert len(replies) == 8 and len(client.requests) == 8
    assert len(list(ctx.raw_dir.glob("*.json"))) == 8
    assert len([json.loads(s) for s in guard.path.read_text().splitlines() if '"event": "charge"' in s]) == 8
    with pytest.raises(R.RunStopped):
        call(9)
    assert len(client.requests) == 8


def test_concurrent_unknown_request_blocks_resume(tmp_path):
    from harness.spend import ConcurrentSpendGuard

    p = tmp_path / "ledger.jsonl"
    guard = ConcurrentSpendGuard(p, 1.5, "deepseek-flash", .1)
    guard.begin("cell", "Q1", 1, 0)
    with pytest.raises(ValueError, match="unresolved"):
        ConcurrentSpendGuard(p, 1.5, "deepseek-flash", .1)


def test_single_call_over_estimate_settles_and_closes_admission(tmp_path):
    from harness.spend import ConcurrentSpendGuard, SpendLimit

    guard = ConcurrentSpendGuard(tmp_path / "ledger.jsonl", 1.5, "deepseek-flash", .1)
    ticket = guard.begin("cell", "Q1", 1, 0)
    usage = dict(prompt_tokens=1, cache_hit_tokens=0, cache_miss_tokens=1, completion_tokens=1)
    guard.charge(ticket, .11, usage)
    assert guard.reached and not guard.outstanding
    with pytest.raises(SpendLimit):
        guard.begin("cell", "Q2", 1, 0)


def test_settled_cost_and_inflight_estimate_both_count(tmp_path):
    from harness.spend import ConcurrentSpendGuard, SpendLimit

    guard = ConcurrentSpendGuard(tmp_path / "ledger.jsonl", .3, "deepseek-flash", .1)
    usage = dict(prompt_tokens=1, cache_hit_tokens=0, cache_miss_tokens=1, completion_tokens=1)
    guard.charge(guard.begin("cell", "Q1", 1, 0), .1, usage)
    guard.begin("cell", "Q2", 1, 0)
    assert not guard.reached
    guard.begin("cell", "Q3", 1, 0)
    assert guard.reached
    with pytest.raises(SpendLimit):
        guard.begin("cell", "Q4", 1, 0)


def test_expanded_runner_keeps_authorized_scopes_and_checks_tag(monkeypatch):
    from scripts import t29_expanded_pilot as runner
    from harness.questions import Question

    old = __import__("json").loads((runner.ROOT / "reports/validation/t29-pilot-preflight.json").read_text())["pilot_qids"]
    ids = old + [f"X{i}" for i in range(30)]
    questions = [Question(q, "synthetic", None, None, meta=dict(split="tuning", low_discrimination=q == "Q17")) for q in ids]
    questions += [Question("heldout", "synthetic", None, None, meta=dict(split="heldout"))]
    ab, c = runner.scopes(questions)
    assert ab == old and len(c) == 49 and "Q17" not in c and len(set(ab+c)) == 50
    def missing_tag(*args, **kwargs):
        raise runner.subprocess.CalledProcessError(128, "git rev-parse")
    monkeypatch.setattr(runner.subprocess, "run", missing_tag)
    with pytest.raises(runner.subprocess.CalledProcessError):
        runner.verify_harness()
