"""Does the model know whether it got a question right? (task card T19c)

decisions/2026-10-23-orphan-rows-and-confidence.md section 2; the verdict rules and the
operational details are frozen in tasks/T19c-abstention-signals.md before any data is seen.

Source: SQL-L1 of ``20261018-T13-sql-direct-01-rescore-01``, every non-judge attempt (327).

Part 1 (no model call): implicit signals already in the log -- first-turn reasoning tokens and
first-turn execution error -- and how well each separates correct from not-correct (AUC, with
"not correct" the positive class; more thinking / an error counts as less confident).

Part 2 (one paid call per attempt): the original conversation -- the T13 system message (its
sha256 is checked against the log), the question, the scored turn's answer (no reasoning, no
execution result) -- plus one fixed follow-up asking for a self-rated confidence A / B / C as JSON.
The original answer and its score are not touched. The follow-up never changes after the first
paid call (its sha256 is on every line); a reply that is not valid JSON is logged as ``unparsed``
and never retried. The committed log holds question ids, reps and tiers only; the reason
sentence and the reasoning stay in runs-raw.

    uv run python -m harness.confidence ask --dry-run
    uv run python -m harness.confidence ask --run-id 20261023-T19c-confidence-01 --budget 5
    uv run python -m harness.confidence report [--run-id 20261023-T19c-confidence-01]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import run_direct as R  # noqa: E402
from harness.cells import CELLS, PEAK_MULTIPLIER, PRICES_OFFPEAK, REPO  # noqa: E402
from harness.client import APIError, DeepSeekClient, Reply  # noqa: E402
from harness.questions import eval_dir, question_files, verify_eval_tag  # noqa: E402

SOURCE_RUN = "20261018-T13-sql-direct-01-rescore-01"
RAW_SOURCE = "20261018-T13-sql-direct-01"      # the rescore reuses its source's runs-raw
CELL = "SQL-L1"
MODEL = "deepseek-flash"
FINGERPRINT = "e72d3c7f663d3e1383b00b3884cb4501"
REPORT = REPO / "reports" / "results" / "confidence-calibration.md"
TIERS = ("A", "B", "C")

FOLLOW_UP = """请在不看执行结果的情况下，自评你上面这条查询答对题目的把握，三选一：
A：肯定对
B：大概对
C：没底

并用一句话说明原因。只输出一个 JSON 对象，不要输出其他内容，格式：
{"confidence": "A", "reason": "一句话原因"}"""


# ---------------------------------------------------------------------------
# Inputs


def bank_records() -> dict[str, dict]:
    out = {}
    for path in question_files(eval_dir()):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for rec in data["questions"] if isinstance(data, dict) else data:
            out[str(rec["id"])] = rec
    return out


def attempts(bank: dict[str, dict]) -> list[dict]:
    """The 327 attempts of the card's scope, in log order, each tagged ``low`` (low discrimination)."""
    path = REPO / "runs" / SOURCE_RUN / f"{CELL}.jsonl"
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        q = bank[r["qid"]]
        if r["status"] != "done" or q["scoring"] == "judge":
            continue
        r["low"] = bool(((q.get("labels") or {}).get("low_discrimination") or {}).get("criteria"))
        r["correct"] = r["final"]["outcome"] == "correct"
        out.append(r)
    return out


def scored_answer(rec: dict) -> str:
    """The content (not the reasoning) of the turn whose query was scored."""
    turn = rec["turns"][-1]
    raw = (R.raw_root() / RAW_SOURCE / CELL / f"{rec['qid']}_r{rec['rep']}_t{turn['turn']}.json").read_bytes()
    if R.sha256(raw) != turn["raw_sha256"]:
        raise RuntimeError(f"{rec['qid']} r{rec['rep']}: runs-raw does not match the logged raw_sha256")
    return json.loads(raw)["choices"][0]["message"]["content"]


def messages_for(system: str, rec: dict, question: str) -> list[dict[str, str]]:
    if R.sha256(question) != rec["question_sha256"]:
        raise RuntimeError(f"{rec['qid']}: question text differs from the source run")
    return [{"role": "system", "content": system}, {"role": "user", "content": question},
            {"role": "assistant", "content": scored_answer(rec)}, {"role": "user", "content": FOLLOW_UP}]


def source_system(recs: list[dict]) -> str:
    system = R.system_for(CELLS[CELL])
    want = {r["system_sha256"] for r in recs}
    if want != {R.sha256(system)}:
        raise RuntimeError(f"system message {R.sha256(system)[:12]} is not the source run's {sorted(want)}; "
                           "re-render build/contexts first (uv run python render/render_all.py)")
    return system


# ---------------------------------------------------------------------------
# Part 2: ask


def parse_tier(content: str) -> tuple[str | None, str | None]:
    """(tier, None) or (None, why unparsed). No repair beyond stripping one code fence."""
    text = content.strip()
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    if m:
        text = m.group(1)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"not JSON: {exc.msg}"
    if not isinstance(obj, dict) or set(obj) != {"confidence", "reason"}:
        return None, "not an object with exactly confidence and reason"
    if obj["confidence"] not in TIERS:
        return None, "confidence not A/B/C"
    if not isinstance(obj["reason"], str):
        return None, "reason not text"
    return obj["confidence"], None


def estimate(system: str, convs: list[list[dict]], output_tokens: int, hit_ratio: float) -> float:
    price = PRICES_OFFPEAK[MODEL]
    sys_tok = R.estimate_tokens_from_text(system)
    rest = [sum(R.estimate_tokens_from_text(m["content"]) for m in c[1:]) for c in convs]
    cost = sum((sys_tok * (price["miss"] if i == 0 else hit_ratio * price["hit"] + (1 - hit_ratio) * price["miss"])
                + t * price["miss"] + output_tokens * price["output"]) / 1e6 for i, t in enumerate(rest))
    print(f"model={MODEL} calls={len(convs)} (one per attempt, no retry)")
    print(f"system prefix ~{sys_tok} tokens; question+answer+follow-up ~{min(rest)}–{max(rest)} "
          f"(mean {sum(rest) / len(rest):.0f}); output assumed {output_tokens}/call; prefix cache hit {hit_ratio:.0%}")
    print(f"estimated cost: {cost:.2f} CNY off-peak (peak {cost * PEAK_MULTIPLIER:.2f})")
    return cost


def ask(args: argparse.Namespace) -> int:
    eval_full = verify_eval_tag(args.eval_tag)
    bank = bank_records()
    recs = attempts(bank)
    system = source_system(recs)
    convs = [messages_for(system, r, bank[r["qid"]]["text_zh"]) for r in recs]
    meta = {"follow_up_sha256": R.sha256(FOLLOW_UP), "system_sha256": R.sha256(system),
            "eval_tag": args.eval_tag, "eval_commit": eval_full[:7], "harness_commit": R.harness_commit()}
    print(f"question bank {args.eval_tag} = {eval_full}; source {SOURCE_RUN}/{CELL}: {len(recs)} attempts "
          f"({sum(not r['low'] for r in recs)} main, {sum(r['low'] for r in recs)} low-discrimination)")
    print(f"system {meta['system_sha256'][:12]} (= source)  follow-up {meta['follow_up_sha256'][:12]}")
    cost = estimate(system, convs, args.est_output_tokens, args.est_hit_ratio)
    for alt in (1000, 4000):
        if alt != args.est_output_tokens:
            print(f"  if output were {alt}/call: {estimate_quiet(system, convs, alt, args.est_hit_ratio):.2f} CNY off-peak")
    if args.dry_run:
        return 0
    if not args.run_id:
        print("--run-id is required unless --dry-run")
        return 2
    if args.budget is not None and cost > args.budget:
        print(f"refused: estimate {cost:.2f} CNY exceeds --budget {args.budget}")
        return 2
    if R.is_peak() and not args.allow_peak:
        print("refused: DeepSeek peak hours (weekdays 09-12, 14-18 Beijing)")
        return 2

    log = REPO / "runs" / args.run_id / "confidence.jsonl"
    raw_dir = R.raw_root() / args.run_id
    done = set()
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            prev = json.loads(line) if line.strip() else None
            if prev and prev["status"] in ("done", "unparsed"):
                if prev["follow_up_sha256"] != meta["follow_up_sha256"] or prev["system_sha256"] != meta["system_sha256"]:
                    raise RuntimeError("the follow-up or system message changed since the first paid call; it must not")
                done.add((prev["qid"], prev["rep"]))
    pending = [(r, c) for r, c in zip(recs, convs) if (r["qid"], r["rep"]) not in done]
    print(f"{len(done)} already rated; {len(pending)} to call")
    log.parent.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    boundary = R.CallBoundary(FINGERPRINT, allow_peak=args.allow_peak)
    client = DeepSeekClient(MODEL, before_request=boundary.before_request)
    lock = threading.Lock()
    spent = [0.0]

    def one(rec: dict, conv: list[dict]) -> None:
        if boundary.stopped.is_set():
            return
        started = datetime.now(R.BEIJING)
        peak = R.is_peak(started)
        reply: Reply | None = None
        error = None
        try:
            reply = client.chat(conv)
            (raw_dir / f"{rec['qid']}_r{rec['rep']}.json").write_bytes(reply.raw)
        except R.RunStopped:
            return
        except APIError as exc:
            error = str(exc)
        tier, why = parse_tier(reply.content) if reply is not None else (None, None)
        line = {"run_id": args.run_id, "qid": rec["qid"], "rep": rec["rep"],
                "status": "api_error" if reply is None else ("done" if tier else "unparsed"),
                "tier": tier, "source": {"run_id": SOURCE_RUN, "cell": CELL, "outcome": rec["final"]["outcome"],
                                         "fixed": rec["fixed"], "low_discrimination": rec["low"]},
                **meta, "model_requested": MODEL, "started_at": started.isoformat(timespec="seconds"), "peak": peak}
        if why:
            line["unparsed"] = why
        if error:
            line["error"] = error[:500]
        if reply is not None:
            line.update({"model_version": reply.model_version, "system_fingerprint": reply.system_fingerprint,
                         "finish_reason": reply.finish_reason, "usage": reply.usage,
                         "latency_s": round(reply.latency_s, 3), "transport_retries": reply.transport_retries,
                         "raw_sha256": R.sha256(reply.raw), "cost_cny": R.cost_cny(MODEL, reply.usage, peak)})
        with lock:
            with log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            spent[0] += line.get("cost_cny") or 0
            print(f"  {rec['qid']} r{rec['rep']}: {line['status']} {tier or ''}  ({spent[0]:.2f} CNY)", flush=True)
        try:
            if reply is not None:
                boundary.check_reply(reply)      # logged first, then stop on another fingerprint
            if args.budget is not None and spent[0] > args.budget:
                boundary.stop(f"spent {spent[0]:.2f} CNY > budget {args.budget}")
        except R.RunStopped:
            pass

    if pending:      # the first call alone, so that the shared prefix is cached for the rest
        one(*pending[0])
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            list(pool.map(lambda p: one(*p), pending[1:]))
    if boundary.stopped.is_set():
        print(f"STOPPED: {boundary.reason}")
        return 1
    print(f"done: {log}  ({spent[0]:.2f} CNY this session)")
    return 0


def estimate_quiet(system: str, convs: list[list[dict]], output_tokens: int, hit_ratio: float) -> float:
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        return estimate(system, convs, output_tokens, hit_ratio)


# ---------------------------------------------------------------------------
# Analysis


def auc(pos: list[float], neg: list[float]) -> float | None:
    """P(score of a positive > score of a negative), ties 0.5 (Mann-Whitney)."""
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def quartile_cuts(values: list[float]) -> list[float]:
    s = sorted(values)
    return [s[int(len(s) * k / 4)] for k in (1, 2, 3)]


def pct(k: int, n: int) -> str:
    return f"{k}/{n}（{100 * k / n:.1f}%）" if n else "0/0（—）"


def part1(recs: list[dict]) -> tuple[list[str], dict]:
    main = [r for r in recs if not r["low"]]
    cuts = quartile_cuts([r["turns"][0]["usage"]["reasoning_tokens"] for r in main])
    labels = [f"≤ {cuts[0]}", f"{cuts[0] + 1}–{cuts[1]}", f"{cuts[1] + 1}–{cuts[2]}", f"> {cuts[2]}"]

    def band(r: dict) -> int:
        t = r["turns"][0]["usage"]["reasoning_tokens"]
        return sum(t > c for c in cuts)

    def err(r: dict) -> int:
        return int(r["turns"][0]["exec"]["status"] == "error")

    out = ["## 第一部分：现有日志里的隐含信号（不调用模型）", "",
           "方向先定（卡「口径细化」第 3 条）：思考 token 越多、首轮执行报错，视为越可能「不对」；AUC 以「不对」为正类。"
           "AUC ≥ 0.70 记为「有用的隐含信号」，只作参照，不单独触发新单元。", "",
           "| 范围 | 作答 | 对 | 思考 token（首轮）AUC | 首轮执行报错 AUC | 结论 |", "|---|---|---|---|---|---|"]
    aucs = {}
    for name, group in (("主表", main), ("低区分度", [r for r in recs if r["low"]]), ("合计", recs)):
        ok = [r for r in group if r["correct"]]
        bad = [r for r in group if not r["correct"]]
        a_tok = auc([r["turns"][0]["usage"]["reasoning_tokens"] for r in bad], [r["turns"][0]["usage"]["reasoning_tokens"] for r in ok])
        a_err = auc([err(r) for r in bad], [err(r) for r in ok])
        aucs[name] = (a_tok, a_err)
        useful = [s for s, a in (("思考 token", a_tok), ("首轮报错", a_err)) if a is not None and a >= 0.70]
        out.append(f"| {name} | {len(group)} | {pct(len(ok), len(group))} | {a_tok:.3f} | {a_err:.3f} | "
                   + ("有用：" + "、".join(useful) if useful else "无有用的隐含信号") + " |")
    out += ["", f"按首轮思考 token 分档的正确率（切点 = 主表 294 次的四分位点 {cuts}，低区分度用同一组切点）：", "",
            "| 思考 token | 主表 | 低区分度 | 合计 |", "|---|---|---|---|"]
    for b, lab in enumerate(labels):
        cells = []
        for group in (main, [r for r in recs if r["low"]], recs):
            g = [r for r in group if band(r) == b]
            cells.append(pct(sum(r["correct"] for r in g), len(g)))
        out.append(f"| {lab} | " + " | ".join(cells) + " |")
    out += ["", "按首轮是否执行报错的正确率（最终判定，含修正一次之后的结果）：", "",
            "| 首轮 | 主表 | 低区分度 | 合计 |", "|---|---|---|---|"]
    for v, lab in ((0, "执行成功"), (1, "执行报错")):
        cells = []
        for group in (main, [r for r in recs if r["low"]], recs):
            g = [r for r in group if err(r) == v]
            cells.append(pct(sum(r["correct"] for r in g), len(g)))
        out.append(f"| {lab} | " + " | ".join(cells) + " |")
    return out, aucs


def verdict(rows: dict[str, tuple[int, int]], parsed: int) -> tuple[str, list[str]]:
    """rows: tier -> (n, correct). Rules exactly as frozen in the card (decided on the main table)."""
    acc = {t: rows[t][1] / rows[t][0] for t in TIERS if rows[t][0]}
    share_a = rows["A"][0] / parsed if parsed else 0.0
    why = []
    confirm = (acc.get("A", 0) >= 0.90 and share_a >= 0.40 and "C" in acc and acc["C"] <= 0.50)
    present = list(acc)
    close = len(present) >= 2 and all(abs(acc[x] - acc[y]) < 0.10 for i, x in enumerate(present) for y in present[i + 1:])
    refute = close or share_a >= 0.80
    why.append(f"A 档正确率 {acc.get('A', float('nan')):.1%}（≥ 90%？{'是' if acc.get('A', 0) >= 0.90 else '否'}）；"
               f"A 档占比 {share_a:.1%}（≥ 40%？{'是' if share_a >= 0.40 else '否'}；≥ 80%？{'是' if share_a >= 0.80 else '否'}）；"
               f"C 档正确率 {('%.1f%%' % (100 * acc['C'])) if 'C' in acc else '—（0 条）'}（≤ 50%？{'是' if 'C' in acc and acc['C'] <= 0.50 else '否'}）")
    why.append("非空档两两正确率差都 < 10 个百分点？" + ("是" if close else "否"))
    if confirm and refute:
        return "矛盾（证实与证伪条件同时成立），如实报告，不建议新单元", why
    if confirm:
        return "证实：模型知道自己会不会 → 第二期候选「按自评把握分流」单元", why
    if refute:
        return "证伪：模型不知道自己会不会 → 自评把握不可用；改进只能靠外部校验或语义层", why
    return "介于两者之间：如实报告，不建议新单元", why


def part2(recs: list[dict], run_id: str) -> list[str]:
    path = REPO / "runs" / run_id / "confidence.jsonl"
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    by = {(x["qid"], x["rep"]): x for x in lines}      # append-only log; the last line of an attempt wins
    src = {(r["qid"], r["rep"]): r for r in recs}
    missing = [k for k in src if k not in by]
    fps = sorted({x.get("system_fingerprint") for x in by.values() if x.get("system_fingerprint")})
    cost = sum(x.get("cost_cny") or 0 for x in lines)
    out = ["## 第二部分：自评把握（追问一轮）", "",
           f"运行 `{run_id}`：{len(by)} 条（缺 {len(missing)}）；状态 "
           + "、".join(f"{s} {sum(x['status'] == s for x in by.values())}" for s in ("done", "unparsed", "api_error"))
           + f"；指纹 {fps}；费用 {cost:.2f} 元。", "",
           "| 范围 | 自评 | 作答 | 占解析成功 | 其中对 | 正确率 |", "|---|---|---|---|---|---|"]
    verdicts = {}
    for name, keep in (("主表", lambda r: not r["low"]), ("低区分度", lambda r: r["low"]), ("合计", lambda r: True)):
        keys = [k for k, r in src.items() if keep(r) and k in by]
        ok_keys = [k for k in keys if by[k]["status"] == "done"]
        rows = {t: (sum(by[k]["tier"] == t for k in ok_keys), sum(by[k]["tier"] == t and src[k]["correct"] for k in ok_keys))
                for t in TIERS}
        for t in TIERS:
            n, c = rows[t]
            out.append(f"| {name} | {t} | {n} | {pct(n, len(ok_keys))} | {c} | {pct(c, n)} |")
        un = [k for k in keys if by[k]["status"] != "done"]
        out.append(f"| {name} | 未解析 / 接口错 | {len(un)} | — | {sum(src[k]['correct'] for k in un)} | — |")
        verdicts[name] = verdict(rows, len(ok_keys))
    v, why = verdicts["主表"]
    out += ["", "### 判定（主表 294 次，规则见任务卡，开跑前冻结）", "", f"**{v}**", ""] + [f"- {w}" for w in why]
    for name in ("低区分度", "合计"):
        out.append(f"- 参照（不判定）：{name}按同一规则会是「{verdicts[name][0].split('：')[0]}」")
    wrong_a = sorted({k[0] for k, r in src.items() if not r["low"] and k in by and by[k]["tier"] == "A" and not r["correct"]},
                     key=lambda q: int(q[1:]))
    out += ["", f"主表中自评 A 却不对的作答涉及的题（{len(wrong_a)} 题）：{', '.join(wrong_a) or '无'}"]
    return out


def report(args: argparse.Namespace) -> int:
    verify_eval_tag(args.eval_tag)
    bank = bank_records()
    recs = attempts(bank)
    main = [r for r in recs if not r["low"]]
    head = ["# T19c 模型知不知道自己会不会（自评把握的校准）", "",
            f"- 来源：`{SOURCE_RUN}` 的 {CELL}，非 judge 109 题 × 3 次 = {len(recs)} 次（主表 {len(main)}，低区分度 {len(recs) - len(main)}）；"
            f"对 = `final.outcome == correct`，其余（错、执行失败、拒答）都算不对。",
            f"- 主表正确率 {pct(sum(r['correct'] for r in main), len(main))}；合计 {pct(sum(r['correct'] for r in recs), len(recs))}。",
            "- 判定规则与口径细化见 `tasks/T19c-abstention-signals.md`（开跑前冻结）。本报告只含题号与数字，不含题面。",
            "- 复现：`uv run python -m harness.confidence report" + (f" --run-id {args.run_id}`" if args.run_id else "`"), ""]
    body, _ = part1(recs)
    tail = part2(recs, args.run_id) if args.run_id else ["## 第二部分：自评把握（追问一轮）", "", "未运行（待用户批准、错峰）。"]
    REPORT.write_text("\n".join(head + body + [""] + tail) + "\n", encoding="utf-8")
    print(f"wrote {REPORT.relative_to(REPO)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask", help="part 2: one follow-up call per attempt")
    a.add_argument("--run-id")
    a.add_argument("--eval-tag", default="eval-v1.2")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--budget", type=float, help="CNY; refuse to start if the estimate exceeds it, stop if spending does")
    a.add_argument("--concurrency", type=int, default=8)
    a.add_argument("--allow-peak", action="store_true")
    a.add_argument("--est-output-tokens", type=int, default=2000)
    a.add_argument("--est-hit-ratio", type=float, default=0.95)
    r = sub.add_parser("report", help="write reports/results/confidence-calibration.md")
    r.add_argument("--run-id", help="the part-2 run; omitted = part 1 only")
    r.add_argument("--eval-tag", default="eval-v1.2")
    args = ap.parse_args(argv)
    return ask(args) if args.cmd == "ask" else report(args)


if __name__ == "__main__":
    raise SystemExit(main())
