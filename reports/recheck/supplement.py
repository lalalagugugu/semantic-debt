"""Read-only checks for inherited v6 numbers; no model or query execution."""
import csv
import hashlib
import json
import os
import re
import statistics
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path(os.environ['SEMDEBT_DATA_DIR'])
OUT = ROOT / 'reports/recheck'
base = json.loads((OUT / 'independent.json').read_text())
hashes = {}


def read(path):
    raw = path.read_bytes()
    name = ('$SEMDEBT_DATA_DIR/' + str(path.relative_to(PRIVATE))
            if path.is_relative_to(PRIVATE) else str(path.relative_to(ROOT)))
    hashes[name] = hashlib.sha256(raw).hexdigest()
    return raw.decode()


def lines(path):
    return [json.loads(s) for s in read(path).splitlines() if s]


result = {}
main_ids = {r['qid'] for r in lines(ROOT / 'runs/20261031-T31-v5-rulings-01/SQL-L1.jsonl') if not r['low']}
audit = list(csv.DictReader(read(ROOT / 'reports/midterm/tool-audit.csv').splitlines()))
result['tools'] = {}
for cell in ['SQL-L0-E', 'SQL-L1-E', 'SQL-L2-E']:
    sources = base['original_logs'][cell]['source_runs']
    original = {}
    for source in sources:
        for r in lines(ROOT / 'runs' / source / (cell + '.jsonl')):
            original[(r['qid'], r['rep'])] = r
    calls = {}
    for (q, rep), r in original.items():
        if q not in main_ids:
            continue
        for step in r['steps']:
            for c in step['tool_calls']:
                calls[(q, rep, step['call'], c['k'])] = hashlib.sha256(c['query'].encode()).hexdigest()
    selected = [r for r in audit if r['unit'] == cell and r['qid'] in main_ids]
    for a in selected:
        assert calls[(a['qid'], int(a['rep']), int(a['call']), int(a['k']))] == a['query_sha256']
    assert len(selected) == len(calls)
    result['tools'][cell] = {'calls': len(calls), 'per_attempt': len(calls) / 294,
                              'purposes': dict(Counter(a['purpose'] for a in selected))}

result['first_execution'] = {}
result['first_delivery'] = {}
for cell in base['original_logs']:
    original = {}
    physical = []
    for source in base['original_logs'][cell]['source_runs']:
        for r in lines(ROOT / 'runs' / source / (cell + '.jsonl')):
            original[(source, r['qid'], r['rep'])] = r
            if r['scoring'] == 'deterministic':
                physical.append(r)
    chosen = [original[(r['source_run'], r['qid'], r['rep'])]
              for r in lines(ROOT / 'runs/20261031-T31-v5-rulings-01' / (cell + '.jsonl')) if not r['low']]
    first_error = sum(r['first'] == 'exec_error' for r in physical)
    result['first_execution'][cell] = {'attempts': len(physical), 'exec_error': first_error,
                                      'rate': first_error / len(physical)}
    result['first_delivery'][cell] = {'attempts': len(chosen),
                                     'correct': sum(r['first'] == 'correct' for r in chosen)}

result['historical_tokens'] = {}
for cell in ['SQL-L0', 'SQL-L1c', 'SQL-L1']:
    rs = lines(ROOT / 'runs/20261018-T13-sql-direct-01' / (cell + '.jsonl'))
    values = [r['turns'][0]['usage']['prompt_tokens'] for r in rs]
    text = read(PRIVATE / 'v7-eval-20261030' / (cell + '-context.txt'))
    cjk = sum('\u4e00' <= c <= '\u9fff' or '\uff00' <= c <= '\uffef' for c in text)
    result['historical_tokens'][cell] = {'requests': len(values), 'min': min(values), 'max': max(values),
                                       'mean': statistics.mean(values), 'characters': len(text),
                                       'heuristic_tokens': round(.6 * cjk + .3 * (len(text) - cjk)),
                                       'system_hashes': sorted({r['system_sha256'] for r in rs})}

source = yaml.safe_load(read(ROOT / 'semantic/source.yaml'))
plus = yaml.safe_load(read(ROOT / 'semantic/l1plus.yaml'))
result['semantic_counts'] = {'conventions': len(source['conventions']), 'metrics': len(source['metrics']),
                              'synonyms': len(source['synonyms']),
                              'plus': {k: len(plus[k]) for k in ['general_rules', 'clarifications', 'concepts', 'aliases', 'hierarchies']}}
correspondence = read(ROOT / 'reports/validation/l1plus-l3a-correspondence.md')
table = [line.split('|')[1:-1] for line in correspondence.splitlines() if re.match(r'\| (general_rules|clarifications|concepts|aliases|hierarchies) \|', line)]
result['correspondence'] = dict(Counter(row[2].strip() for row in table))
model = json.loads(read(ROOT / 'reports/validation/l3a-ontology/model.json'))
missed = json.loads(read(ROOT / 'reports/validation/l3a-ontology/missed.json'))
result['ontology_model'] = {'properties_without_domain_or_range': model['properties_without_domain_or_range']}
union = missed['formalizable_union']
result['ontology_missed'] = {
    'formalized_entries': len(missed['formal_entries']),
    'formalizable_annotation_entries': len(missed['formalizable_annotation_entries']),
    'questions': union['questions'], 'questions_n': union['n'], 'main_questions_n': union['n_main'],
    'historical_l3a_wrong': union['l3a_wrong'], 'historical_l1plus_wrong': union['l1plus_wrong'],
    'historical_l3a_correct': union['l3a_correct_attempts'],
}

d6 = list(csv.DictReader(read(ROOT / 'reports/validation/t31-v7-d6.csv').splitlines()))
assert {(r['qid'], int(r['rep'])) for r in d6} == {(r['qid'], r['rep']) for r in base['d6_records']}
result['d6'] = dict(Counter(r['category'] for r in d6))
d8 = list(csv.DictReader(read(ROOT / 'reports/validation/t31-v7-d8.csv').splitlines()))
assert len({r['ambiguity_id'] for r in d8}) == len(d8)
result['d8'] = dict(Counter(r['category'] for r in d8))
changes = list(csv.DictReader(read(ROOT / 'reports/validation/t31-v7-rescan-changes.csv').splitlines()))
result['rescan_changed_rows'] = len(changes)
result['explicit_user_changes'] = sum(r['explicit_user_ruling'] == 'True' for r in changes)
result['rescan_expanded_changes'] = len(changes) - result['explicit_user_changes']
review = list(csv.DictReader(read(PRIVATE / 't31-v7-census-20261030/claude-review/claude-labels-194.csv').splitlines()))
result['independent_positive_review_rows'] = len(review)
baseline = [r for p in sorted((ROOT / 'runs/20261030-T31-v5-census-03').glob('*.jsonl')) for r in lines(p) if not r['low']]
result['census_original_positive'] = sum(r['census_credit'] for r in baseline)
result['census_reviewed'] = sum(r['census_reviewed'] for r in baseline)
result['census_original_negative'] = result['census_reviewed'] - result['census_original_positive']
manifest = json.loads(read(ROOT / 'runs/20261028-T31-v4-rescore-02/manifest.json'))
result['archive'] = {'attempts': manifest['attempts'], 'exclusions': manifest['exclusions'],
                     'source_count_totals': dict(sum((Counter(r['counts']) for r in manifest['source_logs']), Counter()))}

# Reconcile the inherited ledger with physical logs, retaining its stated rounding.
ledger = list(csv.DictReader(read(ROOT / 'reports/midterm/v3-cost-runs.csv').splitlines()))
result['cost_ledger'] = []
for entry in ledger:
    physical = []
    for p in sorted((ROOT / 'runs' / entry['run']).glob('*.jsonl')):
        if p.name in {'budget.jsonl', 'events.jsonl'}:
            continue
        for r in lines(p):
            if 'cost_cny' in r:
                physical.append(r)
    result['cost_ledger'].append({'run': entry['run'], 'ledger_cny': float(entry['amount']),
                                  'physical_cny': sum(float(r['cost_cny']) for r in physical),
                                  'records': len(physical)})
result['cost_ledger_total'] = sum(r['ledger_cny'] for r in result['cost_ledger'])
result['physical_ledger_total'] = sum(r['physical_cny'] for r in result['cost_ledger'])
result['post_ledger_cost'] = {}
for run in ['20261025-T29-pilot-01', '20261026-T29-expanded-01', '20261025-T30-combo-01']:
    rs = [r for p in sorted((ROOT / 'runs' / run).glob('*.jsonl'))
          if p.name not in {'budget.jsonl', 'events.jsonl'} for r in lines(p) if 'cost_cny' in r]
    result['post_ledger_cost'][run] = sum(float(r['cost_cny']) for r in rs)
result['known_cost_total'] = result['physical_ledger_total'] + sum(result['post_ledger_cost'].values())

# Counts of frozen registry fields and the original external Markdown tables.
historic_source = yaml.safe_load(read(PRIVATE / 'v7-eval-20261030/snapshot/semantic/source.yaml'))
value_fields = []
for dataset in historic_source['datasets']:
    for col in dataset['columns']:
        for key, value in col.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                value_fields.append((dataset['name'], col['name'], key, len(value)))
result['value_field_counts'] = dict(Counter(k for _, _, k, _ in value_fields))
result['value_meaning_entries'] = sum(n for _, _, _, n in value_fields)
external = (Path(os.environ['SEMDEBT_EVAL_DIR']) / 'vendor/cube/fixtures/semantic_layer.md').read_text()
sections = {}
heading = ''
for line in external.splitlines():
    if line.startswith('## '):
        heading = line[3:]
    if line.startswith('|') and not re.match(r'\|\s*[-:]', line):
        sections[heading] = sections.get(heading, 0) + 1
result['external_table_rows_including_headers'] = sections
metric_text = external.split('## Key calculated metrics')[1].split('## Agent steering rules')[0]
result['external_metric_entries'] = len(re.findall(r'^- \*\*', metric_text, re.M)) + 2
result['external_agent_rules'] = len(re.findall(r'^\d+\.', external.split('## Agent steering rules')[1].split('## Time dimension helpers')[0], re.M))
private_report = read(PRIVATE / 'v7-eval-20261030/report.md')
example_table = private_report.split('| L1c 原文 |')[1].split('上表选了')[0]
result['d2_example_rows'] = sum(line.startswith('|') and not line.startswith('|---') for line in example_table.splitlines())
pilot = [r for cell in ['SQL-L0-P', 'SQL-L1-P'] for r in lines(ROOT / 'runs/20261019-T21-pilot-01' / (cell + '.jsonl'))]
result['planning_pilot'] = {'attempts': len(pilot), 'python_calls': sum(c['name'] == 'python' for r in pilot for s in r['steps'] for c in s['tool_calls'])}

# Recount the eight published outside-coverage groups, keeping labels fixed.
grouped_ids = {
    'JSON-L2': [['Q27', 'Q77', 'Q50', 'Q67', 'Q106'], ['Q57', 'Q36', 'Q47', 'Q71'], ['Q10', 'Q51', 'Q55']],
    'SQL-L1.5S': [['Q108', 'Q19'], ['Q27'], ['Q03'], ['Q61'], ['Q112']],
}
result['outside_groups'] = {}
for cell, groups in grouped_ids.items():
    outside = next(r for r in base['coverage'] if r['cell'] == cell and not r['covered'])['correct_qids']
    assert {q for group in groups for q in group} == set(outside)
    result['outside_groups'][cell] = [sum(outside[q] for q in group) for group in groups]

# Q19's quoted tolerance difference: compare recorded metric with frozen CSV.
import subprocess
import io
from decimal import Decimal
eval_dir = Path(os.environ['SEMDEBT_EVAL_DIR'])
reference = subprocess.check_output(['git', '-C', str(eval_dir), 'show', base['eval_commit'] + ':refs/cube/Q19-1.csv'])
ref_rows = list(csv.reader(io.StringIO(reference.decode())))[1:]
raw = json.loads(read(PRIVATE / 'runs-raw/20261019-T13-l15s-v14-01/SQL-L1.5S/Q19_r2_t1.exec.json'))
expected = {r[0]: Decimal(r[1]) for r in ref_rows}
assert raw['columns'][1]['name'] == '客单价'
result['Q19_max_relative_value_difference'] = float(max(abs(Decimal(str(r[1])) - expected[r[0]]) / abs(expected[r[0]]) for r in raw['rows']))

from pyarrow import parquet as pq
account = pq.read_table(PRIVATE / 'parquet/DimAccount.parquet', columns=['AccountKey'])
keys = account.column('AccountKey').to_pylist()
result['account_keys'] = {'rows': len(keys), 'min': min(keys), 'max': max(keys),
                         'key4': keys.count(4), 'key50': keys.count(50)}
plan = pq.read_table(PRIVATE / 'parquet/FactStrategyPlan.parquet', columns=['AccountKey'])
keys = plan.column('AccountKey').to_pylist()
result['plan_accounts'] = {'key4_rows': keys.count(4), 'key50_rows': keys.count(50)}
result['input_hashes'] = hashes
(OUT / 'supplement.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print('Supplement saved; query/model executions: 0')
