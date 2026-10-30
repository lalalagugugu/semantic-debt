"""Offline T20 calculation. Does not import report or harness calculators.

Run from the checkout root. Private inputs are resolved only through environment.
Output contains aggregates and question IDs, never question text or model output.
"""

import csv
import hashlib
import json
import os
import random
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/recheck'
RUN = ROOT / 'runs/20261031-T31-v5-rulings-01'
PRIVATE = Path(os.environ['SEMDEBT_DATA_DIR'])
EVAL = Path(os.environ['SEMDEBT_EVAL_DIR'])
REV = json.loads((RUN / 'manifest.json').read_text())['eval_commit']
SNAP = PRIVATE / 't31-v7-census-20261030/snapshots/20261031-T31-v5-rulings-01'
MOVED = {'Q03', 'Q10', 'Q30', 'Q47', 'Q51', 'Q58', 'Q72'}
INPUTS = {}


def read(path):
    data = path.read_bytes()
    if path.is_relative_to(PRIVATE):
        name = '$SEMDEBT_DATA_DIR/' + str(path.relative_to(PRIVATE))
    else:
        name = str(path.relative_to(ROOT))
    INPUTS[name] = hashlib.sha256(data).hexdigest()
    return data.decode()


def rows(path):
    return [json.loads(line) for line in read(path).splitlines() if line]


def mean(records, key='content_correct'):
    return sum(r[key] for r in records) / len(records)


def interval(values):
    # Resample whole questions, preserving their within-question repetitions.
    rng = random.Random(20261031)
    n = len(values)
    samples = sorted(sum(rng.choices(values, k=n)) / n for _ in range(10000))
    def percentile(p):
        x = p * (len(samples) - 1)
        lo = int(x)
        return samples[lo] + (samples[min(lo + 1, len(samples) - 1)] - samples[lo]) * (x - lo)
    return [percentile(.025), percentile(.975)]


def question_means(records, key='content_correct'):
    groups = defaultdict(list)
    for r in records:
        groups[r['qid']].append(r[key])
    return {q: statistics.mean(v) for q, v in sorted(groups.items())}


questions = {}
for name in ['questions/cube_100.yaml', 'questions/new.yaml']:
    data = subprocess.check_output(['git', '-C', str(EVAL), 'show', REV + ':' + name])
    INPUTS['$SEMDEBT_EVAL_DIR@' + REV + '/' + name] = hashlib.sha256(data).hexdigest()
    for q in yaml.safe_load(data)['questions']:
        # Explicit allowlist: no question text, SQL, or notes retained.
        questions[q['id']] = {
            'scoring': q['scoring'], 'split': q['split'],
            'summary_coverage': q['summary_coverage'],
            **{k: q['labels'][k] for k in ['q_level', 'persona']},
            'low': bool(q['labels']['low_discrimination']['criteria']),
            'semantic_dependency': q['labels']['semantic_dependency']['primary'],
            'complexity_source': q['labels']['complexity_source']['primary'],
        }

cells = {p.stem: rows(p) for p in sorted(RUN.glob('*.jsonl'))}
main = {}
for cell, records in cells.items():
    seen = set()
    for r in records:
        assert (r['qid'], r['rep']) not in seen, (cell, r['qid'], r['rep'])
        seen.add((r['qid'], r['rep']))
        q = questions[r['qid']]
        assert r['low'] == q['low'] and r['split'] == q['split']
        assert r['q_level'] == q['q_level'] and r['persona'] == q['persona']
        assert q['low'] or r['content_correct'] in (0, 1)
    main[cell] = [r for r in records if not questions[r['qid']]['low']]

result = {'eval_commit': REV, 'model_calls': 0, 'bootstrap_seed': 20261031,
          'bootstrap_replicates': 10000, 'cell_metrics': [], 'strata': []}
for cell, records in main.items():
    for split in ['all', 'heldout', 'tuning']:
        sub = [r for r in records if split == 'all' or r['split'] == split]
        if not sub:
            continue
        qm = question_means(sub)
        outcomes = Counter('correct' if r['content_correct'] else
                           'wrong' if r['has_result'] else r['historical_outcome'] for r in sub)
        result['cell_metrics'].append({
            'cell': cell, 'split': split, 'questions': len(qm), 'attempts': len(sub),
            'correct': sum(r['content_correct'] for r in sub),
            'accuracy': mean(sub), 'interval': interval(list(qm.values())),
            'delivery': mean(sub, 'a'), 'outcomes': dict(outcomes),
            'all_repetitions_correct': sum(v == 1 for v in qm.values()),
            'all_three_correct': sum(v == 1 and sum(r['qid'] == q for r in sub) == 3
                                     for q, v in qm.items()),
        })
    for dimension in ['q_level', 'persona', 'semantic_dependency', 'complexity_source', 'summary_coverage']:
        for group in sorted({questions[r['qid']][dimension] for r in records}):
            sub = [r for r in records if questions[r['qid']][dimension] == group]
            result['strata'].append({'cell': cell, 'dimension': dimension, 'group': group,
                                     'attempts': len(sub), 'correct': sum(r['content_correct'] for r in sub),
                                     'accuracy': mean(sub)})

result['comparisons'] = []
pairs = [('SQL-L0', 'SQL-L1'), ('SQL-L0', 'SQL-R'), ('SQL-R', 'SQL-L1c'),
         ('SQL-L1', 'SQL-L1.5W'), ('SQL-L1', 'SQL-L1c'), ('SQL-L0', 'SQL-L0-E'),
         ('SQL-L1', 'SQL-L1-E'), ('SQL-L2', 'SQL-L2-E'), ('SQL-L1plus', 'SQL-L3a'),
         ('SQL-L1', 'SQL-L2'), ('SQL-L1', 'SQL-L1plus'),
         ('SQL-L1', 'SQL-L1-tuned'), ('SQL-L1', 'SQL-L1-tuned-instr'),
         ('SQL-L1-tuned-instr', 'SQL-L1plus-tuned-instr'),
         ('SQL-L1', 'SQL-L1plus-tuned-instr'),
         ('SQL-L1plus', 'SQL-L1plus-tuned-instr'),
         *[('SQL-L1', 'SQL-L1-T' + n) for n in ['2', '3', '4']]]
for left, right in pairs:
    for split in ['all', 'heldout', 'tuning']:
        a = question_means([r for r in main[left] if split == 'all' or r['split'] == split])
        b = question_means([r for r in main[right] if split == 'all' or r['split'] == split])
        common = sorted(a.keys() & b.keys())
        if not common:
            continue
        diff = [b[q] - a[q] for q in common]
        result['comparisons'].append({'left': left, 'right': right, 'split': split,
                                      'questions': len(common), 'delta': statistics.mean(diff),
                                      'interval': interval(diff)})

result['d3'] = []
for moved in [False, True]:
    for dependency in ['可从数据发现', '只能由业务告知']:
        ids = {q for q, labels in questions.items() if not labels['low'] and
               labels['scoring'] == 'deterministic' and
               ('只能由业务告知' if moved and q in MOVED else labels['semantic_dependency']) == dependency}
        for cell in ['SQL-L0', 'SQL-L0-E', 'SQL-L1', 'SQL-L1-E']:
            sub = [r for r in main[cell] if r['qid'] in ids]
            result['d3'].append({'moved': moved, 'dependency': dependency, 'cell': cell,
                                 'questions': len(ids), 'attempts': len(sub),
                                 'correct': sum(r['content_correct'] for r in sub), 'accuracy': mean(sub)})
        for left, right in [('SQL-L0', 'SQL-L0-E'), ('SQL-L0', 'SQL-L1'), ('SQL-L1', 'SQL-L1-E')]:
            a = question_means([r for r in main[left] if r['qid'] in ids])
            b = question_means([r for r in main[right] if r['qid'] in ids])
            diff = [b[q] - a[q] for q in sorted(a)]
            result['d3'].append({'moved': moved, 'dependency': dependency, 'left': left,
                                 'right': right, 'delta': statistics.mean(diff), 'interval': interval(diff)})

coverage = {r['qid']: r['category'] for r in json.loads(read(ROOT / 'reports/validation/t16-v14-8836110/coverage.json'))['rows']}
result['coverage'] = []
coverage_sets = {}
for cell in ['JSON-L2', 'SQL-L1.5S']:
    for covered in [True, False]:
        ids = {q for q, label in questions.items() if
               (coverage.get(q) == 'covered' if cell == 'JSON-L2' else label['summary_coverage'] == 'covered') == covered}
        sub = [r for r in main[cell] if r['qid'] in ids]
        if covered:
            coverage_sets[cell] = {r['qid'] for r in sub}
        counts = Counter('correct' if r['content_correct'] else 'wrong' if r['has_result'] else r['historical_outcome'] for r in sub)
        compared = {}
        for baseline in ['SQL-L1', 'SQL-L2', 'SQL-L1.5W']:
            base = [r for r in main[baseline] if r['qid'] in ids]
            compared[baseline] = mean(base)
        result['coverage'].append({'cell': cell, 'covered': covered,
                                   'questions': len({r['qid'] for r in sub}), 'attempts': len(sub),
                                   'accuracy': mean(sub), 'outcomes': dict(counts),
                                   'correct_qids': dict(Counter(r['qid'] for r in sub if r['content_correct'])),
                                   'baselines': compared})
coverage_sets['intersection'] = coverage_sets['JSON-L2'] & coverage_sets['SQL-L1.5S']
result['coverage_comparisons'] = []
result['coverage_intersection'] = {}
for label, ids in coverage_sets.items():
    if label == 'intersection':
        for cell in ['SQL-L1', 'SQL-L2', 'SQL-L1.5S', 'JSON-L2']:
            sub = [r for r in main[cell] if r['qid'] in ids]
            result['coverage_intersection'][cell] = {'correct': sum(r['content_correct'] for r in sub), 'attempts': len(sub)}
    pairs = [('SQL-L1.5S', 'JSON-L2')] if label == 'intersection' else [('SQL-L1', label), ('SQL-L1', 'SQL-L2')]
    for left, right in pairs:
        a = question_means([r for r in main[left] if r['qid'] in ids])
        b = question_means([r for r in main[right] if r['qid'] in ids])
        diff = [b[q] - a[q] for q in sorted(ids)]
        result['coverage_comparisons'].append({'coverage': label, 'left': left, 'right': right,
                                                'delta': statistics.mean(diff), 'interval': interval(diff)})

equiv = {r['qid']: r['content_equivalent'] for r in json.loads(read(SNAP / 'd4-content-equivalence-audit.json'))}
first = [r for r in main['SQL-L1plus'] if r['rep'] == 1]
selected = [r for r in first if equiv[r['qid']]]
result['d4'] = {'baseline_n': len(first), 'baseline_correct': sum(r['content_correct'] for r in first),
                'selected_n': len(selected), 'selected_correct': sum(r['content_correct'] for r in selected),
                'blocked_wrong': [r['qid'] for r in first if not equiv[r['qid']] and not r['content_correct']],
                'blocked_correct': [r['qid'] for r in first if not equiv[r['qid']] and r['content_correct']]}
confidence = rows(ROOT / 'runs/20261023-T19c-confidence-01/confidence.jsonl')
l1 = {(r['qid'], r['rep']): r for r in main['SQL-L1']}
result['confidence'] = dict(Counter((r['tier'] or 'unparsed') for r in confidence if (r['qid'], r['rep']) in l1))
confident = [l1[(r['qid'], r['rep'])] for r in confidence if r['tier'] == 'A' and (r['qid'], r['rep']) in l1]
result['confidence_selected'] = {'attempts': len(confident), 'correct': sum(r['content_correct'] for r in confident)}
plus = {(r['qid'], r['rep']): r for r in main['SQL-L1plus']}
result['d6_records'] = [{'qid': r['qid'], 'rep': r['rep'], 'has_result': r['has_result']}
                        for r in main['SQL-L3a'] if plus[(r['qid'], r['rep'])]['content_correct'] and not r['content_correct']]
result['combo_errors'] = [{'qid': r['qid'], 'rep': r['rep'], 'has_result': r['has_result']}
                          for r in main['SQL-L1plus-tuned-instr'] if not r['content_correct']]

# Only category/note of private decisions are inspected; notes never leave memory.
decisions = json.loads(read(SNAP / 'codex-decisions.json'))
result['covered_error_categories'] = {}
for cell in ['JSON-L2', 'SQL-L1.5S']:
    counts = Counter()
    missing = []
    for r in main[cell]:
        covered = coverage[r['qid']] == 'covered' if cell == 'JSON-L2' else questions[r['qid']]['summary_coverage'] == 'covered'
        if covered and not r['content_correct']:
            key = '|'.join([r['source_run'], cell, r['qid'], str(r['rep'])])
            d = decisions.get(key)
            if d:
                counts[d['category']] += 1
            else:
                missing.append([r['qid'], r['rep'], r['historical_outcome']])
    result['covered_error_categories'][cell] = {'categories': dict(counts), 'without_private_decision': missing}

result['original_logs'] = {}
for cell, records in main.items():
    original = {}
    all_records = []
    for source in sorted({r['source_run'] for r in records}):
        path = ROOT / 'runs' / source / (cell + '.jsonl')
        for r in rows(path):
            all_records.append(r)
            original[(source, r['qid'], r['rep'])] = r
    chosen = [original[(r['source_run'], r['qid'], r['rep'])] for r in records]
    tools = []
    first_outcomes = Counter()
    for r in chosen:
        first = r.get('first')
        first_outcomes[str(first.get('outcome') if isinstance(first, dict) else first)] += 1
        for step in r.get('steps', []):
            tools.extend(step.get('tool_calls', []))
    result['original_logs'][cell] = {
        'source_runs': sorted({r['source_run'] for r in records}),
        'main_cost': sum(r['cost_cny'] for r in chosen),
        'physical_cost': sum(r['cost_cny'] for r in all_records),
        'physical_attempts': len(all_records),
        'first_outcomes': dict(first_outcomes),
        'tool_calls': sum(r.get('n_tool_calls', 0) for r in chosen),
        'step_tool_records': len(tools),
        'tool_executed': sum(r.get('n_tool_executed', 0) for r in chosen),
        'mean_steps': statistics.mean(r.get('n_steps', 0) for r in chosen),
        'fingerprints': sorted({t.get('system_fingerprint', '') for r in all_records for t in r['turns']}),
        'first_prompt_mean': statistics.mean(r['turns'][0]['usage']['prompt_tokens'] for r in chosen),
        'mean_prompt_total': statistics.mean(r['usage']['prompt_tokens'] for r in chosen),
    }

result['question_counts'] = dict(Counter(q['scoring'] for q in questions.values()))
result['low_qids'] = sorted(q for q, label in questions.items() if label['low'])
result['total_formal_attempts'] = sum(len(v) for v in cells.values())
result['total_main_attempts'] = sum(len(v) for v in main.values())
result['input_hashes'] = INPUTS
(OUT / 'independent.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'main_attempts': result['total_main_attempts'], 'formal_attempts': result['total_formal_attempts'],
                  'cell_metrics': len(result['cell_metrics']), 'strata': len(result['strata']),
                  'output_sha256': hashlib.sha256((OUT / 'independent.json').read_bytes()).hexdigest()}))
