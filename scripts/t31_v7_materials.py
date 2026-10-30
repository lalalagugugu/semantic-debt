"""Hash-verified local materials for the user-authorized v7 residual census.

No model calls, query execution, or frozen-source edits. Full materials stay private.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import io
import subprocess
import tarfile
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness.prompt import parse_response
from scripts.rescore_t23 import frozen_bank, git

TAG='eval-v1.3'
COMMIT='5b65e0c450ba36d83707c00dc9443be16b08d086'
KEY_CELLS={'SQL-L1','SQL-L1-E','SQL-L1plus','SQL-L3a','SQL-L2','SQL-L2-E',
           'SQL-L1-tuned','SQL-L1-tuned-instr','SQL-L1plus-tuned-instr'}


def sha(b):return hashlib.sha256(b).hexdigest()
def key(r):return r['source_run'],r['cell'],r['qid'],int(r['rep'])
def read_csv(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def write_json(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')


def load_scores():
    directory=ROOT/'runs/20261028-T31-v4-rescore-02'
    return [json.loads(s) for p in sorted(directory.glob('*.jsonl')) for s in p.read_text().splitlines()]


def export_contexts(directory):
    """Reconstruct actual delivered system messages and require original hashes."""
    from render import common as common, context, l1plus
    from harness.prompt import system_message
    from harness.tuned_instructions import load, system_message as tuned
    from harness.agent_prompt import agent_system_message
    materials=json.loads((directory/'materials.json').read_text())
    main=Path(os.environ['SEMDEBT_MAIN_DIR'])
    output=[]
    for tag in sorted({m['semantic_tag'] for m in materials if m['cell'] in KEY_CELLS}):
        root=directory/'frozen-inputs'/tag
        root.mkdir(parents=True,exist_ok=True)
        raw=subprocess.check_output(['git','-C',str(main),'archive',tag,'semantic'])
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            archive.extractall(root,filter='data')
        common.SEMANTIC=root/'semantic'
        context.SEMANTIC=common.SEMANTIC
        l1plus.SEMANTIC=common.SEMANTIC
        for function in (common.source,common.metrics_file,common.l0_map,common.summary):
            function.cache_clear()
        for cell in sorted(KEY_CELLS):
            group=[m for m in materials if m['cell']==cell and m['semantic_tag']==tag]
            if not group:
                continue
            base=cell.removesuffix('-E')
            if base=='SQL-L1-tuned-instr':base='SQL-L1-tuned'
            rendered=common.dump_yaml(context.render_cell(base))
            syntax=(ROOT/'render/syntax'/('cube_sql.md' if base=='SQL-L2' else 'clickhouse_sql.md')).read_text()
            text=tuned(rendered,syntax,'yaml',load(root/'semantic/tuning/SQL-L1.instructions.yaml')) if cell.endswith('tuned-instr') else system_message(rendered,syntax)
            if cell.endswith('-E'):text=agent_system_message(text)
            digest=sha(text.encode())
            assert {m['system_sha256'] for m in group}=={digest},(tag,cell)
            path=root/(cell+'-system.txt')
            if path.exists():assert path.read_text()==text
            else:path.write_text(text)
            output.append(dict(cell=cell,tag=tag,semantic_commit=git(main,'rev-parse',tag).decode().strip(),
                               system_file=str(path),system_sha256=digest))
    assert {r['cell'] for r in output}==KEY_CELLS
    write_json(directory/'frozen-context-index.json',output)
    print('Hash-verified delivered contexts:',len(output))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--contexts-for',type=Path,help='reconstruct nine frozen system messages for an existing private census')
    parser.add_argument('--sample-audit',action='store_true',help='export all 200 original sample records for the bidirectional audit')
    parser.add_argument('--d4',action='store_true',help='export all historical L1/L1plus formal attempts needed by D4')
    args=parser.parse_args()
    if args.contexts_for:
        target=args.contexts_for.resolve()
        if ROOT==target or ROOT in target.parents:raise ValueError('private directory required')
        export_contexts(target)
        return
    if args.output is None:parser.error('--output or --contexts-for is required')
    data=Path(os.environ['SEMDEBT_DATA_DIR']).resolve();target=args.output.resolve()
    if target==ROOT or ROOT in target.parents or target.exists():raise ValueError('use a new private directory')
    scores=load_scores()
    selected=[r for r in scores if r['stratum'] and not r['low'] and r['v2_outcome']=='wrong'
              and r['has_result'] and not r['rules']]
    assert len(selected)==1411
    # Extra evidence needed only by the previously published D4 all109 scopes.
    extra=[r for r in scores if r['stratum'] and r['low'] and r['cell'] in ('SQL-L1','SQL-L1plus')
           and not r['content_lower']]
    samples={key(r):r for r in read_csv(ROOT/'reports/validation/t31-residual-sample-claude.csv')}
    known={key(r) for r in read_csv(ROOT/'reports/validation/t31-v4-certain-errors.csv')}
    if args.sample_audit:
        selected=[r for r in scores if key(r) in samples]
        extra=[]
        assert len(selected)==200
    if args.d4:
        if args.sample_audit:
            raise ValueError('choose one export scope')
        selected=[r for r in scores if r['stratum'] in ('SQL-L1','SQL-L1plus')]
        extra=[]
        assert len(selected)==654
    source={};materials=[];manifest={}
    target.mkdir();(target/'questions').mkdir()
    with frozen_bank(Path(os.environ['SEMDEBT_EVAL_DIR']),TAG) as (questions,columns,commit,archive):
        assert commit==COMMIT
        for r in sorted(selected+extra,key=lambda r:(int(r['qid'][1:]),r['cell'],r['source_run'],r['rep'])):
            rk=r['source_run'],r['cell'];path=ROOT/'runs'/rk[0]/(rk[1]+'.jsonl')
            if rk not in source:
                raw=path.read_bytes();assert sha(raw)==r['source_log_sha256']
                manifest[str(path.relative_to(ROOT))]=sha(raw)
                source[rk]={sha(line):json.loads(line) for line in raw.splitlines() if line.strip()}
            rec=source[rk][r['source_record_sha256']];turn=rec['turns'][-1];q=questions[r['qid']]
            assert sha(q.text.encode())==rec['question_sha256']
            rawdir=data/'runs-raw'/rk[0]/rk[1]
            ep=rawdir/f"{r['qid']}_r{r['rep']}_t{turn['turn']}.exec.json"
            raw=ep.read_bytes();assert sha(raw)==r['exec_sha256']
            answer=json.loads(raw)
            api=rawdir/f"{r['qid']}_r{r['rep']}_t{turn['turn']}.json"
            response=api.read_bytes();assert sha(response)==turn['raw_sha256']
            parsed=parse_response(json.loads(response)['choices'][0]['message'].get('content') or '')
            refs=[]
            for i,rows in enumerate(q.refs):
                rule=q.ref_rules[i] if q.ref_rules and q.ref_rules[i] is not None else q.rules
                refs.append(dict(index=i,columns=columns[q.qid][i],rows=rows,rules=rule))
            sample=samples.get(key(r));label=sample['label'] if sample else '内容错误' if key(r) in known else None
            materials.append(dict(**r,scope='sample-audit' if args.sample_audit else 'D4' if args.d4 else 'D4-extra' if r in extra else 'D1',
                question=q.text,meta=q.meta,refs=refs,query=parsed.query,assumption=parsed.assumption,
                answer=answer,exec_path=str(ep),response_sha256=sha(response),
                semantic_tag=rec.get('semantic_tag'),system_sha256=rec['system_sha256'],
                semantic_directory=str(data/'t31-residual-frozen-semantics'/rec.get('semantic_tag','')),
                reused_label=label,reused_principle=sample.get('principle','') if sample else '',
                label_source='existing_sample' if sample else 'known_error' if key(r) in known else 'new_review'))
        for qid in sorted({m['qid'] for m in materials},key=lambda x:int(x[1:])):
            group=[m for m in materials if m['qid']==qid]
            write_json(target/'questions'/f'{qid}.json',group)
        write_json(target/'materials.json',materials)
        write_json(target/'manifest.json',dict(eval_tag=TAG,eval_commit=commit,archive_sha256=archive,
            sources=manifest,materials_sha256=sha((target/'materials.json').read_bytes()),
            census_count=len(selected),extra_count=len(extra),model_calls=0,query_executions=0))
    print(json.dumps(dict(census=len(selected),extra=len(extra),reused=sum(m['reused_label'] is not None for m in materials if m['scope']=='D1'),
                         new=sum(m['reused_label'] is None for m in materials if m['scope']=='D1')),ensure_ascii=False))


if __name__=='__main__':main()
