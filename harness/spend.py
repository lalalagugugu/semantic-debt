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


class ConcurrentSpendGuard:
    """Atomically admit requests using settled cost plus in-flight estimates.

    The estimate is not an API-enforced token cap. Already admitted requests
    always finish and settle, even when another worker closes admission.
    """
    def __init__(self, path: Path, limit: float, model: str, max_call_cost: float) -> None:
        if any(not math.isfinite(x) or x <= 0 for x in (limit, max_call_cost)):
            raise ValueError("budget and maximum call estimate must be finite and positive")
        self.path, self.model = path, model
        self.limit, self.max_call_cost = Decimal(str(limit)), Decimal(str(max_call_cost))
        self.total = Decimal(0)
        self.lock = threading.Lock()
        self.outstanding = set()
        self.sequence = 0
        self.closed = False
        seen = set()
        if path.exists():
            for line in path.read_text().splitlines():
                r = json.loads(line)
                if (r.get("version") != 2 or r["model"] != model or Decimal(r["limit_cny"]) != self.limit
                        or Decimal(r["max_call_cost_cny"]) != self.max_call_cost):
                    raise ValueError("saved concurrent ledger configuration differs")
                ticket = r["request_id"]
                self.closed = self.closed or r.get("admission_closed", False)
                self.sequence = max(self.sequence, ticket)
                if r["event"] == "closed" and r.get("admission_closed") is True:
                    continue
                if r["event"] == "request" and type(ticket) is int and ticket > 0 and ticket not in seen:
                    seen.add(ticket)
                    self.outstanding.add(ticket)
                elif r["event"] == "charge" and ticket in self.outstanding:
                    amount = Decimal(r["cost_cny"])
                    if not amount.is_finite() or amount < 0:
                        raise ValueError("invalid saved charge")
                    self.total += amount
                    self.outstanding.remove(ticket)
                else:
                    raise ValueError("invalid concurrent ledger event order")
            if self.outstanding:
                raise ValueError("unresolved request in concurrent ledger; reconcile before resuming")
        elif path.parent.exists() and any(path.parent.glob("*/Q*_r*_t*.json")):
            raise ValueError("existing raw calls have no spend ledger")

    @property
    def exposure(self):
        return self.total + len(self.outstanding) * self.max_call_cost

    @property
    def reached(self):
        with self.lock:
            return self.closed or self.exposure >= self.limit

    def _append(self, event, ticket, **fields):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps({"version": 2, "event": event, "request_id": ticket,
                                "model": self.model, "limit_cny": str(self.limit),
                                "max_call_cost_cny": str(self.max_call_cost), **fields}) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def begin(self, cell, qid, rep, turn):
        with self.lock:
            if self.closed or self.exposure + self.max_call_cost > self.limit:
                if not self.closed:
                    self._append("closed", self.sequence, admission_closed=True)
                self.closed = True
                raise SpendLimit(f"runtime admission stopped: settled plus in-flight estimate {self.exposure} / {self.limit} CNY")
            self.sequence += 1
            ticket = self.sequence
            closes = self.exposure + self.max_call_cost >= self.limit
            self._append("request", ticket, cell=cell, qid=qid, rep=rep, turn=turn, admission_closed=closes)
            self.outstanding.add(ticket)
            self.closed = closes
            return ticket

    def charge(self, ticket, cost, usage):
        required = ("prompt_tokens", "cache_hit_tokens", "cache_miss_tokens", "completion_tokens")
        if (cost is None or not math.isfinite(cost) or cost < 0
                or any(type(usage.get(k)) is not int or usage[k] < 0 for k in required)
                or usage["prompt_tokens"] <= 0
                or usage["cache_hit_tokens"] + usage["cache_miss_tokens"] != usage["prompt_tokens"]):
            raise SpendLimit("unconfirmed API usage/cost; stop and reconcile")
        with self.lock:
            if ticket not in self.outstanding:
                raise ValueError("unknown or already charged request")
            amount = Decimal(str(cost))
            self.closed = (self.closed or amount > self.max_call_cost
                           or self.total + amount + (len(self.outstanding) - 1) * self.max_call_cost >= self.limit)
            self._append("charge", ticket, cost_cny=str(amount), usage=usage, admission_closed=self.closed)
            self.total += amount
            self.outstanding.remove(ticket)
