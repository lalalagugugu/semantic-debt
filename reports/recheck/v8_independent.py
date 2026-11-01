"""T20 v8 offline calculation; no report calculator imports or model calls.

Private inputs are read only through environment variables. Persist only counts,
question IDs, categories and input hashes, never questions or original responses.
"""
import csv
import hashlib
import itertools
import json
import os
import random
import statistics
import subprocess
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
    if path.is_relative_to(DATA):
        key = '$SEMDEBT_DATA_DIR/' + str(path.relative_to(DATA))
    else:
        key = str(path.relative_to(ROOT))
    HASHES[key] = hashlib.sha256(raw).hexdigest()
    return raw.decode()


def records(path):
    return [json.loads(line) for line in read(path).splitlines() if line.strip()]


def exact_interval(values):
    """Exact percentile bootstrap of question means (three repeats per question)."""
    n = len(values)
    freq = Counter(round(3 * v) for v in values)
    assert all(abs(3 * v - round(3 * v)) < 1e-10 for v in values)
    dist = {0: 1.0}
    for _ in range(n):
        nxt = defaultdict(float)
        for total, probability in dist.items():
            for value, count in freq.items():
                nxt[total + value] += probability * count / n
        dist = nxt
    total, quantiles = 0.0, []
    for value, probability in sorted(dist.items()):
        total += probability
        while len(quantiles) < 2 and total >= [.025, .975][len(quantiles)] - 1e-12:
            quantiles.append(value / (3 * n))
    assert len(quantiles) == 2
    return quantiles


def means(rs, key):
    groups = defaultdict(list)
    for r in rs:
        groups[r['qid']].append(r[key])
    return {q: statistics.mean(v) for q, v in sorted(groups.items())}


def paired(left, right, key):
    a, b = means(left, key), means(right, key)
    assert a.keys() == b.keys()
    diffs = [b[q] - a[q] for q in a]
    interval = exact_interval(diffs)
    return {'questions': len(a), 'delta': statistics.mean(diffs),
            'interval': interval, 'contains_zero': interval[0] <= 1e-12 <= interval[1] + 1e-12}


manifest = json.loads(read(RUN / 'manifest.json'))
rev = manifest['eval_commit']
questions = {}
for name in ['cube_100', 'new']:
    path = 'questions/' + name + '.yaml'
    raw = subprocess.check_output(['git', '-C', str(EVAL), 'show', rev + ':' + path])
    HASHES['$SEMDEBT_EVAL_DIR@' + rev + '/' + path] = hashlib.sha256(raw).hexdigest()
    for q in yaml.safe_load(raw)['questions']:
        questions[q['id']] = {'source': q['source'], 'scoring': q['scoring'],
            'split': q['split'], 'q_level': q['labels']['q_level'],
            'low': bool(q['labels']['low_discrimination']['criteria']),
            'dependency': q['labels']['semantic_dependency']['primary'],
            'coverage': q['summary_coverage']}

main = {}
original_cache = {}


def original(run, cell):
    if (run, cell) not in original_cache:
        rs = records(ROOT / 'runs' / run / (cell + '.jsonl'))
        done = [r for r in rs if r['status'] == 'done']
        index = {(r['qid'], r['rep']): r for r in done}
        assert len(index) == len(done)
        original_cache[run, cell] = index
    return original_cache[run, cell]


result = {'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
          'eval_commit': rev, 'model_api_calls': 0, 'query_executions': 0,
          'interval_method': 'exact discrete percentile bootstrap by question',
          'cells': [], 'process': {}, 'pairs': [], 'coverage': [], 'causes': {}}
for path in sorted(RUN.glob('*.jsonl')):
    rs = records(path)
    for r in rs:
        assert r['low'] == questions[r['qid']]['low']
        assert r['split'] == questions[r['qid']]['split']
    sub = [r for r in rs if not r['low']]
    assert len({(r['qid'], r['rep']) for r in sub}) == len(sub)
    assert all(r['content_correct'] in [0, 1] for r in sub)
    main[path.stem] = sub
    for split in ['all', 'heldout', 'tuning']:
        selected = [r for r in sub if split == 'all' or r['split'] == split]
        if not selected:
            continue
        outcomes = Counter('correct' if r['content_correct'] else 'wrong' if r['has_result'] else r['historical_outcome'] for r in selected)
        qm = means(selected, 'content_correct')
        result['cells'].append({'cell': path.stem, 'split': split,
            'questions': len(qm), 'attempts': len(selected), 'correct': sum(r['content_correct'] for r in selected),
            'accuracy': sum(r['content_correct'] for r in selected) / len(selected),
            'delivery': sum(r['a'] for r in selected) / len(selected),
            'outcomes': dict(outcomes), 'interval': exact_interval(list(qm.values()))})
    source = [original(r['source_run'], path.stem)[r['qid'], r['rep']] for r in sub]
    assert len(source) == len(sub)
    first = [r['turns'][0] for r in source]
    process = {'attempts': len(source), 'first_execution_errors': sum(t['exec']['status'] == 'error' for t in first),
        'first_record_errors': sum(r['first'] == 'exec_error' for r in source),
        'first_prompt_mean': statistics.mean(t['usage']['prompt_tokens'] for t in first),
        'first_prompt_min': min(t['usage']['prompt_tokens'] for t in first),
        'first_prompt_max': max(t['usage']['prompt_tokens'] for t in first),
        'mean_total_prompt': statistics.mean(r['usage']['prompt_tokens'] for r in source),
        'logged_cost': sum(r['cost_cny'] for r in source),
        'cold_cost': sum((2 if r['peak'] else 1) * (r['usage']['prompt_tokens'] + 4 * r['usage']['completion_tokens']) / 1e6 for r in source)}
    if '-E' in path.stem:
        calls = [c for r in source for step in r['steps'] for c in step['tool_calls']]
        process['tool_calls'] = len(calls)
    result['process'][path.stem] = process

# Exact paired intervals for every pair within each compatible main/heldout set.
for a, b in itertools.combinations(sorted(main), 2):
    for split in ['all', 'heldout']:
        left = [r for r in main[a] if split == 'all' or r['split'] == split]
        right = [r for r in main[b] if split == 'all' or r['split'] == split]
        ids = {r['qid'] for r in left} & {r['qid'] for r in right}
        result['pairs'].append({'left': a, 'right': b, 'split': split,
            **paired([r for r in left if r['qid'] in ids], [r for r in right if r['qid'] in ids], 'content_correct')})

ids = {r['qid'] for r in main['SQL-L1']}
result['composition'] = {'questions': len(ids), 'source': dict(Counter(questions[q]['source'] for q in ids)),
    'q_level': dict(Counter(questions[q]['q_level'] for q in ids)),
    'split': dict(Counter(questions[q]['split'] for q in ids)),
    'excluded': dict(Counter(questions[q]['source'] for q in questions.keys() - ids)),
    'excluded_qids': sorted(questions.keys() - ids)}
result['scale'] = {'formal_cells': len(main), 'formal_attempts': sum(map(len, main.values())),
                    'u2_cells': 6, 'u2_attempts': 0}
reg = json.loads(read(ROOT / 'reports/validation/t16-v14-8836110/coverage.json'))
cover = {'JSON-L2': {r['qid'] for r in reg['rows'] if r['category'] == 'covered'},
         'SQL-L1.5S': {q for q in ids if questions[q]['coverage'] == 'covered'}}
for cell, covered in cover.items():
    errors = [r for r in main[cell] if not r['content_correct']]
    outside_errors = [r for r in errors if r['qid'] not in covered]
    inside = [r for r in main[cell] if r['qid'] in covered]
    result['coverage'].append({'cell': cell, 'covered_questions': len(covered & ids),
        'covered_correct': sum(r['content_correct'] for r in inside), 'covered_attempts': len(inside),
        'errors': len(errors), 'outside_errors': len(outside_errors), 'fraction': len(outside_errors) / len(errors)})

# Recount frozen error categories by identity; do not reinterpret private evidence.
classes = json.loads(read(DATA / 't19a-v8-error-causes-20261101/classifications.json'))['records']
for cell in ['SQL-L1', 'SQL-L3a', 'SQL-L1-tuned']:
    expected = {(r['qid'], r['rep']) for r in main[cell] if not r['content_correct']}
    sub = [r for r in classes if r['cell'] == cell]
    assert len(sub) == len({(r['qid'], r['rep']) for r in sub})
    assert expected == {(r['qid'], r['rep']) for r in sub}
    errors = [r for r in main[cell] if not r['content_correct']]
    result['causes'][cell] = {'categories': dict(Counter(r['category'] for r in sub)),
        'total': len(sub), 'with_result': sum(r['has_result'] for r in errors),
        'split': dict(Counter(r['split'] for r in errors)),
        'identities': [{'qid': r['qid'], 'rep': r['rep'], 'category': r['category']} for r in sub]}

moved = {'Q03', 'Q10', 'Q30', 'Q47', 'Q51', 'Q58', 'Q72'}
result['d3'] = []
for move in [False, True]:
    for dep in ['可从数据发现', '只能由业务告知']:
        group = {q for q in ids if ('只能由业务告知' if move and q in moved else questions[q]['dependency']) == dep}
        group_rows = {}
        for cell in ['SQL-L0', 'SQL-L0-E', 'SQL-L1', 'SQL-L1-E']:
            group_rows[cell] = [r for r in main[cell] if r['qid'] in group]
        result['d3'].append({'moved': move, 'dependency': dep, 'questions': len(group),
            'accuracy': {c: sum(r['content_correct'] for r in sub) / len(sub) for c, sub in group_rows.items()},
            'L0_L1': paired(group_rows['SQL-L0'], group_rows['SQL-L1'], 'content_correct'),
            'L0_L0E': paired(group_rows['SQL-L0'], group_rows['SQL-L0-E'], 'content_correct')})

# Native refusals from the supplied final CSV; confidence from original done logs.
labels = list(csv.DictReader(read(ROOT / 'reports/validation/t29-u2-content-labels.csv').splitlines()))
u2 = defaultdict(list)
original_u2 = {}
for cell in sorted({r['cell'] for r in labels}):
    rs = records(DATA / 't29-u2-runtime-v4/runs/20261031-T29-u2-v3-01' / (cell + '.jsonl'))
    done = [r for r in rs if r['status'] == 'done']
    assert len(done) == len({(r['qid'], r['rep']) for r in done}) == 294
    original_u2[cell] = {(r['qid'], r['rep']): r for r in done}
for r in labels:
    src = original_u2[r['cell']][r['qid'], int(r['rep'])]
    refusal = r['native_refusal'] == 'True'
    conf = src.get('confidence')
    assert refusal == (conf['native_refusal'] if conf else src['final']['outcome'] == 'refused')
    u2[r['cell']].append({'qid': r['qid'], 'rep': int(r['rep']), 'correct': int(r['content_correct']),
        'refused': int(refusal), 'confidence': conf['value'] if conf and conf['status'] == 'valid' else None})
result['u2'] = []
for cell, rs in sorted(u2.items()):
    assert {r['qid'] for r in rs} == ids and len(rs) == 294
    assert len({(r['qid'], r['rep']) for r in rs}) == 294
    refused = sum(r['refused'] for r in rs)
    correct = sum(r['correct'] for r in rs)
    assert not any(r['refused'] and r['correct'] for r in rs)
    high = [r for r in rs if not r['refused'] and r['confidence'] is not None and r['confidence'] >= 90]
    result['u2'].append({'cell': cell, 'attempts': len(rs), 'correct': correct,
        'accuracy': correct / len(rs), 'refused': refused, 'refusal_rate': refused / len(rs),
        'answered': len(rs) - refused, 'answered_accuracy': correct / (len(rs) - refused),
        'gate90_answered': len(high), 'gate90_correct': sum(r['correct'] for r in high),
        'gate90_coverage': len(high) / len(rs),
        'gate90_accuracy': sum(r['correct'] for r in high) / len(high) if high else None})
result['scale']['u2_attempts'] = len(labels)
result['scale']['combined_cells'] = len(main) + len(u2)
result['scale']['combined_attempts'] = sum(map(len, main.values())) + len(labels)
result['u2_methods'] = dict(Counter(r['method'] for r in labels))
result['u2_pairs'] = []
for a, b in itertools.combinations(sorted(u2), 2):
    for key in ['correct', 'refused']:
        result['u2_pairs'].append({'left': a, 'right': b, 'metric': key, **paired(u2[a], u2[b], key)})

# Pre-registered refusal selection: baseline per-question three-repeat error rate.
# Resampling whole questions; denominator weights follow each resampled question.
result['u2_baseline_selection'] = []
for cell in ['SQL-L0-u2', 'SQL-L0-u2p', 'SQL-L1-u2', 'SQL-L1-u2p']:
    baseline = cell.split('-u2')[0]
    base = means(u2[baseline], 'correct')
    by_q = defaultdict(list)
    for r in u2[cell]:
        by_q[r['qid']].append(r)
    vectors = []
    for q in sorted(by_q):
        nr = sum(r['refused'] for r in by_q[q])
        vectors.append((nr * (1 - base[q]), nr, (3 - nr) * (1 - base[q]), 3 - nr))
    totals = [sum(v[i] for v in vectors) for i in range(4)]
    rejected_error = totals[0] / totals[1] if totals[1] else None
    answered_error = totals[2] / totals[3]
    rng = random.Random(20261101)
    samples = []
    for _ in range(10000):
        sample = rng.choices(vectors, k=98)
        a, b, c, f = [sum(v[i] for v in sample) for i in range(4)]
        if b and f:
            samples.append(a / b - c / f)
    samples.sort()
    result['u2_baseline_selection'].append({'cell': cell, 'refused_baseline_error': rejected_error,
        'answered_baseline_error': answered_error,
        'difference': rejected_error - answered_error if rejected_error is not None else None,
        'interval': [samples[int(.025 * (len(samples)-1))], samples[int(.975 * (len(samples)-1))]] if samples else None,
        'refusal_rate_at_least_5_percent': totals[1] / 294 >= .05})

# Static inherited numbers, recounted without touching frozen data.
source = yaml.safe_load(read(ROOT / 'semantic/source.yaml'))
plus = yaml.safe_load(read(ROOT / 'semantic/l1plus.yaml'))
result['static'] = {'metrics': len(source['metrics']), 'synonyms': len(source['synonyms']),
    'plus_counts': {k: len(plus[k]) for k in ['general_rules', 'clarifications', 'concepts', 'aliases', 'hierarchies']}}
correspondence = read(ROOT / 'reports/validation/l1plus-l3a-correspondence.md')
formal = {line.split('|')[2].strip() for line in correspondence.splitlines() if line.endswith('形式化 |')}
missed = json.loads(read(ROOT / 'reports/validation/l3a-ontology/missed.json'))
possible = set(missed['formalizable_annotation_entries'])
assert not formal & possible
result['static']['ontology_formal_or_formalizable'] = len(formal | possible)
result['static']['ontology_total'] = sum(result['static']['plus_counts'].values())
# Metadata only: no data values or questions persisted.
import pyarrow.parquet as pq
meta = [pq.ParquetFile(p).metadata for p in sorted((DATA / 'parquet').glob('*.parquet'))]
result['static']['dataset'] = {'tables': len(meta), 'columns': sum(p.num_columns for p in meta), 'rows': sum(p.num_rows for p in meta)}
store = pq.read_table(DATA / 'parquet/DimStore.parquet', columns=['StoreType'])
result['static']['store_types'] = dict(Counter(store.column(0).to_pylist()))
pilot = [r for c in ['SQL-L0-P', 'SQL-L1-P'] for r in records(ROOT / 'runs/20261019-T21-pilot-01' / (c + '.jsonl'))]
result['static']['pilot'] = {'attempts': len(pilot), 'questions': len({r['qid'] for r in pilot}),
    'python_calls': sum(c['name'] == 'python' for r in pilot for step in r['steps'] for c in step['tool_calls'])}
# Fraction of all online-sales rows affected by orphan ProductKey, inherited 14%.
product_ids = set(pq.read_table(DATA / 'parquet/DimProduct.parquet', columns=['ProductKey']).column(0).to_pylist())
sales = pq.ParquetFile(DATA / 'parquet/FactOnlineSales.parquet')
orphans = sum(k not in product_ids for batch in sales.iter_batches(columns=['ProductKey'], batch_size=262144) for k in batch.column(0).to_pylist())
result['static']['orphan_products'] = {'rows': orphans, 'all_rows': sales.metadata.num_rows, 'fraction': orphans / sales.metadata.num_rows}

audit = list(csv.DictReader(read(ROOT / 'reports/midterm/tool-audit.csv').splitlines()))
result['tool_purposes'] = {}
for cell in ['SQL-L0-E', 'SQL-L1-E']:
    rs = [r for r in audit if r['unit'] == cell and r['qid'] in ids]
    calls = {}
    for r in main[cell]:
        src = original(r['source_run'], cell)[r['qid'], r['rep']]
        for step in src['steps']:
            for c in step['tool_calls']:
                calls[r['qid'], r['rep'], step['call'], c['k']] = hashlib.sha256(c['query'].encode()).hexdigest()
    assert len(rs) == len(calls)
    for r in rs:
        assert calls[r['qid'], int(r['rep']), int(r['call']), int(r['k'])] == r['query_sha256']
    result['tool_purposes'][cell] = dict(Counter(r['purpose'] for r in rs))

equivalence = json.loads(read(DATA / 't31-v7-census-20261030/snapshots/20261031-T31-v5-rulings-01/d4-content-equivalence-audit.json'))
selected = {r['qid'] for r in equivalence if r['content_equivalent']}
first = [r for r in main['SQL-L1plus'] if r['rep'] == 1]
result['d4'] = {'first_correct': sum(r['content_correct'] for r in first), 'first_n': len(first),
    'selected': sum(r['qid'] in selected for r in first),
    'selected_correct': sum(r['content_correct'] for r in first if r['qid'] in selected),
    'first_wrong': sum(not r['content_correct'] for r in first),
    'blocked_wrong': sum(not r['content_correct'] and r['qid'] not in selected for r in first),
    'blocked_correct': sum(r['content_correct'] and r['qid'] not in selected for r in first)}

# Reuse inherited independent evidence only when its input bytes remain unchanged.
prior = json.loads(read(OUT / 'v7-fixes.json'))
checked, changed = [], []
for name, digest in prior['source_sha256'].items():
    # Frozen eval metadata is freshly read above. Large data has been recounted.
    if name.startswith('eval@') or name.startswith('$SEMDEBT_DATA_DIR/parquet/') or name.endswith('v7-number-sources.md'):
        continue
    path = DATA / name.removeprefix('$SEMDEBT_DATA_DIR/') if name.startswith('$SEMDEBT_DATA_DIR/') else ROOT / name
    current = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    (checked if current == digest else changed).append(name)
result['inherited_input_verification'] = {'unchanged': checked, 'changed': changed}
assert not changed, changed
result['inherited'] = {k: prior[k] for k in ['pro_flash_cost_ratio', 'tutorial_examples', 'l0_relationships',
    'explorer_step_cap', 'approved_rule_ids', 'scenario_rendering']}
review = list(csv.DictReader(read(DATA / 't29-u2-content-20261031/claude-review/claude-labels-u2-101.csv').splitlines()))
result['u2_independent_review_rows'] = len(review)
result['inputs'] = HASHES
path = OUT / 'v8-independent.json'
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'output_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'scale': result['scale'],
                  'new_first_errors': {c: result['process'][c]['first_record_errors'] for c in ['SQL-L1', 'SQL-L1-T2', 'SQL-L1-T3']}}))
