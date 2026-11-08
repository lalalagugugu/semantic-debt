"""Independent T20 v10 arithmetic from labels and raw API usage; no model or SQL calls."""
from collections import Counter, defaultdict
from fractions import Fraction
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ["SEMDEBT_DATA_DIR"])
INPUTS = {}

def read(path):
    raw = path.read_bytes()
    key = "$SEMDEBT_DATA_DIR/" + str(path.relative_to(DATA)) if path.is_relative_to(DATA) else str(path.relative_to(ROOT))
    INPUTS[key] = hashlib.sha256(raw).hexdigest()
    return raw

def rows(path):
    return [json.loads(x) for x in read(path).splitlines() if x.strip()]

def interval(values):
    # Integer numerator is the difference between counts of three correct attempts.
    n = len(values)
    rng = random.Random(20261108)
    boot = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / (3*n) * 100 for _ in range(5000))
    counts = Counter(values)
    dist = {0: 1}
    for _ in range(n):
        nxt = defaultdict(int)
        for total, ways in dist.items():
            for value, count in counts.items():
                nxt[total+value] += ways*count
        dist = nxt
    den = n**n
    def quantile(num, denominator):
        cumulative = 0
        for total, ways in sorted(dist.items()):
            cumulative += ways
            if cumulative*denominator >= den*num:
                return total/(3*n)*100
        raise ValueError("invalid quantile")
    return dict(n=n, delta_pp=sum(values)/(3*n)*100,
                independent_bootstrap_95_pp=[boot[125],boot[4874]], seed=20261108,
                exact_bootstrap_95_pp=[quantile(1,40),quantile(39,40)],
                contains_zero=boot[125] <= 0 <= boot[4874])

base_dir = ROOT/"runs/20261031-T31-v5-rulings-01"
base = {}
for path in sorted(base_dir.glob("*.jsonl")):
    rr = [r for r in rows(path) if not r["low"]]
    assert len({(r["qid"],r["rep"]) for r in rr}) == len(rr)
    base[path.stem] = rr
main_ids = {r["qid"] for r in base["SQL-L1"]}
assert len(main_ids) == 98
final = rows(ROOT/"runs/20261107-T34-final-01/codex-verdicts.jsonl")
assert len(final) == 1176 and all(r["final"] is True for r in final)
by_cell = defaultdict(list)
for r in final:
    by_cell[r["cell"]].append(r)
result = dict(method="independent implementation; labels fixed; no result-script imports",
              collection_run="20261104-T34-ontology-full-01", model_api_calls=0, sql_executions=0,
              cells={}, pairs={}, drift={}, main={}, display_gaps={})
for cell in ["SQL-L1","SQL-L1-onto","SQL-L1plus","SQL-L3a-full"]:
    rr = by_cell[cell]
    assert len(rr) == 294 and {r["qid"] for r in rr} == main_ids
    q = defaultdict(list)
    for r in rr:q[r["qid"]].append(int(r["content_correct"]))
    assert all(len(v)==3 for v in q.values())
    native = rows(ROOT/"runs"/result["collection_run"]/(cell+".jsonl"))
    ni = {(r["qid"],r["rep"]):r for r in native if r["status"]=="done"}
    assert len(ni)==327
    first_input = 0
    for r in rr:
        rec = ni[r["qid"],r["rep"]]
        t = rec["turns"][0]
        path = DATA/"runs-raw"/result["collection_run"]/cell/f"{r['qid']}_r{r['rep']}_t{t['turn']}.json"
        raw = read(path)
        assert hashlib.sha256(raw).hexdigest()==t["raw_sha256"]
        response = json.loads(raw)
        assert response["system_fingerprint"]=="bc19ba97cbe016479903222bb1578db6"
        assert response["usage"]["prompt_tokens"]==t["usage"]["prompt_tokens"]
        first_input += response["usage"]["prompt_tokens"]
    correct = sum(int(r["content_correct"]) for r in rr)
    causes = Counter(r["wrong_cause"] for r in rr if not r["content_correct"])
    assert sum(causes.values())==len(rr)-correct
    result["cells"][cell] = dict(questions=len(q), attempts=len(rr), correct=correct,
            accuracy_pct=100*correct/len(rr),
            stability=dict(all_correct=sum(sum(v)==3 for v in q.values()),
                           all_wrong=sum(sum(v)==0 for v in q.values()),
                           mixed=sum(0<sum(v)<3 for v in q.values())),
            first_input_total=first_input,first_input_mean=first_input/len(rr),
            causes=dict(causes), by_question_correct={k:sum(v) for k,v in sorted(q.items())})
for text,onto in [("SQL-L1","SQL-L1-onto"),("SQL-L1plus","SQL-L3a-full")]:
    a=result["cells"][text];b=result["cells"][onto]
    result["pairs"][onto+" minus "+text]=interval([b["by_question_correct"][k]-a["by_question_correct"][k] for k in sorted(main_ids)])
    result["pairs"][onto+" minus "+text]["first_input_ratio"]=b["first_input_mean"]/a["first_input_mean"]
for cell in ["SQL-L1","SQL-L1plus"]:
    old=Counter()
    for r in base[cell]:old[r["qid"]]+=int(r["content_correct"])
    new=result["cells"][cell]["by_question_correct"]
    assert set(new)==set(old)
    result["drift"][cell]=interval([new[k]-old[k] for k in sorted(main_ids)])
for cell,rr in base.items():
    result["main"][cell]=dict(attempts=len(rr),correct=sum(int(r["content_correct"]) for r in rr),
            delivery=sum(r["a"] for r in rr), census=sum(bool(r["census_reviewed"]) for r in rr))
    if cell in ["SQL-L0","SQL-R","SQL-L1c","SQL-L1","SQL-L1plus","SQL-L1-tuned","SQL-L1-tuned-instr","SQL-L1plus-tuned-instr"]:
        result["display_gaps"][cell]={}
        for scope in ["all","heldout"]:
            selected=[r for r in rr if scope=="all" or r["split"]=="heldout"]
            result["display_gaps"][cell][scope]=dict(n=len(selected),content=sum(int(r["content_correct"]) for r in selected),
                    delivery=sum(r["a"] for r in selected),gap_pp=100*sum(int(r["content_correct"])-r["a"] for r in selected)/len(selected))
u2=list(csv.DictReader(read(ROOT/"reports/validation/t29-u2-content-labels.csv").decode().splitlines()))
assert len({(r["cell"],r["qid"],r["rep"]) for r in u2})==len(u2)
u2counts=Counter(r["cell"] for r in u2)
assert len(u2counts)==6 and set(u2counts.values())=={294}
main_attempts=sum(len(v) for v in base.values())
result["scale"]=dict(main_cells=len(base),main_attempts=main_attempts,u2=dict(u2counts),
        new_cells=len(by_cell),new_attempts=len(final),
        cells=len(base)+len(u2counts)+len(by_cell),attempts=main_attempts+len(u2)+len(final))
result["census"]=dict(numerator=sum(v["census"] for v in result["main"].values()),denominator=main_attempts)
result["census"]["pct"]=100*result["census"]["numerator"]/main_attempts
result["input_sha256"]=INPUTS
result["script_sha256"]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
result["base_commit"]=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
out=ROOT/"reports/recheck/v10-independent.json"
with out.open("x") as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write("\n")
print(json.dumps({k:v for k,v in result.items() if k not in ["input_sha256","main","display_gaps"]},ensure_ascii=False))
print("DISPLAY_GAPS",json.dumps(result["display_gaps"],ensure_ascii=False))
print("MAIN_COUNTS",json.dumps({k:v["attempts"] for k,v in result["main"].items()}))
