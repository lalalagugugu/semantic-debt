"""Frozen taxonomy, dry-run budget gate and metadata-only material preparation."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import attribute_l1plus as A  # noqa: E402


@pytest.mark.parametrize("category", (*A.CATEGORIES, A.SUSPICIOUS))
def test_exact_labels(category):
    obj = {"category": category}
    assert A.parse_labels(json.dumps(obj, ensure_ascii=False)) == (obj, None)


@pytest.mark.parametrize("text", [
    '{"category":"文字仍有两种以上读法"}',
    '{"category":"只是呈现不同","note":"free text"}',
    '[]', 'not JSON', '{"category":null}',
])
def test_nonfrozen_or_extra_labels_are_unparsed(text):
    obj, why = A.parse_labels(text)
    assert obj is None and why


def test_suspicion_stays_outside_five_categories():
    assert len(A.CATEGORIES) == 5
    assert A.SUSPICIOUS not in A.CATEGORIES


def test_budget_checked_even_in_dry_run(monkeypatch):
    monkeypatch.setattr(A.A, "dry_run", lambda *args: 3.01)
    with pytest.raises(ValueError, match="exceeds budget"):
        A.estimate_with_budget("s", ["u"], 4500, .95, 3)
    with pytest.raises(ValueError, match="outside approved"):
        A.estimate_with_budget("s", ["u"], 4500, .95, 4)


def test_dry_run_never_constructs_client(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("dry-run constructed a paid client")
    monkeypatch.setattr(A.A, "DeepSeekClient", forbidden)
    manifest = {"calls": 1, "questions": 1, "semantic_tag": "t", "semantic_commit": "s",
                "eval_tag": "e", "eval_commit": "c", "source_system_sha256": "h",
                "codebook_sha256": "b", "system_sha256": "a"}
    monkeypatch.setattr(A, "prepare", lambda: ("s", ["u"], manifest.copy()))
    monkeypatch.setattr(A.A, "dry_run", lambda *args: 2)
    path = tmp_path / "manifest.json"
    assert A.main(["--dry-run", "--budget", "3", "--manifest", str(path)]) == 0
    assert json.loads(path.read_text())["paid_calls"] == 0
    assert A.main(["--dry-run", "--budget", "3", "--manifest", str(path)]) == 2


def test_original_system_drift_refused():
    with pytest.raises(RuntimeError, match="system message differs"):
        A.validate_source([], {}, "full", "changed instructions")
