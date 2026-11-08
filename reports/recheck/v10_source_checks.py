"""Source-only checks for T20 v10; fixed tier labels are recounted, not reclassified."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from render import l3a_full as L

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lines(p,needle):return [i for i,s in enumerate(p.read_text().splitlines(),1) if needle in s]
corr=ROOT/"reports/validation/l3a-full-correspondence.md"
parsed=[]
for line in corr.read_text().splitlines():
 cols=[x.strip() for x in line.split("|")]
 if len(cols)>5 and re.fullmatch(r"[ADEHG]\d{2}[bc]?",cols[2] or "") and cols[1] in ["clarifications","concepts","general_rules","aliases","hierarchies"]:
  parsed.append((cols[2],cols[3],cols[4]))
assert len(parsed)==109 and len({r[0] for r in parsed})==109
node=next(n for n in ast.parse((ROOT/"render/l3a_full.py").read_text()).body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=="TIERS")
tiers={ast.literal_eval(k):(ast.literal_eval(v.elts[0]),ast.literal_eval(v.elts[1])) for k,v in zip(node.value.keys,node.value.values)}
table_tiers={i:(o,n) for i,o,n in parsed}
assert all(table_tiers[i]==value for i,value in tiers.items())
# E/H tiers are added after the initial declarative dictionary.
assert table_tiers=={i:value[:2] for i,value in L.TIERS.items()}
ctx=L.l1_context();turtle=L.turtle(ctx,None);graph=L.Parsed(turtle)
metrics=graph.typed(":Metric");conventions=graph.typed(":Convention")
assert len(metrics)==69 and len(conventions)==15
assert all(graph.all(s,":definition") for s in metrics)
assert all(graph.all(s,":rule") for s in conventions)
assert L.VOCAB["definition"][0]==L.VOCAB["rule"][0]=="ann"
predicates={kind:dict(Counter(p for s in nodes for p,o in graph.props[s])) for kind,nodes in [("metrics",metrics),("conventions",conventions)]}
code=(ROOT/"harness/run_direct.py").read_text()
assert not any(re.search(r"^(?:from|import) "+name,code,re.M) for name in ["owlrl","pyshacl","rdflib"])
t08=ROOT/"tasks/T08-blind-semantic-layer.md";t22=ROOT/"tasks/T22-l1plus-l3a.md"
assert "- 工时：\n" in t22.read_text()
assert "写 L1 约 3 小时" in t08.read_text() and "6.4 小时" in t08.read_text()
source_scope=subprocess.check_output(["git","show","a499d80d89e80b5ade11483b401088d761eff399:reports/midterm/v10-number-sources.md"],cwd=ROOT)
result=dict(tiers=dict(Counter(r[2] for r in parsed)),old_tiers=dict(Counter(r[1] for r in parsed)),
 tier_ids={k:[r[0] for r in parsed if r[2]==k] for k in ["1S","1C","2","3"]},
 l1=dict(conventions=len(conventions),metrics=len(metrics),core_rule_literal_annotation=True,
         metric_definition_literal_annotation=True,predicate_counts=predicates),
 task_t08=dict(line=lines(t08,"- 工时："),l1_hours_recorded=3,total_hours_recorded=6.4,
               type="agent session time, not human person-hours",source_only=True),
 task_t22=dict(hours_field_lines=lines(t22,"- 工时："),hours_field_empty=True,
               no_separate_review_or_human_cost_record=True,source_only=True),
 validation_t26=dict(source_only=True,not_reexecuted=True),
 no_runtime_reasoner_imports=True,
 scope_commit=subprocess.check_output(["git","rev-parse","a499d80d89e80b5ade11483b401088d761eff399"],cwd=ROOT,text=True).strip(),
 scope_sha256=hashlib.sha256(source_scope).hexdigest(),
 inputs={str(p.relative_to(ROOT)):digest(p) for p in [corr,t08,t22,ROOT/"render/l3a_full.py",ROOT/"harness/run_direct.py",ROOT/"reports/validation/t34-codex-review.md",ROOT/"reports/validation/l3a-ontology-validation.md"]},
 model_api_calls=0,sql_executions=0)
(ROOT/"reports/recheck/v10-source-checks.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({k:v for k,v in result.items() if k not in ["tier_ids","inputs"]},ensure_ascii=False))
