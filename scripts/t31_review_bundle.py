"""Export candidate-only public flips and private independent-review materials."""
from __future__ import annotations
import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.rescore_t23 import frozen_bank
from scripts.t31_candidate_scan import RULES


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


def main():
    data = Path(os.environ['SEMDEBT_DATA_DIR']).resolve()
    if data == ROOT or ROOT in data.parents:
        raise ValueError('private materials must be outside the repository')
    source = data / 't31-candidate-all-units-validated.json'
    audit = json.loads(source.read_text())
    assert digest((ROOT / 'scripts/t31_candidate_scan.py').read_bytes()) == audit['script_sha256']
    attempts = audit['attempts']
    assert all(not x['v2_correct'] or x['candidate_content_correct'] for x in attempts)
    for cell in {x['cell'] for x in attempts}:
        rows = [x for x in attempts if x['cell'] == cell]
        assert sum(x['candidate_content_correct'] for x in rows) >= sum(x['v2_correct'] for x in rows)
    flips = sorted((x for x in attempts if x['rules']), key=lambda x: (x['source_run'], x['cell'], int(x['qid'][1:]), x['rep']))
    assert all(not x['v2_correct'] and x['candidate_content_correct'] for x in flips)
    assert len(flips) == 338 and sum(not x['seen_error'] for x in flips) == 303
    assert len({(x['source_run'], x['cell'], x['qid'], x['rep']) for x in flips}) == len(flips)
    bundle = data / 't31-claude-review-20261027'
    bundle.mkdir(exist_ok=False)
    public = ROOT / 'reports/validation/t31-v4-flips.csv'
    with public.open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(['qid', 'cell', 'rep', 'rules', 'in_original_sheet'])
        for x in flips:
            writer.writerow([x['qid'], x['cell'], x['rep'], ';'.join(x['rules']), str(x['seen_error']).lower()])
    index = []
    with frozen_bank(Path(os.environ['SEMDEBT_EVAL_DIR'])) as (bank, columns, commit, archive_hash):
        assert commit == audit['eval_commit'] and archive_hash == audit['archive_sha256']
        for number, x in enumerate(flips, 1):
            entry = {'csv_data_row': number, **x}
            if not x['seen_error']:
                target = bundle / f'{number:04d}'
                target.mkdir()
                raw = Path(x['exec_path']).read_bytes()
                assert digest(raw) == x['exec_sha256']
                (target / 'answer-result.json').write_bytes(raw)
                q = bank[x['qid']]
                write_json(target / 'reference-results.json', {'qid': q.qid, 'references': q.refs, 'columns': columns[q.qid], 'rules': q.rules, 'reference_rules': q.ref_rules, 'eval_commit': commit})
                write_json(target / 'question.json', {'qid': q.qid, 'text': q.text, 'meta': q.meta})
                write_json(target / 'hit-rules.json', {r: RULES[r] for r in x['rules']})
                entry['bundle_directory'] = target.name
                entry['file_sha256'] = {p.name: digest(p.read_bytes()) for p in target.iterdir()}
            index.append(entry)
    write_json(bundle / 'index.json', {'public_csv_sha256': digest(public.read_bytes()), 'source_sha256': digest(source.read_bytes()), 'all_flips': index, 'outside_sheet_count': 303, 'model_calls': 0})
    (bundle / 'candidate-rules.py').write_bytes((ROOT / 'scripts/t31_candidate_scan.py').read_bytes())
    (bundle / 'README.md').write_text('''# 独立逐次复核材料（仓库外）

303次判定单外候选改判，每个编号目录对应公共CSV的数据行号（不含表头）。index.json保留全部338行的来源运行与哈希，避免历史运行中相同题号/单元/次数混淆；不得去重合并。

每次必需材料：answer-result.json（完整作答结果、列名类型）、reference-results.json（全部参考、列类型、选择域/并列及评分元数据）、hit-rules.json（命中的通用规则）。另附question.json用于核对题面要求；candidate-rules.py为候选识别实现快照。参考集合可能是边界候选池，须结合规则判断应取行数，不能直接要求全表一致。

请独立核对每次作答的实体、分组、期间、数值与规则适用条件；命中只是待验证主张。逐次记录通过/不通过/待用户裁决及理由，以CSV数据行号关联。需要最终查询或原系统上下文时，index.json中的源日志与系统哈希可追溯；不含原模型思考。材料未出站；用户另开Claude Code会话复核，本脚本没有模型调用。复核通过、用户审定之后才可实施v4和双口径重算。
''')
    lines = ['\n## 每条规则按单元分布\n', '| 规则 | 单元 | 新增认可 | 判定单外 |', '|---|---|---:|---:|']
    for rule in RULES:
        hits = [x for x in flips if rule in x['rules']]
        assert len(hits) == audit['per_rule'][rule]['changed']
        for cell in sorted({x['cell'] for x in hits}):
            subset = [x for x in hits if x['cell'] == cell]
            lines.append(f"| {rule} | {cell} | {len(subset)} | {sum(not x['seen_error'] for x in subset)} |")
    (data / 't31-rule-distribution.md').write_text('\n'.join(lines) + '\n')
    terminal_path = data / 't31-final-review-list.json'
    terminal = json.loads(terminal_path.read_text())
    moved = terminal['await_user_policy']
    assert len(moved) == 3
    lookup = {(x['source_run'], x['cell'], x['qid'], x['rep']): x for x in attempts}
    differences = 0
    for item in moved:
        x = lookup[tuple(item[k] for k in ('source_run', 'cell', 'qid', 'rep'))]
        different = bool(x['null_zero_accept'] and not x['null_zero_reject'])
        differences += different
        item.update(null_zero_policy_difference=different, reason='用户已选空值不等于0；不自动认可。需后续终审核实其余内容与规则适用性，不得将空值改判为0。')
    assert differences == 2
    terminal['ready_for_later_authorization'].extend(moved)
    terminal['await_user_policy'] = []
    terminal['summary'].update(ready_for_later_authorization=2081, await_user_policy=0, original_sheet_ready=12, original_sheet_policy=0)
    terminal['null_policy'] = 'strict: NULL != 0; approved by user 2026-10-27'
    write_json(data / 't31-final-review-list-strict.json', terminal)
    assert len(terminal['ready_for_later_authorization']) == 2081
    print('Exported 338 public flips; 303 private review folders; 2081 future final-review items; no scoring changes.')


if __name__ == '__main__':
    main()
