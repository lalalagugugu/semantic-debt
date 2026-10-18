from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.scorer import score


def rules(types, **extra):
    return {'ordered': False, 'top_n': None, 'value_types': types,
            'value_kinds': ['other'] * len(types), 'required_columns': list(range(len(types))), **extra}


@pytest.mark.parametrize('empty', [None, '', '  '])
def test_empty_labels_match_only_nonconflicting_strings(empty):
    metadata = rules(['Nullable(String)', 'Int64'])
    ref = [[empty, 10], ['Known', 20]]
    assert score([['Unknown', 10], ['Known', 20]], [ref], metadata) == 'correct'
    assert score([['Known', 10], ['Known', 20]], [ref], metadata) == 'wrong'
    assert score([['Other', 10], ['Wrong', 20]], [ref], metadata) == 'wrong'
    assert score([[123, 10], ['Known', 20]], [ref], metadata) == 'wrong'


def test_numeric_null_is_not_a_label_or_zero():
    metadata = rules(['String', 'Nullable(Float64)'])
    for value in ['Unknown', 0, Decimal(0)]:
        assert score([['A', value]], [[['A', None]]], metadata) == 'wrong'


def test_null_label_context_is_per_reference_and_preserves_multiplicity():
    metadata = rules(['Nullable(String)', 'Int64'])
    ref = [[None, 10], [None, 10], ['Known', 20]]
    assert score([['Unknown', 10], ['Unknown', 10], ['Known', 20]], [ref], metadata) == 'correct'
    assert score([['Unknown', 10], ['Known', 20]], [ref], metadata) == 'wrong'
    assert score([['Other', 10]], [[[None, 10]], [['Other', 20]]], metadata) == 'correct'


def test_only_original_adjacent_name_columns_join_in_original_order():
    metadata = rules(['String', 'Int64'])
    ref = [['Jane Doe', 10], ['John Smith', 20]]
    assert score([['Jane', 'Doe', 10], ['John', 'Smith', 20]], [ref], metadata) == 'correct'
    assert score([['Doe', 'Jane', 10], ['Smith', 'John', 20]], [ref], metadata) == 'wrong'
    assert score([['Jane', 10, 'Doe'], ['John', 20, 'Smith']], [ref], metadata) == 'wrong'
    # Joining cannot consume a source column twice to satisfy another answer.
    assert score([['Jane', 'Doe']], [[['Jane Doe', 'Jane']]], rules(['String', 'String'])) == 'wrong'


@pytest.mark.parametrize('timestamp', ['2008-01-01 00:00:00', '2008-01-01T00:00:00.000', datetime(2008, 1, 1)])
def test_date_equals_same_day_midnight(timestamp):
    metadata = rules(['Date', 'Int64'])
    assert score([[timestamp, 10]], [[['2008-01-01', 10]]], metadata) == 'correct'
    assert score([[date(2008, 1, 1), 10]], [[[timestamp, 10]]], metadata) == 'correct'


@pytest.mark.parametrize('value', ['2008-01-01 00:00:01', '2008-01-01 01:00:00', '2008-01-02 00:00:00', '2008-01-01T00:00:00Z', '2008-02-30 00:00:00'])
def test_date_equivalence_does_not_drop_time_timezone_or_invalid_dates(value):
    assert score([[value]], [[['2008-01-01']]], rules(['Date'])) == 'wrong'


def test_unordered_pairs_swap_attributes_together_per_row():
    metadata = rules(['Int64', 'String', 'Int64', 'String', 'Int64'],
                     required_columns=[0, 1, 2, 3, 4],
                     unordered_pairs=[{'left': [0, 1], 'right': [2, 3]}])
    ref = [[1, 'A', 2, 'B', 10], [3, 'C', 4, 'D', 20]]
    assert score([[2, 'B', 1, 'A', 10], [3, 'C', 4, 'D', 20]], [ref], metadata) == 'correct'
    assert score([[2, 'A', 1, 'B', 10], [3, 'C', 4, 'D', 20]], [ref], metadata) == 'wrong'
    assert score([[2, 'B', 1, 'A', 11], [3, 'C', 4, 'D', 20]], [ref], metadata) == 'wrong'
    assert score([[2, 'B', 1, 'A', 10]], [ref], metadata) == 'wrong'


@pytest.mark.parametrize('pair', [None, [[0, 1]], [{'left': [0], 'right': [0]}], [{'left': [0], 'right': [1, 2]}], [{'left': [0], 'right': [3]}]])
def test_invalid_unordered_pairs_fail(pair):
    with pytest.raises(ValueError, match='unordered_pairs'):
        score([[1, 2]], [[[1, 2]]], rules(['Int64', 'Int64'], unordered_pairs=pair))



def test_zero_count_groups_are_optional_in_both_directions():
    metadata = rules(['String','UInt64','Nullable(Float64)'], value_kinds=['other','count','amount'])
    ref = [['A',2,10],['B',0,None],['C',0,0]]
    assert score([['A',2,10]], [ref], metadata) == 'correct'
    assert score([['A',2,10],['extra',0,0]], [ref[:1]], metadata) == 'correct'
    assert score([['A',2,10],['extra',0,None]], [ref], metadata) == 'correct'
    assert score([], [[['B',0,None]]], metadata) == 'correct'
    assert score([['B',0,None]], [[]], metadata) == 'correct'
    assert score([['A',2,10],['extra',0,5]], [ref], metadata) == 'wrong'
    assert score([['A',2,10]], [[['A',2,10],['extra',0,5]]], metadata) == 'wrong'
    assert score([['A',2,10],['extra',0,'0']], [ref], metadata) == 'wrong'
    assert score([['A',2,10],['extra',None,None]], [ref], metadata) == 'wrong'


def test_zero_group_detection_follows_reference_column_mapping_and_required_projection():
    metadata = rules(['String','UInt64','Float64'], value_kinds=['other','count','amount'],required_columns=[0,1])
    assert score([[2,'A'],[0,'B']], [[['A',2,50]]], metadata) == 'correct'
    assert score([], [[['B',0,100]]], metadata) == 'correct'  # Optional amount is not compared.
    assert score([['A',0]], [[['A',1,0]]], metadata) == 'wrong'
    assert score([['A',0],['B',1]], [[['A',0,0]]], metadata) == 'wrong'


def test_zero_measures_without_a_required_count_are_not_optional():
    assert score([], [[['A',0]]], rules(['String','Float64'],value_kinds=['other','amount'])) == 'wrong'
    assert score([], [[['A',None]]], rules(['String','Nullable(UInt64)'],value_kinds=['other','count'])) == 'wrong'


def test_zero_group_rule_does_not_relax_top_n_quota():
    metadata = rules(['String','UInt64'],value_kinds=['other','count'],ordered=True,top_n=2,
                     tie_columns=[1],order_by=[{'column':1,'descending':True}])
    assert score([['A',1]], [[['A',1],['B',0]]], metadata) == 'wrong'



def test_label_conflicts_respect_date_normalization():
    metadata = rules(['Nullable(String)','Int64'])
    ref = [[None,10],['2008-01-01',20]]
    assert score([['2008-01-01 00:00:00',10],['2008-01-01',20]], [ref], metadata) == 'wrong'
    assert score([['Unknown',10],['2008-01-01 00:00:00',20]], [ref], metadata) == 'correct'



def test_identifier_columns_use_exact_values_not_percentage_or_relative_tolerance():
    metadata = rules(['Nullable(String)','Int64','Float64'],identifier_columns=[1],value_kinds=['other','other','amount'])
    ref = [[None,10000,20]]
    assert score([['Unknown',10000,20]], [ref], metadata) == 'correct'
    assert score([['Unknown',10000.0,20]], [ref], metadata) == 'correct'
    for key in [10001,100,False,'10000']:
        assert score([['Unknown',key,20]], [ref], metadata) == 'wrong'


def test_identifier_is_not_a_measure_when_ignoring_zero_groups():
    metadata = rules(['Int64','String','UInt64','Float64'],value_kinds=['other','other','count','amount'],identifier_columns=[0])
    ref = [[10000,'A',2,10],[10001,'B',0,0]]
    assert score([[10000,'A',2,10]], [ref], metadata) == 'correct'
    assert score([[10000,'A',2,10],[10002,'C',0,0]], [ref[:1]], metadata) == 'correct'
    assert score([[10000,'A',2,10],[10002,'C',0,5]], [ref], metadata) == 'wrong'


def test_competition_rank_columns_are_exact_and_do_not_match_percentages():
    metadata = rules(['String','UInt64'],rank_columns=[1])
    ref = [['A',1],['B',1],['C',3],['D',10000]]
    assert score(ref,[ref],metadata) == 'correct'
    for value in [100,1.001,True,'1']:
        assert score([['A',value],*ref[1:]],[ref],metadata) == 'wrong'
    assert score([*ref[:3],['D',10001]],[ref],metadata) == 'wrong'


@pytest.mark.parametrize('field',['identifier_columns','rank_columns'])
@pytest.mark.parametrize('indexes',[[True],[-1],[0,0],[2],'0',None])
def test_exact_column_roles_are_validated(field,indexes):
    with pytest.raises(ValueError,match=field):
        score([[1]],[[[1]]],rules(['Int64'],**{field:indexes}))


def ranked_rules(*, grouped=False, prefix=False, top_n=None):
    metadata = rules(['String','Float64','UInt64'], ordered=True,
                     order_by=[{'column':1,'descending':True}],
                     rank_columns=[2], top_n=top_n, tie_columns=[1])
    metadata['rankings']=[{'column':2,'group_columns':[], 'object_columns':[0],
        'prefix':prefix,'blocks':[
            {'group':[],'rank':1,'dense':1,'size':2},
            {'group':[],'rank':3,'dense':2,'size':2},
            {'group':[],'rank':5,'dense':3,'size':1}]}]
    return metadata


@pytest.mark.parametrize('ranks', [[1,1,3,3,5], [1,1,2,2,3], [1,2,3,4,5]])
def test_whole_answer_accepts_each_consistent_ranking_style(ranks):
    ref=[['A',90,1],['B',90,1],['C',80,3],['D',80,3],['E',70,5]]
    candidate=[[name,value,rank] for (name,value,_),rank in zip(ref,ranks)]
    assert score(candidate,[ref],ranked_rules())=='correct'


def test_mixed_ranking_styles_are_rejected():
    ref=[['A',90,1],['B',90,1],['C',80,3],['D',80,3],['E',70,5]]
    candidate=[['A',90,1],['B',90,1],['C',80,2],['D',80,2],['E',70,5]]
    assert score(candidate,[ref],ranked_rules())=='wrong'


def test_rank_shift_without_ties_is_rejected():
    ref=[['A',90,1],['B',80,2],['C',70,3]]
    metadata=ranked_rules()
    metadata['rankings'][0]['blocks']=[{'group':[],'rank':i,'dense':i,'size':1} for i in [1,2,3]]
    assert score([['A',90,1],['B',80,3],['C',70,2]],[ref],metadata)=='wrong'


def test_position_ranks_are_distinct_and_tie_order_is_free():
    ref=[['A',90,1],['B',90,1],['C',80,3],['D',80,3],['E',70,5]]
    candidate=[['B',90,1],['A',90,2],['D',80,3],['C',80,4],['E',70,5]]
    assert score(candidate,[ref],ranked_rules())=='correct'
    candidate[1][2]=1
    assert score(candidate,[ref],ranked_rules())=='wrong'


def test_one_ranking_style_applies_across_groups():
    metadata=rules(['String','String','Float64','UInt64'],rank_columns=[3])
    metadata['rankings']=[{'column':3,'group_columns':[0],'object_columns':[1], 'prefix':True,
        'blocks':[{'group':[g],'rank':r,'dense':d,'size':s} for g in ['X','Y'] for r,d,s in [(1,1,2),(3,2,1)]]}]
    ref=[[g,n,v,r] for g in ['X','Y'] for n,v,r in [('A',90,1),('B',90,1),('C',80,3)]]
    dense=[[g,n,v,2 if r==3 else r] for g,n,v,r in ref]
    assert score(dense,[ref],metadata)=='correct'
    mixed=[row[:] for row in dense];mixed[-1][-1]=3
    assert score(mixed,[ref],metadata)=='wrong'


def test_top_n_position_numbers_stop_at_selected_prefix():
    ref=[['A',90,1],['B',90,1],['C',80,3],['D',80,3],['E',70,5]]
    metadata=ranked_rules(prefix=True,top_n=3)
    ref=ref[:4]
    assert score([['B',90,1],['A',90,2],['D',80,3]],[ref],metadata)=='correct'
    assert score([['B',90,1],['A',90,2],['D',80,4]],[ref],metadata)=='wrong'


def test_selected_subset_keeps_complete_population_dense_rank():
    metadata=ranked_rules()
    ref=[['E',70,5]]
    assert score([['E',70,3]],[ref],metadata)=='correct'
    assert score([['E',70,1]],[ref],metadata)=='wrong'
