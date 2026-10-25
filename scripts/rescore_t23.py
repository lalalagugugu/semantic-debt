"""Offline v2/v3 comparison, frozen bank objects and hash-verified saved results.

uv run python scripts/rescore_t23.py --run-id <new-run-id>

Paths come only from SEMDEBT_EVAL_DIR, SEMDEBT_DATA_DIR and SEMDEBT_CARDS_DIR.
No model calls, query execution, checkout changes, or source-log rewrites.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

from harness import run_direct as R, scorer_v3 as V3
from harness.questions import load_questions, question_files

REPO = Path(__file__).resolve().parents[1]
TAG = 'eval-v1.2'
CARDS = ('T13', 'T15', 'T16', 'C13', 'T14', 'T22b')
CODE_FILES = ('harness/scorer_v2.py', 'harness/scorer_v3.py', 'scripts/rescore_t23.py')
CURRENT = {
    **{c: ['20261018-T13-sql-direct-01'] for c in ('SQL-L0', 'SQL-R', 'SQL-L1', 'SQL-L1c', 'SQL-L1.5W')},
    'SQL-L1.5S': ['20261019-T13-l15s-v14-01'],
    **{c: ['20261019-T15-explorer-01'] for c in ('SQL-L0-E', 'SQL-L1-E')},
    'SQL-L2-E': ['20261020-T15-explorer-l2e-02', '20261020-T15-explorer-l2e-03'],
    'SQL-L2': ['20261019-T16-full-v14-sql-new-01'],
    'SQL-L2-notes-v12': ['20261019-T16-full-v14-sql-old-01'],
    'JSON-L2': ['20261019-T16-full-v14-json-01'],
    **{f'SQL-L1-T{k}': ['20261019-C13-ladder-02'] for k in (2, 3, 4)},
    **{c: ['20261025-T14-tuned-01'] for c in ('SQL-L1-tuned', 'SQL-L1-tuned-instr')},
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def environment(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f'{name} is not set')
    return Path(value).expanduser()


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True).stdout


@contextmanager
def frozen_bank(root, tag=TAG):
    """Read the tag's immutable objects; the user's bank checkout stays untouched."""
    commit = git(root, 'rev-parse', '--verify', f'{tag}^{{commit}}').decode().strip()
    archive = git(root, 'archive', commit, 'questions', 'refs')
    with tempfile.TemporaryDirectory(prefix='semdebt-t23-bank-') as directory:
        destination = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            members = bundle.getmembers()
            if any(not (m.isfile() or m.isdir()) or m.name.startswith('/')
                   or '..' in Path(m.name).parts for m in members):
                raise ValueError('bank archive contains a nonregular or unsafe entry')
            bundle.extractall(destination, filter='data')
        manifest = json.loads((destination / 'refs/MANIFEST.json').read_text())
        entries = {r['result_path']: r for r in manifest['records']}
        columns = {}
        for file in question_files(destination):
            payload = yaml.safe_load(file.read_text())
            for question in payload['questions'] if isinstance(payload, dict) else payload:
                columns[question['id']] = [entries[r['result_path']]['columns'] for r in question['refs']]
                for ref in question['refs']:
                    entry = entries[ref['result_path']]
                    if sha((destination / ref['result_path']).read_bytes()) != entry['sha256']:
                        raise ValueError(f"reference checksum mismatch: {question['id']}")
        yield {q.qid: q for q in load_questions(destination)}, columns, commit, sha(archive)


@dataclass(frozen=True)
class Source:
    path: Path
    origin: str
    data: bytes

    @property
    def run(self):
        return self.path.parent.name

    @property
    def cell(self):
        return self.path.stem


def discover(repo, cards_dir):
    sources = {}
    roots = [(repo, 'repo')]
    roots += [(cards_dir / card, f'$SEMDEBT_CARDS_DIR/{card}') for card in ('T14', 'T22b')]
    for root, origin in roots:
        for file in sorted((root / 'runs').glob('*/*.jsonl')):
            run = file.parent.name
            if (not re.search(r'-(?:' + '|'.join(CARDS) + r')-', run)
                    or 'rescore' in run or not file.name.startswith(('SQL-', 'JSON-'))):
                continue
            source = Source(file, origin, file.read_bytes())
            key = run, file.stem
            if key in sources:
                old = sources[key]
                if old.data.startswith(source.data):
                    continue
                if not source.data.startswith(old.data):
                    raise ValueError(f'divergent copies of {run}/{file.name}')
            sources[key] = source
    return [sources[key] for key in sorted(sources)]


def saved_turn(turn, raw_dir, qid, rep):
    execution = turn['exec']
    if execution.get('status') == 'refused':
        return V3.REFUSAL, None, None
    if execution.get('error_class') == R.NO_QUERY:
        return V3.ExecError('no_query'), None, None
    file = raw_dir / f"{qid}_r{rep}_t{turn['turn']}.exec.json"
    data = file.read_bytes()
    digest = sha(data)
    if digest != execution.get('exec_raw_sha256'):
        raise ValueError(f'execution checksum mismatch: {raw_dir.name}/{qid}/r{rep}')
    payload = json.loads(data)
    if payload['error'] is not None:
        return V3.ExecError('execution_error'), None, digest
    columns = payload.get('columns')
    if columns is None:
        # Older artifacts with no column evidence remain eligible for v2 only.
        return payload['rows'], None, digest
    rows = [[Decimal(value) if isinstance(value, str) and i < len(columns)
             and columns[i].get('type') == 'number' else value
             for i, value in enumerate(row)] for row in payload['rows']]
    return rows, columns, digest


def compare_turn(turn, raw_dir, question, rep, reference_columns):
    candidate, columns, digest = saved_turn(turn, raw_dir, question.qid, rep)
    v2 = R.score_question(candidate, question, score_timeout_s=None)
    if question.pending or isinstance(candidate, (str, V3.ExecError)):
        v3 = {**v2, 'transformations': []}
    else:
        v3 = asdict(V3.score_detailed(candidate, question.refs, question.rules,
            reference_rules=question.ref_rules, candidate_columns=columns,
            reference_columns=reference_columns))
    return {'v2': v2, 'v3': v3, 'exec_raw_sha256': digest,
            'candidate_columns_sha256': sha(json.dumps(columns, sort_keys=True).encode())}


def rescore_source(source, questions, reference_columns, raw_root, run_id, commit):
    rows, other, seen = [], Counter(), set()
    for line in source.data.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get('status') != 'done':
            other[record.get('status', 'missing_status')] += 1
            continue
        qid, rep = record['qid'], record['rep']
        if (qid, rep) in seen:
            raise ValueError(f'duplicate done attempt in {source.run}/{source.cell}: {qid}/r{rep}')
        seen.add((qid, rep))
        question = questions[qid]
        if record.get('question_sha256') != R.sha256(question.text):
            raise ValueError(f'question text absent/changed: {source.run}/{source.cell}/{qid}')
        raw_dir = raw_root / source.run / source.cell
        turns = record['turns']
        first = compare_turn(turns[0], raw_dir, question, rep, reference_columns[qid])
        final = first if len(turns) == 1 else compare_turn(turns[-1], raw_dir, question, rep, reference_columns[qid])
        rows.append({'run_id': run_id, 'cell': source.cell, 'qid': qid, 'rep': rep, 'status': 'done',
            'source_run': source.run, 'source_origin': source.origin, 'source_log_sha256': sha(source.data),
            'source_record_sha256': sha(line), 'question_sha256': record['question_sha256'],
            'eval_tag': TAG, 'eval_commit': commit, 'semantic_tag': record.get('semantic_tag'),
            'cost_cny': 0, 'first': first, 'final': final})
    return rows, dict(other)


def main_rows(rows, questions):
    return [r for r in rows if questions[r['qid']].scoring == 'deterministic'
            and not questions[r['qid']].meta['low_discrimination']]


def statistics(rows):
    valid = [r for r in rows if all(r['final'][v]['outcome'] in ('correct', 'wrong', 'exec_error', 'refused')
                                  for v in ('v2', 'v3'))]
    counts = [sum(r['final'][v]['outcome'] == 'correct' for r in valid) for v in ('v2', 'v3')]
    flips = sum(r['final']['v2']['outcome'] != r['final']['v3']['outcome'] for r in valid)
    return {'attempts': len(rows), 'denominator': len(valid), 'v2_correct': counts[0], 'v3_correct': counts[1],
            'changed': flips, 'no_verdict': len(rows) - len(valid)}


def pct(count, total):
    return f'{100 * count / total:.1f}% ({count}/{total})' if total else '—'


def current_results(results):
    selected = {}
    for cell, sources in CURRENT.items():
        by_attempt = {}
        for run in sources:
            for row in results.get((run, cell), []):
                by_attempt[row['qid'], row['rep']] = row
        if by_attempt:
            selected[cell] = list(by_attempt.values())
    # New T22b units are named by their logs, never guessed from a future plan.
    for (run, cell), rows in results.items():
        if '-T22b-' in run:
            if cell in selected:
                raise ValueError(f'multiple T22b sources require explicit report selection: {cell}')
            selected[cell] = rows
    return selected


def ordering_changes(selected, questions):
    complete = {}
    expected = {(q.qid, rep) for q in questions.values() if q.scoring == 'deterministic'
                and not q.meta['low_discrimination'] for rep in (1, 2, 3)}
    for cell, rows in selected.items():
        subset = main_rows(rows, questions)
        stats = statistics(subset)
        if {(r['qid'], r['rep']) for r in subset} == expected and not stats['no_verdict']:
            complete[cell] = stats
    changes = []
    sign = lambda x: (x > 0) - (x < 0)
    for i, left in enumerate(sorted(complete)):
        for right in sorted(complete)[i + 1:]:
            before = sign(complete[left]['v2_correct'] - complete[right]['v2_correct'])
            after = sign(complete[left]['v3_correct'] - complete[right]['v3_correct'])
            if before != after:
                changes.append({'left': left, 'right': right, 'v2': before, 'v3': after})
    return changes, sorted(complete)


def report(results, inventory, questions, run_id, commit):
    selected = current_results(results)
    changes, comparable = ordering_changes(selected, questions)
    all_rows = [r for rows in results.values() for r in rows]
    triggered = {stage: Counter(r[stage]['v3'].get('sensitivity') for r in all_rows
        if r[stage]['v2']['outcome'] != r[stage]['v3']['outcome']) for stage in ('first', 'final')}
    out = ['# Scorer v3 呈现容错：敏感性分析', '',
        '**主数字仍用 v2。** v3 规则是在看过错例后归纳的，只作敏感性分析，不替换原报告主数字。', '',
        f'- 题库：`{TAG}` = `{commit}`，从 `$SEMDEBT_EVAL_DIR` 的 tag 对象导出，不读取当前工作区版本。',
        f'- 新 run：`runs/{run_id}/`；源日志只读，执行结果哈希逐份校验；模型调用 0、查询执行 0、费用 0。',
        '- 主表排除 judge 与低区分度，以 98 题 × 3 为完整范围；子集单元如实给出分母，不补造缺失作答。',
        '- 新判对尚待 Claude Code 跨厂商逐条抽查；本报告不宣称最终验收通过。', '',
        '复现（先在命令环境设置用户指定的三个路径，run-id 必须全新）：'
        '`uv run --offline python scripts/rescore_t23.py --run-id <new-run-id>`。', '',
        '## 规则与保守边界', '',
        '- P1：标准年月/季度表示，年份必须完整保留；仅用既有列名、类型识别，不翻译业务上下文。不转换含 selection、rankings、Top-N 或 unordered_pairs 的期间契约。',
        '- P2：单分类维度、单指标；成员列名必须与分类成员完全对应（或 member__measure / measure__member），其余分组列同名且一一映射。不聚合、去重、补零、翻译或猜同义词；任何歧义保持原判。',
        '- P3：仅参考名称为 NULL 或空字符串，完整必答编码精确保留，且名称列值就是该编码时接受。文字 Unknown / 未知 等均不算空名；复合编码或非同名列证据不足时保持原判。',
        '- P4：v2 已通过列映射支持额外列，本次没有新增 P4 判分代码，也没有已证实需要补的缺口；回归覆盖额外列与重复行。v2 原有宽松行为亦未收紧。',
        '- 必答列、排序、Top-N、计数及数值容差不放宽；不接受只给名称代替编码或忽略排序。', '',
        f'全部源日志首次判定转换计数：{dict(triggered["first"])}；最终判定转换计数：{dict(triggered["final"])}。'
        '没有触发的规则不代表实现缺失；在当前保守证据下不新增判对，后续不得为转正错例扩充业务映射。', '',
        '## 当前对照单元（v2 主数字，v3 敏感性）', '',
        '| 单元 | 主表题数 / 作答 | v2 | v3 | 改判条数 | 无判定 |',
        '|---|---:|---|---|---:|---:|']
    for cell, rows in selected.items():
        subset = main_rows(rows, questions)
        stats = statistics(subset)
        out.append(f"| {cell} | {len({r['qid'] for r in subset})} / {len(subset)} | "
                   f"{pct(stats['v2_correct'], stats['denominator'])} | {pct(stats['v3_correct'], stats['denominator'])} | "
                   f"{stats['changed']} | {stats['no_verdict']} |")
    out += ['', 'SQL-L2-E 按已记录的续跑规则合并 -02 与 -03，后者替换同题同次；'
            'C13 T4 是留出子集，不与完整 98 题的准确率直接排位。', '',
            '## 相对排序', '', f'只比较相同 98 题 × 3 且都有判定的单元：{", ".join(comparable)}。', '']
    if changes:
        relation = {-1: '<', 0: '=', 1: '>'}
        out += [f"- {r['left']} 与 {r['right']}：v2 {relation[r['v2']]}，v3 {relation[r['v3']]}。" for r in changes]
    else:
        out.append('相对排序（含并列关系）没有改变。')
    out += ['', '## 含低区分度附表（完整范围 109 题）', '',
            '| 单元 | 作答 | v2 | v3 | 改判条数 |', '|---|---:|---|---|---:|']
    for cell, rows in selected.items():
        subset = [r for r in rows if questions[r['qid']].scoring == 'deterministic']
        s = statistics(subset)
        out.append(f"| {cell} | {len(subset)} | {pct(s['v2_correct'], s['denominator'])} | "
                   f"{pct(s['v3_correct'], s['denominator'])} | {s['changed']} |")
    out += ['', '## 全部源运行清点（含历史、试跑及作废运行，分开保留）', '',
            '| 源 run / 单元 | done | 非 done | 主表 v2 | 主表 v3 | 主表改判 |',
            '|---|---:|---|---|---|---:|']
    for item in inventory:
        rows = results[item['run'], item['cell']]
        s = statistics(main_rows(rows, questions))
        out.append(f"| {item['run']} / {item['cell']} | {len(rows)} | {item['non_done']} | "
                   f"{pct(s['v2_correct'], s['denominator'])} | {pct(s['v3_correct'], s['denominator'])} | {s['changed']} |")
    t22b = any('-T22b-' in run for run, _ in results)
    out += ['', 'T14 从 `$SEMDEBT_CARDS_DIR/T14/runs/` 纳入；'
            + ('T22b 已纳入。' if t22b else '本次未发现 T22b 作答日志，完成后须新开 run 补评。') +
            '历史、试跑和作废源仅用于完整清点，不混入当前单元排序。', '',
            '## 新增判对逐条复核清单', '',
            '每条的转换列索引、源日志与执行结果哈希见新 run 的 JSONL；原始题面、SQL、行值均不入库。', '',
            '| 源 run | 单元 | 题 / 次 | final 转换 | 主表 |', '|---|---|---|---|---|']
    flips = []
    for (source, cell), rows in results.items():
        for row in rows:
            if row['final']['v2']['outcome'] != row['final']['v3']['outcome']:
                flips.append(row)
                out.append(f"| {source} | {cell} | {row['qid']} / {row['rep']} | "
                    f"{row['final']['v3']['sensitivity']} | {'是' if main_rows([row], questions) else '否'} |")
    if not flips:
        out.append('| — | — | — | 无新增判对 | — |')
    return '\n'.join(out) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.run_id):
        parser.error('run-id must be a single safe directory name')
    target = REPO / 'runs' / args.run_id
    if target.exists():
        raise FileExistsError('append-only runs: choose a new run-id')
    code_hashes = {name: sha((REPO / name).read_bytes()) for name in CODE_FILES}
    data_root, cards_dir = environment('SEMDEBT_DATA_DIR'), environment('SEMDEBT_CARDS_DIR')
    sources = discover(REPO, cards_dir)
    if not sources:
        raise ValueError('no source runs found')
    with frozen_bank(environment('SEMDEBT_EVAL_DIR')) as (questions, columns, commit, archive_hash):
        results, inventory = {}, []
        for source in sources:
            rows, other = rescore_source(source, questions, columns, data_root / 'runs-raw', args.run_id, commit)
            results[source.run, source.cell] = rows
            inventory.append({'run': source.run, 'cell': source.cell, 'origin': source.origin,
                'source_log_sha256': sha(source.data), 'done': len(rows), 'non_done': other})
            print(f'{source.run}/{source.cell}: {len(rows)} done', flush=True)
        body = report(results, inventory, questions, args.run_id, commit)
    if code_hashes != {name: sha((REPO / name).read_bytes()) for name in CODE_FILES}:
        raise RuntimeError('scoring code changed during the run; no results written')
    if any(source.path.read_bytes() != source.data for source in sources):
        raise RuntimeError('source logs changed during the run; no results written')
    target.mkdir()
    for (run, cell), rows in results.items():
        with (target / f'{run}--{cell}.jsonl').open('x') as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    manifest = {'eval_tag': TAG, 'eval_commit': commit, 'bank_archive_sha256': archive_hash,
        'code_sha256': code_hashes, 'harness_commit': R.harness_commit(),
        'current_sources': CURRENT,
        'sources': inventory, 't22b_present': any('-T22b-' in s.run for s in sources)}
    (target / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (REPO / 'reports/results/scorer-v3.md').write_text(body)
    with (REPO / 'runs/INDEX.md').open('a') as stream:
        stream.write(f'\n## T23 v3 敏感性重评：{args.run_id}\n\n'
            '| run-id | 单元 | 来源 | 题库 | 费用 | 原因 |\n|---|---|---|---|---:|---|\n'
            f'| {args.run_id} | 全部已发现 T13 / T15 / T16 / C13 / T14 / T22b 单元 | '
            f'{len(sources)} 份源日志，{sum(i["done"] for i in inventory)} 条 done；逐份见 manifest.json | '
            f'{TAG}={commit[:7]} | 0 | 用户审定的 P1–P4；v2 主数字、v3 敏感性分析；只读原始执行结果，'
            '不调用模型、不执行查询；新增判对待 Claude Code 逐条复核 |\n')
    print(f'wrote runs/{args.run_id} and reports/results/scorer-v3.md', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
