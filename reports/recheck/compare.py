"""Compare saved independent outputs, after independent.py and supplement.py."""
import csv
import hashlib
import io
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/recheck'
data = json.loads((OUT / 'independent.json').read_text())
extra = json.loads((OUT / 'supplement.json').read_text())
derived = (ROOT / 'reports/results/t19a-v7-numbers.md').read_text()
checks = []


def check(label, ref, actual, tolerance=.001, kind='point'):
    difference = actual - ref
    checks.append({'item': label, 'kind': kind, 'reference': ref, 'independent': actual,
                   'difference': difference, 'status': 'DIFF' if abs(difference) > tolerance + 1e-10 else 'OK'})


def ci(label, ref, actual):
    check(label + ' lower', ref[0], actual[0], .005, 'interval')
    check(label + ' upper', ref[1], actual[1], .005, 'interval')
    has_zero = lambda x: x[0] <= 1e-12 and x[1] >= -1e-12
    check(label + ' contains zero', int(has_zero(ref)), int(has_zero(actual)), 0, 'zero')


def numbers(value):
    return [float(n) for n in re.findall(r'[+-]?\d+(?:\.\d+)?', value)]


metrics = {(r['cell'], r['split']): r for r in data['cell_metrics']}
section = ''
for line in derived.splitlines():
    if line.startswith('## '):
        section = line[3:]
    if not line.startswith('|'):
        continue
    row = line.split('|')[1:-1]
    if section.startswith('各单元') and row[0] in {r['cell'] for r in data['cell_metrics']}:
        cell = row[0]
        m, h = metrics[cell, 'all'], metrics[cell, 'heldout']
        for name, ref, actual in [('correct', numbers(row[1])[0], m['correct']),
                                  ('attempts', numbers(row[1])[1], m['attempts']),
                                  ('heldout correct', numbers(row[4])[0], h['correct']),
                                  ('heldout attempts', numbers(row[4])[1], h['attempts'])]:
            check(cell + ' ' + name, ref, actual, 0, 'count')
        check(cell + ' accuracy', float(row[2]) / 100, m['accuracy'])
        check(cell + ' heldout accuracy', float(row[5]) / 100, h['accuracy'])
        check(cell + ' delivery', float(row[6]) / 100, m['delivery'])
        ci(cell + ' CI', [v / 100 for v in numbers(row[3])], m['interval'])
    if section.startswith('第 8') and row[1].startswith('SQL-'):
        split = 'heldout' if '留出' in row[0] else 'all'
        m = next(r for r in data['comparisons'] if (r['left'], r['right'], r['split']) == (row[1], row[2], split))
        check('combo ' + ' '.join(row[:3]), float(row[4]) / 100, m['delta'])
        ci('combo ' + ' '.join(row[:3]), [v / 100 for v in numbers(row[5])], m['interval'])
    if section.startswith('D3') and len(row) == 9 and row[0].startswith(('可从', '只能')):
        moved = '（' in row[0]
        dep = row[0].split('（')[0]
        for col, cell in [(2, 'SQL-L0'), (3, 'SQL-L0-E'), (4, 'SQL-L1'), (8, 'SQL-L1-E')]:
            m = next(r for r in data['d3'] if r.get('cell') == cell and r['moved'] == moved and r['dependency'] == dep)
            check('D3 ' + row[0] + ' ' + cell, float(row[col]) / 100, m['accuracy'])
            check('D3 ' + row[0] + ' questions ' + cell, int(row[1]), m['questions'], 0, 'count')
        for col, pair in [(5, ('SQL-L0', 'SQL-L0-E')), (6, ('SQL-L0', 'SQL-L1')), (7, ('SQL-L1', 'SQL-L1-E'))]:
            m = next(r for r in data['d3'] if (r.get('left'), r.get('right')) == pair and r['moved'] == moved and r['dependency'] == dep)
            nums = numbers(row[col])
            label = 'D3 ' + row[0] + ' ' + '→'.join(pair)
            check(label, nums[0] / 100, m['delta'])
            ci(label, [v / 100 for v in nums[1:]], m['interval'])
    if section.startswith('第 5'):
        groups = {'JSON-L2 能覆盖': 'JSON-L2', 'L1.5S 能覆盖': 'SQL-L1.5S', '两者都覆盖': 'intersection'}
        if row[0] in groups and len(row) == 4:
            label, cell = groups[row[0]], row[1]
            if label == 'intersection':
                m = data['coverage_intersection'][cell]
                actual, n = m['correct'], m['attempts']
            else:
                m = next(r for r in data['coverage'] if r['cell'] == label and r['covered'])
                n = m['attempts']
                actual = round(n * (m['accuracy'] if cell == label else m['baselines'][cell]))
            check('coverage ' + row[0] + ' ' + cell + ' correct', numbers(row[2])[0], actual, 0, 'count')
            check('coverage ' + row[0] + ' ' + cell + ' n', numbers(row[2])[1], n, 0, 'count')
            check('coverage ' + row[0] + ' ' + cell, float(row[3]) / 100, actual / n)
        if row[0] in groups and len(row) == 6:
            m = next(r for r in data['coverage_comparisons'] if (r['coverage'], r['left'], r['right']) == (groups[row[0]], row[1], row[2]))
            label = 'coverage ' + ' '.join(row[:3])
            check(label, float(row[4]) / 100, m['delta'])
            ci(label, [v / 100 for v in numbers(row[5])], m['interval'])
        if len(row) == 6 and row[0] in ['JSON-L2', 'SQL-L1.5S']:
            m = next(r for r in data['coverage'] if r['cell'] == row[0] and not r['covered'])
            counts = m['outcomes']
            actuals = [m['attempts'], counts.get('refused', 0), m['attempts'] - counts.get('refused', 0),
                       counts['correct'], counts.get('wrong', 0) + counts.get('exec_error', 0)]
            for name, ref, actual in zip(['attempts', 'refused', 'nonrefused', 'correct', 'wrong-or-error'], row[1:], actuals):
                check('outside ' + row[0] + ' ' + name, int(ref), actual, 0, 'count')

reference_cells = list(csv.DictReader((ROOT / 'reports/results/accuracy-v5-cells.csv').open()))
for r in reference_cells:
    if r['scope'] != 'main98':
        continue
    if r['dimension'] in ['all', 'split']:
        m = metrics[r['cell'], 'all' if r['dimension'] == 'all' else r['group']]
    else:
        m = next(s for s in data['strata'] if (s['cell'], s['dimension'], s['group']) == (r['cell'], r['dimension'], r['group']))
    label = 'cells.csv ' + ' '.join(r[k] for k in ['cell', 'dimension', 'group'])
    check(label, float(r['accuracy']), m['accuracy'])
    check(label + ' correct', int(r['content_correct']), m['correct'], 0, 'count')
    check(label + ' attempts', int(r['attempts']), m['attempts'], 0, 'count')

reference_cmp = list(csv.DictReader((ROOT / 'reports/results/accuracy-v5-comparisons.csv').open()))
for m in data['comparisons']:
    rs = [r for r in reference_cmp if (r['left'], r['right'], r['split'], r['scope']) == (m['left'], m['right'], m['split'], 'main98')]
    if not rs:
        continue
    r = rs[0]
    label = 'cmp.csv ' + ' '.join(m[k] for k in ['left', 'right', 'split'])
    check(label, float(r['accuracy_delta']), m['delta'])
    ci(label, [float(r['accuracy_lo']), float(r['accuracy_hi'])], m['interval'])

buf = io.StringIO()
writer = csv.DictWriter(buf, fieldnames=list(checks[0]), lineterminator='\n')
writer.writeheader()
writer.writerows(checks)
(OUT / 'comparisons.csv').write_text(buf.getvalue())
diffs = [r for r in checks if r['status'] == 'DIFF']
summary = {'checks': len(checks), 'point_count_differences': [r for r in diffs if r['kind'] in ['point', 'count']],
           'interval_differences': [r for r in diffs if r['kind'] == 'interval'],
           'zero_differences': [r for r in diffs if r['kind'] == 'zero'],
           'independent_sha256': hashlib.sha256((OUT / 'independent.json').read_bytes()).hexdigest(),
           'reference_sha256': hashlib.sha256((ROOT / 'reports/results/t19a-v7-numbers.md').read_bytes()).hexdigest()}

# Exact percentile bootstrap for the discrete per-question differences.
# Convolving the empirical score distribution removes Monte Carlo noise.
def exact_ci(values):
    counts = Counter(round(3 * v) for v in values)
    n = len(values)
    distribution = {0: 1.0}
    for _ in range(n):
        nxt = defaultdict(float)
        for total, probability in distribution.items():
            for value, count in counts.items():
                nxt[total + value] += probability * count / n
        distribution = nxt
    cumulative = 0.0
    quantiles = []
    for total, probability in sorted(distribution.items()):
        cumulative += probability
        while len(quantiles) < 2 and cumulative >= [.025, .975][len(quantiles)] - 1e-12:
            quantiles.append(total / (3 * n))
    assert len(quantiles) == 2
    return quantiles


records = {p.stem: [json.loads(line) for line in p.read_text().splitlines() if not json.loads(line)['low']]
           for p in (ROOT / 'runs/20261031-T31-v5-rulings-01').glob('*.jsonl')}


def exact_pair(left, right, ids):
    def means(cell):
        sums, ns = Counter(), Counter()
        for r in records[cell]:
            if r['qid'] in ids:
                sums[r['qid']] += r['content_correct']
                ns[r['qid']] += 1
        return {q: sums[q] / ns[q] for q in ns}
    a, b = means(left), means(right)
    return exact_ci([b[q] - a[q] for q in sorted(a)])


summary['exact_intervals'] = []
for m in data['comparisons']:
    ids = {r['qid'] for r in records[m['right']] if m['split'] == 'all' or r['split'] == m['split']}
    summary['exact_intervals'].append({'label': 'cmp.csv ' + ' '.join(m[k] for k in ['left', 'right', 'split']),
                                       'interval': exact_pair(m['left'], m['right'], ids)})
qs = []
for name in ['cube_100', 'new']:
    qs += yaml.safe_load(subprocess.check_output(['git', '-C', os.environ['SEMDEBT_EVAL_DIR'], 'show', data['eval_commit'] + ':questions/' + name + '.yaml']))['questions']
for m in data['d3']:
    if 'cell' in m:
        continue
    # Membership comes from the independent frozen-label read, not the report.
    ids = {q['id'] for q in qs if ('只能由业务告知' if m['moved'] and q['id'] in {'Q03', 'Q10', 'Q30', 'Q47', 'Q51', 'Q58', 'Q72'} else q['labels']['semantic_dependency']['primary']) == m['dependency']}
    label = m['dependency'] + (('（去掉 7 道可疑题）' if m['dependency'] == '可从数据发现' else '（加入 7 道可疑题）') if m['moved'] else '')
    summary['exact_intervals'].append({'label': 'D3 ' + label + ' ' + m['left'] + '→' + m['right'],
                                       'interval': exact_pair(m['left'], m['right'], ids)})
coverage_ids = {}
registry = json.loads((ROOT / 'reports/validation/t16-v14-8836110/coverage.json').read_text())
coverage_ids['JSON-L2'] = {r['qid'] for r in registry['rows'] if r['category'] == 'covered'}
coverage_ids['SQL-L1.5S'] = {q['id'] for q in qs if q['summary_coverage'] == 'covered'}
coverage_ids['intersection'] = coverage_ids['JSON-L2'] & coverage_ids['SQL-L1.5S']
for m in data['coverage_comparisons']:
    group = {'JSON-L2': 'JSON-L2 能覆盖', 'SQL-L1.5S': 'L1.5S 能覆盖', 'intersection': '两者都覆盖'}[m['coverage']]
    summary['exact_intervals'].append({'label': 'coverage ' + group + ' ' + m['left'] + ' ' + m['right'],
                                       'interval': exact_pair(m['left'], m['right'], coverage_ids[m['coverage']])})
(OUT / 'comparison-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in summary.items()}, ensure_ascii=False, indent=2))
