"""T12 all-wrong audit helper: for one question, print its rules, the reference's
first rows, and every pilot attempt's final verdict, columns and first rows (from
runs-raw). Read-only; no model call, no query execution.

    uv run python scripts/t12_audit_dump.py Q82 [--sql]
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json, os, warnings
warnings.filterwarnings("ignore")
from harness.questions import load_questions
qs = {q.qid: q for q in load_questions(lang="zh")}
RAW = Path(os.environ["SEMDEBT_DATA_DIR"]) / "runs-raw"
RUNS = {"flash": "20261018-T12-pilot-flash-01", "pro": "20261018-T12-pilot-pro-01"}
qid = sys.argv[1]; show_sql = "--sql" in sys.argv; nrows = 4
q = qs[qid]
print("RULES", json.dumps(q.rules, ensure_ascii=False))
if q.ref_rules: print("REF_RULES", json.dumps(q.ref_rules, ensure_ascii=False))
for i, ref in enumerate(q.refs or []):
    print(f"REF{i}: {len(ref)} rows; first {ref[:nrows]}")
for m, run in RUNS.items():
    for cell in ("SQL-R", "SQL-L1"):
        for line in open(Path(__file__).resolve().parent.parent / "runs" / run / f"{cell}.jsonl"):
            r = json.loads(line)
            if r["qid"] != qid: continue
            t = r["turns"][-1]; e = t["exec"]
            f = RAW / run / cell / f"{qid}_r{r['rep']}_t{t['turn']}.exec.json"
            rows = json.load(open(f))["rows"] if f.exists() and e.get("status") == "ok" else None
            cols = [c["name"] for c in e.get("columns", [])]
            print(f"--- {m} {cell} r{r['rep']} turns={len(r['turns'])} final={r['final']['outcome']}/{r['final']['reason']} first={r['first'] if isinstance(r['first'],str) else r['first']['outcome']} exec={e.get('status')} {e.get('error_class') or ''}")
            print(f"    cols={cols} rows={e.get('row_count')} {rows[:nrows] if rows else ''}")
            if t.get("assumption"): print("    assumption:", t["assumption"][:300])
            if show_sql: print("    SQL:", (t.get("query") or "")[:1500].replace("\n", " "))
