"""Offline provenance, input refusal, source discovery and paired reporting."""
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.questions import Question
from scripts import rescore_t23 as T


def question():
    return Question('SYNTHETIC', 'synthetic prompt', [[[2031, 20]]],
        {'required_columns': [0, 1], 'value_types': ['UInt16', 'UInt64'],
         'value_kinds': ['other', 'count'], 'ordered': False, 'top_n': None, 'tie_columns': []},
        meta={'low_discrimination': None})


def saved_source(tmp_path):
    q = question()
    raw = tmp_path / 'raw' / '20310101-T13-synthetic' / 'SQL-L1'
    raw.mkdir(parents=True)
    payload = {'columns': [{'name': 'year', 'type': 'String'}, {'name': 'count', 'type': 'UInt64'}],
               'rows': [['Year 2031', 20]], 'error': None}
    data = json.dumps(payload).encode()
    (raw / 'SYNTHETIC_r1_t0.exec.json').write_bytes(data)
    record = {'qid': q.qid, 'rep': 1, 'status': 'done', 'question_sha256': T.R.sha256(q.text),
              'turns': [{'turn': 0, 'exec': {'exec_raw_sha256': T.sha(data)}}]}
    source = T.Source(tmp_path / '20310101-T13-synthetic/SQL-L1.jsonl', 'repo', json.dumps(record).encode())
    columns = {q.qid: [[{'name': 'year', 'type': 'UInt16'}, {'name': 'count', 'type': 'UInt64'}]]}
    return q, raw, source, columns


def test_verified_same_input_is_scored_by_both_versions_without_raw_output(tmp_path):
    q, raw, source, columns = saved_source(tmp_path)
    rows, other = T.rescore_source(source, {q.qid: q}, columns, tmp_path / 'raw', 'new', 'frozen')
    assert other == {}
    assert rows[0]['final']['v2']['outcome'] == 'wrong'
    assert rows[0]['final']['v3']['outcome'] == 'correct'
    serialized = json.dumps(rows)
    assert 'Year 2031' not in serialized and q.text not in serialized and 'query' not in serialized
    assert rows[0]['source_log_sha256'] == T.sha(source.data)
    assert rows[0]['final']['v3']['transformations'][0]['rule'] == 'P1'


def test_changed_question_and_corrupt_execution_are_refused(tmp_path):
    q, raw, source, columns = saved_source(tmp_path)
    file = raw / 'SYNTHETIC_r1_t0.exec.json'
    file.write_bytes(file.read_bytes() + b' ')
    with pytest.raises(ValueError, match='checksum'):
        T.rescore_source(source, {q.qid: q}, columns, tmp_path / 'raw', 'new', 'frozen')
    q2 = Question(q.qid, 'changed', q.refs, q.rules, meta=q.meta)
    with pytest.raises(ValueError, match='question text'):
        T.rescore_source(source, {q.qid: q2}, columns, tmp_path / 'raw', 'new', 'frozen')


def test_missing_execution_and_duplicate_done_are_not_silently_dropped(tmp_path):
    q, raw, source, columns = saved_source(tmp_path)
    duplicate = T.Source(source.path, source.origin, source.data + b'\n' + source.data)
    with pytest.raises(ValueError, match='duplicate'):
        T.rescore_source(duplicate, {q.qid: q}, columns, tmp_path / 'raw', 'new', 'frozen')
    (raw / 'SYNTHETIC_r1_t0.exec.json').unlink()
    with pytest.raises(FileNotFoundError):
        T.rescore_source(source, {q.qid: q}, columns, tmp_path / 'raw', 'new', 'frozen')


def test_discovery_includes_t14_without_rescoring_existing_rescores(tmp_path):
    repo, cards = tmp_path / 'repo', tmp_path / 'cards'
    for directory in [repo / 'runs/20310101-T13-synthetic', repo / 'runs/20310101-T13-synthetic-rescore-01',
                      cards / 'T14/runs/20310101-T14-synthetic']:
        directory.mkdir(parents=True)
        (directory / 'SQL-L1.jsonl').write_text('{}\n')
    sources = T.discover(repo, cards)
    assert len(sources) == 2
    assert {s.origin for s in sources} == {'repo', '$SEMDEBT_CARDS_DIR/T14'}


def test_divergent_log_copies_fail(tmp_path):
    repo, cards = tmp_path / 'repo', tmp_path / 'cards'
    for root, text in [(repo, 'one\n'), (cards / 'T14', 'two\n')]:
        directory = root / 'runs/20310101-T14-synthetic'
        directory.mkdir(parents=True)
        (directory / 'SQL-L1.jsonl').write_text(text)
    with pytest.raises(ValueError, match='divergent'):
        T.discover(repo, cards)


def test_statistics_keeps_execution_failures_in_denominator_and_no_verdict_apart():
    rows = [{'final': {'v2': {'outcome': a}, 'v3': {'outcome': b}}} for a, b in
            [('wrong', 'correct'), ('exec_error', 'exec_error'), ('refused', 'refused'), ('unscored', 'unscored')]]
    stats = T.statistics(rows)
    assert stats == {'attempts': 4, 'denominator': 3, 'v2_correct': 0, 'v3_correct': 1,
                     'changed': 1, 'no_verdict': 1}


def test_partial_cells_are_not_ranked_against_complete_cells():
    q = question()
    def row(rep, outcome):
        return {'qid': q.qid, 'rep': rep, 'final': {v: {'outcome': outcome} for v in ('v2', 'v3')}}
    changes, comparable = T.ordering_changes({'full': [row(k, 'correct') for k in (1, 2, 3)],
                                             'partial': [row(1, 'wrong')]}, {q.qid: q})
    assert changes == [] and comparable == ['full']
