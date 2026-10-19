"""Budget/fingerprint controls: mocks only, never a paid request."""
from decimal import Decimal
from pathlib import Path
import sys
from types import SimpleNamespace

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
