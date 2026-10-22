"""T19b attribution: label parsing and the committed log line (harness/attribute_l1.py)."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness import attribute_l1 as A  # noqa: E402
from harness.client import Reply  # noqa: E402

GOOD = {"category": "口径错", "declared_assumption": False, "root_cause": 3,
        "doc_evidence": "conventions#1", "note": "自由文本"}


def test_valid_labels_parse_with_or_without_a_fence():
    assert A.parse_labels(json.dumps(GOOD, ensure_ascii=False)) == (GOOD, None)
    assert A.parse_labels("```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```")[0] == GOOD


@pytest.mark.parametrize("bad", [
    "前言 " + json.dumps(GOOD, ensure_ascii=False),      # extra text: unparsed, not repaired
    json.dumps({**GOOD, "category": "别的类"}, ensure_ascii=False),
    json.dumps({**GOOD, "root_cause": 6}),
    json.dumps({**GOOD, "root_cause": True}),
    json.dumps({**GOOD, "declared_assumption": "否"}, ensure_ascii=False),
    json.dumps({k: v for k, v in GOOD.items() if k != "doc_evidence"}, ensure_ascii=False),
    "[]",
])
def test_anything_else_is_unparsed(bad):
    labels, why = A.parse_labels(bad)
    assert labels is None and why


def _reply(content: str) -> Reply:
    return Reply(content=content, reasoning="原作答的思路", model_version="deepseek-flash", finish_reason="stop",
                 usage={"prompt_tokens": 10, "cache_hit_tokens": 0, "cache_miss_tokens": 10, "completion_tokens": 5},
                 latency_s=1.0, raw=b"{}", system_fingerprint=A.FINGERPRINT)


def test_committed_line_holds_ids_and_labels_but_no_free_text():
    rec = {"qid": "Q01", "rep": 2, "final": {"outcome": "wrong", "reason": "values"}}
    sha = {"prompt_sha256": "p", "codebook_sha256": "c", "system_sha256": "s"}
    line = A.log_line(rec, sha, "题面原文", _reply(json.dumps(GOOD, ensure_ascii=False)), "r", False, datetime(2026, 10, 22))
    assert line["status"] == "done" and line["labels"]["root_cause"] == 3
    text = json.dumps(line, ensure_ascii=False)
    assert "自由文本" not in text and "题面原文" not in text and "原作答的思路" not in text
    bad = A.log_line(rec, sha, "u", _reply("不是 JSON"), "r", False, datetime(2026, 10, 22))
    assert bad["status"] == "unparsed" and "labels" not in bad
