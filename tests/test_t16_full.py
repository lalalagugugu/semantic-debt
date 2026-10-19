"""Budget/fingerprint controls: mocks only, never a paid request."""
from decimal import Decimal
from pathlib import Path
import sys
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import json

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.client import Reply
from harness import run_direct as R
from scripts.run_t16_v14_full import BudgetBoundary, FP


def reply(tokens, fingerprint=FP):
    return Reply("CANNOT_ANSWER", None, "deepseek-flash", "stop",
                 {"prompt_tokens": 1, "cache_hit_tokens": 0, "cache_miss_tokens": 1, "completion_tokens": tokens},
                 0.1, b'{"test":true}', system_fingerprint=fingerprint)


def test_budget_overrun_stops_after_raw_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "is_peak", lambda: False)
    guard = BudgetBoundary(tmp_path / "budget.jsonl")
    received = reply(2_500_000)
    ctx = SimpleNamespace(boundary=guard, client=SimpleNamespace(chat=lambda _: received), raw_dir=tmp_path / "raw")
    with pytest.raises(R.RunStopped, match="budget exceeded") as caught:
        R._chat(ctx, SimpleNamespace(qid="Q00"), 1, 0, [])
    assert caught.value.reply is received
    assert (ctx.raw_dir / "Q00_r1_t0.json").read_bytes() == received.raw
    assert guard.spent > Decimal("10") and guard.stopped.is_set()
    with pytest.raises(R.RunStopped):
        guard.before_request()


def test_fingerprint_mismatch_is_charged_and_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "is_peak", lambda: False)
    guard = BudgetBoundary(tmp_path / "budget.jsonl")
    received = reply(10, "different")
    ctx = SimpleNamespace(boundary=guard, client=SimpleNamespace(chat=lambda _: received), raw_dir=tmp_path / "raw")
    with pytest.raises(R.RunStopped, match="fingerprint mismatch"):
        R._chat(ctx, SimpleNamespace(qid="Q00"), 1, 0, [])
    assert guard.calls == 1 and guard.spent > 0
    assert (ctx.raw_dir / "Q00_r1_t0.json").exists()


def test_exhausted_budget_blocks_before_request(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "is_peak", lambda: False)
    guard = BudgetBoundary(tmp_path / "budget.jsonl")
    guard.spent = Decimal("10")
    with pytest.raises(R.RunStopped, match="budget exhausted"):
        guard.before_request()
    assert guard.calls == 0


def test_unknown_usage_stops(tmp_path):
    guard = BudgetBoundary(tmp_path / "budget.jsonl")
    received = reply(0)
    received.usage.update(prompt_tokens=0, cache_miss_tokens=0)
    with pytest.raises(R.RunStopped, match="usage missing"):
        guard.check_reply(received)
    assert guard.calls == 1 and guard.spent == 0


def test_peak_wait_does_not_send_or_change_prompt(tmp_path, monkeypatch):
    state = {"peak": True, "slept": 0}
    monkeypatch.setattr(R, "is_peak", lambda: state["peak"])
    def sleep(seconds):
        state.update(peak=False, slept=seconds)
    monkeypatch.setattr("scripts.run_t16_v14_full.time.sleep", sleep)
    guard = BudgetBoundary(tmp_path / "budget.jsonl")
    guard.before_request()
    assert state["slept"] == 30 and guard.calls == 0 and not guard.stopped.is_set()


def test_concurrent_accounting_keeps_attempt_identity_and_every_charge(tmp_path):
    guard = BudgetBoundary(tmp_path / "budget.jsonl")

    def receive(index):
        guard.local.qid, guard.local.rep, guard.local.turn = f"Q{index}", 2, 0
        guard.check_reply(reply(10))
        guard.check_reply(reply(20))

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(receive, range(20)))
    ledger = [json.loads(s) for s in guard.ledger.read_text().splitlines()]
    assert guard.calls == len(ledger) == 40
    assert [r["call"] for r in ledger] == list(range(1, 41))
    assert {(r["qid"], r["rep"], r["turn"]) for r in ledger} == {(f"Q{i}", 2, t) for i in range(20) for t in (0, 1)}
    assert sum(Decimal(r["cost_cny"]) for r in ledger) == guard.spent == Decimal(ledger[-1]["cumulative_cost_cny"])


def test_offline_member_set_ignores_filter_values_but_keeps_nested_members():
    from scripts.report_t16_v14_full import query_members

    query = {"measures": ["fact.amount"], "dimensions": ["store.name"],
             "filters": [{"or": [{"member": "store.key", "operator": "equals", "values": ["fact.fake"]}]}],
             "timeDimensions": [{"dimension": "fact.date", "dateRange": ["2020-01-01", "2020-02-01"]}],
             "order": [["fact.amount", "desc"]]}
    assert query_members(json.dumps(query)) == ["fact.amount", "fact.date", "store.key", "store.name"]


def test_offline_denominator_keeps_refusals_and_errors_but_excludes_pending():
    from scripts.report_t16_v14_full import counts

    rows = [{"final": {"outcome": x}} for x in ("correct", "wrong", "exec_error", "refused", "pending", "unscored")]
    result = counts(rows)
    assert result["attempts"] == 6 and result["scored_denominator"] == 4
    assert result["accuracy_on_scored"] == 0.25
