import json
import zipfile
import pytest

from scripts.t33_publication_artifacts import (
    LOCAL_PATH, U2_RUN, archive, completed_u2, decoded_text, encoded,
    public_attempt, raw_hashes, referenced_members, sha,
)


def test_public_export_uses_allowlist_and_caps_rows():
    score = dict(rep=2, source_run='selected-run', content_correct=1, a=0, rules=[])
    record = dict(turns=[dict(query='SELECT 1', assumption='无', reasoning_content='PRIVATE')],
                  usage={'completion_tokens': 12}, response='PRIVATE', system='PRIVATE')
    execution = dict(columns=[{'name': 'n'}], rows=[[i] for i in range(50)],
                     detail='PRIVATE', error='PRIVATE')
    result = public_attempt(score, record, execution)
    assert len(result['rows']) == 20 and result['total_rows'] == 50
    assert result['content_correct'] == 1 and result['delivery_correct'] == 0
    assert 'PRIVATE' not in json.dumps(result)


def test_raw_hashes_select_physical_references_only():
    record = dict(turns=[dict(raw_sha256='api', exec={'exec_raw_sha256': 'final'})],
                  steps=[dict(raw_sha256='tool-api', tool_calls=[dict(
                      exec={'exec_raw_sha256': 'tool-result'}, tool_message_sha256='not-a-file')])],
                  question_sha256='not-a-file')
    assert raw_hashes(record) == {'api', 'final', 'tool-api', 'tool-result'}


def test_zip_is_deterministic_and_preserves_selected_bytes(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(b'{"reasoning_content":"preserve raw"}')
    first, second = tmp_path / 'a.zip', tmp_path / 'b.zip'
    inventory = archive(first, {'runs-raw/run/cell/a.json': source, 'z.txt': b'z'})
    archive(second, {'z.txt': b'z', 'runs-raw/run/cell/a.json': source})
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as bundle:
        assert bundle.namelist() == ['runs-raw/run/cell/a.json', 'z.txt']
        assert bundle.read(bundle.namelist()[0]) == source.read_bytes()
    assert inventory[0]['category'] == 'API 回包（可能含思考内容）'


def test_embedded_data_cannot_close_script():
    value = {'query': '</script><img src=x onerror=alert(1)> &'}
    result = encoded(value)
    assert '<' not in result and '&' not in result
    assert json.loads(result) == value


def test_local_path_scan_does_not_treat_json_newlines_as_drive_paths():
    assert not LOCAL_PATH.search(rb'columns:\nrows:\n')
    assert LOCAL_PATH.search(rb'C:\\example\\file.txt')
    assert LOCAL_PATH.search(b'/' + b'Users' + b'/example/file.txt')
    assert not LOCAL_PATH.search(decoded_text(json.loads(r'{"text":"p:\nSELECT 1"}')).encode())


def test_completed_u2_requires_exact_coverage_and_ignores_failed_records():
    records = [dict(run_id=U2_RUN, cell='SQL-L0', qid='Q01', rep=n,
                    status='done', turns=[{'raw_sha256': str(n)}]) for n in (1, 2, 3)]
    failed = dict(records[0], status='api_error', turns=[])
    assert completed_u2(records + [failed], 'SQL-L0', ['Q01']) == records
    with pytest.raises(ValueError, match='incomplete or duplicate'):
        completed_u2(records[:-1], 'SQL-L0', ['Q01'])
    with pytest.raises(ValueError, match='incomplete or duplicate'):
        completed_u2(records + [records[0]], 'SQL-L0', ['Q01'])
    with pytest.raises(ValueError, match='invalid U2 source'):
        completed_u2([dict(r, run_id='other-run') for r in records], 'SQL-L0', ['Q01'])


def test_referenced_members_excludes_orphans_and_rejects_missing_results(tmp_path):
    directory = tmp_path / 'runs-raw' / U2_RUN / 'SQL-L0'
    directory.mkdir(parents=True)
    api, execution = b'{"reasoning_content":"preserved"}', b'{"rows":[[1]]}'
    (directory / 'Q01_r1_t0.json').write_bytes(api)
    (directory / 'Q01_r1_t0.exec.json').write_bytes(execution)
    (directory / 'Q01_r1_t0_obsolete.json').write_bytes(b'{}')
    record = dict(cell='SQL-L0', qid='Q01', rep=1, turns=[
        dict(raw_sha256=sha(api), exec={'exec_raw_sha256': sha(execution)})])
    selected = referenced_members(tmp_path, U2_RUN, record)
    assert len(selected) == 2 and not any('obsolete' in name for name in selected)
    (directory / 'Q01_r1_t0.exec.json').unlink()
    with pytest.raises(ValueError, match='missing referenced raw artifact'):
        referenced_members(tmp_path, U2_RUN, record)
