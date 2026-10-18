"""T12 diagnostic only (not a score): would `missing_columns` answers match if the
reference columns the candidate did not return were optional? Projects each
reference (and its column-indexed rules) onto subsets of its columns and calls the
unchanged scorer; reports the largest matching subset. Skips multi-reference,
selection and Top-N questions. An upper bound: a match after dropping several
columns, or only labels, needs a human look.

    uv run python scripts/t12_column_diagnostic.py
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json, os, glob, itertools, collections, warnings
warnings.filterwarnings("ignore")
from harness.questions import load_questions
from harness.scorer import score_detailed
qs = {q.qid: q for q in load_questions()}
D = os.environ['SEMDEBT_DATA_DIR'] + '/runs-raw/'

def project(rules, S):
    r = dict(rules); idx = {c: i for i, c in enumerate(S)}
    for k in ("value_kinds", "value_types"):
        if r.get(k): r[k] = [r[k][c] for c in S]
    if r.get("tie_columns"):
        if not all(c in idx for c in r["tie_columns"]): return None
        r["tie_columns"] = [idx[c] for c in r["tie_columns"]]
    if r.get("order_by"):
        if not all(c in idx for c, _ in r["order_by"]): return None
        r["order_by"] = [[idx[c], d] for c, d in r["order_by"]]
    return r

out = collections.defaultdict(list)
for m in ('flash', 'pro'):
    for cell in ('SQL-R', 'SQL-L1'):
        for l in open(f'runs/20261018-T12-pilot-{m}-01/{cell}.jsonl'):
            rec = json.loads(l)
            if rec['final']['outcome'] != 'wrong' or rec['final']['reason'] != 'missing_columns': continue
            q = qs[rec['qid']]
            if q.ref_rules or q.rules.get('selection') or q.rules.get('top_n') is not None or len(q.refs) > 1:
                out[(m, cell)].append((rec['qid'], rec['rep'], 'skipped (multi-ref/selection/top_n)')); continue
            t = len(rec['turns']) - 1
            e = json.load(open(D + f"{rec['run_id']}/{cell}/{rec['qid']}_r{rec['rep']}_t{t}.exec.json"))
            ncand, ref = len(e['columns']), q.refs[0]; nref = len(ref[0]) if ref else 0
            best = None
            for k in range(min(ncand, nref), 0, -1):
                for S in itertools.combinations(range(nref), k):
                    pr = project(q.rules, S)
                    if pr is None: continue
                    if score_detailed(e['rows'], [[[row[c] for c in S] for row in ref]], pr).outcome == 'correct':
                        best = S; break
                if best: break
            dropped = None if best is None else [c for c in range(nref) if c not in best]
            out[(m, cell)].append((rec['qid'], rec['rep'], f"cand {ncand} cols / ref {nref}; " +
                                   ("no subset matches" if best is None else f"matches after dropping ref cols {dropped} "
                                    f"({[q.rules['value_kinds'][c] for c in dropped]})")))
for k, v in out.items():
    print(k); [print('  ', *x) for x in v]
