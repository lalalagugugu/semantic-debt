"""T20 v9 changed-item audit. Offline, read-only, no report-calculator imports."""
import csv
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ['SEMDEBT_DATA_DIR']).resolve()
EVAL = Path(os.environ['SEMDEBT_EVAL_DIR']).resolve()
RUN = ROOT / 'runs/20261031-T31-v5-rulings-01'
OUT = ROOT / 'reports/recheck'
HASHES = {}


def read(path):
    raw = path.read_bytes()
    name = '$SEMDEBT_DATA_DIR/' + str(path.relative_to(DATA)) if path.is_relative_to(DATA) else str(path.relative_to(ROOT))
    HASHES[name] = hashlib.sha256(raw).hexdigest()
    return raw.decode()


def records(path):
    return [json.loads(s) for s in read(path).splitlines() if s.strip()]


def exact_ci(values):
    n = len(values)
    frequencies = Counter(round(3*v) for v in values)
    assert all(abs(3*v-round(3*v)) < 1e-10 for v in values)
    dist = {0: 1.0}
    for _ in values:
        nxt = defaultdict(float)
        for a, p in dist.items():
            for b, k in frequencies.items():
                nxt[a+b] += p*k/n
        dist = nxt
    cumulative, result = 0.0, []
    for value, p in sorted(dist.items()):
        cumulative += p
        while len(result) < 2 and cumulative >= [.025, .975][len(result)]-1e-12:
            result.append(value/(3*n))
    assert len(result) == 2
    return result


def qmeans(rs):
    groups = defaultdict(list)
    for r in rs:
        groups[r['qid']].append(r['content_correct'])
    return {q: statistics.mean(v) for q,v in groups.items()}


def paired(left, right):
    a,b = qmeans(left),qmeans(right)
    assert a.keys() == b.keys()
    diff = [b[q]-a[q] for q in sorted(a)]
    ci = exact_ci(diff)
    return {'questions': len(a), 'delta': statistics.mean(diff), 'interval': ci,
            'contains_zero': ci[0] <= 1e-12 and ci[1] >= -1e-12}


main = {}
for path in sorted(RUN.glob('*.jsonl')):
    rows = [r for r in records(path) if not r['low']]
    assert len({(r['qid'],r['rep']) for r in rows}) == len(rows)
    main[path.stem] = rows
result = {'base_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
          'model_api_calls': 0, 'query_executions': 0}
n = sum(map(len, main.values()))
residual = sum(r['census_reviewed'] for rs in main.values() for r in rs)
result['residual'] = {'reviewed': residual, 'denominator': n, 'fraction': residual/n}
result['metrics'] = []
for cell in ['SQL-L1','SQL-L1plus','SQL-L1-tuned','SQL-L1-tuned-instr','SQL-L3a','SQL-L1.5S','JSON-L2']:
    for split in ['all','heldout']:
        rs = [r for r in main[cell] if split=='all' or r['split']==split]
        result['metrics'].append({'cell':cell,'split':split,'correct':sum(r['content_correct'] for r in rs),
            'attempts':len(rs),'accuracy':sum(r['content_correct'] for r in rs)/len(rs)})
    errors = [r for r in main[cell] if not r['content_correct']]
    if cell in ['SQL-L1','SQL-L1-tuned']:
        result.setdefault('errors',{})[cell] = {'errors':len(errors),'with_result':sum(r['has_result'] for r in errors)}

cache = {}


def original(run, cell):
    if (run,cell) not in cache:
        rs = [r for r in records(ROOT/'runs'/run/(cell+'.jsonl')) if r['status']=='done']
        cache[run,cell] = {(r['qid'],r['rep']):r for r in rs}
        assert len(cache[run,cell])==len(rs)
    return cache[run,cell]


classifications = json.loads(read(DATA/'t19a-v8-error-causes-20261101/classifications.json'))['records']
mechanism = [r for r in classifications if r['cell']=='SQL-L1' and r['category']=='SQL 或执行问题']
result['three_sql_cases'] = []
for c in sorted(mechanism,key=lambda r:r['qid']):
    label = next(r for r in main['SQL-L1'] if (r['qid'],r['rep'])==(c['qid'],c['rep']))
    assert label['content_correct']==0
    src = original(label['source_run'],'SQL-L1')[c['qid'],c['rep']]
    result['three_sql_cases'].append({'qid':c['qid'],'rep':c['rep'],'has_result':label['has_result'],
        'first':src['first'],'final':src['final']['outcome'], 'turns':len(src['turns']),
        'execution_statuses':[t['exec']['status'] for t in src['turns']]})

ids = {r['qid'] for r in main['SQL-L1']}
registry = json.loads(read(ROOT/'reports/validation/t16-v14-8836110/coverage.json'))
rev = json.loads(read(RUN/'manifest.json'))['eval_commit']
questions = {}
for name in ['cube_100','new']:
    path = 'questions/'+name+'.yaml'
    raw = subprocess.check_output(['git','-C',str(EVAL),'show',rev+':'+path])
    HASHES['$SEMDEBT_EVAL_DIR@'+rev+'/'+path] = hashlib.sha256(raw).hexdigest()
    questions.update({q['id']:q for q in yaml.safe_load(raw)['questions']})
coverage = {'all':ids,'summary':{q for q in ids if questions[q]['summary_coverage']=='covered'},
            'json':{r['qid'] for r in registry['rows'] if r['category']=='covered'} & ids}
result['same_questions_L1'] = {}
result['covered_comparisons'] = {}
for group,subset in coverage.items():
    base = [r for r in main['SQL-L1'] if r['qid'] in subset]
    result['same_questions_L1'][group] = {'questions':len(subset),'correct':sum(r['content_correct'] for r in base),
        'attempts':len(base),'accuracy':sum(r['content_correct'] for r in base)/len(base)}
    if group!='all':
        cell = {'summary':'SQL-L1.5S','json':'JSON-L2'}[group]
        result['covered_comparisons'][cell] = paired(base,[r for r in main[cell] if r['qid'] in subset])

moved = {'Q03','Q10','Q30','Q47','Q51','Q58','Q72'}
group = {q for q in ids if questions[q]['labels']['semantic_dependency']['primary']=='可从数据发现'}-moved
result['d3'] = {}
for name,subset in [('discoverable',group),('business',ids-group)]:
    rs = {c:[r for r in main[c] if r['qid'] in subset] for c in ['SQL-L0','SQL-L0-E','SQL-L1']}
    result['d3'][name] = {'questions':len(subset), 'L0_L1':paired(rs['SQL-L0'],rs['SQL-L1']),
                         'L0_L0E':paired(rs['SQL-L0'],rs['SQL-L0-E'])}

purpose = list(csv.DictReader(read(ROOT/'reports/midterm/tool-audit.csv').splitlines()))
result['data_and_enum'] = {}
for cell in ['SQL-L0-E','SQL-L1-E']:
    audited = [r for r in purpose if r['unit']==cell and r['qid'] in ids]
    actual = {}
    for label in main[cell]:
        src = original(label['source_run'],cell)[label['qid'],label['rep']]
        for step in src['steps']:
            for c in step['tool_calls']:
                actual[label['qid'],label['rep'],step['call'],c['k']] = hashlib.sha256(c['query'].encode()).hexdigest()
    assert len(actual)==len(audited)
    for r in audited:
        assert actual[r['qid'],int(r['rep']),int(r['call']),int(r['k'])]==r['query_sha256']
    counts = Counter(r['purpose'] for r in audited)
    selected = counts['明细或样例查值']+counts['枚举或分组查值']
    result['data_and_enum'][cell] = {'numerator':selected,'denominator':len(audited),'fraction':selected/len(audited)}

result['first_prompt'] = {}
for cell in ['SQL-L1plus','SQL-L3a']:
    values = [original(r['source_run'],cell)[r['qid'],r['rep']]['turns'][0]['usage']['prompt_tokens'] for r in main[cell]]
    result['first_prompt'][cell] = statistics.mean(values)

# D4 uses rep=1 for accuracy; equivalence selection is fixed input.
equivalent = {r['qid']:r['content_equivalent'] for r in json.loads(read(DATA/'t31-v7-census-20261030/snapshots/20261031-T31-v5-rulings-01/d4-content-equivalence-audit.json'))}
first = [r for r in main['SQL-L1plus'] if r['rep']==1]
wrong = [r for r in first if not r['content_correct']]
blocked = [r for r in first if not equivalent[r['qid']]]
remaining = [r for r in wrong if equivalent[r['qid']]]
result['d4'] = {'questions':len(first),'selected':len(first)-len(blocked),'blocked':len(blocked),
    'blocked_wrong':[r['qid'] for r in blocked if not r['content_correct']],
    'blocked_correct':[r['qid'] for r in blocked if r['content_correct']],
    'remaining_wrong':[{'qid':r['qid'],'scores':[v['content_correct'] for v in sorted(main['SQL-L1plus'],key=lambda x:x['rep']) if v['qid']==r['qid']]} for r in remaining]}

u2 = list(csv.DictReader(read(ROOT/'reports/validation/t29-u2-content-labels.csv').splitlines()))
result['u2'] = {}
for cell in ['SQL-L0-u2','SQL-L0-u2p','SQL-L1-u2','SQL-L1-u2p']:
    rs = [r for r in u2 if r['cell']==cell]
    assert len(rs)==len({(r['qid'],r['rep']) for r in rs})==294
    refused = sum(r['native_refusal']=='True' for r in rs)
    correct = sum(int(r['content_correct']) for r in rs)
    result['u2'][cell] = {'correct':correct,'refused':refused,'attempts':len(rs),
        'accuracy':correct/len(rs),'answered_accuracy':correct/(len(rs)-refused)}
raw_u2 = [r for r in records(DATA/'t29-u2-runtime-v4/runs/20261031-T29-u2-v3-01/SQL-L1-u2.jsonl') if r['status']=='done']
index = {(r['qid'],r['rep']):r for r in raw_u2}
high = [r for r in u2 if r['cell']=='SQL-L1-u2' and r['native_refusal']=='False' and
        (index[r['qid'],int(r['rep'])].get('confidence') or {}).get('status')=='valid' and
        index[r['qid'],int(r['rep'])]['confidence']['value']>=90]
result['u2']['L1_gate90'] = {'answered':len(high),'correct':sum(int(r['content_correct']) for r in high),
    'coverage':len(high)/294,'accuracy':sum(int(r['content_correct']) for r in high)/len(high)}

# Actual stored L1+/L3a contexts: strip only the overlay key and compare bases.
def stored_context(path):
    return yaml.safe_load(read(path).split('```yaml\n',1)[1].split('\n```',1)[0])

frozen = DATA/'t31-v7-census-20261030/frozen-inputs/semantic-v1.6-l1plus'
plus = stored_context(frozen/'SQL-L1plus-system.txt')
l3a = stored_context(frozen/'SQL-L3a-system.txt')
overlay = plus.pop('l1plus')
turtle = l3a.pop('ontology_turtle')
assert plus==l3a
sys.path.insert(0,str(ROOT))
from render.context import render_cell  # Pure in-memory rendering, never main().
assert plus==render_cell('SQL-L1')
sections = ['general_rules','clarifications','concepts','aliases','hierarchies']
mode = Counter(json.loads(match[1]) for line in turtle.splitlines() if (match:=re.search(r' :mode (".*") \.$',line)))
result['l3a_scope'] = {'same_base':plus==l3a,'base_equals_L1_render':plus==render_cell('SQL-L1'),
    'overlay_counts':{k:len(overlay[k]) for k in sections},'modes':dict(mode)}
possible = json.loads(read(ROOT/'reports/validation/l3a-ontology/missed.json'))['formalizable_annotation_entries']
result['l3a_scope']['formalizable_annotations'] = len(possible)

# Independently identify removed YAML nodes and compare retained raw node slices.
def entries(raw):
    text = raw.decode()
    doc = yaml.compose(text)
    indexed = {}
    for key,seq in doc.value:
        if key.value not in ['semantics','rewrites','examples']:
            continue
        for i,node in enumerate(seq.value,1):
            fields = {k.value:v.value for k,v in node.value}
            ident = 'rewrite:'+hashlib.sha256(fields['supersedes'].encode()).hexdigest() if key.value=='rewrites' else fields['id']
            indexed[ident] = (key.value,text[node.start_mark.index:node.end_mark.index])
    return indexed

src = ROOT/'semantic/tuning/SQL-L1.yaml'
dst = ROOT/'semantic/tuning/SQL-L1.combo.yaml'
read(src);read(dst)
a,b = entries(src.read_bytes()),entries(dst.read_bytes())
assert b.keys()<=a.keys()
removed = a.keys()-b.keys()
assert all(a[k]==b[k] for k in b)
rewrite_ids = {k:'R'+str(i) for i,k in enumerate((k for k,v in a.items() if v[0]=='rewrites'),1)}
result['combo_filter'] = {'source':len(a),'retained':len(b),'removed':len(removed),
    'removed_ids':sorted(rewrite_ids.get(k,k) for k in removed),'removed_examples':sum(a[k][0]=='examples' for k in removed),
    'retained_raw_nodes_identical':True}

# Persist only facts from the Q58 notes and reference structure, never their text.
decisions = json.loads(read(DATA/'t31-v7-census-20261030/snapshots/20261031-T31-v5-rulings-01/codex-decisions.json'))
result['Q58'] = []
for rep in [1,2]:
    label = next(r for r in main['JSON-L2'] if r['qid']=='Q58' and r['rep']==rep)
    decision = decisions['|'.join([label['source_run'],'JSON-L2','Q58',str(rep)])]
    result['Q58'].append({'qid':'Q58','rep':rep,'content_correct':label['content_correct'],
        'category':decision['category'],'note_mentions_order':'订单' in decision['note'] or '整单' in decision['note']})
result['Q58_reference_max_sales_row'] = any('max(' in re.sub(r'\s+','',ref['sql'].lower()) and 'salesamount' in ref['sql'].lower() for ref in questions['Q58']['refs'])
result['inputs'] = HASHES
output = OUT/'v9-independent.json'
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'residual':result['residual'],
    'errors':result['errors'],'d4':result['d4'],'l3a':result['l3a_scope'],'combo':result['combo_filter']},ensure_ascii=False))
