"""T13 report: SQL direct-answer results per cell, from the committed run logs.

    uv run python scripts/sql_direct_report.py --run 20261018-T13-sql-direct-01 \\
        --eval-tag eval-v1.1 > reports/results/sql_direct.md

The question bank (``$SEMDEBT_EVAL_DIR``) must be the clean checkout of ``--eval-tag``.
Main-table rules are the T12 ones (decisions/2026-10-18-g3-passed.md): judge questions are
a stratum of their own, out of every accuracy denominator together with their refusals and
exec errors; low-discrimination questions are reported in a separate column. SQL-L1.5S is
split by the T06 summary-coverage label. Only question ids reach the output.
"""

from __future__ import annotations

import argparse
import json
import sys
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


def coverage() -> dict[str, str]:
    data = json.loads((eval_dir() / "audit" / "T06-summary-coverage.json").read_text(encoding="utf-8"))
    return {r["question_id"]: r["summary_coverage"] for r in data["records"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run-id under runs/")
    ap.add_argument("--eval-tag", default="eval-v1.1")
    ap.add_argument("--verdicts", default="运行时 `harness-v1` 评分器的当场判定（暂定）。"
                    "最终数字以 `harness-v1.1` 离线重评为准（decisions/2026-10-18-harness-v1-1-scorer-fixes.md 第二节第 6 条）",
                    help="one line saying where the verdicts in the logs come from")
    args = ap.parse_args()

    commit = verify_eval_tag(args.eval_tag)
    qs = {q.qid: q for q in load_questions()}
    judge = {qid for qid, q in qs.items() if q.scoring == "judge"}
    low = {qid for qid, q in qs.items() if q.meta["low_discrimination"]}
    cov = coverage()
    data = {c: records(args.run, c) for c in CELLS}
    done = {c: [r for r in v if r.get("status") == "done"] for c, v in data.items()}
    # score_timeout (harness/score_guard.py) is no verdict: out of every denominator, listed one by one
    timeout = {c: [r for r in done[c] if r["final"].get("pending") == "score_timeout"] for c in CELLS}
    done_all = done
    done = {c: [r for r in v if r["final"].get("pending") != "score_timeout"] for c, v in done_all.items()}
    first = [r for c in CELLS for r in done_all[c]]
    fps: dict[str, int] = {}
    for r in first:
        for t in r["turns"]:
            fps[t.get("system_fingerprint")] = fps.get(t.get("system_fingerprint"), 0) + 1
    versions = sorted({(r["eval_tag"], r["eval_commit"], r.get("semantic_tag"), r["harness_commit"]) for r in first})

    out = ["# SQL 直答全量结果（T13，自动生成）", "",
           f"- 运行：`runs/{args.run}/`；模型 `deepseek-flash`；每题 {REPS} 次",
           f"- 版本（日志）：{versions}；题库 `{args.eval_tag}` = `{commit[:7]}`",
           f"- 指纹（全部调用）：{fps}",
           f"- 题集 {len(qs)} 题：judge {len(judge)} 题（单列一档，不进任何准确率分母，含其拒答与执行报错）{sorted(judge)}；"
           f"低区分度 {len(low)} 题（主表单列）{sorted(low)}",
           f"- 主表分母：确定性评分题 {len(qs) - len(judge)} 题；不含低区分度 {len(set(qs) - judge - low)} 题",
           "- 生成：`uv run python scripts/sql_direct_report.py --run "
           f"{args.run} --eval-tag {args.eval_tag}`",
           f"- **判定来源**：{args.verdicts}",
           f"- 打分超时（`score_timeout`，不是判定，不进任何分母，逐条见文末）：{sum(len(v) for v in timeout.values())} 条", ""]

    out += ["## 完整性", "", "| 单元 | 作答（done） | 应有 | 非 done 行 | 缺失的 (题, 次) |", "|---|---:|---:|---:|---|"]
    for c in CELLS:
        have = {(r["qid"], r["rep"]) for r in done_all[c]}
        missing = sorted({(q, k) for q in qs for k in range(1, REPS + 1)} - have)
        dup = len(done_all[c]) - len(have)
        out.append(f"| {c} | {len(done_all[c])} | {len(qs) * REPS} | {len(data[c]) - len(done_all[c])} | {missing or '无'}"
                   f"{f'；重复 {dup}' if dup else ''} |")

    out += ["", "## 主表（judge 题不计；准确率 = 最终正确 / 作答）", "",
            "| 单元 | 准确率（不含低区分度） | 准确率（含低区分度） | 首次即对率（不含低区分度） | 三次全对率（不含低区分度，按题） |",
            "|---|---|---|---|---|"]
    for c in CELLS:
        scored = [r for r in done[c] if r["qid"] not in judge]
        main_ = [r for r in scored if r["qid"] not in low]
        a3, nq = all_three(main_)
        out.append(f"| {c} | {pct(correct(main_), len(main_))} | {pct(correct(scored), len(scored))} "
                   f"| {pct(sum(r['first'] == 'correct' for r in main_), len(main_))} | {pct(a3, nq)} |")

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

    out += ["", "### 执行失败的分类（最终结果；judge 题不计）", "", "| 单元 | 分类 | 触发修一次 | 修后正确 |", "|---|---|---:|---:|"]
    for c in CELLS:
        scored = [r for r in done[c] if r["qid"] not in judge]
        cls: dict = {}
        for r in scored:
            if r["final"]["outcome"] == "exec_error":
                cls[r["final"]["error_class"]] = cls.get(r["final"]["error_class"], 0) + 1
        out.append(f"| {c} | {cls or '无'} | {sum(r['fixed'] for r in scored)} "
                   f"| {sum(r['fixed'] and r['final']['outcome'] == 'correct' for r in scored)} |")

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
        turns = [t for r in done_all[c] for t in r["turns"]]
        pt = sum(t["usage"]["prompt_tokens"] for t in turns)
        hit = sum(t["usage"]["cache_hit_tokens"] for t in turns)
        cost = sum(r.get("cost_cny") or 0 for r in done_all[c])
        total += cost
        out.append(f"| {c} | {len(turns)} | {sum(cold(t) for t in turns)} | {pt:,} | {share(hit, pt)} "
                   f"| {sum(t['usage']['completion_tokens'] for t in turns):,} | {cost:.2f} |")
    peak = sum(bool(r.get("peak")) for r in first)
    out += [f"| 合计 | | | | | | {total:.2f} |", "",
            f"价格：`harness/cells.py` 的 `PRICES_OFFPEAK['deepseek-flash']` = {PRICES_OFFPEAK['deepseek-flash']}；"
            f"高峰时段作答 {peak} 条。"]
    out += ["", "## 打分超时（`score_timeout`）", "",
            "冻结评分器在这些作答上超过运行器的打分时限（SQL-R 的 Q79 三条为补写时的 120 秒，其余 10 秒）。"
            "行集在 runs-raw，`harness-v1.1` 合并后离线重评；最终报告里不能剩下。", "",
            "| 单元 | 题 | 次 | 判定来源 |", "|---|---|---:|---|"]
    rows_t = [(c, r) for c in CELLS for r in sorted(timeout[c], key=lambda r: (r["qid"], r["rep"]))]
    out += [f"| {c} | {r['qid']} | {r['rep']} | {'补写（runs-raw）' if 'backfilled_from_raw' in r else '运行时'} |"
            for c, r in rows_t] or ["| 无 | | | |"]
    hc: dict = {}
    for c in CELLS:
        for r in done_all[c]:
            hc.setdefault(c, {}).setdefault(r["harness_commit"], 0)
            hc[c][r["harness_commit"]] += 1
    out += ["", "## 各单元的 harness 提交", "", "| 单元 | 提交（条数） |", "|---|---|"]
    out += [f"| {c} | " + "，".join(f"`{k}`（{v}）" for k, v in hc[c].items()) + " |" for c in CELLS]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
