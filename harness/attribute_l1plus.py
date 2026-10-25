"""T22b attribution preflight; no model client is constructed in this preparation phase.

Material helpers and the price estimate are shared with T19b. Full original system
instructions are included per T19b-2. Paid execution awaits separate user approval.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path

from harness import attribute_l1 as A
from harness import run_direct as R
from harness.cells import L1PLUS_CELLS, REPO
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
    if not isinstance(obj, dict) or set(obj) != {"category"}:
        return None, "expected only category"
    if obj["category"] not in (*CATEGORIES, SUSPICIOUS):
        return None, "category outside frozen codebook"
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", required=True,
                    help="only preflight is enabled; paid attribution awaits user confirmation")
    ap.add_argument("--budget", type=float, required=True)
    ap.add_argument("--est-output-tokens", type=int, default=4500,
                    help="includes reasoning tokens; conservative allowance over T19b's 3000-token assumption")
    ap.add_argument("--est-hit-ratio", type=float, default=0.95)
    ap.add_argument("--manifest", type=Path, help="write a NEW metadata-only preflight manifest")
    args = ap.parse_args(argv)
    try:
        system, users, manifest = prepare()
        estimate = estimate_with_budget(system, users, args.est_output_tokens, args.est_hit_ratio, args.budget)
        manifest.update({"dry_run": True, "paid_calls": 0, "budget_cny": args.budget,
                         "est_output_tokens": args.est_output_tokens, "est_hit_ratio": args.est_hit_ratio,
                         "estimated_cost_cny": estimate})
        print(f"items={manifest['calls']} questions={manifest['questions']}")
        for key in ("semantic_tag", "semantic_commit", "eval_tag", "eval_commit", "source_system_sha256",
                    "codebook_sha256", "system_sha256"):
            print(f"{key}={manifest[key]}")
        if args.manifest:
            with args.manifest.open("x", encoding="utf-8") as fh:
                fh.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        print("budget preflight passed; no model calls")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
