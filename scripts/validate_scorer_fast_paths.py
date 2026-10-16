#!/usr/bin/env python
"""Compare every ScoreResult field on the same 600 retained executions.

Hold the original public reference contract fixed to isolate scorer changes.
The revised private-bank reference impact is a separate audit. No question,
SQL, result row, or execution-error message is written to this report.
"""
from dataclasses import asdict
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
    args = parser.parse_args()
    eval_dir = Path(os.environ['SEMDEBT_EVAL_DIR'])
    data_dir = Path(os.environ['SEMDEBT_DATA_DIR'])
    audit = json.loads(args.candidate_audit.read_text())
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
            rules[qid], references[qid] = rule, reference
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
              'scope': 'fixed original public references/contract; revised-bank effects audited separately',
              'records_compared': len(records), 'excluded_records': sum(r['before']['outcome'] == 'excluded' for r in records),
              'verdict_changes': sum(r['before']['outcome'] != r['after']['outcome'] for r in records),
              'diagnostic_changes': sum(r['before'] != r['after'] for r in records), 'records': records}
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: output[k] for k in ('records_compared', 'excluded_records', 'verdict_changes', 'diagnostic_changes')}))
    if output['diagnostic_changes']:
        raise SystemExit('scorer output changed')


if __name__ == '__main__':
    main()
