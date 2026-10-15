"""Mock end-to-end: 5 self-made questions → mock model → real chDB → scorer → log.

The questions are constructed here (not from the question bank); references are
computed by a differently written query so the scorer really compares results.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness import run_direct as R  # noqa: E402
from harness.cells import CELLS  # noqa: E402
from harness.client import MockClient  # noqa: E402
from harness.questions import Question  # noqa: E402

CHDB = Path(os.environ.get("SEMDEBT_DATA_DIR", "/nonexistent")).expanduser() / "chdb"
pytestmark = pytest.mark.skipif(not CHDB.exists() or not (REPO / "build/contexts/SQL-L1.5S.yaml").exists(),
                                reason="needs chDB and rendered contexts")

# qid → (question text, reference query, scripted model answers, rules)
CASES = {
    "E1": ("门店一共有多少家", "SELECT count() FROM (SELECT DISTINCT * FROM ads.dim_store)",
           ["```sql\nSELECT count() FROM ads.dim_store\n```\n假设：无"],
           {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["count"], "value_types": ["UInt64"]}),
    "E2": ("有多少个渠道", "SELECT count() FROM (SELECT DISTINCT * FROM ads.dim_channel)",
           ["```sql\nSELECT count() FROM ads.dim_chanel\n```\n假设：无",
            "```sql\nSELECT count() FROM ads.dim_channel\n```\n假设：无"],
           {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["count"], "value_types": ["UInt64"]}),
    "E3": ("门店数加一", "SELECT count() FROM ads.dim_store",
           ["```sql\nSELECT count() + 1 FROM ads.dim_store\n```\n假设：多算一家"],
           {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["count"], "value_types": ["UInt64"]}),
    "E4": ("明天的天气", "SELECT 1", ["CANNOT_ANSWER"], {"ordered": False, "top_n": None}),
    "E5": ("线上明细一共多少行", "SELECT 1",
           ["```sql\nSELECT count() FROM retail.FactOnlineSales\n```\n假设：用明细表",
            "```sql\nSELECT count() FROM retail.FactOnlineSales\n```\n假设：仍用明细表"],
           {"ordered": False, "top_n": None}),
}
EXPECTED = {"E1": ("correct", "correct"), "E2": ("exec_error", "correct"), "E3": ("wrong", "wrong"),
            "E4": ("refused", "refused"), "E5": ("exec_error", "exec_error")}


def test_mock_end_to_end_five_questions(tmp_path):
    cell = CELLS["SQL-L1.5S"]
    executor = R.make_executor(cell, timeout_s=60)
    questions = []
    for qid, (text, ref_sql, _, rules) in CASES.items():
        ref = executor.execute(ref_sql)
        assert ref.ok, ref.error
        questions.append(Question(qid, text, [ref.rows], rules))
    by_text = {q.text: q.qid for q in questions}

    def respond(messages):
        qid = by_text[messages[1]["content"]]
        turn = (len(messages) - 2) // 2
        return CASES[qid][2][turn]

    ctx = R.RunContext(run_id="mock-e2e", cell=cell, client=MockClient(respond), executor=executor,
                       system=R.system_for(cell), eval_commit="fixture", harness_commit=R.harness_commit(),
                       timeout_s=60, raw_dir=tmp_path / "raw")
    path = R.run_cell(ctx, questions, reps=1, concurrency=3, runs_root=tmp_path / "runs", progress=lambda *_: None)
    recs = {r["qid"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())}
    assert set(recs) == set(CASES)
    for qid, (first, final) in EXPECTED.items():
        assert (recs[qid]["first"], recs[qid]["final"]["outcome"]) == (first, final), qid
    assert recs["E5"]["final"]["error_class"] == "scope_violation"
    assert recs["E5"]["n_calls"] == 2
    log = path.read_text(encoding="utf-8")
    assert not any(text in log for text, *_ in CASES.values())
    # cache-hit tokens recorded (mock imitates the prefix cache after the first call)
    assert sum(r["usage"]["cache_hit_tokens"] for r in recs.values()) > 0
    summary = R.summarize(path)
    assert summary["outcomes"] == {"correct": 2, "wrong": 1, "refused": 1, "exec_error": 1}
    assert summary["scope_violations_any_turn"] == 1
