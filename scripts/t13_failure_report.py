"""T13 failure report for one cell: scorer-diagnosis buckets, per-question attribution,
category summary, and a comparison with the T12 pilot's SQL-L1 (Flash, final scoring).

Reads only the run log, runs-raw and the question bank checkout of ``--eval-tag``; never
opens chDB. Hand attribution comes from ``--verdicts`` (question ids, categories and short
evidence only). Only question ids reach the output.

    uv run python scripts/t13_failure_report.py --run 20261018-T13-sql-direct-01 --cell SQL-L0 \\
        --verdicts scripts/t13_l0_failure_verdicts.yaml > reports/results/T13-L0-failures.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.questions import load_questions, pilot_ids, verify_eval_tag  # noqa: E402
from scripts.t13_failure_dump import codes_only, raw_dir  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CATS = {"a": "找错表或字段", "b": "连接错", "c": "口径", "d": "技术字段或脏数据", "e": "SQL 逻辑错",
        "f": "展示差异（指令遵循）", "g": "拒答", "h": "判不清"}
BUCKETS = ("缺列", "行数不符", "数值不符", "标签不符", "只给编码", "拒答", "执行错误")
T12_RUN, T12_VERDICTS = "20261018-T12-pilot-flash-01-rescore-01", REPO / "scripts" / "t12_final_verdicts.yaml"


def bucket(r: dict, codes: bool) -> str:
    f = r["final"]
    if f["outcome"] == "refused":
        return "拒答"
    if f["outcome"] == "exec_error":
        return "执行错误"
    if codes:
        return "只给编码"
    if f["reason"] == "missing_columns":
        return "缺列"
    if f["reason"] in ("row_count", "top_n_row_count", "selection_object_count"):
        return "行数不符"
    if f["sensitivity"] == "string_or_label_only":
        return "标签不符"
    return "数值不符"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--cell", required=True)
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--eval-tag", default="eval-v1.1")
    args = ap.parse_args()

    commit = verify_eval_tag(args.eval_tag)
    qs = {q.qid: q for q in load_questions()}
    judge = {q for q, x in qs.items() if x.scoring == "judge"}
    low = {q for q, x in qs.items() if x.meta["low_discrimination"]}
    ver = yaml.safe_load(Path(args.verdicts).read_text(encoding="utf-8"))
    recs = [json.loads(l) for l in (REPO / "runs" / args.run / f"{args.cell}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    done = [r for r in recs if r.get("status") == "done"]
    raw = raw_dir(args.run, args.cell)

    def codes(r: dict) -> bool:
        if r["final"]["outcome"] != "wrong":
            return False
        last = r["turns"][-1]
        ex = json.loads((raw / f"{r['qid']}_r{r['rep']}_t{last['turn']}.exec.json").read_text(encoding="utf-8"))
        q = qs[r["qid"]]
        rr = (q.ref_rules or [None])[0] or q.rules or {}
        return bool(ex.get("columns")) and codes_only(ex["columns"], rr.get("value_types") or [], rr.get("required_columns"))

    strata = {"主表": [r for r in done if r["qid"] not in judge | low],
              "低区分度": [r for r in done if r["qid"] in low and r["qid"] not in judge],
              "judge": [r for r in done if r["qid"] in judge]}
    bad = {k: [r for r in v if r["final"]["outcome"] not in ("correct", "pending")] for k, v in strata.items()}

    out = [f"# {args.cell} 失败归因（T13，`runs/{args.run}/`）", "",
           f"- 题库 `{args.eval_tag}` = `{commit[:7]}`；只用运行日志与 runs-raw 存下的行集，未打开 chDB",
           f"- 口径：主表 = 确定性评分题去掉低区分度（{len(set(qs) - judge - low)} 题 × 3）；主表内不对的作答 {len(bad['主表'])} 条（含拒答、执行错误）；"
           f"低区分度 {len(bad['低区分度'])} 条、judge 题 {len(bad['judge'])} 条（不含返回行集待评的 pending）单列",
           f"- 生成：`uv run python scripts/t13_failure_report.py --run {args.run} --cell {args.cell} --verdicts {args.verdicts}`；"
           f"人工归因 `{args.verdicts}`（逐题审过的子 agent 初稿，见文末说明）", ""]

    out += ["## 一、按评分器诊断自动分桶", "",
            "「只给编码」= 必答参考列含文本列，作答没有任何文本列（先于其他桶判定）；行数不符含 Top-N 行数与选取对象数不符；"
            "数值不符含参考无数值列时的取值不符（`no_numeric_reference`）。", "",
            "| 分层 | 条数 | " + " | ".join(BUCKETS) + " |", "|---|---:|" + "---:|" * len(BUCKETS)]
    for k, v in bad.items():
        c = Counter(bucket(r, codes(r)) for r in v)
        out.append(f"| {k} | {len(v)} | " + " | ".join(str(c.get(b, 0)) for b in BUCKETS) + " |")
    raw_reasons = Counter((r["final"]["outcome"], r["final"]["reason"], r["final"]["sensitivity"]) for r in bad["主表"])
    out += ["", "主表内评分器原始诊断：" + "；".join(f"{o}/{rs or '—'}/{s or '—'} {n}" for (o, rs, s), n in raw_reasons.most_common()), ""]

    def per_q(rs: list[dict]) -> list[str]:
        rows = ["| 题 | Q 级 | 错几轮 | 类别 | 各轮 | 证据 |", "|---|---|---:|---|---|---|"]
        for qid in sorted({r["qid"] for r in rs}, key=lambda x: (len(x), x)):
            v = ver[qid]
            per = {a["rep"]: a["cat"] for a in v["attempts"]}
            mine = sorted(r["rep"] for r in rs if r["qid"] == qid)
            if sorted(per) != mine:
                raise SystemExit(f"{qid}: verdict reps {sorted(per)} != failing reps {mine}")
            rows.append(f"| {qid} | {qs[qid].meta['q_level']} | {len(mine)} | {v['summary_cat']} {CATS[v['summary_cat']]} "
                        f"| {' '.join(f'r{k}:{per[k]}' for k in mine)} | {v['evidence']} |")
        return rows

    out += ["## 二、逐题归因（主表）", "", "类别：" + "；".join(f"{k} {n}" for k, n in CATS.items()) + "。「各轮」是每一轮各自的类别。", ""]
    out += per_q(bad["主表"])
    out += ["", "### 低区分度（单列）", ""] + per_q(bad["低区分度"])
    jc = Counter(r["final"]["outcome"] for r in strata["judge"])
    out += ["", f"### judge 题（单列，待 `judge-v1`）", "",
            f"{len(strata['judge'])} 条作答：" + "，".join(f"{o} {n}" for o, n in jc.most_common()) +
            "。pending 的行集存 runs-raw 待离线评；非 pending 的：" +
            "；".join(f"{r['qid']} r{r['rep']} {r['final']['outcome']}{'（' + r['final']['error_class'] + '）' if r['final']['error_class'] else ''}"
                     for r in sorted(bad["judge"], key=lambda r: (r["qid"], r["rep"]))) + "。"]

    def summary(rs: list[dict]) -> list[str]:
        att = Counter()
        qn: dict[str, set] = {}
        for r in rs:
            cat = next(a["cat"] for a in ver[r["qid"]]["attempts"] if a["rep"] == r["rep"])
            att[cat] += 1
            qn.setdefault(cat, set()).add(r["qid"])
        rows = ["| 类别 | 条数 | 占比 | 涉及题数 |", "|---|---:|---:|---:|"]
        for k, n in CATS.items():
            if att.get(k):
                rows.append(f"| {k} {n} | {att[k]} | {100 * att[k] / len(rs):.1f}% | {len(qn[k])} |")
        rows.append(f"| 合计 | {len(rs)} | 100% | {len({r['qid'] for r in rs})}（题可跨类） |")
        return rows

    out += ["", "## 三、汇总（主表）", ""] + summary(bad["主表"])
    ids = sorted({r["qid"] for r in bad["主表"]})
    cons = [q for q in ids if len({a["cat"] for a in ver[q]["attempts"]}) == 1]
    multi = [q for q in ids if len(ver[q]["attempts"]) > 1]
    cons_multi = [q for q in multi if q in cons]
    out += ["", f"- 出错题 {len(ids)} 道：各轮原因一致 {len(cons)} 道、轮间不一致 {len(ids) - len(cons)} 道 "
            f"{sorted(set(ids) - set(cons), key=lambda x: (len(x), x))}。",
            f"- 只看错了 2 轮以上的 {len(multi)} 道：一致 {len(cons_multi)} 道、不一致 {len(multi) - len(cons_multi)} 道"
            "（只错 1 轮的题天然「一致」）。", "", "### 低区分度汇总", ""] + summary(bad["低区分度"])

    # T12 comparison: Flash SQL-L1, final scoring (t12_final_verdicts.yaml: every attempt still not
    # correct under 「最终」 carries an attribution; anything else counts correct).
    t12v = yaml.safe_load(T12_VERDICTS.read_text(encoding="utf-8"))["attribution"]
    t12 = [json.loads(l) for l in (REPO / "runs" / T12_RUN / "SQL-L1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    pilot = pilot_ids()
    out += ["", "## 四、与 T12 试跑 SQL-L1（Flash，最终口径）对比", "",
            f"只比两边都有的题：T12 试跑 {len(pilot)} 题（`{T12_RUN}`，最终口径归因 `scripts/t12_final_verdicts.yaml`）。"
            "T12 用的是旧系统提示（展示约定第 6–15 条之前），最终口径已把旧提示下不能要求的展示项算对；T13 用 `harness-v1` 新提示、严格评分。"
            "L1 的「语义层差距」对应本表 c（口径）一类。", "",
            "| 题 | 分层 | L1 对几轮 | L1 不对的原因 | L0 对几轮 | L0 不对的原因（本报告） |", "|---|---|---:|---|---:|---|"]
    tally = Counter()
    for qid in sorted(pilot, key=lambda x: (len(x), x)):
        l1 = [r for r in t12 if r["qid"] == qid]
        l1_bad = {r["rep"]: t12v[k]["category"] for r in l1 if (k := f"deepseek-flash SQL-L1 {qid} {r['rep']}") in t12v}
        l0 = [r for r in done if r["qid"] == qid]
        l0_ok = sum(r["final"]["outcome"] == "correct" for r in l0)
        stratum = "judge" if qid in judge else "低区分度" if qid in low else "主表"
        if qid in judge:
            l0_txt = "、".join(f"r{r['rep']} {r['final']['outcome']}" for r in sorted(l0, key=lambda r: r["rep"]))
            l0_ok_txt = "—"
        else:
            l0_txt = "；".join(f"r{a['rep']} {a['cat']}" for a in ver[qid]["attempts"]) if qid in ver else "—"
            l0_ok_txt = str(l0_ok)
            l1_ok = len(l1) - len(l1_bad)
            if stratum == "主表":
                tally["L1 全对、L0 有错" if l1_ok == 3 and l0_ok < 3 else "两边都有错" if l1_ok < 3 and l0_ok < 3
                      else "两边全对" if l1_ok == 3 and l0_ok == 3 else "L1 有错、L0 全对"] += 1
        l1_txt = "；".join(f"r{k} {v}" for k, v in sorted(l1_bad.items())) or "—"
        out.append(f"| {qid} | {stratum} | {'—' if qid in judge else len(l1) - len(l1_bad)} | {l1_txt} | {l0_ok_txt} | {l0_txt} |")
    out += ["", "主表内：" + "；".join(f"{k} {n} 题" for k, n in tally.most_common()) + "。"]

    hs = [(q, v) for q, v in sorted(ver.items(), key=lambda x: (len(x[0]), x[0])) if any(a["cat"] == "h" for a in v["attempts"])]
    out += ["", "## 五、判不清（h）的条目与跟进", "",
            "h 不是模型能力的结论：多数是作答内容与参考一致、却因评分覆盖或题库规则判错。"
            "`harness-v1` 已冻结，按 G3 第二节只在报告注明，不改提示和评分器；涉及题库 `rules` 的交 Codex 核对。", ""]
    out += [f"- {q}（{' '.join('r%d' % a['rep'] for a in v['attempts'] if a['cat'] == 'h')}）：{v['evidence']}" for q, v in hs]
    out += ["", "## 说明", "",
            "- 逐题归因先由 4 个子 agent 按批次起草（输入为 `scripts/t13_failure_dump.py` 的转储：参考 SQL 与行集、各轮作答 SQL、"
            "评分器诊断、返回行集的前几行），再由 T13 会话逐类复核；复核改动写在归因文件开头。证据只写表名、字段名与数值。",
            "- 自动分桶完全来自评分器诊断，人工归因与它独立；两者口径不同（如「数值不符」可能源于找错字段、口径或连接）。"]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
