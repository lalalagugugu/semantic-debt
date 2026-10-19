"""L1.5S vs L1 on the summary-covered main-table questions (reports/results/l15s-covered-analysis.md).

Reads runs/20261018-T13-sql-direct-01-rescore-01 and the eval-v1.2 labels; no model call, no chDB.
    SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/l15s_covered_analysis.py out.json
"""
import json, sys
from collections import Counter
sys.path.insert(0, "scripts"); sys.path.insert(0, ".")
from sql_direct_report import records, coverage, error_group
from harness.questions import load_questions, verify_eval_tag
verify_eval_tag("eval-v1.2")
qs = {q.qid: q for q in load_questions()}
cov = coverage()
ids = sorted((q for q in qs if cov[q]=="covered" and qs[q].scoring!="judge" and not qs[q].meta["low_discrimination"]), key=lambda x:int(x[1:]))
RUN = "20261018-T13-sql-direct-01-rescore-01"
L1={(r["qid"],r["rep"]):r for r in records(RUN,"SQL-L1")}
S={(r["qid"],r["rep"]):r for r in records(RUN,"SQL-L1.5S")}
def code(r):
    f=r["final"]; o=f["outcome"]
    if o=="correct": return "C"
    if o=="wrong": return "W:"+str(f["reason"])
    if o=="exec_error":
        t=r["turns"][-1]; return "E:"+error_group(t["exec"], t["query"])[0]
    return o
out={"ids":ids,"rows":[]}
for q in ids:
    a=[L1[(q,i)] for i in (1,2,3)]; b=[S[(q,i)] for i in (1,2,3)]
    out["rows"].append({"q":q,"l1":sum(r["final"]["outcome"]=="correct" for r in a),"s":sum(r["final"]["outcome"]=="correct" for r in b),
      "l1c":[code(r) for r in a],"sc":[code(r) for r in b]})
json.dump(out,open(sys.argv[1],"w"),ensure_ascii=False)
print(len(ids))
tl1=sum(x["l1"] for x in out["rows"]); ts=sum(x["s"] for x in out["rows"]); n=3*len(ids)
print(tl1,ts,n, 100*(tl1-ts)/n)
print("better",sum(x["s"]>x["l1"] for x in out["rows"]),"worse",sum(x["s"]<x["l1"] for x in out["rows"]))
for x in out["rows"]: print(x["q"],x["l1"],x["s"],x["l1c"],x["sc"])
# part 2
sv=0;svq=set();first=Counter();rescued=Counter();
for q in ids:
  for i in (1,2,3):
    r=S[(q,i)]; t0=r["turns"][0]
    if any(t["exec"].get("error_class")=="scope_violation" for t in r["turns"] if t.get("exec")): sv+=1; svq.add(q)
    if t0.get("exec") and t0["exec"]["status"]=="error":
        g=error_group(t0["exec"],t0["query"])[0]; first[g]+=1
        if len(r["turns"])>1 and r["turns"][-1]["exec"] and r["turns"][-1]["exec"]["status"]=="ok": rescued[(g,"ran")]+=1
        if r["final"]["outcome"]=="correct": rescued[(g,"correct")]+=1
    elif not t0.get("exec"): first["noexec:"+str(t0.get("refused"))]+=1
print("scope",sv,sorted(svq))
print(first); print(rescued)
