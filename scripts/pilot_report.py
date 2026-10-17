"""T12 pilot report: accuracy (with / without low-discrimination questions), by Q
level, outcome shares, token distributions, fingerprints and cost, from the
committed run logs. Question metadata (Q level, low-discrimination label) comes
from the question bank, which must be the clean eval-v1 checkout.

    uv run python scripts/pilot_report.py --run deepseek-flash=20261018-T12-pilot-flash-01 \\
        --run deepseek-v4-pro=20261018-T12-pilot-pro-01 > reports/T12-pilot.md

Only question ids reach the output.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.questions import load_questions, pilot_ids, verify_eval_tag  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CELLS = ("SQL-R", "SQL-L1")
OUTCOMES = ("correct", "wrong", "exec_error", "refused", "pending")


def records(run_id: str, cell: str) -> list[dict]:
    path = REPO / "runs" / run_id / f"{cell}.jsonl"
    recs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return recs


def pct(n: int, d: int) -> str:
    return f"{n}/{d} = {100 * n / d:.1f}%" if d else "—"


def dist(values: list[int]) -> str:
    if not values:
        return "—"
    v = sorted(values)
    q = lambda p: v[min(len(v) - 1, int(p * len(v)))]   # noqa: E731
    return f"{statistics.mean(v):,.0f} / {q(0.5):,} / {q(0.9):,} / {v[-1]:,}（合计 {sum(v):,}）"


def cache_window(run_ids: list[str]) -> list[str]:
    out = ["", "## 缓存过期时间窗（`harness/cache_probe.py`）", "",
           "每个间隔一份独立前缀：预热一次，隔 d 秒再调一次；命中 = 第二次调用的 `prompt_cache_hit_tokens`。", "",
           "| run | 模型 | 间隔 | 实际间隔（秒） | 命中 | 未命中 |", "|---|---|---:|---:|---:|---:|"]
    for run_id in run_ids:
        path = REPO / "runs" / run_id / "cache-probe.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["kind"] != "probe":
                continue
            u = r.get("usage") or {}
            d = r["delay_s"]
            label = f"{d // 3600} h" if d >= 3600 else f"{d // 60} min" if d >= 60 else f"{d} s"
            out.append(f"| {run_id} | {r['model_requested']} | {label} | {r['since_warm_s']} "
                       f"| {u.get('cache_hit_tokens', r.get('status'))} | {u.get('cache_miss_tokens', '')} |")
    return out


def budget_model(runs: dict[str, str], done: dict) -> list[str]:
    """T13 cost = calls x warm cost per call + cold starts x prefix x (miss - hit price).

    Per-call output tokens, residual (uncached) input per warm call and calls per
    attempt are the pilot's measurements per model. Prefix sizes of the T13 cells
    are the dry-run estimates scaled by the measured / estimated ratio of SQL-L1.
    """
    from harness.cells import CELLS, PRICES_OFFPEAK
    from harness.questions import load_questions
    from harness.run_direct import estimate_tokens_from_text, system_for

    l1 = [t for (m, c), recs in done.items() if c == "SQL-L1" for r in recs for t in r["turns"]]
    ratio = statistics.mean(t["usage"]["prompt_tokens"] for t in l1) / (estimate_tokens_from_text(system_for(CELLS["SQL-L1"])) + 60)
    n = {"zh": len(load_questions()), "en": len(load_questions(lang="en"))}
    cells = [c for c in CELLS.values() if c.card == "T13"]
    prefix = {c.name: ratio * estimate_tokens_from_text(system_for(c)) for c in cells}
    out = ["", "## T13 预算模型（按冷启动次数）", "",
           f"费用 = 调用数 × 热调用单价 + 冷启动次数 × 前缀 token × (未命中价 − 命中价)。前缀 token 用 dry-run 估算 × 实测/估算比 {ratio:.3f}"
           f"（SQL-L1 实测）。T13 单元：{', '.join(c.name for c in cells)}；中文 {n['zh']} 题、英文 {n['en']} 题，各 3 次；错峰价。", "",
           "| 模型 | 每次作答调用数 | 每次调用输出 token | 热调用未命中输入 | 热调用部分（元） | 每冷启动一轮全部单元（元） | 冷启动 8 次 | 24 次 | 100 次 |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m in runs:
        recs = [r for (mm, c), rs in done.items() if mm == m for r in rs]
        turns = [t for r in recs for t in r["turns"]]
        warm = [t for t in turns if t["usage"]["cache_miss_tokens"] <= t["usage"]["prompt_tokens"] / 2]
        cpa = len(turns) / len(recs)
        outp = statistics.mean(t["usage"]["completion_tokens"] for t in turns)
        resid = statistics.mean(t["usage"]["cache_miss_tokens"] for t in warm)
        pr = PRICES_OFFPEAK[m]
        warm_total = sum(3 * n[c.lang] * cpa * (prefix[c.name] * pr["hit"] + resid * pr["miss"] + outp * pr["output"]) / 1e6
                         for c in cells)
        cold_round = sum(prefix[c.name] * (pr["miss"] - pr["hit"]) / 1e6 for c in cells)
        per_cold = cold_round / len(cells)
        out.append(f"| {m} | {cpa:.2f} | {outp:,.0f} | {resid:,.0f} | {warm_total:.1f} | {cold_round:.2f} "
                   f"| {warm_total + 8 * per_cold:.1f} | {warm_total + 24 * per_cold:.1f} | {warm_total + 100 * per_cold:.1f} |")
    out += ["", "（冷启动 N 次按各单元平均前缀计；8 次 = 每单元只冷启动一次。）"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True, help="model=run-id")
    ap.add_argument("--eval-tag", default="eval-v1")
    ap.add_argument("--cache-run", action="append", default=[], help="run-id of a harness.cache_probe run")
    args = ap.parse_args()
    runs = dict(x.split("=", 1) for x in args.run)

    commit = verify_eval_tag(args.eval_tag)
    pilot = pilot_ids()
    meta = {q.qid: q for q in load_questions() if q.qid in set(pilot)}
    level = {qid: meta[qid].meta["q_level"] for qid in pilot}
    low = {qid for qid in pilot if meta[qid].meta["low_discrimination"]}
    judge = {qid for qid in pilot if meta[qid].pending}

    out = [f"# T12 试跑结果（自动生成）\n",
           f"- 题库：`{args.eval_tag}` = `{commit}`；试跑 {len(pilot)} 题；低区分度 {sorted(low)}；"
           f"judge 题（行集待离线评分、不进准确率分母）{sorted(judge)}",
           "- 运行：" + "；".join(f"{m} → `runs/{r}/`" for m, r in runs.items()), ""]

    data = {(m, c): [r for r in records(r_id, c)] for m, r_id in runs.items() for c in CELLS}
    done = {k: [r for r in v if r.get("status") == "done"] for k, v in data.items()}

    out += ["## 准确率（correct / 可评作答）", "",
            "| 模型 | 单元 | 含低区分度 | 不含低区分度（选模型用） | 首答即对（不含低区分度） |", "|---|---|---|---|---|"]
    for (m, c), recs in done.items():
        scored = [r for r in recs if r["final"]["outcome"] != "pending"]
        main_ = [r for r in scored if r["qid"] not in low]
        out.append(f"| {m} | {c} | {pct(sum(r['final']['outcome'] == 'correct' for r in scored), len(scored))} "
                   f"| {pct(sum(r['final']['outcome'] == 'correct' for r in main_), len(main_))} "
                   f"| {pct(sum(r['first'] == 'correct' for r in main_), len(main_))} |")

    out += ["", "## 按 Q 级（不含低区分度 / 含）", "",
            "| 模型 | 单元 | Q1 | Q2 | Q3 |", "|---|---|---|---|---|"]
    for (m, c), recs in done.items():
        cells = []
        for lv in ("Q1", "Q2", "Q3"):
            s = [r for r in recs if level[r["qid"]] == lv and r["final"]["outcome"] != "pending"]
            sm = [r for r in s if r["qid"] not in low]
            cells.append(f"{pct(sum(r['final']['outcome'] == 'correct' for r in sm), len(sm))}"
                         f"（含 {pct(sum(r['final']['outcome'] == 'correct' for r in s), len(s))}）")
        out.append(f"| {m} | {c} | " + " | ".join(cells) + " |")

    out += ["", "## 四种结果占比（全部作答，含低区分度；pending = judge 题返回了行集）", "",
            "| 模型 | 单元 | 作答 | " + " | ".join(OUTCOMES) + " | 非 done 行 |", "|---|---|---:|" + "---|" * (len(OUTCOMES) + 1)]
    for (m, c), recs in done.items():
        n = len(recs)
        counts = {o: sum(r["final"]["outcome"] == o for r in recs) for o in OUTCOMES}
        out.append(f"| {m} | {c} | {n} | " + " | ".join(f"{counts[o]}（{100 * counts[o] / n:.0f}%）" for o in OUTCOMES)
                   + f" | {len(data[(m, c)]) - n} |")

    out += ["", "### 最终执行错误的分类", "", "| 模型 | 单元 | 分类 |", "|---|---|---|"]
    for (m, c), recs in done.items():
        cls: dict = {}
        for r in recs:
            if r["final"]["outcome"] == "exec_error":
                cls[r["final"]["error_class"]] = cls.get(r["final"]["error_class"], 0) + 1
        fixed = sum(r["fixed"] for r in recs)
        fixed_ok = sum(r["fixed"] and r["final"]["outcome"] == "correct" for r in recs)
        out.append(f"| {m} | {c} | {cls or '无'}；触发修一次 {fixed} 次，修后正确 {fixed_ok} 次 |")

    out += ["", "## 逐题正确次数（/3）", "", "| 题 | Q级 | 低区分度 | " + " | ".join(f"{m} {c}" for m, c in done) + " |",
            "|---|---|---|" + "---|" * len(done)]
    for qid in pilot:
        row = []
        for k, recs in done.items():
            rs = [r for r in recs if r["qid"] == qid]
            if qid in judge:
                row.append("pending" if all(r["final"]["outcome"] == "pending" for r in rs) else
                           "/".join(r["final"]["outcome"] for r in rs))
            else:
                row.append(f"{sum(r['final']['outcome'] == 'correct' for r in rs)}/{len(rs)}")
        out.append(f"| {qid} | {level[qid]} | {'是' if qid in low else ''} | " + " | ".join(row) + " |")

    out += ["", "## token 分布（每次调用；均值 / 中位 / P90 / 最大，括号内为合计）", "",
            "| 模型 | 单元 | 调用 | reasoning | completion | 缓存未命中输入 | prompt |", "|---|---|---:|---|---|---|---|"]
    for (m, c), recs in done.items():
        turns = [t for r in recs for t in r["turns"]]
        u = lambda k: [t["usage"][k] for t in turns]   # noqa: E731
        out.append(f"| {m} | {c} | {len(turns)} | {dist(u('reasoning_tokens'))} | {dist(u('completion_tokens'))} "
                   f"| {dist(u('cache_miss_tokens'))} | {dist(u('prompt_tokens'))} |")

    out += ["", "### 冷启动（缓存未命中 > prompt 的一半的调用）与费用", "",
            "| 模型 | 单元 | 冷启动次数 | 冷启动费用 | 热调用费用均值 | 总费用（元） |", "|---|---|---:|---:|---:|---:|"]
    for (m, c), recs in done.items():
        from harness.run_direct import cost_cny
        turns = [t for r in recs for t in r["turns"]]
        cold = [t for t in turns if t["usage"]["cache_miss_tokens"] > t["usage"]["prompt_tokens"] / 2]
        warm = [t for t in turns if t not in cold]
        cc = sum(cost_cny(m, t["usage"], False) for t in cold)
        wc = statistics.mean(cost_cny(m, t["usage"], False) for t in warm) if warm else 0
        total = sum(r.get("cost_cny") or 0 for r in recs)
        out.append(f"| {m} | {c} | {len(cold)} | {cc:.4f} | {wc:.4f} | {total:.4f} |")

    out += ["", "## 指纹", "", "| 模型 | system_fingerprint（调用次数） | 无指纹调用 |", "|---|---|---:|"]
    for m in runs:
        fps: dict = {}
        none = 0
        for c in CELLS:
            for r in data[(m, c)]:
                for t in r.get("turns") or []:
                    fp = t.get("system_fingerprint")
                    if fp:
                        fps[fp] = fps.get(fp, 0) + 1
                    else:
                        none += 1
        out.append(f"| {m} | {fps} | {none} |")

    out += budget_model(runs, done)
    out += cache_window(args.cache_run)
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
