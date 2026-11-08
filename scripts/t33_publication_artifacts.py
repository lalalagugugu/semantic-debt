"""Offline publication candidates. No model calls or query execution.

uv run --offline python scripts/t33_publication_artifacts.py
Inputs: SEMDEBT_DATA_DIR and SEMDEBT_EVAL_DIR; outputs remain outside git.
"""
from __future__ import annotations

import csv
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import sys
import re
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.rescore_t23 import frozen_bank

RUN = '20261031-T31-v5-rulings-01'
U2_RUN = '20261031-T29-u2-v3-01'
U2_CELLS = ('SQL-L0', 'SQL-L1', 'SQL-L0-u2', 'SQL-L1-u2', 'SQL-L0-u2p', 'SQL-L1-u2p')
T34_RUN = '20261104-T34-ontology-full-01'
T34_FINAL = '20261107-T34-final-01'
T34_AUDIT = T34_RUN + '-content-01'
T34_CELLS = ('SQL-L1', 'SQL-L1-onto', 'SQL-L1plus', 'SQL-L3a-full')
T34_REVIEW_SHA = '1634d223b90257bb7843a24cd879e000b20a0f1a98b1acba0de0e9803e8c96a9'
T34_NOTE = '本体对照：新版本模型的同一批次（20261104-T34-ontology-full-01）；仅比较本批次四个单元，和旧版主表不直接比较。'
MISSING = '未运行（T4 只跑留出题）'
LOCAL_PATH = re.compile(rb'(?:/(?:Users|home|private|tmp)/[^\s"<>]+|(?<![A-Za-z0-9_])[A-Za-z]:\\[^\s"<>]+)')
SOURCE_RUNS = {
    '20261018-T13-sql-direct-01', '20261019-C13-ladder-02',
    '20261019-T13-l15s-v14-01', '20261019-T15-explorer-01',
    '20261019-T16-full-v14-json-01', '20261019-T16-full-v14-sql-new-01',
    '20261020-T15-explorer-l2e-02', '20261020-T15-explorer-l2e-03',
    '20261025-T14-tuned-01', '20261025-T22b-l1plus-l3a-03',
    '20261025-T30-combo-01',
}
PRIVATE_FILES = (
    'v7-eval-20261030/report.md',
    'v7-eval-20261030/evidence.json',
    'v7-eval-20261030/discoverability-review.md',
    'v7-eval-20261030/SQL-L0-context.txt',
    'v7-eval-20261030/SQL-L1-context.txt',
    'v7-eval-20261030/SQL-L1c-context.txt',
    'v7-eval-20261030/snapshot/semantic/source.yaml',
    't31-v7-census-20261030/claude-review/claude-labels-194.csv',
    't31-v7-census-20261030/frozen-inputs/semantic-v1.6-l1plus/SQL-L3a-system.txt',
    f't31-v7-census-20261030/snapshots/{RUN}/codex-decisions.json',
    f't31-v7-census-20261030/snapshots/{RUN}/d4-content-equivalence-audit.json',
)
# Reviewed SQL identifiers/expressions, pinned to complete file bytes. New or
# changed findings still fail closed; gitleaks rules remain enabled everywhere.
REVIEWED_GENERIC = {
    'answer-browser/Q31.html': 'eec4fca4374489300d85195c61518f83a9aadfcf4035cbfd330a86e7d360f213',
    't33-formal-raw.zip/runs-raw/20261018-T13-sql-direct-01/SQL-L1/Q49_r2_t0.json': '49bc0738326173830e4f78f3e3b763d9c75aef78d6a9396f834c5bdae1ddc265',
    't33-formal-raw.zip/runs-raw/20261018-T13-sql-direct-01/SQL-R/Q31_r1_t1.json': 'd02cf49ee5cfa4e37818d03140b1267b610a9be39c29b7edf131854dca797620',
    't33-formal-raw.zip/runs-raw/20261019-T16-full-v14-sql-new-01/SQL-L2/Q49_r2_t0.json': 'a5fd0dc341694131c59eea12a3eeed13c6a63c850671484b7f06f98e330efb35',
    't33-formal-raw.zip/runs-raw/20261025-T14-tuned-01/SQL-L1-tuned-instr/Q79_r2_t0.json': 'd072df469ab28277dc403a666c9cf144e7b0c0ab63ca9766128e7598dfdb78ef',
    't33-formal-raw.zip/runs-raw/20261031-T29-u2-v3-01/SQL-L1-u2/Q119_r2_t1.json': 'c391aeedd0a4a5587872ac18c0d78205dbdffdabcca4aed6e01ad2b29bd3f39b',
    't33-formal-raw.zip/runs-raw/20261031-T29-u2-v3-01/SQL-L1-u2p/Q118_r2_t0.json': '61b20647b826d18644ff38b407b93cd186d644cab51ef09693e6ffdcb58b5199',
    'answer-browser/t34/Q49.html': '56085fa6734fa064c3227c5e8412aa1c8c00aa669bd790a9e9e9a51eb3379115',
    't33-cited-private.zip/t34-run-20261104/codex/20261104-T34-ontology-full-01-content-01/SQL-L3a-full/materials.json': '08b3259317c8b793a3dd46e20346037f3c015c73266395e44b0d72d79f929467',
    't33-formal-raw.zip/runs-raw/20261104-T34-ontology-full-01/SQL-L3a-full/Q49_r3_t0.json': 'a228f6e479a995be3aef972547c0e648be5d8ed0b81ea7a6dafe1a73b7cd1027',
    't33-formal-raw.zip/runs-raw/20261104-T34-ontology-full-01/SQL-L3a-full/Q49_r3_t1.json': 'c432c45c30a237731e3f939c7bb9e780814fd8b895e06fe5885988b368965f1d',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            .replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'))


def lines(path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def raw_hashes(value):
    """Only physical API/execute artifacts referenced by the selected attempt."""
    result = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('raw_sha256', 'exec_raw_sha256') and item:
                result.add(item)
            elif isinstance(item, (dict, list)):
                result.update(raw_hashes(item))
    elif isinstance(value, list):
        for item in value:
            result.update(raw_hashes(item))
    return result


def decoded_text(value):
    """Inspect JSON strings after unescaping; JSON newlines are not drive paths."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return '\n'.join(decoded_text(item) for pair in value.items() for item in pair)
    if isinstance(value, list):
        return '\n'.join(decoded_text(item) for item in value)
    return ''


def completed_u2(records, cell, qids):
    """Keep completed U2 answers; stopped/API-error records are not answers."""
    selected = [r for r in records if r['status'] == 'done']
    expected = {(qid, rep) for qid in qids for rep in (1, 2, 3)}
    identities = [(r['qid'], r['rep']) for r in selected]
    if len(identities) != len(expected) or set(identities) != expected:
        raise ValueError(f'incomplete or duplicate U2 identities: {cell}')
    if any(r['run_id'] != U2_RUN or r['cell'] != cell or not r['turns'] for r in selected):
        raise ValueError(f'invalid U2 source record: {cell}')
    return selected


def referenced_members(data, run, record):
    """Select exact hash-referenced files, excluding orphan/replaced attempts."""
    rawdir = data / 'runs-raw' / run / record['cell']
    wanted = raw_hashes(record)
    found, members = set(), {}
    for path in sorted(rawdir.glob(f"{record['qid']}_r{record['rep']}_*.json")):
        digest = sha(path.read_bytes())
        if digest in wanted:
            members[str(path.relative_to(data))] = path
            found.add(digest)
    if not wanted or found != wanted:
        raise ValueError(f'missing referenced raw artifact: {run}, {record["cell"]}, {record["qid"]}, {record["rep"]}')
    return members


def u2_members(data, qids):
    report = json.loads((ROOT / 'reports/validation/t29-u2-v4-collection.json').read_text())
    if report['run_id'] != U2_RUN or {r['cell'] for r in report['rows']} != set(U2_CELLS):
        raise ValueError('unexpected U2 collection scope')
    members, sources = {}, {}
    count = 0
    for row in report['rows']:
        path = data / 't29-u2-runtime-v4' / 'runs' / U2_RUN / (row['cell'] + '.jsonl')
        digest = sha(path.read_bytes())
        if digest != row['source_log_sha256']:
            raise ValueError(f'U2 source checksum mismatch: {row["cell"]}')
        sources[row['cell']] = digest
        records = completed_u2(lines(path), row['cell'], qids)
        for record in records:
            if {t['system_fingerprint'] for t in record['turns']} != set(report['fingerprints']):
                raise ValueError('unexpected U2 fingerprint')
            members.update(referenced_members(data, U2_RUN, record))
        count += len(records)
    if count != 1764 or count != report['completed_attempts']:
        raise ValueError('unexpected U2 attempt count')
    return members, sources, count


def validate_t34_binding(material, label, verdict):
    original = {k: v for k, v in material.items() if k != 'material_sha256'}
    digest = sha((json.dumps(original, ensure_ascii=False, sort_keys=True, default=str) + '\n').encode())
    identity = tuple(material[k] for k in ('cell', 'qid', 'rep'))
    if (digest != material['material_sha256'] or
            any(r['material_sha256'] != digest or tuple(r[k] for k in ('cell', 'qid', 'rep')) != identity
                for r in (label, verdict)) or not label['final'] or
            label['source_run'] != T34_RUN or label['content_audit'] != T34_AUDIT or
            type(label['content_correct']) is not bool or
            label['content_correct'] != verdict['correct'] or not verdict['basis']):
        raise ValueError('T34 final label/material/verdict binding mismatch')


def t34_artifacts(data, qids, questions):
    """Export frozen evidence and final labels; never re-score or execute SQL."""
    final = ROOT / 'runs' / T34_FINAL
    summary = json.loads((final / 'summary-final.json').read_text())
    receipt = json.loads((final / 'review-receipt.json').read_text())
    labels = lines(final / 'codex-verdicts.jsonl')
    expected = {(c, q, n) for c in T34_CELLS for q in qids for n in (1, 2, 3)}
    lookup = {(r['cell'], r['qid'], r['rep']): r for r in labels}
    if len(labels) != 1176 or set(lookup) != expected or not summary['final']:
        raise ValueError('incomplete T34 final labels')
    private = data / 't34-run-20261104' / 'codex' / T34_AUDIT
    review_path = data / 't34-run-20261104/claude-review/results.json'
    if sha(review_path.read_bytes()) != T34_REVIEW_SHA or receipt['review_results_sha256'] != T34_REVIEW_SHA:
        raise ValueError('T34 Claude review checksum mismatch')
    cited = {str(review_path.relative_to(data)): review_path}
    for name, field in (('review-identity-map-non-v2-v2.json', 'identity_map_sha256'),
                        ('review-note-audit-final.json', 'note_audit_sha256')):
        path = private / name
        if sha(path.read_bytes()) != receipt[field]:
            raise ValueError('T34 private review binding mismatch')
        cited[str(path.relative_to(data))] = path
    mapping = json.loads((private / 'review-identity-map-non-v2-v2.json').read_text())
    notes = {r['anonymous_id']: r for r in json.loads((private / 'review-note-audit-final.json').read_text())}
    reviews = json.loads(review_path.read_text())
    reviewed = {r['anonymous_id']: r for r in reviews}
    if len(reviews) != 174 or set(reviewed) != set(mapping) or set(notes) != set(mapping):
        raise ValueError('incomplete T34 independent review')
    for ident, review in reviewed.items():
        m = mapping[ident]
        label = lookup[m['cell'], m['qid'], m['rep']]
        if (not review['note'].strip() or review['correct'] != label['content_correct'] or
                label['review_anonymous_id'] != ident or label['material_sha256'] != m['material_sha256'] or
                notes[ident]['note_sha256'] != sha(review['note'].encode())):
            raise ValueError('T34 review note/identity mismatch')
    lock_path = private / 'locked-verdicts.json'
    locks = json.loads(lock_path.read_text())
    cited[str(lock_path.relative_to(data))] = lock_path
    members, provenance = {}, {}
    pages = {q: dict(qid=q, question=questions[q].text, attempts={}) for q in qids}
    for cell in T34_CELLS:
        path = ROOT / 'runs' / T34_RUN / (cell + '.jsonl')
        meta = json.loads((ROOT / 'runs' / T34_AUDIT / (cell + '-manifest.json')).read_text())
        if sha(path.read_bytes()) != meta['source_log_sha256']:
            raise ValueError('T34 source log checksum mismatch')
        records = {sha(line): json.loads(line) for line in path.read_bytes().splitlines() if line.strip()}
        material_path = private / cell / 'materials.json'
        ledger_path = private / cell / 'codex-decisions.json'
        if sha(material_path.read_bytes()) != meta['materials_sha256'] or sha(ledger_path.read_bytes()) != locks[cell]:
            raise ValueError('T34 private source checksum mismatch')
        materials = json.loads(material_path.read_text())
        ledger = json.loads(ledger_path.read_text())['records']
        identities = {(m['qid'], m['rep']) for m in materials}
        if len(materials) != 327 or len(records) != 327 or identities != {
                (q, n) for q in {m['qid'] for m in materials} for n in (1, 2, 3)}:
            raise ValueError('incomplete T34 109 x 3 collection')
        cited[str(material_path.relative_to(data))] = material_path
        cited[str(ledger_path.relative_to(data))] = ledger_path
        system_path = private / cell / 'system.txt'
        system_hash = sha(system_path.read_bytes())
        if cell in ('SQL-L1-onto', 'SQL-L3a-full'):
            cited[str(system_path.relative_to(data))] = system_path
        for m in materials:
            record = records[m['source_record_sha256']]
            if (record['status'] != 'done' or record['run_id'] != T34_RUN or record['cell'] != cell or
                    (record['qid'], record['rep']) != (m['qid'], m['rep']) or
                    record['question_sha256'] != sha(questions[m['qid']].text.encode()) or
                    record['system_sha256'] != system_hash):
                raise ValueError('T34 source identity/system mismatch')
            selected = referenced_members(data, T34_RUN, record)
            members.update(selected)
            if m['low']:
                continue
            label = lookup[cell, m['qid'], m['rep']]
            validate_t34_binding(m, label, ledger[f"{m['qid']}:r{m['rep']}"])
            execution = {}
            if m['exec_sha256']:
                matches = [p for p in selected.values() if sha(p.read_bytes()) == m['exec_sha256']]
                if not matches:
                    raise ValueError('missing T34 final execution')
                execution = json.loads(matches[0].read_bytes())
            score = dict(rep=m['rep'], source_run=T34_RUN, content_correct=label['content_correct'],
                         a=int(m['v2_outcome'] == 'correct'), rules=m['rules'])
            pages[m['qid']]['attempts'].setdefault(cell, []).append(public_attempt(score, record, execution))
        correct = sum(r['content_correct'] for r in labels if r['cell'] == cell)
        if correct != summary['main98'][cell]['correct']:
            raise ValueError('T34 final summary count mismatch')
        provenance[cell] = dict(source_log_sha256=meta['source_log_sha256'], system_sha256=system_hash,
                                main_correct=correct, main_attempts=294, all_attempts=327)
    all_files = {str(p.relative_to(data)) for cell in T34_CELLS
                 for p in (data / 'runs-raw' / T34_RUN / cell).glob('*.json')}
    if set(members) != all_files:
        raise ValueError('T34 archive does not cover all raw response/execution files')
    return members, cited, pages, provenance


def public_attempt(score, record, execution):
    turn = record['turns'][-1] if record['turns'] else {}
    rows = execution.get('rows')
    return dict(rep=score['rep'], source_run=score['source_run'],
                query=turn.get('query'), assumption=turn.get('assumption'),
                refused=turn.get('refused', False),
                columns=execution.get('columns', []), rows=(rows or [])[:20],
                total_rows=len(rows) if rows is not None else 0,
                execution_status=turn.get('exec', {}).get('status', '未执行'),
                content_correct=score['content_correct'], delivery_correct=score['a'],
                rules=score['rules'], usage=record.get('usage', {}))


def archive(path, members):
    """Stable ordering, metadata and bytes; source timestamps never affect ZIP."""
    inventory = []
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, source in sorted(members.items()):
            raw = source.read_bytes() if isinstance(source, Path) else source
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            bundle.writestr(entry, raw, compresslevel=9)
            inventory.append(dict(file=name, bytes=len(raw), sha256=sha(raw),
                                  category='执行结果' if name.endswith('.exec.json') else
                                  'API 回包（可能含思考内容）' if name.startswith('runs-raw/') else '报告引用材料'))
    return inventory


STYLE = '<style>body{font:16px system-ui;max-width:1300px;margin:24px auto;padding:0 16px}select{margin:8px;padding:8px}main{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{min-width:0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f5f7;padding:12px}table{display:block;overflow:auto;border-collapse:collapse}td,th{border:1px solid #bbb;padding:5px}a{color:#145bad}@media(max-width:700px){main{grid-template-columns:1fr}}</style>'


def question_page(payload, cells, navigation, *, batch_note='', default_right='SQL-L1plus'):
    return ('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>作答对照</title>' + STYLE + '<a href="index.html">题目与案例列表</a>'
            '<h1 id="title"></h1>' + (f'<p role="note"><strong>{html.escape(batch_note)}</strong></p>' if batch_note else '') +
            '<p id="question"></p><label>题目<select id="nav"></select></label>'
            '<label>共同次数<select id="rep"><option>1</option><option>2</option><option>3</option></select></label>'
            '<main><article><select id="left"></select><div id="a"></div></article>'
            '<article><select id="right"></select><div id="b"></div></article></main>'
            '<p>结果最多展示 20 行；判定采用 accuracy-v5。思考内容不在页面中。题源：Cube semantic-layer-benchmark（MIT）及本项目新题，见仓库 NOTICE。</p>'
            '<script>const data=' + encoded(payload) + ',cells=' + encoded(cells) + ',nav=' + encoded(navigation) + ';'
            "const $=id=>document.getElementById(id);function node(tag,text,parent){const n=document.createElement(tag);n.textContent=text;parent.appendChild(n);return n;}"
            "$('title').textContent=data.qid+' 作答对照';$('question').textContent=data.question;"
            "for(const q of nav){let o=node('option',q,$('nav'));o.value=q;o.selected=q===data.qid;}$('nav').onchange=()=>location.href=$('nav').value+'.html';"
            "for(const id of ['left','right']){for(const c of cells){node('option',c,$(id)).value=c;}$(id).onchange=render;}"
            "const params=new URLSearchParams(location.search);$('right').value=cells.includes(params.get('right'))?params.get('right'):'" + default_right + "';$('left').value=cells.includes(params.get('left'))?params.get('left'):'SQL-L1';$('rep').value=['1','2','3'].includes(params.get('rep'))?params.get('rep'):'1';$('rep').onchange=render;"
            "function side(cell,id){const p=$(id);p.replaceChildren();const r=(data.attempts[cell]||[]).find(r=>r.rep===Number($('rep').value));"
            "if(!r){node('p',cell==='SQL-L1-T4'?'未运行（T4 只跑留出题）':'缺失记录',p);return;}"
            "node('p','内容判定：'+(r.content_correct?'正确':'错误')+'；按约定交付：'+(r.delivery_correct?'通过':'未通过'),p);"
            "node('p','来源：'+r.source_run+' / 第 '+r.rep+' 次；执行：'+r.execution_status,p);"
            "node('pre',r.query||(r.refused?'CANNOT_ANSWER':'无查询'),p);node('p','假设：'+(r.assumption||'未声明'),p);"
            "node('p','结果 '+r.total_rows+' 行（展示前 20 行）',p);const t=node('table','',p),head=node('tr','',t);"
            "for(const c of r.columns)node('th',typeof c==='object'?c.name:c,head);for(const row of r.rows){const tr=node('tr','',t);for(const v of (Array.isArray(row)?row:Object.values(row)))node('td',v===null?'NULL':String(v),tr);}"
            "if(r.rules.length)node('pre','规则标记：'+JSON.stringify(r.rules),p);}function render(){side($('left').value,'a');side($('right').value,'b');}render();</script>")


def index_page(questions, cells, *, title='作答对照：98 题、19 单元',
               introduction='同一次数并排比较。T4 只跑 49 道留出题，其余题标注未运行。',
               default_right='SQL-L1plus'):
    # Pair lists are computed from exported verdicts, without loading response text.
    summary = {q['qid']: {c: {str(r['rep']): r['content_correct'] for r in rs}
                         for c, rs in q['attempts'].items()} for q in questions}
    return ('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>作答对照目录</title>' + STYLE + '<h1>' + html.escape(title) + '</h1>'
            '<p>' + html.escape(introduction) + '</p><nav>' +
            ' · '.join(f'<a href="{q["qid"]}.html">{q["qid"]}</a>' for q in questions) + '</nav>'
            '<h2>同题两单元一对一错</h2><select id="left"></select><select id="right"></select><ul id="pairs"></ul>'
            '<h2>三次时对时错</h2><ul id="mixed"></ul><script>const data=' + encoded(summary) + ',cells=' + encoded(cells) + ';'
            "const $=id=>document.getElementById(id);function item(parent,q,text,left,right,rep){const li=document.createElement('li'),a=document.createElement('a');a.href=q+'.html?'+new URLSearchParams({left,right,rep});a.textContent=text;li.appendChild(a);parent.appendChild(li);}"
            "for(const id of ['left','right']){for(const c of cells){let o=document.createElement('option');o.value=c;o.textContent=c;$(id).appendChild(o);}$(id).onchange=render;}"
            "$('left').value='SQL-L1';$('right').value='" + default_right + "';function render(){$('pairs').replaceChildren();for(const [q,cs] of Object.entries(data)){for(const rep of ['1','2','3']){let a=cs[$('left').value]?.[rep],b=cs[$('right').value]?.[rep];if(a!==undefined&&b!==undefined&&a!==b)item($('pairs'),q,q+' 第 '+rep+' 次：'+$('left').value+' '+(a?'对':'错')+' / '+$('right').value+' '+(b?'对':'错'),$('left').value,$('right').value,rep);}}}"
            "for(const [q,cs] of Object.entries(data)){for(const [c,rs] of Object.entries(cs)){const vs=Object.values(rs);if(vs.length===3&&new Set(vs).size>1)item($('mixed'),q,q+' / '+c+'：'+vs.map(v=>v?'对':'错').join('、'),c,c,'1');}}render();</script>")


def scan(output):
    """Scan extracted bytes, record only filenames/categories, never matched values."""
    patterns = {
        '本机路径': LOCAL_PATH,
        '邮箱': re.compile(rb'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
        'DEEPSEEK_API_KEY 标识': re.compile(rb'DEEPSEEK_API_KEY'),
    }
    key = os.environ.get('DEEPSEEK_API_KEY')
    findings = []
    with tempfile.TemporaryDirectory(prefix='semdebt-t33-scan-') as tmp:
        target = Path(tmp)
        for package in ('t33-formal-raw.zip', 't33-cited-private.zip'):
            with zipfile.ZipFile(output / package) as bundle:
                bundle.extractall(target / package)
        for path in (output / 'answer-browser').rglob('*.html'):
            dest = target / 'answer-browser' / path.relative_to(output / 'answer-browser')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(path.read_bytes())
        for path in sorted(target.rglob('*')):
            if not path.is_file():
                continue
            raw = path.read_bytes()
            searchable = decoded_text(json.loads(raw)).encode() if path.suffix == '.json' else raw
            for category, pattern in patterns.items():
                matches = list(pattern.finditer(searchable))
                if matches:
                    findings.append(dict(file=str(path.relative_to(target)), category=category, count=len(matches)))
            if key and (key.encode() in raw or key.encode() in searchable):
                raise ValueError('environment API key found in candidate; publication blocked')
        result = subprocess.run(['gitleaks', 'dir', str(target), '--redact=100', '--no-banner',
                                 '--no-color', '--ignore-gitleaks-allow', '--log-level', 'error',
                                 '--report-format', 'json', '--report-path', str(target / 'gitleaks.json')],
                                capture_output=True)
        if result.returncode not in (0, 1):
            raise RuntimeError('gitleaks scan failed; inspect local tool configuration')
        leaks = json.loads((target / 'gitleaks.json').read_text())
        unreviewed = 0
        for entry in leaks:
            name = str(Path(entry['File']).relative_to(target))
            reviewed = (entry['RuleID'] == 'generic-api-key' and
                        REVIEWED_GENERIC.get(name) == sha((target / name).read_bytes()))
            unreviewed += not reviewed
            findings.append(dict(file=name, category='gitleaks:' + entry['RuleID'], count=1,
                                 review='已核对：SQL 标识符或表达式误报' if reviewed else '待核对'))
        report = dict(gitleaks_version=subprocess.check_output(['gitleaks', 'version']).decode().strip(),
                      gitleaks_findings=len(leaks), unreviewed_gitleaks_findings=unreviewed,
                      environment_key_checked=bool(key),
                      findings=findings, scanned_files=sum(p.is_file() for p in target.rglob('*')) - 1)
        (output / 't33-scan.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        if unreviewed:
            raise ValueError('gitleaks findings require review; see filenames/categories in t33-scan.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scan', action='store_true', help='scan all extracted package files and browser pages')
    args = parser.parse_args()
    data = Path(os.environ['SEMDEBT_DATA_DIR']).resolve()
    output = data / 'publication'
    browser = output / 'answer-browser'
    if ROOT == output or ROOT in output.parents:
        raise ValueError('publication outputs must stay outside repository')
    browser.mkdir(parents=True, exist_ok=True)
    scores = [r for p in sorted((ROOT / 'runs' / RUN).glob('*.jsonl')) for r in lines(p)]
    assert {r['source_run'] for r in scores} == SOURCE_RUNS
    cells = sorted({r['stratum'] for r in scores})
    assert len(cells) == 19 and all(r['stratum'] == r['cell'] for r in scores)
    main_rows = [r for r in scores if not r['low']]
    qids = sorted({r['qid'] for r in main_rows}, key=lambda q: int(q[1:]))
    assert len(qids) == 98 and len(main_rows) == 5439
    counts = list(csv.DictReader((ROOT / 'reports/results/accuracy-v5-cells.csv').open()))
    for c in cells:
        selected = [r for r in main_rows if r['cell'] == c]
        expected = next(r for r in counts if r['cell'] == c and r['dimension'] == 'all')
        assert len(selected) == int(expected['attempts'])
        assert sum(r['content_correct'] for r in selected) == int(expected['content_correct'])
        assert sum(r['a'] for r in selected) == int(expected['v2_correct'])
        assert len({(r['qid'], r['rep']) for r in selected}) == len(selected)
        if c == 'SQL-L1-T4':
            assert len(selected) == 147 and all(r['split'] == 'heldout' for r in selected)
        else:
            assert {(r['qid'], r['rep']) for r in selected} == {(q, n) for q in qids for n in (1, 2, 3)}
    records = {}
    members = {}
    pages = {q: dict(qid=q, attempts={}) for q in qids}
    for s in scores:
        source = s['source_run'], s['cell']
        if source not in records:
            path = ROOT / 'runs' / source[0] / (source[1] + '.jsonl')
            assert sha(path.read_bytes()) == s['source_log_sha256']
            records[source] = {sha(line): json.loads(line) for line in path.read_bytes().splitlines() if line.strip()}
        record = records[source][s['source_record_sha256']]
        assert (record['qid'], record['rep']) == (s['qid'], s['rep'])
        rawdir = data / 'runs-raw' / source[0] / source[1]
        wanted = raw_hashes(record)
        found = set()
        final_exec = {}
        for path in sorted(rawdir.glob(f"{s['qid']}_r{s['rep']}_*.json")):
            raw = path.read_bytes()
            digest = sha(raw)
            if digest not in wanted:
                continue
            members[str(path.relative_to(data))] = path
            found.add(digest)
            if digest == s.get('exec_sha256'):
                final_exec = json.loads(raw)
        if found != wanted:
            raise ValueError(f'missing referenced raw artifact: {source}, {s["qid"]}, {s["rep"]}')
        if s['has_result'] and not final_exec:
            raise ValueError('missing final execution result')
        if not s['low']:
            pages[s['qid']]['attempts'].setdefault(s['cell'], []).append(public_attempt(s, record, final_exec))
    with frozen_bank(Path(os.environ['SEMDEBT_EVAL_DIR']), 'eval-v1.3') as (questions, _, commit, _):
        assert commit == json.loads((ROOT / 'runs' / RUN / 'manifest.json').read_text())['eval_commit']
        for qid, payload in pages.items():
            payload['question'] = questions[qid].text
            for attempts in payload['attempts'].values():
                attempts.sort(key=lambda r: r['rep'])
            (browser / (qid + '.html')).write_text(question_page(payload, cells, qids))
        onto_members, onto_cited, onto_pages, onto_sources = t34_artifacts(data, qids, questions)
    members.update(onto_members)
    main_index = index_page(list(pages.values()), cells)
    (browser / 'index.html').write_text(main_index.replace('<nav>',
        '<p><a href="t34/index.html">本体对照：新版本模型，同批次四单元（与旧主表不直接比较）</a></p><nav>'))
    onto_browser = browser / 't34'
    onto_browser.mkdir(exist_ok=True)
    for qid, payload in onto_pages.items():
        for attempts in payload['attempts'].values():
            attempts.sort(key=lambda r: r['rep'])
        (onto_browser / (qid + '.html')).write_text(question_page(payload, list(T34_CELLS), qids,
            batch_note=T34_NOTE, default_right='SQL-L1-onto'))
    (onto_browser / 'index.html').write_text(index_page(list(onto_pages.values()), list(T34_CELLS),
        title='本体对照：98 题、4 单元', introduction=T34_NOTE, default_right='SQL-L1-onto'))
    extra_members, u2_sources, u2_attempts = u2_members(data, qids)
    members.update(extra_members)
    packages = {}
    packages['t33-formal-raw.zip'] = archive(output / 't33-formal-raw.zip', members)
    packages['t33-cited-private.zip'] = archive(output / 't33-cited-private.zip',
        {**{p: data / p for p in PRIVATE_FILES}, **onto_cited})
    manifest = dict(model_calls=0, query_executions=0, formal_attempts=len(scores),
                    u2_run=U2_RUN, u2_cells=list(U2_CELLS), u2_attempts=u2_attempts,
                    raw_attempts=len(scores) + u2_attempts + 1308, u2_source_logs=u2_sources,
                    t34_run=T34_RUN, t34_final_run=T34_FINAL, t34_attempts=1308,
                    t34_source_logs=onto_sources, t34_review_sha256=T34_REVIEW_SHA,
                    browser_attempts=len(main_rows) + 1176, questions=98, cells=23,
                    browser_batches={'main': dict(cells=cells, attempts=len(main_rows)),
                                     't34': dict(cells=list(T34_CELLS), attempts=1176, note=T34_NOTE)},
                    t4_note=MISSING, user_scope_confirmation='pending',
                    packages={name: dict(bytes=(output / name).stat().st_size,
                                         sha256=sha((output / name).read_bytes()), files=entries)
                              for name, entries in packages.items()},
                    browser={str(p.relative_to(browser)): dict(bytes=p.stat().st_size, sha256=sha(p.read_bytes()))
                             for p in sorted(browser.rglob('*.html'))})
    (output / 't33-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (output / 't33-SHA256SUMS').write_text(''.join(f'{sha((output / name).read_bytes())}  {name}\n'
                                               for name in sorted(packages)))
    if args.scan:
        scan(output)
    print(json.dumps({k: v for k, v in manifest.items() if k not in ('packages', 'browser')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
