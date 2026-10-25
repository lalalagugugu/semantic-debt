"""T22b offline completeness and stability definitions."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.l1plus_report import metrics, validate


def test_stability_counts_noncorrect_outcomes_and_three_attempts():
    rows = []
    for qid, outcomes in [('A', ['correct']*3), ('B', ['wrong', 'exec_error', 'refused']),
                          ('C', ['wrong', 'correct', 'correct'])]:
        rows.extend({'qid': qid, 'rep': i, 'status': 'done', 'final': {'outcome': o}}
                    for i, o in enumerate(outcomes, 1))
    result = metrics(rows, {'A', 'B', 'C'})
    assert result['correct'] == 5 and result['attempts'] == 9
    assert result['accuracy'] == 5/9
    assert (result['all_correct'], result['all_wrong'], result['mixed']) == (1, 1, 1)
    assert metrics(rows, {'A'})['correct'] == 3


@pytest.mark.parametrize('bad', ['duplicate', 'missing', 'unscored', 'pending', 'not_done'])
def test_incomplete_inputs_are_not_silently_reported(bad):
    rows = [{'qid': 'A', 'rep': i, 'status': 'done', 'final': {'outcome': 'correct'}} for i in (1, 2, 3)]
    if bad == 'duplicate':
        rows.append(copy.deepcopy(rows[0]))
    elif bad == 'missing':
        rows.pop()
    elif bad == 'unscored':
        rows[0]['final']['outcome'] = 'unscored'
    elif bad == 'pending':
        rows[0]['final']['pending'] = 'score_timeout'
    else:
        rows[0]['status'] = 'api_error'
    with pytest.raises(ValueError):
        validate(rows, {'A'})


def test_receipt_cost_checks_raw_hash_and_accounting(tmp_path):
    import hashlib
    import json
    from scripts.l1plus_report import receipt_cost

    payload = json.dumps({'usage': {'prompt_cache_hit_tokens': 1000, 'prompt_cache_miss_tokens': 1000,
                                   'completion_tokens': 1000}}).encode()
    path = tmp_path/'A_r1_t0.json'
    path.write_bytes(payload)
    row = {'qid': 'A', 'rep': 1, 'peak': False, 'cost_cny': .00502,
           'turns': [{'turn': 0, 'raw_sha256': hashlib.sha256(payload).hexdigest()}]}
    assert receipt_cost([row], tmp_path) == pytest.approx(.00502)
    row['cost_cny'] = .1
    with pytest.raises(ValueError, match='Cost mismatch'):
        receipt_cost([row], tmp_path)
    row['cost_cny'] = .00502
    path.write_bytes(payload+b' ')
    with pytest.raises(ValueError, match='hash mismatch'):
        receipt_cost([row], tmp_path)
