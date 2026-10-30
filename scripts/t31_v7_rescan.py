"""Validate/apply the local 2026-10-31 content audit; no model or SQL execution.

Full result projections stay private. This is an audit importer, not a scorer.
"""
from __future__ import annotations
import argparse
from collections import Counter
import copy
from decimal import Decimal,InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.t31_v4_recompute import identity


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def record_key(r):return '|'.join(map(str,identity(r)))


def extra_values_are_zero(values):
    # NULL, missing values and nonzero counts cannot masquerade as zero groups.
    try:
        return all(v is not None and not isinstance(v,bool) and Decimal(str(v))==0 for v in values)
    except (InvalidOperation,ValueError):
        return False


def inference_allowed(*,steps,contradiction,cumulative,complete,groups_explicit):
    return steps==1 and not contradiction and not cumulative and complete and groups_explicit


def validate_audit(materials,baseline,audit):
    pool={record_key(m):m for m in materials if m['scope']=='D1'
          and baseline[record_key(m)]['label']=='内容正确'}
    reviewed={record_key(r):r for r in audit['records']}
    if len(reviewed)!=len(audit['records']) or set(reviewed)!=set(pool):
        raise ValueError('audit must cover every previously correct main-table residual exactly once')
    for k,m in pool.items():
        r=reviewed[k]
        raw=json.dumps(m,sort_keys=True,ensure_ascii=False).encode()
        if r['material_sha256']!=hashlib.sha256(raw).hexdigest():
            raise ValueError(f'stale material: {k}')
        result=json.dumps(m['answer']['rows'],ensure_ascii=False).encode()
        if r['result_values_sha256']!=hashlib.sha256(result).hexdigest():
            raise ValueError(f'stale result: {k}')
        if r['checked_rows']!=len(m['answer']['rows']) or not r['core_rows_verified']:
            raise ValueError(f'incomplete row review: {k}')
        if r['old_label']!='内容正确' or r['label'] not in ('内容正确','内容错误'):
            raise ValueError(f'unresolved verdict: {k}')
        failure={'strict_null','nonzero_extra','window_mismatch','numeric_mismatch',
                 'contradictory_result','multi_step'}
        if r['label']=='内容正确' and r['criterion'] in failure:
            raise ValueError(f'cannot rescue a contradictory or mismatched result: {k}')
        if r['label']=='内容正确' and not extra_values_are_zero(r.get('discarded_extra_values',[])):
            raise ValueError(f'extra group is not zero: {k}')
        if r['label']=='内容正确' and r['criterion']=='one_step':
            flags={field:r[field] for field in ('steps','contradiction','cumulative','complete','groups_explicit')}
            if not inference_allowed(**flags):raise ValueError(f'ineligible inference: {k}')
        if len(r['note'])>30:raise ValueError(f'long public note: {k}')
    for ruling in audit.get('rulings',[]):
        if reviewed[record_key(ruling)]['label']!=ruling['label']:
            raise ValueError('audit contradicts explicit user ruling')
    return reviewed


def apply_verdicts(baseline,reviewed,audit_sha):
    result=copy.deepcopy(baseline)
    categories=dict(strict_null='数值错误',nonzero_extra='缺行或多行',
                    window_mismatch='数值错误',numeric_mismatch='数值错误',
                    contradictory_result='口径不同',multi_step='列取舍')
    for k,r in reviewed.items():
        d=result[k]
        d['rescan_audit_sha256']=audit_sha
        if r['label']!=d['label']:
            d.update(label=r['label'],category=categories[r['criterion']],note=r['note'],
                     principle='用户2026-10-31统一规则',origin='codex_rescan_20261031',
                     basis='Full private audit record: '+k+'; criterion='+r['criterion'])
    return result


def main():
    from scripts.t31_accuracy_v5 import write_table
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    args=parser.parse_args()
    private=Path(os.environ['SEMDEBT_DATA_DIR'])/'t31-v7-census-20261030'
    audit=json.loads(args.audit.read_text());baseline=json.loads(args.baseline.read_text())
    assert sha(args.baseline)==audit['baseline_decisions_sha256']
    assert sha(private/'materials.json')==audit['materials_sha256']
    assert audit['model_calls']==audit['query_executions']==0
    materials=json.loads((private/'materials.json').read_text())
    reviewed=validate_audit(materials,baseline,audit)
    assert len(reviewed)==420 and len({r['cell'] for r in reviewed.values()})==19
    final=apply_verdicts(baseline,reviewed,sha(args.audit))
    current=json.loads((private/'codex-decisions.json').read_text())
    if current!=baseline and current!=final:
        raise ValueError('live ledger differs; preserve new work instead of overwriting')
    (private/'codex-decisions.json').write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n')
    rulings={record_key(r) for r in audit.get('rulings',[])}
    changes=[dict(source_run=r['source_run'],cell=r['cell'],qid=r['qid'],rep=r['rep'],
                  old_label=r['old_label'],new_label=r['label'],criterion=r['criterion'],note=r['note'],
                  explicit_user_ruling=record_key(r) in rulings)
             for r in reviewed.values() if r['old_label']!=r['label']]
    write_table(ROOT/'reports/validation/t31-v7-rescan-changes.csv',changes)
    coverage=[]
    for cell in sorted({r['cell'] for r in reviewed.values()}):
        rs=[r for r in reviewed.values() if r['cell']==cell]
        coverage.append(dict(cell=cell,reviewed=len(rs),retained=sum(r['label']=='内容正确' for r in rs),
                             changed=sum(r['label']=='内容错误' for r in rs)))
    write_table(ROOT/'reports/validation/t31-v7-rescan-coverage.csv',coverage)
    # Current original-sample audit changes; preserved run snapshots remain intact.
    sample_path=private/'original-sample-bidirectional-audit.json'
    sample=json.loads(sample_path.read_text())
    for r in sample:
        if record_key(r) in reviewed:
            r['new_label']=reviewed[record_key(r)]['label']
            if r['old_label']==r['new_label'] and record_key(r) in {record_key(x) for x in changes}:
                r['reason']='2026-10-31用户裁决撤销上轮改对，恢复原错标签'
    sample_path.write_text(json.dumps(sample,ensure_ascii=False,indent=2)+'\n')
    d4_path=private/'d4-content-equivalence-audit.json';d4=json.loads(d4_path.read_text())
    for patch in audit.get('d4_changes',[]):
        row=next(r for r in d4 if r['qid']==patch['qid'])
        assert row['content_equivalent'] in (patch['old_equivalent'],patch['content_equivalent'])
        row.update(content_equivalent=patch['content_equivalent'],note=patch['note'],rescan_audit_sha256=sha(args.audit))
    d4_path.write_text(json.dumps(d4,ensure_ascii=False,indent=2)+'\n')
    counts=Counter(r['criterion'] for r in changes)
    lines=['# 2026-10-31 D1 判对残余复扫','',
           '依据用户对 PR #214 的裁决，复查全部 19 个正式单元主表内的 420 次原判对残余。原快照为 `20261030-T31-v5-census-03`。本次只下调残余判定，不撤销 v2 或 R1–R11 信用。','',
           f'共保留 {420-len(changes)} 次，改错 {len(changes)} 次。其中用户逐次裁定改错 9 次，同类扩扫新增改错 '+str(len(changes)-9)+' 次；Q110 SQL-L2 第 3 次按裁决保留内容正确。','',
           '先核对是否已直接给出矛盾结果，再考虑一步推导。无矛盾的一次分组求和、计数或算术可接受，须完整且分组明确；跨期前缀累计不接受。实际值非零或为空的额外组不能按零组删除。窗口表显式对齐期间并检查全部所问值，列绑定与全部差异留仓库外。原直接结果的完整投影及文档 C 例外继续保留，未扩大推导许可。','',
           '|改判原因|次数|','|---|---:|']
    labels=dict(strict_null='空值不等于零／已给空结果',window_mismatch='窗口人数逐行不符',
                nonzero_extra='非零额外组误作零组',contradictory_result='已给另一口径的矛盾结果',multi_step='需多步跨期累计')
    lines += [f'|{labels[c]}|{n}|' for c,n in sorted(counts.items())]
    lines += ['', '逐次变更见 `t31-v7-rescan-changes.csv`；全部 19 单元覆盖计数见 `t31-v7-rescan-coverage.csv`。旧样本 Q47 SQL-L1 第 2 次的改对已撤销，当前判错；10-30 变更表作为历史保留，不表示本轮仍放行。','',
              'D4 的 Q26：三次结果并不等价，差异是非零季度人数，不是形式差异；选择集合据此改为不作答，并用新标签重算所有范围的已答准确率。D6 仍按同题同次作答重新取集合；D8 分类不变。','',
              '完整材料及复查账仅在 SEMDEBT_DATA_DIR；主仓库没有题面、SQL、参考结果或作答数值。没有模型 API 调用或 SQL 执行。PR #214 只独立复核过九个关键单元原判对的 194 次，不能称全部 1,411 次都已跨厂商复核；本轮新增变更另供核对。','',
              '复现：`uv run --offline python scripts/t31_v7_rescan.py --audit "$SEMDEBT_DATA_DIR/t31-v7-rescan-20261031/approved-rescan.json" --baseline "$SEMDEBT_DATA_DIR/t31-v7-rescan-20261031/baseline-decisions.json"`，再运行 accuracy-v5 和 followups 聚合。','']
    (ROOT/'reports/validation/t31-v7-rescan.md').write_text('\n'.join(lines))
    print(json.dumps(dict(reviewed=len(reviewed),changed=len(changes),criteria=counts),ensure_ascii=False))


if __name__=='__main__':main()
