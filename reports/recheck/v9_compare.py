"""Compare saved v9 independent facts with the changed-item source list."""
import csv
import hashlib
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'reports/recheck'
x = json.loads((OUT/'v9-independent.json').read_text())
source = ROOT/'reports/results/t19a-v8-numbers.md'
text = source.read_text()
checks = []


def check(item, ref, actual, kind='point', tol=.001, integer_percent=False):
    delta = actual-ref
    status = 'OK' if abs(delta)<=tol+1e-10 else 'DIFF'
    if status=='DIFF' and integer_percent and round(actual*100)==round(ref*100):
        status = 'ROUNDING'
    checks.append({'item':item,'kind':kind,'reference':ref,'independent':actual,
                   'difference':delta,'status':status})


def count(item,ref,actual):
    check(item,ref,actual,'count',0)


def ci(item,ref,actual):
    for end,a,b in zip(['lower','upper'],ref,actual):
        check(item+' '+end,a,b,'interval',.005)
    includes = lambda z:z[0]<=1e-12 and z[1]>=-1e-12
    check(item+' contains zero',int(includes(ref)),int(includes(actual)),'zero',0)


def nums(s):
    return [float(n) for n in re.findall(r'[+-]?\d+(?:\.\d+)?',s.replace(',',''))]


# Newly appended v9 footer, read only after the independent JSON was saved.
line = next(l for l in text.splitlines() if l.startswith('L1 未得分'))
values = nums(line)
count('v8num footer L1 errors',values[1],x['errors']['SQL-L1']['errors'])  # L1 contributes the leading 1.
count('v8num footer L1 with result',values[2],x['errors']['SQL-L1']['with_result'])
line = next(l for l in text.splitlines() if l.startswith('主表作答'))
v = nums(line)
count('v8num footer main attempts',v[0],x['residual']['denominator'])
count('v8num footer manual residuals',v[1],x['residual']['reviewed'])
check('v8num footer residual percent',v[2]/100,x['residual']['fraction'])
check('v9 residual 26%',.26,x['residual']['fraction'],integer_percent=True)
for cell,ref in [('SQL-L0-E',.44),('SQL-L1-E',.13)]:
    check('v9 data/enums '+cell,ref,x['data_and_enum'][cell]['fraction'],integer_percent=True)
for cell,ref in [('SQL-L1plus',75258),('SQL-L3a',219864)]:
    check('v8num first prompt '+cell,ref,x['first_prompt'][cell],'token',.5)

metrics = {(r['cell'],r['split']):r for r in x['metrics']}
check('v9 title L1+ 93%',.93,metrics['SQL-L1plus','all']['accuracy'],integer_percent=True)
check('v9 title L1+ detailed 93.2%',.932,metrics['SQL-L1plus','all']['accuracy'])
check('v9 title minimum below 40%',1,int(metrics['SQL-L1.5S','all']['accuracy']<.40),'predicate',0)
check('v9 heldout tuned 92.5%',.925,metrics['SQL-L1-tuned','heldout']['accuracy'])
for cell,ref in [('SQL-L1plus',.932),('SQL-L1-tuned',.925),('SQL-L1-tuned-instr',.932)]:
    check('v9 section9 '+cell,ref,metrics[cell,'heldout']['accuracy'])
for label,group,ref in [('full first','all',.850),('full second','all',.850),('summary','summary',.929),('json','json',.919)]:
    check('v9 same questions L1 '+label,ref,x['same_questions_L1'][group]['accuracy'])
for cell,ref,interval in [('SQL-L1.5S',-.079,[-.190,.032]),('JSON-L2',-.045,[-.126,.027])]:
    p=x['covered_comparisons'][cell]
    check('v9 covered '+cell,ref,p['delta'])
    ci('v9 covered '+cell,interval,p['interval'])
for group,ref in [('business',.432),('discoverable',.133)]:
    check('v9 D3 '+group,ref,x['d3'][group]['L0_L1']['delta'])
check('v9 D3 agent 20 questions',-.017,x['d3']['discoverable']['L0_L0E']['delta'])
count('v9 D3 business questions',78,x['d3']['business']['questions'])
count('v9 D3 discoverable questions',20,x['d3']['discoverable']['questions'])

cases=x['three_sql_cases']
count('v9 SQL cases',3,len(cases))
count('v9 SQL repair still failing',2,sum(r['execution_statuses']==['error','error'] and r['final']=='exec_error' for r in cases))
count('v9 SQL executable mechanism error',1,sum(r['has_result'] and r['final']=='wrong' for r in cases))
assert {(r['qid'],r['rep']) for r in cases if not r['has_result']}=={('Q24',2),('Q113',2)}
assert {(r['qid'],r['rep']) for r in cases if r['has_result']}=={('Q05',2)}
count('v9 L1 errors',44,x['errors']['SQL-L1']['errors'])
count('v9 L1 with result',42,x['errors']['SQL-L1']['with_result'])
count('v9 tuned errors',12,x['errors']['SQL-L1-tuned']['errors'])
count('v9 tuned with result',12,x['errors']['SQL-L1-tuned']['with_result'])
d=x['d4']
for label,ref,actual in [('questions',98,d['questions']),('selected',89,d['selected']),('blocked',9,d['blocked']),
    ('blocked wrong',3,len(d['blocked_wrong'])),('blocked correct',6,len(d['blocked_correct'])),
    ('remaining wrong questions',3,len(d['remaining_wrong'])),
    ('remaining wrong all three',3,sum(r['scores']==[0,0,0] for r in d['remaining_wrong']))]:
    count('v9 D4 '+label,ref,actual)
assert set(d['blocked_wrong'])=={'Q05','Q73','Q82'}
assert set(d['blocked_correct'])=={'Q112','Q122','Q18','Q26','Q64','Q98'}
for cell,ref in [('SQL-L0-u2',.481),('SQL-L0-u2p',.652),('SQL-L1-u2',.820),('SQL-L1-u2p',.860)]:
    check('v9 U2 answered '+cell,ref,x['u2'][cell]['answered_accuracy'])
for base,ref in [('SQL-L0',.303),('SQL-L1',.054)]:
    a,b=x['u2'][base+'-u2'],x['u2'][base+'-u2p']
    check('v9 U2 refusal difference '+base,ref,(b['refused']-a['refused'])/294)
u=x['u2']['SQL-L1-u2'];g=x['u2']['L1_gate90']
count('v9 U2 L1 answered',294,u['attempts']-u['refused'])
check('v9 U2 L1 accuracy',.820,u['accuracy'])
count('v9 U2 >=90 answered',157,g['answered'])
check('v9 U2 >=90 coverage',.534,g['coverage'])
check('v9 U2 >=90 accuracy',.873,g['accuracy'])

for k,ref in [('source',40),('retained',28),('removed',12),('removed_examples',9)]:
    count('v9 combo '+k,ref,x['combo_filter'][k])
assert x['combo_filter']['retained_raw_nodes_identical']
a=x['l3a_scope']
count('v9 overlay entries',109,sum(a['overlay_counts'].values()))
count('v9 formal',30,a['modes']['形式化'])
count('v9 annotation',79,a['modes']['注解保留'])
count('v9 formalizable',16,a['formalizable_annotations'])
count('v9 total formalizable',46,a['modes']['形式化']+a['formalizable_annotations'])
assert a['same_base'] and a['base_equals_L1_render']
assert all(not r['content_correct'] and r['note_mentions_order'] for r in x['Q58']) and x['Q58_reference_max_sales_row']

buf=io.StringIO()
writer=csv.DictWriter(buf,fieldnames=list(checks[0]),lineterminator='\n')
writer.writeheader();writer.writerows(checks)
(OUT/'v9-comparisons.csv').write_text(buf.getvalue())
summary={'independent_sha256':hashlib.sha256((OUT/'v9-independent.json').read_bytes()).hexdigest(),
    'reference_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'checks':len(checks),
    'differences':[r for r in checks if r['status']=='DIFF'],
    'integer_rounding_over_point_threshold':[r for r in checks if r['status']=='ROUNDING']}
(OUT/'v9-comparison-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
