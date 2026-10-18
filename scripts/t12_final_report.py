"""T12 final rescore report: strict and final accuracy, every verdict change, every
remaining error attributed, and the model-choice rule applied to both.

Inputs: the rescore run logs (``runs/<pilot run>-rescore-01/``), the relaxation results
of ``scripts/t12_final_rescore.py`` (JSON under ``$SEMDEBT_DATA_DIR``) and the hand
verdicts in ``scripts/t12_final_verdicts.yaml``. Question metadata (Q level,
low-discrimination label, judge) comes from the bank, which must be eval-v1.1.

    SEMDEBT_EVAL_DIR=<eval-v1.1 worktree> uv run python scripts/t12_final_report.py \\
        --final-json $SEMDEBT_DATA_DIR/t12-final/final.json --write reports/T12-pilot.md

The section goes between the ``final-rescore`` markers at the top of the report
(created on first use); everything else in the file is kept. Only question ids reach
the output.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.questions import eval_dir, load_questions, pilot_ids, verify_eval_tag  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MODELS = ("deepseek-flash", "deepseek-v4-pro")
CELLS = ("SQL-L1", "SQL-R")
BEGIN, END = "<!-- final-rescore:begin -->", "<!-- final-rescore:end -->"
CATEGORIES = ("SQL 真错", "语义层差距", "指令遵循", "参考问题", "执行错误/超时/拒答")
RELAX = {"conv": "约定列只看有没有", "key": "只给键、没给名称（按键核对对象）", "trunc": "截断（自加 LIMIT，返回行全在参考里）"}


def key(r: dict) -> str:
    return f"{r['model']} {r['cell']} {r['qid']} {r['rep']}"


def short(r: dict) -> str:
    return f"{r['qid']} | {r['model'].removeprefix('deepseek-')} | {r['cell']} | r{r['rep']}"


def pct(n: int, d: int) -> str:
    return f"{n}/{d} = {100 * n / d:.1f}%" if d else "—"


def load(final_json: Path, verdicts: Path) -> tuple[list[dict], dict, dict, dict]:
    data = json.loads(final_json.read_text(encoding="utf-8"))
    v = yaml.safe_load(verdicts.read_text(encoding="utf-8"))
    pres, attr, p2s = v.get("presentation") or {}, v.get("attribution") or {}, v.get("pilot_to_strict") or {}
    rows = data["rows"]
    seen = {key(r) for r in rows}
    if len(rows) != 288 or len(seen) != 288:
        raise SystemExit(f"expected 288 distinct answers, got {len(rows)} / {len(seen)}")
    for k in list(pres) + list(attr):
        if k not in seen:
            raise SystemExit(f"verdict for an unknown answer: {k}")
    for r in rows:
        k = key(r)
        if r["final_diag"] == "timeout" or r.get("first_diag") == "timeout":
            raise SystemExit(f"{k}: a relaxation timed out; resolve it before reporting")
        if k in pres:
            if r["strict"] != "wrong" or r["final_relax"]:
                raise SystemExit(f"{k}: hand presentation verdict on an answer that is not a remaining wrong")
            r["final_how"] = "pres"
            r["final_out"] = "correct"
        elif r["final_relax"]:
            r["final_how"], r["final_out"] = r["final_relax"], "correct"
        else:
            r["final_how"], r["final_out"] = None, r["strict"]
        if r["n_turns"] == 1:
            r["first_out"] = r["final_out"]
        else:
            r["first_out"] = "correct" if r["first_relax"] else r["strict_first"]
        needs = r["final_out"] in ("wrong", "exec_error", "refused")
        if needs and k not in attr:
            raise SystemExit(f"{k}: final {r['final_out']} without an attribution")
        if not needs and k in attr:
            raise SystemExit(f"{k}: attribution on an answer that is {r['final_out']} under final")
        if k in attr and attr[k]["category"] not in CATEGORIES:
            raise SystemExit(f"{k}: unknown category {attr[k]['category']}")
    for r in rows:
        if r["pilot"] != "correct" and r["strict"] == "correct" and r["qid"] not in p2s:
            raise SystemExit(f"{key(r)}: wrong -> correct under strict without a reason for {r['qid']}")
    return rows, pres, attr, p2s


def headers_of(qids) -> dict[str, list[list[str]]]:
    from scripts.t12_final_rescore import ref_files
    files = ref_files()
    out = {}
    for qid in qids:
        out[qid] = []
        for f in files[qid]:
            with (eval_dir() / f).open(encoding="utf-8") as fh:
                out[qid].append(next(csv.reader(fh)))
    return out


def why_relaxed(r: dict, conv: dict, headers: dict, pres: dict) -> str:
    if r["final_how"] == "pres":
        p = pres[key(r)]
        return f"展示差异（{p['kind']}）：{p['note']}"
    parts = []
    for step in r["final_how"].split("+"):
        if step == "conv":
            names = sorted({headers[r["qid"]][i][c] for i, cols in enumerate(conv[r["qid"]]) for c in cols})
            parts.append(f"{RELAX['conv']}（{'、'.join(names)}）")
        else:
            parts.append(RELAX[step])
    return "；".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final-json", required=True)
    ap.add_argument("--verdicts", default=str(REPO / "scripts" / "t12_final_verdicts.yaml"))
    ap.add_argument("--eval-tag", default="eval-v1.1")
    ap.add_argument("--write", help="report to update between the final-rescore markers (default: stdout)")
    args = ap.parse_args()

    commit = verify_eval_tag(args.eval_tag)
    rows, pres, attr, p2s = load(Path(args.final_json), Path(args.verdicts))
    conv = json.loads(Path(args.final_json).read_text(encoding="utf-8"))["conv"]
    pilot = pilot_ids()
    meta = {q.qid: q for q in load_questions() if q.qid in set(pilot)}
    level = {qid: meta[qid].meta["q_level"] for qid in pilot}
    low = sorted((qid for qid in pilot if meta[qid].meta["low_discrimination"]), key=lambda x: int(x[1:]))
    judge = sorted(qid for qid in pilot if meta[qid].scoring == "judge")
    changed = sorted({r["qid"] for r in rows if r["question_changed"]})
    headers = headers_of(pilot)
    by = defaultdict(list)
    for r in rows:
        by[(r["model"], r["cell"])].append(r)

    def acc(recs, field, scope):
        s = [r for r in recs if r["qid"] not in judge and (scope == "all" or r["qid"] not in low)]
        return sum(r[field] == "correct" for r in s), len(s)

    o = [BEGIN, "", "## 最终重评（eval-v1.1，G3 选模型依据）", "",
         f"- 题库：`{args.eval_tag}` = `{commit[:7]}`（只读 worktree）；评分器：main `ea90587`（含 #91）；"
         f"重评日志 `runs/20261018-T12-pilot-{{flash,pro}}-01-rescore-01/`（`harness.rescore`，离线，不调用模型、不执行查询）",
         f"- 范围：试跑全部 {len(rows)} 条作答（2 模型 × SQL-L1、SQL-R × 24 题 × 3 轮），一条不漏",
         f"- judge 题 {judge} 不进任何分母（拒答、pending 一并拿出）；低区分度 {low} 不进主表，单列",
         f"- 本轮改写过题面的题在试跑里只有 {changed}（12 条）。`harness.rescore` 默认拒绝题面已变的行，"
         "这 12 条用显式开关 `--allow-changed-question` 按 eval-v1.1 参考评分、日志行标 `question_changed`；"
         "该开关只用于这 12 条。它们作答针对的是旧题面，单列，且 Q69 本就是低区分度题，不进主表",
         "- **严格**：eval-v1.1 下评分器的原始判定（日志里的 `final`）",
         "- **最终**：在严格的基础上，对旧系统提示下不能要求的项不扣分（`scripts/t12_final_rescore.py` 的通用放宽，"
         "加上逐条手核，见 `scripts/t12_final_verdicts.yaml`）：只给编码的按键核对对象；截断、自造标签、季度写法、宽表按内容核对；"
         "第 13–15 条的约定列（变化量的绝对值与百分比、名次、分母）只看有没有。约定列的界定是通用的："
         "eval-v1.1 新增为必答、且不在基础标注里（或追加在 eval-v1 参考之后）的列，标识键除外",
         ""]

    for name, field in (("严格", "strict"), ("最终", "final_out")):
        o += [f"### 准确率：{name}", "",
              "| 模型 | 单元 | 主表（不含低区分度、judge） | 含低区分度 | 首答即对（主表） |", "|---|---|---|---|---|"]
        for m in MODELS:
            for c in CELLS:
                recs = by[(m, c)]
                first_field = "strict_first" if field == "strict" else "first_out"
                o.append(f"| {m} | {c} | {pct(*acc(recs, field, 'main'))} | {pct(*acc(recs, field, 'all'))} "
                         f"| {pct(*acc(recs, first_field, 'main'))} |")
        o.append("")

    o += ["### 按 Q 级（主表；括号内为含低区分度）", "", "| 口径 | 模型 | 单元 | Q1 | Q2 | Q3 |", "|---|---|---|---|---|---|"]
    for name, field in (("严格", "strict"), ("最终", "final_out")):
        for m in MODELS:
            for c in CELLS:
                cells = []
                for lv in ("Q1", "Q2", "Q3"):
                    s = [r for r in by[(m, c)] if level[r["qid"]] == lv]
                    cells.append(f"{pct(*acc(s, field, 'main'))}（{pct(*acc(s, field, 'all'))}）")
                o.append(f"| {name} | {m} | {c} | " + " | ".join(cells) + " |")
    o.append("")

    outs = ("correct", "wrong", "exec_error", "refused", "pending")
    o += ["### 四种结果占比（全部 72 条作答，含低区分度与 judge；pending = judge 题返回了行集）", "",
          "| 口径 | 模型 | 单元 | " + " | ".join(outs) + " |", "|---|---|---|" + "---|" * len(outs)]
    for name, field in (("严格", "strict"), ("最终", "final_out")):
        for m in MODELS:
            for c in CELLS:
                n = Counter(r[field] for r in by[(m, c)])
                o.append(f"| {name} | {m} | {c} | " + " | ".join(f"{n[x]}（{100 * n[x] / 72:.0f}%）" for x in outs) + " |")
    o.append("")

    o += ["### 低区分度题（不进主表）", "", "| 题 | 模型 | 单元 | 严格 | 最终 |", "|---|---|---|---|---|"]
    for qid in low:
        for m in MODELS:
            for c in CELLS:
                s = sorted((r for r in by[(m, c)] if r["qid"] == qid), key=lambda r: r["rep"])
                mark = "（作答针对旧题面）" if qid in changed else ""
                o.append(f"| {qid}{mark} | {m} | {c} | {sum(r['strict'] == 'correct' for r in s)}/3 "
                         f"| {sum(r['final_out'] == 'correct' for r in s)}/3 |")
    o += ["", "### judge 题（不进任何分母）", "", "| 题 | 模型 | 单元 | 三轮结果 |", "|---|---|---|---|"]
    for qid in judge:
        for m in MODELS:
            for c in CELLS:
                s = sorted((r for r in by[(m, c)] if r["qid"] == qid), key=lambda r: r["rep"])
                o.append(f"| {qid} | {m} | {c} | {' / '.join(r['strict'] for r in s)} |")
    o.append("")

    # ---- verdict changes
    def changes(a: str, b: str):
        return sorted((r for r in rows if r[a] != r[b]), key=lambda r: (int(r["qid"][1:]), r["model"], r["cell"], r["rep"]))

    pilot_to_strict = changes("pilot", "strict")
    c2w = [r for r in pilot_to_strict if r["pilot"] == "correct"]
    w2c = [r for r in pilot_to_strict if r["pilot"] != "correct"]
    o += ["### 判定变化一：试跑原判定（eval-v1、旧评分器）→ 严格（eval-v1.1）", "",
          f"共 {len(pilot_to_strict)} 处：对 → 错 {len(c2w)}、错 → 对 {len(w2c)}，其他 "
          f"{len(pilot_to_strict) - len(c2w) - len(w2c)}。原因按「最终」口径下能否救回给出。", "",
          "**从对变错（单列）**", "", "| 题 | 模型 | 单元 | 轮次 | 原因 |", "|---|---|---|---|---|"]
    for r in c2w:
        why = why_relaxed(r, conv, headers, pres) if r["final_out"] == "correct" else \
            f"最终仍错：{attr[key(r)]['category']}；{attr[key(r)]['note']}"
        o.append(f"| {short(r)} | eval-v1.1 新增要求 → {why} |" if r["final_out"] == "correct" else f"| {short(r)} | {why} |")
    o += ["", "**从错变对**", "", "| 题 | 模型 | 单元 | 轮次 | 原因 |", "|---|---|---|---|---|"]
    o += [f"| {short(r)} | {p2s[r['qid']]} |" for r in w2c]
    o.append("")

    s2f = changes("strict", "final_out")
    o += ["### 判定变化二：严格 → 最终（逐条）", "",
          f"共 {len(s2f)} 处，全部是错 → 对（最终只放宽、不收紧，没有对 → 错）。", "",
          "| 题 | 模型 | 单元 | 轮次 | 原因 |", "|---|---|---|---|---|"]
    o += [f"| {short(r)} | {why_relaxed(r, conv, headers, pres)} |" for r in s2f]
    kinds = Counter((r["final_how"] if r["final_how"] != "pres" else "pres:" + pres[key(r)]["kind"]) for r in s2f)
    o += ["", "汇总：" + "；".join(f"{k} {n}" for k, n in sorted(kinds.items())), ""]

    # ---- attribution
    for cell in CELLS:
        rs = sorted((r for r in rows if r["cell"] == cell and key(r) in attr),
                    key=lambda r: (int(r["qid"][1:]), r["model"], r["rep"]))
        title = "SQL-L1" if cell == "SQL-L1" else "SQL-R（语义层差距即「缺约定（档位差距）」：约定写在 L1，R 没有）"
        o += [f"### 归因：{title}", "",
              "最终口径下仍不对的每一条（wrong、exec_error、refused）。judge 题的拒答也列出，但不进分母。", ""]
        tally = defaultdict(Counter)
        for r in rs:
            scope = "judge" if r["qid"] in judge else "低区分度" if r["qid"] in low else "主表"
            tally[r["model"]][(attr[key(r)]["category"], scope)] += 1
        o += ["| 模型 | " + " | ".join(CATEGORIES) + " |", "|---|" + "---|" * len(CATEGORIES)]
        for m in MODELS:
            cells = []
            for cat in CATEGORIES:
                t = {s: tally[m][(cat, s)] for s in ("主表", "低区分度", "judge")}
                extra = "，".join(f"{s} {n}" for s, n in t.items() if s != "主表" and n)
                cells.append(f"{t['主表']}" + (f"（另 {extra}）" if extra else ""))
            o.append(f"| {m} | " + " | ".join(cells) + " |")
        o += ["", "（数字是主表内的条数；括号里是低区分度题和 judge 题的条数。）", "",
              "| 题 | 模型 | 轮次 | 结果 | 类别 | 证据 |", "|---|---|---|---|---|---|"]
        for r in rs:
            a = attr[key(r)]
            tag = "（judge）" if r["qid"] in judge else "（低区分度）" if r["qid"] in low else ""
            o.append(f"| {r['qid']}{tag} | {r['model'].removeprefix('deepseek-')} | r{r['rep']} | {r['final_out']} "
                     f"| {a['category']} | {a['note']} |")
        o.append("")
    keyonly = [r for r in rows if r["final_how"] and "key" in r["final_how"]]
    o += ["**按裁决判错：只给键、没给名称。** 严格口径下只因此判错的：" +
          ("、".join(short(r).replace(" | ", " ") for r in keyonly) or "无") +
          "。旧提示没要求给名称，最终口径按键核对对象后算对（上表「只给键」）。SQL-L1 没有这一类："
          "Pro SQL-L1 Q34 r3 也只给了键，但同时漏了 4 个产品，归 SQL 真错。", ""]
    o += ["暂时归不了类的：无。Pro SQL-L1 Q73 r3（差额方向）与 Q82 r3（「团队」含不含间接下属）起初归「参考问题 · 题面歧义」，"
          "用户裁决改为语义层差距：都是 L1 没写的口径选择，记为调优候选，不补参考。", ""]

    # ---- model choice
    o += ["### 选模型（卡片规则）", "",
          "规则：Flash SQL-L1 < 50%，或 Pro 比 Flash 高 10 个百分点以上，就选 Pro；否则选 Flash。按主表（不含低区分度、judge）判。", "",
          "| 口径 | Flash SQL-L1 | Pro SQL-L1 | Pro − Flash | Flash < 50%？ | Pro 高 10 点以上？ | 结论 |", "|---|---|---|---|---|---|---|"]
    verdict = {}
    for name, field in (("严格", "strict"), ("最终", "final_out")):
        fn, fd = acc(by[("deepseek-flash", "SQL-L1")], field, "main")
        pn, pd = acc(by[("deepseek-v4-pro", "SQL-L1")], field, "main")
        f, p = 100 * fn / fd, 100 * pn / pd
        choose = "Pro" if f < 50 or p - f > 10 else "Flash"
        verdict[name] = choose
        o.append(f"| {name} | {pct(fn, fd)} | {pct(pn, pd)} | {p - f:+.1f} 点 | {'是' if f < 50 else '否'} "
                 f"| {'是' if p - f > 10 else '否'} | **{choose}** |")
    o += ["", ("两套数结论一致：**" + verdict["严格"] + "**。") if verdict["严格"] == verdict["最终"] else
          f"**两套数结论不同**：严格选 {verdict['严格']}，最终选 {verdict['最终']}。", "", END]
    section = "\n".join(o) + "\n"

    if not args.write:
        sys.stdout.write(section)
        return 0
    path = Path(args.write)
    text = path.read_text(encoding="utf-8")
    if BEGIN in text:
        head, rest = text.split(BEGIN, 1)
        text = head + section + "\n" + rest.split(END, 1)[1].lstrip("\n")
    else:
        title, _, body = text.partition("\n")
        text = (title + "\n\n" + section + "\n## 附：试跑原判定（eval-v1、旧评分器；历史，选模型不用）\n\n"
                + body.lstrip("\n"))
    path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
