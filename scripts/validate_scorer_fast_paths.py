#!/usr/bin/env python
"""Compare every ScoreResult field on the same 600 retained executions.

Hold the original public reference contract fixed to isolate scorer changes.
The revised private-bank reference impact is a separate audit. No question,
SQL, result row, or execution-error message is written to this report.
"""
from dataclasses import asdict
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness import scorer
import validate_scorer as adapter


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def git_source(revision, path):
    return subprocess.run(['git', 'show', f'{revision}:{path}'], cwd=ROOT,
                          text=True, capture_output=True, check=True).stdout


def public_result(result):
    result = asdict(result)
    if result['outcome'] == 'exec_error':
        result['reason_sha256'] = hashlib.sha256(result.pop('reason').encode()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref', required=True)
    parser.add_argument('--candidate-audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--order-registry', type=Path, help='persisted original-reference order metadata from the bank')
    parser.add_argument('--allow-tie-improvements', action='store_true')
    parser.add_argument('--reexecute-candidates', action='store_true', help='execute the same 600 retained SQL statements in fresh chDB sessions')
    args = parser.parse_args()
    if args.allow_tie_improvements and args.order_registry is None:
        parser.error('tie-contract comparison requires --order-registry')
    eval_dir = Path(os.environ['SEMDEBT_EVAL_DIR'])
    data_dir = Path(os.environ['SEMDEBT_DATA_DIR'])
    audit = json.loads(args.candidate_audit.read_text())
    previous_records = {(r['system'], r['question_id']): r for r in audit['records']}
    raw = Path(audit['raw_candidates_path'])
    if digest(raw) != audit['raw_candidates_sha256'] or audit['executed_candidates'] != 600:
        raise ValueError('a completed, unchanged 600-execution audit is required')
    revision = subprocess.run(['git', 'rev-parse', args.baseline_ref], cwd=ROOT,
                              text=True, capture_output=True, check=True).stdout.strip()
    source = git_source(revision, 'harness/scorer.py')
    for dependency in ('harness/value_units.py', 'harness/selection.py'):
        if git_source(revision, dependency) != (ROOT / dependency).read_text():
            raise ValueError('comparison must hold scorer dependencies fixed')
    baseline = types.ModuleType('baseline_scorer')
    baseline.__file__ = str(ROOT / 'harness/scorer.py')
    sys.modules[baseline.__name__] = baseline
    exec(compile(source, baseline.__file__, 'exec'), baseline.__dict__)
    questions = json.loads((eval_dir / 'vendor/cube/text_to_sql_benchmark.json').read_text())['questions']
    order_records = {r['question_id']: r for r in json.loads(args.order_registry.read_text())['original_records']} if args.order_registry else {}
    references, rules = {}, {}
    from chdb import session
    sess = adapter.open_session(session, data_dir / 'chdb-eval')
    try:
        for question in sorted(questions, key=lambda q: int(q['id'])):
            qid = int(question['id'])
            if qid in adapter.EXCLUDED_QUESTION_IDS:
                continue
            rule = adapter.question_rules(qid, question['expected_sql'])
            reference, _, _ = adapter.stable_reference(sess, question['expected_sql'], qid, rule)
            if args.order_registry and rule['ordered']:
                declared = order_records[qid]
                sql_hash = hashlib.sha256(question['expected_sql'].strip().rstrip(';').encode()).hexdigest()
                if sql_hash != declared['sql_sha256'] or rule['reference_columns'] != declared['columns']:
                    raise ValueError('persisted original-reference ordering provenance differs')
                rule['order_by'] = declared['order_by']
            rules[qid], references[qid] = rule, reference
    finally:
        sess.close()
    if args.order_registry and {qid for qid, rule in rules.items() if rule['ordered']} != set(order_records):
        raise ValueError('persisted ordering registry does not cover exactly the ordered originals')
    input_raw_sha256 = digest(raw)
    session_resets = 0
    if args.reexecute_candidates:
        run_root = eval_dir / 'vendor/cube/published-runs' / adapter.RUN_ID
        folder = data_dir / 'rules-backfill' / ('ordered-ties-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        folder.mkdir(parents=True, exist_ok=False)
        retained = raw
        raw = folder / 'candidates.jsonl'
        sess = adapter.open_session(session, data_dir / 'chdb-eval')
        try:
            with retained.open() as previous, raw.open('x') as output:
                for line in previous:
                    key = json.loads(line)
                    qid, system = key['question_id'], key['system']
                    sql = adapter.load_json(run_root / system / f'q{qid:02d}.json')['sql']
                    candidate = adapter.execute_rows(sess, sql)
                    failed = isinstance(candidate, scorer.ExecError)
                    output.write(json.dumps({'system': system, 'question_id': qid,
                                             'error': candidate.message if failed else None,
                                             'rows': None if failed else candidate}, ensure_ascii=False) + '\n')
                    if failed:
                        sess = adapter.reset_session(sess, session, data_dir / 'chdb-eval')
                        session_resets += 1
                    if qid % 10 == 0:
                        print(f'reexecuted {system} Q{qid:02d}', flush=True)
        finally:
            sess.close()
    records, seen = [], set()
    for line in raw.open():
        candidate = json.loads(line)
        qid = candidate['question_id']
        key = candidate['system'], qid
        if key in seen:
            raise ValueError('duplicate candidate key')
        seen.add(key)
        result = {'system': key[0], 'question_id': qid}
        if qid in adapter.EXCLUDED_QUESTION_IDS:
            excluded = {'outcome': 'excluded', 'reason': 'published_reference_unavailable',
                        'matched_ref': None, 'sensitivity': None}
            result.update(before=excluded, after=excluded.copy())
        else:
            for label, module in (('before', baseline), ('after', scorer)):
                rows = module.ExecError(candidate['error']) if candidate['error'] else candidate['rows']
                start = time.perf_counter()
                scored = module.score_detailed(rows, [references[qid]], rules[qid])
                result[label] = public_result(scored)
                result[label + '_seconds'] = time.perf_counter() - start
        result['unchanged'] = result['before'] == result['after']
        records.append(result)
        if len(records) % 10 == 0:
            print(f'full ScoreResult compared {len(records)}/600', flush=True)
    expected = {(system, int(q['id'])) for system in {key[0] for key in seen} for q in questions}
    if len(records) != 600 or seen != expected or len({key[0] for key in seen}) != 6:
        raise ValueError('candidate audit must cover exactly six systems and 100 questions')
    output = {'run_utc': datetime.now(timezone.utc).isoformat(), 'baseline_commit': revision,
              'baseline_scorer_sha256': hashlib.sha256(source.encode()).hexdigest(),
              'current_scorer_sha256': digest(ROOT / 'harness/scorer.py'),
              'candidate_audit_sha256': digest(args.candidate_audit), 'raw_candidates_sha256': digest(raw),
              'scope': 'fixed original public reference rows; persisted order keys when supplied; revised-bank effects audited separately',
              'order_registry_sha256': digest(args.order_registry) if args.order_registry else None,
              'candidate_sql_reexecuted': args.reexecute_candidates, 'session_resets': session_resets,
              'input_raw_candidates_sha256': input_raw_sha256,
              'records_compared': len(records), 'excluded_records': sum(r['before']['outcome'] == 'excluded' for r in records),
              'verdict_changes': sum(r['before']['outcome'] != r['after']['outcome'] for r in records),
              'diagnostic_changes': sum(r['before'] != r['after'] for r in records), 'records': records}
    output['unexpected_verdict_changes'] = sum(r['before']['outcome'] != r['after']['outcome'] and
                                             (r['before']['outcome'], r['after']['outcome']) != ('wrong', 'correct') for r in records)
    output['wrong_to_correct'] = sum((r['before']['outcome'], r['after']['outcome']) == ('wrong', 'correct') for r in records)
    output['wrong_diagnostic_changes'] = sum(r['before']['outcome'] == r['after']['outcome'] == 'wrong' and r['before'] != r['after'] for r in records)
    output['previous_baseline_verdict_changes'] = sum(r['before']['outcome'] != previous_records[r['system'], r['question_id']]['baseline'] for r in records)
    output['before_counts'] = dict(Counter(r['before']['outcome'] for r in records))
    output['after_counts'] = dict(Counter(r['after']['outcome'] for r in records))
    comparable = [r for r in records if r['before']['outcome'] != 'excluded']
    for label in ('before', 'after'):
        output[label + '_strict_agreements'] = sum((r[label]['outcome'] == 'correct') == (previous_records[r['system'], r['question_id']]['strict'] == 'pass') for r in comparable)
        output[label + '_analytical_agreements'] = sum((r[label]['outcome'] == 'correct') == (previous_records[r['system'], r['question_id']]['analytical'] == 'pass') for r in comparable)
    output['comparable_records'] = len(comparable)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: output[k] for k in ('records_compared', 'excluded_records', 'verdict_changes', 'diagnostic_changes')}))
    if output['unexpected_verdict_changes'] or (output['diagnostic_changes'] and not args.allow_tie_improvements):
        raise SystemExit('scorer output changed')


if __name__ == '__main__':
    main()
