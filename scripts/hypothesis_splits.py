"""Hypothesis splits on the committed direct-cell logs (reports/hypotheses.md C2, C3, C9).

    SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/hypothesis_splits.py \\
        --run 20261018-T13-sql-direct-01-rescore-01 --eval-tag eval-v1.2 > reports/results/hypothesis_splits.md

No model calls, no query execution. Table rules are those of ``scripts/sql_direct_report.py``: judge
questions are out of every denominator; low-discrimination questions are out of the main numbers.

- C2: SQL-L1 vs SQL-L1c (and L0, R) split by question source (external benchmark vs new) and by split
  (tuning vs holdout).
- C3: SQL-L1 vs SQL-L1.5S and SQL-L1.5W on the same questions, split by the T06 summary-coverage label.
- C9: every direct cell split by the bank's user-type label. The label key is not fixed in this repo;
  ``--user-key`` names it (dotted path under ``labels``). Without it the script lists the label keys
  it found and stops.

Paired comparisons are per question (mean of the 3 attempts, 0 / ⅓ / ⅔ / 1): mean difference, a
percentile bootstrap 95% interval over questions (fixed seed), and a two-sided exact sign test on the
questions that differ. The design (v5) reports no significance tests; these are exploratory, for
reading the size of a gap against question-to-question noise. Only question ids reach the output.
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from math import comb
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CELLS = ("SQL-L0", "SQL-R", "SQL-L1", "SQL-L1c", "SQL-L1.5W", "SQL-L1.5S")
BOOT = 10_000
SEED = 20261019


def per_question(recs: list[dict], keep: set[str]) -> dict[str, float]:
    """Question id → share of its attempts that are correct, over done attempts with a verdict."""
    hits, n = defaultdict(int), defaultdict(int)
    for r in recs:
        if r.get("status") != "done" or r["qid"] not in keep or r["final"].get("pending"):
            continue
        n[r["qid"]] += 1
        hits[r["qid"]] += r["final"]["outcome"] == "correct"
    return {q: hits[q] / n[q] for q in n}


def acc(pq: dict[str, float], ids: set[str]) -> str:
    xs = [pq[q] for q in ids if q in pq]
    return f"{100 * sum(xs) / len(xs):.1f}%" if xs else "—"


def sign_test(pos: int, neg: int) -> float:
    n = pos + neg
    if n == 0:
        return 1.0
    k = min(pos, neg)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def paired(a: dict[str, float], b: dict[str, float], ids: set[str]) -> dict:
    """b − a per question on the questions both cells answered."""
    common = sorted(q for q in ids if q in a and q in b)
    d = [b[q] - a[q] for q in common]
    if not d:
        return {"n": 0}
    rng = random.Random(SEED)
    means = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(BOOT))
    pos, neg = sum(x > 0 for x in d), sum(x < 0 for x in d)
    return {"n": len(d), "diff": 100 * sum(d) / len(d), "lo": 100 * means[int(0.025 * BOOT)],
            "hi": 100 * means[int(0.975 * BOOT) - 1], "pos": pos, "neg": neg, "p": sign_test(pos, neg)}


def paired_row(label: str, p: dict) -> str:
    if not p["n"]:
        return f"| {label} | 0 | — | — | — | — |"
    return (f"| {label} | {p['n']} | {p['diff']:+.1f} 点 | [{p['lo']:+.1f}, {p['hi']:+.1f}] | "
            f"{p['pos']} / {p['neg']} | {p['p']:.3f} |")


PAIRED_HEAD = ["| 对比（后者 − 前者） | 题数 | 差 | 95% 区间（按题自助法） | 后者更好 / 更差的题 | 符号检验 p |",
               "|---|---:|---:|---|---|---:|"]


def by_group(pq: dict[str, dict[str, float]], groups: dict[str, set[str]], cells=CELLS) -> list[str]:
    out = ["| 组 | 题数 | " + " | ".join(cells) + " |", "|---|---:|" + "---|" * len(cells)]
    for g, ids in groups.items():
        out.append(f"| {g} | {len(ids)} | " + " | ".join(acc(pq[c], ids) for c in cells) + " |")
    return out


def report(pq: dict[str, dict[str, float]], main: set[str], source: dict[str, str], split: dict[str, str],
           coverage: dict[str, str] | None, user: dict[str, str] | None) -> list[str]:
    out: list[str] = []

    def groups(label: dict[str, str]) -> dict[str, set[str]]:
        g = defaultdict(set)
        for q in main:
            g[label.get(q, "—")].add(q)
        return dict(sorted(g.items()))

    out += ["## C2：外部原题 vs 新题（SQL-L1 vs SQL-L1c）", ""]
    out += by_group(pq, groups(source)) + [""]
    out += PAIRED_HEAD
    for g, ids in groups(source).items():
        out.append(paired_row(f"L1c → L1，{g}", paired(pq["SQL-L1c"], pq["SQL-L1"], ids)))
    out.append(paired_row("L1c → L1，全部", paired(pq["SQL-L1c"], pq["SQL-L1"], main)))
    out += ["", "按划分（调优题 / 留出题）：", ""] + by_group(pq, groups(split)) + [""]

    if coverage is not None:
        cov = groups(coverage)
        out += ["## C3：汇总层覆盖内外，同题比较", ""] + by_group(pq, cov) + [""] + PAIRED_HEAD
        for g, ids in cov.items():
            out.append(paired_row(f"L1 → L1.5S，{g}", paired(pq["SQL-L1"], pq["SQL-L1.5S"], ids)))
            out.append(paired_row(f"L1 → L1.5W，{g}", paired(pq["SQL-L1"], pq["SQL-L1.5W"], ids)))
        out.append("")

    if user is not None:
        ug = groups(user)
        out += ["## C9：按用户类型", ""] + by_group(pq, ug) + [""] + PAIRED_HEAD
        for g, ids in ug.items():
            out.append(paired_row(f"L0 → L1，{g}", paired(pq["SQL-L0"], pq["SQL-L1"], ids)))
        out.append("")
    return out


def label_paths(labels: dict, prefix: str = "") -> set[str]:
    out = set()
    for k, v in labels.items():
        out.add(prefix + k)
        if isinstance(v, dict):
            out |= label_paths(v, prefix + k + ".")
    return out


def dig(d: dict, path: str):
    for k in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def main() -> int:
    import yaml

    from harness.questions import eval_dir, load_questions, question_files, verify_eval_tag
    from scripts.sql_direct_report import coverage, records

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="20261018-T13-sql-direct-01-rescore-01")
    ap.add_argument("--eval-tag", default="eval-v1.2")
    ap.add_argument("--user-key", help="dotted path under a question's labels holding its user type")
    args = ap.parse_args()

    commit = verify_eval_tag(args.eval_tag)
    qs = {q.qid: q for q in load_questions()}
    judge = {q for q, x in qs.items() if x.scoring == "judge"}
    low = {q for q, x in qs.items() if x.meta["low_discrimination"]}
    main_ids = set(qs) - judge - low
    raw = {}
    for path in question_files(eval_dir()):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for rec in data["questions"] if isinstance(data, dict) else data:
            raw[str(rec["id"])] = rec.get("labels") or {}
    if not args.user_key:
        keys = sorted(set().union(*(label_paths(v) for v in raw.values())))
        print("label keys in the bank (pass one as --user-key):\n" + "\n".join(keys), file=sys.stderr)
        return 2
    user = {q: str(dig(raw.get(q, {}), args.user_key)) for q in qs}
    pq = {c: per_question(records(args.run, c), set(qs) - judge) for c in CELLS}
    out = ["# 假设拆分：C2、C3、C9（自动生成）", "",
           f"- 运行 `runs/{args.run}/`；题库 `{args.eval_tag}` = `{commit[:7]}`；judge 题不计、不含低区分度，"
           f"{len(main_ids)} 题；每题 3 次取平均后按题配对",
           f"- 用户类型取 `labels.{args.user_key}`",
           "- 生成：`SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/hypothesis_splits.py "
           f"--run {args.run} --eval-tag {args.eval_tag} --user-key {args.user_key}`",
           "- 区间与 p 值是探索性的（设计 v5 不做显著性检验），只用来对照题与题之间的波动", ""]
    out += report(pq, main_ids, {q: qs[q].meta["source"] for q in qs},
                  {q: str(qs[q].meta.get("split")) for q in qs}, coverage(), user)
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
