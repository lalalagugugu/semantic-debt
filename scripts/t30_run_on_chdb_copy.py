"""T30 runner: use only this card's private chDB copy (hard rule 9)."""
import os
import sys
import json
import math
import threading
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import executors  # noqa: E402
from harness import run_direct  # noqa: E402

class BudgetBoundary(run_direct.CallBoundary):
    """Account each saved API receipt before SQL execution or another fix call."""

    def __init__(self, expected_fingerprint, allow_peak=False, *, budget, raw_dir):
        super().__init__(expected_fingerprint, allow_peak)
        self.budget = Decimal(str(budget))
        self.spent = Decimal(0)
        self.lock = threading.Lock()
        for path in raw_dir.glob("*_r*_t[01].json"):
            self.spent += self.receipt_cost(path.read_bytes())

    @staticmethod
    def receipt_cost(raw):
        usage = json.loads(raw)["usage"]
        fields = ("prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens")
        if any(type(usage.get(k)) is not int or usage[k] < 0 for k in fields):
            raise ValueError("API receipt has missing or invalid billing usage")
        return sum(Decimal(usage[k]) * rate for k, rate in zip(
            fields, (Decimal("0.02"), Decimal("1"), Decimal("4")))) / Decimal(1_000_000)

    def before_request(self):
        with self.lock:
            if self.spent >= self.budget:
                self.stop(f"budget reached: {self.spent} CNY >= {self.budget} CNY")
            super().before_request()

    def check_reply(self, reply):
        with self.lock:
            try:
                self.spent += self.receipt_cost(reply.raw)
            except (ValueError, KeyError, TypeError):
                self.stop("cannot reconcile API billing usage; stop before further calls")
            super().check_reply(reply)
            if self.spent >= self.budget:
                self.stop(f"budget reached: {self.spent} CNY >= {self.budget} CNY")
            if self.stopped.is_set():
                raise run_direct.RunStopped(self.reason)


def main(argv=None):
    args = run_direct.parse_args(argv)
    if args.cell != ["SQL-L1plus-tuned-instr"] or args.model != "deepseek-flash" or args.allow_peak:
        raise SystemExit("T30 wrapper requires only the combo cell, Flash and off-peak execution")
    copy = Path(os.environ["SEMDEBT_DATA_DIR"]) / "chdb-t30"
    executors.default_chdb_path = lambda: str(copy)
    if not args.dry_run:
        if not copy.is_dir():
            raise SystemExit("Missing private chDB copy: SEMDEBT_DATA_DIR/chdb-t30")
        if args.budget is None or not math.isfinite(args.budget) or args.budget <= 0:
            raise SystemExit("A positive finite --budget is required")
        raw_dir = run_direct.raw_root() / args.run_id / args.cell[0]
        run_direct.CallBoundary = lambda expected_fingerprint, allow_peak=False: BudgetBoundary(
            expected_fingerprint, allow_peak, budget=args.budget, raw_dir=raw_dir)
    return run_direct.main(argv)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
