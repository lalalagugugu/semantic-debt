"""Questions and reference results, read from ``$SEMDEBT_EVAL_DIR/questions/``.

The harness never interprets ``rules``: it is passed to the scorer exactly as the
question record carries it (``ordered``, ``top_n``, ``tie_columns``,
``value_kinds``, ``value_types`` ...; decisions/2026-10-14-scorer-contract-and-acceptance.md).
Question text never reaches a committed log; only ``qid`` does.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Question:
    qid: str
    text: str
    refs: list                      # acceptable result sets, each a list of rows
    rules: dict                     # passed through to the scorer untouched
    lang: str = "zh"
    meta: dict = field(default_factory=dict)


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
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "questions", "refs"],
                           capture_output=True, text=True, check=True).stdout.strip()
    return f"{head}-dirty" if dirty else head


def _records(path: Path) -> list[dict]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    data = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "questions" in data:
        data = data["questions"]
    return data if isinstance(data, list) else [data]


def from_record(record: dict, lang: str = "zh") -> Question:
    """Map one question record to :class:`Question`.

    FORMAT NOT YET CONFIRMED against the question bank (reading it was blocked in
    this session, see the T11 card record). Expected keys: ``id``, the question
    text, ``refs`` (list of result sets) and ``rules``.
    """
    qid = str(record["id"])
    text = record.get(f"question_{lang}") or record["question"]
    return Question(qid=qid, text=text, refs=record["refs"], rules=record["rules"], lang=lang)


def load_questions(root: Path | None = None, lang: str = "zh") -> list[Question]:
    qdir = (root or eval_dir()) / "questions"
    files = sorted(p for p in qdir.rglob("*") if p.suffix in {".json", ".jsonl", ".yaml", ".yml"})
    questions = [from_record(r, lang) for p in files for r in _records(p)]
    ids = [q.qid for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate question ids in the question bank")
    return sorted(questions, key=lambda q: q.qid)
