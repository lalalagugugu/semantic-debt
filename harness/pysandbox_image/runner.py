"""Runs inside the Python sandbox container (T21 planning agent). Not imported by the harness.

stdin  : one JSON object {"code": str, "tables": {"<n>": {"columns": [{"name", "type"}], "rows": [[...]]}},
         "want_answer": bool}
stdout : one JSON object {"ok": bool, "stdout": str, "error": str | null,
         "answer": {"columns": [{"name", "type"}], "rows": [[...]]} | null}

The model's code sees ``results``: a dict from result number to a pandas DataFrame, with
columns typed from the ClickHouse column types. When ``want_answer`` is set the code must
assign a DataFrame to ``answer``; its rows come back as plain JSON values (dates as
YYYY-MM-DD, NaN as null). The container has no network and no mounted files; this script
does not need either.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import re
import sys
import traceback

import numpy as np
import pandas as pd

_WRAPPER = re.compile(r"^(?:Nullable|LowCardinality)\((.*)\)$")


def _base_type(t: str) -> str:
    t = (t or "").strip()
    while (m := _WRAPPER.match(t)):
        t = m.group(1).strip()
    return t


def _frame(table: dict) -> pd.DataFrame:
    cols = table.get("columns") or []
    names = [c.get("name", f"c{i}") for i, c in enumerate(cols)]
    rows = table.get("rows") or []
    if not names and rows:
        names = [f"c{i}" for i in range(len(rows[0]))]
    df = pd.DataFrame(rows, columns=names)
    for i, c in enumerate(cols):
        t = _base_type(c.get("type", ""))
        s = df.iloc[:, i]
        if re.match(r"^U?Int\d+$", t):
            na = s.isna().any()
            kind = ("UInt64" if na else "uint64") if t == "UInt64" else ("Int64" if na else "int64")
            df.isetitem(i, pd.to_numeric(s, errors="coerce").astype(kind))
        elif t.startswith(("Float", "Decimal")):
            df.isetitem(i, pd.to_numeric(s, errors="coerce").astype("float64"))
        elif t.startswith(("Date", "DateTime")):
            df.isetitem(i, pd.to_datetime(s, errors="coerce"))
    return df


def _value(v):
    if v is None or v is pd.NaT:
        return None
    if isinstance(v, (pd.Timestamp,)):
        return v.strftime("%Y-%m-%d") if v == v.normalize() else v.isoformat(sep=" ")
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (bool, int, float, str)):
        return v
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return str(v)


def _dtype(series: pd.Series) -> str:
    kind = series.dtype.kind
    return {"i": "Int64", "u": "UInt64", "f": "Float64", "b": "Bool", "M": "Date"}.get(kind, "String")


def _answer(obj) -> dict:
    if isinstance(obj, pd.Series):
        obj = obj.to_frame()
    if not isinstance(obj, pd.DataFrame):
        raise TypeError(f"answer 必须是 pandas DataFrame，实际是 {type(obj).__name__}")
    df = obj.reset_index(drop=True)
    return {"columns": [{"name": str(c), "type": _dtype(df.iloc[:, i])} for i, c in enumerate(df.columns)],
            "rows": [[_value(v) for v in row] for row in df.itertuples(index=False, name=None)]}


def main() -> None:
    request = json.loads(sys.stdin.read())
    out = {"ok": False, "stdout": "", "error": None, "answer": None}
    buf = io.StringIO()
    try:
        results = {int(k): _frame(v) for k, v in (request.get("tables") or {}).items()}
        scope = {"results": results, "pd": pd, "np": np, "__name__": "__main__"}
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(compile(request["code"], "<python>", "exec"), scope)
        if request.get("want_answer"):
            if "answer" not in scope:
                raise NameError("代码没有给变量 answer 赋值（需要一个 pandas DataFrame）")
            out["answer"] = _answer(scope["answer"])
        out["ok"] = True
    except BaseException:  # noqa: BLE001 - every failure goes back to the model as text
        lines = traceback.format_exc().splitlines()
        # drop this runner's own frames; keep the model's code frames and the message
        keep = [l for l in lines if 'File "/sandbox/runner.py"' not in l]
        out["error"] = "\n".join(keep[-20:])
    out["stdout"] = buf.getvalue()
    sys.__stdout__.write(json.dumps(out, ensure_ascii=False, default=str))
    sys.__stdout__.flush()


if __name__ == "__main__":
    main()
