"""Read-only acceptance of T05b data; never imports the independent checker."""
import json
import os
from pathlib import Path
from time import perf_counter

import pytest

from harness import scorer_v2
from scripts.validate_scorer_v2 import deadline, decode_candidate, decode_value


def _cases():
    root = os.environ.get('SEMDEBT_DATA_DIR')
    if not root:
        return [pytest.param(None, marks=pytest.mark.skip(reason='SEMDEBT_DATA_DIR is required for shared acceptance'))]
    path = Path(root) / 'scorer-corpus' / 't05b-cases.jsonl'
    with path.open() as source:
        records = [json.loads(line) for line in source if line.strip()]
    return [pytest.param(record, id=record['case_id']) for record in records]


@pytest.mark.parametrize('case', _cases())
def test_independent_shared_case(case):
    candidate = decode_candidate(case['candidate'])
    refs = decode_value(case['refs'])
    rows = max([len(candidate) if isinstance(candidate, list) else 0] + [len(ref) for ref in refs])
    limit = 2 if rows <= 10000 else 30
    expected = case['expected']
    start = perf_counter()
    if expected['outcome'] == 'error':
        with deadline(limit), pytest.raises((ValueError, TypeError)):
            scorer_v2.score_detailed(candidate, refs, {}, reference_rules=case['rules'])
        return
    with deadline(limit):
        result = scorer_v2.score_detailed(candidate, refs, {}, reference_rules=case['rules'])
    assert perf_counter() - start <= limit
    if result.outcome == 'unscored' or expected['outcome'] == 'unscored':
        # Spec 12.7: screening-dependent caps are reported separately, not disagreements.
        if result.outcome == 'unscored':
            assert result.reason == 'mapping_cap'
        return
    assert result.outcome == expected['outcome'], result
    if expected.get('reason') is not None:
        assert result.reason == expected['reason'], result
