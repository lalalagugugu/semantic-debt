"""Persistent, serialized API spend accounting for the T29 runtime threshold."""
from __future__ import annotations

import json
import math
import os
import threading
from decimal import Decimal
from pathlib import Path


class SpendLimit(RuntimeError):
    pass


class SpendGuard:
    def __init__(self, path: Path, limit: float, model: str) -> None:
        if not math.isfinite(limit) or limit <= 0:
            raise ValueError("runtime budget must be finite and positive")
        self.path = path
        self.limit = Decimal(str(limit))
        self.model = model
        self.total = Decimal(0)
        self.pending = False
        self.lock = threading.Lock()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                if record["model"] != model or Decimal(record["limit_cny"]) != self.limit:
                    raise ValueError("runtime budget/model differs from the saved spend ledger")
                if record["event"] == "request":
                    if self.pending:
                        raise ValueError("unresolved request in spend ledger; reconcile its cost before resuming")
                    self.pending = True
                elif record["event"] == "charge" and self.pending:
                    cost = Decimal(record["cost_cny"])
                    if not cost.is_finite() or cost < 0:
                        raise ValueError("invalid cost in spend ledger")
                    self.total += cost
                    self.pending = False
                else:
                    raise ValueError("invalid spend ledger event order")
            if self.pending:
                raise ValueError("unresolved request in spend ledger; reconcile its cost before resuming")
        elif path.parent.exists() and any(path.parent.glob("*/Q*_r*_t*.json")):
            raise ValueError("existing raw calls have no spend ledger; reconcile costs before resuming")

    def _append(self, event: str, **fields) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as out:
            out.write(json.dumps({"event": event, "model": self.model,
                                  "limit_cny": str(self.limit), **fields}) + "\n")
            out.flush()
            # A crash must not erase a started request and reset its spend.
            os.fsync(out.fileno())

    @property
    def reached(self) -> bool:
        return self.total >= self.limit

    def begin(self, cell: str, qid: str, rep: int, turn: int) -> None:
        if self.pending or self.reached:
            raise SpendLimit(f"runtime budget stopped: spent {self.total} CNY / {self.limit} CNY")
        self._append("request", cell=cell, qid=qid, rep=rep, turn=turn)
        self.pending = True

    def charge(self, cost: float | None, usage: dict) -> None:
        required = ("prompt_tokens", "cache_hit_tokens", "cache_miss_tokens", "completion_tokens")
        if (cost is None or not math.isfinite(cost) or cost < 0
                or any(type(usage.get(k)) is not int or usage[k] < 0 for k in required)
                or usage["prompt_tokens"] <= 0
                or usage["cache_hit_tokens"] + usage["cache_miss_tokens"] != usage["prompt_tokens"]):
            raise SpendLimit("unconfirmed API usage/cost; stop and reconcile before resuming")
        amount = Decimal(str(cost))
        self._append("charge", cost_cny=str(amount), usage=usage)
        self.total += amount
        self.pending = False
