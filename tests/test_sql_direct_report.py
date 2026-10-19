"""T13 report: execution-error categories (scripts/sql_direct_report.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from sql_direct_report import error_group, no_verdict  # noqa: E402

SYNTAX = ("Code: 62. DB::Exception: Unrecognized token: Syntax error: failed at position 19 ({ch}) "
          "(line 1, col 31): {word}\nFROM retail.DimProduct. . (SYNTAX_ERROR)")


def _e(msg: str, cls: str = "engine_error") -> dict:
    return {"status": "error", "error_class": cls, "error": msg}


@pytest.mark.parametrize("query,where", [
    ("SELECT count(DISTINCT ProductKey) AS 产品种类数\nFROM retail.DimProduct", "AS"),
    ("WITH 产品种类数 AS (SELECT 1) SELECT * FROM 产品种类数", "other"),     # a CTE name, not an AS alias
])
def test_unquoted_chinese_identifier_is_chinese_alias_syntax_error(query, where):
    assert error_group(_e(SYNTAX.format(ch="产", word="产品种类数")), query) == ("中文别名语法错误", where)


def test_other_syntax_errors_and_codes():
    assert error_group(_e(SYNTAX.format(ch="(", word="(x")), "SELECT (x") == ("其他语法错误", None)
    # the logged message may be cut before the code's name; the leading code decides
    assert error_group(_e("Code: 47. DB::Exception: Unknown expression identifier `StoreKey`. In scope WITH"), "") \
        == ("标识符与作用域", None)
    assert error_group(_e("Code: 184. DB::Exception: aggregate inside aggregate (ILLEGAL_AGGREGATION)"), "") == ("聚合用法", None)
    assert error_group(_e("Code: 999. DB::Exception: something new"), "") == ("其他（Code 999）", None)
    assert error_group(_e("no query code block in the response", "no_query"), None) == ("no_query", None)


def test_no_verdict():
    assert no_verdict({"final": {"outcome": "pending", "pending": "score_timeout"}})
    assert no_verdict({"final": {"outcome": "unscored"}})
    assert not no_verdict({"final": {"outcome": "pending", "pending": "judge"}})
    assert not no_verdict({"final": {"outcome": "wrong"}})
