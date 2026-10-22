"""SQL-L1 failure attribution, Flash first pass (task card T19b).

decisions/2026-10-20-l1-error-attribution.md: every non-correct SQL-L1 attempt of the T13
rescore (judge questions excluded, low-discrimination included) is labelled by ``deepseek-flash``
with one of the design's 10 categories, a declared-assumption flag and one of 5 root causes,
following reports/attribution/codebook.md.

The model sees only: the question, the SQL-L1 context exactly as the run had it (the system
prompt's sha256 is checked against the source log), the references (SQL, interpretation, first
rows), the attempt's final SQL with its first rows or its error, the attempt's declared
assumption, and the scorer's reason. **Never the attempt's reasoning.**

The prompt is fixed (reports/attribution/prompt.md + codebook + context); its sha256 goes on
every line. Thinking mode on, no temperature. One call per item: a reply that is not a valid
label object is logged as ``unparsed``, never retried. The committed log holds question ids and
labels only; the full reply (with ``note`` and the reasoning) stays in runs-raw.

    uv run python -m harness.attribute_l1 --dry-run
    uv run python -m harness.attribute_l1 --run-id 20261020-T19b-attrib-01 --budget 3
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

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import run_direct as R  # noqa: E402
from harness.cells import CELLS, PEAK_MULTIPLIER, PRICES_OFFPEAK, REPO  # noqa: E402
from harness.client import APIError, DeepSeekClient, Reply  # noqa: E402
from harness.questions import eval_dir, question_files, verify_eval_tag  # noqa: E402
from harness.rescore import candidate_of  # noqa: E402
from harness.scorer_v2 import REFUSAL, ExecError  # noqa: E402

SOURCE_RUN = "20261018-T13-sql-direct-01-rescore-01"
CELL = "SQL-L1"
MODEL = "deepseek-flash"
FINGERPRINT = "e72d3c7f663d3e1383b00b3884cb4501"
PROMPT = REPO / "reports" / "attribution" / "prompt.md"
CODEBOOK = REPO / "reports" / "attribution" / "codebook.md"
ROWS = 10            # first rows shown, of each reference and of the attempt
CELL_CHARS = 200     # one value longer than this is cut (the row count is always given)
CATEGORIES = ("汇总层未覆盖", "接口表达不了", "语法错", "读错问题", "选错表或字段",
              "路径错", "口径错", "筛选错", "粒度错", "拒答")
LABELS = ("category", "declared_assumption", "root_cause", "doc_evidence", "note")


# ---------------------------------------------------------------------------
# Inputs


def bank_records() -> dict[str, dict]:
    """Question records as the bank stores them (text, refs with SQL and interpretation)."""
    out = {}
    for path in question_files(eval_dir()):
        for rec in json.loads(path.read_text(encoding="utf-8"))["questions"]:
            out[str(rec["id"])] = rec
    return out


def source_lines() -> list[dict]:
    path = REPO / "runs" / SOURCE_RUN / f"{CELL}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def items(lines: list[dict], bank: dict[str, dict]) -> list[dict]:
    """Every non-correct attempt, judge questions excluded, in log order."""
    return [r for r in lines if r.get("status") == "done" and bank[r["qid"]]["scoring"] != "judge"
            and r["final"]["outcome"] != "correct"]


def system_message(source_system_sha256: str) -> str:
    """Prompt + codebook + the SQL-L1 context the run had; refuses if the context drifted."""
    cell = CELLS[CELL]
    if R.sha256(R.system_for(cell)) != source_system_sha256:
        raise RuntimeError(f"build/contexts for {CELL} no longer give the source run's system prompt; "
                           "re-render from the source run's semantic tag first")
    return (PROMPT.read_text(encoding="utf-8").rstrip() + "\n\n# 编码手册\n\n" + CODEBOOK.read_text(encoding="utf-8").rstrip()
            + "\n\n# L1 上下文\n\n```yaml\n" + R.context_text(cell).rstrip() + "\n```\n")


def _cell(v) -> object:
    if isinstance(v, str) and len(v) > CELL_CHARS:
        return v[:CELL_CHARS] + "…"
    return v


def _rows(columns: list[str], rows: list[list]) -> str:
    head = [[_cell(v) for v in row] for row in rows[:ROWS]]
    lines = [f"列：{json.dumps(columns, ensure_ascii=False)}",
             f"共 {len(rows)} 行" + (f"，以下是前 {ROWS} 行" if len(rows) > ROWS else "") + "："]
    lines += [json.dumps(row, ensure_ascii=False, default=str) for row in head]
    return "\n".join(lines)


def _ref_rows(path: Path) -> tuple[list[str], list[list]]:
    import csv
    with path.open(encoding="utf-8", newline="") as fh:
        table = list(csv.reader(fh))
    return table[0], table[1:]


def user_message(rec: dict, q: dict, raw_dir: Path) -> str:
    turn = rec["turns"][-1]
    parts = ["## 题面", q["text_zh"], "", f"## 参考答案（共 {len(q['refs'])} 份，作答与任一份一致即算对）"]
    for i, ref in enumerate(q["refs"], 1):
        cols, rows = _ref_rows(eval_dir() / ref["result_path"])
        parts += [f"### 参考 {i}：{ref.get('interpretation') or ''}", "```sql", ref["sql"].strip(), "```", _rows(cols, rows), ""]
    parts += ["## 作答（最终一轮）", f"假设说明：{turn.get('assumption') or '（无）'}"]
    if turn.get("query"):
        parts += ["```sql", turn["query"].strip(), "```"]
    cand = candidate_of(turn, raw_dir, rec["qid"], rec["rep"])
    if cand == REFUSAL:
        parts.append("结果：拒答（CANNOT_ANSWER）")
    elif isinstance(cand, ExecError):
        parts.append(f"结果：执行失败。报错：{cand.message[:1500]}")
    else:
        cols = [c["name"] for c in turn["exec"].get("columns", [])]
        parts.append(_rows(cols, cand))
    f = rec["final"]
    parts += ["", "## 评分器", f"判定：{f['outcome']}；原因：{f.get('reason') or '（无）'}"]
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Parsing


def parse_labels(content: str) -> tuple[dict | None, str | None]:
    """The label object, or (None, why it is unparsed). No repair beyond stripping a code fence."""
    text = content.strip()
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    if m:
        text = m.group(1)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"not JSON: {exc.msg}"
    if not isinstance(obj, dict):
        return None, "not an object"
    missing = [k for k in LABELS if k not in obj]
    if missing:
        return None, f"missing {missing}"
    if obj["category"] not in CATEGORIES:
        return None, "category not in the codebook"
    if not isinstance(obj["declared_assumption"], bool):
        return None, "declared_assumption not a boolean"
    if not isinstance(obj["root_cause"], int) or isinstance(obj["root_cause"], bool) or not 1 <= obj["root_cause"] <= 5:
        return None, "root_cause not an integer 1-5"
    if not isinstance(obj["doc_evidence"], str) or not isinstance(obj["note"], str):
        return None, "doc_evidence / note not text"
    return obj, None


# ---------------------------------------------------------------------------
# Run


def log_line(rec: dict, prompt_sha: dict, user: str, reply: Reply | None, raw_sha: str | None,
             peak: bool, started: datetime, error: str | None = None) -> dict:
    labels, why = parse_labels(reply.content) if reply is not None else (None, None)
    line = {"run_id": None, "qid": rec["qid"], "rep": rec["rep"],
            "status": "api_error" if reply is None else ("done" if labels else "unparsed"),
            "source": {"run_id": SOURCE_RUN, "cell": CELL, "outcome": rec["final"]["outcome"],
                       "reason": rec["final"].get("reason")},
            **prompt_sha, "user_sha256": R.sha256(user), "model_requested": MODEL,
            "started_at": started.isoformat(timespec="seconds"), "peak": peak}
    if labels:   # note stays in runs-raw: it is free text
        line["labels"] = {k: labels[k] for k in LABELS if k != "note"}
    if why:
        line["unparsed"] = why
    if error:
        line["error"] = error[:500]
    if reply is not None:
        line.update({"model_version": reply.model_version, "system_fingerprint": reply.system_fingerprint,
                     "finish_reason": reply.finish_reason, "usage": reply.usage, "latency_s": round(reply.latency_s, 3),
                     "transport_retries": reply.transport_retries, "raw_sha256": raw_sha,
                     "cost_cny": R.cost_cny(MODEL, reply.usage, peak)})
    return line


def dry_run(system: str, users: list[str], output_tokens: int, hit_ratio: float) -> float:
    price = PRICES_OFFPEAK[MODEL]
    sys_tok = R.estimate_tokens_from_text(system)
    user_tok = [R.estimate_tokens_from_text(u) for u in users]
    n = len(users)
    # the first call reads the shared prefix uncached; the rest hit it at ``hit_ratio``
    cost = sum(((sys_tok * (price["miss"] if i == 0 else hit_ratio * price["hit"] + (1 - hit_ratio) * price["miss"]))
                + u * price["miss"] + output_tokens * price["output"]) / 1e6 for i, u in enumerate(user_tok))
    print(f"model={MODEL} items={n} calls={n} (one call per item, no retry)")
    print(f"system prefix ~{sys_tok} tokens; user ~{min(user_tok)}–{max(user_tok)} (mean {sum(user_tok) / n:.0f}); "
          f"output assumed {output_tokens}/call; prefix cache hit {hit_ratio:.0%}")
    print(f"estimated cost: {cost:.2f} CNY off-peak (peak {cost * PEAK_MULTIPLIER:.2f})")
    return cost


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", help="runs/<run-id>/; required unless --dry-run")
    ap.add_argument("--eval-tag", default="eval-v1.2")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget", type=float, help="CNY; refuse to start if the estimate exceeds it")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--allow-peak", action="store_true")
    ap.add_argument("--est-output-tokens", type=int, default=3000)
    ap.add_argument("--est-hit-ratio", type=float, default=0.95)
    args = ap.parse_args(argv)

    eval_full = verify_eval_tag(args.eval_tag)
    bank = bank_records()
    lines = source_lines()
    todo = items(lines, bank)
    system = system_message(lines[0]["system_sha256"])
    raw_src = R.raw_root() / "20261018-T13-sql-direct-01" / CELL     # the rescore reuses its source's runs-raw
    users = [user_message(r, bank[r["qid"]], raw_src) for r in todo]
    prompt_sha = {"prompt_sha256": R.sha256(PROMPT.read_bytes()), "codebook_sha256": R.sha256(CODEBOOK.read_bytes()),
                  "system_sha256": R.sha256(system), "eval_tag": args.eval_tag, "eval_commit": eval_full[:7],
                  "harness_commit": R.harness_commit()}
    print(f"question bank: {args.eval_tag} = {eval_full}; source {SOURCE_RUN}/{CELL}: {len(todo)} items "
          f"({sum(r['final']['outcome'] == 'wrong' for r in todo)} wrong, "
          f"{sum(r['final']['outcome'] == 'exec_error' for r in todo)} exec_error, "
          f"{sum(r['final']['outcome'] == 'refused' for r in todo)} refused)")
    print(f"prompt {prompt_sha['prompt_sha256'][:12]}  codebook {prompt_sha['codebook_sha256'][:12]}  "
          f"system {prompt_sha['system_sha256'][:12]}")
    estimate = dry_run(system, users, args.est_output_tokens, args.est_hit_ratio)
    if args.dry_run:
        return 0
    if not args.run_id:
        ap.error("--run-id is required unless --dry-run")
    if args.budget is not None and estimate > args.budget:
        print(f"refused: estimate {estimate:.2f} CNY exceeds --budget {args.budget}")
        return 2
    if R.is_peak() and not args.allow_peak:
        print("refused: DeepSeek peak hours (weekdays 09-12, 14-18 Beijing)")
        return 2

    log = REPO / "runs" / args.run_id / "attribution.jsonl"
    raw_dir = R.raw_root() / args.run_id
    done = set()
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line) if line.strip() else None
            if rec and rec["status"] in ("done", "unparsed"):
                if rec["system_sha256"] != prompt_sha["system_sha256"]:
                    raise RuntimeError("the prompt changed since the first paid call; it must not (T19b step 2)")
                done.add((rec["qid"], rec["rep"]))
    pending = [(r, u) for r, u in zip(todo, users) if (r["qid"], r["rep"]) not in done]
    print(f"{len(done)} already labelled; {len(pending)} to call")
    log.parent.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    boundary = R.CallBoundary(FINGERPRINT, allow_peak=args.allow_peak)
    client = DeepSeekClient(MODEL, before_request=boundary.before_request)
    lock = threading.Lock()
    spent = [0.0]

    def one(rec: dict, user: str) -> None:
        if boundary.stopped.is_set():
            return
        started = datetime.now(R.BEIJING)
        peak = R.is_peak(started)
        reply, raw_sha, error = None, None, None
        try:
            reply = client.chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
            raw_sha = R.sha256(reply.raw)
            (raw_dir / f"{rec['qid']}_r{rec['rep']}.json").write_bytes(reply.raw)
        except R.RunStopped:
            return
        except APIError as exc:
            error = str(exc)
        line = log_line(rec, prompt_sha, user, reply, raw_sha, peak, started, error)
        line["run_id"] = args.run_id
        with lock:
            with log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            spent[0] += line.get("cost_cny") or 0
            print(f"  {rec['qid']} r{rec['rep']}: {line['status']}"
                  + (f" {line['labels']['category']}/{line['labels']['root_cause']}" if "labels" in line else "")
                  + f"  ({spent[0]:.2f} CNY)", flush=True)
        if reply is not None:
            try:
                boundary.check_reply(reply)      # logged first, then stop on a second fingerprint
            except R.RunStopped:
                pass
        if args.budget is not None and spent[0] > args.budget:
            try:
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


if __name__ == "__main__":
    raise SystemExit(main())
