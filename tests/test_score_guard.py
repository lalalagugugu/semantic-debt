"""T13 scoring time limit (harness/score_guard.py) and backfill from runs-raw.

decisions/2026-10-18-harness-v1-1-scorer-fixes.md §4: only the runner changes; the system prompt and
the scorer stay byte-for-byte the ``harness-v1`` versions.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness import run_direct as R  # noqa: E402
from harness.client import MockClient  # noqa: E402
from harness.executors import ExecResult  # noqa: E402
from harness.score_guard import SCORE_TIMEOUT, Scored, score_with_timeout  # noqa: E402
from harness.scorer import ExecError, score_detailed  # noqa: E402
from tests.test_harness import QTEXT, FakeExecutor, Q, _ctx, _scripted  # noqa: E402

FROZEN = ("harness/prompt.py", "harness/scorer.py")


def _tag_blob(path: str) -> bytes | None:
    out = subprocess.run(["git", "-C", str(REPO), "show", f"harness-v1:{path}"], capture_output=True)
    return out.stdout if out.returncode == 0 else None


@pytest.mark.parametrize("path", FROZEN)
def test_prompt_and_scorer_are_byte_identical_to_harness_v1(path):
    blob = _tag_blob(path)
    if blob is None:
        pytest.skip("tag harness-v1 not available in this clone")
    assert (REPO / path).read_bytes() == blob


def test_guarded_score_equals_in_process_score():
    rules = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["other", "count"],
             "value_types": ["String", "UInt64"]}
    for cand in ([["a", 7]], [["a", 8]], [["a", 7], ["b", 1]]):
        s = score_detailed(cand, [[["a", 7]]], rules)
        assert score_with_timeout(cand, [[["a", 7]]], rules, timeout_s=60) == Scored(s.outcome, s.reason, s.matched_ref, s.sensitivity)


def test_guarded_score_returns_none_when_out_of_time():
    assert score_with_timeout([[42]], Q.refs, Q.rules, timeout_s=0) is None


def test_scorer_exception_is_raised_not_swallowed():
    with pytest.raises(RuntimeError, match="scorer raised"):
        score_with_timeout([[1, 2], [3]], Q.refs, Q.rules, timeout_s=60)   # not rectangular


def test_timeout_is_pending_never_a_verdict():
    rec = R.score_question([[42]], Q, score_timeout_s=0)
    assert rec["outcome"] == R.PENDING and rec["pending"] == SCORE_TIMEOUT and rec["score_timeout_s"] == 0
    # refusals and exec errors need no search and are scored in-process even with no time left
    assert R.score_question(ExecError("boom"), Q, score_timeout_s=0)["outcome"] == "exec_error"


def test_attempt_with_scoring_timeout_is_logged_as_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(R.score_question, "__defaults__", (0,))
    respond, _ = _scripted("```sql\nSELECT 42\n```")
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])})), Q, 1)
    assert rec["status"] == "done" and rec["final"]["outcome"] == R.PENDING
    assert rec["final"]["pending"] == SCORE_TIMEOUT and rec["first"] == R.PENDING
    assert (tmp_path / "raw" / "Q001_r1_t0.exec.json").exists()


def _strip(rec: dict) -> dict:
    """Fields a backfill cannot reproduce: timing (not saved) and the backfill marker."""
    out = {k: v for k, v in rec.items() if k not in ("started_at", "latency_s", "peak", "cost_cny", "backfilled_from_raw")}
    out["turns"] = [{k: (v if k != "exec" else {kk: vv for kk, vv in v.items() if kk != "elapsed_s"})
                     for k, v in t.items() if k != "latency_s"} for t in rec["turns"]]
    return out


@pytest.mark.parametrize("answers,table", [
    (("```sql\nSELECT 42\n```\n假设：无",), {"SELECT 42": ExecResult(rows=[[42]], columns=[{"name": "c", "type": "UInt64"}])}),
    (("```sql\nSELECT nope\n```", "```sql\nSELECT 42\n```"), {"SELECT 42": ExecResult(rows=[[42]])}),
    (("无法回答：缺数据",), {}),
])
def test_backfill_rebuilds_the_line_from_runs_raw_without_calls(tmp_path, answers, table):
    respond, _ = _scripted(*answers)
    live = R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor(table)), Q, 1)
    before = {p.name: p.read_bytes() for p in (tmp_path / "raw").iterdir()}

    def no_call(messages):
        raise AssertionError("backfill must not call the model")

    class NoExec:
        name = "none"

        def execute(self, query):
            raise AssertionError("backfill must not execute")

    back = R.attempt_from_raw(_ctx(tmp_path, MockClient(no_call), NoExec()), Q, 1, "test")
    assert _strip(back) == _strip(live)
    assert back["backfilled_from_raw"]["note"] == "test"
    assert {p.name: p.read_bytes() for p in (tmp_path / "raw").iterdir()} == before   # runs-raw untouched


def test_backfill_cell_skips_done_pairs_and_keeps_question_text_out(tmp_path):
    respond, _ = _scripted("```sql\nSELECT 42\n```")
    ctx = _ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])}))
    R.run_attempt(ctx, Q, 1)      # raw files only, no log line (as when the process is stopped while scoring)
    runs = tmp_path / "runs"
    R.backfill_cell(ctx, [Q], [("Q001", 1)], "stopped while scoring", runs_root=runs, progress=lambda *_: None)
    R.backfill_cell(ctx, [Q], [("Q001", 1)], "again", runs_root=runs, progress=lambda *_: None)
    lines = (runs / "test-run" / "SQL-L1.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["final"]["outcome"] == "correct"
    assert QTEXT not in lines[0]


def test_backfill_refuses_an_incomplete_attempt(tmp_path):
    respond, _ = _scripted("```sql\nSELECT nope\n```", "```sql\nSELECT 42\n```")
    R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])})), Q, 1)
    for f in (tmp_path / "raw").glob("Q001_r1_t1*"):
        f.unlink()                   # the fix turn never happened
    with pytest.raises(ValueError, match="incomplete"):
        R.attempt_from_raw(_ctx(tmp_path, MockClient(lambda m: None), FakeExecutor({})), Q, 1, "x")
