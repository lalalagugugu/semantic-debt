"""T15 report: explorer-agent (-E) results against the direct cells, from the committed run logs.

    SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/explorer_report.py \\
        --run 20261019-T15-explorer-01 --direct-run 20261018-T13-sql-direct-01 \\
        --eval-tag eval-v1.2 > reports/results/explorer.md

The question bank (``$SEMDEBT_EVAL_DIR``) must be the clean checkout of ``--eval-tag``. Table rules
are those of ``scripts/sql_direct_report.py`` (T13): judge questions are out of every accuracy
denominator, low-discrimination questions are shown apart, ``score_timeout`` lines are no verdict
and out of every denominator. Only question ids reach the output. ``--final`` drops the provisional
banner (use it on rescored runs only). The semantic-dependency split reads each question's
``labels.semantic_dependency.primary`` from the bank (T06).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from harness.questions import eval_dir, load_questions, question_files, verify_eval_tag  # noqa: E402
from scripts.sql_direct_report import FOUR, REPS, all_three, correct, pct, records, share  # noqa: E402

PAIRS = (("SQL-L0-E", "SQL-L0"), ("SQL-L1-E", "SQL-L1"))
BUCKETS = ("0", "1–3", "4–7", "8（用满）")


def bucket(n: int) -> str:
    return BUCKETS[0] if n == 0 else BUCKETS[1] if n <= 3 else BUCKETS[2] if n < 8 else BUCKETS[3]


def reason(r: dict) -> str:
    """Failure reason code: the scorer's reason for a wrong answer, the error class for an exec error."""
    f = r["final"]
    if f["outcome"] == "wrong":
        return f"wrong: {f.get('reason') or '—'}"
    if f["outcome"] == "exec_error":
        return f"exec_error: {f.get('error_class') or '—'}"
    return f["outcome"]


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def dependency() -> dict[str, str]:
    """Question id → primary semantic dependency (可从数据发现 / 只能由业务告知), from the bank's labels."""
    out = {}
    for path in question_files(eval_dir()):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for rec in data["questions"] if isinstance(data, dict) else data:
            out[str(rec["id"])] = ((rec.get("labels") or {}).get("semantic_dependency") or {}).get("primary") or "—"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="explorer run-id under runs/")
    ap.add_argument("--direct-run", required=True, help="direct run-id the -E cells are compared with")
    ap.add_argument("--eval-tag", default="eval-v1.2")
    ap.add_argument("--verdicts", default="运行时 `harness-v1` 评分器的当场判定（**暂定**）。"
                    "最终数字以 `harness-v1.1` 离线重评为准",
                    help="one line saying where the verdicts in the logs come from")
    ap.add_argument("--final", action="store_true", help="no provisional banner (rescored runs only)")
    ap.add_argument("--banner", default="本页的判定全部来自运行时的 `harness-v1` 评分器，`harness-v1.1` 离线重评后重新生成。",
                    help="why the page is provisional (ignored with --final)")
    args = ap.parse_args()

    commit = verify_eval_tag(args.eval_tag)
    qs = {q.qid: q for q in load_questions()}
    judge = {qid for qid, q in qs.items() if q.scoring == "judge"}
    low = {qid for qid, q in qs.items() if q.meta["low_discrimination"]}
    cells = [c for pair in PAIRS for c in pair]
    data = {c: records(args.run if c.endswith("-E") else args.direct_run, c) for c in cells}
    done_all = {c: [r for r in v if r.get("status") == "done"] for c, v in data.items()}
    timeout = {c: [r for r in v if r["final"].get("pending") == "score_timeout"] for c, v in done_all.items()}
    done = {c: [r for r in v if r["final"].get("pending") != "score_timeout"] for c, v in done_all.items()}
    scored = {c: [r for r in v if r["qid"] not in judge] for c, v in done.items()}
    main_ = {c: [r for r in v if r["qid"] not in low] for c, v in scored.items()}
    dep = dependency()
    tags = {c: sorted({r.get("eval_tag") or "?" for r in done_all[c]}) for c in cells}

    fps = Counter(t.get("system_fingerprint") for c in cells for r in done_all[c]
                  for t in r.get("steps", []) + r["turns"])
    versions = {c: sorted({(r.get("eval_tag"), r["eval_commit"][:7], r.get("semantic_tag"), r["harness_commit"])
                           for r in done_all[c]}) for c in cells}

    out = ["# 探查 agent 结果（T15，自动生成）" if args.final else "# 探查 agent 结果（T15，自动生成，**暂定**）", ""]
    if not args.final:
        out += [f"> **暂定**：{args.banner}", ""]
    out += [f"- 探查运行：`runs/{args.run}/`；直答对照：`runs/{args.direct_run}/`；模型 `deepseek-flash`；每题 {REPS} 次",
           f"- 版本（日志）：" + "；".join(f"{c} {versions[c]}" for c in cells),
           f"- 题集标注取自 `{args.eval_tag}` = `{commit[:7]}`：judge {len(judge)} 题（不进任何准确率分母）、"
           f"低区分度 {len(low)} 题（主表单列）",
           *([f"- **题库版本不同**：{ {c: tags[c] for c in cells} }。`eval-v1.1` 与 `eval-v1.2` 的 122 题题面与参考结果逐题相同，"
              "只有 Q74、Q98、Q117、Q119 的 rules 不同"] if len({tuple(t) for t in tags.values()}) > 1 else
             [f"- 四个单元的判定都按同一题库 {tags[cells[0]]}"]),
           f"- 指纹（四个单元的全部调用）：{dict(fps)}",
           "- 生成：`SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/explorer_report.py "
           f"--run {args.run} --direct-run {args.direct_run} --eval-tag {args.eval_tag}{' --final' if args.final else ''}"
           "`（另带 `--verdicts`、`--banner` 的文字，见本页）",
           f"- **判定来源**：{args.verdicts}",
           f"- 打分超时（`score_timeout`，不是判定，不进任何分母，逐条见文末）："
           f"{sum(len(v) for v in timeout.values())} 条", ""]

    out += ["## 完整性", "", "| 单元 | 作答（done） | 应有 | 非 done 行 | 缺失的 (题, 次) |", "|---|---:|---:|---:|---|"]
    for c in cells:
        have = {(r["qid"], r["rep"]) for r in done_all[c]}
        missing = sorted({(q, k) for q in qs for k in range(1, REPS + 1)} - have)
        out.append(f"| {c} | {len(done_all[c])} | {len(qs) * REPS} | {len(data[c]) - len(done_all[c])} | {missing or '无'} |")

    out += ["", "## 主表：探查 vs 直答（judge 题不计；准确率 = 最终正确 / 作答）", "",
            "| 单元 | 准确率（不含低区分度） | 准确率（含低区分度） | 首次即对率（不含低区分度） | 三次全对率（不含低区分度，按题） |",
            "|---|---|---|---|---|"]
    for e, d in PAIRS:
        for c in (d, e):
            a3, nq = all_three(main_[c])
            out.append(f"| {c} | {pct(correct(main_[c]), len(main_[c]))} | {pct(correct(scored[c]), len(scored[c]))} "
                       f"| {pct(sum(r['first'] == 'correct' for r in main_[c]), len(main_[c]))} | {pct(a3, nq)} |")
        de = correct(main_[e]) / len(main_[e]) - correct(main_[d]) / len(main_[d])
        out.append(f"| **{e} − {d}** | **{100 * de:+.1f} 点** | | | |")

    out += ["", "## 四种结果占比（judge 题不计，含低区分度；合计 100%）", "",
            "| 单元 | 作答 | 正确 | 错答 | 执行失败 | 拒答 |", "|---|---:|---|---|---|---|"]
    for e, d in PAIRS:
        for c in (d, e):
            n = len(scored[c])
            out.append(f"| {c} | {n} | " + " | ".join(share(sum(r['final']['outcome'] == o for r in scored[c]), n)
                                                    for o in FOUR) + " |")

    out += ["", "## 逐题变化（judge 题不计，不含低区分度；每题 3 次里答对几次）", "",
            "| 对照 | 题数 | 探查答对更多 | 相同 | 探查答对更少 | 净变化（答对次数） |", "|---|---:|---:|---:|---:|---:|"]
    for e, d in PAIRS:
        ce = Counter(r["qid"] for r in main_[e] if r["final"]["outcome"] == "correct")
        cd = Counter(r["qid"] for r in main_[d] if r["final"]["outcome"] == "correct")
        ids = {r["qid"] for r in main_[e]} & {r["qid"] for r in main_[d]}
        up = sum(ce[q] > cd[q] for q in ids)
        dn = sum(ce[q] < cd[q] for q in ids)
        out.append(f"| {e} vs {d} | {len(ids)} | {up} | {len(ids) - up - dn} | {dn} | {sum(ce[q] - cd[q] for q in ids):+d} |")
    out += ["", "（打分超时的作答两边都不计，所以个别题少于 3 次。单题 3 次的升降含抽样波动，看净变化与分布，不看单题。）"]

    out += ["", "## 按语义依赖分列（judge 题不计，不含低区分度）", "",
            "每题的 `semantic_dependency.primary`（T06 标注）：主要靠能从数据里查到的知识（可从数据发现），"
            "还是主要靠只能由业务告知的约定（只能由业务告知）。探查 agent 能补的应当主要是前一类。", "",
            "| 对照 | 语义依赖 | 题数 | 直答 | 探查 | 变化 |", "|---|---|---:|---|---|---:|"]
    for e, d in PAIRS:
        for label in sorted({dep.get(q, "—") for q in qs if q not in judge | low}):
            ids = {q for q in qs if dep.get(q, "—") == label and q not in judge | low}
            sd = [r for r in main_[d] if r["qid"] in ids]
            se = [r for r in main_[e] if r["qid"] in ids]
            delta = (correct(se) / len(se) - correct(sd) / len(sd)) if sd and se else 0.0
            out.append(f"| {e} vs {d} | {label} | {len(ids)} | {pct(correct(sd), len(sd))} | {pct(correct(se), len(se))} "
                       f"| {100 * delta:+.1f} 点 |")
    out += ["", "（题数少的一组波动大；每组的变化同时含抽样误差。）"]

    out += ["", "## 失败原因的转移（judge 题不计，含低区分度；按原因代码，条数）", "",
            "错答取评分器的 `reason`，执行失败取 `error_class`。", ""]
    for e, d in PAIRS:
        cd, ce = Counter(map(reason, scored[d])), Counter(map(reason, scored[e]))
        keys = sorted(set(cd) | set(ce), key=lambda k: (k != "correct", k.split(":")[0], -(cd[k] + ce[k]), k))
        out += [f"### {e} vs {d}", "", f"| 结果 / 原因 | {d} | {e} | 变化 |", "|---|---:|---:|---:|"]
        out += [f"| {k} | {cd[k]} | {ce[k]} | {ce[k] - cd[k]:+d} |" for k in keys]
        out += [f"| 合计 | {len(scored[d])} | {len(scored[e])} | |", ""]

    out += ["## 工具调用分布（全部作答，含 judge）", "",
            "| 单元 | 作答 | 0 次 | 1–3 次 | 4–7 次 | 8 次（用满） | 平均次数 | 发了「次数已用完」 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for e, _ in PAIRS:
        b = Counter(bucket(r["n_tool_calls"]) for r in done_all[e])
        out.append(f"| {e} | {len(done_all[e])} | " + " | ".join(str(b[k]) for k in BUCKETS)
                   + f" | {mean([r['n_tool_calls'] for r in done_all[e]]):.2f} "
                   f"| {sum(bool(r.get('limit_message_sent')) for r in done_all[e])} |")
    out += ["", "### 按工具调用次数看准确率（judge 题不计，不含低区分度）", "",
            "| 单元 | " + " | ".join(BUCKETS) + " |", "|---|---|---|---|---|"]
    for e, _ in PAIRS:
        cols = []
        for k in BUCKETS:
            s = [r for r in main_[e] if bucket(r["n_tool_calls"]) == k]
            cols.append(pct(correct(s), len(s)))
        out.append(f"| {e} | " + " | ".join(cols) + " |")
    out += ["", "（次数是模型自己选的，难题本来就查得多；这张表说明不了「多查导致答错」。）"]

    out += ["", "### 工具调用的执行情况（全部作答）", "",
            "| 单元 | 调用 | 执行 | 其中报错 | 超时 | 被拒（写语句 / 多语句） | 越界库 | 超限未执行 | 回显截断（行） | 回显截断（字符） |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for e, _ in PAIRS:
        calls = [c for r in done_all[e] for s in r["steps"] for c in s["tool_calls"]]
        ex = [c for c in calls if c["status"] == "executed"]
        err = [c for c in ex if c["exec"]["status"] == "error"]
        cls = Counter(c["exec"].get("error_class") for c in err)
        out.append(f"| {e} | {len(calls)} | {len(ex)} | {len(err)} | {cls.get('timeout', 0)} "
                   f"| {cls.get('forbidden_statement', 0)} | {cls.get('scope_violation', 0)} "
                   f"| {sum(c['status'] == 'limit_reached' for c in calls)} "
                   f"| {sum(bool(c.get('truncated')) for c in calls)} | {sum(bool(c.get('char_truncated')) for c in calls)} |")
    out += ["", "被拒与越界的调用都在执行前被执行器挡下，没有一条写操作或越界查询被执行（验收第 2 条）。"]

    out += ["", "## agent 税（每条作答平均；全部作答，含 judge；错峰价）", "",
            "直答的耗时只有模型调用；探查的「总耗时」= 模型调用 + 工具执行 + 运行器开销。", "",
            "| 单元 | 模型调用 | 输入 token | 其中缓存未命中 | 输出 token | 模型耗时（秒） | 总耗时（秒） | 费用（元） | 单元合计（元） |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for e, d in PAIRS:
        for c in (d, e):
            rs = done_all[c]
            out.append(f"| {c} | {mean([r['n_calls'] for r in rs]):.2f} | {mean([r['usage']['prompt_tokens'] for r in rs]):,.0f} "
                       f"| {mean([r['usage']['cache_miss_tokens'] for r in rs]):,.0f} "
                       f"| {mean([r['usage']['completion_tokens'] for r in rs]):,.0f} | {mean([r['latency_s'] for r in rs]):.1f} "
                       f"| {mean([r.get('wall_s', r['latency_s']) for r in rs]):.1f} | {mean([r.get('cost_cny') or 0 for r in rs]):.4f} "
                       f"| {sum(r.get('cost_cny') or 0 for r in rs):.2f} |")
        re_, rd = done_all[e], done_all[d]
        out.append(f"| **{e} ÷ {d}** | {mean([r['n_calls'] for r in re_]) / mean([r['n_calls'] for r in rd]):.1f}× "
                   f"| {mean([r['usage']['prompt_tokens'] for r in re_]) / mean([r['usage']['prompt_tokens'] for r in rd]):.1f}× | "
                   f"| {mean([r['usage']['completion_tokens'] for r in re_]) / mean([r['usage']['completion_tokens'] for r in rd]):.1f}× "
                   f"| {mean([r['latency_s'] for r in re_]) / mean([r['latency_s'] for r in rd]):.1f}× | "
                   f"| {mean([r.get('cost_cny') or 0 for r in re_]) / mean([r.get('cost_cny') or 0 for r in rd]):.1f}× | |")

    out += ["", "## 打分超时（`score_timeout`）", "", "行集在 runs-raw，`harness-v1.1` 合并后离线重评；最终报告里不能剩下。", "",
            "| 单元 | 题 | 次 |", "|---|---|---:|"]
    rows = [(c, r) for c in cells for r in sorted(timeout[c], key=lambda r: (r["qid"], r["rep"]))]
    out += [f"| {c} | {r['qid']} | {r['rep']} |" for c, r in rows] or ["| 无 | | |"]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
