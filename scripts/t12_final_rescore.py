"""T12 final rescore: strict (eval-v1.1 + the merged scorer, as logged by
``harness.rescore``) and final (strict, minus what the old system prompt could not
ask for), for every pilot answer.

Strict is read from the rescore run logs. Final re-scores each answer that is not
correct under strict with generic relaxations, applied the same way to every
reference (decisions/2026-10-18-names-required-by-system-prompt.md §2.3 / §3,
decisions/2026-10-18-ux-conventions-and-annotation-disputes.md §1.4 / §5 / §8):

  conv   convention columns are presence-only: required columns the presentation
         revision added (required in eval-v1.1 but not in the base annotation, or
         appended after the eval-v1 reference), minus identifier keys, are dropped
         from required_columns, together with their rank rules.
  key    a key in place of a name: a required name column is swapped for the
         identifier key column of the same entity (``ProductKey`` ↔ ``ProductName``,
         matched on the reference headers), so the check is on content: the same
         objects. A key is never swapped for another entity's name.
  trunc  an extra LIMIT: every returned row matches a distinct reference row,
         fewer rows than the reference, the question asks for no Top-N, and the
         query carries a LIMIT.

Every relaxation keeps all other rules (numbers, row multiplicity, order, Top-N,
selection). Answers that are still wrong get the scorer's numeric-projection
diagnostic (``label_only``: numbers match, labels differ) so they can be checked by
hand; the hand verdicts and every attribution live in ``scripts/t12_final_verdicts.yaml``.

    SEMDEBT_EVAL_DIR=<eval-v1.1 worktree> uv run python scripts/t12_final_rescore.py \\
        --json $SEMDEBT_DATA_DIR/t12-final/final.json

Only question ids reach stdout and the JSON (no question text, no rows).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import signal
import sys
from dataclasses import replace
from itertools import permutations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import run_direct as R  # noqa: E402
from harness import scorer as S  # noqa: E402
from harness.questions import eval_dir, load_questions, pilot_ids  # noqa: E402
from harness.rescore import candidate_of  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CELLS = ("SQL-L1", "SQL-R")
RUNS = {"deepseek-flash": "20261018-T12-pilot-flash-01", "deepseek-v4-pro": "20261018-T12-pilot-pro-01"}
RESCORED = "{}-rescore-01"


def ref_files() -> dict[str, list[str]]:
    """Reference CSV paths (relative to the bank) per question, in ``q.refs`` order."""
    import yaml
    from harness.questions import question_files
    out = {}
    for f in question_files(eval_dir()):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        for rec in data["questions"] if isinstance(data, dict) else data:
            out[rec["id"]] = [r["result_path"] for r in rec.get("refs") or []]
    return out


def old_width(path: str, old_bank: Path) -> int | None:
    f = old_bank / path
    if not f.exists():
        return None
    with f.open(encoding="utf-8") as fh:
        return len(next(csv.reader(fh)))


def convention_columns(rules: dict, path: str, presentation: dict, old_bank: Path) -> list[int]:
    req = set(rules.get("required_columns") or ())
    base = set(presentation["base_required_columns"].get(path, req))
    width = old_width(path, old_bank)
    appended = {c for c in req if width is not None and c >= width}
    return sorted(((req - base) | appended) - set(rules.get("identifier_columns") or ()))


def without(rules: dict, drop: list[int]) -> dict:
    if not drop:
        return rules
    out = dict(rules)
    out["required_columns"] = [c for c in rules["required_columns"] if c not in drop]
    ranks = [c for c in rules.get("rank_columns", []) if c not in drop]
    out["rank_columns"] = ranks
    out["rankings"] = [s for s in rules.get("rankings", []) if s["column"] in ranks]
    if not out["rank_columns"]:
        out.pop("rank_columns"), out.pop("rankings", None)
    return out


def entity(header: str) -> str:
    """``t.StoreKey`` -> ``store``; ``StoreName`` / ``customer_name`` -> ``store`` / ``customer``."""
    h = header.split(".")[-1].lower().replace("_", "")
    return re.sub(r"(key|name)$", "", h)


def key_variants(rules: dict, header: list[str]) -> list[dict]:
    """Each required name column swapped for the identifier key column of the same entity."""
    ids = rules.get("identifier_columns") or []
    kinds, types = rules.get("value_kinds") or [], rules.get("value_types") or []
    out = []
    for key in ids:
        for c in rules["required_columns"]:
            if c in ids or kinds[c] != "other" or "String" not in types[c]:
                continue
            if not header[c].lower().endswith("name") or entity(header[c]) != entity(header[key]):
                continue
            req = [key if x == c else x for x in rules["required_columns"]]
            if len(set(req)) == len(req):
                out.append({**rules, "required_columns": req})
    return out


class Timeout(Exception):
    pass


def _alarm(*_):
    raise Timeout


def score(cand, q, ref_rules, limit: int = 600) -> S.ScoreResult:
    """One scorer call; a call that runs past ``limit`` seconds raises Timeout (reported, never a verdict)."""
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(limit)
    try:
        return S.score_detailed(cand, q.refs, q.rules, reference_rules=ref_rules)
    finally:
        signal.alarm(0)


def truncated_subset(cand, q, ref_rules, query: str) -> bool:
    if not isinstance(cand, list) or not cand or not re.search(r"\bLIMIT\b", query or "", re.I):
        return False
    for i, ref in enumerate(q.refs):
        rules = S._parse_rules(ref_rules[i])
        if rules.top_n is not None or rules.selection is not None or len(cand) >= len(ref):
            continue
        c, r = S._coerce_rows(cand, "c"), S._coerce_rows(ref, "r")
        rules = S._reference_labels(r, replace(rules, ordered=False, order_by=()))
        width = len(S._comparison_columns(r[0], rules))
        if len(c[0]) < width:
            continue
        if any(S._rows_match_subset(c, r, m, rules) for m in permutations(range(len(c[0])), width)):
            return True
    return False


def relax(cand, q, query: str, conv: list[list[int]], headers: list[list[str]]) -> tuple[str | None, str | None]:
    """(relaxation that makes the answer correct, diagnostic) for a non-correct strict answer."""
    if not isinstance(cand, list):
        return None, None
    base = [r or q.rules for r in (q.ref_rules or [None] * len(q.refs))]
    relaxed = [without(r, d) for r, d in zip(base, conv)]
    if any(conv) and score(cand, q, relaxed).outcome == "correct":
        return "conv", None
    for i, r in enumerate(relaxed):
        for v in key_variants(r, headers[i]):
            rr = relaxed[:i] + [v] + relaxed[i + 1:]
            if score(cand, q, rr).outcome == "correct":
                return ("conv+key" if conv[i] else "key"), None
            if truncated_subset(cand, q, rr, query):
                return ("conv+key+trunc" if conv[i] else "key+trunc"), None
    if truncated_subset(cand, q, relaxed, query):
        return ("conv+trunc" if any(conv) else "trunc"), None
    s = score(cand, q, relaxed)
    return None, s.sensitivity if s.outcome == "wrong" else s.outcome


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-bank", default=None, help="eval-v1 worktree (for the reference widths at the pilot)")
    ap.add_argument("--json", required=True)
    args = ap.parse_args()
    old_bank = Path(args.old_bank) if args.old_bank else eval_dir().parent / "eval-ro-eval-v1"
    presentation = json.loads((eval_dir() / "refs" / "PRESENTATION.json").read_text(encoding="utf-8"))
    qs = {q.qid: q for q in load_questions()}
    pilot = pilot_ids()
    conv, headers, files_of = {}, {}, ref_files()
    for qid in pilot:
        q = qs[qid]
        rules = [r or q.rules for r in (q.ref_rules or [None] * len(q.refs))]
        files = files_of[qid]
        assert len(files) == len(rules), (qid, files)
        conv[qid] = [convention_columns(r, f, presentation, old_bank) for r, f in zip(rules, files)]
        headers[qid] = []
        for f in files:
            with (eval_dir() / f).open(encoding="utf-8") as fh:
                headers[qid].append(next(csv.reader(fh)))

    out = []
    for model, run in RUNS.items():
        for cell in CELLS:
            path = REPO / "runs" / RESCORED.format(run) / f"{cell}.jsonl"
            raw = R.raw_root() / run / cell
            for rec in map(json.loads, path.read_text(encoding="utf-8").splitlines()):
                q = qs[rec["qid"]]
                row = {"model": model, "cell": cell, "qid": rec["qid"], "rep": rec["rep"],
                       "question_changed": rec.get("question_changed", False),
                       "pilot": rec["rescored_from"]["final"]["outcome"], "pilot_first": rec["rescored_from"]["first"],
                       "strict": rec["final"]["outcome"], "strict_first": rec["first"],
                       "reason": rec["final"].get("reason"), "error_class": rec["final"].get("error_class"),
                       "n_turns": len(rec["turns"])}
                for which, turn in (("final", rec["turns"][-1]), ("first", rec["turns"][0])):
                    key = "strict" if which == "final" else "strict_first"
                    if which == "first" and len(rec["turns"]) == 1:      # same candidate as final
                        how, diag = row["final_relax"], row["final_diag"]
                    elif row[key] == "wrong":
                        cand = candidate_of(turn, raw, rec["qid"], rec["rep"])
                        try:
                            how, diag = relax(cand, q, turn.get("query") or "", conv[rec["qid"]], headers[rec["qid"]])
                        except Timeout:
                            how, diag = None, "timeout"
                    else:
                        how, diag = None, None
                    row[f"{which}_relax"], row[f"{which}_diag"] = how, diag
                out.append(row)
                print(row["model"][9:], cell, row["qid"], row["rep"], row["pilot"], "->", row["strict"],
                      row["final_relax"] or "", row["final_diag"] or "", flush=True)
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps({"conv": conv, "rows": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
