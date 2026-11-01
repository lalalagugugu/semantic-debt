"""Compare the already saved v8 independent calculation with report sources."""
import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/recheck'
independent = json.loads((OUT / 'v8-independent.json').read_text())
reference = ROOT / 'reports/results/t19a-v8-numbers.md'
text = reference.read_text()
checks = []


def check(item, ref, actual, kind='point', tolerance=.001):
    checks.append({'item': item, 'kind': kind, 'reference': ref, 'independent': actual,
        'difference': actual - ref,
        'status': 'DIFF' if abs(actual - ref) > tolerance + 1e-10 else 'OK'})


def count(item, ref, actual):
    check(item, ref, actual, 'count', 0)


def interval(item, ref, actual, check_zero=True):
    for end, r, a in zip(['lower', 'upper'], ref, actual):
        check(item + ' ' + end, r, a, 'interval', .005)
    if check_zero:
        contains = lambda x: x[0] <= 1e-12 and x[1] >= -1e-12
        check(item + ' contains zero', int(contains(ref)), int(contains(actual)), 'zero', 0)


def nums(s):
    return [float(v) for v in re.findall(r'[+-]?\d+(?:\.\d+)?', s.replace(',', ''))]


cells = {(r['cell'], r['split']): r for r in independent['cells']}
section = ''
for line in text.splitlines():
    if line.startswith('## '):
        section = line[3:]
    if not line.startswith('|'):
        continue
    r = line.split('|')[1:-1]
    if section == '题目构成' and r[0] in ['cube_100', 'new']:
        key = 'cube' if r[0] == 'cube_100' else 'new'
        actual = independent['composition']['source'][key]
        excluded = independent['composition']['excluded'].get(key, 0)
        for name, ref, value in zip(['bank', 'scored', 'unscored'], r[1:], [actual + excluded, actual, excluded]):
            count('composition ' + key + ' ' + name, int(ref), value)
    if section.startswith('第 6') and len(r) == 4 and r[1] in independent['process']:
        process = independent['process'][r[1]]
        count(r[1] + ' first errors', nums(r[2])[0], process['first_execution_errors'])
        count(r[1] + ' first denominator', nums(r[2])[1], process['attempts'])
        check(r[1] + ' first error rate', float(r[3])/100, process['first_execution_errors']/process['attempts'])
    if section.startswith('第 3') and r[0] in independent['tool_purposes']:
        process = independent['process'][r[0]]
        count(r[0] + ' tool calls', int(r[1]), process['tool_calls'])
        count(r[0] + ' tool denominator', int(r[2]), process['attempts'])
        check(r[0] + ' calls per attempt', float(r[3]), process['tool_calls']/process['attempts'], 'ratio', .005)
        for purpose, n in independent['tool_purposes'][r[0]].items():
            match = re.search(re.escape(purpose) + r' ([\d.]+)%', r[4])
            assert match, purpose
            check(r[0] + ' ' + purpose, float(match[1])/100, n/process['tool_calls'])
    if section.startswith('第 2、4') and r[0] in independent['process']:
        process = independent['process'][r[0]]
        for label, ref, actual in [('first prompt', nums(r[1])[0], process['first_prompt_mean']),
                                    ('total prompt', nums(r[2])[0], process['mean_total_prompt'])]:
            check(r[0] + ' ' + label, ref, actual, 'token', .5)
    if section.startswith('第 5') and r[0] in ['JSON-L2', 'SQL-L1.5S']:
        cov = next(c for c in independent['coverage'] if c['cell'] == r[0])
        actual = cells[r[0], 'all']
        for label, ref, value in [('correct', nums(r[1])[0], actual['correct']),
                ('denominator', nums(r[1])[1], actual['attempts']), ('errors', int(r[2]), cov['errors']),
                ('outside errors', int(r[3]), cov['outside_errors']),
                ('covered correct', nums(r[5])[0], cov['covered_correct']),
                ('covered denominator', nums(r[5])[1], cov['covered_attempts'])]:
            count(r[0] + ' ' + label, ref, value)
        check(r[0] + ' outside fraction of errors', nums(r[4])[0]/100, cov['fraction'])

# This prose has four numeric fields, kept explicit rather than depending on dict order.
errors = independent['causes']['SQL-L1-tuned']
for name, ref, value in [('tuned errors', 12, errors['total']), ('tuned with result', 12, errors['with_result']),
                       ('tuned heldout errors', 11, errors['split']['heldout']), ('tuned tuning errors', 1, errors['split']['tuning'])]:
    count(name, ref, value)

# All relevant main-table cell values, and both reported paired scopes.
for r in csv.DictReader((ROOT / 'reports/results/accuracy-v5-cells.csv').open()):
    if r['dimension'] not in ['all', 'split']:
        continue
    key = r['cell'], ('all' if r['dimension'] == 'all' else r['group'])
    m = cells[key]
    check('cells.csv ' + ' '.join(key), float(r['accuracy']), m['accuracy'])
    check('delivery.csv ' + ' '.join(key), float(r['delivery']), m['delivery'])
    count('correct.csv ' + ' '.join(key), int(r['content_correct']), m['correct'])


def pair(left, right, split):
    for p in independent['pairs']:
        if p['split'] != split:
            continue
        if (p['left'], p['right']) == (left, right):
            return p
        if (p['left'], p['right']) == (right, left):
            return {**p, 'delta': -p['delta'], 'interval': [-p['interval'][1], -p['interval'][0]]}
    raise ValueError((left, right, split))


for r in csv.DictReader((ROOT / 'reports/results/accuracy-v5-comparisons.csv').open()):
    if r['split'] not in ['all', 'heldout']:
        continue
    p = pair(r['left'], r['right'], r['split'])
    label = 'cmp.csv ' + ' '.join(r[k] for k in ['left', 'right', 'split'])
    check(label, float(r['accuracy_delta']), p['delta'])
    interval(label, [float(r['accuracy_lo']), float(r['accuracy_hi'])], p['interval'])

# Recount the public cause rows, using the private final categories as fixed inputs.
cause_text = (ROOT / 'reports/results/t19a-v8-error-causes.md').read_text()
public_identities = set()
for line in cause_text.splitlines():
    if not line.startswith('|'):
        continue
    r = line.split('|')[1:-1]
    if len(r) == 6 and r[0] in independent['causes']:
        actual = independent['causes'][r[0]]
        categories = actual['categories']
        values = [categories.get(k, 0) for k in ['怎么算（口径或算法读偏）', '是什么、属于谁（对象或范围）', 'SQL 或执行问题', '其他']] + [actual['total']]
        for i, (ref, value) in enumerate(zip(r[1:], values)):
            count('cause ' + r[0] + ' column ' + str(i+1), int(ref), value)
    if len(r) == 4 and re.fullmatch(r'Q\d+', r[0]):
        public_identities.add((r[1], r[0], int(r[2]), r[3]))
fixed_identities = {(c, r['qid'], r['rep'], r['category']) for c, v in independent['causes'].items() for r in v['identities']}
assert public_identities == fixed_identities
count('public cause identities', len(public_identities), len(fixed_identities))

u2_ref = json.loads((ROOT / 'reports/results/t29-u2-content-analysis.json').read_text())
for u in independent['u2']:
    c = u['cell']
    s = u2_ref['summary'][c]
    count('U2 ' + c + ' n', s['attempts'], u['attempts'])
    count('U2 ' + c + ' correct', s['correct'], u['correct'])
    check('U2 ' + c + ' accuracy', s['accuracy'], u['accuracy'])
    count('U2 ' + c + ' refused', s['methods'].get('refused', 0), u['refused'])
    if c in u2_ref['arms']:
        a = u2_ref['arms'][c]
        for name, k in [('refusal_rate','refusal_rate'), ('accuracy_answered','answered_accuracy')]:
            check('U2 ' + c + ' ' + name, a[name], u[k])
        for name, k in [('answered','gate90_answered'), ('coverage','gate90_coverage'), ('accuracy_answered','gate90_accuracy')]:
            check('U2 ' + c + ' gate90 ' + name, a['gate90'][name], u[k], 'count' if name=='answered' else 'point', 0 if name=='answered' else .001)
    else:
        # Explicit baseline values in the v8 source list.
        refusal, answered = {'SQL-L0': (.031, .477), 'SQL-L1': (.0, .799)}[c]
        check('U2 baseline ' + c + ' refusal rate', refusal, u['refusal_rate'])
        check('U2 baseline ' + c + ' answered accuracy', answered, u['answered_accuracy'])
for base, c in u2_ref['penalty_contrasts'].items():
    p = next(p for p in independent['u2_pairs'] if p['left']==base+'-u2' and p['right']==base+'-u2p' and p['metric']=='refused')
    check('U2 penalty ' + base, c['penalty_minus_unpenalized'], p['delta'])
    interval('U2 penalty ' + base, c['ci95'], p['interval'])
for p in independent['u2_baseline_selection']:
    c = p['cell']
    ref = u2_ref['arms'][c]
    if not p['refusal_rate_at_least_5_percent']:
        assert ref['refusal_error_difference'] is None
        continue
    check('U2 ' + c + ' baseline error refused', ref['baseline_error_refused'], p['refused_baseline_error'])
    check('U2 ' + c + ' baseline error answered', ref['baseline_error_answered'], p['answered_baseline_error'])
    check('U2 ' + c + ' selection delta', ref['refusal_error_difference'], p['difference'])
    interval('U2 ' + c + ' selection delta', ref['refusal_error_difference_ci'], p['interval'])
count('U2 independent review n', u2_ref['independent_review']['reviewed'], independent['u2_independent_review_rows'])
count('U2 deterministic credits', u2_ref['independent_review']['deterministic_credits'], independent['u2_methods']['v2']+independent['u2_methods']['R1-R11'])
for k, v in {'combined_cells':25, 'combined_attempts':7203, 'formal_cells':19, 'formal_attempts':5439, 'u2_attempts':1764}.items():
    count('scale ' + k, v, independent['scale'][k])
for k,v in {'questions':98}.items():
    count('composition ' + k, v, independent['composition'][k])
for level,n in [('Q1',38),('Q2',33),('Q3',27)]:
    count('composition '+level,n,independent['composition']['q_level'][level])

# The v8 appendix inherits the v7 unit table, including its single-cell CIs.
v7 = (ROOT / 'reports/results/t19a-v7-numbers.md').read_text()
section = ''
for line in v7.splitlines():
    if line.startswith('## '):
        section = line[3:]
    if not line.startswith('|'):
        continue
    row = line.split('|')[1:-1]
    if section.startswith('各单元') and row[0] in independent['process']:
        actual = cells[row[0], 'all']
        interval('appendix ' + row[0], [n/100 for n in nums(row[3])], actual['interval'], False)
    if section.startswith('D3') and len(row)==9 and row[0].startswith(('可从', '只能')):
        moved = '（' in row[0]
        dep = row[0].split('（')[0]
        actual = next(d for d in independent['d3'] if d['moved']==moved and d['dependency']==dep)
        count('D3 ' + row[0] + ' questions', int(row[1]), actual['questions'])
        for index, cell in [(2,'SQL-L0'),(3,'SQL-L0-E'),(4,'SQL-L1'),(8,'SQL-L1-E')]:
            check('D3 '+row[0]+' '+cell, float(row[index])/100, actual['accuracy'][cell])
        for index,key in [(5,'L0_L0E'),(6,'L0_L1')]:
            values = nums(row[index])
            check('D3 '+row[0]+' '+key, values[0]/100, actual[key]['delta'])
            interval('D3 '+row[0]+' '+key, [v/100 for v in values[1:]], actual[key]['interval'])

buffer = io.StringIO()
writer = csv.DictWriter(buffer, fieldnames=list(checks[0]), lineterminator='\n')
writer.writeheader()
writer.writerows(checks)
(OUT / 'v8-comparisons.csv').write_text(buffer.getvalue())
summary = {'independent_sha256': hashlib.sha256((OUT/'v8-independent.json').read_bytes()).hexdigest(),
    'v8_reference_sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
    'checks': len(checks), 'counts': dict(Counter((r['kind']+' '+r['status']) for r in checks)),
    'differences': [r for r in checks if r['status']=='DIFF']}
(OUT / 'v8-comparison-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({k: (len(v) if k == 'differences' else v) for k, v in summary.items()}, ensure_ascii=False, indent=2))
