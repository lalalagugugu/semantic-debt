"""T19c self-rated confidence: reply parsing, AUC and the frozen verdict rules (harness/confidence.py)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness import confidence as C  # noqa: E402


def test_tier_parses_with_or_without_a_fence():
    assert C.parse_tier('{"confidence": "B", "reason": "口径可能不同"}') == ("B", None)
    assert C.parse_tier('```json\n{"confidence": "A", "reason": "x"}\n```') == ("A", None)


def test_anything_else_is_unparsed_not_repaired():
    for bad in ('A', '{"confidence": "D", "reason": "x"}', '{"confidence": "A"}',
                '{"confidence": "A", "reason": "x", "extra": 1}', '[]', '好的：{"confidence": "A", "reason": "x"}'):
        tier, why = C.parse_tier(bad)
        assert tier is None and why


def test_auc_counts_ties_as_half():
    assert C.auc([3, 4], [1, 2]) == 1.0
    assert C.auc([1], [1]) == 0.5
    assert C.auc([1, 0], [0, 1]) == 0.5
    assert C.auc([], [1]) is None


def test_confirmed():
    v, _ = C.verdict({"A": (150, 140), "B": (100, 60), "C": (44, 10)}, 294)
    assert v.startswith("证实")


def test_refuted_by_flat_accuracy_and_by_share_of_a():
    assert C.verdict({"A": (100, 70), "B": (100, 65), "C": (94, 62)}, 294)[0].startswith("证伪")
    assert C.verdict({"A": (240, 230), "B": (40, 20), "C": (14, 2)}, 294)[0].startswith("矛盾")   # both hold
    assert C.verdict({"A": (240, 170), "B": (54, 30), "C": (0, 0)}, 294)[0].startswith("证伪")


def test_empty_c_cannot_confirm():
    v, _ = C.verdict({"A": (200, 190), "B": (94, 9), "C": (0, 0)}, 294)
    assert v.startswith("介于")
