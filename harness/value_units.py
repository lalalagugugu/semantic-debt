"""Global reference-column unit policy; no benchmark IDs or values are used."""

from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import re
from numbers import Number
from typing import Literal, TypeAlias

ValueKind: TypeAlias = Literal["percentage", "ratio", "amount", "count", "other"]
KINDS = {"percentage", "ratio", "amount", "count", "other"}


def infer_value_kind(column_name: str, column_type: str = "") -> ValueKind:
    """Classify a reference name with fixed, case-insensitive lexical rules.

    Explicit percentage/ratio names take priority over underlying money words.
    Unrecognized names receive no absolute tolerance. This is not a semantic
    inference from magnitudes, integral values, candidate names, or question IDs.
    """
    name = re.sub(r"([a-z])([A-Z])", r"\1_\2", column_name).lower()
    tokens = set(re.findall(r"[a-z]+", name))
    if tokens & {"pct", "percent", "percentage", "percentile", "pp"}:
        return "percentage"
    if tokens & {"ratio", "rate", "correlation", "corr"}:
        return "ratio"
    if (tokens & {"count", "countdistinct", "num", "n", "customers", "orders", "stores", "brands", "employees", "observations", "reports", "units", "returns"}
            or {"cohort", "size"} <= tokens or "returned" in tokens):
        return "count"
    if re.search(r"\bU?Int\d+\b", column_type) and "sales" in tokens and not tokens & {"amount", "price", "revenue"}:
        return "count"
    if tokens & {"amount", "amt", "revenue", "sales", "spend", "spent", "cost", "cogs", "price", "profit", "income", "budget", "quota", "ltv", "dollars", "discount", "margin"} or {"lifetime", "value"} <= tokens:
        return "amount"
    return "other"


def absolute_tolerance(kind: ValueKind) -> float:
    # Percentage reference values are in percentage points; normalize to a
    # fraction before applying 1e-4, equivalent to 0.01 in the original unit.
    return {"percentage": 0.01, "ratio": 0.0001, "amount": 0.01}.get(kind, 0.0)


def quantize_tie(value: object, kind: ValueKind = "other") -> object:
    if isinstance(value, (bool, complex)) or not isinstance(value, (Number, Decimal)):
        return value
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("tie keys must be finite")
    with localcontext() as ctx:
        ctx.prec = max(50, len(number.as_tuple().digits) + abs(number.adjusted()) + 10)
        if kind == "percentage":
            number /= Decimal(100)
        quantum = Decimal("0.01") if kind == "amount" else Decimal("0.000001")
        return number.quantize(quantum, rounding=ROUND_HALF_EVEN)
