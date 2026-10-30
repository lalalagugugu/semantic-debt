"""Census integrity, immutable delivery credits and question-paired comparisons."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.t31_accuracy_v5 import attach_labels, summaries
from scripts.t31_v7_followups import D6, D8, selective_summary


def row(qid='Q01', **updates):
    return dict(dict(source_run='run',cell='SQL-L1',stratum='SQL-L1',qid=qid,rep=1,
                     low=False,a=0,b=0,content_lower=0,v2_outcome='wrong',has_result=True,
                     rules=[],known_content_error=False,q_level='Q1',split='heldout'),**updates)


def verdict(r, correct=True):
    m={**r,'scope':'D1'}
    k='|'.join(str(r[x]) for x in ('source_run','cell','qid','rep'))
    d=dict(label='内容正确' if correct else '内容错误',material_sha256=
           hashlib.sha256(json.dumps(m,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    return m,k,d


def test_missing_or_stale_verdict_fails_closed():
    r=row();m,k,d=verdict(r)
    with pytest.raises(ValueError,match='missing census'):
        attach_labels([r],[],{})
    with pytest.raises(ValueError,match='mismatch'):
        attach_labels([r],[{**m,'scope':'changed'}],{k:d})
    with pytest.raises(ValueError,match='unresolved'):
        attach_labels([r],[m],{k:{**d,'label':'需用户裁定'}})


def test_delivery_and_rule_credits_cannot_be_revoked_or_double_counted():
    v2=row(a=1,content_lower=1,v2_outcome='correct')
    rule=row('Q02',b=1,content_lower=1,rules=['R1'])
    r=row('Q03');m,k,d=verdict(r)
    result=attach_labels([v2,rule,r],[m],{k:d})
    assert [(s['a'],s['b'],s['census_credit'],s['content_correct']) for s in result]==[
        (1,0,0,1),(0,1,0,1),(0,0,1,1)]
    m2,k2,d2=verdict(v2,False)
    with pytest.raises(AssertionError):
        attach_labels([v2],[m2],{k2:d2})


def test_known_errors_never_receive_credit_and_low_questions_are_not_extrapolated():
    r=row(known_content_error=True);m,k,d=verdict(r)
    with pytest.raises(AssertionError):
        attach_labels([r],[m],{k:d})
    result=attach_labels([row(low=True)],[],{})
    assert result[0]['content_correct'] is None
    assert summaries(result)==[]


def test_consistency_selection_does_not_require_a_correct_answer():
    rs=[{**row(rep=i), 'content_correct':0} for i in (1,2,3)]
    s=selective_summary(rs,{'Q01'},{'Q01':True},'SQL-L1','content_equivalent','main98')
    assert s['coverage']==1 and s['accuracy_answered']==0
    assert s['decision_units']==1 and s['selection_unit']=='question'


def test_classification_count_and_user_ruling_for_execution_failures():
    assert len(D8)==14 and len({r[0] for r in D8})==14
    assert sum(c=='是什么/属于谁' for _,_,c,_ in D8)==4
    assert {k for k,(c,_) in D6.items() if c=='执行失败'}=={('Q73',3),('Q117',3)}


def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))


def test_public_labels_and_tables_reconcile_without_raw_material():
    labels=read(ROOT/'reports/validation/t31-v7-residual-codex.csv')
    assert len(labels)==1411
    assert len({tuple(r[k] for k in ('source_run','cell','qid','rep')) for r in labels})==1411
    assert all(r['label'] in ('内容正确','内容错误') and len(r['note'])<=30 for r in labels)
    cells=read(ROOT/'reports/results/accuracy-v5-cells.csv')
    totals=[r for r in cells if r['dimension']=='all']
    baseline={r['cell']:r for r in read(ROOT/'reports/results/accuracy-v4-cells.csv')
              if r['kind']=='formal' and r['scope']=='main98' and r['dimension']=='all'}
    assert len(totals)==19 and sum(int(r['attempts']) for r in totals)==5439
    for r in totals:
        n=int(r['attempts']);a=int(r['v2_correct']);b=int(r['rule_credit']);c=int(r['census_credit'])
        assert int(r['content_correct'])==a+b+c
        assert float(r['accuracy'])==pytest.approx((a+b+c)/n)
        assert float(r['delivery'])==pytest.approx(a/n)
        assert a==int(baseline[r['cell']]['a']) and b==int(baseline[r['cell']]['b'])
        assert c==sum(s['label']=='内容正确' for s in labels if s['cell']==r['cell'])
    for r in read(ROOT/'reports/results/accuracy-v5-comparisons.csv'):
        assert r['scope']=='main98'
        assert float(r['accuracy_lo'])<=float(r['accuracy_delta'])<=float(r['accuracy_hi'])
    for r in read(ROOT/'reports/results/accuracy-v5-d4.csv'):
        assert float(r['coverage'])==pytest.approx(int(r['answered'])/int(r['decision_units']))
    forbidden=('reference_rows','FROM retail.','SELECT ','/'+'Users'+'/')
    for p in [*ROOT.glob('reports/results/accuracy-v5*.csv'),*ROOT.glob('reports/validation/t31-v7*.csv')]:
        assert not {'question','query','rows','refs','answer'} & set(read(p)[0]),p
        assert not any(s in p.read_text() for s in forbidden),p
