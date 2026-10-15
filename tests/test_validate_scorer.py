import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.validate_scorer import complete_boundary, final_order_clause, question_rules, reference_digest, verify_reference_digests, reviewed_categories


def test_outer_order_excludes_window_subquery_and_comments() -> None:
    assert final_order_clause("SELECT row_number() OVER (ORDER BY x) FROM t") is None
    assert final_order_clause("SELECT * FROM (SELECT x FROM t ORDER BY x) -- ORDER BY x") is None
    assert final_order_clause("SELECT 'ORDER BY x' FROM t ORDER BY y DESC LIMIT 2") == "y DESC"


def test_ordered_metadata_cannot_use_unsorted_reference() -> None:
    assert not question_rules(22, "SELECT row_number() OVER (ORDER BY x) FROM t")["ordered"]
    assert not question_rules(45, "SELECT x FROM t")["ordered"]
    assert question_rules(45, "SELECT x FROM t ORDER BY x DESC")["ordered"]
    assert not question_rules(1, "SELECT x FROM t ORDER BY x")["ordered"]


def test_exact_projected_boundary_is_stable_under_physical_row_order() -> None:
    rows = [["B", 9.6], ["C", 9.6], ["A", 10], ["D", 9.59]]
    rules = {"top_n": 2, "tie_columns": [1]}
    assert complete_boundary(rows, rules, True) == [["A", 10], ["B", 9.6], ["C", 9.6]]
    assert complete_boundary(rows[::-1], rules, True) == complete_boundary(rows, rules, True)
    assert complete_boundary(rows, rules, False) == [["D", 9.59], ["B", 9.6], ["C", 9.6]]


def test_changed_reference_members_are_rejected() -> None:
    first = reference_digest([["A", 10], ["B", 9]])
    changed = reference_digest([["A", 10], ["C", 9]])
    assert first != changed
    with pytest.raises(RuntimeError, match="not reproducible"):
        verify_reference_digests([first, changed, first], 25)
    verify_reference_digests([first, first, first], 25)


def test_reviewed_category_ledger_applies_ruling() -> None:
    ledger = reviewed_categories()
    assert len(ledger) == 68
    assert ledger[("O-S", 90)][0] == "舍入/相对误差"
    assert ledger[("S-R", 88)][0] == "行序与验证流程"


def test_global_unit_rules_and_cross_engine_tie_quantization() -> None:
    from decimal import Decimal
    from harness.value_units import infer_value_kind, quantize_tie
    assert infer_value_kind('gross_margin_pct') == 'percentage'
    assert infer_value_kind('promo_to_fullprice_ratio') == 'ratio'
    assert infer_value_kind('total_sales', 'UInt64') == 'count'
    assert infer_value_kind('sum(SalesAmount)', 'Float64') == 'amount'
    assert infer_value_kind('month','UInt8') == 'other'
    assert quantize_tie(Decimal('10.23000000001'),'amount') == quantize_tie(Decimal('10.22999999999'),'amount')
    assert quantize_tie(Decimal('0.123456000001'),'ratio') == quantize_tie(Decimal('12.3455999999'),'percentage')
    assert quantize_tie(Decimal('1.005'),'amount') == Decimal('1.00')
    assert quantize_tie(Decimal('1.015'),'amount') == Decimal('1.02')


def test_count_provenance_does_not_capture_ratio_denominators() -> None:
    from scripts.validate_scorer import reference_value_kinds
    columns = [{'name':'holiday_days','type':'UInt64'}, {'name':'aov','type':'Float64'}, {'name':'retention_pct','type':'Float64'}]
    sql = 'SELECT count() AS holiday_days, sum(amount)/count() AS aov, countIf(x)*100.0/count() AS retention_pct FROM t'
    assert reference_value_kinds(sql,columns) == ['count','other','percentage']
