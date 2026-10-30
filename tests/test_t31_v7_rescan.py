"""Regression boundaries from the user-adjudicated independent D1 review."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.t31_v7_rescan import extra_values_are_zero,inference_allowed,validate_audit,record_key


def test_literal_zero_is_required_even_when_other_groups_are_correct():
    assert extra_values_are_zero([0,0.0,'0'])
    assert not extra_values_are_zero([0,1])
    assert not extra_values_are_zero([None])
    assert not extra_values_are_zero([False])


def test_one_step_cannot_override_contradiction_or_prefix_accumulation():
    flags=dict(steps=1,contradiction=False,cumulative=False,complete=True,groups_explicit=True)
    assert inference_allowed(**flags)
    for changes in ({'steps':2},{'contradiction':True},{'cumulative':True},
                    {'complete':False},{'groups_explicit':False}):
        assert not inference_allowed(**{**flags,**changes})


def fixture():
    m=dict(source_run='run',cell='SQL-L1',qid='Q01',rep=1,scope='D1',answer={'rows':[['first',0],['later',1]]})
    key=record_key(m)
    r={k:m[k] for k in ('source_run','cell','qid','rep')}
    r.update(material_sha256=hashlib.sha256(json.dumps(m,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
             result_values_sha256=hashlib.sha256(json.dumps(m['answer']['rows'],ensure_ascii=False).encode()).hexdigest(),
             old_label='内容正确',label='内容错误',criterion='nonzero_extra',
             core_rows_verified=True,checked_rows=2,note='后续组非零')
    return m,{key:{'label':'内容正确'}},r


def test_full_coverage_and_all_rows_not_just_first_row():
    m,baseline,r=fixture()
    assert validate_audit([m],baseline,{'records':[r]})
    with pytest.raises(ValueError,match='exactly once'):
        validate_audit([m],baseline,{'records':[]})
    with pytest.raises(ValueError,match='incomplete row'):
        validate_audit([m],baseline,{'records':[{**r,'checked_rows':1}]})
    changed=copy.deepcopy(m);changed['answer']['rows'][1][1]=2
    with pytest.raises(ValueError,match='stale material'):
        validate_audit([changed],baseline,{'records':[r]})


def test_a_correct_looking_projection_cannot_rescue_a_failed_criterion():
    m,baseline,r=fixture()
    with pytest.raises(ValueError,match='cannot rescue'):
        validate_audit([m],baseline,{'records':[{**r,'label':'内容正确'}]})
    with pytest.raises(ValueError,match='not zero'):
        validate_audit([m],baseline,{'records':[{**r,'label':'内容正确','criterion':'direct','discarded_extra_values':[1]}]})


def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))


def test_rulings_and_changes_reconcile_with_new_totals():
    changes=read(ROOT/'reports/validation/t31-v7-rescan-changes.csv')
    assert len({(r['source_run'],r['cell'],r['qid'],r['rep']) for r in changes})==len(changes)
    assert all(r['old_label']=='内容正确' and r['new_label']=='内容错误' for r in changes)
    assert sum(r['explicit_user_ruling']=='True' for r in changes)==9
    before=[json.loads(line) for f in (ROOT/'runs/20261030-T31-v5-census-03').glob('*.jsonl') for line in f.read_text().splitlines()]
    cells=read(ROOT/'reports/results/accuracy-v5-cells.csv')
    for cell in {r['cell'] for r in cells}:
        old=[r for r in before if r['stratum']==cell and not r['low']]
        new=next(r for r in cells if r['cell']==cell and r['dimension']=='all')
        delta=sum(r['cell']==cell for r in changes)
        assert int(new['content_correct'])==sum(r['content_correct'] for r in old)-delta
        assert int(new['v2_correct'])==sum(r['a'] for r in old)
        assert int(new['rule_credit'])==sum(r['b'] for r in old)
    labels={(r['cell'],r['qid'],r['rep']):r['label'] for r in read(ROOT/'reports/validation/t31-v7-residual-codex.csv')}
    assert labels['SQL-L1','Q47','2']=='内容错误'
    assert labels['SQL-L2','Q110','3']=='内容正确'
    eqs={r['qid']:r for r in read(ROOT/'reports/validation/t31-v7-d4-equivalence.csv')}
    assert eqs['Q26']['content_equivalent']=='False'
    sixth=read(ROOT/'reports/validation/t31-v7-d6.csv')
    assert sum(r['category']=='执行失败' for r in sixth)==2
    assert {('Q47','2'),('Q72','3')} <= {(r['qid'],r['rep']) for r in sixth}
