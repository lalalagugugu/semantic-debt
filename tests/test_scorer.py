from decimal import Decimal
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness.scorer import (
    BOUNDARY_TIE_FULL_GROUP,
    ExecError,
    score,
    score_detailed,
)


UNORDERED = {"ordered": False, "top_n": None}
ORDERED = {"ordered": True, "top_n": None}


def test_complete_result_set_matches_all_rows() -> None:
    assert score([(1,), (2,)], [[(2,), (1,)]], UNORDERED) == "correct"


@pytest.mark.parametrize("candidate", [[(1,)], [(1,), (2,), (3,)]])
def test_complete_result_set_rejects_missing_or_extra_rows(candidate: list[tuple[int]]) -> None:
    assert score(candidate, [[(1,), (2,)]], UNORDERED) == "wrong"


@pytest.mark.parametrize(
    ("candidate", "reference"),
    [(100.5, 100.0), (-99.5, -100.0), (Decimal("0.995"), Decimal("1"))],
)
def test_numeric_relative_tolerance_accepts_half_percent(candidate: object, reference: object) -> None:
    assert score([(candidate,)], [[(reference,)]], UNORDERED) == "correct"


@pytest.mark.parametrize(("candidate", "reference"), [(100.51, 100.0), (-99.49, -100.0)])
def test_numeric_relative_tolerance_rejects_more_than_half_percent(candidate: float, reference: float) -> None:
    assert score([(candidate,)], [[(reference,)]], UNORDERED) == "wrong"


@pytest.mark.parametrize(("candidate", "reference"), [(" north ", "north"), ("x\t", " x")])
def test_strings_ignore_surrounding_whitespace(candidate: str, reference: str) -> None:
    assert score([(candidate,)], [[(reference,)]], UNORDERED) == "correct"


@pytest.mark.parametrize(("candidate", "reference"), [("North", "north"), ("a b", "ab")])
def test_strings_preserve_case_and_internal_whitespace(candidate: str, reference: str) -> None:
    assert score([(candidate,)], [[(reference,)]], UNORDERED) == "wrong"


def test_column_names_are_absent_and_column_order_is_ignored() -> None:
    candidate = [(10, "A"), (20, "B")]
    reference = [("B", 20), ("A", 10)]
    assert score(candidate, [reference], UNORDERED) == "correct"


def test_extra_candidate_columns_are_ignored() -> None:
    candidate = [("unused", 1, "A"), ("unused", 2, "B")]
    reference = [("A", 1), ("B", 2)]
    assert score(candidate, [reference], UNORDERED) == "correct"


def test_every_reference_column_needs_a_distinct_candidate_column() -> None:
    assert score([(1,)], [[(1, 1)]], UNORDERED) == "wrong"


def test_unordered_question_ignores_row_order() -> None:
    assert score([(2,), (1,)], [[(1,), (2,)]], UNORDERED) == "correct"


def test_large_unordered_result_uses_dimension_values_to_match_rows() -> None:
    reference = [(f"item-{index}", index * 10.0) for index in range(2_000)]
    candidate = [(name, value * 1.004) for name, value in reversed(reference)]
    assert score(candidate, [reference], UNORDERED) == "correct"


def test_ordered_question_compares_row_order() -> None:
    assert score([(2,), (1,)], [[(1,), (2,)]], ORDERED) == "wrong"


def test_top_n_accepts_any_members_of_complete_boundary_tie_group() -> None:
    rules = {"ordered": True, "top_n": 3, "tie_columns": [1]}
    reference = [("A", 10), ("B", 9), ("C", 9), ("D", 9)]
    assert score([("A", 10), ("D", 9), ("B", 9)], [reference], rules) == "correct"
    assert score([("A", 10), ("C", 9), ("D", 9)], [reference], rules) == "correct"


def test_top_n_rejects_non_boundary_substitution() -> None:
    rules = {"ordered": True, "top_n": 2, "tie_columns": [1]}
    reference = [("A", 10), ("B", 9), ("C", 9)]
    assert score([("A", 10), ("D", 8)], [reference], rules) == "wrong"


def test_top_n_rejects_complete_boundary_group_with_diagnostic() -> None:
    rules = {"ordered": True, "top_n": 2, "tie_columns": [1]}
    reference = [("A", 10), ("B", 9), ("C", 9)]
    result = score_detailed([("A", 10), ("C", 9), ("B", 9)], [reference], rules)
    assert result.outcome == "wrong"
    assert result.reason == BOUNDARY_TIE_FULL_GROUP


@pytest.mark.parametrize(("candidate", "reference"), [(0.9967, 99.67), (99.67, 0.9967)])
def test_decimal_and_percentage_are_equivalent(candidate: float, reference: float) -> None:
    assert score([(candidate,)], [[(reference,)]], UNORDERED) == "correct"


@pytest.mark.parametrize(("candidate", "reference"), [(0.5, 60.0), (200.0, 1.0)])
def test_unrelated_scaled_numbers_are_not_equivalent(candidate: float, reference: float) -> None:
    assert score([(candidate,)], [[(reference,)]], UNORDERED) == "wrong"


def test_any_acceptable_reference_can_match() -> None:
    assert score([(2,)], [[(1,)], [(2,)]], UNORDERED) == "correct"


def test_all_acceptable_references_can_miss() -> None:
    assert score([(3,)], [[(1,)], [(2,)]], UNORDERED) == "wrong"


def test_empty_candidate_and_empty_reference_are_valid_results() -> None:
    assert score([], [[]], UNORDERED) == "correct"


def test_refusal_is_distinct_from_empty_rows() -> None:
    assert score("CANNOT_ANSWER", [[]], UNORDERED) == "refused"
    assert score("  CANNOT_ANSWER  ", [[(1,)]], UNORDERED) == "refused"


def test_execution_error_preserves_original_message() -> None:
    result = score_detailed(ExecError("Unknown table retail.X"), [[(1,)]], UNORDERED)
    assert result.outcome == "exec_error"
    assert result.reason == "Unknown table retail.X"


def test_wrong_and_correct_complete_the_four_outcomes() -> None:
    assert score([(1,)], [[(1,)]], UNORDERED) == "correct"
    assert score([(2,)], [[(1,)]], UNORDERED) == "wrong"


def test_top_n_reference_with_extra_rows_requires_tie_columns() -> None:
    with pytest.raises(ValueError, match="requires tie_columns"):
        score([("A", 10)], [[("A", 10), ("B", 9)]], {"ordered": True, "top_n": 1})


def test_top_n_reference_rejects_rows_below_boundary_tie() -> None:
    rules = {"ordered": True, "top_n": 2, "tie_columns": [1]}
    with pytest.raises(ValueError, match="below the complete boundary"):
        score([("A", 10), ("B", 9)], [[("A", 10), ("B", 9), ("C", 8)]], rules)


def test_numeric_tolerance_does_not_enlarge_boundary_ties() -> None:
    rules = {"ordered": True, "top_n": 2, "tie_columns": [1]}
    reference = [("A", 100), ("B", 99.6), ("C", 99.6)]
    assert score([("B", 99.6), ("C", 99.6)], [reference], rules) == "wrong"


def test_sensitivity_labels_only_does_not_change_outcome() -> None:
    result = score_detailed([("Holiday", 10)], [[("Yes", 10)]], UNORDERED)
    assert result.outcome == "wrong"
    assert result.sensitivity == "string_or_label_only"


def test_sensitivity_requires_joint_numeric_row_matching() -> None:
    result = score_detailed([("X", 1, 20), ("Y", 2, 10)], [[("A", 1, 10), ("B", 2, 20)]], UNORDERED)
    assert result.sensitivity == "numeric_mismatch"


def test_sensitivity_missing_numeric_column_is_not_formatting() -> None:
    assert score_detailed([("A", 10)], [[("A", 10, 20)]], UNORDERED).sensitivity == "numeric_mismatch"


def test_sensitivity_preserves_numeric_nulls() -> None:
    result = score_detailed([("X", None), ("Y", 2)], [[("A", None), ("B", 2)]], UNORDERED)
    assert result.sensitivity == "string_or_label_only"


def test_sensitivity_extra_rows_are_not_formatting() -> None:
    assert score_detailed([("X", 1), ("Y", 2)], [[("A", 1)]], UNORDERED).sensitivity != "string_or_label_only"


def test_sensitivity_respects_order_and_any_reference() -> None:
    assert score_detailed([("X", 2), ("Y", 1)], [[("A", 1), ("B", 2)]], ORDERED).sensitivity == "numeric_mismatch"
    assert score_detailed([("X", 2)], [[("A", 1)], [("B", 2)]], UNORDERED).sensitivity == "string_or_label_only"


def test_sensitivity_keeps_non_results_and_no_numeric_separate() -> None:
    assert score_detailed(ExecError("failure"), [[(1,)]], UNORDERED).sensitivity is None
    assert score_detailed("CANNOT_ANSWER", [[(1,)]], UNORDERED).sensitivity is None
    assert score_detailed([("X",)], [[("A",)]], UNORDERED).sensitivity == "no_numeric_reference"


def test_sensitivity_top_n_keeps_boundary_contract() -> None:
    rules = {"ordered": True, "top_n": 2, "tie_columns": [1]}
    refs = [[("A", 10), ("B", 9), ("C", 9)]]
    assert score_detailed([("X", 10), ("Y", 9)], refs, rules).sensitivity == "string_or_label_only"
    assert score_detailed(refs[0], refs, rules).sensitivity == "structure_mismatch"


@pytest.mark.parametrize(('kind','candidate','reference'), [('ratio',0.0008,0.0007),('percentage',0.08,0.07),('amount',0.009,0.0)])
def test_unit_absolute_floor_accepts_near_zero(kind, candidate, reference) -> None:
    rules = {**UNORDERED, 'value_kinds':[kind]}
    assert score([(candidate,)], [[(reference,)]], rules) == 'correct'
    assert score([(candidate,)], [[(reference,)]], {**rules,'use_absolute_tolerance':False}) == 'wrong'


@pytest.mark.parametrize(('kind','candidate'), [('ratio',0.0001001),('percentage',0.01001),('amount',0.01001),('other',0.00001)])
def test_unit_absolute_floor_rejects_outside_bound(kind, candidate) -> None:
    assert score([(candidate,)], [[(0.0,)]], {**UNORDERED,'value_kinds':[kind]}) == 'wrong'


def test_percentage_floor_normalizes_mixed_units() -> None:
    assert score([(0.0008,)], [[(0.07,)]], {**UNORDERED,'value_kinds':['percentage']}) == 'correct'
    assert score([(0.08,)], [[(0.0007,)]], {**UNORDERED,'value_kinds':['ratio']}) == 'correct'


def test_absolute_tolerance_does_not_merge_money_ties() -> None:
    rules = {'ordered':True,'top_n':1,'tie_columns':[1],'value_kinds':['other','amount']}
    assert score([('B',0.009)], [[('A',0.01),('B',0.009)]], rules) == 'correct'
    with pytest.raises(ValueError, match='below the complete boundary'):
        score([('B',0.0)], [[('A',0.01),('B',0.0)]], rules)


def test_integer_count_exactness_is_default() -> None:
    rules = {**UNORDERED,'value_kinds':['count'],'value_types':['UInt64']}
    assert score([(10040,)], [[(10000,)]], {**rules,'exact_counts':False}) == 'correct'
    assert score([(10040,)], [[(10000,)]], rules) == 'wrong'
    assert score([(10040,)], [[(10000,)]], {**rules,'exact_counts':True}) == 'wrong'
    assert score([(10000,)], [[(10000,)]], {**rules,'exact_counts':True}) == 'correct'


def test_unit_metadata_tracks_reference_columns_after_permutation() -> None:
    rules={**UNORDERED,'value_kinds':['amount','count'],'value_types':['Float64','UInt64']}
    assert score([(10000,0.009)], [[(0.0,10000)]], rules) == 'correct'
    assert score([(10040,0.009)], [[(0.0,10000)]], {**rules,'exact_counts':True}) == 'wrong'


@pytest.mark.parametrize('column_type', ['Int8', 'UInt64', 'Int128', 'Nullable(UInt256)', 'LowCardinality(Nullable(Int32))', 'int64'])
def test_count_guard_uses_reference_integer_return_type(column_type) -> None:
    rules = {**UNORDERED, 'value_kinds': ['count'], 'value_types': [column_type]}
    assert score([(10040,)], [[(10000,)]], rules) == 'wrong'
    assert score([(10000.0,)], [[(10000,)]], rules) == 'correct'
    assert score([(100,)], [[(10000,)]], rules) == 'wrong'
    assert score([(2**60+1,)], [[(2**60,)]], rules) == 'wrong'


@pytest.mark.parametrize('column_type', ['Float64', 'Nullable(Float64)', 'Decimal(18, 2)', 'Array(UInt64)', 'String'])
def test_noninteger_count_keeps_relative_tolerance_even_for_integral_values(column_type) -> None:
    rules = {**UNORDERED, 'value_kinds': ['count'], 'value_types': [column_type]}
    assert score([(10040,)], [[(10000,)]], rules) == 'correct'
    assert score([(10060,)], [[(10000,)]], rules) == 'wrong'
    assert score([(0.00001,)], [[(0,)]], rules) == 'wrong'


def test_missing_type_does_not_guess_integer_from_value() -> None:
    assert score([(10040,)], [[(10000,)]], {**UNORDERED, 'value_kinds': ['count']}) == 'correct'
    assert score([(10040,)], [[(10000,)]], {**UNORDERED, 'value_kinds': ['other'], 'value_types': ['UInt64']}) == 'correct'


def test_type_metadata_checked_and_projected_with_sensitivity() -> None:
    rules = {**UNORDERED, 'value_kinds': ['other', 'count'], 'value_types': ['String', 'UInt64']}
    assert score_detailed([(10040, 'X')], [[('A',10000)]], rules).sensitivity == 'numeric_mismatch'
    assert score_detailed([(10000, 'X')], [[('A',10000)]], rules).sensitivity == 'string_or_label_only'
    with pytest.raises(ValueError, match='reference column count'):
        score([('A',10000)], [[('A',10000)]], {**rules, 'value_types': ['String']})
    with pytest.raises(ValueError, match='value_types'):
        score([(1,)], [[(1,)]], {**UNORDERED, 'value_types': 'UInt64'})
