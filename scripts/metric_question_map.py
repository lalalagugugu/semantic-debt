"""Questions that touch the A / B class metrics of reports/validation/metric-text-vs-impl.md,
and how every cell did on them (T21-2). Prints question ids and counts only, never question text.

    SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/metric_question_map.py

The bank has no per-metric label, so a question is matched when its Chinese text contains one
of the group's keywords (metric names and aliases from semantic/source.yaml, plus the plain
words of the metric's definition) or one of its reference SQLs matches the group's pattern
(the table / columns the metric is computed from). The match reason is printed, so a reader
can drop false positives; the match is a screen, not a judgement.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness.questions import eval_dir  # noqa: E402

# group -> (metrics, text keywords, reference-SQL pattern or None)
GROUPS = {
    "A1": ("平均在手库存金额", ["平均在手库存", "平均库存"],
           r"FactInventory.*(avg|uniqExact\(\s*\w*\.?DateKey|count\(\s*DISTINCT\s+\w*\.?DateKey)"),
    "A2": ("库存周转率", ["周转"], None),
    "A3": ("销售额占比", ["占比", "份额", "贡献度", "比重"], None),
    "A4": ("同店销售额", ["同店"], None),
    "A5": ("产品利润率", ["产品利润率"], r"UnitPrice.*UnitCost|UnitCost.*UnitPrice"),
    "A6": ("产品标价、产品单位成本", ["标价", "单位成本"], r"\b(avg|sum|max|min)\(\s*\w*\.?Unit(Price|Cost)\b"),
    "A7": ("坪效、门店人均销售额", ["坪效", "单位面积", "人均销售"], r"SellingAreaSize|EmployeeCount"),
    "A8": ("当前在手 / 在订 / 安全库存、低于安全库存的门店产品数",
           ["当前库存", "在手库存", "在途", "在订", "安全库存", "缺货"], r"SafetyStockQuantity|OnOrderQuantity"),
    "B1": ("销售额环比增长率", ["环比"], None),
    "B2": ("新客数、新客销售额、新客销售额占比", ["新客", "新增客户"], None),
    "B3": ("目标销售额、目标销量、目标毛利、计划收入", ["目标", "配额", "预算", "计划收入"],
           r"FactSalesQuota|FactStrategyPlan"),
}

RUNS = [
    ("20261018-T13-sql-direct-01-rescore-01", ["SQL-L0", "SQL-R", "SQL-L1", "SQL-L1c", "SQL-L1.5W", "SQL-L1.5S"]),
    ("20261019-T15-explorer-01-rescore-01", ["SQL-L0-E", "SQL-L1-E"]),
    ("20261019-T21-pilot-01", ["SQL-L0-P", "SQL-L1-P"]),
]


def load_bank() -> list[dict]:
    out = []
    for name in ("cube_100.yaml", "new.yaml"):
        out += json.loads((eval_dir() / "questions" / name).read_text(encoding="utf-8"))["questions"]
    return out


def matches(q: dict) -> dict[str, list[str]]:
    text = q.get("text_zh") or ""
    sqls = " ".join(r.get("sql") or "" for r in q.get("refs") or [])
    hit = {}
    for g, (_, words, pattern) in GROUPS.items():
        why = [f"题面「{w}」" for w in words if w in text]
        if pattern and re.search(pattern, sqls, re.IGNORECASE | re.DOTALL):
            why.append("参考 SQL")
        if why:
            hit[g] = why
    return hit


def outcomes() -> dict[str, dict[str, Counter]]:
    res: dict[str, dict[str, Counter]] = {}
    for run, cells in RUNS:
        for cell in cells:
            path = REPO / "runs" / run / f"{cell}.jsonl"
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                if r.get("status") == "done":
                    res.setdefault(r["qid"], {}).setdefault(cell, Counter())[r["final"]["outcome"]] += 1
    return res


def main() -> int:
    bank = load_bank()
    res = outcomes()
    cells = [c for _, cs in RUNS for c in cs]
    print("| 组 | 指标 | 题号（匹配依据） |")
    print("|---|---|---|")
    hits = {q["id"]: matches(q) for q in bank}
    for g, (metrics, _, _) in GROUPS.items():
        ids = [f"{qid}（{'、'.join(h[g])}）" for qid, h in hits.items() if g in h]
        print(f"| {g} | {metrics} | {'；'.join(ids) or '—'} |")
    print()
    print("各单元在这些题上的对错（对 / 作答次数；judge 题与 score_timeout 记 p）：")
    print()
    print("| 题号 | 组 | 打分 | " + " | ".join(cells) + " |")
    print("|---|---|---|" + "---|" * len(cells))
    for q in bank:
        h = hits[q["id"]]
        if not h:
            continue
        row = []
        for c in cells:
            cnt = res.get(q["id"], {}).get(c)
            if not cnt:
                row.append("—")
                continue
            n = sum(cnt.values())
            p = cnt.get("pending", 0) + cnt.get("unscored", 0)
            row.append(f"{cnt.get('correct', 0)}/{n}" + (f" p{p}" if p else ""))
        low = "低区分度" if (q.get("labels", {}).get("low_discrimination") or {}).get("criteria") else ""
        kind = "judge" if q.get("scoring") != "deterministic" else (low or "确定")
        print(f"| {q['id']} | {'、'.join(h)} | {kind} | " + " | ".join(row) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
