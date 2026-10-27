"""Synthetic guards for scripts/review_v4_flips_claude.py (no real questions or results)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "review_v4", Path(__file__).resolve().parents[1] / "scripts" / "review_v4_flips_claude.py")
rv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rv)


def cols(*names):
    return [{"name": n, "type": "String"} for n in names]


MONTH_REF = (cols("month", "sales"), [[1, 100.0], [2, 200.0]],
             {"ordered": False, "required_columns": [0, 1], "value_kinds": ["other", "amount"]})


def run(acols, arows, ref, hits, q="2009 年各月销售额"):
    rcols, rrows, rules = ref
    return rv.check_against(acols, arows, rcols, rrows, rules, set(hits), q, rv.question_years(q))


def test_r1_month_name_and_single_year():
    assert run(cols("m", "s"), [["January", 100.0], ["February", 200.0]], MONTH_REF, ["R1"])["ok"]
    assert run(cols("m", "s"), [["2009-01", 100.0], ["2009-02", 200.0]], MONTH_REF, ["R1"])["ok"]


def test_r1_year_not_inferred_from_multi_year_question():
    res = run(cols("m", "s"), [["2009-01", 100.0], ["2009-02", 200.0]], MONTH_REF, ["R1"], q="2008 和 2009 年各月")
    assert not res["ok"]


def test_period_needs_r1():
    assert not run(cols("m", "s"), [["January", 100.0], ["February", 200.0]], MONTH_REF, [])["ok"]


def test_value_outside_tolerance_fails():
    assert not run(cols("m", "s"), [["January", 102.0], ["February", 200.0]], MONTH_REF, ["R1"])["ok"]


def test_numeric_null_is_not_zero():
    ref = (cols("g", "v"), [["a", None], ["b", 5.0]],
           {"ordered": False, "required_columns": [0, 1], "value_kinds": ["other", "amount"]})
    assert not run(cols("g", "v"), [["a", 0.0], ["b", 5.0]], ref, ["R1"])["ok"]
    assert run(cols("g", "v"), [["a", None], ["b", 5.0]], ref, [])["ok"]


def test_r7_guard_blocks_sort_questions():
    ref = (cols("name", "v"), [["x", 3.0], ["y", 1.0]],
           {"ordered": True, "order_by": [{"column": 1, "descending": True}],
            "required_columns": [0, 1], "value_kinds": ["other", "amount"]})
    swapped = [["y", 1.0], ["x", 3.0]]
    assert run(cols("n", "v"), swapped, ref, ["R7"], q="哪些门店销售下降")["ok"]
    assert not run(cols("n", "v"), swapped, ref, ["R7"], q="按销售额从高到低列出门店")["ok"]
    assert not run(cols("n", "v"), swapped, ref, [], q="哪些门店销售下降")["ok"]


def test_r3_code_fallback_only_for_placeholder():
    ref = (cols("FirstName", "LastName", "v", "CustomerKey"),
           [["Not Provided", "Not Provided", 9.0, 7], ["Ann", "Lee", 5.0, 8]],
           {"ordered": False, "required_columns": [0, 1, 3], "identifier_columns": [3],
            "value_kinds": ["other", "other", "amount", "other"]})
    good = [[7, "7", 9.0], [8, "Ann Lee", 5.0]]
    bad = [[7, "7", 9.0], [8, "8", 5.0]]
    assert run(cols("k", "name", "v"), good, ref, ["R3"])["ok"]
    assert not run(cols("k", "name", "v"), bad, ref, ["R3"])["ok"]


def test_r6_needs_decrease_header():
    ref = (cols("change",), [[-40.0]], {"ordered": False, "required_columns": [0], "value_kinds": ["amount"]})
    assert run(cols("减少额"), [[40.0]], ref, ["R6"])["ok"]
    assert not run(cols("变化额"), [[40.0]], ref, ["R6"])["ok"]
