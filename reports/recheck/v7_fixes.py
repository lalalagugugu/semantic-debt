"""Independent offline recheck of PR 231 additions; no report calculators or APIs.

Run from the T20 checkout with SEMDEBT_DATA_DIR and SEMDEBT_EVAL_DIR set.
Only aggregates, question IDs, source paths and hashes are saved.
"""
import csv
import hashlib
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ['SEMDEBT_DATA_DIR'])
EVAL = Path(os.environ['SEMDEBT_EVAL_DIR'])
RUN = ROOT / 'runs/20261031-T31-v5-rulings-01'
inputs = {}
result = {'model_calls': 0, 'query_executions': 0,
          'reviewed_head': 'a8a1ec260290013a6ab0fa551bd538d4202f2538'}


def read(path):
    raw = path.read_bytes()
    key = ('$SEMDEBT_DATA_DIR/' + str(path.relative_to(DATA)) if path.is_relative_to(DATA)
           else str(path.relative_to(ROOT)))
    inputs[key] = hashlib.sha256(raw).hexdigest()
    return raw.decode()


def records(path):
    return [json.loads(line) for line in read(path).splitlines() if line.strip()]


rev = json.loads(read(RUN / 'manifest.json'))['eval_commit']
questions = {}
counts = {}
for name in ['cube_100', 'new']:
    path = 'questions/' + name + '.yaml'
    raw = subprocess.check_output(['git', '-C', str(EVAL), 'show', rev + ':' + path])
    inputs['eval@' + rev + '/' + path] = hashlib.sha256(raw).hexdigest()
    bank = yaml.safe_load(raw)['questions']
    counts[name] = len(bank)
    questions.update({q['id']: q for q in bank})
result['bank_counts'] = {**counts, 'total': len(questions)}
main = {}
for cell in ['SQL-L0', 'SQL-L1', 'SQL-L0-E', 'SQL-L1-E', 'SQL-L2', 'SQL-L2-E',
             'SQL-L1plus', 'SQL-L3a', 'JSON-L2', 'SQL-L1.5S', 'SQL-L1.5W', 'SQL-L1plus-tuned-instr']:
    rs = records(RUN / (cell + '.jsonl'))
    main[cell] = [r for r in rs if not r['low']]
    assert len({(r['qid'], r['rep']) for r in main[cell]}) == 294
l1 = main['SQL-L1']
assert len(l1) == 294
unique = {r['qid']: r for r in l1}
for qid, r in unique.items():
    labels = questions[qid]['labels']
    assert r['q_level'] == labels['q_level'] and r['split'] == questions[qid]['split']
    assert r['persona'] == labels['persona']
result['main_question_counts'] = {key: dict(Counter(r[key] for r in unique.values()))
                                  for key in ['q_level', 'split', 'persona']}

# Original attempts include all repair/tool turns in their top-level usage.
cache = {}


def source(run, cell):
    key = run, cell
    if key not in cache:
        rs = records(ROOT / 'runs' / run / (cell + '.jsonl'))
        cache[key] = {(r['qid'], r['rep']): r for r in rs
                      if r.get('status') == 'done' and 'qid' in r}
    return cache[key]


usage = {}
for cell in ['SQL-L0', 'SQL-L1', 'SQL-L2', 'SQL-L0-E', 'SQL-L1-E', 'SQL-L2-E']:
    rs = [source(r['source_run'], cell)[r['qid'], r['rep']] for r in main[cell]]
    assert len(rs) == 294
    totals = {k: sum(r['usage'][k] for r in rs)
              for k in ['prompt_tokens', 'cache_hit_tokens', 'cache_miss_tokens', 'completion_tokens']}
    assert totals['prompt_tokens'] == totals['cache_hit_tokens'] + totals['cache_miss_tokens']
    # Historical Flash off-peak prices per million tokens; peak doubles all prices.
    actual = sum(Decimal(2 if r.get('peak') else 1) *
                 (Decimal('.02') * r['usage']['cache_hit_tokens'] +
                  r['usage']['cache_miss_tokens'] + 4 * r['usage']['completion_tokens']) /
                 1000000 for r in rs)
    cold = sum(Decimal(2 if r.get('peak') else 1) *
               (r['usage']['prompt_tokens'] + 4 * r['usage']['completion_tokens']) /
               1000000 for r in rs)
    assert abs(float(actual) - sum(r['cost_cny'] for r in rs)) < 1e-7
    usage[cell] = {**totals, 'attempts': len(rs), 'mean_input': totals['prompt_tokens'] / len(rs),
                   'recorded_cny': float(actual), 'all_cold_cny': float(cold)}
result['usage'] = usage
result['exploration_ratios'] = {
    cell: {'input': usage[cell + '-E']['prompt_tokens'] / usage[cell]['prompt_tokens'],
           'all_cold_cost': usage[cell + '-E']['all_cold_cny'] / usage[cell]['all_cold_cny'],
           'recorded_cost': usage[cell + '-E']['recorded_cny'] / usage[cell]['recorded_cny']}
    for cell in ['SQL-L0', 'SQL-L1', 'SQL-L2']}

# Keep the exact historical run scope, including pilots, obsolete variants and retries.
ledger = list(csv.DictReader(read(ROOT / 'reports/midterm/v3-cost-runs.csv').splitlines()))
post = ['20261025-T29-pilot-01', '20261026-T29-expanded-01', '20261025-T30-combo-01']
assert not set(post) & {r['run'] for r in ledger}
assert len({r['run'] for r in ledger}) == len(ledger)
ledger_costs = []
for run in [r['run'] for r in ledger] + post:
    costs = []
    for path in sorted((ROOT / 'runs' / run).glob('*.jsonl')):
        if path.name in {'budget.jsonl', 'events.jsonl'}:
            continue
        costs.extend(Decimal(str(r['cost_cny'])) for r in records(path) if 'cost_cny' in r)
    ledger_costs.append({'run': run, 'records': len(costs), 'cny': str(sum(costs))})
result['cost_ledger'] = ledger_costs
result['cost_scope'] = {'old_physical_cny': str(sum(Decimal(r['cny']) for r in ledger_costs[:-3])),
                        'known_total_cny': str(sum(Decimal(r['cny']) for r in ledger_costs)),
                        'rounded_ledger_total_cny': str(sum(Decimal(r['amount']) for r in ledger) +
                                                       sum(Decimal(r['cny']) for r in ledger_costs[-3:])),
                        'excluded': ['U2', 'requests without returned usage/cost',
                                     'budget/events duplicate accounting']}
for cell in ['SQL-L1plus', 'SQL-L3a']:
    result.setdefault('ontology_run_costs', {})[cell] = sum(
        Decimal(str(r['cost_cny'])) for r in source('20261025-T22b-l1plus-l3a-03', cell).values())
result['ontology_cost_ratio'] = float(result['ontology_run_costs']['SQL-L3a'] /
                                      result['ontology_run_costs']['SQL-L1plus'])
result['main_cost_per_attempt'] = {
    cell: sum(source(r['source_run'], cell)[r['qid'], r['rep']]['cost_cny']
              for r in rs) / len(rs) for cell, rs in main.items()}

# Recount both disjoint entry sets, not just the displayed numerator 46.
correspondence = read(ROOT / 'reports/validation/l1plus-l3a-correspondence.md')
entries = [line.split('|')[1:-1] for line in correspondence.splitlines()
           if re.match(r'\| (general_rules|clarifications|concepts|aliases|hierarchies) \|', line)]
formal = {r[1].strip() for r in entries if r[2].strip() == '形式化'}
annotation = {r[1].strip() for r in entries if r[2].strip() == '注解保留'}
missed = json.loads(read(ROOT / 'reports/validation/l3a-ontology/missed.json'))
possible = set(missed['formalizable_annotation_entries'])
assert formal == set(missed['formal_entries']) and possible <= annotation
assert not formal & possible and len(formal | annotation) == len(entries) == 109
result['ontology_entries'] = {'formalized': len(formal), 'formalizable_annotations': len(possible),
                              'disjoint_union': len(formal | possible), 'total': len(entries),
                              'fraction': len(formal | possible) / len(entries)}

# Parquet metadata and bounded batches: no database open and no SQL execution.
parquet_counts = []
for path in sorted((DATA / 'parquet').glob('*.parquet')):
    pf = pq.ParquetFile(path)
    parquet_counts.append({'table': path.stem, 'columns': pf.metadata.num_columns,
                           'rows': pf.metadata.num_rows})
result['dataset'] = {'tables': len(parquet_counts), 'columns': sum(r['columns'] for r in parquet_counts),
                     'rows': sum(r['rows'] for r in parquet_counts), 'per_table': parquet_counts}
product = pq.read_table(DATA / 'parquet/DimProduct.parquet', columns=['ProductKey'])
products = set(product.column(0).to_pylist())
fact = pq.ParquetFile(DATA / 'parquet/FactOnlineSales.parquet')
orphan = total = 0
for batch in fact.iter_batches(columns=['ProductKey'], batch_size=262144):
    keys = batch.column(0).to_pylist()
    total += len(keys)
    orphan += sum(k not in products for k in keys)
assert total == fact.metadata.num_rows
result['orphan_product_rows'] = {'orphan': orphan, 'total': total, 'fraction': orphan / total}
for table in ['DimStore', 'DimProduct', 'FactOnlineSales']:
    path = DATA / 'parquet' / (table + '.parquet')
    inputs['$SEMDEBT_DATA_DIR/parquet/' + path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
store = pq.read_table(DATA / 'parquet/DimStore.parquet', columns=['StoreType'])
result['store_types'] = dict(Counter(store.column(0).to_pylist()))

# Frozen rendering: count only the Turtle string, not base YAML enum mentions.
system = read(DATA / 't31-v7-census-20261030/frozen-inputs/semantic-v1.6-l1plus/SQL-L3a-system.txt')
context = yaml.safe_load(system.split('```yaml\n', 1)[1].split('\n```', 1)[0])
turtle = context['ontology_turtle'].splitlines()
result['scenario_rendering'] = {'H10_lines': sum('H10' in line for line in turtle),
                                'related_lines': sum(bool(re.search('H10|Actual|Budget|Forecast|ScenarioKey', line))
                                                     for line in turtle)}

# Exact finite discrete bootstrap, resampling all 20 questions with 3 reps together.
moved = {'Q03', 'Q10', 'Q30', 'Q47', 'Q51', 'Q58', 'Q72'}
ids = {q for q in unique if questions[q]['labels']['semantic_dependency']['primary'] == '可从数据发现'} - moved
assert len(ids) == 20
sums = {}
for cell in ['SQL-L0', 'SQL-L1']:
    sums[cell] = {q: sum(r['content_correct'] for r in main[cell] if r['qid'] == q) for q in ids}
differences = Counter(sums['SQL-L1'][q] - sums['SQL-L0'][q] for q in ids)
distribution = {0: 1}
for _ in ids:
    next_distribution = defaultdict(int)
    for a, na in distribution.items():
        for b, nb in differences.items():
            next_distribution[a+b] += na*nb
    distribution = next_distribution
weight = len(ids) ** len(ids)
assert sum(distribution.values()) == weight

def quantile(numerator):
    seen = 0
    for value, count in sorted(distribution.items()):
        seen += count
        if seen * 40 >= numerator * weight:
            return value / (3 * len(ids))

result['moved_L0_L1'] = {'questions': len(ids), 'L0_correct': sum(sums['SQL-L0'].values()),
                        'L1_correct': sum(sums['SQL-L1'].values()), 'attempts': 3 * len(ids),
                        'difference': sum(k*v for k, v in differences.items()) / (3 * len(ids)),
                        'exact_bootstrap_interval': [quantile(1), quantile(39)]}

for model in ['flash', 'pro']:
    run = '20261018-T12-pilot-' + model + '-01'
    rs = records(ROOT / 'runs' / run / 'SQL-L1.jsonl')
    pilot_ids = {r['qid'] for r in rs}
    # T12 used the frozen eval-v1.1 low-discrimination registry, before later labels.
    bank = {}
    for name in ['cube_100', 'new']:
        path = 'questions/' + name + '.yaml'
        raw = subprocess.check_output(['git', '-C', str(EVAL), 'show', 'eval-v1.1:' + path])
        inputs['eval@eval-v1.1/' + path] = hashlib.sha256(raw).hexdigest()
        bank.update({q['id']: q for q in yaml.safe_load(raw)['questions']})
    judge = {q for q in pilot_ids if bank[q]['scoring'] == 'judge'}
    low = {q for q in pilot_ids if bank[q]['labels']['low_discrimination']['criteria']}
    valid = pilot_ids - judge - low
    result.setdefault('model_pilot', {})[model] = {'questions': len(pilot_ids), 'judge': sorted(judge),
        'low': sorted(low), 'main_questions': len(valid),
        'main_attempts': sum(r['qid'] in valid for r in rs),
        'physical_cost_cny': sum(r['cost_cny'] for c in ['SQL-L1', 'SQL-R']
                                 for r in records(ROOT / 'runs' / run / (c + '.jsonl')))}
result['pro_flash_cost_ratio'] = result['model_pilot']['pro']['physical_cost_cny'] / result['model_pilot']['flash']['physical_cost_cny']

result['planning_pilot'] = {}
for cell in ['SQL-L0-P', 'SQL-L1-P']:
    rs = records(ROOT / 'runs/20261019-T21-pilot-01' / (cell + '.jsonl'))
    ids = {r['qid'] for r in rs}
    result['planning_pilot'][cell] = {'attempts': len(rs), 'questions': len(ids),
                                    'levels': dict(Counter(questions[q]['labels']['q_level'] for q in ids))}

result['brand_result_rows'] = []
for rep in [1, 2, 3]:
    path = DATA / f'runs-raw/20261019-T16-full-v14-json-01/JSON-L2/Q57_r{rep}_t0.exec.json'
    value = json.loads(read(path))
    result['brand_result_rows'].append(len(value['rows']))
# Confirm the six documented tutorial examples belong to tuning, without copying prompts.
text = read(ROOT / 'decisions/2026-10-23-blind-data-dir.md')
example_ids = set(re.search(r'（(Q60、Q12、Q78、Q82、Q50、Q49)）', text).group(1).split('、'))
assert all(questions[q]['split'] == 'tuning' for q in example_ids)
result['tutorial_examples'] = sorted(example_ids)
l0 = yaml.safe_load(read(ROOT / 'semantic/l0_map.yaml'))['relationships']
result['l0_relationships'] = {'kept': len(l0['kept']), 'dropped': len(l0['dropped']),
                              'kept_fraction': len(l0['kept']) / (len(l0['kept']) + len(l0['dropped']))}
text = read(ROOT / 'docs/design-v5-public.md')
assert '最多 8 步' in text
result['explorer_step_cap'] = 8
combo = [r for r in main['SQL-L1plus-tuned-instr'] if r['split'] == 'heldout']
result['combo_heldout'] = {'correct': sum(r['content_correct'] for r in combo), 'attempts': len(combo),
                          'wrong': sum(not r['content_correct'] for r in combo), 'one_attempt_pp': 100 / len(combo)}
result['answered_coverage_pct'] = 100 * 89 / 98
registry = json.loads(read(ROOT / 'reports/validation/t16-v14-8836110/coverage.json'))
json_covered = {r['qid'] for r in registry['rows'] if r['category'] == 'covered'}
result['coverage_outside'] = []
for cell in ['JSON-L2', 'SQL-L1.5S']:
    covered = json_covered if cell == 'JSON-L2' else {
        q for q in unique if questions[q]['summary_coverage'] == 'covered'}
    rs = [r for r in main[cell] if r['qid'] not in covered]
    result['coverage_outside'].append({
        'cell': cell, 'attempts': len(rs), 'has_result': sum(r['has_result'] for r in rs),
        'outcomes': dict(Counter('correct' if r['content_correct'] else 'wrong' if r['has_result']
                                 else r['historical_outcome'] for r in rs))})
result['widetable_deltas'] = {}
for split in ['all', 'heldout']:
    sub = {cell: [r for r in main[cell] if split == 'all' or r['split'] == split]
           for cell in ['SQL-L1', 'SQL-L1.5W']}
    result['widetable_deltas'][split] = (
        sum(r['content_correct'] for r in sub['SQL-L1.5W']) / len(sub['SQL-L1.5W']) -
        sum(r['content_correct'] for r in sub['SQL-L1']) / len(sub['SQL-L1']))
result['approved_rule_ids'] = sorted(set(re.findall(r'\bR\d+\b', read(ROOT / 'reports/validation/reference-and-presentation-review.md'))),
                                     key=lambda v: int(v[1:]))
assert result['approved_rule_ids'] == ['R' + str(i) for i in range(1, 12)]
checklist = read(ROOT / 'reports/midterm/v7-number-sources.md')
expected_checklist = subprocess.check_output(['git', '-C', str(ROOT), 'show',
    result['reviewed_head'] + ':reports/midterm/v7-number-sources.md']).decode()
assert checklist == expected_checklist
assert result['bank_counts'] == {'cube_100': 100, 'new': 22, 'total': 122}
assert result['dataset']['tables'] == 25 and result['dataset']['columns'] == 244
assert result['dataset']['rows'] == 34326191
assert result['orphan_product_rows']['orphan'] == 1715380 and total == 12627608
assert result['ontology_entries']['disjoint_union'] == 46
assert result['scenario_rendering'] == {'H10_lines': 46, 'related_lines': 81}
assert result['moved_L0_L1']['exact_bootstrap_interval'] == [0, .3]
assert result['brand_result_rows'] == [11, 11, 11]
assert all(v['main_questions'] == 19 and v['main_attempts'] == 57
           for v in result['model_pilot'].values())
for cell, expected in [('SQL-L0', (5.18, 2.03)), ('SQL-L1', (2.70, 2.51)), ('SQL-L2', (3.23, 2.76))]:
    values = result['exploration_ratios'][cell]
    assert (round(values['input'], 2), round(values['all_cold_cost'], 2)) == expected
assert abs(Decimal(result['cost_scope']['known_total_cny']) - Decimal('104.61022284')) < Decimal('.000000001')
result['validation'] = 'All stated numeric and input-identity assertions passed.'
result['source_sha256'] = inputs
out = ROOT / 'reports/recheck/v7-fixes.json'
out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n')
print('Offline recheck saved; model/API/query executions: 0')
