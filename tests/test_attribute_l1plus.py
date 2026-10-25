"""Frozen taxonomy, dry-run budget gate and metadata-only material preparation."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import attribute_l1plus as A  # noqa: E402


@pytest.mark.parametrize("category", (*A.CATEGORIES, A.SUSPICIOUS))
def test_exact_labels(category):
    obj = {"category": category, "data_quality_related": True}
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


@pytest.mark.parametrize("bad", [None, "是", 1])
def test_auxiliary_flag_requires_boolean(bad):
    obj = {"category": A.CATEGORIES[0], "data_quality_related": bad}
    assert A.parse_labels(json.dumps(obj))[0] is None


def test_paid_run_rejects_changed_material_before_client(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "prepare", lambda: ("s", ["u"], {"calls": 1, "questions": 1, **{k: "x" for k in ("semantic_tag", "semantic_commit", "eval_tag", "eval_commit", "source_system_sha256", "codebook_sha256", "system_sha256")}}))
    monkeypatch.setattr(A.A, "dry_run", lambda *args: 2)
    def forbidden(*args):
        pytest.fail("paid entry reached despite drift")
    monkeypatch.setattr(A, "run_paid", forbidden)
    path = tmp_path / "preflight.json"
    path.write_text('{"calls":2}')
    assert A.main(["--budget", "3", "--run-id", "test", "--preflight", str(path)]) == 2


def test_request_bound_uses_uncached_bytes_and_default_max_output():
    assert A.request_bound("s", "u") > 65536 * 4 / 1e6
    assert A.request_bound("中文", "u") > A.request_bound("s", "u")


def test_serial_run_stops_before_request_exceeds_budget(monkeypatch, tmp_path):
    from harness.client import MockClient
    (tmp_path / "runs").mkdir()
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(A, "REPO", tmp_path)
    monkeypatch.setattr(A.R, "raw_root", lambda: raw)
    monkeypatch.setattr(A.R, "is_peak", lambda *args: False)
    monkeypatch.setattr(A, "request_bound", lambda *args: 4.0)
    client = MockClient(lambda _: pytest.fail("budget allowed request"))
    monkeypatch.setattr(A, "DeepSeekClient", lambda *args, **kwargs: client)
    # MockClient does not implement before_request; wrap its existing chat boundary.
    def chat(messages):
        client.before_request()
        pytest.fail("request escaped budget boundary")
    monkeypatch.setattr(client, "chat", chat)
    manifest = {"system_sha256": "s", "codebook_sha256": "c",
                "items": [{"qid": "Q01", "rep": 1, "user_sha256": "u"}]}
    assert A.run_paid("offline-test", "s", ["u"], manifest, 3) == 1
    summary = json.loads((tmp_path / "runs/offline-test/summary.json").read_text())
    assert summary["known_cost_cny"] == summary["uncertain_cost_bound_cny"] == 0
    with pytest.raises(ValueError, match="already exists"):
        A.run_paid("offline-test", "s", ["u"], manifest, 3)
