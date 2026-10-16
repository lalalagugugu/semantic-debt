from copy import deepcopy
from decimal import Decimal
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.scorer import score, score_detailed
from harness.selection import complete_selection


def order(column, descending=True):
    return {'column': column, 'descending': descending}


def stage(group, obj, key, n, parent=None, where=None):
    return {'parent': parent, 'where': where or [], 'group_columns': group, 'object_columns': obj, 'order_by': [order(key)], 'n': n}


def rules(stages, kinds, output=None):
    return {'ordered': bool(output), 'top_n': None, 'tie_columns': [], 'value_kinds': kinds, 'value_types': ['String' if k == 'other' else 'Float64' for k in kinds], 'selection': {'version': 1, 'stages': stages, 'output_order': output or []}}


GROUPS = [['A', 'a', 10], ['A', 'b', 10], ['B', 'c', 5], ['B', 'd', 5]]
GROUP_RULES = rules([stage([0], [1], 2, 1)], ['other', 'other', 'amount'])


def test_group_ties_require_each_group_and_unique_object():
    assert score([GROUPS[0], GROUPS[2]], [GROUPS], GROUP_RULES) == 'correct'
    assert score([GROUPS[1], GROUPS[3]], [GROUPS], GROUP_RULES) == 'correct'
    for rows in ([GROUPS[0]], [GROUPS[0], GROUPS[1]], [GROUPS[0], GROUPS[0], GROUPS[2]], GROUPS):
        assert score(rows, [GROUPS], GROUP_RULES) == 'wrong'


def test_strict_prefix_cannot_be_replaced_by_another_boundary_member():
    ref = [['A', 'a', 20], ['A', 'b', 10], ['A', 'c', 10]]
    metadata = rules([stage([0], [1], 2, 2)], ['other', 'other', 'amount'])
    assert score([ref[0], ref[2]], [ref], metadata) == 'correct'
    assert score(ref[1:], [ref], metadata) == 'wrong'
    assert score(ref, [ref], metadata) == 'wrong'


def test_parent_choice_controls_required_child_groups():
    ref = [['A', 100, 'a', 10], ['A', 100, 'b', 10], ['B', 100, 'c', 8], ['C', 50, 'd', 20]]
    metadata = rules([stage([], [0], 1, 1), stage([0], [2], 3, 1, parent=0)], ['other', 'amount', 'other', 'amount'])
    complete, checks = complete_selection(ref, metadata['selection'], metadata['value_kinds'])
    assert complete == ref[:3] and checks[0][0]['boundary'] == 2
    assert score([ref[0]], [complete], metadata) == 'correct'
    assert score([ref[2]], [complete], metadata) == 'correct'
    assert score([ref[0], ref[2]], [complete], metadata) == 'wrong'
    assert score([ref[3]], [complete], metadata) == 'wrong'
    with pytest.raises(ValueError, match='below a boundary'):
        score([ref[0]], [ref], metadata)


def test_independent_branches_have_opposite_directions():
    ref = [['HIGH', 'a', 100], ['HIGH', 'b', 100], ['LOW', 'c', 5], ['LOW', 'd', 5]]
    high = stage([0], [1], 2, 1, where=[{'column': 0, 'equals': 'HIGH'}])
    low = stage([0], [1], 2, 1, where=[{'column': 0, 'equals': 'LOW'}])
    low['order_by'][0]['descending'] = False
    metadata = rules([high, low], ['other', 'other', 'amount'])
    assert score([ref[1], ref[3]], [ref], metadata) == 'correct'
    assert score(ref[:2], [ref], metadata) == 'wrong'


def test_fixed_quantization_not_result_tolerance_controls_members():
    ref = [['A', 'a', Decimal('1.004')], ['A', 'b', Decimal('1.005')], ['A', 'c', Decimal('0.999')], ['A', 'd', Decimal('0.994')]]
    complete, _ = complete_selection(ref, GROUP_RULES['selection'], GROUP_RULES['value_kinds'])
    assert complete == ref[:3]
    assert score([ref[2]], [complete], GROUP_RULES) == 'correct'
    assert score([ref[3]], [complete], GROUP_RULES) == 'wrong'


def test_object_identity_is_exact_even_when_numeric_values_are_close():
    metadata = rules([stage([0], [1], 2, 1)], ['other', 'other', 'amount'])
    ref = [['A', 10000, 50]]
    assert score([['A', 10001, 50]], [ref], metadata) == 'wrong'
    assert score([['A', 10000, 50.001]], [ref], metadata) == 'correct'


def test_column_permutations_extra_columns_and_percentage_units():
    ref = [['A', 'a', 50]]
    metadata = rules([stage([0], [1], 2, 1)], ['other', 'other', 'percentage'])
    assert score([[0.5, 'a', 'A', 'extra']], [ref], metadata) == 'correct'


def test_output_order_uses_reference_quantized_values():
    metadata = rules([stage([0], [1], 2, 1)], ['other', 'other', 'amount'], [order(2)])
    rows = [GROUPS[0], GROUPS[2]]
    assert score(rows, [GROUPS], metadata) == 'correct'
    assert score(rows[::-1], [GROUPS], metadata) == 'wrong'


def test_empty_domain_and_fewer_than_n():
    assert score([], [[]], GROUP_RULES) == 'correct'
    assert score([], [GROUPS], GROUP_RULES) == 'wrong'
    metadata = rules([stage([0], [1], 2, 5)], ['other', 'other', 'amount'])
    assert score([GROUPS[0]], [[GROUPS[0]]], metadata) == 'correct'
    assert score([GROUPS[0], GROUPS[0]], [[GROUPS[0]]], metadata) == 'wrong'


@pytest.mark.parametrize('change', [
    lambda s: s.update(version=2),
    lambda s: s['stages'][0].update(n=0),
    lambda s: s['stages'][0].update(n=True),
    lambda s: s['stages'][0].update(parent=0),
    lambda s: s['stages'][0].update(object_columns=[]),
    lambda s: s['stages'][0].update(group_columns=[4]),
    lambda s: s['stages'][0].update(order_by=[]),
    lambda s: s['stages'][0].update(unknown=True),
])
def test_malformed_spec_is_rejected(change):
    metadata = deepcopy(GROUP_RULES)
    change(metadata['selection'])
    with pytest.raises(ValueError):
        score([GROUPS[0]], [GROUPS], metadata)


def test_inconsistent_parent_value_and_duplicate_leaf_are_rejected():
    metadata = rules([stage([], [0], 1, 1), stage([0], [2], 3, 1, parent=0)], ['other', 'amount', 'other', 'amount'])
    with pytest.raises(ValueError, match='inconsistent'):
        score([], [[['A', 100, 'a', 5], ['A', 90, 'b', 5]]], metadata)
    with pytest.raises(ValueError, match='duplicate leaf'):
        score([GROUPS[0]], [[GROUPS[0], GROUPS[0]]], GROUP_RULES)


def test_per_reference_rules_override_and_fallback_with_different_widths():
    common = {'ordered': False, 'top_n': None, 'value_kinds': ['count'], 'value_types': ['UInt64']}
    refs = [[[10000]], [['A', 1.0]]]
    overrides = [None, {**common, 'value_kinds': ['other', 'amount'], 'value_types': ['String', 'Float64']}]
    assert score([['A', 1.009]], refs, common, reference_rules=overrides) == 'correct'
    assert score([[10001]], refs, common, reference_rules=overrides) == 'wrong'
    assert score_detailed([[10000]], refs, common, reference_rules=overrides).matched_ref == 0
    with pytest.raises(ValueError, match='align'):
        score([[10000]], refs, common, reference_rules=[None])


def test_numeric_branch_condition_is_an_exact_identity():
    left = stage([], [1], 2, 1, where=[{'column': 0, 'equals': 100}])
    right = stage([], [1], 2, 1, where=[{'column': 0, 'equals': 200}])
    metadata = rules([left, right], ['other', 'other', 'amount'])
    ref = [[100, 'a', 10], [200, 'b', 5]]
    assert score(ref, [ref], metadata) == 'correct'
    assert score([[10000, 'a', 10], ref[1]], [ref], metadata) == 'wrong'


def test_child_group_must_retain_parent_identity():
    metadata = rules([stage([], [0], 1, 1), stage([], [2], 3, 1, parent=0)], ['other', 'amount', 'other', 'amount'])
    with pytest.raises(ValueError, match='retain'):
        score([], [[]], metadata)


def test_explicit_incomplete_reference_rules_do_not_silently_fall_back():
    common = {'ordered': False, 'top_n': None}
    with pytest.raises(ValueError, match='missing required'):
        score([[1]], [[[1]]], common, reference_rules=[{}])
