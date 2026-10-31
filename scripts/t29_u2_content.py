"""Offline U2 content review and preregistered analysis; no model or SQL calls."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness import scorer_v2 as V2, u2_analysis as A
from scripts.rescore_t23 import frozen_bank
from scripts.t31_v4_recompute import approved_rules

RUN = '20261031-T29-u2-v3-01'
FP = 'bc19ba97cbe016479903222bb1578db6'
CELLS = ('SQL-L0','SQL-L1','SQL-L0-u2','SQL-L1-u2','SQL-L0-u2p','SQL-L1-u2p')
PRIVATE_NAME = 't29-u2-content-20261031'
D1_RUN = '20261031-T31-v5-rulings-01'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str)+'\n')


def blinded(material, anon_id):
    # Confidence, assumption, system instruction variants and source identity are not review evidence.
    return dict(anon_id=anon_id, qid=material['qid'], question=material['question'],
                context_key=material['context_key'], query=material['query'],
                answer=material['answer'], refs=material['refs'])


def final_labels(keys, decisions, materials):
    expected = {m['anon_id'] for m in materials}
    if set(decisions) != expected:
        raise ValueError('manual labels must cover every anonymous residual exactly once')
    out = []
    lookup = {m['anon_id']:m for m in materials}
    for k in keys:
        r = dict(k)
        if k['method'] == 'manual':
            d = decisions[k['anon_id']]
            if d['material_sha256'] != sha(json.dumps(lookup[k['anon_id']], ensure_ascii=False, sort_keys=True).encode()):
                raise ValueError('stale anonymous judgment')
            if d['label'] not in ('内容正确','内容错误'):
                raise ValueError('unresolved rule boundary; ask user before analysis')
            r.update(correct=d['label']=='内容正确', category=d['category'])
        out.append(r)
    return out


def historical_baseline(rows, qids):
    selected=[r for r in rows if r['qid'] in qids]
    expected={(q,rep) for q in qids for rep in (1,2,3)}
    if len(selected)!=len(expected) or {(r['qid'],r['rep']) for r in selected}!=expected:
        raise ValueError('historical baseline scope incomplete or duplicated')
    if any(type(r.get('content_correct')) not in (int,bool) or r['content_correct'] not in (0,1) for r in selected):
        raise ValueError('historical baseline requires final content labels')
    return {q:[bool(r['content_correct']) for r in sorted(selected,key=lambda r:r['rep']) if r['qid']==q] for q in qids}


def lock_verdicts(path, value):
    if path.exists():
        if json.loads(path.read_text())!=value:
            raise ValueError('anonymous verdict lock differs; preserve the existing audit')
    else:
        write(path,value)


def prepare(data, private):
    if private.exists():
        raise ValueError('preserve the existing private review; do not overwrite')
    report = json.loads((ROOT/'reports/validation/t29-u2-v4-collection.json').read_text())
    runtime = data/'t29-u2-runtime-v4'
    frozen = json.loads((ROOT/'runs/20261028-T31-v4-rescore-02/manifest.json').read_text())
    for name in ('harness/scorer_v2.py','harness/scorer_v3.py','scripts/t31_candidate_scan.py','scripts/rescore_t23.py'):
        assert sha((ROOT/name).read_bytes()) == frozen['inputs'][name]
    records = []
    inputs = {}
    for row in report['rows']:
        path = runtime/'runs'/RUN/(row['cell']+'.jsonl')
        raw = path.read_bytes()
        assert sha(raw) == row['source_log_sha256']
        inputs[row['cell']] = sha(raw)
        done = [json.loads(line) for line in raw.splitlines() if json.loads(line)['status']=='done']
        assert len(done)==294 and len({(r['qid'],r['rep']) for r in done})==294
        records.extend(done)
    assert len(records)==1764
    random.SystemRandom().shuffle(records)
    private.mkdir()
    (private/'contexts').mkdir()
    contexts = {}
    for base in ('SQL-L0','SQL-L1'):
        text = (runtime/'build/contexts'/f'{base}.yaml').read_bytes()
        key = sha(text)
        (private/'contexts'/f'{key}.yaml').write_bytes(text)
        contexts[base] = key
    keys, materials = [], []
    with frozen_bank(Path(os.environ['SEMDEBT_EVAL_DIR']), 'eval-v1.3') as (questions, columns, commit, bank_sha):
        assert commit=='5b65e0c450ba36d83707c00dc9443be16b08d086'
        raw_indexes = {}
        for i, rec in enumerate(records, 1):
            cell, qid, rep = rec['cell'], rec['qid'], rec['rep']
            q = questions[qid]
            assert rec['question_sha256']==sha(q.text.encode()) and not q.meta['low_discrimination']
            turn = rec['turns'][-1]
            assert all(t['system_fingerprint']==FP for t in rec['turns'])
            if cell not in raw_indexes:
                index = {}
                for p in (data/'runs-raw'/RUN/cell).glob('Q*_r*_t*.json'):
                    index[sha(p.read_bytes())] = p
                raw_indexes[cell] = index
            index = raw_indexes[cell]
            response_path = index[turn['raw_sha256']]
            response = json.loads(response_path.read_bytes())
            from harness.prompt import parse_response
            parsed = parse_response(response['choices'][0]['message'].get('content') or '')
            native = bool(parsed.refused)
            answer = None
            if turn['exec']['status']=='refused':
                candidate, cc = V2.REFUSAL, None
            elif turn['exec'].get('error_class')=='no_query':
                candidate, cc = V2.ExecError('no_query'), None
            else:
                ep = index[turn['exec']['exec_raw_sha256']]
                answer = json.loads(ep.read_bytes())
                cc = answer['columns']
                candidate = V2.ExecError('execution_error') if answer['error'] is not None else [
                    [Decimal(v) if isinstance(v,str) and cc[j]['type']=='number' else v for j,v in enumerate(row)]
                    for row in answer['rows']]
            v2 = V2.score_detailed(candidate,q.refs,q.rules,reference_rules=q.ref_rules).outcome
            rules = approved_rules(candidate,cc,q,columns[qid]) if v2=='wrong' else []
            method = 'v2' if v2=='correct' else 'R1-R11' if rules else 'refused' if native else 'execution_or_format' if isinstance(candidate,V2.ExecError) else 'manual'
            base = cell if cell in contexts else cell.rsplit('-',1)[0]
            refs = [dict(index=j,columns=columns[qid][j],rows=ref,
                         rules=q.ref_rules[j] if q.ref_rules and q.ref_rules[j] is not None else q.rules)
                    for j,ref in enumerate(q.refs)]
            item = dict(qid=qid,question=q.text,context_key=contexts[base],query=parsed.query,answer=answer,refs=refs)
            anon = f'U{i:04d}'
            conf = rec.get('confidence',{})
            keys.append(dict(anon_id=anon,cell=cell,qid=qid,rep=rep,method=method,correct=method in ('v2','R1-R11'),
                             rules=rules,v2_outcome=v2,native_refusal=native,confidence=conf.get('value'),
                             confidence_status=conf.get('status'),response_sha256=turn['raw_sha256'],
                             exec_sha256=turn['exec'].get('exec_raw_sha256'),context_key=contexts[base]))
            if method=='manual':materials.append(blinded(item,anon))
            if i%100==0:print(f'prepared anonymous {i}/1764',flush=True)
        for key in keys:
            group = [k for k in keys if k['cell']==key['cell']]
            assert {(k['qid'],k['rep']) for k in group}=={(q,rep) for q in {k['qid'] for k in group} for rep in (1,2,3)}
        write(private/'identity-key.json',keys)
        write(private/'blinded-materials.json',materials)
        write(private/'manifest.json',dict(source_run=RUN,attempts=1764,residuals=len(materials),model_api_calls=0,
              query_executions=0,eval_commit=commit,bank_sha256=bank_sha,source_logs=inputs,
              identity_key_sha256=sha((private/'identity-key.json').read_bytes()),
              blinded_materials_sha256=sha((private/'blinded-materials.json').read_bytes()),
              inputs={n:sha((ROOT/n).read_bytes()) for n in ('harness/scorer_v2.py','scripts/t31_candidate_scan.py',
                  'scripts/t31_v4_recompute.py','decisions/2026-10-31-v7-content-review-rulings.md')}))
    print(json.dumps(dict(attempts=len(keys),anonymous_residuals=len(materials),methods=dict(Counter(k['method'] for k in keys))),ensure_ascii=False))


def analyze(data, private):
    keys = json.loads((private/'identity-key.json').read_text())
    materials = json.loads((private/'blinded-materials.json').read_text())
    manifest = json.loads((private/'manifest.json').read_text())
    assert sha((private/'identity-key.json').read_bytes())==manifest['identity_key_sha256']
    assert sha((private/'blinded-materials.json').read_bytes())==manifest['blinded_materials_sha256']
    if len(keys)!=1764 or len({(k['cell'],k['qid'],k['rep']) for k in keys})!=1764:
        raise ValueError('U2 identity scope incomplete or duplicated')
    for name,digest in manifest['inputs'].items():
        if sha((ROOT/name).read_bytes())!=digest:
            raise ValueError('frozen adjudication input changed')
    decisions_path=private/'anonymous-judgments.json'
    decisions=json.loads(decisions_path.read_text())
    labels=final_labels(keys,decisions,materials)
    # Freeze the anonymous verdicts before reconnecting arm identities or computing outcomes.
    lock_verdicts(private/'verdict-lock.json',dict(judgments_sha256=sha(decisions_path.read_bytes()),model_api_calls=0))
    by_cell={c:[k for k in labels if k['cell']==c] for c in CELLS}
    baseline={c:{q:[r['correct'] for r in sorted(by_cell[c],key=lambda r:r['rep']) if r['qid']==q]
                 for q in {k['qid'] for k in by_cell[c]}} for c in CELLS[:2]}
    result={}
    for cell in CELLS[2:]:
        base=cell.rsplit('-',1)[0]
        attempts=[dict(qid=k['qid'],rep=k['rep'],refused=k['native_refusal'],correct=k['correct'],
                       confidence=k['confidence'],confidence_status=k['confidence_status']) for k in by_cell[cell]]
        result[cell]=A.analyze_cell(attempts,baseline[base],baseline_fingerprint=FP,treatment_fingerprint=FP,
                                   baseline_run_id=RUN,treatment_run_id=RUN,d1_complete=True)
    contrasts={base:A.compare_refusal_arms(
        [dict(qid=k['qid'],rep=k['rep'],refused=k['native_refusal']) for k in by_cell[base+'-u2']],
        [dict(qid=k['qid'],rep=k['rep'],refused=k['native_refusal']) for k in by_cell[base+'-u2p']],d1_complete=True)
        for base in CELLS[:2]}
    drift={}
    for base in CELLS[:2]:
        old=[json.loads(s) for s in (ROOT/'runs'/D1_RUN/(base+'.jsonl')).read_text().splitlines()]
        previous=historical_baseline(old,set(baseline[base]))
        drift[base]=A.compare_baseline_accuracy(previous,baseline[base],d1_complete=True)
    write(private/'final-labels.json',labels)
    write(private/'analysis.json',dict(arms=result,penalty_contrasts=contrasts,baseline_drift=drift))
    print(json.dumps(dict(labeled=len(labels),methods=dict(Counter(k['method'] for k in labels))),ensure_ascii=False))


def export(data, private):
    labels=json.loads((private/'final-labels.json').read_text())
    lock=json.loads((private/'verdict-lock.json').read_text())
    if sha((private/'anonymous-judgments.json').read_bytes())!=lock['judgments_sha256']:
        raise ValueError('verdicts changed after unblinding')
    rows=[]
    for r in sorted(labels,key=lambda r:(r['cell'],int(r['qid'][1:]),r['rep'])):
        rows.append(dict(qid=r['qid'],cell=r['cell'],rep=r['rep'],anonymous_id=r['anon_id'],
            content_correct=int(r['correct']),method=r['method'],
            category=r.get('category',r['method']),native_refusal=r['native_refusal']))
    path=ROOT/'reports/validation/t29-u2-content-labels.csv'
    with path.open('w',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    analysis=json.loads((private/'analysis.json').read_text())
    summary={cell:dict(attempts=len(rs),correct=sum(r['correct'] for r in rs),
                      accuracy=sum(r['correct'] for r in rs)/len(rs),
                      methods=dict(Counter(r['method'] for r in rs)))
             for cell in CELLS for rs in ([r for r in labels if r['cell']==cell],)}
    write(ROOT/'reports/results/t29-u2-content-analysis.json',dict(source_run=RUN,
          fingerprint=FP,model_api_calls=0,query_executions=0,
          verdict_lock_sha256=sha((private/'verdict-lock.json').read_bytes()),
          summary=summary,**analysis))
    # A separate private packet lets the other vendor review all positives.
    # It deliberately contains neither arm identity nor the first reviewer's rationale.
    packet=[]
    with frozen_bank(Path(os.environ['SEMDEBT_EVAL_DIR']),'eval-v1.3') as (bank,columns,commit,bank_sha):
        for cell in CELLS:
            group=[r for r in labels if r['cell']==cell and r['correct']]
            wanted={r['response_sha256'] for r in group}|{r['exec_sha256'] for r in group}
            index={}
            for path in (data/'runs-raw'/RUN/cell).glob('Q*_r*_t*.json'):
                digest=sha(path.read_bytes())
                if digest in wanted:index[digest]=path
            for r in group:
                from harness.prompt import parse_response
                response=json.loads(index[r['response_sha256']].read_text())
                parsed=parse_response(response['choices'][0]['message'].get('content') or '')
                q=bank[r['qid']]
                refs=[dict(index=j,columns=columns[q.qid][j],rows=ref,
                      rules=q.ref_rules[j] if q.ref_rules and q.ref_rules[j] is not None else q.rules)
                      for j,ref in enumerate(q.refs)]
                packet.append(blinded(dict(qid=q.qid,question=q.text,query=parsed.query,
                    context_key=r['context_key'],answer=json.loads(index[r['exec_sha256']].read_text()),refs=refs),r['anon_id']))
    packet.sort(key=lambda r:r['anon_id'])
    write(private/'claude-positive-materials.json',packet)
    write(private/'publication-manifest.json',dict(positive_review_attempts=len(packet),
          packet_sha256=sha((private/'claude-positive-materials.json').read_bytes()),
          labels_sha256=sha((ROOT/'reports/validation/t29-u2-content-labels.csv').read_bytes()),
          analysis_code_sha256=sha(Path(__file__).read_bytes()),
          decisions_sha256=lock['judgments_sha256'],model_api_calls=0,query_executions=0))
    pct=lambda v:'不可估计' if v is None else f'{100*v:.2f}%'
    interval=lambda v,scale=1:'不计算' if v is None else f'[{v[0]*scale:.3f}, {v[1]*scale:.3f}]'
    lines=['# U2 全量内容判定与预登记分析（Codex 初判，待 Claude 独立复核）','',
        '日期：2026-11-01。原始采集 run `'+RUN+'`，指纹 `'+FP+'`。六单元各98题×3次，共1764次；本次模型API调用0、SQL执行0。分析只用本次同指纹基线，旧指纹基线仅描述漂移。','',
        '## 判定与盲法','',
        '沿用D1定稿的v2、R1–R11及2026-10-31统一内容规则：929次v2判对、90次规则放行、128次原生拒答、6次执行或协议失败；其余611次匿名逐条核对，102次判对、509次判错，总计1121次内容正确。完整结果、SQL、题面及证据均留数据目录。公开逐次标签见 `../validation/t29-u2-content-labels.csv`。','',
        '先用系统随机源打乱1764次作答并生成匿名编号。人工材料移除了单元/臂别、次数、系统提示、假设文本及把握分，仅含题号、题面、所交付基础上下文、SQL和结果/参考。按首次遇到题号的随机顺序分组审阅；所有标签完成后写入不可覆盖的verdict-lock，再接回身份。不是严格双盲：同一Codex会话构建材料并判定，SQL表名与基础上下文可提示L0/L1，但未依据惩罚臂或把握值判内容。','',
        '用户2026-11-01确认Q110的NULL所问格可按一步、无歧义、无矛盾规则补全，新增1次内容正确；暂停前285次标签中的同类回查无变更，变更/新增单列 `../validation/t29-u2-null-review-changes.csv`。没有把NULL当0。19个正式单元只读核对另见 `../validation/t29-u2-d1-null-one-step.md`，发现4次Q96现有判错，D1标签全部保持不动。','',
        '## 六单元总计','',
        '|单元|次数|内容正确|准确率|原生拒答|执行/协议失败|',
        '|---|---:|---:|---:|---:|---:|']
    for cell in CELLS:
        s=summary[cell];rs=[r for r in labels if r['cell']==cell]
        lines.append(f"|{cell}|{s['attempts']}|{s['correct']}|{pct(s['accuracy'])}|{sum(r['native_refusal'] for r in rs)}|{s['methods'].get('execution_or_format',0)}|")
    lines+=['','## 四处理臂独立判定','',
        '每臂98题、294次。Δ为拒答侧减作答侧的同题新基线平均错误率；拒答率<5%时按预登记不算Δ，记“该单元未见取舍”。AUC用处理作答自身的内容标签，有效原始把握分，不含原生拒答；缺失/非法把握不补值。','',
        '|单元|拒答/294|拒答率|已答准确率|Δ（百分点）及95%区间|拒答判定|AUC及95%区间|把握判定|',
        '|---|---:|---:|---:|---|---|---|---|']
    for cell,a in analysis['arms'].items():
        delta='不计算' if a['refusal_error_difference'] is None else f"{a['refusal_error_difference']*100:.3f} {interval(a['refusal_error_difference_ci'],100)}"
        lines.append(f"|{cell}|{a['refused']}|{pct(a['refusal_rate'])}|{pct(a['accuracy_answered'])}|{delta}|{a['refusal_conclusion']}|{a['auc']:.3f} {interval(a['auc_ci'])}|{'达标' if a['confidence_success'] else '未达标'}|")
    lines+=['','拒答与把握为独立结论，不要求同时成立：无惩罚两臂拒答率均<5%；惩罚两臂Δ区间下界均>0；四臂AUC区间下界均>0.5。该结果限本模型、本题集和本指纹，不推断其他模型，也不将名义区间称为多重比较校正后的区间。','',
        '|单元|拒答侧基线错误率|作答侧基线错误率|缺失把握|非法把握|有效把握|≥90交付次数|≥90覆盖率|≥90已答准确率|',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for cell,a in analysis['arms'].items():
        g=a['gate90'];lines.append(f"|{cell}|{pct(a['baseline_error_refused'])}|{pct(a['baseline_error_answered'])}|{a['confidence_missing']}|{a['confidence_invalid']}|{a['confidence_valid']}|{g['answered']}|{pct(g['coverage'])}|{pct(g['accuracy_answered'])}|")
    lines+=['','≥90门控只作描述，未增加成功门槛。未计算的拒答侧比较由<5%规则决定，不表示观察到基线错误率为零。','',
        '## 惩罚臂减无惩罚臂','',
        '|基础单元|拒答率差（百分点）|95%区间（百分点）|',
        '|---|---:|---|']
    for cell,a in analysis['penalty_contrasts'].items():lines.append(f"|{cell}|{a['penalty_minus_unpenalized']*100:.3f}|{interval(a['ci95'],100)}|")
    lines+=['','## 仅描述新旧基线漂移','',
        '|基础单元|旧指纹准确率|新指纹准确率|新减旧（百分点）|95%区间（百分点）|',
        '|---|---:|---:|---:|---|']
    for cell,a in analysis['baseline_drift'].items():lines.append(f"|{cell}|{pct(a['old_accuracy'])}|{pct(a['new_accuracy'])}|{a['new_minus_old']*100:.3f}|{interval(a['ci95'],100)}|")
    lines+=['','两侧均使用内容标签，旧基线来自D1最终快照 `'+D1_RUN+'`。这些差异只描述漂移，不进入U2拒答判据，不作为新的成功条件。','',
        '## 复现与独立复核','',
        '全部区间沿用冻结的 `harness/u2_analysis.py`：98题成簇、每题保留3次，10,000次、种子20261019、经验百分位95%区间；两臂差和新旧基线差按题配对。四臂Δ/AUC有效重采样次数在同名JSON中逐项报告，本次所有可计算指标均为10,000次；<5%臂Δ为0次。判据未改。','',
        '数据目录中的 `t29-u2-content-20261031/claude-positive-materials.json` 含1121次判对材料及上下文哈希，不含臂别和Codex理由，供Claude独立核对；identity-key及初判理由另存，不应先交给独立判定者。上下文在同目录 `contexts/`。尚未声称已独立复核，后续分歧需单列，不覆盖本次匿名锁。','',
        '离线复算（使用已锁定的私有证据目录；环境变量须已指向授权目录）：','',
        '```sh','uv run --offline python scripts/t29_u2_content.py analyze',
        'uv run --offline python scripts/t29_u2_content.py export','```','',
        '脚本不导入模型客户端、不执行数据库查询。准备阶段 `prepare` 仅可写入新的私有证据目录，拒绝覆盖；现有匿名分配以材料哈希和锁为准，不重新抽签。公开CSV/JSON只含题号、单元、次数、标签、统计及审计元数据，不含题面或SQL。','',
        'D4原L0/L1基线的三次内容一致对照按原登记交D4统一产出；现有D4主报告未列这两项，本次不冒充已完成该对照。它不是本次U2两项独立判据的输入。','']
    (ROOT/'reports/results/t29-u2-content-analysis.md').write_text('\n'.join(lines))
    print(json.dumps(dict(public_labels=len(rows),private_positive_materials=len(packet))))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','analyze','export'])
    args=parser.parse_args()
    data=Path(os.environ['SEMDEBT_DATA_DIR'])
    private=data/PRIVATE_NAME
    {'prepare':prepare,'analyze':analyze,'export':export}[args.phase](data,private)


if __name__=='__main__':main()
