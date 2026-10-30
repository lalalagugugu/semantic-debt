"""Aggregate the local D4 content-equivalence audit and D6/D8 classifications."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.t31_accuracy_v5 import write_table

# Classification decisions, not scoring exceptions. All correctness comes from D1.
D6 = {
    ('Q18', 1): ('是什么/属于谁', '以活动代类型，缺所问分组归属'),
    ('Q37', 1): ('怎么算', '百分位方向反向'),
    ('Q37', 2): ('怎么算', '部分百分位偏离一档，非舍入差异'),
    ('Q49', 3): ('怎么算', '层级已有金额按下属路径重复累计'),
    ('Q61', 3): ('是什么/属于谁', '漏未归属子品类对象'),
    ('Q65', 1): ('是什么/属于谁', '额外职务筛选排除应含经理'),
    ('Q73', 3): ('执行失败', '同名别名替换形成嵌套聚合'),
    ('Q82', 2): ('怎么算', '整年差替代按天折算的小数年'),
    ('Q89', 1): ('怎么算', '产品种类计数额外筛掉非正数量行'),
    ('Q89', 3): ('怎么算', '产品种类计数额外筛掉非正数量行'),
    ('Q98', 1): ('怎么算', '跨年取峰值替代年度依赖程度'),
    ('Q113', 3): ('怎么算', '月序列取目标记录导致连续区间缺失'),
    ('Q117', 3): ('执行失败', '同名别名使聚合表达式进入过滤条件'),
    ('Q122', 1): ('怎么算', '提升度订单基数筛选不同'),
}

D8 = [
    ('A1', 'Q34;Q87', '怎么算', '平均值分母使用哪些快照日期'),
    ('A2', 'Q34', '怎么算', '继承平均值分母及缺失值处理'),
    ('A3', '', '是什么/属于谁', '分母归属查询整体还是各上层分组'),
    ('A4', 'Q50;Q117', '是什么/属于谁', '比较年份决定纳入哪个门店集合'),
    ('A5', 'Q27', '怎么算', '先合计再除还是逐项比率求平均'),
    ('A6-1', 'Q52', '怎么算', '分组后均值合计或最大值未定'),
    ('A6-2', 'Q09', '怎么算', '分组后均值合计或最大值未定'),
    ('A7-1', 'Q45;Q70', '是什么/属于谁', '分母纳入全部还是有销售的门店'),
    ('A7-2', 'Q70', '是什么/属于谁', '分母纳入全部还是有销售的门店'),
    ('A8-1', 'Q20;Q21;Q73;Q87', '怎么算', '最近快照按全库还是指定时间窗口'),
    ('A8-2', 'Q20;Q21;Q73;Q87', '怎么算', '最近快照按全库还是指定时间窗口'),
    ('A8-3', 'Q20;Q21;Q73;Q87', '怎么算', '最近快照按全库还是指定时间窗口'),
    ('A8-4', 'Q20;Q21;Q73;Q87', '怎么算', '最近快照按全库还是指定时间窗口'),
    ('A8-5', 'Q20;Q21;Q73;Q87', '怎么算', '最近快照按全库还是指定时间窗口'),
]


def selective_summary(rows, ids, answered, cell, method, scope):
    selected = [r for r in rows if r['qid'] in ids and r['stratum'] == cell]
    by = {q:sorted([r for r in selected if r['qid']==q], key=lambda r:r['rep']) for q in ids}
    assert all(len(rs)==3 and all(r['content_correct'] is not None for r in rs) for rs in by.values())
    kept = [by[q][0] for q in ids if answered[q]]
    return dict(cell=cell, method=method, scope=scope, questions=len(ids), decision_units=len(ids),
                selection_unit='question', answered=len(kept),
                coverage=len(kept)/len(ids), correct_answered=sum(r['content_correct'] for r in kept),
                accuracy_answered=sum(r['content_correct'] for r in kept)/len(kept) if kept else None,
                delivery_answered=sum(r['a'] for r in kept)/len(kept) if kept else None,
                baseline_accuracy=sum(r['content_correct'] for r in selected)/len(selected),
                baseline_delivery=sum(r['a'] for r in selected)/len(selected))


def d6_rows(rows):
    plus = {(r['qid'],r['rep']):r for r in rows if r['stratum']=='SQL-L1plus' and not r['low']}
    selected = [r for r in rows if r['stratum']=='SQL-L3a' and not r['low']
                and not r['content_correct'] and plus[r['qid'],r['rep']]['content_correct']]
    assert {(r['qid'],r['rep']) for r in selected} == set(D6)
    return [dict(cell=r['cell'], qid=r['qid'], rep=r['rep'], category=D6[r['qid'],r['rep']][0],
                 note=D6[r['qid'],r['rep']][1],
                 ontology_relation='直接原因无关；长上下文间接影响无法核实' if r['v2_outcome']=='exec_error' else '')
            for r in sorted(selected,key=lambda r:(int(r['qid'][1:]),r['rep']))]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-id',required=True)
    p.add_argument('--audit-file',type=Path,help='use a preserved private equivalence audit')
    args=p.parse_args()
    directory=ROOT/'runs'/args.run_id
    rows=[json.loads(line) for f in directory.glob('*.jsonl') for line in f.read_text().splitlines()]
    if not rows:
        raise ValueError('no v5 records')
    private=Path(os.environ['SEMDEBT_DATA_DIR'])/'t31-v7-census-20261030'
    audit_file=args.audit_file or private/'d4-content-equivalence-audit.json'
    audit=json.loads(audit_file.read_text())
    assert len(audit)==109 and len({r['qid'] for r in audit})==109
    old={r['qid']:r['old_category']=='consistent' for r in audit}
    new={r['qid']:r['content_equivalent'] for r in audit}
    plus=[r for r in rows if r['stratum']=='SQL-L1plus']
    pilot=set(json.loads((ROOT/'reports/validation/t29-pilot-preflight.json').read_text())['pilot_qids'])
    scopes=dict(main98={r['qid'] for r in plus if not r['low']},
                heldout49={r['qid'] for r in plus if not r['low'] and r['split']=='heldout'},
                tuning20=pilot, all109={r['qid'] for r in plus})
    summary=[]
    for scope, ids in scopes.items():
        for method, decisions in [('original_result_multiset',old),('content_equivalent',new)]:
            summary.append(selective_summary(rows, ids, decisions, 'SQL-L1plus', method, scope))
    # Early T19c confidence tiers refer to the original L1 answers, not a new answer.
    confidence=ROOT/'runs/20261023-T19c-confidence-01/confidence.jsonl'
    judgments=[json.loads(line) for line in confidence.read_text().splitlines()]
    by={(r['qid'],r['rep']):r for r in rows if r['stratum']=='SQL-L1'}
    confidence_ids=[]
    for scope in ('main98','all109'):
        pool=[r for r in judgments if scope=='all109' or not by[r['qid'],r['rep']]['low']]
        kept=[by[r['qid'],r['rep']] for r in pool if r.get('tier')=='A']
        assert all(r['content_correct'] is not None for r in kept)
        confidence_ids.extend(dict(scope=scope,cell='SQL-L1',qid=r['qid'],rep=r['rep']) for r in kept)
        full=[r for r in rows if r['stratum']=='SQL-L1' and (scope=='all109' or not r['low'])]
        summary.append(dict(cell='SQL-L1',method='early_confidence_A',scope=scope,questions=len({r['qid'] for r in pool}),
            decision_units=len(pool),selection_unit='attempt',
            answered=len(kept),coverage=len(kept)/len(pool),correct_answered=sum(r['content_correct'] for r in kept),
            accuracy_answered=sum(r['content_correct'] for r in kept)/len(kept),
            delivery_answered=sum(r['a'] for r in kept)/len(kept),
            baseline_accuracy=sum(r['content_correct'] for r in full)/len(full),
            baseline_delivery=sum(r['a'] for r in full)/len(full)))
    sixth=d6_rows(rows)
    eighth=[dict(ambiguity_id=i,qids=q,category=c,note=n) for i,q,c,n in D8]
    for path,table in [('reports/results/accuracy-v5-d4.csv',summary),
                       ('reports/validation/t31-v7-d4-equivalence.csv',
                        [dict(qid=r['qid'],old_equivalent=old[r['qid']],content_equivalent=new[r['qid']]) for r in audit]),
                       ('reports/validation/t31-v7-confidence-A.csv',confidence_ids),
                       ('reports/validation/t31-v7-d6.csv',sixth),
                       ('reports/validation/t31-v7-d8.csv',eighth)]:
        write_table(ROOT/path,table)
    lines=['# T31 v7：D4、D6、D8（待独立复核）','',
           'D4 对三次最终结果逐题比较所问对象、分组及指标；仅辅助列、长宽表、名称编码、期间、比例和允许的并列边界变化不算内容不一致。正确性与一致性分开：三次一致但都答错仍可被选中。空值和零不同，执行失败不一致。','',
           '原规则和新规则均取被选中题目的第 1 次作答计算已答准确率。原选择集合不变，以本轮内容准确率重评，避免同时混入参考版本和选择规则变化。','',
           '|单元|方法|范围|题数|选择次数|选择单位|已答|覆盖率|已答内容正确|已答准确率|已答交付率|基线准确率|',
           '|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|']
    for r in summary:
        lines.append(f"|{r['cell']}|{r['method']}|{r['scope']}|{r['questions']}|{r['decision_units']}|{r['selection_unit']}|{r['answered']}|{r['coverage']:.1%}|{r['correct_answered']}|{r['accuracy_answered']:.1%}|{r['delivery_answered']:.1%}|{r['baseline_accuracy']:.1%}|")
    lines += ['', '早期“有把握”为原 T19c 的 A 档，只重评原回答，不重新追问；覆盖率分母为该范围全部追问记录，无法解析的记录不选中。全部 109 题的内容复判只为 D4 的 L1／L1plus 对照，不外推到其他单元。','',
              'D6 按相同题号和第几次作答配对，列出 L1plus 内容正确而 L3a 内容错误的逐次记录，不把两单元净差额当作错例数。对象类型、归属及对象全集记“是什么/属于谁”；公式、聚合、分母、时间窗口记“怎么算”。两次执行失败按用户裁决单列。','',
              '|D6 类别|次数|','|---|---:|']
    for c,n in Counter(r['category'] for r in sixth).items():
        lines.append(f'|{c}|{n}|')
    lines += ['', 'D6 逐次清单见 `../validation/t31-v7-d6.csv`。Q73 第 3 次与 Q117 第 3 次直接原因均为 SQL 同名别名解析引起的非法聚合，与本体格式无关；已核对系统提示哈希，没有发现出错片段照抄本体注解或将类／属性名当列名的证据。是否受长上下文间接影响，既有日志无法确认。','',
              'D8 来源为 `../validation/metric-text-vs-impl.md` 的 A 类 14 项、8 组；拆分 A6 两项、A7 两项、A8 五项。这里只判断歧义类型，不新增业务裁定。逐条编号与理由见 `../validation/t31-v7-d8.csv`。','',
              '|D8 类别|次数|','|---|---:|']
    for c,n in Counter(r['category'] for r in eighth).items():
        lines.append(f'|{c}|{n}|')
    lines += ['', 'A4 的时间参数改变纳入的对象集合，归“是什么/属于谁”；A8 的时间参数改变最近快照运算的搜索窗口，归“怎么算”。分类取主要分歧点，存在边界判断；不据此推断因果。','',
              '复现：`uv run --offline python scripts/t31_v7_followups.py --run-id <accuracy-v5-run-id>`。不调用模型、不执行 SQL、不修改历史作答或冻结材料。','']
    (ROOT/'reports/results/t31-v7-followups.md').write_text('\n'.join(lines))
    manifest=dict(run_id=args.run_id,model_calls=0,query_executions=0,
                  inputs={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
                          for f in [ROOT/'scripts/t31_v7_followups.py',confidence,
                                    ROOT/'reports/validation/metric-text-vs-impl.md',
                                    ROOT/'reports/validation/t29-pilot-preflight.json']},
                  equivalence_audit_sha256=hashlib.sha256(audit_file.read_bytes()).hexdigest(),
                  d6=Counter(r['category'] for r in sixth),d8=Counter(r['category'] for r in eighth))
    target=directory/'followups-manifest.json'
    serialized=json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'
    if target.exists():
        if target.read_text()!=serialized:raise ValueError('append a new run; existing follow-up manifest differs')
    else:target.write_text(serialized)
    print(json.dumps(dict(d4=summary,d6=Counter(r['category'] for r in sixth),d8=Counter(r['category'] for r in eighth)),ensure_ascii=False))


if __name__=='__main__':
    main()
