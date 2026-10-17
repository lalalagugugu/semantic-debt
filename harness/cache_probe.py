"""Measure how long DeepSeek's prefix cache keeps a cell's system message (T12).

For each delay d a distinct prefix is made by putting a probe line in front of the
cell's real system message (``[cache-probe <run-id> d=<d>s]``), so every delay has
its own cache entry. Each prefix gets one warm call at the start and one probe call
d seconds later; the probe's ``prompt_cache_hit_tokens`` says whether the entry
survived. The user message is a fixed instruction unrelated to the question bank,
so no question text is sent or logged.

    uv run python -m harness.cache_probe --cell SQL-L1 --model deepseek-flash --dry-run
    uv run python -m harness.cache_probe --cell SQL-L1 --model deepseek-flash --run-id 20261018-T12-cache-flash-01

Log      runs/<run-id>/cache-probe.jsonl        one line per call, append-only
Raw      $SEMDEBT_DATA_DIR/runs-raw/<run-id>/cache-probe/
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.cells import CELLS, PRICES_OFFPEAK, REPO  # noqa: E402
from harness.client import APIError  # noqa: E402
from harness.run_direct import (  # noqa: E402
    BEIJING, cost_cny, estimate_tokens_from_text, harness_commit, is_peak, raw_root, sha256, system_for,
)

USER_MESSAGE = "这是一次缓存测试，不是业务问题。请只回复 OK。"
DEFAULT_DELAYS = (10, 300, 900, 1800, 3600, 7200, 14400)   # seconds


def probe_system(system: str, run_id: str, delay: int) -> str:
    return f"[cache-probe {run_id} d={delay}s]\n{system}"


def estimate(cell: str, model: str, delays: tuple[int, ...]) -> tuple[int, float]:
    """Upper bound: every call a full cache miss, 300 output tokens."""
    tokens = estimate_tokens_from_text(system_for(CELLS[cell])) + 40
    price = PRICES_OFFPEAK[model]
    calls = 2 * len(delays)
    return calls, calls * (tokens * price["miss"] + 300 * price["output"]) / 1e6


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell", default="SQL-L1")
    ap.add_argument("--model", default="deepseek-flash", choices=sorted(PRICES_OFFPEAK))
    ap.add_argument("--run-id")
    ap.add_argument("--delays", default=",".join(map(str, DEFAULT_DELAYS)), help="seconds, comma-separated")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget", type=float)
    ap.add_argument("--allow-peak", action="store_true")
    args = ap.parse_args(argv)
    delays = tuple(sorted(int(x) for x in args.delays.split(",")))
    calls, bound = estimate(args.cell, args.model, delays)
    print(f"{args.cell} {args.model}: {calls} calls, at most {bound:.2f} CNY off-peak (all misses); "
          f"longest delay {delays[-1] / 3600:.1f} h")
    if args.dry_run:
        return 0
    if not args.run_id:
        ap.error("--run-id is required unless --dry-run")
    if args.budget is not None and bound > args.budget:
        print(f"bound {bound:.2f} CNY exceeds budget {args.budget:.2f}; stop and ask the user")
        return 2

    from harness.client import DeepSeekClient

    client = DeepSeekClient(args.model)
    system = system_for(CELLS[args.cell])
    log = REPO / "runs" / args.run_id / "cache-probe.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    raw = raw_root() / args.run_id / "cache-probe"
    raw.mkdir(parents=True, exist_ok=True)
    commit = harness_commit()

    def call(delay: int, kind: str, warmed_at: float | None) -> float:
        text = probe_system(system, args.run_id, delay)
        started = time.time()
        peak = is_peak()
        rec = {"run_id": args.run_id, "cell": args.cell, "model_requested": args.model, "delay_s": delay,
               "kind": kind, "system_sha256": sha256(system), "probe_system_sha256": sha256(text),
               "harness_commit": commit, "started_at": datetime.now(BEIJING).isoformat(timespec="seconds"),
               "since_warm_s": round(started - warmed_at, 1) if warmed_at else None}
        try:
            reply = client.chat([{"role": "system", "content": text}, {"role": "user", "content": USER_MESSAGE}])
        except APIError as exc:
            rec.update(status="api_error", error=str(exc)[:500], transport_retries=exc.transport_retries)
        else:
            path = raw / f"d{delay}_{kind}.json"
            path.write_bytes(reply.raw)
            rec.update(status="done", system_fingerprint=reply.system_fingerprint, usage=reply.usage,
                       latency_s=round(reply.latency_s, 3), transport_retries=reply.transport_retries,
                       raw_sha256=sha256(reply.raw), cost_cny=cost_cny(args.model, reply.usage, peak), peak=peak)
        with log.open("a", encoding="utf-8") as out:
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        u = rec.get("usage") or {}
        print(f"d={delay}s {kind}: hit {u.get('cache_hit_tokens')} miss {u.get('cache_miss_tokens')} "
              f"since_warm {rec['since_warm_s']}", flush=True)
        return started

    if is_peak() and not args.allow_peak:
        print("DeepSeek peak hours: run off-peak (hard rule 6)")
        return 2
    warmed = {d: call(d, "warm", None) for d in delays}
    for d in delays:
        wait = warmed[d] + d - time.time()
        if wait > 0:
            time.sleep(wait)
        call(d, "probe", warmed[d])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
