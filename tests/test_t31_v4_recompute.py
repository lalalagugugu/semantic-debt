"""Statistical and monotonicity boundaries for the offline v4 recomputation."""
import pytest
import csv
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.t31_v4_recompute import (
    estimate, hypergeom_interval, paired_interval, residual, robustness, sample_update,
    canonical_formal, mark_known_errors, summaries,
)


def test_finite_population_census_and_extremes():
    assert hypergeom_interval(10, 10, 3) == (3, 3)
    assert hypergeom_interval(0, 0, 0) == (0, 0)
    lo, hi = hypergeom_interval(100, 10, 0)
    assert lo == 0 and hi > 0
    assert hypergeom_interval(100, 10, 10) == (100-hi, 100)
    assert hypergeom_interval(10, 1, 0) == (0, 9)


def test_fpc_reduces_interval_for_high_sampling_fraction():
    lo, hi = hypergeom_interval(20, 10, 5)
    lo2, hi2 = hypergeom_interval(2000, 10, 5)
    assert (hi-lo)/20 < (hi2-lo2)/2000
    with pytest.raises(ValueError):
        hypergeom_interval(5, 6, 1)


def test_no_sample_is_unavailable_not_zero():
    assert estimate(9, [])['c'] is None
    assert estimate(0, [])['c'] == 0
    assert estimate(8, [{'label':'内容正确'}, {'label':'内容错误'}])['c'] == 4


def test_residual_requires_result_and_no_rule_or_v2_credit():
    r = dict(v2_outcome='wrong', has_result=True, rules=[])
    assert residual(r)
    for updates in ({'v2_outcome':'correct'}, {'has_result':False}, {'rules':['R1']}):
        assert not residual({**r, **updates})


def test_moved_sample_is_not_counted_twice():
    rows, samples, labels = [], [], []
    for i in range(200):
        s = dict(source_run='run',cell='cell',qid=f'Q{i:03}',rep=1,stratum='cell')
        r = {**s,'low':False,'v2_outcome':'wrong','has_result':True,'rules':[],'a':0,'b':0}
        if i == 0:
            r.update(v2_outcome='correct',a=1)
        if i == 1:
            r.update(rules=['R1'],b=1)
        rows.append(r)
        samples.append(s)
        labels.append({**s,'label':'内容正确'})
    updated = sample_update(rows,samples,labels)
    assert [r['state'] for r in updated[:3]] == ['v2_pass','rule_pass','retained']
    assert sum(r['state']=='retained' for r in updated)==198


def test_paired_question_interval_and_preregistered_labels():
    assert paired_interval([.2]*8) == pytest.approx((.2,.2,.2))
    positive=(.1,.02,.2)
    uncertain=(.1,-.02,.2)
    assert robustness(positive,positive)=='稳健'
    assert robustness(positive,uncertain)=='强弱依口径而定'
    assert robustness(positive,(-.1,-.2,-.02))=='依赖交付口径'
    assert paired_interval([-.5,0,.5]) == paired_interval([-.5,0,.5])


def test_formal_l2e_uses_later_completion_but_history_is_preserved():
    old = dict(source_run='01', cell='SQL-L2-E', stratum='SQL-L2-E',qid='Q80',rep=2,has_result=False)
    new = {**old,'source_run':'02','has_result':True}
    result = canonical_formal([old,new])
    assert len(result) == 2 and result[0]['stratum'] is None
    assert result[0]['superseded_in_formal'] and result[1]['stratum']=='SQL-L2-E'


def test_109_boundary_does_not_extrapolate_or_erase_known_credits():
    common = dict(source_run='run',cell='cell',rep=1,stratum='cell',low=False,q_level='Q1',
                  persona='分析师',split='heldout',a=0,b=0,content_lower=0,
                  v2_outcome='wrong',rules=[],has_result=True)
    rows = [{**common,'qid':'Q01','a':1,'content_lower':1,'v2_outcome':'correct'},
            {**common,'qid':'Q02'}, {**common,'qid':'Q03','low':True}]
    sample = [{**rows[1],'state':'retained','label':'内容正确'}]
    result = summaries(rows,sample)
    main = next(r for r in result if r['kind']=='formal' and r['scope']=='main98' and r['dimension']=='all')
    full = next(r for r in result if r['kind']=='formal' and r['scope']=='all109' and r['dimension']=='all')
    assert main['estimate']==1 and main['c']==1
    assert full['estimate'] is None and full['c'] is None
    assert full['uncovered_zero']==pytest.approx(2/3)
    assert full['uncovered_all']==1


def test_certainty_errors_never_receive_estimated_credit():
    common = dict(source_run='run',cell='cell',rep=1,stratum='cell',low=False,q_level='Q1',
                  persona='分析师',split='heldout',a=0,b=0,content_lower=0,
                  v2_outcome='wrong',rules=[],has_result=True)
    rows = [{**common,'qid':'Q01'}, {**common,'qid':'Q02'}]
    mark_known_errors(rows,[rows[0]])
    sample=[{**rows[1],'state':'retained','label':'内容正确'}]
    result=summaries(rows,sample)
    main=next(r for r in result if r['kind']=='formal' and r['scope']=='main98' and r['dimension']=='all')
    assert main['residual']==2 and main['known_errors']==1 and main['covered_residual']==1
    assert main['c']==1 and main['estimate']==.5
    with pytest.raises(AssertionError):
        mark_known_errors([{**common,'qid':'Q01','a':1,'content_lower':1,'v2_outcome':'correct'}],rows[:1])


def test_hypergeometric_interval_has_design_coverage_for_small_population():
    N, n = 12, 4
    for K in range(N+1):
        coverage = 0
        for x in range(max(0,n-(N-K)), min(n,K)+1):
            lo,hi=hypergeom_interval(N,n,x)
            if lo <= K <= hi:
                coverage += math.comb(K,x)*math.comb(N-K,n-x)/math.comb(N,n)
        assert coverage >= .95-1e-12


def test_published_artifacts_reconcile_and_do_not_contain_raw_material():
    root=Path(__file__).resolve().parents[1]
    directory=root/'runs/20261028-T31-v4-rescore-02'
    manifest=json.loads((directory/'manifest.json').read_text())
    allowed={'source_run','cell','qid','rep','v2_outcome','a','b','rules','content_lower',
             'has_result','low','q_level','persona','split','stratum','source_log_sha256',
             'source_record_sha256','exec_sha256','historical_outcome','known_content_error',
             'superseded_in_formal'}
    rows=[json.loads(line) for p in directory.glob('*.jsonl') for line in p.read_text().splitlines()]
    assert len(rows)==manifest['attempts']
    assert sum(r['a'] for r in rows)==manifest['a']
    assert sum(r['b'] for r in rows)==manifest['b']
    assert sum(r['known_content_error'] for r in rows)==manifest['known_content_errors']==15
    assert all(set(r)<=allowed and r['a']+r['b']==r['content_lower']>=r['a'] for r in rows)
    with (root/'reports/results/accuracy-v4-cells.csv').open() as f:
        summaries=list(csv.DictReader(f))
    for r in summaries:
        total,a,b=int(r['attempts']),int(r['a']),int(r['b'])
        assert float(r['delivery'])==pytest.approx(a/total)
        assert float(r['lower'])==pytest.approx((a+b)/total)
        if r['kind']=='formal' and r['scope']=='main98' and r['estimate']:
            assert float(r['lo'])<=float(r['estimate'])<=float(r['hi'])
            assert float(r['estimate'])>=float(r['lower'])
        else:
            assert not r['estimate'] and not r['c']
