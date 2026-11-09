"""Offline independent D3 recomputation; retains only labels, IDs and arithmetic."""
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import yaml

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'runs/20261031-T31-v5-rulings-01'
EVAL=Path(os.environ['SEMDEBT_EVAL_DIR'])
INPUTS={}
def read(p):
 b=p.read_bytes();INPUTS[str(p.relative_to(ROOT))]=hashlib.sha256(b).hexdigest();return b
manifest=json.loads(read(RUN/'manifest.json'));rev=manifest['eval_commit']
labels={}
for name in ['questions/cube_100.yaml','questions/new.yaml']:
 b=subprocess.check_output(['git','-C',str(EVAL),'show',rev+':'+name])
 INPUTS['$SEMDEBT_EVAL_DIR@'+rev+'/'+name]=hashlib.sha256(b).hexdigest()
 for q in yaml.safe_load(b)['questions']:
  labels[q['id']]=dict(low=bool(q['labels']['low_discrimination']['criteria']),
    scoring=q['scoring'],dependency=q['labels']['semantic_dependency']['primary'])
moved={'Q03','Q10','Q30','Q47','Q51','Q58','Q72'}
bycell={}
for cell in ['SQL-L1','SQL-L1-E']:
 rr=[json.loads(x) for x in read(RUN/(cell+'.jsonl')).splitlines() if x.strip()]
 rr=[r for r in rr if not r['low']]
 assert len(rr)==294 and len({(r['qid'],r['rep']) for r in rr})==294
 counts=Counter();reps=defaultdict(set)
 for r in rr:
  assert not labels[r['qid']]['low'] and r['content_correct'] in (0,1)
  counts[r['qid']]+=r['content_correct'];reps[r['qid']].add(r['rep'])
 assert len(counts)==98 and all(len(r)==3 for r in reps.values())
 bycell[cell]=counts

def paired(ids):
 vals=[bycell['SQL-L1-E'][q]-bycell['SQL-L1'][q] for q in sorted(ids)];n=len(vals)
 rng=random.Random(20261109)
 boot=sorted(sum(rng.choices(vals,k=n))/(3*n)*100 for _ in range(10000))
 # Linear interpolation at percentile*(B-1).
 def pct(p):
  x=p*(len(boot)-1);i=int(x);return boot[i]+(boot[min(i+1,len(boot)-1)]-boot[i])*(x-i)
 # Exact discrete empirical bootstrap distribution of the integer sums.
 dist={0:1};freq=Counter(vals)
 for _ in vals:
  out=defaultdict(int)
  for total,ways in dist.items():
   for v,c in freq.items():out[total+v]+=ways*c
  dist=out
 def exact(num,den):
  accum=0
  for total,ways in sorted(dist.items()):
   accum+=ways
   if accum*den>=n**n*num:return total/(3*n)*100
  raise AssertionError('quantile not found')
 return dict(questions=n,attempts_per_cell=3*n,ids=sorted(ids),
  correct={c:sum(bycell[c][q] for q in ids) for c in bycell},
  delta_pp=sum(vals)/(3*n)*100,bootstrap_ci95_pp=[pct(.025),pct(.975)],
  exact_ci95_pp=[exact(1,40),exact(39,40)],difference_count_histogram=dict(Counter(vals)))
groups={}
for dep in ['可从数据发现','只能由业务告知']:
 ids={q for q,l in labels.items() if not l['low'] and l['scoring']=='deterministic' and
      ('只能由业务告知' if q in moved else l['dependency'])==dep}
 groups[dep]=paired(ids)
assert [v['questions'] for v in groups.values()]==[20,78]
result=dict(eval_commit=rev,groups=groups,bootstrap_replicates=10000,seed=20261109,
 input_sha256=INPUTS,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 model_api_calls=0,sql_executions=0)
out=ROOT/'reports/recheck/v103-independent.json'
with out.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(groups,ensure_ascii=False,indent=2))
