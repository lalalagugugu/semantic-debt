"""Offline census aggregation; consumes reviewed local labels, never calls a model.

uv run --offline python scripts/t31_accuracy_v5.py --run-id <new-run>
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.t31_v4_recompute import comparisons, identity, residual
from scripts.t31_v7_materials import COMMIT, KEY_CELLS, load_scores


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_table(path, rows):
    if not rows:
        raise ValueError(f'empty table: {path.name}')
    with path.open('w', newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def attach_labels(scores, materials, decisions):
    """Missing judgments fail closed; approved v2/rule credits stay immutable."""
    lookup = {identity(m): m for m in materials}
    if len(lookup) != len(materials):
        raise ValueError('duplicate private material')
    out = []
    for original in scores:
        r = dict(original)
        k = identity(r)
        m = lookup.get(k)
        d = decisions.get('|'.join(map(str, k)))
        eligible = bool(r['stratum'] and not r['low'] and residual(r))
        if eligible and (m is None or d is None):
            raise ValueError(f'missing census verdict: {k}')
        if m is not None:
            expected = hashlib.sha256(json.dumps(m, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if d is None or d['material_sha256'] != expected:
                raise ValueError(f'judgment/material mismatch: {k}')
            if d['label'] not in ('内容正确', '内容错误'):
                raise ValueError(f'unresolved judgment: {k}')
            assert not r['content_lower']
        reviewed = d is not None
        credit = int(reviewed and d['label'] == '内容正确')
        complete = bool(not r['low'] or r['content_lower'] or reviewed
                        or r['v2_outcome'] != 'wrong' or not r['has_result'])
        r.update(census_credit=credit, content_correct=r['content_lower'] + credit if complete else None,
                 census_reviewed=reviewed)
        if r['content_correct'] is not None:
            assert r['content_correct'] >= r['content_lower'] >= r['a']
        if r.get('known_content_error'):
            assert not credit
        out.append(r)
    return out


def summaries(rows):
    out = []
    for cell in sorted({r['stratum'] for r in rows if r['stratum']}):
        pool = [r for r in rows if r['stratum'] == cell and not r['low']]
        for dimension, groups in [('all', ['all']), ('q_level', ['Q1', 'Q2', 'Q3']),
                                   ('split', ['tuning', 'heldout'])]:
            for group in groups:
                rs = [r for r in pool if dimension == 'all' or r[dimension] == group]
                if not rs:
                    continue
                assert all(r['content_correct'] is not None for r in rs)
                n = len(rs)
                a, b, c = (sum(r[k] for r in rs) for k in ('a', 'b', 'census_credit'))
                out.append(dict(cell=cell, scope='main98', dimension=dimension, group=group,
                                questions=len({r['qid'] for r in rs}), attempts=n,
                                v2_correct=a, rule_credit=b, census_credit=c,
                                content_correct=a+b+c, accuracy=(a+b+c)/n, delivery=a/n,
                                residual=sum(residual(r) for r in rs)))
    return out


def census_comparisons(rows):
    # Reuse the preregistered pairs and question-cluster bootstrap unchanged.
    main = [{**r, 'content_lower': r['content_correct']} for r in rows
            if r['stratum'] and not r['low']]
    raw = comparisons(main, [], include_estimate=False)
    out = []
    for r in raw:
        if r['scope'] != 'main98':
            continue
        z = {k:r[k] for k in ('left', 'right', 'scope', 'split', 'questions')}
        for old, new in [('delivery', 'delivery'), ('lower', 'accuracy')]:
            for suffix in ('delta', 'lo', 'hi'):
                z[new+'_'+suffix] = r[old+'_'+suffix]
        z['direction'] = '更高' if z['accuracy_lo'] > 0 else '更低' if z['accuracy_hi'] < 0 else '区间含零'
        out.append(z)
    return out


def public_labels(materials, decisions):
    out = []
    for m in materials:
        d = decisions['|'.join(map(str, identity(m)))]
        assert len(d['note']) <= 30
        out.append({**{k:m[k] for k in ('scope', 'source_run', 'cell', 'qid', 'rep')},
                    **{k:d[k] for k in ('label', 'category', 'note', 'principle', 'origin')}})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--decisions-file',type=Path,help='use a preserved private verdict snapshot')
    args = parser.parse_args()
    if Path(args.run_id).name != args.run_id:
        raise ValueError('run-id must be a single directory name')
    private = Path(os.environ['SEMDEBT_DATA_DIR'])/'t31-v7-census-20261030'
    materials = json.loads((private/'materials.json').read_text())
    decisions_file=args.decisions_file or private/'codex-decisions.json'
    decisions = json.loads(decisions_file.read_text())
    manifest = json.loads((private/'manifest.json').read_text())
    assert manifest['eval_commit'] == COMMIT
    assert digest(private/'materials.json') == manifest['materials_sha256']
    assert sum(m['scope'] == 'D1' for m in materials) == 1411
    base=ROOT/'runs/20261028-T31-v4-rescore-02'
    frozen=json.loads((base/'manifest.json').read_text())
    assert frozen['eval_commit']==COMMIT
    for file in ('harness/scorer_v2.py','harness/scorer_v3.py',
                 'scripts/t31_candidate_scan.py','scripts/rescore_t23.py'):
        assert digest(ROOT/file)==frozen['inputs'][file]
    for m in materials:
        assert digest(Path(m['exec_path']))==m['exec_sha256']
    rows = attach_labels(load_scores(), materials, decisions)
    formal = [r for r in rows if r['stratum']]
    main_rows = [r for r in formal if not r['low']]
    assert len(main_rows) == 5439
    assert sum(r['census_reviewed'] for r in main_rows) == 1411
    assert sum(r.get('known_content_error', False) for r in main_rows) == 15
    result = summaries(rows)
    comps = census_comparisons(rows)
    labels = public_labels(materials, decisions)
    audit = json.loads((private/'original-sample-bidirectional-audit.json').read_text())
    assert len(audit) == 200
    run = ROOT/'runs'/args.run_id
    run.mkdir()
    snapshots=private/'snapshots'/args.run_id
    snapshots.mkdir(parents=True)
    for name in ('codex-decisions.json','original-sample-bidirectional-audit.json',
                 'd4-content-equivalence-audit.json','frozen-context-index.json'):
        source=decisions_file if name=='codex-decisions.json' else private/name
        (snapshots/name).write_bytes(source.read_bytes())
    for cell in sorted({r['stratum'] for r in formal}):
        (run/(cell+'.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in formal if r['stratum'] == cell))
    provenance = dict(eval_tag='eval-v1.3', eval_commit=COMMIT, formal_attempts=len(formal),
                      main_attempts=len(main_rows), census_attempts=1411,
                      materials_sha256=digest(private/'materials.json'),
                      decisions_sha256=digest(decisions_file),
                      sample_audit_sha256=digest(private/'original-sample-bidirectional-audit.json'),
                      baseline_scores={str(p.relative_to(ROOT)):digest(p) for p in sorted(base.glob('*.jsonl'))},
                      inputs={str(p.relative_to(ROOT)):digest(p) for p in
                              [ROOT/'scripts/t31_accuracy_v5.py', ROOT/'scripts/t31_v4_recompute.py',
                               ROOT/'reports/validation/t31-v7-label-changes.csv']},
                      model_calls=0, query_executions=0, bootstrap_replicates=5000, bootstrap_seed=0,
                      status='Codex candidate; nine key cells await independent Claude Code review')
    (run/'manifest.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n')
    for filename, table in [('accuracy-v5-cells.csv', result), ('accuracy-v5-comparisons.csv', comps)]:
        write_table(ROOT/'reports/results'/filename, table)
    write_table(ROOT/'reports/validation/t31-v7-residual-codex.csv', [r for r in labels if r['scope']=='D1'])
    write_table(ROOT/'reports/validation/t31-v7-d4-extra-codex.csv', [r for r in labels if r['scope']=='D4-extra'])
    packets = private/'claude-review'/args.run_id
    packets.mkdir(parents=True)
    packet_counts = {}
    for cell in sorted(KEY_CELLS):
        group = [m for m in materials if m['scope']=='D1' and m['cell']==cell]
        # Keep final labels separate so the independent reviewer can first read materials alone.
        fields = ('source_run','cell','qid','rep','question','meta','refs','query','assumption',
                  'answer','exec_path','exec_sha256','response_sha256','semantic_tag',
                  'system_sha256','semantic_directory')
        blind = [{k:m[k] for k in fields} for m in group]
        (packets/(cell+'-materials.json')).write_text(json.dumps(blind, ensure_ascii=False, indent=2)+'\n')
        (packets/(cell+'-codex.json')).write_text(json.dumps([r for r in labels if r['scope']=='D1' and r['cell']==cell], ensure_ascii=False, indent=2)+'\n')
        packet_counts[cell] = len(group)
    (packets/'index.json').write_text(json.dumps(dict(counts=packet_counts, materials='*-materials.json',
        labels='*-codex.json', semantic_documents='semantic_directory in each material record',
        delivered_system_contexts=json.loads((private/'frozen-context-index.json').read_text()),
        ruling='decisions/2026-10-30-complete-detail-aggregation.md',
        no_outbound=True), ensure_ascii=False, indent=2)+'\n')
    lines = ['# accuracy-v5：残余全量判定（待跨厂商复核）', '',
             '状态：Codex 首轮候选。九个关键单元尚待 Claude Code 独立复核，分歧交用户；这些数不能直接作为已核定报告数字。', '',
             '主表 98 题、19 个正式单元，共 5,439 次作答。T4 只覆盖留出 49 题。', '',
             '准确率 = v2 判对 + R1–R11 已审定放行 + 残余逐次内容判定；不再抽样外推。按约定交付率保持 eval-v1.3 下的 v2 原值。', '',
             '残余 1,411 次包含原样本中仍残余的 180 次、已知错误 15 次，以及新增判定 1,216 次。原样本 200 次另做双向复查，逐次变更见 `../validation/t31-v7-label-changes.csv`。已转为 v2 或规则放行的 20 条不重复计入残余。', '',
             '|单元|题数|作答数|v2 判对|规则放行|残余判对|内容判对|准确率|按约定交付率|',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in result:
        if r['dimension']=='all':
            lines.append(f"|{r['cell']}|{r['questions']}|{r['attempts']}|{r['v2_correct']}|{r['rule_credit']}|{r['census_credit']}|{r['content_correct']}|{r['accuracy']:.1%}|{r['delivery']:.1%}|")
    lines += ['', '按 Q 级与调优／留出题集的全部计数和比例见 `accuracy-v5-cells.csv`；全部比较见 `accuracy-v5-comparisons.csv`。管理层／分析师不作为正文分组。', '',
              '比较以题号为配对和重采样单位，先平均每题各次作答，再取右侧单元减左侧单元；5,000 次配对自助法、seed=0，与既有调优报告相同。95% 区间直接用内容准确率计算。区间不含零记方向，含零保留区间供用户判断，未另造“宽／窄”门槛。', '',
              '只看结果，声明的假设不参与评分。遵守 A/B/C 与五题裁决；空值不等于零。完整明细推导须无截断或 LIMIT，且每行明确所属分组。原 v2 和规则放行不撤销，脚本逐次断言准确率不低于按约定交付率。', '',
              '本轮全量内容准确率仅覆盖主表 98 题。低区分度题未全量复判，不能把主表比例套用于这 11 题；D4 所需的 L1／L1plus 补充判定另列，不据此声称全部单元的 109 题准确率。', '',
              '全部判断来自既有日志、最终执行结果和所在单元冻结语义材料；没有模型调用、没有 SQL 执行。完整材料、依据和九单元复核包均在 SEMDEBT_DATA_DIR 内，仓库只含题号、单元、标签、类别、次数与比例。', '',
              f'可复现：`uv run --offline python scripts/t31_accuracy_v5.py --run-id <new-run-id> --decisions-file "$SEMDEBT_DATA_DIR/t31-v7-census-20261030/snapshots/{args.run_id}/codex-decisions.json"`。本次追加目录：`runs/{args.run_id}`。已有日志、评分器 v2、参考答案和冻结文档均不修改。',
              '私有材料导出命令：`uv run --offline python scripts/t31_v7_materials.py --output <new-private-directory>`；实际系统提示重建：`uv run --offline python scripts/t31_v7_materials.py --contexts-for "$SEMDEBT_DATA_DIR/t31-v7-census-20261030"`。导出不产生判断标签，必须使用人工审定账或其保存的快照；缺标签或需用户裁定时脚本拒绝重算。', '']
    (ROOT/'reports/results/accuracy-v5.md').write_text('\n'.join(lines))
    print(json.dumps(dict(run=args.run_id, main_attempts=len(main_rows), packets=packet_counts,
                          labels=Counter(r['label'] for r in labels if r['scope']=='D1')), ensure_ascii=False))


if __name__ == '__main__':
    main()
