"""T19b step 6: reports/results/l1-error-attribution.md from the Flash log and Codex's CSV.

    SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/l1_attribution_report.py

Reads runs/20261020-T19b-attrib-01/attribution.jsonl (Flash), reports/attribution/codex.csv
(Codex) and the question labels of eval-v1.2. Writes only question ids, rounds, counts, labels and
L1 positions: no question text, no SQL, no free-text note.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.attribute_l1 import CATEGORIES, bank_records  # noqa: E402
from harness.questions import verify_eval_tag  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
RUN = "20261020-T19b-attrib-01"
OUT = REPO / "reports" / "results" / "l1-error-attribution.md"
ROOTS = {1: "文档没写", 2: "文档有歧义", 3: "文档清楚、模型没理解或没用上", 4: "题面有歧义", 5: "参考答案或评分可疑"}
SPOT = 10


def kappa(a: list, b: list) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def load() -> list[dict]:
    flash = {}
    for line in (REPO / "runs" / RUN / "attribution.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        flash[(r["qid"], r["rep"])] = r
    items = list(csv.DictReader((REPO / "reports" / "attribution" / "items.csv").open(encoding="utf-8")))
    codex = list(csv.DictReader((REPO / "reports" / "attribution" / "codex.csv").open(encoding="utf-8")))
    if [(r["question_id"], r["round"]) for r in codex] != [(r["question_id"], r["round"]) for r in items]:
        raise ValueError("codex.csv does not list the items of items.csv in order")
    if set(flash) != {(r["question_id"], int(r["round"])) for r in items}:
        raise ValueError("the Flash log does not cover exactly the items of items.csv")
    rows = []
    for c in codex:
        f = flash[(c["question_id"], int(c["round"]))]
        fl = f.get("labels")
        rows.append({"qid": c["question_id"], "round": int(c["round"]), "outcome": f["source"]["outcome"],
                     "f_cat": fl["category"] if fl else "unparsed", "f_root": fl["root_cause"] if fl else None,
                     "f_assume": fl["declared_assumption"] if fl else None, "f_doc": fl["doc_evidence"] if fl else "",
                     "c_cat": c["category"], "c_root": int(c["root_cause"]),
                     "c_assume": c["declared_assumption"].strip().lower() == "true", "c_doc": c["doc_evidence"]})
    return rows


def crosstab(rows: list[dict], cat: str, root: str) -> list[str]:
    cats = [c for c in CATEGORIES if any(r[cat] == c for r in rows)] + sorted({r[cat] for r in rows} - set(CATEGORIES))
    out = ["| 类别 \\ 根因 | " + " | ".join(str(k) for k in ROOTS) + " | 合计 |", "|---|" + "---:|" * (len(ROOTS) + 1)]
    for c in cats:
        n = [sum(r[cat] == c and r[root] == k for r in rows) for k in ROOTS]
        out.append(f"| {c} | " + " | ".join(str(x) for x in n) + f" | {sum(n)} |")
    tot = [sum(r[root] == k for r in rows) for k in ROOTS]
    out.append("| **合计** | " + " | ".join(f"**{x}**" for x in tot) + f" | **{sum(tot)}** |")
    return out


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%（{n}/{d}）" if d else "—"


def ids(rs: list[dict]) -> str:
    return "、".join(f"{r['qid']} r{r['round']}" for r in rs) or "无"


def main() -> int:
    commit = verify_eval_tag("eval-v1.2")
    bank = bank_records()
    rows = load()
    n = len(rows)
    for r in rows:
        lab = bank[r["qid"]].get("labels") or {}
        r["dep"] = ((lab.get("semantic_dependency") or {}).get("primary")) or "（无）"
        r["level"] = lab.get("q_level") or "（无）"
        r["persona"] = lab.get("persona") or "（无）"
        r["low"] = bool((lab.get("low_discrimination") or {}).get("criteria"))

    md = ["# SQL-L1 失败归类（T19b）", "",
          "- 依据：`decisions/2026-10-20-l1-error-attribution.md`，`tasks/T19b-l1-error-attribution.md`，"
          "编码手册 `reports/attribution/codebook.md`。",
          f"- 条目：`20261018-T13-sql-direct-01-rescore-01` 中 SQL-L1 的全部非正确作答，judge 题除外，含低区分度，共 {n} 条"
          f"（错答 {sum(r['outcome'] == 'wrong' for r in rows)}、执行失败 {sum(r['outcome'] == 'exec_error' for r in rows)}、"
          f"拒答 {sum(r['outcome'] == 'refused' for r in rows)}）。每次作答单独归类。",
          f"- Flash：`runs/{RUN}/attribution.jsonl`（deepseek-flash 初判）。Codex：`reports/attribution/codex.csv`"
          "（独立复核，不看 Flash 的结果）。题目标签取自 eval-v1.2 = " + commit[:7] + "。",
          "- 复现：`SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/l1_attribution_report.py`",
          "- 本文只含题号、次数、标签和 L1 位置，不含题面、参考 SQL、作答 SQL 和自由文本说明。", "",
          "## 偏离与已知局限", "",
          "1. **Flash 自评偏差（已知局限）**：初判用的是被测模型 `deepseek-flash` 本身，不是设计里的 V4 Pro。"
          "它可能倾向于把自己的错归给文档或题面。缓解办法：不给原作答的思考内容；文档证据必须给出位置；Codex 全量独立复核。"
          "本文的结论以两家一致的部分为准，并给出根因 3 的下限和上限。",
          "2. **高峰时段运行**：Flash 初判在 2026-10-22 16:29–16:36 运行，经用户明确批准，预算上限由 3 元提到 5 元，实际 4.42 元。",
          "3. **在 T13 的 clone 里开分支**：卡片负责方是 T13 会话，T19b 当时未列入 cards.yaml。"
          "Codex 在自己的 clone（分支 `T19b-codex`）里标注，那个 clone 里也有 Flash 的日志；"
          "交接时已要求它不得读，Codex 自述未读取。",
          "4. **用户抽检尚未做**：第 7 节列出待抽检的分歧条目，抽检结果由用户填写。", ""]

    # key points, all computed
    ok0 = [r for r in rows if r["f_root"] is not None]
    f3c2 = [r for r in ok0 if r["f_root"] == 3 and r["c_root"] == 2]
    f3c2_cat = Counter(r["c_cat"] for r in f3c2).most_common(2)
    b5 = [r for r in ok0 if r["f_root"] == 5 and r["c_root"] == 5]
    lo3 = sum(r["f_root"] == 3 and r["c_root"] == 3 for r in ok0)
    hi3 = sum(r["f_root"] == 3 or r["c_root"] == 3 for r in rows)
    md += ["## 要点", "",
           f"1. **类别较一致，根因一致性一般。** 类别 κ = {kappa([r['f_cat'] for r in ok0], [r['c_cat'] for r in ok0]):.2f}，"
           f"根因 κ = {kappa([r['f_root'] for r in ok0], [r['c_root'] for r in ok0]):.2f}。根因的数字要按区间读，不宜取单点。",
           f"2. **「模型没理解或没用上」（根因 3）占 {100 * lo3 / n:.0f}%–{100 * hi3 / n:.0f}%**（下限：两家都判；上限：至少一家判）。",
           f"3. **最大的分歧是 Flash 判 3、Codex 判 2（文档有歧义）**，共 {len(f3c2)} 条，"
           f"Codex 的类别主要是 " + "、".join(f"{c}（{k}）" for c, k in f3c2_cat) + "。"
           f"Flash 判根因 3 的条目（{sum(r['f_root'] == 3 for r in ok0)}）多于 Codex（{sum(r['c_root'] == 3 for r in ok0)}）。"
           "也就是说，裁决担心的偏向（被测模型把自己的错推给文档或题面）在总量上没有出现，Flash 反而更多地归咎于自己。",
           f"4. **参考答案或评分可疑（根因 5）两家都判的有 {len(b5)} 条、{len({r['qid'] for r in b5})} 题。** 比例不低，"
           "第 5 节的清单交题库负责方核对。核对之前，根因的占比有这一块不确定性。", ""]

    # 1. crosstabs
    md += ["## 1. 类别 × 根因", "", "根因：" + "；".join(f"{k} = {v}" for k, v in ROOTS.items()) + "。", "",
           "### Flash", ""] + crosstab(rows, "f_cat", "f_root") + ["", "### Codex", ""] + crosstab(rows, "c_cat", "c_root")
    md += ["", f"已声明假设：Flash 判「是」{pct(sum(bool(r['f_assume']) for r in rows), n)}，"
           f"Codex 判「是」{pct(sum(r['c_assume'] for r in rows), n)}。", ""]

    # 2. agreement
    ok = [r for r in rows if r["f_root"] is not None]
    agree_cat = sum(r["f_cat"] == r["c_cat"] for r in ok)
    agree_root = sum(r["f_root"] == r["c_root"] for r in ok)
    agree_as = sum(r["f_assume"] == r["c_assume"] for r in ok)
    md += ["## 2. 两家一致率", "",
           "| 标签 | 原始一致率 | Cohen's κ |", "|---|---:|---:|",
           f"| 类别 | {pct(agree_cat, len(ok))} | {kappa([r['f_cat'] for r in ok], [r['c_cat'] for r in ok]):.2f} |",
           f"| 根因 | {pct(agree_root, len(ok))} | {kappa([r['f_root'] for r in ok], [r['c_root'] for r in ok]):.2f} |",
           f"| 已声明假设 | {pct(agree_as, len(ok))} | {kappa([r['f_assume'] for r in ok], [r['c_assume'] for r in ok]):.2f} |", "",
           "根因的混淆矩阵（行 = Flash，列 = Codex）：", "",
           "| Flash \\ Codex | " + " | ".join(str(k) for k in ROOTS) + " |", "|---|" + "---:|" * len(ROOTS)]
    for a in ROOTS:
        md.append(f"| {a} | " + " | ".join(str(sum(r['f_root'] == a and r['c_root'] == b for r in ok)) for b in ROOTS) + " |")
    md.append("")

    # 3. root cause 3 bounds
    both3 = [r for r in ok if r["f_root"] == 3 and r["c_root"] == 3]
    any3 = [r for r in rows if r["f_root"] == 3 or r["c_root"] == 3]
    doc12 = [r for r in ok if r["f_root"] in (1, 2) and r["c_root"] in (1, 2)]
    any12 = [r for r in rows if r["f_root"] in (1, 2) or r["c_root"] in (1, 2)]
    both5 = [r for r in ok if r["f_root"] == 5 and r["c_root"] == 5]
    any5 = [r for r in rows if r["f_root"] == 5 or r["c_root"] == 5]
    md += ["## 3. 根因 3（模型没理解或没用上）的占比", "",
           "| 口径 | 根因 3 | 对照：根因 1 或 2（文档问题） | 对照：根因 5（参考或评分可疑） |", "|---|---:|---:|---:|",
           f"| 下限：两家都判为该根因 | {pct(len(both3), n)} | {pct(len(doc12), n)} | {pct(len(both5), n)} |",
           f"| 上限：至少一家判为该根因 | {pct(len(any3), n)} | {pct(len(any12), n)} | {pct(len(any5), n)} |", ""]

    # 4. splits
    def split(key: str, title: str) -> list[str]:
        out = [f"### 按{title}", "", f"| {title} | 条目 | 根因 1/2/3/4/5（Flash） | 根因 1/2/3/4/5（Codex） | 根因 3 下限–上限 |",
               "|---|---:|---|---|---|"]
        for v in sorted({r[key] for r in rows}, key=str):
            g = [r for r in rows if r[key] == v]
            fc = "/".join(str(sum(r["f_root"] == k for r in g)) for k in ROOTS)
            cc = "/".join(str(sum(r["c_root"] == k for r in g)) for k in ROOTS)
            lo = sum(r["f_root"] == 3 and r["c_root"] == 3 for r in g)
            hi = sum(r["f_root"] == 3 or r["c_root"] == 3 for r in g)
            out.append(f"| {v} | {len(g)} | {fc} | {cc} | {lo}–{hi} |")
        return out + [""]

    md += ["## 4. 按题目标签拆根因", ""] + split("dep", "语义依赖") + split("level", "Q 级") + split("persona", "用户类型")
    md += [f"低区分度题的条目：{sum(r['low'] for r in rows)} 条，已含在上面各表里。", ""]

    # 5. root cause 5
    by_q: dict[str, list[dict]] = {}
    for r in any5:
        by_q.setdefault(r["qid"], []).append(r)
    md += ["## 5. 根因 5（参考答案或评分可疑）的题号清单", "",
           "交题库负责方核对，本卡不改分。「两家」= Flash 与 Codex 都判为 5。", "",
           "| 题 | 两家 | 仅 Flash | 仅 Codex |", "|---|---|---|---|"]
    for q in sorted(by_q, key=lambda x: int(x[1:])):
        g = by_q[q]
        cell = lambda pred: "、".join(f"r{r['round']}" for r in g if pred(r)) or "—"  # noqa: E731
        md.append(f"| {q} | {cell(lambda r: r['f_root'] == 5 and r['c_root'] == 5)} | "
                  f"{cell(lambda r: r['f_root'] == 5 and r['c_root'] != 5)} | {cell(lambda r: r['f_root'] != 5 and r['c_root'] == 5)} |")
    md += ["", f"共 {len(by_q)} 题；两家都判 5 的题：{len({r['qid'] for r in both5})} 题。", ""]

    # 6. doc evidence for agreed doc-problem items
    md += ["## 6. 两家都判为文档问题（根因 1 或 2）的条目与 L1 位置", "",
           "| 题 | 次 | Flash 根因 / 位置 | Codex 根因 / 位置 |", "|---|---:|---|---|"]
    for r in doc12:
        md.append(f"| {r['qid']} | {r['round']} | {r['f_root']} / {r['f_doc']} | {r['c_root']} / {r['c_doc']} |")
    md.append("")

    # 7. spot check
    dis = [r for r in ok if r["f_root"] != r["c_root"]]
    step = max(1, len(dis) // SPOT)
    pick = dis[::step][:SPOT]
    md += ["## 7. 用户抽检（待填）", "",
           f"根因不一致的条目共 {len(dis)} 条。按清单顺序等距抽 {len(pick)} 条，由用户判定哪家对，或给出第三种判定。", "",
           "| 题 | 次 | Flash 类别 / 根因 | Codex 类别 / 根因 | 用户判定 | 说明 |", "|---|---:|---|---|---|---|"]
    for r in pick:
        md.append(f"| {r['qid']} | {r['round']} | {r['f_cat']} / {r['f_root']} | {r['c_cat']} / {r['c_root']} |  |  |")
    md.append("")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
