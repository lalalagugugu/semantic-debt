"""Synthetic v2 specification coverage; no private questions or SQL."""
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import scorer_v2 as S


def rules(types=("Float64",), kinds=None, **extra):
    return {"required_columns": list(range(len(types))), "value_types": list(types),
            "value_kinds": kinds or ["other"] * len(types), "ordered": False,
            "top_n": None, "tie_columns": [], **extra}


def check(candidate, reference, metadata, outcome="correct", reason=None):
    result = S.score_detailed(candidate, [reference], metadata)
    assert result.outcome == outcome, result
    if reason:
        assert result.reason == reason
    return result


@pytest.mark.parametrize("candidate,outcome", [(S.ExecError("engine failed"), "exec_error"),
    ("CANNOT_ANSWER", "refused"), ([], "correct"), ([[1]], "wrong")])
def test_input_states(candidate, outcome):
    check(candidate, [], rules(), outcome)


def test_invalid_input_and_determinism():
    with pytest.raises(TypeError):
        S.score("answer", [[[1]]], rules())
    with pytest.raises(ValueError):
        S.score([[1], [1, 2]], [[[1]]], rules())
    first = S.score_detailed([[1]], [[[1]]], rules())
    assert first == S.score_detailed([[1]], [[[1]]], rules())


@pytest.mark.parametrize("field", ["required_columns", "value_types", "value_kinds", "ordered"])
def test_required_metadata(field):
    r = rules(); r.pop(field)
    with pytest.raises(ValueError, match=field):
        S.score([[1]], [[[1]]], r)


@pytest.mark.parametrize("extra", [dict(required_columns=[]), dict(required_columns=[0, 0]),
    dict(required_columns=[1]), dict(value_types=[]), dict(value_kinds=[]), dict(value_kinds=["guess"]),
    dict(ordered=1), dict(ordered=True), dict(use_absolute_tolerance=True), dict(exact_counts=True),
    dict(top_n=1), dict(tie_columns=[0]), dict(identifier_columns=[2]), dict(rank_columns=[-1])])
def test_invalid_metadata(extra):
    with pytest.raises(ValueError):
        S.score([[1]], [[[1]]], rules(**extra))


def test_per_reference_rules_replace_without_merging():
    refs = [[[100]], [[1]]]
    assert S.score([[1]], refs, rules(), reference_rules=[rules(), rules()]) == "correct"
    with pytest.raises(ValueError):
        S.score([[1]], refs, rules(), reference_rules=[rules(), {}])
    with pytest.raises(ValueError):
        S.score([[1]], refs, rules(), reference_rules=[])


@pytest.mark.parametrize("a,b,ok", [(" x ", "x", True), ("X", "x", False), ("翻译", "label", False),
    (None, None, True), (0, None, False), (None, 0, False), ("NaN", None, True),
    (None, "real", False), ("", "real", False)])
def test_strings_and_null_labels(a, b, ok):
    check([[a]], [[b]], rules(["String"]), "correct" if ok else "wrong")


@pytest.mark.parametrize("candidate,reference,ok", [("new", None, True), ("new", "", True),
    ("known", None, False), (None, "new", False), ("", "new", False)])
def test_reference_only_empty_labels(candidate, reference, ok):
    check([[candidate, 1], ["known", 2]], [[reference, 1], ["known", 2]],
          rules(["String", "Int64"]), "correct" if ok else "wrong")


@pytest.mark.parametrize("kind,typ,c,r,ok", [
    ("other", "Float64", 100, 100.502, True), ("other", "Float64", 100.502, 100, False),
    ("amount", "Float64", .009, 0, True), ("amount", "Float64", .011, 0, False),
    ("ratio", "Float64", .00009, 0, True), ("ratio", "Float64", .00011, 0, False),
    ("percentage", "Float64", .009, 0, True), ("percentage", "Float64", .011, 0, False),
    ("other", "Float64", .0000002, .0000001, False), ("other", "Float64", 0, 0, True),
    ("count", "Nullable(LowCardinality(UInt64))", 10001, 10000, False),
    ("count", "Nullable(LowCardinality(UInt64))", 10000, 10001, False),
    ("count", "Float64", 10001, 10000, True), ("count", "Int64", 10000, 10000, True),
    ("other", "Float64", .9967, 99.67, True), ("other", "Float64", 99.67, .9967, True),
    ("ratio", "Float64", .001, 0, False), ("other", "Float64", "100", 100, False),
    ("amount", "Float64", 1, 10000, False), ("other", "Float64", -10, 10, False),
    ("other", "Float64", float("nan"), float("nan"), False),
    ("other", "Float64", float("inf"), float("inf"), False),
    ("other", "Float64", None, 0, False), ("other", "Float64", "NaN", None, False),
])
def test_numeric_rules(kind, typ, c, r, ok):
    check([[c]], [[r]], rules([typ], [kind]), "correct" if ok else "wrong")


@pytest.mark.parametrize("c,r,ok", [(10000, "10000", True), ("10000", 10000, True),
    (" 10000 ", 10000, True), ("010000", 10000, False), (10000, "010000", False),
    ("10000.0", 10000, False), (10001, 10000, False), (100, 1, False),
    (Decimal("10000"), 10000, True)])
def test_identifiers(c, r, ok):
    check([[c]], [[r]], rules(["String"], identifier_columns=[0]), "correct" if ok else "wrong")


@pytest.mark.parametrize("c,r,ok", [(date(2024, 1, 2), "2024-01-02", True),
    ("2024-01-02", date(2024, 1, 2), True),
    (datetime(2024, 1, 2), "2024-01-02", True),
    ("2024-01-02", "2024-01-02 00:00:00", True),
    ("2024-01-02 00:00:00", date(2024, 1, 2), True),
    (datetime(2024, 1, 2, 1), date(2024, 1, 2), False),
    (date(2024, 1, 2), datetime(2024, 1, 2, tzinfo=timezone.utc), False),
    ("2024-01", "2024-01-01", False), ("Q1", "第一季度", False)])
def test_dates(c, r, ok):
    check([[c]], [[r]], rules(["Date"]), "correct" if ok else "wrong")


@pytest.mark.parametrize("candidate,reference,types,ok", [
    ([['Ada', 'Lovelace']], [['Ada Lovelace']], ['String'], True),
    ([['Lovelace', 'Ada']], [['Ada Lovelace']], ['String'], True),
    ([['Ada Lovelace']], [['Ada', 'Lovelace']], ['String', 'String'], True),
    ([['Ada Lovelace']], [['Lovelace', 'Ada']], ['String', 'String'], True),
    ([['Ada,Lovelace']], [['Ada', 'Lovelace']], ['String', 'String'], False),
    ([['Ada', 'Byron', 'Lovelace']], [['Ada Byron Lovelace']], ['String'], False),
])
def test_adjacent_name_join(candidate, reference, types, ok):
    check(candidate, reference, rules(types), "correct" if ok else "wrong")


def test_only_one_required_name_column_does_not_join():
    check([['Ada Lovelace']], [['Ada', 'Lovelace']], rules(['String', 'String'], required_columns=[0]), 'wrong')
    check([['Lovelace']], [['Ada', 'Lovelace']], rules(['String', 'String'], required_columns=[1]))


def test_column_permutation_extra_missing_and_nonrequired():
    r = rules(['String', 'Float64', 'Int64'], required_columns=[0, 1])
    check([[3, 10, 'x', 'extra']], [['x', 10, 5]], r)
    check([[10]], [['x', 10, 5]], r, 'wrong', 'missing_columns')
    check([['x', 11]], [['x', 10, 5]], r, 'wrong')
    check([['x']], [['x', 'x']], rules(['String', 'String']), 'wrong')


def test_multiset_duplicates_and_augmenting_paths():
    check([[1], [1], [2]], [[2], [1], [1]], rules())
    check([[1], [2], [2]], [[2], [1], [1]], rules(), 'wrong')
    check([[100.49], [99.6]], [[100], [100.5]], rules())
    check([[99], [99.6]], [[100], [100.5]], rules(), 'wrong')


def ordered(**extra):
    return rules(['String', 'Float64'], ['other', 'amount'], ordered=True,
                 order_by=[{'column': 1, 'descending': True}], **extra)


def test_ordered_tie_blocks_and_hidden_key():
    reference = [['a', 10.001], ['b', 10.002], ['c', 9]]
    check([['b'], ['a'], ['c']], reference, ordered(required_columns=[0]))
    check([['c'], ['a'], ['b']], reference, ordered(required_columns=[0]), 'wrong', 'order')
    check([['c'], ['a'], ['b']], reference, {**ordered(required_columns=[0]), 'ordered': False})


def test_top_n_boundary_members_and_full_group():
    ref = [['a', 10], ['b', 9], ['c', 9], ['d', 9]]
    r = ordered(top_n=2, tie_columns=[1])
    check([['a', 10], ['d', 9]], ref, r)
    check([['b', 9], ['d', 9]], ref, r, 'wrong')
    check(ref, ref, r, 'wrong', 'top_n_full_group')
    check([['a', 10]], ref, r, 'wrong', 'row_count')
    check([['d', 9], ['a', 10]], ref, r, 'wrong', 'order')


@pytest.mark.parametrize('reference_extra', [True, False])
def test_optional_zero_rows_both_directions(reference_extra):
    base = [['x', 4, 8, 10]]
    zero = ['empty', 0, None, 999]
    r = rules(['String', 'UInt64', 'Float64', 'Int64'], ['other', 'count', 'amount', 'other'], identifier_columns=[3])
    check(base if reference_extra else base + [zero], base + [zero] if reference_extra else base, r)
    nonzero = ['empty', 0, 1, 999]
    check(base if reference_extra else base + [nonzero], base + [nonzero] if reference_extra else base, r, 'wrong')


def test_zero_rows_need_count_and_do_not_apply_to_top_n():
    check([], [[0]], rules(), 'wrong')
    check([], [[0]], rules(['UInt64'], ['count']))
    r = rules(['UInt64'], ['count'], top_n=1, tie_columns=[0])
    check([], [[0]], r, 'wrong', 'row_count')
    check([[0]], [[0]], r)


@pytest.mark.parametrize('candidate,ok', [([['a',1,'b',2], ['d',4,'c',3]], True),
    ([['b',2,'a',1], ['c',3,'d',4]], True), ([['b',1,'a',2], ['c',3,'d',4]], False)])
def test_unordered_pairs_are_whole_groups_per_row(candidate, ok):
    ref = [['a',1,'b',2], ['c',3,'d',4]]
    check(candidate, ref, rules(['String','Int64','String','Int64'],
        unordered_pairs=[{'left':[0,1], 'right':[2,3]}]), 'correct' if ok else 'wrong')


def selection_rules(n=1, nested=False):
    stages = [{'parent':None, 'where':[], 'group_columns':[], 'object_columns':[0],
               'order_by':[{'column':1, 'descending':True}], 'n':n}]
    if nested:
        stages.append({'parent':0, 'where':[], 'group_columns':[0], 'object_columns':[2],
                       'order_by':[{'column':3,'descending':True}], 'n':1})
    return rules(['String','Float64','String','Float64'] if nested else ['String','Float64'],
                 selection={'version':1,'stages':stages,'output_order':[]})


def test_selection_parent_and_leaf_constraints():
    ref = [['a',10,'x',4],['a',10,'y',4],['b',9,'z',3]]
    r = selection_rules(nested=True)
    check([['a',10,'y',4]], ref, r)
    check([['b',9,'z',3]], ref, r, 'wrong', 'selection')
    check([['a',10,'x',4],['a',10,'y',4]], ref, r, 'wrong', 'selection')
    check([['a',10,'missing',4]], ref, r, 'wrong')


def test_selection_ties_missing_groups_duplicates_and_zero_not_optional():
    r = selection_rules()
    ref = [['a',10],['b',10]]
    check([['b',10]], ref, r)
    check(ref, ref, r, 'wrong', 'selection')
    r = rules(['String','String','UInt64'], ['other','other','count'], selection={
        'version':1,'stages':[{'parent':None,'where':[],'group_columns':[0], 'object_columns':[1],
        'order_by':[{'column':2,'descending':True}],'n':1}],'output_order':[]})
    ref = [['g','a',0],['h','b',1]]
    check(ref, ref, r)
    check(ref[1:], ref, r, 'wrong')
    check(ref + [ref[0]], ref, r, 'wrong')


def test_selection_identity_must_be_required_and_exact():
    r = selection_rules()
    with pytest.raises(ValueError, match='identity'):
        S.score([['a',1]], [[['a',1]]], {**r,'required_columns':[1]})
    r = rules(['Int64','Float64'], selection=r['selection'])
    check([[10000,1]], [[10000,1]], r)
    check([[10001,1]], [[10000,1]], r, 'wrong')


def ranked_rules():
    return rules(['String','Float64','UInt64'], rank_columns=[2], rankings=[{
        'column':2,'group_columns':[],'object_columns':[0], 'prefix':False,
        'blocks':[{'group':[],'rank':1,'dense':1,'size':2}, {'group':[],'rank':3,'dense':2,'size':1}]}])


@pytest.mark.parametrize('ranks,ok', [([1,1,3],True),([1,1,2],True),([1,2,3],True),
    ([2,1,3],True),([1,2,2],False),([1,1,4],False),([1,1,Decimal('3.01')],False)])
def test_whole_answer_ranking_modes(ranks, ok):
    ref = [['a',90,1],['b',90,1],['c',80,3]]
    check([[n,v,r] for (n,v,_),r in zip(ref,ranks)], ref, ranked_rules(), 'correct' if ok else 'wrong')


def test_no_ties_rank_exact_and_top_n_position_prefix():
    r = ranked_rules(); r['rankings'][0]['blocks'] = [{'group':[],'rank':i,'dense':i,'size':1} for i in (1,2)]
    ref = [['a',90,1],['b',80,2]]
    check(ref, ref, r)
    check([['a',90,2],['b',80,1]], ref, r, 'wrong', 'rank')
    r = ranked_rules(); r.update(top_n=1, tie_columns=[1]); r['rankings'][0]['prefix'] = True
    check([['b',90,1]], [['a',90,1],['b',90,1]], r)
    check([['b',90,2]], [['a',90,1],['b',90,1]], r, 'wrong', 'rank')


def cap_case():
    ref = [[int(i == j) for j in range(7)] for i in range(7)]
    ref += [[1-x for x in row] for row in ref]
    return [[0]*7]*7 + [[1]*7]*7, ref, rules(['Int64']*7)


def test_mapping_cap_and_early_success():
    c, r, meta = cap_case()
    check(c, r, meta, 'unscored', 'mapping_cap')
    check(r, r, meta)


def test_multiple_reference_outcome_precedence():
    c, r, meta = cap_case()
    assert S.score(c, [r,c], meta) == 'correct'
    result = S.score_detailed(c, [c[:1],r], meta)
    assert (result.outcome,result.reason) == ('unscored','mapping_cap')
    check([[3]], [[1]], rules(), 'wrong', 'values')


def test_diagnostics_separate_and_bounded(monkeypatch):
    monkeypatch.setattr(S, 'diagnose_sensitivity', lambda *a, **k: pytest.fail('diagnosis in scoring'))
    check([['wrong',10]], [['right',10]], rules(['String','Float64']), 'wrong')


def test_numeric_projection_diagnosis():
    r = rules(['String','Float64'])
    assert S.diagnose_sensitivity([['wrong',10]], [[['right',10]]], r) == 'string_or_label_only'
    assert S.diagnose_sensitivity([['wrong',11]], [[['right',10]]], r) == 'numeric_mismatch'
    assert S.diagnose_sensitivity([[1]], [[[1]]], rules(), time_limit=0) == 'not_diagnosed'


def test_prompt_byte_identical_to_frozen_tag():
    root = Path(__file__).resolve().parents[1]
    frozen = subprocess.check_output(['git','show','harness-v1:harness/prompt.py'], cwd=root)
    assert frozen == (root/'harness/prompt.py').read_bytes()


def test_random_small_tables_against_exhaustive_matching_oracle():
    # Exhaustion is confined to a four-row test oracle, never the scorer.
    from itertools import permutations
    import random
    rng = random.Random(20261019)
    for _ in range(120):
        ref = [[100+rng.randrange(8)/10,200+rng.randrange(8)/10] for _ in range(4)]
        candidate = [[100+rng.randrange(16)/10,200+rng.randrange(16)/10] for _ in range(4)]
        def equal(a,b):
            return abs(Decimal(str(a))-Decimal(str(b))) <= Decimal('.005')*abs(Decimal(str(b)))
        expected = any(all(equal(candidate[i][cols[d]],ref[j][d]) for i,j in enumerate(rows) for d in range(2))
                       for cols in permutations(range(2)) for rows in permutations(range(4)))
        assert S.score(candidate,[ref],rules(['Float64']*2)) == ('correct' if expected else 'wrong')


def test_count_nullable_noninteger_guard_and_wrapped_strings():
    check([[10001]],[[10000]],rules(['Nullable(Float64)'],['count']))
    check([[10100]],[[10000]],rules(['Nullable(Float64)'],['count']),'wrong')
    check([['Ada Lovelace']], [['Ada','Lovelace']],rules(['LowCardinality(String)','Nullable(String)']))
    check([['Ada,Lovelace']], [['Ada','Lovelace']],rules(['LowCardinality(String)','Nullable(String)']),'wrong')


def test_order_blocks_use_quantization_not_result_tolerance():
    ref=[['a',10],['b',9.99]]
    check([['a',10],['b',9.99]],ref,ordered())
    check([['b',9.99],['a',10]],ref,ordered(),'wrong','order')


def test_multiple_refs_none_fallback_and_all_wrong():
    assert S.score([[2]],[[[1]],[[2]]],rules(),reference_rules=[None,None])=='correct'
    assert S.score([[3]],[[[1]],[[2]]],rules(),reference_rules=[None,None])=='wrong'


def test_rank_style_uniform_across_groups_and_columns():
    r=rules(['String','String','Float64','UInt64'],rank_columns=[3],rankings=[{
        'column':3,'group_columns':[0],'object_columns':[1],'prefix':False,
        'blocks':[{'group':[g],'rank':rank,'dense':dense,'size':size}
                  for g in ['g','h'] for rank,dense,size in [(1,1,2),(3,2,1)]]}])
    ref=[[g,n,v,rank] for g in ['g','h'] for n,v,rank in [('a',90,1),('b',90,1),('c',80,3)]]
    candidate=[[g,n,v,2 if rank==3 else rank] for g,n,v,rank in ref]
    check(candidate,ref,r)
    candidate[-1][-1]=3
    check(candidate,ref,r,'wrong','rank')


def test_selection_separate_root_filters_and_invalid_contracts():
    r=rules(['String','String','Float64'],selection={'version':1,'stages':[
        {'parent':None,'where':[{'column':0,'equals':g}],'group_columns':[0],
         'object_columns':[1],'order_by':[{'column':2,'descending':True}],'n':1} for g in ['g','h']],
        'output_order':[]})
    ref=[['g','a',10],['g','b',9],['h','c',8]]
    check([ref[0],ref[2]],ref,r)
    check([ref[0]],ref,r,'wrong','selection')
    check([ref[1],ref[2]],ref,r,'wrong','selection')
    with pytest.raises(ValueError):
        S.score([ref[0]],[ref],{**r,'top_n':1,'tie_columns':[2]})


def test_fast_path_miss_is_not_rejection_and_never_rounds():
    check([[Decimal('0.10001')]],[[Decimal('0.1')]],rules())
    check([[Decimal('0.0000002')]],[[Decimal('0.0000001')]],rules(),'wrong')
    check([[100]],[[1]],rules())
    check([[Decimal('1.000000000000001')]],[[Decimal('1.000000000000001')]],rules())


def test_refusal_does_not_hide_invalid_rules():
    with pytest.raises(ValueError):
        S.score('CANNOT_ANSWER',[[[1]]],{})
    assert S.score('CANNOT_ANSWER',[[[1]]],rules())=='refused'


def test_join_requires_adjacent_columns_and_full_table_correspondence():
    check([['Ada',42,'Lovelace']],[['Ada Lovelace']],rules(['String']),'wrong')
    check([['Ada','Lovelace']],[['Ada Lovelace']],rules(['String']))


@pytest.mark.parametrize('reverse',[False,True])
def test_zero_fractional_midnight_and_timezone_rejection(reverse):
    c,r='2024-01-02T00:00:00.000000',date(2024,1,2)
    if reverse:
        c,r=r,c
    check([[c]],[[r]],rules(['Date']))
    c,r='2024-01-02T00:00:00+00:00',date(2024,1,2)
    if reverse:
        c,r=r,c
    check([[c]],[[r]],rules(['Date']),'wrong')


def test_join_cannot_erase_nonempty_column_when_other_column_is_null():
    check([[None]],[[None,'Ada']],rules(['Nullable(String)','String']),'wrong')
    check([['Ada Lovelace']],[['Ada','Lovelace']],rules(['Nullable(String)','String']))


def test_top_n_duplicate_boundary_cannot_replace_strict_prefix():
    r=rules(['String','Float64'],top_n=2,tie_columns=[1])
    reference=[['strict',10],['b',9],['c',9]]
    check([['strict',10],['c',9]],reference,r)
    check([['b',9],['b',9]],reference,r,'wrong')


def test_diagnostic_real_deadline():
    candidate=[[1]]*100000
    assert S.diagnose_sensitivity(candidate,[candidate],rules(),time_limit=.001)=='not_diagnosed'


def test_flow_witness_requires_reassigning_across_two_numeric_dimensions():
    check([[100.1,200.9],[100.2,200]],[[100,200],[100.3,201.5]],rules(['Float64']*2))
    check([[100.1,200.9],[100.2,198]],[[100,200],[100.3,201.5]],rules(['Float64']*2),'wrong')


def test_optional_zero_rows_keep_numerical_and_label_requirements():
    r=rules(['String','UInt64','Float64'],['other','count','amount'])
    check([['a',1,10],['extra',0,0]],[['a',1,10],['unused',0,0]],r)
    check([['wrong',1,10],['extra',0,0]],[['a',1,10],['unused',0,0]],r,'wrong')
    check([['a',1,10]],[['a',1,10],['b',1,0]],r,'wrong','row_count')


def test_corpus_runner_reports_decoded_cases_without_private_values(tmp_path):
    import json
    from scripts.validate_scorer_v2 import run
    corpus=tmp_path/'cases.jsonl'
    cases=[{'case_id':'synthetic/1','source':'synthetic','question_id':'S1',
            'candidate':[[{'$decimal':'1.0'}]], 'refs':[[[1]]], 'rules':[rules()]},
           {'case_id':'synthetic/2','source':'synthetic','question_id':'S2',
            'candidate':[[3]], 'refs':[[[1]]], 'rules':[rules()]},
           {'case_id':'synthetic/judge','source':'synthetic','question_id':'SJ','judge':True}]
    corpus.write_text(''.join(json.dumps(c)+'\n' for c in cases))
    output,report=tmp_path/'out.jsonl',tmp_path/'report.md'
    assert run([corpus],output,report)==0
    records=[json.loads(l) for l in output.read_text().splitlines()]
    assert [r.get('outcome',r['status']) for r in records]==['correct','wrong','judge']
    assert 'seconds' in records[0] and 'old_seconds' in records[0]
    assert 'candidate' not in output.read_text() and 'refs' not in output.read_text()


def test_corpus_runner_rejects_incomplete_rules_without_a_verdict(tmp_path):
    import json
    from scripts.validate_scorer_v2 import run
    corpus=tmp_path/'cases.jsonl'
    corpus.write_text(json.dumps({'case_id':'synthetic/invalid','source':'synthetic',
        'question_id':'S1','candidate':[[1]],'refs':[[[1]]],'rules':[{}]})+'\n')
    output=tmp_path/'out.jsonl'
    assert run([corpus],output,tmp_path/'report.md')==1
    record=json.loads(output.read_text())
    assert record['status']=='invalid_input' and 'outcome' not in record


def test_column_hall_impossibility_is_pruned_before_full_mapping(monkeypatch):
    r=rules(['UInt64']*14)
    reference=[[100]*14]
    candidate=[[100]*13+[999]]
    monkeypatch.setattr(S,'_check_mapping',lambda *args: pytest.fail('infeasible column assignment enumerated'))
    check(candidate,reference,r,'wrong')


def test_nonrelaxed_formats_and_wide_long_conversion():
    check([['2009-Q1']],[['2009-Q1']],rules(['String']))
    check([['Q1']],[['2009-Q1']],rules(['String']),'wrong')
    check([['1,000']],[[1000]],rules(),'wrong')
    check([[1000]],[['1,000']],rules(['String']),'wrong')
    check([['a',1],['b',2]],[['a',1,'b',2]],rules(['String','Float64','String','Float64']),'wrong','row_count')
    check([['a',1,'b',2]],[['a',1],['b',2]],rules(['String','Float64']),'wrong','row_count')


def test_structure_rejections_precede_matching(monkeypatch):
    monkeypatch.setattr(S,'_match',lambda *a,**k: pytest.fail('matching before structural rejection'))
    check([[1]],[[1],[2]],rules(),'wrong','row_count')
    check([[1]],[[1,2]],rules(['Float64']*2),'wrong','missing_columns')


def test_decimal_window_endpoints_do_not_round_away_matching_edges():
    from decimal import localcontext
    with localcontext() as ctx:
        ctx.prec=100
        ref=Decimal('1.'+'0'*50+'1')
        boundary=ref*Decimal('1.005')
        beyond=boundary+Decimal('1e-60')
    metadata=[('other',False,None)]
    assert list(S._edges([((S._NUM,boundary),)],[((S._NUM,ref),)],metadata))==[[0]]
    assert list(S._edges([((S._NUM,beyond),)],[((S._NUM,ref),)],metadata))==[[]]
    check([[boundary]],[[ref]],rules())
    check([[beyond]],[[ref]],rules(),'wrong')


@pytest.mark.parametrize('kind',['percentage','ratio','other'])
@pytest.mark.parametrize('reverse',[False,True])
def test_v12_percentage_scope_and_integer_guard(kind,reverse):
    candidate,reference=1,100
    if reverse:
        candidate,reference=reference,candidate
    check([[candidate]],[[reference]],rules(['Float64'],[kind]))
    check([[candidate]],[[reference]],rules(['Nullable(LowCardinality(Int64))'],[kind]),'wrong')


@pytest.mark.parametrize('kind',['amount','count'])
@pytest.mark.parametrize('reverse',[False,True])
def test_v12_amount_and_count_never_scale(kind,reverse):
    candidate,reference=12.34,1234
    if reverse:
        candidate,reference=reference,candidate
    check([[candidate]],[[reference]],rules(['Float64'],[kind]),'wrong')
    check([[100.1]],[[100]],rules(['Float64'],[kind]))


@pytest.mark.parametrize('kind',['other','amount','ratio','percentage','count'])
def test_v12_integer_types_exact_in_all_units(kind):
    check([[2008]],[[2008]],rules(['UInt16'],[kind]))
    check([[2009]],[[2008]],rules(['UInt16'],[kind]),'wrong')


@pytest.mark.parametrize('field',['top_n','tie_columns'])
def test_v12_additional_required_fields(field):
    r=rules()
    check([[1]],[[1]],r)
    r.pop(field)
    with pytest.raises(ValueError,match=field):
        S.score([[1]],[[[1]]],r)


def test_v12_unknown_rules_rejected():
    check([[1]],[[1]],rules())
    with pytest.raises(ValueError,match='unknown'):
        S.score([[1]],[[[1]]],rules(label_values=[['x']]))


def test_v12_where_columns_required_and_literal_membership():
    r=rules(['String','String','Float64'],selection={'version':1,'output_order':[],
       'stages':[{'parent':None,'where':[{'column':0,'equals':'high'}],'group_columns':[],
                  'object_columns':[1],'order_by':[{'column':2,'descending':True}],'n':1}]})
    check([[' high ','a',10]],[['high','a',10]],r)
    check([['low','a',10]],[['high','a',10]],r,'wrong')
    with pytest.raises(ValueError,match='where'):
        S.score([['high','a',10]],[[['high','a',10]]],{**r,'required_columns':[1,2]})


def test_v12_top_n_short_domain_and_malformed_boundary():
    r=ordered(top_n=3,tie_columns=[1])
    check([['a',10]],[['a',10]],r)
    check([],[['a',10]],r,'wrong','row_count')
    check([['a',10],['b',9]],[['a',10],['b',9]],r)
    with pytest.raises(ValueError,match='boundary'):
        S.score([['a',10]],[[['a',10],['b',9]]],ordered(top_n=1,tie_columns=[1]))


def test_v12_reason_first_reference_and_farthest_correspondence():
    result=S.score_detailed([[1]],[[[1],[2]],[[3]]],rules())
    assert (result.outcome,result.reason)==('wrong','row_count')
    r=ranked_rules()
    reference=[['a',90,1],['b',90,1],['c',80,3]]
    check([['a',90,1],['b',90,1],['c',80,9]],reference,r,'wrong','rank')
    check([['a',10,1],['b',10,1],['c',10,9]],reference,r,'wrong','values')


def test_v12_selection_names_merge_as_exact_identity_in_both_orders():
    r=rules(['String','String','String','Float64'],selection={'version':1,'output_order':[],
       'stages':[{'parent':None,'where':[],'group_columns':[2],'object_columns':[0,1],
                  'order_by':[{'column':3,'descending':True}],'n':1}]})
    reference=[['Ann','Lee','US',9],['Bo','Chen','CN',8],['Cy','Wu','CN',8]]
    check([['Ann Lee','US',9],['Cy Wu','CN',8]],reference,r)
    check([['Lee Ann','US',9],['Wu Cy','CN',8]],reference,r)
    check([['Ann Lee','US',9],['Unknown','CN',8]],reference,r,'wrong')
    check([['Ann Lee','US',9],['Cy Wu','CN',8],['Bo Chen','CN',8]],reference,r,'wrong','selection')


@pytest.mark.parametrize('role',['identifier_columns','rank_columns'])
def test_v12_names_never_merge_exact_roles(role):
    r=rules(['String','Float64'],**{role:[0]})
    check([['Ann Lee',1]],[['Ann Lee',1]],r)
    check([['Ann','Lee',1]],[['Ann Lee',1]],r,'wrong')


def test_v12_only_string_empty_labels_and_empty_to_null():
    r=rules(['Nullable(String)','Float64'])
    check([[None,10]],[['',10]],r)
    check([['replacement',10]],[[None,10]],r)
    check([['replacement',10]],[[None,10]],rules(['Nullable(Date)','Float64']),'wrong')
    check([['replacement',10]],[[None,10]],{**r,'identifier_columns':[0]},'wrong')


def test_v12_multiple_zero_counts_and_nonzero_rank_exception():
    r=rules(['String','UInt64','UInt64'],['other','count','count'])
    check([],[['unused',0,0]],r)
    check([],[['retained',0,1]],r,'wrong','row_count')
    r=rules(['String','UInt64','UInt64'],['other','count','other'],rank_columns=[2])
    check([['a',5,1]],[['a',5,1],['b',0,2]],r)
    check([['a',5,1]],[['a',5,1],['b',1,2]],r,'wrong','row_count')


def test_v12_ordered_zero_rows_at_any_position():
    r=rules(['String','UInt64'],['other','count'],ordered=True,order_by=[{'column':1,'descending':True}])
    reference=[['a',5],['b',2],['empty',0]]
    check([['before',0],['a',5],['between',0],['b',2]],reference,r)
    check([['b',2],['between',0],['a',5]],reference,r,'wrong','order')


def test_v12_nonprefix_position_ranks_allow_gaps_but_not_duplicates():
    r=rules(['String','Float64','UInt64'],top_n=2,tie_columns=[1],rank_columns=[2],rankings=[{
        'column':2,'group_columns':[],'object_columns':[0],'prefix':False,
        'blocks':[{'group':[],'rank':1,'dense':1,'size':4}]}])
    ref=[[name,10,1] for name in ['a','b','c','d']]
    check([['b',10,2.0],['d',10,4.0]],ref,r)
    check([['b',10,2],['d',10,2]],ref,r,'wrong','rank')
    check([['b',10,'2'],['d',10,'4']],ref,r,'wrong','rank')


def test_v12_pair_projection_swaps_only_both_required_positions():
    r=rules(['Int64','String','Int64','String','UInt64'],['other']*4+['count'],required_columns=[1,3,4],
            identifier_columns=[0,2],unordered_pairs=[{'left':[0,1],'right':[2,3]}])
    ref=[[1,'A',2,'B',10],[3,'C',4,'D',7]]
    check([['B','A',10],['C','D',7]],ref,r)
    check([['B','A',10],['D','wrong',7]],ref,r,'wrong')
    one={**r,'required_columns':[1,4]}
    check([['A',10],['C',7]],ref,one)
    check([['B',10],['C',7]],ref,one,'wrong')


def test_v12_empty_reference_bool_and_structured_cells():
    check([],[],rules())
    check([[0]],[],rules(['UInt64'],['count']),'wrong','row_count')
    check([[True]],[[True]],rules(['Bool']))
    check([[1]],[[True]],rules(['Bool']),'wrong')
    check([[(1,2)]],[[[1,2]]],rules(['Array(UInt8)']))
    check([[(1,3)]],[[[1,2]]],rules(['Array(UInt8)']),'wrong')


def test_v12_selection_float_identity_never_uses_tolerance():
    r=rules(['Float64','String','Float64'],selection={'version':1,'output_order':[],
       'stages':[{'parent':None,'where':[],'group_columns':[0],'object_columns':[1],
                  'order_by':[{'column':2,'descending':True}],'n':1}]})
    check([[2008.0,'a',9]],[[2008.0,'a',9]],r)
    check([[2009.0,'a',9]],[[2008.0,'a',9]],r,'wrong')


def test_v12_overlapping_numeric_windows_keep_optional_boundary_edges():
    r=rules(['Float64'],['ratio'],top_n=1,tie_columns=[0])
    reference=[[1e-9],[1e-9]]
    check([[1e-8]],reference,r)
    check([[1]],reference,r,'wrong')


def test_v12_empty_string_label_accepts_date_spelling_but_not_native_date():
    r=rules(['Nullable(String)','Float64'])
    check([['2024-01-01',1]],[[None,1]],r)
    check([[date(2024,1,1),1]],[[None,1]],r,'wrong')
    check([['2024-01-01',1],['known',2]],[[None,1],['2024-01-01',2]],r,'wrong')
    check([['2024-01-01',1],['other',2]],[[None,1],[None,2]],r)
    check([['2024-01-01',1],[date(2024,1,1),2]],[[None,1],[None,2]],r,'wrong')


def test_v12_date_equivalence_survives_optional_top_n_matching():
    r=rules(['String'],top_n=1,tie_columns=[0])
    reference=[[date(2024,1,1)],[date(2024,1,1)]]
    check([['2024-01-01T00:00:00.000']],reference,r)
    check([['2024-01-02']],reference,r,'wrong')
    check([[[float('nan')]]],[[[float('nan')]]],rules(['Array(Float64)']),'wrong')


def test_v12_real_reconciliation_requires_the_reexported_bank(tmp_path):
    import json
    from scripts.validate_scorer_v2 import run
    corpus=tmp_path/'cases.jsonl'
    case={'case_id':'synthetic/bank','source':'synthetic','question_id':'S1','bank':'eval-v1.1@old',
          'candidate':[[1]],'refs':[[[1]]],'rules':[rules()]}
    corpus.write_text(json.dumps(case)+'\n')
    with pytest.raises(ValueError,match='eval-v1.2'):
        run([corpus],tmp_path/'out.jsonl',tmp_path/'report.md',eval_tag='eval-v1.2')
    case['bank']='eval-v1.2@new'
    corpus.write_text(json.dumps(case)+'\n')
    assert run([corpus],tmp_path/'out.jsonl',tmp_path/'report.md',eval_tag='eval-v1.2')==0


def test_v12_report_does_not_commit_execution_error_sql(tmp_path):
    import hashlib,json
    from scripts.validate_scorer_v2 import run,run_shared
    message='synthetic failure containing SELECT private_value FROM private_table'
    case={'case_id':'synthetic/error','source':'synthetic','question_id':'S1',
          'candidate':{'exec_error':message},'refs':[[[1]]],'rules':[rules()],
          'expected':{'outcome':'exec_error','reason':message}}
    corpus=tmp_path/'cases.jsonl';corpus.write_text(json.dumps(case)+'\n')
    for runner in [run,run_shared]:
        out=tmp_path/'out.jsonl';report=tmp_path/'report.md'
        assert runner([corpus] if runner is run else corpus,out,report)==0
        record=json.loads(out.read_text())
        assert record['outcome']=='exec_error' and record['reason']=='execution_failed'
        assert record['execution_error_sha256']==hashlib.sha256(message.encode()).hexdigest()
        assert message not in out.read_text() and 'SELECT' not in out.read_text()


def test_corpus_report_groups_by_case_id_suffix(tmp_path):
    import json
    from scripts.validate_scorer_v2 import run
    cases = [dict(case_id=case_id, source='synthetic', turn=0,
                  candidate=[[1]], refs=[[[1]]], rules=[rules()])
             for case_id in ('synthetic/final', 'synthetic/t0')]
    corpus = tmp_path / 'cases.jsonl'
    corpus.write_text(''.join(json.dumps(case) + '\n' for case in cases))
    output, report = tmp_path / 'out.jsonl', tmp_path / 'report.md'
    assert run([corpus], output, report) == 0
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert [record['phase'] for record in records] == ['final', 't0']
    assert '| final | 1 |' in report.read_text()
    assert '| t0 | 1 |' in report.read_text()


def test_legacy_flip_evidence_checks_null_identity_and_does_not_attribute_rank():
    from scripts.validate_scorer_v2 import explain_rejection
    rank_rule = rules(['String', 'UInt64'], rank_columns=[1], rankings=[{
        'column': 1, 'group_columns': [], 'object_columns': [0], 'prefix': False,
        'blocks': [{'group': [], 'rank': 1, 'dense': 1, 'size': 1},
                   {'group': [], 'rank': 2, 'dense': 2, 'size': 1}]}])
    ref = [['a', 1], ['b', 2]]
    proof = explain_rejection([['a', 2], ['b', 1]], [ref], [rank_rule], 'rank')
    assert proof is None
    assert explain_rejection([['c', 2], ['b', 1]], [ref], [rank_rule], 'rank') is None
    selection_rule = rules(['String', 'String', 'Float64'], selection={
        'version': 1, 'output_order': [], 'stages': [{
            'parent': None, 'where': [], 'group_columns': [0], 'object_columns': [1],
            'order_by': [{'column': 2, 'descending': True}], 'n': 1}]})
    ref = [[None, 'object', 10.0]]
    proof = explain_rejection([['invented', 'object', 10.0]], [ref], [selection_rule], 'values')
    assert proof[1]['status'] == 'identity_mismatch'
    assert explain_rejection([['invented', 'wrong object', 10.0]], [ref], [selection_rule], 'values') is None


@pytest.mark.parametrize('style', ['competition', 'dense', 'position'])
def test_v13_rank_counts_objects_across_repeated_output_rows_and_groups(style):
    r = rules(['String', 'String', 'String', 'Float64', 'UInt64'],
              rank_columns=[4], rankings=[{
                  'column': 4, 'group_columns': [0], 'object_columns': [1], 'prefix': True,
                  'blocks': [{'group': [group], 'rank': rank, 'dense': dense, 'size': size}
                             for group in ('g', 'h')
                             for rank, dense, size in ((1, 1, 2), (3, 2, 1))]}])
    ref = [[group, obj, bucket, score, rank]
           for group in ('g', 'h')
           for obj, score, rank in (('a', 10, 1), ('b', 10, 1), ('c', 9, 3))
           for bucket in ('x', 'y')]
    check(ref, ref, r)
    candidate = [row[:] for row in ref]
    for row in candidate:
        if style == 'dense' and row[1] == 'c':
            row[4] = 2
        if style == 'position':
            row[4] = {'a': 1, 'b': 2, 'c': 3}[row[1]]
            if row[0] == 'h' and row[1] in ('a', 'b'):
                row[4] = 3 - row[4]
    check(candidate, ref, r)
    bad = [row[:] for row in candidate]
    bad[-1][4] = 99
    check(bad, ref, r, 'wrong', 'rank')
    if style == 'position':
        bad = [row[:] for row in candidate]
        bad[2][4] = bad[3][4] = 1
        check(bad, ref, r, 'wrong', 'rank')
        bad = [row[:] for row in candidate]
        bad[1][4] = 2  # one object must have one position even across output rows
        check(bad, ref, r, 'wrong', 'rank')


def test_v13_selection_reason_for_identity_failures_and_values_only():
    r = rules(['String', 'String', 'Float64'], selection={
        'version': 1, 'output_order': [], 'stages': [{
            'parent': None, 'where': [], 'group_columns': [0], 'object_columns': [1],
            'order_by': [{'column': 2, 'descending': True}], 'n': 1}]})
    ref = [['g', 'a', 10], ['g', 'b', 9], ['h', 'c', 8], ['h', 'd', 7]]
    answer = [ref[0], ref[2]]
    check(answer, ref, r)
    for bad in (answer[:1], [], answer + [['extra', 'a', 10]],
                answer + [ref[1]], [ref[1], ref[2]],
                [['g', 'missing', 1000], ref[2]]):
        check(bad, ref, r, 'wrong', 'selection')
    check([['g', 'a', 1234], ref[2]], ref, r, 'wrong', 'values')
    check([['g', 'a', 10.001], ref[2]], ref, r)


def test_v13_order_stage_precedes_rank_when_nonrank_values_match():
    r = rules(['String', 'Float64', 'UInt64'], ordered=True,
              order_by=[{'column': 1, 'descending': True}], rank_columns=[2], rankings=[{
                  'column': 2, 'group_columns': [], 'object_columns': [0], 'prefix': True,
                  'blocks': [{'group': [], 'rank': rank, 'dense': rank, 'size': 1}
                             for rank in (1, 2)]}])
    ref = [['a', 100, 1], ['b', 90, 2]]
    check(ref, ref, r)
    check([['b', 90, 1], ['a', 100, 2]], ref, r, 'wrong', 'order')
    check([['a', 100, 2], ['b', 90, 1]], ref, r, 'wrong', 'rank')
    check(list(reversed(ref)), ref, r, 'wrong', 'order')


def test_v13_nonprefix_global_object_repeated_in_selection_groups():
    r = rules(['String', 'String', 'Float64', 'UInt64'], rank_columns=[3], rankings=[{
        'column': 3, 'group_columns': [], 'object_columns': [1], 'prefix': False,
        'blocks': [{'group': [], 'rank': 1, 'dense': 1, 'size': 1},
                   {'group': [], 'rank': 2, 'dense': 2, 'size': 1}]}])
    ref = [['g', 'a', 10, 1], ['h', 'a', 10, 1], ['i', 'b', 9, 2]]
    check(ref, ref, r)
    with_selection = {**r, 'selection': {
        'version': 1, 'output_order': [], 'stages': [{
            'parent': None, 'where': [], 'group_columns': [0], 'object_columns': [1],
            'order_by': [{'column': 2, 'descending': True}], 'n': 1}]}}
    check(ref, ref, with_selection)
    bad = [ref[0], ['h', 'a', 10, 2], ref[2]]
    check(bad, ref, r, 'wrong', 'rank')
    check(bad, ref, with_selection, 'wrong', 'rank')


def test_v13_hidden_object_identifiers_with_one_reference_row_per_object():
    r = rules(['UInt64', 'String', 'Float64', 'UInt64'], required_columns=[1, 2, 3],
              rank_columns=[3], rankings=[{
                  'column': 3, 'group_columns': [], 'object_columns': [0], 'prefix': True,
                  'blocks': [{'group': [], 'rank': 1, 'dense': 1, 'size': 2}]}])
    ref = [[100, 'a', 10, 1], [200, 'b', 10, 1]]
    check([['a', 10, 1], ['b', 10, 2]], ref, r)
    check([['a', 10, 2], ['b', 10, 1]], ref, r)
    check([['a', 10, 2], ['b', 10, 2]], ref, r, 'wrong', 'rank')
    check([['a', 10, 1], ['missing', 10, 2]], ref, r, 'wrong', 'values')
