"""Synthetic presentation equivalence and adversarial boundary coverage."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import scorer_v2 as V2, scorer_v3 as V3


def rules(types, **extra):
    return {'required_columns': list(range(len(types))), 'value_types': list(types),
            'value_kinds': ['other'] * len(types), 'ordered': False,
            'top_n': None, 'tie_columns': [], **extra}


def columns(names, types):
    return [{'name': n, 'type': t} for n, t in zip(names, types)]


def evaluate(candidate, ref, names, cnames=None, *, types=None, ctypes=None, **extra):
    types = types or ['String'] * (len(names) - 1) + ['Float64']
    ctypes = ctypes or types
    metadata = rules(types, **extra)
    evidence = {'candidate_columns': columns(cnames or names, ctypes),
                'reference_columns': [columns(names, types)]}
    before = deepcopy((candidate, ref, metadata, evidence))
    result = V3.score_detailed(candidate, [ref], metadata, **evidence)
    assert (candidate, ref, metadata, evidence) == before
    return result


@pytest.mark.parametrize('label', ['January', '1月', '01'])
def test_month_labels(label):
    assert evaluate([[label, 20]], [[1, 20]], ['month', 'amount'],
                    types=['UInt8', 'Float64']).sensitivity == 'P1'


@pytest.mark.parametrize('label', ['Year 2031', '2031', '2031年'])
def test_year_labels(label):
    assert evaluate([[label, 20]], [[2031, 20]], ['year', 'amount'],
                    types=['UInt16', 'Float64']).outcome == 'correct'


@pytest.mark.parametrize('label', ['Q2', '第二季度', '第2季度'])
def test_quarter_labels(label):
    assert evaluate([[label, 20]], [[2, 20]], ['quarter', 'amount'],
                    types=['UInt8', 'Float64']).outcome == 'correct'


def test_split_and_fused_months_both_directions():
    split = [[2031, 1, 20], [2032, 1, 30]]
    fused = [['2031-01-01', 20], ['2032-01-01', 30]]
    assert evaluate(fused, split, ['year', 'month', 'amount'], ['month', 'amount'],
        types=['UInt16', 'UInt8', 'Float64'], ctypes=['Date', 'Float64']).outcome == 'correct'
    assert evaluate(split, fused, ['month', 'amount'], ['year', 'month', 'amount'],
        types=['Date', 'Float64'], ctypes=['UInt16', 'UInt8', 'Float64']).outcome == 'correct'


def test_no_year_can_be_discarded_even_if_candidate_has_only_one_year():
    assert evaluate([['2031-01-01', 20]], [[1, 20]], ['month', 'amount'],
                    types=['UInt8', 'Float64']).outcome == 'wrong'


@pytest.mark.parametrize('value', ['2032-01-01', '2031-01-02', '2031-02-30',
    '2031-01-01T00:00:01', '2031-01-01T00:00:00Z', '2031-13', 'Unknown'])
def test_wrong_invalid_or_noninitial_periods(value):
    assert evaluate([[2031, value, 20]], [[2031, 1, 20]], ['year', 'month', 'amount'],
        types=['UInt16', 'String', 'Float64']).outcome == 'wrong'


def test_business_contexts_are_not_merged_or_translated():
    assert evaluate([[2031, '2032-01-01', 20]], [[2031, 1, 20]],
        ['cohort_year', 'cohort_month', 'amount'], types=['UInt16', 'String', 'Float64']).outcome == 'wrong'
    assert evaluate([['January', 20]], [[1, 20]], ['product', 'amount'],
        cnames=['month', 'amount'], types=['UInt8', 'Float64']).outcome == 'wrong'


def test_calendar_equivalence_preserves_duplicates_and_values():
    ref = [[2031, 1, 20], [2031, 1, 20]]
    names, types = ['year', 'month', 'amount'], ['UInt16', 'UInt8', 'Float64']
    assert evaluate([['2031', 'January', 20]] * 2, ref, names, types=types).outcome == 'correct'
    assert evaluate([['2031', 'January', 20]], ref, names, types=types).outcome == 'wrong'
    assert evaluate([['2031', 'January', 22]] * 2, ref, names, types=types,
                    value_kinds=['other', 'other', 'amount']).outcome == 'wrong'


def test_period_order_is_preserved_including_cross_year():
    ref = [['2031-12-01', 20], ['2032-01-01', 30]]
    candidate = [[2031, 'December', 20], [2032, 'January', 30]]
    kwargs = dict(cnames=['year', 'month', 'amount'], types=['Date', 'Float64'],
                  ctypes=['UInt16', 'String', 'Float64'], ordered=True,
                  order_by=[{'column': 0, 'descending': False}])
    assert evaluate(candidate, ref, ['month', 'amount'], **kwargs).outcome == 'correct'
    assert evaluate(candidate[::-1], ref, ['month', 'amount'], **kwargs).outcome == 'wrong'


@pytest.mark.parametrize('kind', ['count', 'amount', 'ratio'])
def test_measure_named_month_is_not_a_dimension(kind):
    assert evaluate([['January', 20]], [[1, 20]], ['month', 'amount'],
        types=['UInt8', 'Float64'], value_kinds=[kind, 'amount']).outcome == 'wrong'


def test_p1_does_not_rewrite_selection_or_identifier_contracts():
    assert evaluate([['January', 20]], [[1, 20]], ['month', 'amount'],
        types=['UInt8', 'Float64'], identifier_columns=[0]).outcome == 'wrong'
    assert evaluate([['January', 20]], [[1, 20]], ['month', 'amount'],
        types=['UInt8', 'Float64'], ordered=True, top_n=1, tie_columns=[1],
        order_by=[{'column': 1, 'descending': True}]).outcome == 'wrong'


def wide_long(candidate, reference=None, **extra):
    reference = reference or [['east', 'actual', 20], ['east', 'budget', 30],
                              ['west', 'actual', 40], ['west', 'budget', 50]]
    return evaluate(candidate, reference, ['region', 'scenario', 'amount'],
        ['region', 'actual', 'budget'], types=['String', 'String', 'Float64'],
        ctypes=['String', 'Float64', 'Float64'], **extra)


def test_wide_to_long_exact_members():
    result = wide_long([['east', 20, 30], ['west', 40, 50]])
    assert result.outcome == 'correct' and result.sensitivity == 'P2'


def test_long_to_wide_exact_members():
    assert evaluate([['east', 'actual', 20], ['east', 'budget', 30]], [['east', 20, 30]],
        ['region', 'actual', 'budget'], ['region', 'scenario', 'amount'],
        types=['String', 'Float64', 'Float64'], ctypes=['String', 'String', 'Float64']).sensitivity == 'P2'


@pytest.mark.parametrize('candidate', [[['east', 30, 20], ['west', 40, 50]],
    [['east', 20, 30]], [['east', 20, 30], ['east', 40, 50]],
    [['east', 20, 30], ['west', 40, 50], ['west', 40, 50]]])
def test_p2_does_not_move_values_drop_groups_or_deduplicate(candidate):
    assert wide_long(candidate).outcome == 'wrong'


def test_p2_no_business_synonym_translation_or_missing_member():
    assert evaluate([['east', 20, 30]], [['east', 'actual', 20], ['east', 'budget', 30]],
        ['region', 'scenario', 'amount'], ['region', '实际', '预算'],
        types=['String', 'String', 'Float64'], ctypes=['String', 'Float64', 'Float64']).outcome == 'wrong'
    assert evaluate([['east', 20]], [['east', 'actual', 20], ['east', 'budget', 30]],
        ['region', 'scenario', 'amount'], ['region', 'actual'],
        types=['String', 'String', 'Float64'], ctypes=['String', 'Float64']).outcome == 'wrong'


def test_p2_preserves_order_and_top_n_quota():
    order = {'ordered': True, 'order_by': [{'column': 0, 'descending': False}]}
    assert wide_long([['east', 20, 30], ['west', 40, 50]], **order).outcome == 'correct'
    assert wide_long([['west', 40, 50], ['east', 20, 30]], **order).outcome == 'wrong'
    tied = [['east', 'actual', 50], ['east', 'budget', 50],
            ['west', 'actual', 50], ['west', 'budget', 50]]
    assert wide_long([['east', 50, 50], ['west', 50, 50]], tied,
        ordered=True, order_by=[{'column': 2, 'descending': True}], top_n=1,
        tie_columns=[2]).outcome == 'wrong'


@pytest.mark.parametrize('blank', [None, ''])
def test_p3_numeric_name_keeps_exact_key(blank):
    result = evaluate([[42, 42, 20]], [[42, blank, 20]], ['entity_id', 'name', 'amount'],
        types=['Int64', 'String', 'Float64'], identifier_columns=[0])
    assert result.sensitivity == 'P3'


@pytest.mark.parametrize('normal', ['Unknown', '未知', 'NULL', 'N/A', ' '])
def test_p3_never_reclassifies_textual_members_as_blank(normal):
    result = evaluate([[42, 42, 20]], [[42, normal, 20]], ['entity_id', 'name', 'amount'],
        types=['Int64', 'String', 'Float64'], identifier_columns=[0])
    assert result.outcome == 'wrong'


@pytest.mark.parametrize('candidate', [[[43, 42, 20]], [[42, 43, 20]], [[42, 42, 22]], [[42, 20]]])
def test_p3_rejects_wrong_key_name_measure_or_missing_key(candidate):
    cnames = ['entity_id', 'name', 'amount'] if len(candidate[0]) == 3 else ['name', 'amount']
    assert evaluate(candidate, [[42, None, 20]], ['entity_id', 'name', 'amount'], cnames,
        types=['Int64', 'String', 'Float64'], ctypes=['Int64', 'String', 'Float64'] if len(cnames) == 3 else ['String', 'Float64'],
        identifier_columns=[0]).outcome == 'wrong'


def test_p3_ambiguous_repeated_identity_not_replaced():
    assert evaluate([[42, 42, 20], [42, 'Real', 30]], [[42, None, 20], [42, 'Real', 30]],
        ['id', 'name', 'amount'], types=['Int64', 'String', 'Float64'], identifier_columns=[0]).outcome == 'wrong'


def test_p4_already_supported_in_v2():
    metadata = rules(['String', 'Float64'])
    candidate, refs = [[99, 20, 'east', 'constant']], [[['east', 20]]]
    assert V2.score(candidate, refs, metadata) == 'correct'
    assert V3.score(candidate, refs, metadata) == 'correct'
    assert V3.score([*candidate, *candidate], refs, metadata) == 'wrong'


def test_without_evidence_or_on_nonwrong_input_v3_is_v2():
    metadata = rules(['UInt64'])
    for value in [[[1]], [[2]], [], V2.REFUSAL, V2.ExecError('failed')]:
        assert V3.score(value, [[[1]]], metadata) == V2.score(value, [[[1]]], metadata)
    with pytest.raises(ValueError, match='width'):
        V3.score([[2]], [[[1]]], metadata, candidate_columns=[], reference_columns=[[]])


def test_multiple_references_use_own_rules_and_report_original_index():
    metadata = rules(['UInt16', 'Float64'])
    result = V3.score_detailed([['Year 2031', 20]], [[[2030, 20]], [[2031, 20]]], metadata,
        candidate_columns=columns(['year', 'amount'], ['String', 'Float64']),
        reference_columns=[columns(['year', 'amount'], metadata['value_types'])] * 2,
        reference_rules=[metadata, metadata])
    assert result.outcome == 'correct' and result.matched_ref == 1


def test_missing_reference_evidence_and_array_rows_keep_v2_verdict():
    metadata = rules(['UInt16', 'UInt64'])
    assert V3.score([['Year 2031', 20]], [[[2031, 20]]], metadata,
        candidate_columns=columns(['year', 'count'], ['String', 'UInt64']),
        reference_columns=[None]) == 'wrong'
    assert V3.score_detailed((([1, 2], 'January', 20),),
        [(([1, 2], 2, 20),)], rules(['Array(Int64)', 'UInt8', 'UInt64']),
        candidate_columns=columns(['group', 'month', 'count'], ['Array(Int64)', 'String', 'UInt64']),
        reference_columns=[columns(['group', 'month', 'count'], ['Array(Int64)', 'UInt8', 'UInt64'])]).outcome == 'wrong'
