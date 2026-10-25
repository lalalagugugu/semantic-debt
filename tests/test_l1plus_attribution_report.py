"""Completeness, independent labels and single-bin counts for T22b attribution."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import l1plus_attribution_report as S  # noqa: E402


def records():
    items = [{'qid': 'Q01', 'rep': 1}, {'qid': 'Q01', 'rep': 2}]
    flash = [{**i, 'status': 'done', 'labels': {'category': S.A.CATEGORIES[0], 'data_quality_related': True}} for i in items]
    codex = [{**i, 'category': S.A.SUSPICIOUS, 'data_quality_related': 'false'} for i in items]
    return items, flash, codex


def test_single_bin_excluded_from_five_class_denominator():
    rows = S.paired_rows(*records())
    assert S.counts(rows, 'flash')['five_class_total'] == 2
    c = S.counts(rows, 'codex')
    assert c['five_class_total'] == 0 and c['single_total'] == 2
    assert c['data_quality_related'] == 0
    assert S.counts(rows, 'flash')['data_quality_related'] == 2


@pytest.mark.parametrize('change', ('missing', 'duplicate', 'unfinished', 'bad_flag', 'new_category'))
def test_invalid_review_cannot_appear_complete(change):
    items, flash, codex = records()
    if change == 'missing':
        flash.pop()
    elif change == 'duplicate':
        flash.append(flash[0])
    elif change == 'unfinished':
        flash[0]['status'] = 'unparsed'
    elif change == 'bad_flag':
        codex[0]['data_quality_related'] = '是'
    else:
        codex[0]['category'] = 'new category'
    with pytest.raises(ValueError):
        S.paired_rows(items, flash, codex)


def test_agreement_does_not_merge_disagreements():
    rows = S.paired_rows(*records())
    assert all(r['flash']['category'] != r['codex']['category'] for r in rows)
    assert S.kappa(['a','b','a','b'], ['a','b','b','a']) == 0
    assert S.kappa(['a','a'], ['a','a']) == 1
