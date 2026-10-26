"""Build the private T31 decision sheet from saved attribution material; offline only.

Human descriptions live in $SEMDEBT_DATA_DIR/t31-presentation-notes.json.
Refuse to overwrite the sheet, which may already contain user decisions.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
RUN = '20261025-T22b-attrib-01'


def reference_review(proposal_path=None, output=None, questions=None):
    """Replay proposed references only; retain frozen rules and original logs."""
    sys.path.insert(0, str(ROOT))
    from harness.rescore import candidate_of
    from harness.run_direct import score_question
    from reports.midterm.analyze import SPECS
    from scripts.rescore_t23 import frozen_bank

    data = Path(os.environ['SEMDEBT_DATA_DIR'])
    proposal_path = proposal_path or data / 't31-reference-proposals-final.json'
    output = output or data / 't31-reference-replay-reproduced.json'
    if ROOT == output.resolve() or ROOT in output.resolve().parents:
        raise ValueError('private output must be outside the repository')
    if output.exists():
        raise FileExistsError('preserve existing replay: choose a new output filename')
    proposals = json.loads(proposal_path.read_text())
    if questions:
        if not set(questions) <= proposals.keys():
            raise ValueError('unknown proposal question')
        proposals = {q: proposals[q] for q in questions}
    specifications = SPECS + [
        (cell, cell, [run], '定稿')
        for run, cells in [
            ('20261025-T14-tuned-01', ['SQL-L1-tuned', 'SQL-L1-tuned-instr']),
            ('20261025-T22b-l1plus-l3a-03-rescore-01', ['SQL-L1plus', 'SQL-L3a'])]
        for cell in cells]
    attempts, changes, sources = [], [], {}
    with frozen_bank(Path(os.environ['SEMDEBT_EVAL_DIR'])) as (bank, _, commit, archive):
        for label, cell, runs, scope in specifications:
            records = {}
            for run in runs:
                path = ROOT / 'runs' / run / f'{cell}.jsonl'
                raw = path.read_bytes()
                sources[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
                for row in map(json.loads, raw.splitlines()):
                    if row['qid'] in proposals:
                        records[row['qid'], row['rep']] = row
            for (qid, rep), row in sorted(records.items()):
                if row['status'] != 'done':
                    raise ValueError('incomplete source attempt')
                question = bank[qid]
                raw_run = row.get('rescored_from', {}).get('run_id', row['run_id'])
                candidate = candidate_of(row['turns'][-1], data / 'runs-raw' / raw_run / cell, qid, rep)
                old = score_question(candidate, question)
                if old['outcome'] != row['final']['outcome']:
                    raise ValueError(f'baseline mismatch: {label} {qid} r{rep}')
                spec = proposals[qid]
                refs, rules = [], []
                for entry in spec['references']:
                    if 'existing_index' in entry:
                        index = entry['existing_index']
                        refs.append(question.refs[index])
                        rules.append(question.ref_rules[index] if question.ref_rules else None)
                    else:
                        artifact = Path(entry['path'])
                        raw = artifact.read_bytes()
                        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
                            raise ValueError('proposed reference checksum mismatch')
                        refs.append(json.loads(raw)['rows'])
                        rules.append(None)
                new = score_question(candidate, replace(question, refs=refs, ref_rules=rules))
                item = {'cell': label, 'scope': scope, 'qid': qid, 'rep': rep,
                        'category': spec['category'], 'source_run': row['run_id'],
                        'old': old, 'proposed': new}
                attempts.append(item)
                if old['outcome'] != new['outcome']:
                    changes.append(item)
    result = {'eval_commit': commit, 'bank_archive_sha256': archive,
              'proposal_sha256': hashlib.sha256(proposal_path.read_bytes()).hexdigest(),
              'source_sha256': sources, 'attempts': attempts, 'changes': changes,
              'model_calls': 0, 'cost_cny': 0}
    with output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'review_questions': len(proposals), 'attempts': len(attempts),
                      'changed_outcomes': len(changes),
                      'pending': sum(r['proposed']['outcome'] == 'pending' for r in attempts)}, ensure_ascii=False))


def main():
    data = Path(os.environ['SEMDEBT_DATA_DIR']).resolve()
    if data == ROOT or ROOT in data.parents:
        raise ValueError('private output must be outside the repository')
    target = data / 't31-presentation-sheet.md'
    if target.exists():
        raise FileExistsError('preserve user decisions: sheet already exists')
    report = json.loads((ROOT / 'reports/results/l1plus-error-attribution.json').read_text())
    selected = [r for r in report['items'] if any(
        r[s]['category'] == '只是呈现不同' for s in ('flash', 'codex'))]
    notes_path = data / 't31-presentation-notes.json'
    notes = json.loads(notes_path.read_text())
    keys = {f"{r['qid']}_r{r['rep']}" for r in selected}
    if len(selected) != 47 or len({r['qid'] for r in selected}) != 22:
        raise ValueError('expected 22 questions / 47 unique attempts')
    if set(notes['attempts']) != keys or len(keys) != 47:
        raise ValueError('human notes do not cover exactly the selected attempts')
    counts = Counter()
    md = ['# T31 呈现差异用户判定单', '',
          '范围：SQL-L1plus 任一家归因为「只是呈现不同」的 22 题、47 次作答。',
          '请在每题末尾填「算对 / 不算对 / 看情况」；同题不同次数可分别判定，并注明条件。',
          '归因标签仅用于圈定范围，不代表这些作答均应判对。此处不改变主评分。',
          '证据摘自既有归因输入（最多前10行），不是完整结果相等证明；完整作答结果路径另附。',
          '含题面及结果，仅存仓库外，不提交。第二部分第3、4步待用户填写后进行。', '']
    for qid in sorted({r['qid'] for r in selected}, key=lambda q: int(q[1:])):
        rows = sorted((r for r in selected if r['qid'] == qid), key=lambda r: r['rep'])
        md += [f'## {qid}', '']
        first = True
        for row in rows:
            key = f"{qid}_r{row['rep']}"
            note = notes['attempts'][key]
            path = data / 'runs-raw' / RUN / 'inputs' / f'{key}.txt'
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != note['material_sha256']:
                raise ValueError(f'material changed: {key}')
            material = raw.decode()
            if first:
                md += [material.split('## 参考答案')[0].replace('## 题面\n', '').strip(), '']
                descriptions = list(dict.fromkeys(
                    notes['attempts'][f"{qid}_r{r['rep']}"]['difference'] for r in rows))
                md += ['差异说明：' + ' '.join(descriptions), '']
                first = False
            counts.update(note['categories'])
            md += [f"### r{row['rep']}", '',
                   f"- 差异形态：{'；'.join(note['categories'])}",
                   f"- 原归因：Flash＝{row['flash']['category']}；Codex＝{row['codex']['category']}",
                   f"- [完整作答执行结果]({note['execution_path']})", '',
                   '<details><summary>参考与作答结果摘录（保留原始标签、量纲与空值）</summary>', '']
            evidence = material.split('## 参考答案', 1)[1]
            evidence = re.sub(r'```sql.*?```\n?', '', evidence, flags=re.S)
            md += ['参考答案' + evidence, '</details>', '']
        md += ['用户判定：____（算对 / 不算对 / 看情况）', '', '条件或分次数判定：____', '']
    md += ['## 补充：SQL-L1-tuned-instr 调优题同类作答（不计入上述47次）', '',
           'Q36 r1：标签措辞差异；具体材料见下方。', '',
           notes['tuned_supplement'], '',
           '用户判定（补充 Q36 r1）：____（算对 / 不算对 / 看情况）', '']
    with target.open('x') as stream:
        stream.write('\n'.join(md))
    print(json.dumps({'questions': 22, 'attempts': 47, 'supplement_attempts': 1,
                      'category_attempt_counts_overlapping': dict(counts)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-proposals', action='store_true')
    parser.add_argument('--proposal-file', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--questions', nargs='+')
    args = parser.parse_args()
    if args.reference_proposals:
        reference_review(args.proposal_file, args.output, args.questions)
    elif args.proposal_file or args.output or args.questions:
        parser.error('reference options require --reference-proposals')
    else:
        main()
