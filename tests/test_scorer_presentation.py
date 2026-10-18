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
