"""Questions and reference results, read from ``$SEMDEBT_EVAL_DIR``.

Two question sets:

- ``zh`` (the Chinese set every self-built cell answers): ``questions/*.yaml``
  (``cube_100.yaml`` + ``new.yaml``), text ``text_zh``; each ref's result is the
  CSV at ``result_path``, typed with the column types in ``refs/MANIFEST.json``.
- ``en`` (the English anchors R-EN / L1c-EN): the external benchmark's original
  questions from ``vendor/cube/text_to_sql_benchmark.json``, n = 99 (q33 excluded,
  as in the benchmark's published numbers). Scored against the benchmark's own
  original reference (built by ``harness/anchor_refs.py``), with our current
  revised references as a second, comparison column
  (decisions/2026-10-16-q79-release-and-anchor-refs.md §2).

``rules`` are reference metadata and are passed to the scorer untouched
(decisions/2026-10-14-scorer-contract-and-acceptance.md). A ref may carry its own
``rules``, which replace the question's ``rules`` wholesale for that ref
(decisions/2026-10-16-per-reference-rules.md); the harness hands both to the
scorer as ``rules`` + ``reference_rules`` and never merges, infers or rewrites
them (``selection`` included). The loader refuses a bank whose MANIFEST records
a different effective ``rules`` for a ref than the question file.
Question text never reaches a committed log; only ``qid`` does.
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# The benchmark's published n = 99 excludes q33 (its reference exceeds their
# ClickHouse memory quota; vendor/cube/REPORT.md). The anchors reproduce that n.
EN_EXCLUDED = frozenset({33})
CSV_NULL = "\\N"


@dataclass(frozen=True)
class Question:
    qid: str
    text: str
    refs: list | None               # acceptable result sets, each a list of rows; None = not built
    rules: dict | None              # question-level rules, untouched; None = not available
    lang: str = "zh"
    scoring: str = "deterministic"  # "deterministic" or "judge" (question-bank field)
    meta: dict = field(default_factory=dict)
    ref_rules: list | None = None   # per ref: that ref's own rules, or None = use ``rules``
    revised: "Question | None" = None   # anchors only: the same answer scored on our revised refs

    @property
    def pending(self) -> str | None:
        """Why a returned row set cannot be scored here, or None if it can."""
        if self.scoring != "deterministic":
            return "judge"
        if self.refs is None:
            return "no_refs"
        if self.rules is None:
            return self.meta.get("rules_pending", "no_rules")
        return None


def eval_dir() -> Path:
    root = os.environ.get("SEMDEBT_EVAL_DIR")
    if not root:
        raise RuntimeError("SEMDEBT_EVAL_DIR is not set")
    return Path(root).expanduser()


BANK_PATHS = ("questions", "refs", "vendor")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def eval_commit(root: Path | None = None) -> str:
    """Short commit of the question bank's content that the harness reads.

    Clean checkout → its HEAD. If ``questions/``, ``refs/`` or ``vendor/`` have local
    changes but are byte-identical to ``origin/main`` (a checkout someone else is
    working in), that commit is reported as ``<sha>@origin/main``; otherwise
    ``<head>-dirty``.
    """
    root = root or eval_dir()
    head = _git(root, "rev-parse", "--short", "HEAD").stdout.strip()
    if not _git(root, "status", "--porcelain", "--", *BANK_PATHS).stdout.strip():
        return head
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "--", *BANK_PATHS).stdout.strip()
    same = _git(root, "diff", "--quiet", "origin/main", "--", *BANK_PATHS).returncode == 0
    if same and not untracked:
        return _git(root, "rev-parse", "--short", "origin/main").stdout.strip() + "@origin/main"
    return f"{head}-dirty"


# ---------------------------------------------------------------------------
# Reference CSVs


def _base_type(t: str) -> str:
    m = re.fullmatch(r"(?:Nullable|LowCardinality)\((.*)\)", t)
    return _base_type(m.group(1)) if m else t


def parse_value(text: str, ch_type: str):
    """One CSV cell back to the value the engine returned (JSONCompact semantics)."""
    if text == CSV_NULL:
        return None
    base = _base_type(ch_type)
    if re.fullmatch(r"U?Int\d+", base):
        return int(text)
    if re.fullmatch(r"Float\d+|Decimal.*|BFloat16", base):
        return float(text)
    if base == "Bool":
        return text == "True"
    return text


def read_ref_csv(path: Path, columns: list[dict]) -> list[list]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header != [c["name"] for c in columns]:
            raise ValueError(f"{path}: header {header} does not match MANIFEST columns")
        return [[parse_value(v, c["type"]) for v, c in zip(row, columns, strict=True)] for row in reader]


def _manifest(root: Path) -> dict[str, dict]:
    data = json.loads((root / "refs" / "MANIFEST.json").read_text(encoding="utf-8"))
    return {r["result_path"]: r for r in data["records"]}


# ---------------------------------------------------------------------------
# Loading


def from_record(record: dict, manifest: dict[str, dict], root: Path) -> Question:
    refs, ref_rules = [], []
    for ref in record["refs"]:
        entry = manifest.get(ref["result_path"])
        if entry is None:
            raise ValueError(f"{record['id']}: {ref['result_path']} is not in refs/MANIFEST.json")
        own = ref.get("rules")
        effective = own if own is not None else record.get("rules")
        if "rules" in entry and entry["rules"] != effective:
            raise ValueError(f"{record['id']}: rules for {ref['result_path']} differ between the question file "
                             "and refs/MANIFEST.json; the question bank must fix this")
        refs.append(read_ref_csv(root / ref["result_path"], entry["columns"]))
        ref_rules.append(own)
    return Question(qid=str(record["id"]), text=record["text_zh"], refs=refs, rules=record.get("rules"),
                    lang="zh", scoring=record["scoring"],
                    meta={"source": record["source"], "type": record["type"], "split": record.get("split"),
                          "text_en": record["text_en"]},
                    ref_rules=ref_rules if any(r is not None for r in ref_rules) else None)


def load_zh(root: Path) -> list[Question]:
    manifest = _manifest(root)
    records = []
    for path in sorted((root / "questions").glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        records += data["questions"] if isinstance(data, dict) else data
    return [from_record(r, manifest, root) for r in records]


def vendor_questions(root: Path) -> list[dict]:
    return json.loads((root / "vendor" / "cube" / "text_to_sql_benchmark.json").read_text(encoding="utf-8"))["questions"]


def anchor_mapping(root: Path, zh: list[Question] | None = None) -> dict[int, str]:
    """Benchmark question id → our question id, matched on the English text.

    Built from the texts themselves (our ``text_en`` is the benchmark's question
    verbatim), not from a numbering scheme, so an exclusion or renumbering cannot
    shift it. Every benchmark question must match exactly one of ours.
    """
    zh = zh if zh is not None else load_zh(root)
    by_text: dict[str, list[str]] = {}
    for q in zh:
        by_text.setdefault(q.meta["text_en"].strip(), []).append(q.qid)
    mapping = {}
    for vq in vendor_questions(root):
        hits = by_text.get(vq["question"].strip(), [])
        if len(hits) != 1:
            raise ValueError(f"benchmark q{vq['id']}: {len(hits)} questions in the bank have its English text")
        mapping[int(vq["id"])] = hits[0]
    return mapping


def effective_rules(q: Question) -> list[dict | None]:
    return [own if own is not None else q.rules for own in (q.ref_rules or [None] * len(q.refs or []))]


def anchor_rules(meta: list[dict], rows: list[list], current: Question) -> tuple[dict | None, str | None]:
    """The current question's rules for the original reference, if it has the same
    column structure (column count and return types) as one of the current refs.

    Returns (rules, None) or (None, reason). The rules are taken as they are; the
    scorer must also accept the original rows as a reference under them.
    """
    from harness.scorer import score_detailed

    types = [c["type"] for c in meta]
    for rules in effective_rules(current):
        if rules is not None and list(rules.get("value_types", [])) == types:
            try:
                ok = score_detailed(rows, [rows], rules).outcome == "correct"
            except (ValueError, TypeError) as exc:
                return None, f"rules_invalid_for_original: {exc}"
            return (rules, None) if ok else (None, "rules_invalid_for_original: self-match failed")
    return None, "structure_differs"


def load_en(root: Path, anchors: Path | None = None) -> list[Question]:
    from harness.anchor_refs import load_anchor_ref

    zh = {q.qid: q for q in load_zh(root)}
    mapping = anchor_mapping(root, list(zh.values()))
    out = []
    for vq in vendor_questions(root):
        vid = int(vq["id"])
        if vid in EN_EXCLUDED:
            continue
        current = zh[mapping[vid]]
        revised = Question(qid=current.qid, text="", refs=current.refs, rules=current.rules, lang="en",
                           scoring=current.scoring, ref_rules=current.ref_rules)
        meta = {"vendor_id": vid, "bank_qid": current.qid, "level": vq.get("level")}
        original = load_anchor_ref(vid, anchors)
        refs, rules = None, None
        if original is not None:
            columns, rows = original
            refs = [rows]
            rules, reason = anchor_rules(columns, rows, current)
            if reason:
                meta["rules_pending"] = "anchor_" + reason.split(":")[0]
                meta["rules_pending_detail"] = reason
        out.append(Question(qid=f"EN{vid:02d}", text=vq["question"], refs=refs, rules=rules, lang="en",
                            scoring=current.scoring, meta=meta, revised=revised))
    return out


def load_questions(root: Path | None = None, lang: str = "zh") -> list[Question]:
    root = root or eval_dir()
    questions = {"zh": load_zh, "en": load_en}[lang](root)
    ids = [q.qid for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate question ids in the question bank")
    return sorted(questions, key=lambda q: q.qid)

