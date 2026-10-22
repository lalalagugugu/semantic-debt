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
import json
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from harness.run_direct import cost_cny  # noqa: E402
from harness.questions import eval_dir, load_questions, question_files, verify_eval_tag  # noqa: E402
from scripts.sql_direct_report import FOUR, REPO, REPS, all_three, correct, pct, records, share  # noqa: E402

PAIRS = (("SQL-L0-E", "SQL-L0"), ("SQL-L1-E", "SQL-L1"))
L2_PAIR = ("SQL-L2-E", "SQL-L2")
COVERAGE_PATH = "reports/validation/t16-v14-8836110/coverage.json"   # JSON-L2 coverage table (T16)
BOOT_REPS, BOOT_SEED = 10_000, 20261020
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


def cost(r: dict) -> float:
    """The attempt's model cost, from its token usage: a rescored line logs ``cost_cny = 0`` (the rescore
    spent nothing) but keeps the source attempt's ``usage`` and ``peak``."""
    return cost_cny(r["model_requested"], r["usage"], bool(r.get("peak"))) or 0.0


def dependency() -> dict[str, str]:
    """Question id → primary semantic dependency (可从数据发现 / 只能由业务告知), from the bank's labels."""
    out = {}
    for path in question_files(eval_dir()):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for rec in data["questions"] if isinstance(data, dict) else data:
            out[str(rec["id"])] = ((rec.get("labels") or {}).get("semantic_dependency") or {}).get("primary") or "—"
    return out


def merged(run_ids: list[str], cell: str) -> tuple[list[dict], list[tuple[str, int, str]]]:
    """One record per (question, rep) over several runs of a cell, in the order given: a later run's
    ``done`` line replaces an earlier one for the same pair (a continuation run that redoes void
    attempts). Returns the records and the replaced pairs as (qid, rep, run it came from)."""
    by_pair: dict[tuple[str, int], dict] = {}
    replaced = []
    for run_id in run_ids:
        for r in records(run_id, cell):
            if r.get("status") != "done":
                continue
            key = (r["qid"], r["rep"])
            if key in by_pair:
                replaced.append((*key, by_pair[key]["run_id"]))
            by_pair[key] = r
    return list(by_pair.values()), replaced


def json_coverage(commit: str, path: str = COVERAGE_PATH) -> dict[str, str]:
    """Question id → JSON-L2 coverage category (``covered`` or a / b / c / d), from the frozen table at ``commit``."""
    text = subprocess.run(["git", "-C", str(REPO), "show", f"{commit}:{path}"], check=True,
                          capture_output=True, text=True).stdout
    return {row["qid"]: row["category"] for row in json.loads(text)["rows"]}


def per_question(recs: list[dict]) -> dict[str, float]:
    """Question id → share of its attempts that are correct."""
    n, k = Counter(r["qid"] for r in recs), Counter(r["qid"] for r in recs if r["final"]["outcome"] == "correct")
    return {q: k[q] / n[q] for q in n}


def paired_bootstrap(e: list[dict], d: list[dict], reps: int = BOOT_REPS, seed: int = BOOT_SEED) -> tuple[float, float, float]:
    """Difference in mean per-question accuracy (e − d) over the questions both answered, and its 95%
    percentile interval from resampling questions with replacement (attempts stay paired by question)."""
    pe, pd = per_question(e), per_question(d)
    ids = sorted(set(pe) & set(pd))
    diffs = [pe[q] - pd[q] for q in ids]
    rng = random.Random(seed)
    boots = sorted(sum(rng.choice(diffs) for _ in ids) / len(ids) for _ in range(reps))
    return sum(diffs) / len(ids), boots[int(0.025 * reps)], boots[int(0.975 * reps) - 1]


def l2_section(e_runs: list[str], d_run: str, cov_commit: str, judge: set[str], low: set[str]) -> list[str]:
    e_all, replaced = merged(e_runs, L2_PAIR[0])
    d_all = [r for r in records(d_run, L2_PAIR[1]) if r.get("status") == "done"]
    verdict = lambda rs: [r for r in rs if r["final"].get("pending") != "score_timeout"]  # noqa: E731
    e_sc = [r for r in verdict(e_all) if r["qid"] not in judge]
    d_sc = [r for r in verdict(d_all) if r["qid"] not in judge]
    cov = json_coverage(cov_commit)
    e_ids = {r["qid"] for r in e_sc}
    e, d = L2_PAIR
    out = ["", f"## {e} vs {d}（Cube SQL API，semantic-v1.4）", "",
           f"- 探查：{' + '.join(f'`runs/{r}/`' for r in e_runs)}，按 (题, 次) 合并，后面的 run 覆盖前面的同一 (题, 次)；"
           f"被覆盖的：{', '.join(f'{q} r{k}（{src}）' for q, k, src in sorted(replaced)) or '无'}",
           f"- 直答对照：`runs/{d_run}/`",
           f"- 两边都不答 judge 题：探查 {len({r['qid'] for r in e_all})} 题 × 3 = {len(e_all)} 条，"
           f"直答 {len({r['qid'] for r in d_all})} 题 × 3 = {len(d_all)} 条（judge 行 {sum(r['qid'] in judge for r in d_all)} 条，不计）",
           f"- 版本（日志）：{e} {sorted({(r.get('eval_tag'), r['eval_commit'][:7], r.get('semantic_tag')) for r in e_all})}；"
           f"{d} {sorted({(r.get('eval_tag'), r['eval_commit'][:7], r.get('semantic_tag')) for r in d_all})}",
           f"- 区间：按题配对的自助法（{BOOT_REPS} 次，种子 {BOOT_SEED}），对题有放回抽样，取每题 3 次里答对的比例之差的均值的 2.5% / 97.5% 分位", ""]

    out += ["### 主表（judge 题不计；准确率 = 最终正确 / 作答）", "",
            "| 题组 | 题数 | " + d + " | " + e + " | 差值 | 95% 区间 |", "|---|---:|---|---|---:|---|"]
    groups = [("主表（不含低区分度）", lambda q: q not in low), ("低区分度（单列）", lambda q: q in low),
              ("合计（含低区分度）", lambda q: True)]
    for name, keep in groups:
        se, sd = [r for r in e_sc if keep(r["qid"])], [r for r in d_sc if keep(r["qid"])]
        diff, lo, hi = paired_bootstrap(se, sd)
        out.append(f"| {name} | {len({r['qid'] for r in se})} | {pct(correct(sd), len(sd))} | {pct(correct(se), len(se))} "
                   f"| {100 * diff:+.1f} 点 | [{100 * lo:+.1f}, {100 * hi:+.1f}] |")
    se, sd = [r for r in e_sc if r["qid"] not in low], [r for r in d_sc if r["qid"] not in low]
    a3e, nqe = all_three(se)
    a3d, nqd = all_three(sd)
    out += ["", f"首次即对率（主表）：{d} {pct(sum(r['first'] == 'correct' for r in sd), len(sd))}，"
            f"{e} {pct(sum(r['first'] == 'correct' for r in se), len(se))}；三次全对率（按题）：{d} {pct(a3d, nqd)}，{e} {pct(a3e, nqe)}"]

    out += ["", "### 四种结果（judge 题不计；条数）", "", "| 单元 | 题组 | 作答 | 正确 | 错答 | 执行失败 | 拒答 |",
            "|---|---|---:|---:|---:|---:|---:|"]
    for c, rs in ((d, d_sc), (e, e_sc)):
        for name, keep in groups:
            s = [r for r in rs if keep(r["qid"])]
            out.append(f"| {c} | {name} | {len(s)} | " + " | ".join(str(sum(r['final']['outcome'] == o for r in s)) for o in FOUR) + " |")

    out += ["", "### 逐题变化（主表；每题 3 次里答对几次）", "",
            "| 题数 | 探查答对更多 | 相同 | 探查答对更少 | 净变化（答对次数） |", "|---:|---:|---:|---:|---:|"]
    ce = Counter(r["qid"] for r in se if r["final"]["outcome"] == "correct")
    cd = Counter(r["qid"] for r in sd if r["final"]["outcome"] == "correct")
    ids = {r["qid"] for r in se} & {r["qid"] for r in sd}
    up, dn = sum(ce[q] > cd[q] for q in ids), sum(ce[q] < cd[q] for q in ids)
    out.append(f"| {len(ids)} | {up} | {len(ids) - up - dn} | {dn} | {sum(ce[q] - cd[q] for q in ids):+d} |")

    out += ["", f"### 按 JSON-L2 覆盖拆分（`{COVERAGE_PATH}` @ `{cov_commit}`；judge 题不计，含低区分度）", "",
            "覆盖表把每题分成 JSON-L2 能用已公开成员答的（covered）和其余（a / c / d 类，b 类 0 题）。", "",
            "| 题组 | 题数 | " + d + " | " + e + " | 差值 | 95% 区间 |", "|---|---:|---|---|---:|---|"]
    for name, keep in (("能答（covered）", lambda q: cov.get(q) == "covered"),
                       ("其余（a / b / c / d）", lambda q: cov.get(q) != "covered")):
        s_e, s_d = [r for r in e_sc if keep(r["qid"])], [r for r in d_sc if keep(r["qid"])]
        diff, lo, hi = paired_bootstrap(s_e, s_d)
        out.append(f"| {name} | {len({r['qid'] for r in s_e})} | {pct(correct(s_d), len(s_d))} | {pct(correct(s_e), len(s_e))} "
                   f"| {100 * diff:+.1f} 点 | [{100 * lo:+.1f}, {100 * hi:+.1f}] |")
    missing = sorted(e_ids - set(cov))
    out += [""] + ([f"覆盖表里没有的题：{missing}（算作「其余」）", ""] if missing else []) + [
        "能答的题：" + "、".join(sorted((q for q in e_ids if cov.get(q) == "covered"), key=lambda q: int(q[1:])))]

    out += ["", "### 步数与工具调用（全部作答）", "",
            "步数 = 发出 `run_sql` 的模型调用次数（不含交卷与修正那一两次调用；全部模型调用见 agent 税表）。", "",
            "| 步数 | " + " | ".join(str(k) for k in range(1, 11)) + " | 更多 |", "|---|" + "---:|" * 11]
    steps = Counter(r["n_steps"] for r in e_all)
    out.append(f"| {e} 条数 | " + " | ".join(str(steps[k]) for k in range(1, 11))
               + f" | {sum(v for k, v in steps.items() if k > 10)} |")
    b = Counter(bucket(r["n_tool_calls"]) for r in e_all)
    out += ["", "| 单元 | 作答 | " + " | ".join(f"run_sql {k}" for k in BUCKETS) + " | 平均 run_sql | 用满 8 次 | 发了「次数已用完」 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            f"| {e} | {len(e_all)} | " + " | ".join(str(b[k]) for k in BUCKETS)
            + f" | {mean([r['n_tool_calls'] for r in e_all]):.2f} | {sum(bool(r.get('hit_tool_limit')) for r in e_all)} "
            f"| {sum(bool(r.get('limit_message_sent')) for r in e_all)} |"]
    calls = [c for r in e_all for s in r["steps"] for c in s["tool_calls"]]
    ex = [c for c in calls if c["status"] == "executed"]
    cls = Counter(c["exec"].get("error_class") for c in ex if c["exec"]["status"] == "error")
    out += ["", f"`run_sql` 执行 {len(ex)} 次，其中报错 {sum(cls.values())} 次：{dict(cls.most_common())}。"]

    out += ["", "### agent 税（每条作答平均；全部作答；错峰价）", "",
            "| 单元 | 模型调用 | 输入 token | 输出 token | 总耗时（秒） | 费用（元） | 单元合计（元） |", "|---|---:|---:|---:|---:|---:|---:|"]
    for c, rs in ((d, [r for r in d_all if r["qid"] in e_ids]), (e, e_all)):
        out.append(f"| {c} | {mean([r['n_calls'] for r in rs]):.2f} | {mean([r['usage']['prompt_tokens'] for r in rs]):,.0f} "
                   f"| {mean([r['usage']['completion_tokens'] for r in rs]):,.0f} | {mean([r.get('wall_s', r['latency_s']) for r in rs]):.1f} "
                   f"| {mean([cost(r) for r in rs]):.4f} | {sum(cost(r) for r in rs):.2f} |")
    rd = [r for r in d_all if r["qid"] in e_ids]
    out.append(f"| **{e} ÷ {d}** | {mean([r['n_calls'] for r in e_all]) / mean([r['n_calls'] for r in rd]):.1f}× "
               f"| {mean([r['usage']['prompt_tokens'] for r in e_all]) / mean([r['usage']['prompt_tokens'] for r in rd]):.1f}× "
               f"| {mean([r['usage']['completion_tokens'] for r in e_all]) / mean([r['usage']['completion_tokens'] for r in rd]):.1f}× "
               f"| {mean([r.get('wall_s', r['latency_s']) for r in e_all]) / mean([r['latency_s'] for r in rd]):.1f}× "
               f"| {mean([cost(r) for r in e_all]) / mean([cost(r) for r in rd]):.1f}× | |")
    out += ["", "（直答只取探查也答的题，即同样不含 judge；费用按日志里的 token 用量重算。）"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="explorer run-id under runs/")
    ap.add_argument("--direct-run", required=True, help="direct run-id the -E cells are compared with")
    ap.add_argument("--l2e-run", action="append", default=[],
                    help="SQL-L2-E run-id (repeatable, in order: a later run's line replaces an earlier one for the same (question, rep))")
    ap.add_argument("--l2-direct-run", help="SQL-L2 direct run-id the SQL-L2-E cell is compared with")
    ap.add_argument("--json-coverage-commit", default="381ed1d", help=f"commit of the frozen {COVERAGE_PATH}")
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
    # the bank commit each verdict was made against: a rescored line updates eval_commit but keeps the
    # source run's eval_tag, so the tag alone would misreport the bank a rescore used
    tags = {c: sorted({r["eval_commit"][:7] for r in done_all[c]}) for c in cells}

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
           *([f"- **判定所用的题库提交不同**：{ {c: tags[c] for c in cells} }。`eval-v1.1`（938957f）与 `eval-v1.2`（90e13b3）"
              "的 122 题题面与参考结果逐题相同，只有 Q74、Q98、Q117、Q119 的 rules 不同"]
             if len({tuple(t) for t in tags.values()}) > 1 else
             [f"- 四个单元的判定都按同一题库提交 `{tags[cells[0]][0]}`（{args.eval_tag}）；重评行的 `eval_tag` 字段沿用源运行，"
              "以 `eval_commit` 为准"]),
           f"- 指纹（四个单元的全部调用）：{dict(fps)}",
           "- 生成：`SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/explorer_report.py "
           f"--run {args.run} --direct-run {args.direct_run} --eval-tag {args.eval_tag}{' --final' if args.final else ''}"
           + "".join(f" --l2e-run {r}" for r in args.l2e_run)
           + (f" --l2-direct-run {args.l2_direct_run} --json-coverage-commit {args.json_coverage_commit}"
              if args.l2_direct_run else "")
           + "`（另带 `--verdicts`、`--banner` 的文字，见本页）",
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
                       f"| {mean([r.get('wall_s', r['latency_s']) for r in rs]):.1f} | {mean([cost(r) for r in rs]):.4f} "
                       f"| {sum(cost(r) for r in rs):.2f} |")
        re_, rd = done_all[e], done_all[d]
        out.append(f"| **{e} ÷ {d}** | {mean([r['n_calls'] for r in re_]) / mean([r['n_calls'] for r in rd]):.1f}× "
                   f"| {mean([r['usage']['prompt_tokens'] for r in re_]) / mean([r['usage']['prompt_tokens'] for r in rd]):.1f}× | "
                   f"| {mean([r['usage']['completion_tokens'] for r in re_]) / mean([r['usage']['completion_tokens'] for r in rd]):.1f}× "
                   f"| {mean([r['latency_s'] for r in re_]) / mean([r['latency_s'] for r in rd]):.1f}× | "
                   f"| {mean([cost(r) for r in re_]) / mean([cost(r) for r in rd]):.1f}× | |")

    if args.l2e_run and args.l2_direct_run:
        out += l2_section(args.l2e_run, args.l2_direct_run, args.json_coverage_commit, judge, low)

    out += ["", "## 打分超时（`score_timeout`）", "", "行集在 runs-raw，`harness-v1.1` 合并后离线重评；最终报告里不能剩下。", "",
            "| 单元 | 题 | 次 |", "|---|---|---:|"]
    rows = [(c, r) for c in cells for r in sorted(timeout[c], key=lambda r: (r["qid"], r["rep"]))]
    out += [f"| {c} | {r['qid']} | {r['rep']} |" for c, r in rows] or ["| 无 | | |"]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
