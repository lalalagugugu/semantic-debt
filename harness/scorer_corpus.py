"""Export real answers as a shared scorer corpus, and read it back (scorer spec v2 acceptance).

decisions/2026-10-18-scorer-spec-v2.md is accepted by two independent implementations
agreeing case by case on real answers. This module turns finished runs into those cases.
It makes no model call and runs no query: each attempt's final candidate is rebuilt from
runs-raw exactly as ``harness.rescore.candidate_of`` does (sha256 checked against the log),
and its references and rules come from the harness's own loader (``load_questions``), read
from the bank checkout of ``--eval-tag``. ``runs/`` is only read.

One JSON line per attempt::

    {"case_id": "t13/SQL-L1/Q79/r2", "source": "t13", "run_id": ..., "question_id": "Q79",
     "cell": "SQL-L1", "round": 2, "turn": 0, "judge": false,
     "candidate": <row set> | "CANNOT_ANSWER" | {"exec_error": "<engine message>"},
     "refs": [<row set>, ...], "rules": [<effective rules of each ref>, ...],
     "value_types": [<value_types of each ref's effective rules>, ...],
     "bank": "eval-v1.1@938957f"}

A row set is a list of rows (lists). Values JSON cannot carry natively are typed objects:
``{"$date": ...}``, ``{"$datetime": ...}``, ``{"$decimal": ...}``, ``{"$float": "nan" | "inf" |
"-inf"}``. Strings stay strings: a date the engine returned as text is text, as it is for
the scorer. ``question_changed: true`` marks an answer to an older wording of the question
(source log's ``question_sha256`` differs from the bank's text; Q69 in the T12 pilot runs).
Cases whose source line has ``model`` set carry it (the pilot ran two models).
The corpus holds no question text, but it holds reference rows: it stays under
``$SEMDEBT_DATA_DIR/scorer-corpus/``, never in the repository.

    uv run python -m harness.scorer_corpus --eval-tag eval-v1.1 --source t13 \\
        --run 20261018-T13-sql-direct-01
    uv run python -m harness.scorer_corpus --eval-tag eval-v1.1 --source pilot288 \\
        --run 20261018-T12-pilot-flash-01:flash --run 20261018-T12-pilot-pro-01:pro
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import run_direct as R  # noqa: E402
from harness.questions import Question, effective_rules, load_questions, verify_eval_tag  # noqa: E402
from harness.rescore import candidate_of  # noqa: E402
from harness.scorer import REFUSAL, ExecError  # noqa: E402

# ---------------------------------------------------------------------------
# Values


def encode_value(v):
    if isinstance(v, float) and not math.isfinite(v):
        return {"$float": "nan" if math.isnan(v) else ("inf" if v > 0 else "-inf")}
    if isinstance(v, datetime):           # before date: datetime is a date
        return {"$datetime": v.isoformat()}
    if isinstance(v, date):
        return {"$date": v.isoformat()}
    if isinstance(v, Decimal):
        return {"$decimal": str(v)}
    if isinstance(v, (list, tuple)):
        return [encode_value(x) for x in v]
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    raise TypeError(f"no corpus encoding for {type(v).__name__}: {v!r}")


_FLOATS = {"nan": math.nan, "inf": math.inf, "-inf": -math.inf}
_TAGS = {"$date": date.fromisoformat, "$datetime": datetime.fromisoformat,
         "$decimal": Decimal, "$float": _FLOATS.__getitem__}


def decode_value(v):
    if isinstance(v, dict):
        if len(v) != 1 or next(iter(v)) not in _TAGS:
            raise ValueError(f"not a typed value: {v!r}")
        (tag, text), = v.items()
        return _TAGS[tag](text)
    if isinstance(v, list):
        return [decode_value(x) for x in v]
    return v


def encode_candidate(c):
    if isinstance(c, ExecError):
        return {"exec_error": c.message}
    if isinstance(c, str):
        if c != REFUSAL:
            raise ValueError(f"unexpected string candidate {c!r}")
        return c
    return encode_value(c)


def decode_candidate(c):
    if isinstance(c, dict):
        return ExecError(c["exec_error"])
    if isinstance(c, str):
        return c
    return decode_value(c)


# ---------------------------------------------------------------------------
# Export


def case_of(rec: dict, q: Question, raw_dir: Path, source: str, bank: str, label: str | None = None) -> dict:
    last = rec["turns"][-1]
    rules = effective_rules(q) if q.refs is not None else []
    parts = [source, *([label] if label else []), rec["cell"], rec["qid"], f"r{rec['rep']}"]
    case = {
        "case_id": "/".join(parts), "source": source, "run_id": rec["run_id"],
        "question_id": rec["qid"], "cell": rec["cell"], "round": rec["rep"], "turn": last["turn"],
        "judge": q.scoring == "judge",
        "candidate": encode_candidate(candidate_of(last, raw_dir, rec["qid"], rec["rep"])),
        "refs": encode_value(q.refs) if q.refs is not None else None,
        "rules": rules,
        "value_types": [(r or {}).get("value_types") for r in rules],
        "bank": bank,
    }
    if label:
        case["model"] = label
    if "question_sha256" in rec and rec["question_sha256"] != R.sha256(q.text):
        case["question_changed"] = True
    return case


def export_run(run_id: str, source: str, questions: dict[str, Question], bank: str,
               label: str | None = None, runs_root: Path | None = None, raw_root: Path | None = None) -> list[dict]:
    """Every ``done`` attempt of every cell of a run, in (cell, qid, rep) order of the log."""
    root = (runs_root or R.REPO / "runs") / run_id
    cases = []
    for log in sorted(root.glob("*.jsonl")):
        raw_dir = (raw_root or R.raw_root()) / run_id / log.stem
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("status") != "done":
                raise ValueError(f"{log}: {rec['qid']} r{rec['rep']} is not done; the corpus takes finished attempts only")
            if rec["cell"] != log.stem:
                raise ValueError(f"{log}: line for cell {rec['cell']}")
            cases.append(case_of(rec, questions[rec["qid"]], raw_dir, source, bank, label))
    return cases


def write_corpus(cases: list[dict], path: Path) -> None:
    ids = [c["case_id"] for c in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate case_id")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False, allow_nan=False) + "\n")


# ---------------------------------------------------------------------------
# Read back


def load_corpus(path: Path) -> list[dict]:
    """Cases with ``candidate`` and ``refs`` decoded back to what the scorer receives:
    rows as lists of Python values, ``ExecError`` for an execution error, ``REFUSAL`` for
    a refusal. Everything else is as written."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            c["candidate"] = decode_candidate(c["candidate"])
            c["refs"] = decode_value(c["refs"]) if c["refs"] is not None else None
            out.append(c)
    return out


def corpus_dir() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        raise RuntimeError("SEMDEBT_DATA_DIR is not set")
    return Path(root).expanduser() / "scorer-corpus"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eval-tag", required=True, help="refuse to start unless the bank is exactly this tag's content")
    ap.add_argument("--source", required=True, help="corpus name: case_id prefix and output file stem")
    ap.add_argument("--run", action="append", required=True,
                    help="run id, optionally RUN:LABEL (label goes into case_id and 'model'); repeatable")
    args = ap.parse_args(argv)
    commit = verify_eval_tag(args.eval_tag)
    bank = f"{args.eval_tag}@{commit[:7]}"
    questions = {q.qid: q for q in load_questions(lang="zh")}
    cases = []
    for spec in args.run:
        run_id, _, label = spec.partition(":")
        cases += export_run(run_id, args.source, questions, bank, label or None)
    path = corpus_dir() / f"{args.source}.jsonl"
    write_corpus(cases, path)
    kinds = {"rows": 0, "refusal": 0, "exec_error": 0}
    for c in cases:
        cand = c["candidate"]
        kinds["refusal" if cand == REFUSAL else "exec_error" if isinstance(cand, dict) else "rows"] += 1
    print(f"{len(cases)} cases -> {path}  ({bank})")
    print(f"  candidates: {kinds}; judge: {sum(c['judge'] for c in cases)}; "
          f"question_changed: {sum(bool(c.get('question_changed')) for c in cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
