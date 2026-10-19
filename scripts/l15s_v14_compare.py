"""SQL-L1.5S before / after the semantic-v1.4 summary-doc fix, on the basis of
decisions/2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md §一: cross-level accuracy on the
summary-covered questions only; the questions outside coverage reported apart (boundary behaviour).

Judge and low-discrimination questions are left out of both strata, as in reports/results/sql_direct.md.
No model call, no chDB. Prints markdown for reports/results/l15s-covered-analysis.md.
    SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/l15s_v14_compare.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sql_direct_report import coverage, error_group, records  # noqa: E402
from harness.questions import load_questions, verify_eval_tag  # noqa: E402

BEFORE = "20261018-T13-sql-direct-01-rescore-01"
AFTER = "20261019-T13-l15s-v14-01"
WORSE = "Q02 Q10 Q12 Q13 Q16 Q37 Q41 Q72 Q101 Q105 Q106 Q107 Q109".split()
OUT = ("correct", "wrong", "exec_error", "refused")


def by_q(recs):
    out: dict[str, list[dict]] = {}
    for r in recs:
        out.setdefault(r["qid"], []).append(r)
    return out


def n_ok(rs) -> int:
    return sum(r["final"]["outcome"] == "correct" for r in rs)


def dist(rs) -> str:
    c = Counter(r["final"]["outcome"] for r in rs)
    other = len(rs) - sum(c[o] for o in OUT)
    return " | ".join(f"{100 * c[o] / len(rs):.1f}%（{c[o]}）" for o in OUT) + (f" | 其他 {other}" if other else "")


def main() -> int:
    verify_eval_tag("eval-v1.2")
    qs = {q.qid: q for q in load_questions()}
    cov = coverage()
    keep = {q for q in qs if qs[q].scoring != "judge" and not qs[q].meta["low_discrimination"]}
    covered = sorted((q for q in keep if cov[q] == "covered"), key=lambda x: int(x[1:]))
    outside = sorted((q for q in keep if cov[q] != "covered"), key=lambda x: int(x[1:]))
    done = lambda run, cell: [r for r in records(run, cell) if r.get("status") == "done"]  # noqa: E731
    l1 = by_q(done(BEFORE, "SQL-L1"))
    pre = by_q(done(BEFORE, "SQL-L1.5S"))
    post_all = records(AFTER, "SQL-L1.5S")
    post = by_q([r for r in post_all if r.get("status") == "done"])
    pending = Counter(r["final"].get("pending") for r in post_all if r.get("status") == "done" and r["final"]["outcome"] == "pending")

    n = 3 * len(covered)
    a, b, c = (sum(n_ok(d[q]) for q in covered) for d in (l1, pre, post))
    print(f"状态：{Counter(r.get('status') for r in post_all)}；pending：{dict(pending)}；"
          f"费用 {sum(r.get('cost_cny', 0) for r in post_all):.2f} 元；调用 {sum(r.get('n_calls', 0) for r in post_all)}；"
          f"指纹 {sorted({t.get('system_fingerprint') for r in post_all for t in r.get('turns', [])})}\n")
    print(f"### 覆盖内 {len(covered)} 题 × 3 次 = {n}\n")
    print("| | 正确 | 准确率 | 与 SQL-L1 之差 |\n|---|---:|---:|---:|")
    for name, k in (("SQL-L1", a), ("SQL-L1.5S 修复前（semantic-v1.2）", b), ("SQL-L1.5S 修复后（semantic-v1.4）", c)):
        print(f"| {name} | {k}/{n} | {100 * k / n:.1f}% | {100 * (k - a) / n:+.1f} |")
    print("\n| | correct | wrong | exec_error | refused |\n|---|---:|---:|---:|---:|")
    for name, d in (("修复前", pre), ("修复后", post)):
        print(f"| {name} | " + dist([r for q in covered for r in d[q]]) + " |")
    better = [q for q in covered if n_ok(post[q]) > n_ok(l1[q])]
    worse = [q for q in covered if n_ok(post[q]) < n_ok(l1[q])]
    print(f"\n修复后与 SQL-L1 逐题比：好 {len(better)} 题（{' '.join(better)}），差 {len(worse)} 题（{' '.join(worse)}）。\n")
    print("| 题 | L1 | 修复前 | 修复后 |\n|---|---:|---:|---:|")
    for q in covered:
        if n_ok(pre[q]) != n_ok(post[q]) or q in WORSE:
            print(f"| {q}{'＊' if q in WORSE else ''} | {n_ok(l1[q])}/3 | {n_ok(pre[q])}/3 | {n_ok(post[q])}/3 |")
    first = {name: Counter(error_group(r["turns"][0]["exec"], r["turns"][0]["query"])[0]
                           for q in covered for r in d[q] if r["turns"][0].get("exec") and r["turns"][0]["exec"]["status"] == "error")
             for name, d in (("修复前", pre), ("修复后", post))}
    print(f"\n首轮执行报错（覆盖内）：修复前 {sum(first['修复前'].values())} {dict(first['修复前'])}；"
          f"修复后 {sum(first['修复后'].values())} {dict(first['修复后'])}")
    sv = sum(t.get("exec", {}) and t["exec"].get("error_class") == "scope_violation"
             for q in covered + outside for r in post[q] for t in r["turns"])
    print(f"修复后越界（scope_violation，全部 {len(covered) + len(outside)} 题）：{sv} 次\n")
    print(f"### 覆盖外 {len(outside)} 题 × 3 次 = {3 * len(outside)}（边界行为，不进跨档位比较）\n")
    print("| | correct | wrong | exec_error | refused |\n|---|---:|---:|---:|---:|")
    for name, d in (("修复前", pre), ("修复后", post)):
        print(f"| {name} | " + dist([r for q in outside for r in d[q]]) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
