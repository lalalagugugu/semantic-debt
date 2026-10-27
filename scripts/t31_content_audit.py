"""Audit manually declared T31 projections; this is not a v4 scorer.

All question-specific mappings and user feedback stay outside the repository.
No SQL execution, model calls, frozen-source changes, or production scoring.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.value_units import absolute_tolerance, quantize_tie
from harness.rescore import candidate_of
from scripts.rescore_t23 import frozen_bank


def number(value):
    return Decimal(str(value))


def evaluate(expr, row, table):
    if not isinstance(expr, list):
        return expr
    op, *args = expr
    if op == 'col':
        return row[args[0]]
    if op == 'lookup':
        key_col, key, value_col = args
        matches = [r[value_col] for r in table if str(r[key_col]) == str(key)]
        if len(matches) != 1:
            raise ValueError('lookup is not unique')
        return matches[0]
    values = [evaluate(a, row, table) for a in args]
    if op in ('add', 'sub', 'mul', 'div'):
        a, b = values
        if a is None or b is None:
            return None
        a, b = number(a), number(b)
        return {'add': lambda: a + b, 'sub': lambda: a - b,
                'mul': lambda: a * b, 'div': lambda: None if b == 0 else a / b}[op]()
    if op == 'if_eq':
        return values[2] if str(values[0]) == str(values[1]) else values[3]
    if op == 'id':
        return str(int(number(values[0])))
    if op == 'concat':
        return ' '.join(str(v).strip() for v in values)
    if op == 'name':
        name, key = values
        return str(int(number(key))) if name is None or 'Not Provided' in str(name) else ' '.join(str(name).split())
    if op == 'replace':
        return values[1].get(str(values[0]), values[0])
    if op == 'unknown':
        return None if values[0] in (None, '未知') else values[0]
    if op == 'roundint':
        return int(round(number(values[0])))
    if op == 'quarter':
        text = str(values[0])
        if not re.fullmatch(r'(?:2009 )?Q[1-4]', text):
            raise ValueError('unrecognized quarter')
        return text[-2:]
    if op == 'year_month':
        return f'{int(number(values[0])):04}-{int(number(values[1])):02}-01'
    if op == 'month':
        value, year = values
        names = 'January February March April May June July August September October November December'.split()
        if value in names:
            return names.index(value) + 1
        text = str(value)
        if re.fullmatch(r'\d{4}-\d{2}(?:-01)?', text):
            if int(text[:4]) != year:
                raise ValueError('month from a different year')
            return int(text[5:7])
        month = int(number(value))
        if not 1 <= month <= 12:
            raise ValueError('invalid month')
        return month
    raise ValueError(f'unsupported declared audit operation: {op}')


def project(table, specification):
    rows = []
    for view in specification:
        for row in table:
            condition = view.get('where')
            if condition and str(row[condition['column']]) not in condition['values']:
                continue
            rows.append([evaluate(e, row, table) for e in view['columns']])
    return rows


def equal(a, b, kind):
    if a is None or b is None:
        return a is b
    if kind == 'label':
        return str(a) == str(b)
    a, b = number(a), number(b)
    if kind == 'count':
        return a == b
    return abs(a - b) <= max(abs(b) * Decimal('.005'), number(absolute_tolerance(kind)))


def compare(candidate, reference, kinds, mode='complete', top_n=None):
    def index(rows):
        result = {}
        for row in rows:
            key = tuple(str(v) if v is not None else None for v in row[:1])
            if key in result:
                raise ValueError('declared identity is not unique')
            result[key] = row
        return result
    c, r = index(candidate), index(reference)
    identity_equal = set(c) == set(r)
    if mode == 'top_n':
        amount_column = kinds.index('amount')
        values = sorted((quantize_tie(row[amount_column], 'amount') for row in reference), reverse=True)
        cutoff = values[min(top_n, len(values)) - 1]
        mandatory = {k for k, row in r.items() if quantize_tie(row[amount_column], 'amount') > cutoff}
        identity_equal = (len(c) == min(top_n, len(r)) and set(c) <= set(r) and mandatory <= set(c)
                          and all(quantize_tie(row[amount_column], 'amount') >= cutoff for row in candidate))
        ordered = [quantize_tie(row[amount_column], 'amount') for row in candidate]
        identity_equal = identity_equal and ordered == sorted(ordered, reverse=True)
    mismatches, maxima = [], {}
    for key in c.keys() & r.keys():
        for i, kind in enumerate(kinds):
            a, b = c[key][i], r[key][i]
            if not equal(a, b, kind):
                mismatches.append({'identity': key, 'column': i, 'candidate': a, 'reference': b})
            if a is not None and b is not None and kind != 'label':
                maxima[str(i)] = max(maxima.get(str(i), Decimal(0)), abs(number(a) - number(b)))
    return {'identities_equal': identity_equal, 'normalized_values_equal': not mismatches,
            'all_compared_values_exact': all(v == 0 for v in maxima.values()) and not mismatches,
            'max_absolute_difference': maxima, 'mismatches': mismatches,
            'candidate_rows': len(candidate), 'reference_rows': len(reference)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    data = Path(os.environ['SEMDEBT_DATA_DIR'])
    source = args.input or data / 't31-content-audit-spec-reviewed.json'
    output = args.output or data / 't31-content-audit-reviewed.json'
    if ROOT == output.resolve() or ROOT in output.resolve().parents:
        raise ValueError('audit evidence must stay outside the repository')
    if output.exists():
        raise FileExistsError('preserve existing evidence: choose a new output')
    raw = source.read_bytes()
    spec = json.loads(raw)
    for attachment in spec.get('attachments', []):
        if hashlib.sha256(Path(attachment['path']).read_bytes()).hexdigest() != attachment['sha256']:
            raise ValueError('supporting evidence checksum mismatch')
    systems = {}
    for entry in spec['systems']:
        payload = Path(entry['path']).read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry['sha256']:
            raise ValueError('system material checksum mismatch')
        systems[entry['cell']] = entry
    logs, results = {}, []
    with frozen_bank(Path(os.environ['SEMDEBT_EVAL_DIR'])) as (questions, _, commit, archive):
        for item in spec['attempts']:
            log = ROOT / item['log']
            if log not in logs:
                payload = log.read_bytes()
                logs[log] = (hashlib.sha256(payload).hexdigest(),
                             {(r['qid'], r['rep']): r for r in map(json.loads, payload.splitlines())})
            rec = logs[log][1][item['qid'], item['rep']]
            if rec['system_sha256'] != item['system_sha256']:
                raise ValueError('attempt system checksum mismatch')
            folder = data / 'runs-raw' / item['raw_run'] / rec['cell']
            candidate = candidate_of(rec['turns'][-1], folder, item['qid'], item['rep'])
            if not isinstance(candidate, list):
                raise ValueError('expected a saved successful row result')
            reference = questions[item['qid']].refs[item.get('reference_index', 0)]
            c = project(candidate, item['candidate_views'])
            r = project(reference, item['reference_views'])
            evidence = compare(c, r, item['kinds'], item.get('mode', 'complete'), item.get('top_n'))
            checks = []
            for check in item.get('row_checks', []):
                checked_rows = candidate
                if condition := check.get('where'):
                    checked_rows = [row for row in candidate
                                    if str(row[condition['column']]) in condition['values']]
                failures = sum(not equal(evaluate(check['left'], row, candidate),
                                         evaluate(check['right'], row, candidate), check['kind']) for row in checked_rows)
                checks.append({'name': check['name'], 'checked_rows': len(checked_rows), 'failed_rows': failures})
            passed = evidence['identities_equal'] and evidence['normalized_values_equal'] and not any(x['failed_rows'] for x in checks)
            baseline_correct = rec['final']['outcome'] == 'correct'
            content_correct = baseline_correct or (passed and item['content_route'] == '候选确定性核验')
            assert not baseline_correct or content_correct, 'candidate content cannot revoke v2'
            results.append({**item, 'evidence': evidence, 'row_checks_result': checks,
                            'normalized_core_verified': passed, 'v2_correct': baseline_correct,
                            'candidate_content_correct': content_correct})
    keys = {(r['cell'], r['qid'], r['rep']) for r in results}
    if len(results) != 48 or len(keys) != 48:
        raise ValueError('expected 47 L1plus attempts and one separate tuned attempt')
    assert sum(r['candidate_content_correct'] for r in results) >= sum(r['v2_correct'] for r in results)
    result = {'eval_commit': commit, 'bank_archive_sha256': archive,
              'spec_sha256': hashlib.sha256(raw).hexdigest(),
              'source_log_sha256': {str(p.relative_to(ROOT)): v[0] for p, v in logs.items()},
              'systems': systems, 'attempts': results,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'routes': dict(Counter(r['content_route'] for r in results)),
              'model_calls': 0, 'cost_cny': 0,
              'limit': 'Human-declared column/meaning mappings; evidence audit only, not a generic implemented v4 rule.'}
    with output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({'attempts': len(results), 'verified': sum(r['normalized_core_verified'] for r in results),
                      'routes': result['routes']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
