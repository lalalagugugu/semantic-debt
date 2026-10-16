"""Reference results for the English anchors (R-EN, L1c-EN).

decisions/2026-10-16-q79-release-and-anchor-refs.md §2: the anchors are scored
against the external benchmark's *own* reference — its ``expected_sql`` from
``vendor/cube/text_to_sql_benchmark.json``, unmodified — so the numbers stay
comparable with the published ones. (Our revised references are a second,
sensitivity column; see ``harness/questions.py``.)

This script executes each original reference query once, in full, on the same
chDB the candidates run on, with the reference settings used by the question
bank (``max_threads = 1``, no time limit), and stores the result outside the
repository:

    $SEMDEBT_DATA_DIR/anchor-refs/<benchmark run>/qNN.json     {"meta": [...], "rows": [...]}
    $SEMDEBT_DATA_DIR/anchor-refs/<benchmark run>/MANIFEST.json

Top-N boundary (decisions/2026-10-16-q79-release-and-anchor-refs.md §4.3, and
the scorer's contract that a Top-N reference holds the complete boundary tie
group): an original query that truncates with ``LIMIT n`` or ``row_number()`` can
drop rows tied at the boundary (EN79: all 306 stores tie, the original keeps 10).
Each original query is therefore also run with only those two truncations made
tie-inclusive (``LIMIT n WITH TIES``, ``rank()``; nothing else changes, so the
result differs only where there are ties). When that adds rows, it is stored next
to the original as ``qNN.boundary.json``; ``harness/questions.py`` uses it for
anchors whose rules are Top-N (``top_n`` or ``selection``).

Reference answers never enter this repository. ``--check`` re-executes and
compares the stored files byte for byte.

    uv run python -m harness.anchor_refs
    uv run python -m harness.anchor_refs --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.questions import EN_EXCLUDED, eval_dir, vendor_questions  # noqa: E402

RUN = "paper-2026-04-22"        # the benchmark's published run the anchors are compared with
_DENORMALS = {"inf": math.inf, "-inf": -math.inf, "nan": math.nan}


def anchor_dir() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        raise RuntimeError("SEMDEBT_DATA_DIR is not set")
    return Path(root).expanduser() / "anchor-refs" / RUN


def restore_denormals(meta: list[dict], rows: list[list]) -> list[list]:
    floats = [i for i, c in enumerate(meta) if "Float" in c["type"]]
    for row in rows:
        for i in floats:
            if isinstance(row[i], str) and row[i] in _DENORMALS:
                row[i] = _DENORMALS[row[i]]
    return rows


def boundary_sql(sql: str) -> str:
    """The original query with its truncations made tie-inclusive, and nothing else changed."""
    sql = re.sub(r"\bLIMIT\s+(\d+)\b(?!\s+WITH\s+TIES)", r"LIMIT \1 WITH TIES", sql, flags=re.I)
    return re.sub(r"\brow_number\s*\(\s*\)", "rank()", sql, flags=re.I)


def load_anchor_ref(vendor_id: int, root: Path | None = None,
                    boundary: bool = False) -> tuple[list[dict], list[list]] | None:
    """The original reference (``boundary=False``) or its boundary-complete
    version (``boundary=True``; None when completing the ties adds no row)."""
    path = (root or anchor_dir()) / f"q{vendor_id:02d}{'.boundary' if boundary else ''}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["meta"], restore_denormals(payload["meta"], payload["rows"])


def anchor_manifest(root: Path | None = None) -> dict[int, dict]:
    path = (root or anchor_dir()) / "MANIFEST.json"
    if not path.exists():
        return {}
    return {r["vendor_id"]: r for r in json.loads(path.read_text(encoding="utf-8"))["records"]}


def _payload(meta: list[dict], rows: list[list]) -> bytes:
    return json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, separators=(",", ":")).encode()


def build(check: bool = False) -> int:
    from chdb import session

    out = anchor_dir()
    out.mkdir(parents=True, exist_ok=True)
    data = os.environ["SEMDEBT_DATA_DIR"]
    sess = session.Session(str(Path(data).expanduser() / "chdb"))
    records, failures = [], 0
    try:
        for statement in ("SET max_threads = 1", "SET max_execution_time = 0",
                          "SET output_format_json_quote_denormals = 1",
                          "SET output_format_json_quote_64bit_integers = 0", "SET output_format_json_quote_decimals = 0"):
            sess.query(statement)
        version = str(sess.query("SELECT version()", "TSV")).strip()
        for vq in vendor_questions(eval_dir()):
            vid = int(vq["id"])
            if vid in EN_EXCLUDED:
                continue
            sql = vq["expected_sql"].strip().rstrip(";")
            started = time.monotonic()
            payload = json.loads(str(sess.query(sql, "JSONCompact")))
            body = _payload(payload["meta"], payload["data"])
            record = {"vendor_id": vid, "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
                      "row_count": len(payload["data"]), "columns": payload["meta"],
                      "sha256": hashlib.sha256(body).hexdigest(),
                      "elapsed_s": round(time.monotonic() - started, 3), "boundary": None}
            files = {f"q{vid:02d}.json": body}
            tie_sql = boundary_sql(sql)
            if tie_sql != sql:
                tied = json.loads(str(sess.query(tie_sql, "JSONCompact")))
                if len(tied["data"]) != len(payload["data"]):
                    tied_body = _payload(tied["meta"], tied["data"])
                    files[f"q{vid:02d}.boundary.json"] = tied_body
                    record["boundary"] = {"sql_sha256": hashlib.sha256(tie_sql.encode()).hexdigest(),
                                          "row_count": len(tied["data"]),
                                          "sha256": hashlib.sha256(tied_body).hexdigest()}
            for name, data in files.items():
                path = out / name
                if check:
                    same = path.exists() and path.read_bytes() == data
                    failures += not same
                    print(f"{name} {'same' if same else 'DIFFERENT'}", flush=True)
                else:
                    path.write_bytes(data)
            if check and record["boundary"] is None and (out / f"q{vid:02d}.boundary.json").exists():
                failures += 1
                print(f"q{vid:02d}.boundary.json DIFFERENT (no longer adds rows)", flush=True)
            records.append(record)
    finally:
        sess.close()
    manifest = {"benchmark_run": RUN, "source": "vendor/cube/text_to_sql_benchmark.json expected_sql, unmodified",
                "engine": f"chdb {version}", "max_threads": 1, "max_execution_time": 0,
                "boundary": "qNN.boundary.json: LIMIT n WITH TIES / rank(), stored only when it adds rows",
                "excluded": sorted(EN_EXCLUDED), "records": records}
    if not check:
        (out / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {len(records)} anchor references to {out}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="re-execute and compare with the stored files")
    return build(check=ap.parse_args(argv).check)


if __name__ == "__main__":
    raise SystemExit(main())
