"""Statistical and result-comparison contracts for the T28 offline report."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reports.midterm.v3_data import auc, same_rows, token_statistics


def test_auc_wrong_is_positive_and_ties_receive_half_credit():
    assert auc([(1, False), (2, True)]) == 1
    assert auc([(2, False), (1, True)]) == 0
    assert auc([(2, False), (2, True)]) == .5
    assert auc([(1, False)]) is None


def test_result_comparison_ignores_order_but_preserves_full_joint_rows():
    assert same_rows([[1, 'a'], [2, 'b']], [['b', 2.0], ['a', 1]])
    assert not same_rows([[1, 'a'], [2, 'b']], [[1, 'b'], [2, 'a']])
    assert not same_rows([[1], [1], [2]], [[1], [2], [2]])
    assert not same_rows([[1]], [['1']])
    assert not same_rows([[1, 2]], [[1]])
    # Identical marginal distributions are insufficient: tuples must match.
    assert not same_rows([[0, 0], [1, 1]], [[0, 1], [1, 0]])


def test_within_question_signal_is_not_confounded_by_question_difficulty():
    rows = {}
    for qid, scores, outcomes in [('Q01', [1, 2, 3], [False, True, True]),
                                  ('Q02', [100, 200, 300], [False, False, False])]:
        for rep, (score, correct) in enumerate(zip(scores, outcomes), 1):
            rows[qid, rep] = {'turns': [{'usage': {'reasoning_tokens': score}}],
                             'final': {'outcome': 'correct' if correct else 'wrong'}}
    result = token_statistics(rows, {'Q01', 'Q02'}, samples=100)
    assert result['auc'] == .75
    assert result['mixed'] == 1
    assert result['within_auc'] == 0
    assert result['longest_wrong'] == .5
    assert result['shortest_wrong'] == 1
    assert result['valid'] < result['draws']
