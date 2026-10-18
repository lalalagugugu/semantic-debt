#!/usr/bin/env python
"""Re-execute the public candidates against two immutable private-bank snapshots.

Only IDs, counts, diagnostics and hashes enter the main-repository report.
Raw SQL, rows and execution errors remain in the external data directory.
"""
import argparse
import ast
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import warnings

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import scorer
import validate_scorer as adapter


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def bank(path):
    questions = json.loads((path / 'questions/cube_100.yaml').read_text())['questions']
    manifest = json.loads((path / 'refs/MANIFEST.json').read_text())
    records = {r['result_path']: r for r in manifest['records']}
    loaded = {}
    for question in questions:
        refs, rules = [], []
        for ref in question['refs']:
            record = records[ref['result_path']]
            csv_path = path / ref['result_path']
            if digest(csv_path) != record['sha256']:
                raise ValueError('bank CSV hash differs from manifest')
            rows = []
            with csv_path.open(newline='') as stream:
                reader = csv.reader(stream)
                if next(reader) != [c['name'] for c in record['columns']]:
                    raise ValueError('bank CSV columns differ from manifest')
                for row in reader:
                    values = []
                    for value, column in zip(row, record['columns'], strict=True):
                        typ = column['type']
                        if value == '\\N': value = None
                        elif typ.startswith(('Array','Tuple','Map')): value = ast.literal_eval(value)
                        elif 'Int' in typ: value = int(value)
                        elif any(t in typ for t in ('Float','Decimal')): value = Decimal(value)
                        values.append(value)
                    rows.append(values)
            refs.append(rows)
            rules.append(ref.get('rules',question['rules']))
        loaded[int(question['id'][1:])] = (question,refs,rules)
    if set(loaded) != set(range(1,101)):
        raise ValueError('expected the complete external 100-question bank')
    return loaded


def scored(module, candidate, entry):
    question, refs, overrides = entry
    if question['scoring'] != 'deterministic':
        return {'outcome':'judge','reason':'examples_are_not_closed_answer_sets',
                'matched_ref':None,'sensitivity':None}
    if isinstance(candidate, scorer.ExecError):
        candidate = module.ExecError(candidate.message)
    # Sensitivity runs only after the formal wrong verdict is fixed. This
    # audit requests verdicts/reasons, not the optional numeric projection.
    diagnostic = module._sensitivity
    try:
        module._sensitivity = lambda *args: None
        result = asdict(module.score_detailed(candidate,refs,question['rules'],reference_rules=overrides))
    finally:
        module._sensitivity = diagnostic
    result.pop('sensitivity')
    if result['outcome'] == 'exec_error':
        result['reason_sha256'] = hashlib.sha256(result.pop('reason').encode()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-bank',type=Path,required=True)
    parser.add_argument('--current-bank',type=Path,required=True)
    parser.add_argument('--baseline-bank-revision',required=True)
    parser.add_argument('--current-bank-revision',required=True)
    parser.add_argument('--baseline-scorer',required=True)
    parser.add_argument('--historical-audit',type=Path,required=True)
    parser.add_argument('--raw-dir',type=Path)
    parser.add_argument('--candidate-cache',type=Path,help='rescore exactly one completed 600-record execution without opening a database')
    parser.add_argument('--cache-provenance',type=Path,help='completed audit containing the candidate-cache SHA256')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if bool(args.candidate_cache) != bool(args.cache_provenance):
        parser.error('candidate-cache and cache-provenance must be supplied together')
    if args.candidate_cache is None and args.raw_dir is None:
        parser.error('raw-dir is required to reexecute SQL')
    baseline, current = bank(args.baseline_bank), bank(args.current_bank)
    history = json.loads(args.historical_audit.read_text())
    historical = {(r['system'],r['question_id']):r for r in history['records']}
    if len(historical) != 600:
        raise ValueError('historical audit must contain 600 unique keys')
    source = subprocess.check_output(['git','show',f'{args.baseline_scorer}:harness/scorer.py'],cwd=ROOT,text=True)
    old = types.ModuleType('presentation_baseline_scorer')
    old.__file__ = str(ROOT/'harness/scorer.py')
    sys.modules[old.__name__] = old
    exec(compile(source,old.__file__,'exec'),old.__dict__)
    for dependency in ('harness/selection.py','harness/value_units.py'):
        if subprocess.check_output(['git','show',f'{args.baseline_scorer}:{dependency}'],cwd=ROOT) != (ROOT/dependency).read_bytes():
            raise ValueError('baseline scorer dependencies must be identical')
    eval_dir = Path(os.environ['SEMDEBT_EVAL_DIR'])
    data_dir = Path(os.environ['SEMDEBT_DATA_DIR'])
    run_root = eval_dir/'vendor/cube/published-runs'/adapter.RUN_ID
    systems = sorted(adapter.SYSTEM_LABELS)
    expected = {(s,q) for s in systems for q in range(1,101)}
    if set(historical) != expected:
        raise ValueError('historical candidate keys differ')
    if args.candidate_cache is not None:
        provenance = json.loads(args.cache_provenance.read_text())
        cache_sha = digest(args.candidate_cache)
        completed = [r for r in provenance['rounds'] if r['executed']==600 and r['raw_candidates_sha256']==cache_sha]
        if len(completed)!=1:
            raise ValueError('candidate cache is not a completed, unchanged 600-SQL execution')
        records=[];seen=set()
        with args.candidate_cache.open() as stream:
            for line in stream:
                saved=json.loads(line);key=saved['system'],saved['question_id']
                if key in seen or key not in expected:
                    raise ValueError('duplicate or unexpected candidate key')
                seen.add(key);qid=key[1]
                candidate=scorer.ExecError(saved['error']) if saved['error'] else saved['rows']
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore',RuntimeWarning)
                    row={'system':key[0],'question_id':qid,
                         'baseline_scorer_result':scored(old,candidate,baseline[qid]),
                         'baseline_bank_result':scored(scorer,candidate,baseline[qid]),
                         'current_bank_result':scored(scorer,candidate,current[qid]),
                         'g0_outcome':historical[key]['historical_clean'],
                         'strict':historical[key]['strict'],'analytical':historical[key]['analytical']}
                records.append(row)
                if len(records)%10==0:print('cache rescored',len(records),'/600',flush=True)
        if seen!=expected or len(records)!=600:
            raise ValueError('cache must contain exactly all 600 candidates')
        result={'run_utc':datetime.now(timezone.utc).isoformat(),'sql_executed':0,
                'raw_candidates_sha256':cache_sha,'cache_provenance_sha256':digest(args.cache_provenance),
                'scorer_sha256':digest(ROOT/'harness/scorer.py'),
                'baseline_scorer_commit':args.baseline_scorer,
                'baseline_bank_commit':args.baseline_bank_revision,
                'current_bank_commit':args.current_bank_revision,'records':records}
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print('PASS: 600 immutable cached executions rescored; SQL executed 0',flush=True)
        return
    args.raw_dir.mkdir(parents=True,exist_ok=False)
    from chdb import session
    output = {'run_utc':datetime.now(timezone.utc).isoformat(),
              'scorer_sha256':digest(ROOT/'harness/scorer.py'),
              'baseline_scorer_sha256':hashlib.sha256(source.encode()).hexdigest(),
              'baseline_scorer_commit':args.baseline_scorer,
              'baseline_bank_commit':args.baseline_bank_revision,
              'current_bank_commit':args.current_bank_revision,
              'historical_audit_sha256':digest(args.historical_audit),
              'runtime':{'max_threads':1,'max_execution_time':30,'reset_after_each_error':True,'numeric_sensitivity_projection':False},
              'records':[], 'rounds':[]}
    first = {}
    for label, entries in (('baseline_bank',baseline),('current_bank',current)):
        raw_path = args.raw_dir/(label+'.jsonl')
        records=[];resets=0
        sess=adapter.open_session(session,data_dir/'chdb-eval')
        try:
            with raw_path.open('x') as raw:
                for system in systems:
                    for qid in range(1,101):
                        sql=adapter.load_json(run_root/system/f'q{qid:02d}.json')['sql']
                        candidate=adapter.execute_rows(sess,sql)
                        failed=isinstance(candidate,scorer.ExecError)
                        saved={'system':system,'question_id':qid,'error':candidate.message if failed else None,
                               'rows':None if failed else candidate}
                        raw.write(json.dumps(saved,ensure_ascii=False)+'\n');raw.flush()
                        if failed:
                            sess=adapter.reset_session(sess,session,data_dir/'chdb-eval');resets+=1
                        with warnings.catch_warnings():
                            warnings.simplefilter('ignore',RuntimeWarning)
                            result=scored(scorer,candidate,entries[qid])
                            row={'system':system,'question_id':qid,'result':result,
                                 'candidate_width':len(candidate[0]) if not failed and candidate else 0,
                                 'candidate_rows':len(candidate) if not failed else None,
                                 'candidate_sha256':hashlib.sha256(json.dumps(saved,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
                                 'strict':historical[system,qid]['strict'], 'analytical':historical[system,qid]['analytical'],
                                 'g0_outcome':historical[system,qid]['historical_clean']}
                            if label=='baseline_bank':
                                row['baseline_scorer_result']=scored(old,candidate,entries[qid])
                                row['current_bank_on_same_execution']=scored(scorer,candidate,current[qid])
                                first[system,qid]=row
                            else:
                                row['baseline_bank_on_same_execution']=scored(scorer,candidate,baseline[qid])
                                row['same_execution_output']=row['candidate_sha256']==first[system,qid]['candidate_sha256']
                        records.append(row)
                        if len(records)%10==0:
                            print(label,len(records),'/600',flush=True)
        finally:
            sess.close()
        output['rounds'].append({'label':label,'executed':len(records),'session_resets':resets,
                                 'raw_candidates_sha256':digest(raw_path),
                                 'counts':dict(Counter(r['result']['outcome'] for r in records))})
        for row in records: row['round']=label
        output['records'].extend(records)
        args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    if len(output['records']) != 1200:
        raise ValueError('both complete 600-execution rounds required')
    print(json.dumps(output['rounds'],ensure_ascii=False),flush=True)


if __name__=='__main__':main()
