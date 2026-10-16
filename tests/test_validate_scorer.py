import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.validate_scorer import complete_boundary, final_order_clause, question_rules, reference_digest, reset_session, verify_reference_digests, reviewed_categories


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


def test_boundary_hash_versions_detect_policy_changes(tmp_path: Path, monkeypatch) -> None:
    from scripts import validate_scorer

    (tmp_path / "harness").mkdir()
    policy = tmp_path / "harness/value_units.py"
    policy.write_text("first policy")
    monkeypatch.setattr(validate_scorer, "REPO", tmp_path)
    first = validate_scorer.boundary_hash_versions()
    policy.write_text("second policy")
    second = validate_scorer.boundary_hash_versions()
    assert first["unit_policy_sha256"] != second["unit_policy_sha256"]
    assert first["boundary_policy_sha256"] == second["boundary_policy_sha256"]
    assert first["serialization_version"] == "json-compact-utf8-v1"


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
    assert infer_value_kind('total_sales', 'int64') == 'count'
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


def test_count_transition_guard_stops_unexpected_flips() -> None:
    from scripts.validate_scorer import verify_count_transition
    semantic = 'claude_claude_sonnet_4_6_semantic'
    verify_count_transition(semantic, 83, 'correct', 'wrong')
    verify_count_transition(semantic, 24, 'correct', 'correct')
    for qid, before, after in [(24,'correct','wrong'), (83,'wrong','correct'), (83,'exec_error','wrong')]:
        with pytest.raises(RuntimeError, match='unexpected flip'):
            verify_count_transition(semantic, qid, before, after)


def test_reference_type_coverage_includes_numeric_other_and_guard_exemptions() -> None:
    from harness.value_units import is_integer_type, is_numeric_type
    from scripts.validate_scorer import reference_column_report
    assert is_integer_type('Nullable(UInt64)')
    assert not is_integer_type('Array(UInt64)')
    for value in ['Float64', 'Nullable(Decimal(18, 2))', 'Decimal128(2)', 'Int64']:
        assert is_numeric_type(value)
    for value in ['Date', 'String', 'Array(Int64)']:
        assert not is_numeric_type(value)
    cols = [
        {'question_id':1, 'position':1, 'name':'customers','type':'Float64','kind':'count'},
        {'question_id':1, 'position':2, 'name':'x','type':'Nullable(Float64)','kind':'other'},
        {'question_id':1, 'position':3, 'name':'label','type':'String','kind':'other'},
    ]
    report = '\n'.join(reference_column_report(cols))
    assert '**1列**；占2个数值列的**50.00%**' in report
    assert '| Q01 | 1 | `customers` | `Float64` |' in report


def test_reset_session_discards_failed_session_and_restores_settings(tmp_path: Path) -> None:
    class FakeSession:
        def __init__(self, path: str) -> None:
            self.path = path
            self.queries = []
            self.closed = False

        def query(self, sql: str) -> None:
            self.queries.append(sql)

        def close(self) -> None:
            self.closed = True

    class FakeSessionModule:
        opened = []

        @classmethod
        def Session(cls, path: str) -> FakeSession:
            created = FakeSession(path)
            cls.opened.append(created)
            return created

    failed = FakeSession(str(tmp_path))
    clean = reset_session(failed, FakeSessionModule, tmp_path)

    assert failed.closed
    assert clean is FakeSessionModule.opened[0]
    assert clean.path == str(tmp_path)
    assert clean.queries == ["SET max_execution_time = 30", "SET max_threads = 1"]
    assert not clean.closed
