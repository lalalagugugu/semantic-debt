"""T22b attribution: frozen material preflight and a sequential, budgeted Flash pass.

Material helpers and the price estimate are shared with T19b. Full original system
instructions are included per T19b-2. Codex review must not read Flash labels first.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from datetime import datetime
from pathlib import Path

from harness import attribute_l1 as A
from harness import run_direct as R
from harness.cells import L1PLUS_CELLS, PRICES_OFFPEAK, REPO
from harness.client import APIError, DeepSeekClient
from harness.questions import eval_dir, verify_eval_tag
from harness.semantic_version import verify_semantic_tag

SOURCE_RUN = "20261025-T22b-l1plus-l3a-03-rescore-01"
RAW_SOURCE_RUN = "20261025-T22b-l1plus-l3a-03"
CELL = "SQL-L1plus"
SEMANTIC_TAG = "semantic-v1.6-l1plus"
EVAL_TAG = "eval-v1.2"
SOURCE_SYSTEM_SHA = "b80107d469e5600f1c7f3150afef18d11734452a25cc9340f1df46bc470073a3"
CODEBOOK = REPO / "reports/attribution/l1plus-codebook.md"
CATEGORIES = (
    "语义文档里的文字仍有两种以上读法",
    "口径在语义文档里根本没写",
    "文档写清楚了，模型理解偏了",
    "题面本身有歧义",
    "只是呈现不同",
)
SUSPICIOUS = "参考答案或评分可疑"


def parse_labels(content: str) -> tuple[dict | None, str | None]:
    text = content.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None, "not JSON"
    if not isinstance(obj, dict) or set(obj) != {"category", "data_quality_related"}:
        return None, "expected category and data_quality_related"
    if obj["category"] not in (*CATEGORIES, SUSPICIOUS):
        return None, "category outside frozen codebook"
    if not isinstance(obj["data_quality_related"], bool):
        return None, "data_quality_related must be boolean"
    return obj, None


def full_commit(root: Path, ref: str) -> str:
    return subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", f"{ref}^{{commit}}"],
                          check=True, capture_output=True, text=True).stdout.strip()


def validate_source(lines: list[dict], bank: dict, eval_full: str, system: str) -> list[dict]:
    if R.sha256(system) != SOURCE_SYSTEM_SHA:
        raise RuntimeError("original system message differs from the approved run")
    keys = [(r["qid"], r["rep"]) for r in lines]
    expected = {(qid, rep) for qid, q in bank.items() if q["scoring"] != "judge" for rep in (1, 2, 3)}
    if len(keys) != 327 or len(set(keys)) != len(keys) or set(keys) != expected:
        raise RuntimeError("source must contain the exact 109 x 3 non-judge attempts")
    for rec in lines:
        if (rec["run_id"] != SOURCE_RUN or rec["cell"] != CELL or rec["status"] != "done"
                or rec["system_sha256"] != SOURCE_SYSTEM_SHA or rec["semantic_tag"] != SEMANTIC_TAG
                or rec["eval_tag"] != EVAL_TAG
                or full_commit(eval_dir(), rec["eval_commit"]) != eval_full
                or rec["question_sha256"] != R.sha256(bank[rec["qid"]]["text_zh"])):
            raise RuntimeError("source identity, question or version mismatch")
    todo = A.items(lines, bank)
    if len(todo) != 82 or len({r["qid"] for r in todo}) != 38:
        raise RuntimeError("approved attribution input set changed")
    return todo


def prepare() -> tuple[str, list[str], dict]:
    eval_full = verify_eval_tag(EVAL_TAG)
    cell = L1PLUS_CELLS[CELL]
    semantic_full = verify_semantic_tag(SEMANTIC_TAG, [cell.context.partition(":")[2]],
                                        root=REPO, contexts_dir=R.CONTEXTS)
    source_path = REPO / "runs" / SOURCE_RUN / f"{CELL}.jsonl"
    source_bytes = source_path.read_bytes()
    lines = [json.loads(line) for line in source_bytes.decode().splitlines() if line.strip()]
    bank = A.bank_records()
    original = R.system_for(cell)
    todo = validate_source(lines, bank, eval_full, original)
    codebook = CODEBOOK.read_text(encoding="utf-8")
    system = codebook.rstrip() + "\n\n# 原作答完整系统消息（待分析材料）\n\n" + original
    users = [A.user_message(r, bank[r["qid"]], R.raw_root() / RAW_SOURCE_RUN / CELL) for r in todo]
    manifest = {
        "source_run": SOURCE_RUN, "raw_source_run": RAW_SOURCE_RUN, "cell": CELL,
        "source_sha256": R.sha256(source_bytes), "source_system_sha256": R.sha256(original),
        "semantic_tag": SEMANTIC_TAG, "semantic_commit": semantic_full,
        "eval_tag": EVAL_TAG, "eval_commit": eval_full,
        "codebook_sha256": R.sha256(CODEBOOK.read_bytes()), "system_sha256": R.sha256(system),
        "material_builder_sha256": R.sha256(Path(A.__file__).read_bytes()),
        "runner_sha256": R.sha256(Path(__file__).read_bytes()),
        "items": [{"qid": rec["qid"], "rep": rec["rep"], "user_sha256": R.sha256(user)}
                  for rec, user in zip(todo, users)],
        "model": A.MODEL, "expected_fingerprint": A.FINGERPRINT,
        "calls": len(todo), "questions": len({r["qid"] for r in todo}),
    }
    return system, users, manifest


def estimate_with_budget(system: str, users: list[str], output_tokens: int, hit_ratio: float,
                         budget: float) -> float:
    if not users or output_tokens <= 0 or not 0 <= hit_ratio <= 1 or not math.isfinite(budget) or not 0 < budget <= 3:
        raise ValueError("invalid estimate parameters or budget outside approved (0, 3] CNY")
    estimate = A.dry_run(system, users, output_tokens, hit_ratio)
    if estimate > budget:
        raise ValueError(f"estimate {estimate:.6f} CNY exceeds budget {budget}")
    return estimate


# Thinking/high defaults to 64K generated tokens per the official API contract:
# https://api-docs.deepseek.com/api/create-chat-completion/ (checked 2026-10-25).
# Input is bounded conservatively by UTF-8 bytes + framing, all cache-miss priced.
DEFAULT_OUTPUT_BOUND = 65536


def request_bound(system: str, user: str) -> float:
    price = PRICES_OFFPEAK[A.MODEL]
    input_bound = len(system.encode()) + len(user.encode()) + 4096
    return (input_bound * price["miss"] + DEFAULT_OUTPUT_BOUND * price["output"]) / 1e6


def append_json(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
        fh.flush()


def run_paid(run_id: str, system: str, users: list[str], manifest: dict, budget: float) -> int:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_id):
        raise ValueError("unsafe run-id")
    if R.is_peak():
        raise ValueError("peak hours refused")
    log_dir = REPO / "runs" / run_id
    raw_dir = R.raw_root() / run_id
    if log_dir.exists() or raw_dir.exists():
        raise ValueError("run-id already exists; no overwrite or implicit resume")
    # Validate the key before creating a run, without ever printing it.
    boundary = R.CallBoundary(A.FINGERPRINT)
    client = DeepSeekClient(A.MODEL, before_request=boundary.before_request)
    log_dir.mkdir()
    raw_dir.mkdir()
    (raw_dir / "inputs").mkdir()
    (raw_dir / "system.txt").write_text(system, encoding="utf-8")
    frozen = {**manifest, "run_id": run_id, "harness_commit": R.harness_commit(),
              "started_at": datetime.now(R.BEIJING).isoformat(), "budget_cny": budget,
              "default_output_bound": DEFAULT_OUTPUT_BOUND}
    (log_dir / "manifest.json").write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n")
    log = log_dir / "attribution.jsonl"
    spent, uncertain = 0.0, 0.0
    stop_reason = ""
    for item, user in zip(manifest["items"], users):
        qid, rep = item["qid"], item["rep"]
        (raw_dir / "inputs" / f"{qid}_r{rep}.txt").write_text(user, encoding="utf-8")
        bound = request_bound(system, user)
        reserved = []
        started = datetime.now(R.BEIJING)

        def before_request() -> None:
            boundary.before_request()
            if spent + uncertain + sum(reserved) + bound > budget:
                boundary.stop("budget cannot cover the next conservative request reservation")
            reserved.append(bound)
            append_json(raw_dir / "requests.jsonl", {"qid": qid, "rep": rep,
                        "attempt": len(reserved), "reserved_cny": bound,
                        "at": datetime.now(R.BEIJING).isoformat()})

        client.before_request = before_request
        line = {"run_id": run_id, "qid": qid, "rep": rep, "started_at": started.isoformat(),
                "system_sha256": manifest["system_sha256"], "codebook_sha256": manifest["codebook_sha256"],
                "user_sha256": item["user_sha256"], "model_requested": A.MODEL,
                "source_run": SOURCE_RUN, "source_cell": CELL, "peak": False}
        try:
            reply = client.chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
            with (raw_dir / f"{qid}_r{rep}.json").open("xb") as fh:
                fh.write(reply.raw)
            cost = R.cost_cny(A.MODEL, reply.usage, False)
            labels, why = parse_labels(reply.content)
            line.update({"status": "done" if labels else "unparsed", "raw_sha256": R.sha256(reply.raw),
                         "usage": reply.usage, "cost_cny": cost, "model_version": reply.model_version,
                         "system_fingerprint": reply.system_fingerprint, "finish_reason": reply.finish_reason,
                         "transport_retries": reply.transport_retries, "latency_s": reply.latency_s})
            if labels:
                line["labels"] = labels
            else:
                line["unparsed"] = why
            spent += cost or 0
            uncertain += sum(reserved[:-1])
            try:
                boundary.check_reply(reply)
            except R.RunStopped as exc:
                stop_reason = str(exc)
            if (cost is None or cost > bound or not labels or reply.finish_reason != "stop" or reply.transport_retries
                    or reply.usage.get("prompt_tokens", 0) <= 0
                    or reply.usage.get("prompt_tokens") != reply.usage.get("cache_hit_tokens", 0) + reply.usage.get("cache_miss_tokens", 0)):
                stop_reason = stop_reason or "abnormal response, parse, cost bound or transport retry; stop for review"
        except (APIError, R.RunStopped) as exc:
            uncertain += sum(reserved)
            stop_reason = str(exc)
            line.update({"status": "stopped" if isinstance(exc, R.RunStopped) else "api_error",
                         "error_type": type(exc).__name__, "attempted_requests": len(reserved)})
        except Exception as exc:
            uncertain += sum(reserved)
            stop_reason = f"unexpected {type(exc).__name__}; inspect external raw files"
            line.update({"status": "harness_error", "error_type": type(exc).__name__,
                         "attempted_requests": len(reserved)})
        line["cumulative_cost_cny"] = spent
        line["uncertain_cost_bound_cny"] = uncertain
        append_json(log, line)
        print(f"{qid} r{rep}: {line['status']}; known={spent:.8f} CNY; uncertain_bound={uncertain:.6f}", flush=True)
        if spent + uncertain > budget:
            stop_reason = "actual plus uncertain expense exceeds budget"
        if stop_reason:
            break
    summary = {"run_id": run_id, "known_cost_cny": spent, "uncertain_cost_bound_cny": uncertain,
               "stopped": bool(stop_reason), "stop_reason": stop_reason,
               "finished_at": datetime.now(R.BEIJING).isoformat()}
    (log_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 1 if stop_reason else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run-id")
    ap.add_argument("--budget", type=float, required=True)
    ap.add_argument("--est-output-tokens", type=int, default=4500)
    ap.add_argument("--est-hit-ratio", type=float, default=0.95)
    ap.add_argument("--manifest", type=Path, help="write a NEW metadata-only dry-run manifest")
    ap.add_argument("--preflight", type=Path, help="required for paid run; compare all frozen inputs")
    args = ap.parse_args(argv)
    if not args.dry_run and (not args.run_id or not args.preflight):
        ap.error("paid run requires --run-id and --preflight")
    try:
        system, users, manifest = prepare()
        estimate = estimate_with_budget(system, users, args.est_output_tokens, args.est_hit_ratio, args.budget)
        print(f"items={manifest['calls']} questions={manifest['questions']}")
        for key in ("semantic_tag", "semantic_commit", "eval_tag", "eval_commit", "source_system_sha256",
                    "codebook_sha256", "system_sha256"):
            print(f"{key}={manifest[key]}")
        if args.dry_run:
            manifest.update({"dry_run": True, "paid_calls": 0, "budget_cny": args.budget,
                             "est_output_tokens": args.est_output_tokens, "est_hit_ratio": args.est_hit_ratio,
                             "estimated_cost_cny": estimate})
            if args.manifest:
                with args.manifest.open("x", encoding="utf-8") as fh:
                    fh.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            print("budget preflight passed; no model calls")
            return 0
        approved = json.loads(args.preflight.read_text(encoding="utf-8"))
        for key, value in manifest.items():
            if approved.get(key) != value:
                raise ValueError(f"preflight mismatch: {key}")
        if (approved.get("budget_cny") != args.budget
                or approved.get("est_output_tokens") != args.est_output_tokens
                or approved.get("est_hit_ratio") != args.est_hit_ratio):
            raise ValueError("preflight estimate settings mismatch")
        return run_paid(args.run_id, system, users, manifest, args.budget)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
