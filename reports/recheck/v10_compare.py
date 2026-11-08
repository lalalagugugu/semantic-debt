"""Compare persisted independent v10 results with the supplied displayed claims."""
import csv
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=ROOT/'reports/recheck/v10-independent.json'
d=json.loads(p.read_text()); rows=[]
def check(name,actual,claimed,tolerance=0.1):
    rows.append(dict(item=name,independent=actual,claim=claimed,difference=actual-claimed,
                     tolerance=tolerance,within_tolerance=abs(actual-claimed)<=tolerance+1e-9))
cells=['SQL-L1','SQL-L1-onto','SQL-L1plus','SQL-L3a-full']
for c,n,a,t,s,causes in zip(cells,[234,235,269,275],[79.6,79.9,91.5,93.5],
 [46495.69,62629.69,75257.69,107079.69],[(65,9,24),(69,9,20),(82,2,14),(82,0,16)],[(28,30,2),(27,26,6),(16,3,6),(14,3,2)]):
 r=d['cells'][c]
 for key,claim,tol in [('correct',n,0),('accuracy_pct',a,.1),('first_input_mean',t,.01)]:check(c+'/'+key,r[key],claim,tol)
 for key,v in zip(['all_correct','all_wrong','mixed'],s):check(c+'/stability/'+key,r['stability'][key],v,0)
 for key,v in zip(['怎么算','是什么/属于谁','SQL'],causes):check(c+'/cause/'+key,r['causes'][key],v,0)
 check(c+'/wrong_total',sum(r['causes'].values()),294-n,0)
intervals=[]
for kind,k,point,lo,hi in [('pairs','SQL-L1-onto minus SQL-L1',.34,-3.74,4.76),('pairs','SQL-L3a-full minus SQL-L1plus',2.04,-1.70,5.78),('drift','SQL-L1',-5.44,-9.86,-1.36),('drift','SQL-L1plus',-1.70,-5.78,2.72)]:
 r=d[kind][k];check(k+'/delta_pp',r['delta_pp'],point)
 for j,v in enumerate([lo,hi]):check(k+'/CI/'+str(j),r['independent_bootstrap_95_pp'][j],v,.5)
 assert r['contains_zero']==(lo<=0<=hi)
 intervals.append(dict(comparison=k,contains_zero=r['contains_zero'],source_contains_zero=lo<=0<=hi))
for k,v in zip(d['pairs'],[1.35,1.42]):check(k+'/token_ratio',d['pairs'][k]['first_input_ratio'],v,.01)
for k,v in zip(['SQL-L0','SQL-R','SQL-L1c','SQL-L1','SQL-L1plus','SQL-L1-tuned','SQL-L1-tuned-instr','SQL-L1plus-tuned-instr'],[8.5,8.5,11.9,16.3,17.3,9.5,4.1,6.1]):check(k+'/delivery_gap',d['display_gaps'][k]['all']['gap_pp'],v)
for k,v in [('cells',29),('attempts',8379),('main_cells',19),('main_attempts',5439),('new_cells',4),('new_attempts',1176)]:check('scale/'+k,d['scale'][k],v,0)
check('census/numerator',d['census']['numerator'],1411,0)
for cell,title in [('SQL-L0',48),('SQL-L1plus',93)]:check('title/'+cell,100*d['main'][cell]['correct']/d['main'][cell]['attempts'],title)
check('gap_integer_upper',max(r['all']['gap_pp'] for r in d['display_gaps'].values()),17)
# Cross-check the published CSV only after independent arithmetic was persisted.
with (ROOT/'reports/results/accuracy-v5-cells.csv').open() as f:
 published=[r for r in csv.DictReader(f) if r['scope']=='main98' and r['dimension']=='all' and r['group']=='all']
assert len(published)==19
for r in published:
 own=d['main'][r['cell']]
 for pub,key in [('attempts','attempts'),('content_correct','correct'),('v2_correct','delivery')]:check('published/'+r['cell']+'/'+pub,own[key],int(r[pub]),0)
with (ROOT/'reports/recheck/v10-comparison.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
out=dict(checks=len(rows),outside_tolerance=[r for r in rows if not r['within_tolerance']],interval_zero_checks=intervals,
 independent_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),model_api_calls=0)
(ROOT/'reports/recheck/v10-comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
