"""Boundaries of the evidence audit, independent of private benchmark data."""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.t31_content_audit import compare, evaluate
from scripts.t31_candidate_scan import variants, zero_amount_variant, numeric_null_needs_ruling


def test_null_is_not_a_defined_zero():
    result = compare([['group', None]], [['group', 0]], ['label', 'percentage'])
    assert result['identities_equal']
    assert not result['normalized_values_equal']


def test_wrong_amount_is_not_hidden_by_projection():
    result = compare([['group', 120]], [['group', 100]], ['label', 'amount'])
    assert not result['normalized_values_equal']


def test_counts_remain_exact():
    result = compare([['group', 200]], [['group', 199]], ['label', 'count'])
    assert not result['normalized_values_equal']


def test_period_normalization_preserves_year():
    with pytest.raises(ValueError, match='different year'):
        evaluate(['month', ['col', 0], 2020], ['2021-01-01'], [])


def test_duplicate_identity_cannot_disappear():
    with pytest.raises(ValueError, match='not unique'):
        compare([['group', 1], ['group', 1]], [['group', 1]], ['label', 'count'])


def test_top_n_cannot_omit_a_strictly_higher_object():
    result = compare([['low', 10]], [['high', 20], ['low', 10]],
                     ['label', 'amount'], mode='top_n', top_n=1)
    assert not result['identities_equal']


def test_boundary_tie_can_select_one_member():
    result = compare([['second', 10]], [['first', 10], ['second', 10]],
                     ['label', 'amount'], mode='top_n', top_n=1)
    assert result['identities_equal']
    assert result['normalized_values_equal']


def test_sort_rule_preserves_an_explicit_request():
    cols = [{'name': 'label', 'type': 'String'}]
    assert not list(variants('R7', [['a']], [['a']], {'ordered': True}, cols, cols, '按名称降序排序'))


def test_nested_results_are_not_guessed():
    cols = [{'name': 'label', 'type': 'Array(String)'}]
    assert not list(variants('R5', [[['未知']]], [[None]], {}, cols, cols, ''))


def test_empty_amount_alternative_does_not_change_a_ratio():
    rule = {'value_kinds': ['count', 'percentage']}
    cols = [{'name': 'stores', 'type': 'UInt64'}, {'name': 'ratio', 'type': 'Float64'}]
    assert zero_amount_variant([[0, None]], [[0, 0]], rule, cols, cols) is None


def test_relaxing_an_identifier_cannot_implicitly_approve_null_zero():
    rule = {'required_columns': [0, 1, 2], 'value_types': ['String', 'UInt64', 'Float64']}
    cols = [{'name': 'manager', 'type': 'String'}, {'name': 'stores', 'type': 'UInt64'},
            {'name': 'gap', 'type': 'Nullable(Float64)'}]
    assert numeric_null_needs_ruling([['manager', 0, None]], [['manager', 0, 0]], rule, cols)


def test_matching_total_cannot_hide_wrong_group_amounts():
    cc = [{'name': 'day', 'type': 'String'}, {'name': 'sales_amount', 'type': 'Float64'},
          {'name': 'share', 'type': 'Float64'}]
    rc = cc[:2] + [{'name': 'percentage', 'type': 'Float64'}, {'name': 'total_sales_amount', 'type': 'Float64'}]
    rule = {'required_columns': [0, 2, 3], 'value_kinds': ['other', 'amount', 'percentage', 'amount']}
    assert not list(variants('R9', [['a', 150, 1/3], ['b', 150, 2/3]],
                             [['a', 100, 100/3, 300], ['b', 200, 200/3, 300]], rule, cc, rc, ''))


def test_pivot_cannot_hide_a_contradictory_variance():
    cc = [{'name': 'CategoryName', 'type': 'String'}, {'name': 'ActualRevenue', 'type': 'Float64'},
          {'name': 'BudgetRevenue', 'type': 'Float64'}, {'name': 'RevenueVariance', 'type': 'Float64'}]
    rc = [{'name': 'category', 'type': 'String'}, {'name': 'scenario', 'type': 'String'},
          {'name': 'sales_amount', 'type': 'Float64'}]
    rule = {'required_columns': [0, 1, 2], 'value_kinds': ['other', 'other', 'amount']}
    assert not list(variants('R2', [['a', 100, 80, 999]], [['a', 'Actual', 100], ['a', 'Budget', 80]], rule, cc, rc, ''))
