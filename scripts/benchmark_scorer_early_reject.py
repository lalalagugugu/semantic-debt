#!/usr/bin/env python
"""Compare full scorer latency on synthetic large rows; no database or model."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
from pathlib import Path
import queue
import subprocess
import sys
import time
import types

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def worker(output, source, count, case):
    try:
        if source is None:
            from harness import scorer
        else:
            scorer=types.ModuleType('baseline_scorer')
            scorer.__file__=str(ROOT/'harness/scorer.py')
            sys.modules[scorer.__name__]=scorer
            exec(compile(source,scorer.__file__,'exec'),scorer.__dict__)
        if case=='null_mismatch':
            candidate=[('missing',f'row-{i}') for i in range(count)]
            reference=[(None,f'row-{i}') for i in range(count)]
        else:
            candidate=[('missing',i%97,i,i%11) for i in range(count)]
            reference=[(None,None if case=='numeric_projection_unequal' and i==0 else i%97,i) for i in range(count)]
        output.put({'status':'ready'})
        started=time.perf_counter()
        result=scorer.score_detailed(candidate,[reference],{'ordered':False,'top_n':None})
        output.put({'status':'completed','elapsed_seconds':time.perf_counter()-started,
                    'outcome':result.outcome,'reason':result.reason,'sensitivity':result.sensitivity})
    except Exception as error:
        output.put({'status':'error','error':repr(error)})


def measure(source, size, case, timeout):
    context=multiprocessing.get_context('spawn')
    output=context.Queue()
    process=context.Process(target=worker,args=(output,source,size,case))
    process.start()
    phase='input_construction'
    try:
        ready=output.get(timeout=30)
        if ready['status']!='ready':
            return ready
        phase='score_detailed'
        return output.get(timeout=timeout)
    except queue.Empty:
        return {'status':'timeout','phase':phase,'timeout_seconds':timeout if phase=='score_detailed' else 30}
    finally:
        process.join(0.5)
        if process.is_alive():
            process.terminate();process.join()
        output.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref',default='origin/main')
    parser.add_argument('--sizes',nargs='+',type=int,default=[100,2000,600000])
    parser.add_argument('--cases',nargs='+',choices=['null_mismatch','numeric_projection','numeric_projection_unequal'],default=['null_mismatch','numeric_projection','numeric_projection_unequal'])
    parser.add_argument('--timeout-seconds',type=float,default=10)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/validation/scorer_early_reject_performance.json')
    args=parser.parse_args()
    if min(args.sizes)<1 or args.timeout_seconds<=0:
        parser.error('sizes/timeouts must be positive')
    revision=subprocess.run(['git','rev-parse',args.baseline_ref],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
    baseline=subprocess.run(['git','show',f'{revision}:harness/scorer.py'],cwd=ROOT,text=True,capture_output=True,check=True).stdout
    records=[]
    for case in args.cases:
        for count in args.sizes:
            record={'case':case,'rows':count}
            for label,source in [('before',baseline),('after',None)]:
                record[label]=measure(source,count,case,args.timeout_seconds)
                print(json.dumps({'case':case,'rows':count,'implementation':label,**record[label]}),flush=True)
            if record['before']['status']==record['after']['status']=='completed':
                record['same_result']=all(record['before'][k]==record['after'][k] for k in ['outcome','reason','sensitivity'])
                if not record['same_result']:
                    raise ValueError('benchmark changed scorer result')
            records.append(record)
    result={'run_utc':datetime.now(timezone.utc).isoformat(),'baseline_commit':revision,
            'baseline_scorer_sha256':hashlib.sha256(baseline.encode()).hexdigest(),
            'current_scorer_sha256':hashlib.sha256((ROOT/'harness/scorer.py').read_bytes()).hexdigest(),
            'measurement':'full score_detailed; timer and scoring timeout exclude input construction; startup/construction have a separate 30-second limit; timeouts remain lower bounds',
            'records':records}
    args.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
