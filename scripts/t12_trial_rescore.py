"""T12 trial re-score (not the official one): T05b's required_columns annotation,
injected into each reference's rules in memory only, never written to the bank.

Rebuilds every stored pilot answer from runs-raw (sha256-checked, as in
harness/rescore.py) and scores its final turn three ways:

  strict     the scorer with the bank's rules as they are (all reference columns required)
  required   the same rules plus T05b's ``required_columns`` per reference
  upper      strict correct, or a match after projecting the reference onto a subset of
             its columns (scripts/t12_column_diagnostic.py; an upper bound, not a score)
  names      (--identifier-names) as ``required``, but where T05b marked a key column
             required and the object's name as a non-required alt_identifier, the name is
             required instead (decisions/2026-10-18-reference-columns-asked-only.md §5)

Judge questions are out of every denominator, refusals and exec errors included
(decisions/2026-10-18-judge-stratum-and-t12-audit.md §1). ``--from-json`` re-prints
the tables from a saved ``--json-out`` without re-scoring.

Run against the scorer under test by putting its tree first on the path:

    PYTHONPATH=<scorer tree> uv run python scripts/t12_trial_rescore.py \\
        --annotation "$SEMDEBT_DATA_DIR/handoff-claude/T05b-required-columns.json"
"""
from __future__ import annotations

import argparse
import collections
import copy
import dataclasses
import itertools
import json
import os
import warnings
from pathlib import Path

import yaml

from harness import run_direct as R
from harness.questions import eval_dir, load_questions, question_files
from harness.rescore import candidate_of
from harness.scorer import score_detailed

RUNS = {"flash": "20261018-T12-pilot-flash-01", "pro": "20261018-T12-pilot-pro-01"}
CELLS = ("SQL-R", "SQL-L1")
REPO = Path(__file__).resolve().parent.parent


def ref_paths(root: Path) -> dict[str, list[str]]:
    out = {}
    for f in question_files(root):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        for rec in data["questions"] if isinstance(data, dict) else data:
            out[str(rec["id"])] = [r["result_path"] for r in rec["refs"]]
    return out


def names_for_keys(a: dict) -> list[int]:
    """§5: the object's identifier is its name; swap a required key for its alt_identifier name."""
    req = list(a["required_columns"])
    alts = [n["position"] for n in a.get("non_required", []) if n.get("role") == "alt_identifier"]
    keys = [i for i in req if a["columns"][i].split(".")[-1].endswith("Key")]
    if alts and keys:
        req = sorted((set(req) - {keys[0]}) | {alts[0]})
    return req


def inject(q, paths: list[str], ann: dict[tuple[str, str], dict], names: bool = False):
    """A copy of q whose per-reference rules carry T05b's required_columns."""
    if q.refs is None or q.rules is None:
        return q, "no refs/rules"
    base = q.ref_rules or [None] * len(q.refs)
    new, hit = [], 0
    for path, own in zip(paths, base):
        a = ann.get((q.qid, path))
        if a is None or "required_columns" not in a:
            new.append(own)
            continue
        r = copy.deepcopy(own if own is not None else q.rules)
        r["required_columns"] = names_for_keys(a) if names else list(a["required_columns"])
        new.append(r)
        hit += 1
    return dataclasses.replace(q, ref_rules=new if any(x is not None for x in new) else None), f"{hit}/{len(paths)}"


def project(rules, S):
    r = dict(rules); idx = {c: i for i, c in enumerate(S)}
    for k in ("value_kinds", "value_types"):
        if r.get(k): r[k] = [r[k][c] for c in S]
    if r.get("tie_columns"):
        if not all(c in idx for c in r["tie_columns"]): return None
        r["tie_columns"] = [idx[c] for c in r["tie_columns"]]
    if r.get("order_by"):
        if not all(c in idx for c, _ in r["order_by"]): return None
        r["order_by"] = [[idx[c], d] for c, d in r["order_by"]]
    return r


def upper_bound(q, rows, strict) -> bool:
    if strict["outcome"] == "correct":
        return True
    if strict["outcome"] != "wrong" or strict.get("reason") != "missing_columns":
        return False
    if q.ref_rules or q.rules.get("selection") or q.rules.get("top_n") is not None or len(q.refs) > 1:
        return False
    ref = q.refs[0]; nref = len(ref[0]) if ref else 0; ncand = len(rows[0]) if rows else 0
    for k in range(min(ncand, nref), 0, -1):
        for S in itertools.combinations(range(nref), k):
            pr = project(q.rules, S)
            if pr is not None and score_detailed(rows, [[[row[c] for c in S] for row in ref]], pr).outcome == "correct":
                return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--annotation", required=True)
    ap.add_argument("--json-out")
    ap.add_argument("--from-json", help="re-print the tables from a saved --json-out")
    ap.add_argument("--identifier-names", action="store_true", help="also score with names as identifiers (§5)")
    args = ap.parse_args()
    warnings.filterwarnings("ignore", message="rules missing required_columns")
    if args.from_json:
        saved = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        return report(saved["rows"], saved["coverage"])
    annotation = json.loads(Path(args.annotation).read_text(encoding="utf-8"))
    ann = {(a["question_id"], a["ref"]): a for a in annotation["references"]}
    root = eval_dir()
    paths = ref_paths(root)
    qs = {q.qid: q for q in load_questions(lang="zh")}
    raw_root = Path(os.environ["SEMDEBT_DATA_DIR"]) / "runs-raw"
    rows_out, coverage = [], {}
    for model, run in RUNS.items():
        for cell in CELLS:
            for line in (REPO / "runs" / run / f"{cell}.jsonl").read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                if rec.get("status") != "done":
                    continue
                q = qs[rec["qid"]]
                qi, coverage[q.qid] = inject(q, paths[q.qid], ann)
                last = rec["turns"][-1]
                cand = candidate_of(last, raw_root / run / cell, rec["qid"], rec["rep"])
                ec, lim = last["exec"].get("error_class"), last["exec"].get("limit")
                strict = R.final_score(cand, q, ec, lim)
                req = R.final_score(cand, qi, ec, lim)
                up = upper_bound(q, cand, strict) if isinstance(cand, list) else False
                row = {"model": model, "cell": cell, "qid": q.qid, "rep": rec["rep"],
                       "q_level": q.meta.get("q_level"), "low": bool(q.meta.get("low_discrimination")),
                       "judge": q.scoring == "judge",
                       "logged": rec["final"]["outcome"], "strict": strict["outcome"],
                       "strict_reason": strict.get("reason"), "required": req["outcome"],
                       "required_reason": req.get("reason"), "upper": up}
                if args.identifier_names:
                    qn, _ = inject(q, paths[q.qid], ann, names=True)
                    same = qn.ref_rules == qi.ref_rules
                    row["names"] = req["outcome"] if same else R.final_score(cand, qn, ec, lim)["outcome"]
                rows_out.append(row)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({"coverage": coverage, "rows": rows_out}, ensure_ascii=False, indent=1))
    return report(rows_out, coverage)


def report(rows_out: list[dict], coverage: dict) -> int:
    names = all("names" in r for r in rows_out)

    drift = [r for r in rows_out if r["logged"] != r["strict"]]
    print(f"strict vs logged final: {len(drift)} differences")
    for r in drift:
        print("  ", r["model"], r["cell"], r["qid"], r["rep"], r["logged"], "->", r["strict"])

    def acc(rs, key):
        rs = [r for r in rs if not r["judge"]]
        ok = sum((r[key] is True) if key == "upper" else (r[key] == "correct") for r in rs)
        return f"{ok}/{len(rs)} = {100 * ok / len(rs):.1f}%" if rs else "-"

    cols = ["strict", "required", "upper"] + (["names"] if names else [])
    head = "| 模型 | 单元 | 严格 | required_columns（T05b） | 诊断上界 |" + (" T05b + 第五节（标识用名称） |" if names else "")
    for title, keep in (("不含低区分度（judge 题不计）", lambda r: not r["low"]), ("含低区分度（judge 题不计）", lambda r: True)):
        print(f"\n{title}\n\n{head}\n|---|---|" + "---|" * len(cols))
        for model in RUNS:
            for cell in CELLS:
                rs = [r for r in rows_out if r["model"] == model and r["cell"] == cell and keep(r)]
                print(f"| {model} | {cell} | " + " | ".join(acc(rs, k) for k in cols) + " |")

    print("\n按 Q 级（不含低区分度，judge 题不计）：严格 → required" + (" → 第五节" if names else ""))
    for model in RUNS:
        for cell in CELLS:
            parts = []
            for lv in ("Q1", "Q2", "Q3"):
                rs = [r for r in rows_out if r["model"] == model and r["cell"] == cell and not r["low"] and r["q_level"] == lv]
                parts.append(f"{lv} {acc(rs, 'strict')} → {acc(rs, 'required')}" + (f" → {acc(rs, 'names')}" if names else ""))
            print(f"  {model} {cell}: " + "; ".join(parts))

    print("\n逐题（correct 次数 /3，严格 → required；上界）")
    per = collections.defaultdict(lambda: [0, 0, 0, 0])
    for r in rows_out:
        p = per[(r["qid"], r["model"], r["cell"])]
        p[0] += r["strict"] == "correct"; p[1] += r["required"] == "correct"; p[2] += r["upper"]; p[3] += 1
    for k, (s, q_, u, n) in sorted(per.items()):
        if s != q_ or u != s:
            print(f"  {k[0]} {k[1]} {k[2]}: {s} → {q_} (upper {u})")

    flips = [r for r in rows_out if r["strict"] == "correct" and r["required"] != "correct"]
    print(f"\ncorrect → not correct: {len(flips)}")
    for r in flips:
        print("  ", r)
    other = collections.Counter((r["strict"], r["required"]) for r in rows_out if r["strict"] != r["required"])
    print("transitions:", dict(other))
    print("still wrong under required, reasons:",
          dict(collections.Counter(r["required_reason"] for r in rows_out if r["required"] == "wrong")))
    print("coverage (annotated refs / refs):", dict(sorted(coverage.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
