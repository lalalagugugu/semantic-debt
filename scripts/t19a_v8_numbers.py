#!/usr/bin/env python3
"""Derive the T19a v8 process statistics on the 98 main-table questions.

Stdlib only. No model calls, no SQL, no new content judgement: labels come from
runs/20261031-T31-v5-rulings-01, usage and first-round status from the source logs.
Writes question ids and counts, never question text.
Usage: SEMDEBT_EVAL_DIR=... python3 scripts/t19a_v8_numbers.py > reports/results/t19a-v8-numbers.md
"""
import csv
import json
import os
from collections import Counter
from pathlib import Path

RUN = Path("runs/20261031-T31-v5-rulings-01")
EVAL = Path(os.environ["SEMDEBT_EVAL_DIR"])


def labels(cell):
    rows = [json.loads(line) for line in (RUN / f"{cell}.jsonl").open(encoding="utf-8")]
    return [r for r in rows if r["stratum"] and not r["low"]]


def source(cell, keys):
    runs = {r["source_run"] for r in labels(cell)}
    assert len(runs) == 1, cell
    rows = [json.loads(line) for line in (Path("runs") / runs.pop() / f"{cell}.jsonl").open(encoding="utf-8")]
    chosen = {(r["qid"], r["rep"]): r for r in rows if (r["qid"], r["rep"]) in keys and r.get("status") == "done"}
    assert len(chosen) == len(keys), cell
    return chosen


def row(*cells):
    print("|" + "|".join(str(c) for c in cells) + "|")


def main():
    base = labels("SQL-L1")
    main_q = {r["qid"] for r in base}
    assert len(main_q) == 98

    print("# T19a v8：过程统计（主表 98 题）\n")
    print("由 `scripts/t19a_v8_numbers.py` 算出。主表范围取 `runs/20261031-T31-v5-rulings-01`；首轮状态和用量取各单元的原始运行日志。"
          "没有模型调用、没有 SQL、没有新的内容判定。只含题号和计数。\n")

    print("## 题目构成\n")
    ids = {}
    for name in ("cube_100", "new"):
        ids[name] = {q["id"] for q in json.load(open(EVAL / f"questions/{name}.yaml", encoding="utf-8"))["questions"]}
    row("来源", "题库题数", "计分", "未计分")
    row(*["---"] * 4)
    for name, qs in ids.items():
        row(name, len(qs), len(qs & main_q), len(qs - main_q))
    levels = Counter(r["q_level"] for r in base if r["rep"] == 1)
    splits = Counter(r["split"] for r in base if r["rep"] == 1)
    print(f"\n级别：{dict(sorted(levels.items()))}；划分：{dict(sorted(splits.items()))}。\n")

    print("## 第 6 节：首轮执行报错（98 题 × 3）\n")
    row("写法说明", "单元", "首轮报错/作答", "比例")
    row(*["---"] * 4)
    for name, cell in (("1 级", "SQL-L1"), ("2 级", "SQL-L1-T2"), ("3 级", "SQL-L1-T3")):
        keys = {(r["qid"], r["rep"]) for r in labels(cell)}
        rows = source(cell, keys)
        bad = sum(r["first"] == "exec_error" for r in rows.values())
        row(name, cell, f"{bad}/{len(rows)}", f"{bad / len(rows) * 100:.1f}")

    print("\n## 第 3 节：查库次数和用途（98 题 × 3）\n")
    audit = [r for r in csv.DictReader(open("reports/midterm/tool-audit.csv", encoding="utf-8")) if r["qid"] in main_q]
    row("单元", "查库次数", "作答", "每次作答", "用途占比")
    row(*["---"] * 5)
    for cell in ("SQL-L0-E", "SQL-L1-E"):
        calls = [r for r in audit if r["unit"] == cell]
        purposes = Counter(r["purpose"] for r in calls)
        n = len(labels(cell))
        share = "；".join(f"{k} {v / len(calls) * 100:.1f}%" for k, v in purposes.most_common())
        row(cell, len(calls), n, f"{len(calls) / n:.2f}", share)

    print("\n## 第 2、4 节：模型第一轮收到的输入 token（98 题 × 3 的均值）\n")
    row("单元", "第一轮输入均值", "每次作答累计输入均值")
    row(*["---"] * 3)
    for cell in ("SQL-L0", "SQL-L1c", "SQL-L1", "SQL-L1plus", "SQL-L3a"):
        rows = source(cell, {(r["qid"], r["rep"]) for r in labels(cell)}).values()
        first = sum(r["turns"][0]["usage"]["prompt_tokens"] for r in rows) / len(rows)
        total = sum(r["usage"]["prompt_tokens"] for r in rows) / len(rows)
        row(cell, f"{first:,.0f}", f"{total:,.0f}")

    print("\n## 第 5 节：未得分里有多少来自覆盖范围外\n")
    json_cov = json.load(open("reports/validation/t16-v14-8836110/coverage.json", encoding="utf-8"))
    cov37 = {r["qid"] for r in json_cov["rows"] if r["category"] == "covered"} & main_q
    t06 = json.load(open(EVAL / "audit/T06-summary-coverage.json", encoding="utf-8"))
    cov42 = {r["question_id"] for r in t06["records"] if r["summary_coverage"] == "covered"} & main_q
    row("单元", "全表判对/作答", "未得分", "其中覆盖范围外", "占比", "覆盖范围内判对/作答")
    row(*["---"] * 6)
    for cell, cov in (("JSON-L2", cov37), ("SQL-L1.5S", cov42)):
        rows = labels(cell)
        lost = [r for r in rows if not r["content_correct"]]
        out = [r for r in lost if r["qid"] not in cov]
        inside = [r for r in rows if r["qid"] in cov]
        row(cell, f"{sum(r['content_correct'] for r in rows)}/{len(rows)}", len(lost), len(out),
            f"{len(out) / len(lost) * 100:.1f}%", f"{sum(r['content_correct'] for r in inside)}/{len(inside)}")

    print("\n## 第 9 节：复盘补语义单元的错答能否执行\n")
    wrong = [r for r in labels("SQL-L1-tuned") if not r["content_correct"]]
    print(f"未得分 {len(wrong)} 次，其中有查询结果 {sum(r['has_result'] for r in wrong)} 次；"
          f"结局：{dict(Counter(r['historical_outcome'] for r in wrong))}；"
          f"划分：{dict(Counter(r['split'] for r in wrong))}。")


main()
