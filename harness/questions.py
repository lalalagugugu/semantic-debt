"""Questions and reference results, read from ``$SEMDEBT_EVAL_DIR``.

Two question sets:

- ``zh`` (the Chinese set every self-built cell answers): ``questions/*.yaml``
  (``cube_100.yaml`` + ``new.yaml``), text ``text_zh``; each ref's result is the
  CSV at ``result_path``, typed with the column types in ``refs/MANIFEST.json``.
- ``en`` (the English anchors R-EN / L1c-EN): the external benchmark's original
  questions from ``vendor/cube/text_to_sql_benchmark.json``, n = 99 (q33 excluded,
  as in the benchmark's published numbers). Their reference results are not built
  yet, so they are loaded without refs (scoring pending, see open question T11-3).

The harness never interprets ``rules``: it is passed to the scorer exactly as the
question record carries it (decisions/2026-10-14-scorer-contract-and-acceptance.md).
A record without ``rules`` (the 100 ``cube`` questions as of 2026-10-16) is loaded
with ``rules=None`` and is not scored deterministically; the harness does not derive
``ordered`` / ``top_n`` from SQL or CSV order (pipeline contract, correction 1).
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
    rules: dict | None              # passed through to the scorer untouched; None = absent in the bank
    lang: str = "zh"
    scoring: str = "deterministic"  # "deterministic" or "judge" (question-bank field)
    meta: dict = field(default_factory=dict)

    @property
    def pending(self) -> str | None:
        """Why a returned row set cannot be scored here, or None if it can."""
        if self.scoring != "deterministic":
            return "judge"
        if self.refs is None:
            return "no_refs"
        if self.rules is None:
            return "no_rules"
        return None


def eval_dir() -> Path:
    root = os.environ.get("SEMDEBT_EVAL_DIR")
    if not root:
        raise RuntimeError("SEMDEBT_EVAL_DIR is not set")
    return Path(root).expanduser()


def eval_commit(root: Path | None = None) -> str:
    """Short commit of the question bank, with ``-dirty`` when the tree has local changes."""
    root = root or eval_dir()
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "questions", "refs", "vendor"],
                           capture_output=True, text=True, check=True).stdout.strip()
    return f"{head}-dirty" if dirty else head


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
    refs = []
    for ref in record["refs"]:
        entry = manifest.get(ref["result_path"])
        if entry is None:
            raise ValueError(f"{record['id']}: {ref['result_path']} is not in refs/MANIFEST.json")
        refs.append(read_ref_csv(root / ref["result_path"], entry["columns"]))
    return Question(qid=str(record["id"]), text=record["text_zh"], refs=refs, rules=record.get("rules"),
                    lang="zh", scoring=record["scoring"],
                    meta={"source": record["source"], "type": record["type"], "split": record.get("split")})


def load_zh(root: Path) -> list[Question]:
    manifest = _manifest(root)
    records = []
    for path in sorted((root / "questions").glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        records += data["questions"] if isinstance(data, dict) else data
    return [from_record(r, manifest, root) for r in records]


def load_en(root: Path) -> list[Question]:
    data = json.loads((root / "vendor" / "cube" / "text_to_sql_benchmark.json").read_text(encoding="utf-8"))
    return [Question(qid=f"EN{int(q['id']):02d}", text=q["question"], refs=None, rules=None, lang="en",
                     meta={"level": q.get("level")})
            for q in data["questions"] if int(q["id"]) not in EN_EXCLUDED]


def load_questions(root: Path | None = None, lang: str = "zh") -> list[Question]:
    root = root or eval_dir()
    questions = {"zh": load_zh, "en": load_en}[lang](root)
    ids = [q.qid for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate question ids in the question bank")
    return sorted(questions, key=lambda q: q.qid)

