"""Per-question failure dump for one T13 cell, for attribution by hand.

Reads only the run log, runs-raw (model responses and stored row sets) and the question
bank checkout of ``--eval-tag``; never opens chDB. Writes a JSON dump (question text,
reference SQL and rows, each failing attempt's SQL, assumption, scorer diagnosis and
returned rows) to ``--out``, which goes outside the repository: it holds question text.

    uv run python scripts/t13_failure_dump.py --run 20261018-T13-sql-direct-01 --cell SQL-L0 \\
        --out "$TMPDIR/t13-L0-dump.json"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402
from harness.questions import eval_dir, load_questions, verify_eval_tag  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SHOW_ROWS = 6


def raw_dir(run: str, cell: str) -> Path:
    return Path(os.environ["SEMDEBT_DATA_DIR"]).expanduser() / "runs-raw" / run / cell


def bank_records() -> dict[str, dict]:
    out = {}
    for f in sorted((eval_dir() / "questions").glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "questions" in data:
            out.update({q["id"]: q for q in data["questions"] if isinstance(q, dict)})
    return out


def is_text(t: str) -> bool:
    return "String" in t or "Enum" in t


def codes_only(cand_cols: list[dict], ref_types: list[str], required: list[int] | None) -> bool:
    """The answer carries no text column where a required reference column is text."""
    req = required if required is not None else list(range(len(ref_types)))
    return any(is_text(ref_types[i]) for i in req if i < len(ref_types)) and not any(is_text(c["type"]) for c in cand_cols)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--cell", required=True)
    ap.add_argument("--eval-tag", default="eval-v1.1")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    verify_eval_tag(args.eval_tag)
    qs = {q.qid: q for q in load_questions()}
    bank = bank_records()
    raw = raw_dir(args.run, args.cell)
    recs = [json.loads(l) for l in (REPO / "runs" / args.run / f"{args.cell}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    dump = {}
    for r in sorted(recs, key=lambda r: (r["qid"], r["rep"])):
        if r.get("status") != "done" or r["final"]["outcome"] == "correct":
            continue
        q, b = qs[r["qid"]], bank[r["qid"]]
        entry = dump.setdefault(r["qid"], {
            "q_level": q.meta["q_level"], "judge": q.scoring == "judge", "low": bool(q.meta["low_discrimination"]),
            "text": b["text_zh"], "notes": b.get("scoring_notes", ""),
            "required_columns": (b.get("rules") or {}).get("required_columns"),
            "refs": [{"sql": ref["sql"], "rows": len(rows), "head": rows[:SHOW_ROWS],
                      "types": ((ref.get("rules") or b.get("rules") or {}).get("value_types"))}
                     for ref, rows in zip(b["refs"], q.refs or [[]] * len(b["refs"]))],
            "attempts": []})
        last = r["turns"][-1]
        stem = f"{r['qid']}_r{r['rep']}_t{last['turn']}"
        ex = json.loads((raw / f"{stem}.exec.json").read_text(encoding="utf-8")) if (raw / f"{stem}.exec.json").exists() else {}
        ref_types = entry["refs"][0]["types"] or []
        cols = ex.get("columns") or []
        entry["attempts"].append({
            "rep": r["rep"], "outcome": r["final"]["outcome"], "reason": r["final"]["reason"],
            "sensitivity": r["final"]["sensitivity"], "error_class": r["final"]["error_class"], "fixed": r["fixed"],
            "query": last.get("query"), "assumption": last.get("assumption"), "refused": last.get("refused"),
            "first_query": r["turns"][0].get("query") if r["fixed"] else None,
            "first_error": (r["turns"][0]["exec"].get("error_class") if r["fixed"] else None),
            "columns": cols, "rows": len(ex.get("rows") or []), "head": (ex.get("rows") or [])[:SHOW_ROWS],
            "error": ex.get("error"),
            "codes_only": bool(cols) and codes_only(cols, ref_types, entry["required_columns"])})
    Path(args.out).write_text(json.dumps(dump, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"{len(dump)} questions, {sum(len(e['attempts']) for e in dump.values())} attempts -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
