"""T13 report: SQL direct-answer results per cell, from the committed run logs.

    uv run python scripts/sql_direct_report.py --run 20261018-T13-sql-direct-01-rescore-01 \\
        --before 20261018-T13-sql-direct-01 --eval-tag eval-v1.2 > reports/results/sql_direct.md

The question bank (``$SEMDEBT_EVAL_DIR``) must be the clean checkout of ``--eval-tag``.
Main-table rules are the T12 ones (decisions/2026-10-18-g3-passed.md): judge questions are
a stratum of their own, out of every accuracy denominator together with their refusals and
exec errors; low-discrimination questions are reported in a separate column. SQL-L1.5S is
split by the T06 summary-coverage label. Only question ids reach the output.

``--run`` may be an offline rescore (harness.rescore) of ``--before``: then the verdicts are
the rescore's, ``--before``'s provisional ones appear only as a before → after column and a
list of flipped attempts, and cost, cache and harness commits are those of the original run.
Not a verdict, out of every denominator and listed one by one: ``pending`` with reason
``score_timeout`` and scorer v2's ``unscored`` (spec §6.5). Execution errors are broken down
by the engine's error code; a syntax error at an unquoted Chinese identifier is
「中文别名语法错误」.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.cells import PRICES_OFFPEAK  # noqa: E402
from harness.questions import eval_dir, load_questions, verify_eval_tag  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CELLS = ("SQL-L0", "SQL-R", "SQL-L1", "SQL-L1c", "SQL-L1.5W", "SQL-L1.5S")
FOUR = ("correct", "wrong", "exec_error", "refused")
REPS = 3


def records(run_id: str, cell: str) -> list[dict]:
    path = REPO / "runs" / run_id / f"{cell}.jsonl"
    if not path.exists():   # a cell not run yet shows up as missing in the completeness table
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%（{n}/{d}）" if d else "—"


def share(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "—"


def correct(recs: list[dict]) -> int:
    return sum(r["final"]["outcome"] == "correct" for r in recs)


def all_three(recs: list[dict]) -> tuple[int, int]:
    """Questions answered correctly in all three attempts / questions."""
    by_q: dict[str, list[str]] = {}
    for r in recs:
        by_q.setdefault(r["qid"], []).append(r["final"]["outcome"])
    return sum(len(v) == REPS and all(o == "correct" for o in v) for v in by_q.values()), len(by_q)


def cold(turn: dict) -> bool:
    u = turn["usage"]
    return u["cache_miss_tokens"] > u["prompt_tokens"] / 2


def no_verdict(r: dict) -> bool:
    """A done attempt the scorer gave no verdict for (judge questions are a stratum of their own)."""
    return r["final"].get("pending") == "score_timeout" or r["final"]["outcome"] == "unscored"


# ClickHouse error code → failure category (the logged message may be cut before the code's name)
ERROR_GROUPS = (("中文别名语法错误", ()), ("其他语法错误", (62,)), ("标识符与作用域", (47, 206, 207, 403)),
                ("聚合用法", (184, 215)), ("UNION 缺 ALL/DISTINCT", (558,)), ("类型与参数", (36, 38, 43)),
                ("函数与特性不支持", (46, 48, 306)))
CJK = re.compile(r"[\u3400-\u9fff]")


def error_group(execution: dict, query: str | None) -> tuple[str, str | None]:
    """(category, for 中文别名语法错误: 'AS' when the token is right after AS, else 'other')."""
    msg = execution.get("error") or ""
    if execution.get("error_class") != "engine_error":
        return execution.get("error_class") or "unknown", None
    code = int(m.group(1)) if (m := re.match(r"Code: (\d+)", msg)) else None
    at = re.search(r"failed at position \d+ \((.)\)[^:]*: (\S*)", msg)
    if code == 62 and at and CJK.match(at.group(1)):
        word = re.match(r"[\w\u3400-\u9fff]+", at.group(2))
        after_as = bool(word) and re.search(r"\bAS\s+" + re.escape(word.group(0)), query or "", re.I) is not None
        return "中文别名语法错误", "AS" if after_as else "other"
    for name, codes in ERROR_GROUPS:
        if code in codes:
            return name, None
    return f"其他（Code {code}）", None


def coverage() -> dict[str, str]:
    data = json.loads((eval_dir() / "audit" / "T06-summary-coverage.json").read_text(encoding="utf-8"))
    return {r["question_id"]: r["summary_coverage"] for r in data["records"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run-id under runs/")
    ap.add_argument("--eval-tag", default="eval-v1.2")
    ap.add_argument("--before", help="the original run when --run is its offline rescore (provisional verdicts)")
    ap.add_argument("--verdicts", help="one line saying where the verdicts in the logs come from")
    args = ap.parse_args()
    if args.verdicts is None:
        args.verdicts = ("`harness-v1.1`（评分器 v2，decisions/2026-10-18-scorer-spec-v2.md）离线重评，为最终判定；"
                         "运行时的暂定判定只出现在「暂定 → 重评」一列与翻转清单里" if args.before else
                         "运行时评分器的当场判定（暂定）。最终数字以离线重评为准"
                         "（decisions/2026-10-18-harness-v1-1-scorer-fixes.md 第二节第 6 条）")

    commit = verify_eval_tag(args.eval_tag)
    qs = {q.qid: q for q in load_questions()}
    judge = {qid for qid, q in qs.items() if q.scoring == "judge"}
    low = {qid for qid, q in qs.items() if q.meta["low_discrimination"]}
    cov = coverage()
    data = {c: records(args.run, c) for c in CELLS}
    done = {c: [r for r in v if r.get("status") == "done"] for c, v in data.items()}
    # score_timeout (harness/score_guard.py) and unscored (scorer v2) are no verdict: out of every
    # denominator, listed one by one
    timeout = {c: [r for r in done[c] if no_verdict(r)] for c in CELLS}
    done_all = done
    done = {c: [r for r in v if not no_verdict(r)] for c, v in done_all.items()}
    # the original run: provisional verdicts (before → after), and the calls, cost and commits
    orig_all = {c: [r for r in records(args.before, c) if r.get("status") == "done"] for c in CELLS} if args.before else done_all
    orig = {c: [r for r in v if not no_verdict(r)] for c, v in orig_all.items()}
    first = [r for c in CELLS for r in orig_all[c]]
    fps: dict[str, int] = {}
    for r in first:
        for t in r["turns"]:
            fps[t.get("system_fingerprint")] = fps.get(t.get("system_fingerprint"), 0) + 1
    versions = sorted({(r["eval_tag"], r["eval_commit"], r.get("semantic_tag"), r["harness_commit"]) for r in first})

    out = ["# SQL 直答全量结果（T13，自动生成）", "",
           f"- 运行：`runs/{args.run}/`；模型 `deepseek-flash`；每题 {REPS} 次",
           f"- 版本（{'原运行' if args.before else '日志'}）：{versions}；题库 `{args.eval_tag}` = `{commit[:7]}`",
           *([f"- 重评：`runs/{args.run}/` 由 `harness.rescore` 离线重评原运行 `runs/{args.before}/`（无模型调用、无查询执行），"
              f"harness 提交 {sorted({r['rescored_from']['harness_commit'] for c in CELLS for r in done_all[c]})}，"
              f"题库提交 {sorted({r['eval_commit'] for c in CELLS for r in done_all[c]})}"] if args.before else []),
           f"- 指纹（全部调用）：{fps}",
           f"- 题集 {len(qs)} 题：judge {len(judge)} 题（单列一档，不进任何准确率分母，含其拒答与执行报错）{sorted(judge)}；"
           f"低区分度 {len(low)} 题（主表单列）{sorted(low)}",
           f"- 主表分母：确定性评分题 {len(qs) - len(judge)} 题；不含低区分度 {len(set(qs) - judge - low)} 题",
           "- 生成：`uv run python scripts/sql_direct_report.py --run "
           f"{args.run}{f' --before {args.before}' if args.before else ''} --eval-tag {args.eval_tag}`",
           f"- **判定来源**：{args.verdicts}",
           f"- 没有判定的作答（打分超时 `score_timeout` 与 `unscored`，不进任何分母，逐条见文末）："
           f"{sum(len(v) for v in timeout.values())} 条", ""]

    out += ["## 完整性", "", "| 单元 | 作答（done） | 应有 | 非 done 行 | 缺失的 (题, 次) |", "|---|---:|---:|---:|---|"]
    for c in CELLS:
        have = {(r["qid"], r["rep"]) for r in done_all[c]}
        missing = sorted({(q, k) for q in qs for k in range(1, REPS + 1)} - have)
        dup = len(done_all[c]) - len(have)
        out.append(f"| {c} | {len(done_all[c])} | {len(qs) * REPS} | {len(data[c]) - len(done_all[c])} | {missing or '无'}"
                   f"{f'；重复 {dup}' if dup else ''} |")

    out += ["", "## 主表（judge 题不计；准确率 = 最终正确 / 作答）", "",
            "| 单元 | 准确率（不含低区分度） | 准确率（含低区分度） | 首次即对率（不含低区分度） | 三次全对率（不含低区分度，按题） |"
            + (" 暂定 → 重评（不含低区分度） | 翻转（作答条数） |" if args.before else ""),
            "|---|---|---|---|---|" + ("---|---:|" if args.before else "")]
    flips = {}
    for c in CELLS:
        scored = [r for r in done[c] if r["qid"] not in judge]
        main_ = [r for r in scored if r["qid"] not in low]
        a3, nq = all_three(main_)
        row = (f"| {c} | {pct(correct(main_), len(main_))} | {pct(correct(scored), len(scored))} "
               f"| {pct(sum(r['first'] == 'correct' for r in main_), len(main_))} | {pct(a3, nq)} |")
        if args.before:
            old = [r for r in orig[c] if r["qid"] not in judge | low]
            prev = {(r["qid"], r["rep"]): r["final"]["outcome"] for r in orig_all[c]}
            flips[c] = sorted(((r["qid"], r["rep"], prev[(r["qid"], r["rep"])], r["final"]["outcome"])
                               for r in done_all[c] if r["qid"] not in judge
                               and prev[(r["qid"], r["rep"])] != r["final"]["outcome"]), key=lambda f: (int(f[0][1:]), f[1]))
            row += f" {share(correct(old), len(old))} → {share(correct(main_), len(main_))} | {len(flips[c])} |"
        out.append(row)
    if args.before:
        out += ["", "暂定 = 原运行时 `harness-v1` 评分器的当场判定（其打分超时不进分母）；重评 = 本表。"
                "翻转 = 最终结果与暂定不同的作答（judge 题不计，含低区分度；`pending` 打分超时变为判定也计入）。"]

    out += ["", "## 四种结果占比（judge 题不计，含低区分度；合计 100%）", "",
            "| 单元 | 作答 | 正确 | 错答 | 执行失败 | 拒答 | 合计 |", "|---|---:|---|---|---|---|---|"]
    for c in CELLS:
        scored = [r for r in done[c] if r["qid"] not in judge]
        n = len(scored)
        k = {o: sum(r["final"]["outcome"] == o for r in scored) for o in FOUR}
        other = n - sum(k.values())
        out.append(f"| {c} | {n} | " + " | ".join(share(k[o], n) for o in FOUR)
                   + f" | {share(sum(k.values()), n)}{f'（另有 {other} 条非四类）' if other else ''} |")

    out += ["", "### 低区分度题单列（judge 题不计）", "", "| 单元 | 作答 | 准确率 | 错答 | 执行失败 | 拒答 |", "|---|---:|---|---|---|---|"]
    for c in CELLS:
        s = [r for r in done[c] if r["qid"] in low and r["qid"] not in judge]
        out.append(f"| {c} | {len(s)} | " + " | ".join(share(sum(r['final']['outcome'] == o for r in s), len(s)) for o in FOUR) + " |")

    out += ["", "### 执行失败的分类（judge 题不计）", "",
            "按引擎报错码归类。「中文别名语法错误」= 语法错误停在未加引号的中文标识符上"
            "（括号里是停在 `AS` 之后的别名处的条数；其余是 CTE 名或对别名的引用）。"
            "首轮报错 = 触发「修一次」的报错；最终 = 修后仍失败。", "",
            "| 单元 | 首轮报错（触发修一次） | 修后正确 | 最终执行失败 |", "|---|---|---:|---|"]

    def groups(turns: list[dict]) -> str:
        k: Counter = Counter()
        alias = 0
        for t in turns:
            g, where = error_group(t["exec"], t.get("query"))
            k[g] += 1
            alias += where == "AS"
        if not k:
            return "无"
        return "；".join(f"{g} {n}" + (f"（AS {alias}）" if g == "中文别名语法错误" else "") for g, n in k.most_common())
    totals: Counter = Counter()
    for c in CELLS:
        scored = [r for r in done[c] if r["qid"] not in judge]
        trig = [r["turns"][0] for r in scored if r["fixed"]]
        last = [r["turns"][-1] for r in scored if r["final"]["outcome"] == "exec_error"]
        totals.update(error_group(t["exec"], t.get("query"))[0] for t in trig + last)
        out.append(f"| {c} | {len(trig)}：{groups(trig)} "
                   f"| {sum(r['fixed'] and r['final']['outcome'] == 'correct' for r in scored)} | {len(last)}：{groups(last)} |")
    out += ["", f"合计（首轮报错 + 最终执行失败）：{dict(totals.most_common())}。"]

    out += ["", "## judge 题（单列一档，待 `judge-v1` 离线评）", "",
            "| 单元 | 作答 | 返回行集（pending） | 错答 | 执行失败 | 拒答 |", "|---|---:|---:|---:|---:|---:|"]
    for c in CELLS:
        s = [r for r in done[c] if r["qid"] in judge]
        k = {o: sum(r["final"]["outcome"] == o for r in s) for o in ("pending", "wrong", "exec_error", "refused")}
        out.append(f"| {c} | {len(s)} | {k['pending']} | {k['wrong']} | {k['exec_error']} | {k['refused']} |")

    out += ["", "## SQL-L1.5S 按汇总层能否回答（T06 覆盖标注；judge 题不计）", "",
            "| 覆盖 | 题数 | 作答 | 准确率 | 错答率 | 执行失败率 | 拒答率 |", "|---|---:|---:|---|---|---|---|"]
    for label in sorted({cov[q] for q in qs}):
        ids = {q for q in qs if cov[q] == label and q not in judge}
        s = [r for r in done["SQL-L1.5S"] if r["qid"] in ids]
        out.append(f"| {label} | {len(ids)} | {len(s)} | "
                   + " | ".join(share(sum(r['final']['outcome'] == o for r in s), len(s)) for o in FOUR) + " |")
    out += ["", "（覆盖外的拒答是期望行为：汇总层答不了的题，拒答优于错答。不含低区分度的同口径："]
    for label in sorted({cov[q] for q in qs}):
        ids = {q for q in qs if cov[q] == label and q not in judge and q not in low}
        s = [r for r in done["SQL-L1.5S"] if r["qid"] in ids]
        out.append(f"{label} {len(ids)} 题：准确率 {share(correct(s), len(s))}，错答 "
                   f"{share(sum(r['final']['outcome'] == 'wrong' for r in s), len(s))}，拒答 "
                   f"{share(sum(r['final']['outcome'] == 'refused' for r in s), len(s))}；")
    out[-1] = out[-1].rstrip("；") + "。）"

    out += ["", "## 按 Q 级（judge 题不计，不含低区分度）", "", "| 单元 | Q1 | Q2 | Q3 |", "|---|---|---|---|"]
    for c in CELLS:
        row = []
        for lv in ("Q1", "Q2", "Q3"):
            s = [r for r in done[c] if qs[r["qid"]].meta["q_level"] == lv and r["qid"] not in judge | low]
            row.append(pct(correct(s), len(s)))
        out.append(f"| {c} | " + " | ".join(row) + " |")

    out += ["", "## 费用与缓存（全部作答，含 judge；错峰价）", "",
            "单元按顺序在一个进程里连续跑完，单元之间切换 "
            f"{len(CELLS) - 1} 次；每个单元的首个调用单独先跑以写好前缀缓存。冷启动 = 未命中 > prompt 一半的调用。", "",
            "| 单元 | 调用 | 冷启动 | 输入 token | 命中率 | 输出 token | 费用（元） |", "|---|---:|---:|---:|---:|---:|---:|"]
    total = 0.0
    for c in CELLS:
        turns = [t for r in orig_all[c] for t in r["turns"]]
        pt = sum(t["usage"]["prompt_tokens"] for t in turns)
        hit = sum(t["usage"]["cache_hit_tokens"] for t in turns)
        cost = sum(r.get("cost_cny") or 0 for r in orig_all[c])
        total += cost
        out.append(f"| {c} | {len(turns)} | {sum(cold(t) for t in turns)} | {pt:,} | {share(hit, pt)} "
                   f"| {sum(t['usage']['completion_tokens'] for t in turns):,} | {cost:.2f} |")
    peak = sum(bool(r.get("peak")) for r in first)
    out += [f"| 合计 | | | | | | {total:.2f} |", "",
            f"价格：`harness/cells.py` 的 `PRICES_OFFPEAK['deepseek-flash']` = {PRICES_OFFPEAK['deepseek-flash']}；"
            f"高峰时段作答 {peak} 条。"]
    if args.before:
        out += ["", "## 翻转的作答（暂定 → 重评；judge 题不计）", ""]
        trans: Counter = Counter(f"{a} → {b}" for c in CELLS for _, _, a, b in flips[c])
        out += [f"合计 {sum(trans.values())} 条：{dict(trans.most_common())}。", "",
                "| 单元 | 题 | 次 | 暂定 | 重评 |", "|---|---|---:|---|---|"]
        out += [f"| {c} | {q} | {k} | {a} | {b} |" for c in CELLS for q, k, a, b in flips[c]] or ["| 无 | | | | |"]
    out += ["", "## 没有判定的作答（`score_timeout` 与 `unscored`）", "",
            "不是判定，不进任何分母。", "",
            "| 单元 | 题 | 次 | 结果 | 原因 |", "|---|---|---:|---|---|"]
    rows_t = [(c, r) for c in CELLS for r in sorted(timeout[c], key=lambda r: (r["qid"], r["rep"]))]
    out += [f"| {c} | {r['qid']} | {r['rep']} | {r['final']['outcome']} | {r['final'].get('pending') or r['final'].get('reason')} |"
            for c, r in rows_t] or ["| 无 | | | | |"]
    hc: dict = {}
    for c in CELLS:
        for r in orig_all[c]:
            hc.setdefault(c, {}).setdefault(r["harness_commit"], 0)
            hc[c][r["harness_commit"]] += 1
    out += ["", "## 各单元的 harness 提交（原运行：作答时的提交）", "", "| 单元 | 提交（条数） |", "|---|---|"]
    out += [f"| {c} | " + "，".join(f"`{k}`（{v}）" for k, v in hc[c].items()) + " |" for c in CELLS]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
