"""Audit T29 pilot refusals, format, hashes and cost without reporting accuracy.

    uv run --offline python scripts/t29_pilot_report.py

Requires the original frozen runtime checkout and SEMDEBT_DATA_DIR. The source
logs and raw responses are read only; output contains ids and counts only.
"""
import csv, hashlib, json, os, sys
from decimal import Decimal
from pathlib import Path

root=Path(os.environ['SEMDEBT_DATA_DIR'])
card=Path(__file__).resolve().parents[1]
run_id='20261025-T29-pilot-01'
work=root/'t29-pilot-sel-v1'
sys.path.insert(0,str(work))
from harness import prompt as P
from harness.executors import mask_sql,strip_trailing_semicolons
from harness.cells import PRICES_OFFPEAK
raw=root/'runs-raw'/run_id
pre=json.loads((raw/'approved-preflight.json').read_text())
for name,expected in pre['source_sha256'].items():
 assert hashlib.sha256((work/name).read_bytes()).hexdigest()==expected,name
records=[]
for name in ('SQL-L1plus-sel-k1','SQL-L1plus-sel-k3'):
 p=work/'runs'/run_id/(name+'.jsonl')
 if p.exists(): records += [json.loads(s) for s in p.read_text().splitlines() if s]
assert len(records)==40 and all(r['status']=='done' for r in records),'pilot incomplete or abnormal'
assert len({(r['cell'],r['qid'],r['rep']) for r in records})==40
ledger=[json.loads(s) for s in (raw/'spend-ledger.jsonl').read_text().splitlines()]
assert len(ledger)%2==0
for i in range(0,len(ledger),2): assert ledger[i]['event']=='request' and ledger[i+1]['event']=='charge'
charge_by_key={tuple(a[k] for k in ('cell','qid','rep','turn')):b for a,b in zip(ledger[::2],ledger[1::2])}
assert len(charge_by_key)==len(ledger)//2
price=PRICES_OFFPEAK['deepseek-flash']
calls=[]
rows=[]

def format_error(content):
 if content.strip()==P.REFUSAL: return False
 parsed=P.parse_response(content)
 return not(parsed.query and parsed.n_code_blocks==1) or ';' in mask_sql(strip_trailing_semicolons(parsed.query or ''))

for r in records:
 assert r['qid'] in pre['pilot_qids'] and r['rep']==1
 assert r['system_sha256']==pre['system_sha256'][r['cell']]
 assert r['semantic_tag']=='semantic-v1.6-l1plus' and r['eval_tag']=='eval-v1.2'
 assert r['harness_commit']=='903c767-dirty' and r['eval_commit']=='90e13b3'
 assert not r['peak']
 turn_errors=[]
 cost=Decimal(0)
 for t in r['turns']:
  p=raw/r['cell']/f"{r['qid']}_r1_t{t['turn']}.json"
  b=p.read_bytes()
  assert hashlib.sha256(b).hexdigest()==t['raw_sha256']
  payload=json.loads(b)
  assert payload['system_fingerprint']=='e72d3c7f663d3e1383b00b3884cb4501'
  assert t['transport_retries']==0
  u=t['usage']
  ru=payload['usage']
  assert u['prompt_tokens']==ru['prompt_tokens'] and u['completion_tokens']==ru['completion_tokens']
  assert u['cache_hit_tokens']==ru['prompt_cache_hit_tokens'] and u['cache_miss_tokens']==ru['prompt_cache_miss_tokens']
  amount=(Decimal(u['cache_hit_tokens'])*Decimal(str(price['hit']))+Decimal(u['cache_miss_tokens'])*Decimal(str(price['miss']))+Decimal(u['completion_tokens'])*Decimal(str(price['output'])))/Decimal(1000000)
  key=(r['cell'],r['qid'],r['rep'],t['turn'])
  assert abs(amount-Decimal(charge_by_key[key]['cost_cny']))<Decimal('0.000000000001')
  cost+=amount
  content=payload['choices'][0]['message'].get('content') or ''
  turn_errors.append(format_error(content))
  calls.append({'cell':r['cell'],'qid':r['qid'],'turn':t['turn'],'cost':amount,'format_error':turn_errors[-1]})
 final_text=payload['choices'][0]['message'].get('content') or ''
 refused=r['final']['outcome']=='refused'
 assert refused==(final_text.strip()==P.REFUSAL),'refusal parser/protocol discrepancy'
 assert abs(cost-Decimal(str(r['cost_cny'])))<Decimal('0.000000000001')
 rows.append({'cell':r['cell'],'qid':r['qid'],'rep':1,'refused':int(refused),'final_format_error':int(turn_errors[-1]),'calls':len(r['turns']),'format_error_calls':sum(turn_errors),'cost_cny':str(cost)})
assert len(calls)==len(charge_by_key)
report={'run_id':run_id,'harness_tag':'harness-sel-v1','harness_commit':pre['harness_commit'],'source_preflight_sha256':hashlib.sha256((raw/'approved-preflight.json').read_bytes()).hexdigest(),'cells':[]}
report['logged_harness_commit']='903c767-dirty'
report['dirty_reason']='The runtime intentionally restores semantic/ and render/ from semantic-v1.6-l1plus; harness source hashes exactly match the tagged commit.'
for name in ('SQL-L1plus-sel-k1','SQL-L1plus-sel-k3'):
 selected=[r for r in rows if r['cell']==name]
 assert len(selected)==20 and {r['qid'] for r in selected}==set(pre['pilot_qids'])
 report['cells'].append({'cell':name,'attempts':len(selected),'refusals':sum(r['refused'] for r in selected),'final_format_errors':sum(r['final_format_error'] for r in selected),'format_error_calls':sum(r['format_error_calls'] for r in selected),'calls':sum(r['calls'] for r in selected),'cost_cny':str(sum((Decimal(r['cost_cny']) for r in selected),Decimal(0)))})
report['total_cost_cny']=str(sum((Decimal(r['cost_cny']) for r in rows),Decimal(0)))
report['ledger_cost_cny']=str(sum((Decimal(r['cost_cny']) for r in ledger if r['event']=='charge'),Decimal(0)))
report['total_calls']=len(calls)
report['format_error_qids']=[{'cell':r['cell'],'qid':r['qid']} for r in rows if r['final_format_error']]
report['estimated_cost_cny']=pre['total_cost_offpeak_cny']
report['integrity']='40 unique done attempts; frozen hashes/version checked; every raw response hash, fingerprint and usage checked; cost independently recalculated from usage and reconciled with ledger and logs; no transport retries.'
report['logs_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (work/'runs'/run_id).glob('*.jsonl')}
assert Decimal(report['total_cost_cny'])<1
out=card/'reports/validation'
(out/'t29-pilot-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
with (out/'t29-pilot-attempts.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(report,ensure_ascii=False,indent=2))
