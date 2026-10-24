"""Instruction patch of a tuned cell (T14 second unit, decisions/2026-10-23-tuning-instructions.md).

``semantic/tuning/<cell>.instructions.yaml`` holds two lists of ``{id, text[, why]}``:

- ``answer_requirements`` are numbered on after the last item of the frozen system prompt;
- ``syntax_notes`` are bullets after the cell's syntax notes.

Each item keeps its id in the message (items refer to one another by id); ``why`` is the
author's rationale and is not sent. ``harness/prompt.py`` stays byte for byte ``harness-v1``:
the patch is applied around ``prompt.system_message``, and a cell without a patch gets exactly
the message it had before.
"""

from __future__ import annotations

import re
from pathlib import Path

from harness import prompt as P

KEYS = {"answer_requirements", "syntax_notes"}
ITEM_KEYS = {"id", "text", "why"}


def load(path: Path) -> dict:
    import yaml

    if not path.exists():
        raise FileNotFoundError(f"{path} missing: the cell's instruction patch is not written yet")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not set(doc) <= KEYS:
        raise ValueError(f"{path}: only {sorted(KEYS)} are allowed")
    for key, items in doc.items():
        if not isinstance(items, list) or any(not isinstance(x, dict) or not {"id", "text"} <= set(x)
                                              or not set(x) <= ITEM_KEYS for x in items):
            raise ValueError(f"{path}: {key} must be a list of {{id, text[, why]}}")
    return doc


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def system_message(context_text: str, syntax_text: str, context_lang: str | None, patch: dict) -> str:
    last = int(re.findall(r"^(\d+)\. ", P.SYSTEM_PROMPT, re.MULTILINE)[-1])
    requirements = "".join(f"\n{last + i}. （{x['id']}）{_one_line(x['text'])}"
                           for i, x in enumerate(patch.get("answer_requirements") or [], 1))
    notes = "".join(f"\n- （{x['id']}）{_one_line(x['text'])}" for x in patch.get("syntax_notes") or [])
    base = P.system_message(context_text, syntax_text.strip() + notes, context_lang)
    assert base.startswith(P.SYSTEM_PROMPT)
    return P.SYSTEM_PROMPT + requirements + base[len(P.SYSTEM_PROMPT):]
