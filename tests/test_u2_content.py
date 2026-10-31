"""U2 offline review boundaries; synthetic inputs only."""
import hashlib
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.t29_u2_content import blinded, final_labels, historical_baseline, lock_verdicts, apply_amendments


def test_review_view_excludes_arm_confidence_and_source_identity():
    material=dict(qid='Q_SYNTH',question='synthetic',context_key='context-digest',query='SELECT 1',
                  answer={'rows':[[1]]},refs=[],cell='hidden-arm',rep=3,confidence=99,
                  assumption='hidden',source_path='hidden-source',system='hidden penalty')
    view=blinded(material,'U0001')
    assert set(view)=={'anon_id','qid','question','context_key','query','answer','refs'}
    assert 'hidden' not in json.dumps(view)


def test_missing_unresolved_or_stale_judgments_block_unblinding():
    material=dict(anon_id='U0001',qid='Q_SYNTH',question='synthetic',context_key='digest',
                  query='SELECT 1',answer={'rows':[[1]]},refs=[])
    key=dict(anon_id='U0001',cell='hidden-arm',method='manual',correct=False)
    digest=hashlib.sha256(json.dumps(material,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    with pytest.raises(ValueError,match='cover every'):
        final_labels([key],{},[material])
    with pytest.raises(ValueError,match='unresolved'):
        final_labels([key],{'U0001':dict(material_sha256=digest,label='待裁决',category='边界')},[material])
    with pytest.raises(ValueError,match='stale'):
        final_labels([key],{'U0001':dict(material_sha256='wrong',label='内容正确',category='等价')},[material])
    result=final_labels([key],{'U0001':dict(material_sha256=digest,label='内容正确',category='等价')},[material])
    assert result[0]['correct'] and result[0]['cell']=='hidden-arm'


def test_unknown_historical_labels_cannot_be_coerced_to_wrong():
    rows=[dict(qid='synthetic',rep=rep,content_correct=1) for rep in (1,2,3)]
    assert historical_baseline(rows,{'synthetic'})=={'synthetic':[True]*3}
    rows[0]['content_correct']=None
    with pytest.raises(ValueError,match='final content labels'):
        historical_baseline(rows,{'synthetic'})
    with pytest.raises(ValueError,match='duplicated'):
        historical_baseline(rows+rows[1:],{'synthetic'})


def test_locked_verdicts_cannot_be_replaced(tmp_path):
    path=tmp_path/'lock.json'
    lock_verdicts(path,{'digest':'first'})
    lock_verdicts(path,{'digest':'first'})
    with pytest.raises(ValueError,match='preserve'):
        lock_verdicts(path,{'digest':'changed'})
    assert json.loads(path.read_text())=={'digest':'first'}


def test_user_amendment_changes_only_explicit_identity_and_preserves_original():
    rows=[dict(anon_id='A',qid='synthetic',cell='unit',rep=1,correct=True,category='old'),
          dict(anon_id='B',qid='synthetic',cell='unit',rep=2,correct=True,category='missing_without_null')]
    patch=dict(anon_id='A',qid='synthetic',cell='unit',rep=1,old_correct=True,
               correct=False,category='direct_null',decision='user superseding ruling')
    result=apply_amendments(rows,[patch])
    assert not result[0]['correct'] and result[1]==rows[1]
    assert rows[0]['correct']
    with pytest.raises(ValueError,match='original verdict'):
        apply_amendments(rows,[dict(patch,rep=3)])
    with pytest.raises(ValueError,match='duplicate adjudication'):
        apply_amendments(rows,[patch,patch])
