"""Summarize existing paired CIs and compute explicitly conditional normal MDEs."""
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from statistics import NormalDist, median, stdev
ROOT=Path(__file__).resolve().parents[2]
inputs={}
def read(p):
 b=p.read_bytes();inputs[str(p.relative_to(ROOT))]=hashlib.sha256(b).hexdigest();return b.decode()
rr=list(csv.DictReader(read(ROOT/'reports/results/accuracy-v5-comparisons.csv').splitlines()))
rows=[]
for r in rr:
 assert r['scope']=='main98'
 lo=float(r['accuracy_lo'])*100;hi=float(r['accuracy_hi'])*100
 rows.append(dict(source='main',left=r['left'],right=r['right'],split=r['split'],questions=int(r['questions']),
  delta_pp=float(r['accuracy_delta'])*100,lo_pp=lo,hi_pp=hi,halfwidth_pp=(hi-lo)/2))
report=read(ROOT/'reports/results/l3a-full.md')
for line in report.splitlines():
 if ' minus ' not in line:continue
 cols=[x.strip() for x in line.split('|')]
 right,left=cols[1].split(' minus ')
 lo,hi=map(float,re.findall(r'[+-]?\d+\.\d+',cols[3]))
 rows.append(dict(source='ontology',left=left,right=right,split='all',questions=98,
   delta_pp=float(cols[2]),lo_pp=lo,hi_pp=hi,halfwidth_pp=(hi-lo)/2))
assert sum(r['source']=='ontology' for r in rows)==2
# Drift rows are historical/new comparisons, kept separate from within-batch treatment effects.
drift=[]
for line in report.splitlines():
 cols=[x.strip() for x in line.split('|')]
 if len(cols)==8 and cols[1] in ['SQL-L1','SQL-L1plus'] and '[' in cols[5]:
  lo,hi=map(float,re.findall(r'[+-]?\d+\.\d+',cols[5]))
  drift.append(dict(cell=cols[1],lo_pp=lo,hi_pp=hi,halfwidth_pp=(hi-lo)/2))
assert len(drift)==2

def summary(rr):
 vals=[r['halfwidth_pp'] for r in rr]
 return dict(n=len(rr),min_pp=min(vals),median_pp=median(vals),max_pp=max(vals),
   within_4_to_6=sum(4<=v<=6 for v in vals),within_4_to_6_fraction=sum(4<=v<=6 for v in vals)/len(vals),
   minimum_rows=[r for r in rr if r['halfwidth_pp']==min(vals)],
   maximum_rows=[r for r in rr if r['halfwidth_pp']==max(vals)])
sets={
 'main_all_rows':[r for r in rows if r['source']=='main'],
 'main_all98':[r for r in rows if r['source']=='main' and r['split']=='all' and r['questions']==98],
 'main_heldout49':[r for r in rows if r['source']=='main' and r['split']=='heldout'],
 'main_T4_all49':[r for r in rows if r['source']=='main' and r['split']=='all' and r['questions']==49],
 'ontology':[r for r in rows if r['source']=='ontology'],
 'combined_all98':[r for r in rows if r['split']=='all' and r['questions']==98]}
# Plug-in local normal power approximation uses per-question differences, not 294 independent questions.
z=NormalDist().inv_cdf(.975);zb=NormalDist().inv_cdf(.8)
main={}
for cell in {r[k] for r in rows if r['source']=='main' for k in ['left','right']}:
 q=defaultdict(list)
 for line in read(ROOT/'runs/20261031-T31-v5-rulings-01'/(cell+'.jsonl')).splitlines():
  r=json.loads(line)
  if not r['low']:q[r['qid']].append(r['content_correct'])
 main[cell]={k:sum(v)/len(v) for k,v in q.items()}
onto=defaultdict(lambda:defaultdict(list))
for line in read(ROOT/'runs/20261107-T34-final-01/codex-verdicts.jsonl').splitlines():
 r=json.loads(line);onto[r['cell']][r['qid']].append(r['content_correct'])
onto={c:{q:sum(v)/len(v) for q,v in qs.items()} for c,qs in onto.items()}
empirical=[]
for r in rows:
 if not(r['split']=='all' and r['questions']==98):continue
 cells=main if r['source']=='main' else onto
 a,b=cells[r['left']],cells[r['right']];ids=sorted(a.keys()&b.keys());assert len(ids)==98
 se=stdev([b[q]-a[q] for q in ids])/math.sqrt(len(ids))
 empirical.append(dict(source=r['source'],left=r['left'],right=r['right'],se_pp=se*100,
   mde80_pp=(z+zb)*se*100,normal_approx_power_for_5pp=NormalDist().cdf(.05/se-z)+NormalDist().cdf(-.05/se-z)))
independent=[]
for p in [.8,.85,.9]:
 for effective_repeats in [3,1]:
  se=math.sqrt(2*p*(1-p)/(98*effective_repeats))
  independent.append(dict(p=p,effective_repeats=effective_repeats,se_pp=se*100,
    ci95_halfwidth_pp=z*se*100,mde80_pp=(z+zb)*se*100))
scope_commit='9fe12ecdad1d61306200ca17404577b2d18e776f'
scope=subprocess.check_output(['git','show',scope_commit+':reports/midterm/v10-number-sources.md'],cwd=ROOT)
inputs[scope_commit+':reports/midterm/v10-number-sources.md']=hashlib.sha256(scope).hexdigest()
d3_source=read(ROOT/'reports/results/t19a-v7-numbers.md')
assert '|可从数据发现（去掉 7 道可疑题）|20|' in d3_source
assert '-1.7 [-6.7, +3.3]' in d3_source
independent_path=ROOT/'reports/recheck/v103-independent.json'
independent=json.loads(read(independent_path))
group=independent['groups']['可从数据发现']
assert group['correct']=={'SQL-L1':55,'SQL-L1-E':54}
assert abs(group['delta_pp']-(-1.7))<.1
assert all(abs(a-b)<.5 for a,b in zip(group['bootstrap_ci95_pp'],[-6.7,3.3]))
assert group['bootstrap_ci95_pp'][0]<0<group['bootstrap_ci95_pp'][1]
result=dict(scope_commit=scope_commit,scope_sha256=hashlib.sha256(scope).hexdigest(),d3_source_comparison='point within 0.1 pp; CI endpoints within 0.5 pp; contains zero agrees',summaries={k:summary(v) for k,v in sets.items()},ontology_drift=drift,
 method=dict(alpha_two_sided=.05,power=.8,z_975=z,z_80=zb,formula='MDE=(z_.975+z_.80)*sd(per-question paired mean difference)/sqrt(n)',
 caveat='Local normal approximation: fixes observed difference variance; not preregistered design power or a bootstrap power guarantee.'),
 empirical_mde=empirical,independent_bernoulli_scenarios=independent,input_sha256=inputs,
 model_api_calls=0,sql_executions=0)
with (ROOT/'reports/recheck/v103-paired-widths.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
(ROOT/'reports/recheck/v103-precision.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['input_sha256','empirical_mde']},ensure_ascii=False,indent=2))
print('EMPIRICAL_MDE_RANGE',min(r['mde80_pp'] for r in empirical),max(r['mde80_pp'] for r in empirical))
print('ONTOLOGY_MDE',[r for r in empirical if r['source']=='ontology'])
