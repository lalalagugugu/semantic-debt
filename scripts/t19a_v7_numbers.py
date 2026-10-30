#!/usr/bin/env python3
"""Derive the T19a v7 report numbers not already in accuracy-v5 from attempt labels.

Stdlib only. No model calls, no SQL. Writes question ids and counts, never question text.
Usage: SEMDEBT_EVAL_DIR=... python3 scripts/t19a_v7_numbers.py > reports/results/t19a-v7-numbers.md
"""
import csv
import json
import os
import random
from pathlib import Path

RUN = Path("runs/20261031-T31-v5-rulings-01")
EVAL = Path(os.environ["SEMDEBT_EVAL_DIR"])
SUSPECT = ["Q03", "Q10", "Q30", "Q47", "Q51", "Q58", "Q72"]
REPLICATES, SEED = 5000, 0


def load(cell):
    rows = [json.loads(line) for line in (RUN / f"{cell}.jsonl").open(encoding="utf-8")]
    return [r for r in rows if r["stratum"] and not r["low"]]


def per_question(rows, qids=None):
    out = {}
    for r in rows:
        if qids is None or r["qid"] in qids:
            out.setdefault(r["qid"], []).append(r["content_correct"])
    return {q: sum(v) / len(v) for q, v in out.items()}


def ci(values):
    rng = random.Random(SEED)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(REPLICATES))
    return means[int(.025 * REPLICATES)], means[int(.975 * REPLICATES) - 1]


def pct(x):
    return f"{x * 100:.1f}"


def signed(x):
    return f"{x * 100:+.1f}"


def compare(left, right, qids=None):
    a, b = per_question(left, qids), per_question(right, qids)
    keys = sorted(set(a) & set(b))
    diffs = [b[q] - a[q] for q in keys]
    lo, hi = ci(diffs)
    return len(keys), sum(diffs) / len(diffs), lo, hi


def count(rows, qids=None):
    chosen = [r for r in rows if qids is None or r["qid"] in qids]
    return sum(r["content_correct"] for r in chosen), len(chosen)


def row(*cells):
    print("|" + "|".join(str(c) for c in cells) + "|")


def main():
    cells = sorted(p.stem for p in RUN.glob("*.jsonl") if p.stem != "summary")
    data = {c: load(c) for c in cells}
    data = {c: v for c, v in data.items() if v}
    published = {r["cell"]: r for r in csv.DictReader(open("reports/results/accuracy-v5-cells.csv", encoding="utf-8"))
                 if r["dimension"] == "all"}
    for c, rows in data.items():
        assert count(rows)[0] == int(published[c]["content_correct"]), c

    questions = []
    for name in ("cube_100", "new"):
        questions += json.load(open(EVAL / f"questions/{name}.yaml", encoding="utf-8"))["questions"]
    primary = {q["id"]: q["labels"]["semantic_dependency"]["primary"] for q in questions}
    main_q = {r["qid"] for r in data["SQL-L1"]}

    json_cov = json.load(open("reports/validation/t16-v14-8836110/coverage.json", encoding="utf-8"))
    cov37 = {r["qid"] for r in json_cov["rows"] if r["category"] == "covered"} & main_q
    t06 = json.load(open(EVAL / "audit/T06-summary-coverage.json", encoding="utf-8"))
    cov42 = {r["question_id"] for r in t06["records"] if r["summary_coverage"] == "covered"} & main_q
    both = cov37 & cov42

    print("# T19a v7：报告派生数字\n")
    print("由 `scripts/t19a_v7_numbers.py` 从 `runs/20261031-T31-v5-rulings-01` 逐次标签算出，单元总数已对 `accuracy-v5-cells.csv` 断言。"
          f"配对与单元区间都以题为重采样单位，{REPLICATES} 次、seed={SEED}，用标准库随机数，和 `accuracy-v5-comparisons.csv` 的数值可能差零点几。只含题号和计数，无模型调用、无 SQL。\n")

    print("## 各单元准确率与 95% 区间（全部题）\n")
    row("单元", "判对/作答", "准确率", "95% 区间", "留出题判对/作答", "留出题准确率", "按约定交付率")
    row(*["---"] * 7)
    for c, rows in data.items():
        k, n = count(rows)
        lo, hi = ci(list(per_question(rows).values()))
        held = {r["qid"] for r in rows if r["split"] == "heldout"}
        hk, hn = count(rows, held)
        row(c, f"{k}/{n}", pct(k / n), f"[{pct(lo)}, {pct(hi)}]", f"{hk}/{hn}", pct(hk / hn), pct(float(published[c]["delivery"])))

    print(f"\n## 第 5 节：覆盖内准确率\n\nJSON-L2 覆盖 {len(cov37)} 题（v1.4 标注），L1.5S 覆盖 {len(cov42)} 题（T06 标注），两者都覆盖 {len(both)} 题。\n")
    subsets = [("JSON-L2 能覆盖", cov37, ["SQL-L1", "SQL-L2", "JSON-L2"]),
               ("L1.5S 能覆盖", cov42, ["SQL-L1", "SQL-L2", "SQL-L1.5S"]),
               ("两者都覆盖", both, ["SQL-L1", "SQL-L2", "SQL-L1.5S", "JSON-L2"])]
    row("题集", "单元", "判对/作答", "准确率")
    row(*["---"] * 4)
    for name, qids, cs in subsets:
        for c in cs:
            k, n = count(data[c], qids)
            row(name, c, f"{k}/{n}", pct(k / n))
    print()
    row("题集", "左", "右", "题数", "差值", "95% 区间")
    row(*["---"] * 6)
    pairs = [("JSON-L2 能覆盖", cov37, "SQL-L1", "JSON-L2"), ("JSON-L2 能覆盖", cov37, "SQL-L1", "SQL-L2"),
             ("L1.5S 能覆盖", cov42, "SQL-L1", "SQL-L1.5S"), ("L1.5S 能覆盖", cov42, "SQL-L1", "SQL-L2"),
             ("两者都覆盖", both, "SQL-L1.5S", "JSON-L2")]
    for name, qids, l, r in pairs:
        n, d, lo, hi = compare(data[l], data[r], qids)
        row(name, l, r, n, signed(d), f"[{signed(lo)}, {signed(hi)}]")

    print("\n覆盖外（标注为答不了的题）的作答结果，按内容判定：\n")
    row("单元", "覆盖外作答", "拒答", "给出结果", "内容对", "内容错或执行失败")
    row(*["---"] * 6)
    for c, qids in (("JSON-L2", cov37), ("SQL-L1.5S", cov42)):
        out = [r for r in data[c] if r["qid"] not in qids]
        ref = sum(r["historical_outcome"] == "refused" for r in out)
        ok = sum(r["content_correct"] for r in out)
        row(c, len(out), ref, len(out) - ref, ok, len(out) - ref - ok)

    print("\n## 第 8 节：叠加相关比较\n")
    row("题集", "左", "右", "题数", "差值", "95% 区间")
    row(*["---"] * 6)
    heldout = {r["qid"] for r in data["SQL-L1"] if r["split"] == "heldout"}
    for name, qids in (("留出 49 题", heldout), ("全部 98 题", None)):
        for l, r in (("SQL-L1-tuned-instr", "SQL-L1plus-tuned-instr"), ("SQL-L1plus", "SQL-L1plus-tuned-instr"), ("SQL-L1", "SQL-L1plus-tuned-instr")):
            n, d, lo, hi = compare(data[l], data[r], qids)
            row(name, l, r, n, signed(d), f"[{signed(lo)}, {signed(hi)}]")

    print("\n## D3：按主依赖标签\n")
    groups = {"可从数据发现": {q for q in main_q if primary[q] == "可从数据发现"}}
    groups["只能由业务告知"] = main_q - groups["可从数据发现"]
    moved = {"可从数据发现（去掉 7 道可疑题）": groups["可从数据发现"] - set(SUSPECT),
             "只能由业务告知（加入 7 道可疑题）": groups["只能由业务告知"] | set(SUSPECT)}
    assert set(SUSPECT) <= groups["可从数据发现"]
    row("分组", "题数", "L0", "L0-E", "L1", "L0→L0-E [95%]", "L0→L1 [95%]", "L1→L1-E [95%]", "L1-E")
    row(*["---"] * 9)
    for name, qids in {**groups, **moved}.items():
        vals = [count(data[c], qids) for c in ("SQL-L0", "SQL-L0-E", "SQL-L1", "SQL-L1-E")]
        p = [pct(k / n) for k, n in vals]
        cmp = []
        for l, r in (("SQL-L0", "SQL-L0-E"), ("SQL-L0", "SQL-L1"), ("SQL-L1", "SQL-L1-E")):
            _, d, lo, hi = compare(data[l], data[r], qids)
            cmp.append(f"{signed(d)} [{signed(lo)}, {signed(hi)}]")
        row(name, len(qids), p[0], p[1], p[2], *cmp, p[3])
    print(f"\n7 道可疑题：{'、'.join(SUSPECT)}。标签本身不改，见 `$SEMDEBT_DATA_DIR/v7-eval-20261030/discoverability-review.md`。")

    print("\n## D4：L1+ 三次内容一致才答（首答）\n")
    eq = {r["qid"]: r["content_equivalent"] == "True"
          for r in csv.DictReader(open("reports/validation/t31-v7-d4-equivalence.csv", encoding="utf-8"))}
    first = [r for r in data["SQL-L1plus"] if r["rep"] == 1]
    wrong = [r["qid"] for r in first if not r["content_correct"]]
    print(f"- 首答对 {sum(r['content_correct'] for r in first)}/{len(first)}。")
    print(f"- 一致才答：答 {sum(eq[r['qid']] for r in first)} 题，对 {sum(r['content_correct'] for r in first if eq[r['qid']])} 题。")
    print(f"- 首答错 {len(wrong)} 题（{'、'.join(sorted(wrong))}），拦下 {'、'.join(sorted(q for q in wrong if not eq[q]))}。")
    print(f"- 误拦首答对的：{'、'.join(sorted(r['qid'] for r in first if r['content_correct'] and not eq[r['qid']]))}。")


main()
