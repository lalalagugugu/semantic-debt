import json
import zipfile

from scripts.t33_publication_artifacts import LOCAL_PATH, archive, decoded_text, encoded, public_attempt, raw_hashes


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
