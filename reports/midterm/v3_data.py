"""T28 offline analysis. No model calls, SQL execution, or source-log updates.

uv run --offline python reports/midterm/v3_data.py --rescore-run <new-run-id>
uv run --offline python reports/midterm/v3_data.py
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from decimal import Decimal
import itertools
import json
import math
import os
from pathlib import Path
import random
import re
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from reports.midterm import analyze as A
from scripts import rescore_t23 as V

T22 = '20261025-T22b-l1plus-l3a-03'
T14 = '20261025-T14-tuned-01'
V3_OLD = '20261025-T23-v3-02'
V3_NEW = '20261025-T28-v3-01'
CELLS = ('SQL-L1', 'SQL-L1plus', 'SQL-L3a', 'SQL-L1-tuned', 'SQL-L1-tuned-instr')
CATEGORIES = ('语义文档里的文字仍有两种以上读法', '口径在语义文档里根本没写',
              '文档写清楚了，模型理解偏了', '题面本身有歧义', '只是呈现不同', '参考答案或评分可疑')
SPECS = A.SPECS + [(c, c, [T14], '调优') for c in CELLS[-2:]] + [
    (c, c, [T22 + '-rescore-01'], '定稿') for c in CELLS[1:3]]
SOURCES = {}
RAW = {}
COMMAND = 'uv run --offline python reports/midterm/v3_data.py'


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    key = str(path.relative_to(ROOT))
    value = {'sha256': V.sha(raw), 'lines': len(raw.splitlines())}
    if key in SOURCES and SOURCES[key] != value:
        raise ValueError(f'input changed: {key}')
    SOURCES[key] = value
    return raw.decode()


def records(path):
    return [json.loads(s) for s in read(path).splitlines() if s.strip()]


def csv_rows(path):
    return list(csv.DictReader(read(path).splitlines()))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def write_csv(name, rows):
    assert rows
    with (OUT / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def metadata():
    root = V.environment('SEMDEBT_EVAL_DIR')
    commit = V.git(root, 'rev-parse', 'eval-v1.2^{commit}').decode().strip()
    result = {}
    for name in ('cube_100.yaml', 'new.yaml'):
        raw = V.git(root, 'show', f'eval-v1.2:questions/{name}')
        SOURCES[f'$SEMDEBT_EVAL_DIR@{commit}/questions/{name}'] = {'sha256': V.sha(raw)}
        for q in yaml.safe_load(raw)['questions']:
            labels = q['labels']
            result[q['id']] = {'judge': q['scoring'] == 'judge',
                'low': bool(labels['low_discrimination']['criteria']), 'split': q['split'],
                'persona': labels['persona'], 'type': labels['complexity_source']['primary'],
                'complexity': labels['complexity_source']['items'],
                'dependency': labels['semantic_dependency']['items'], 'level': labels['q_level'],
                'coverage': q['summary_coverage']}
    assert len(result) == 122
    return result, commit


def supplement(run_id):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', run_id):
        raise ValueError('invalid run-id')
    target = ROOT / 'runs' / run_id
    if target.exists():
        raise FileExistsError('append-only runs: choose a new run-id')
    code = {name: V.sha((ROOT / name).read_bytes()) for name in
            (*V.CODE_FILES, 'reports/midterm/v3_data.py')}
    results, inputs = {}, {}
    with V.frozen_bank(V.environment('SEMDEBT_EVAL_DIR')) as (qs, columns, commit, archive):
        for cell in CELLS[1:3]:
            path = ROOT / 'runs' / T22 / f'{cell}.jsonl'
            source = V.Source(path, 'repo', path.read_bytes())
            inputs[str(path.relative_to(ROOT))] = V.sha(source.data)
            rows, other = V.rescore_source(source, qs, columns,
                V.environment('SEMDEBT_DATA_DIR') / 'runs-raw', run_id, commit)
            assert len(rows) == 327 and not other
            results[cell] = rows
    assert all(V.sha((ROOT / name).read_bytes()) == digest for name, digest in code.items())
    assert all(V.sha((ROOT / name).read_bytes()) == digest for name, digest in inputs.items())
    target.mkdir()
    for cell, rows in results.items():
        with (target / f'{T22}--{cell}.jsonl').open('x') as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    dump(target / 'manifest.json', {'eval_commit': commit, 'bank_archive_sha256': archive,
        'code_sha256': code, 'source_sha256': inputs, 'attempts': 654, 'cost_cny': 0})
    with (ROOT / 'runs/INDEX.md').open('a') as stream:
        stream.write(f'\n| {run_id} | 2026-10-25 | SQL-L1plus、SQL-L3a | T28 | 654（各109×3） | '
            '无模型调用 | eval-v1.2=90e13b3 | 0 | 沿用源运行 runs-raw | '
            'T28 免费补评；复用 scripts/rescore_t23.py，逐执行结果哈希核对；不执行查询；'
            'v2 主数字、v3 敏感性；新增判对待跨厂商复核。 |\n')
    print(f'{run_id}: 654 offline rescored attempts; cost 0', flush=True)


def load_units():
    units, versions = {}, {}
    for name, cell, runs, note in SPECS:
        pairs, vs = {}, {}
        for run in runs:
            path = ROOT / 'runs' / run / f'{cell}.jsonl'
            for n, r in enumerate(records(path), 1):
                assert r['status'] == 'done'
                key = r['qid'], r['rep']
                if key in pairs:
                    assert runs == A.L2E and key in {('Q80', 2), ('Q81', 1)}
                pairs[key] = {**r, 'source': f'{path.relative_to(ROOT)}:{n}'}
            origins = {r.get('rescored_from', {}).get('run_id', run)
                       for r in records(path)}
            assert len(origins) == 1
            origin = origins.pop()
            original = ROOT / 'runs' / origin / f'{cell}.jsonl'
            original_hash = V.sha(read(original).encode())
            folder = V3_NEW if cell in CELLS[1:3] else V3_OLD
            vp = ROOT / 'runs' / folder / f'{origin}--{cell}.jsonl'
            for r in records(vp):
                assert r['source_log_sha256'] == original_hash, (origin, cell)
                vs[r['qid'], r['rep']] = r
        assert pairs.keys() == vs.keys(), name
        for key, row in pairs.items():
            assert row['final']['outcome'] == vs[key]['final']['v2']['outcome'], (name, key)
        units[name], versions[name] = pairs, vs
    return units, versions


def hits(rows, qid):
    return sum(A.good(r) for (q, _), r in rows.items() if q == qid)


def accuracy(rows, ids, version=None):
    rs = [r for (q, _), r in rows.items() if q in ids]
    good = sum(r['final'][version]['outcome'] == 'correct' if version else A.good(r) for r in rs)
    return A.pct(good, len(rs))


def saved_execution(r):
    turn = r['turns'][-1]
    if turn['exec'].get('status') == 'refused':
        return '拒答', None
    if turn['exec'].get('error_class') == 'no_query':
        return '执行报错', None
    origin = r.get('rescored_from', {}).get('run_id', r['run_id'])
    relative = f"runs-raw/{origin}/{r['cell']}/{r['qid']}_r{r['rep']}_t{turn['turn']}.exec.json"
    path = V.environment('SEMDEBT_DATA_DIR') / relative
    raw = path.read_bytes()
    digest = V.sha(raw)
    assert digest == turn['exec']['exec_raw_sha256'], relative
    RAW['$SEMDEBT_DATA_DIR/' + relative] = digest
    payload = json.loads(raw)
    if payload['error'] is not None:
        return '执行报错', None
    columns = payload.get('columns') or []
    payload['rows'] = [[Decimal(value) if isinstance(value, str) and i < len(columns)
                        and columns[i].get('type') == 'number' else value
                        for i, value in enumerate(row)] for row in payload['rows']]
    return '结果', payload


def scalar(value):
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        number = Decimal(str(value))
        return ('number', str(number.normalize()))
    return ('null' if value is None else type(value).__name__, json.dumps(value, sort_keys=True))


def same_rows(left, right):
    """Exact multiset equality, ignoring row and column order, preserving duplicates.

    Column marginal signatures prune mappings; full row tuples prove each match.
    No scorer tolerance, projection, label normalization or aggregation is used.
    """
    if len(left) != len(right):
        return False
    if not left:
        return True
    if len(left[0]) != len(right[0]):
        return False
    a = [tuple(map(scalar, row)) for row in left]
    b = [tuple(map(scalar, row)) for row in right]
    width = len(a[0])
    sa = [Counter(row[i] for row in a) for i in range(width)]
    sb = [Counter(row[i] for row in b) for i in range(width)]
    options = [[j for j in range(width) if sa[i] == sb[j]] for i in range(width)]
    if any(not choices for choices in options):
        return False
    order = sorted(range(width), key=lambda i: len(options[i]))

    def search(mapping, used):
        if len(mapping) == width:
            return True
        i = order[len(mapping)]
        for j in options[i]:
            if j in used:
                continue
            new = mapping + [(i, j)]
            if Counter(tuple(row[x] for x, _ in new) for row in a) != Counter(
                    tuple(row[y] for _, y in new) for row in b):
                continue
            if search(new, used | {j}):
                return True
        return False
    return search([], set())


def auc(points):
    """P(score_wrong > score_correct), ties receive half credit."""
    groups = defaultdict(lambda: [0, 0])
    for score, wrong in points:
        groups[score][bool(wrong)] += 1
    positives = sum(v[1] for v in groups.values())
    negatives = sum(v[0] for v in groups.values())
    if not positives or not negatives:
        return None
    below, wins = 0, 0
    for _, (correct, wrong) in sorted(groups.items()):
        wins += wrong * (below + correct / 2)
        below += correct
    return wins / (positives * negatives)


def token_statistics(rows, ids, samples=10000):
    groups = {q: [(r['turns'][0]['usage']['reasoning_tokens'], not A.good(r))
                  for (qid, _), r in sorted(rows.items()) if qid == q] for q in sorted(ids)}
    assert all(len(v) == 3 for v in groups.values())
    points = list(itertools.chain.from_iterable(groups.values()))
    rng = random.Random(20261025)
    draws = [auc(list(itertools.chain.from_iterable(rng.choices(list(groups.values()), k=len(groups)))))
             for _ in range(samples)]
    valid = sorted(d for d in draws if d is not None)
    between = [(sum(s for s, _ in ps)/3, sum(w for _, w in ps)/3) for ps in groups.values()]
    mean_x, mean_y = [sum(p[i] for p in between)/len(between) for i in (0, 1)]
    cov = sum((x-mean_x)*(y-mean_y) for x, y in between)
    variance = math.sqrt(sum((x-mean_x)**2 for x, _ in between)*sum((y-mean_y)**2 for _, y in between))
    within = [auc(ps) for ps in groups.values() if any(w for _, w in ps) and not all(w for _, w in ps)]
    longest = [sum(w for s, w in ps if s == max(x for x, _ in ps)) /
               sum(s == max(x for x, _ in ps) for s, _ in ps) for ps in groups.values()]
    shortest = [sum(w for s, w in ps if s == min(x for x, _ in ps)) /
                sum(s == min(x for x, _ in ps) for s, _ in ps) for ps in groups.values()]
    return {'auc': auc(points), 'lo': valid[int(.025*len(valid))],
        'hi': valid[int(.975*len(valid))-1], 'draws': samples, 'valid': len(valid),
        'between_r': cov/variance if variance else None,
        'within_auc': sum(within)/len(within) if within else None, 'mixed': len(within),
        'longest_wrong': sum(longest)/len(longest), 'shortest_wrong': sum(shortest)/len(shortest),
        'wrong': sum(w for _, w in points)/len(points)}


def cost_inventory():
    text = read(ROOT / 'runs/INDEX.md')
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    selected, evidence = {}, defaultdict(list)
    for line in text.splitlines():
        if not line.startswith('| '):
            continue
        cells = [x.strip().replace('**', '') for x in line.split('|')[1:-1]]
        if len(cells) != 10 or not re.match(r'^2026\d{4}-', cells[0]):
            continue
        run = re.match(r'[A-Za-z0-9_.-]+', cells[0]).group()
        card, amount = cells[3], cells[7]
        evidence[run].append(amount)
        if 'rescore' in run or card == 'T28':
            continue
        if '不重复' in amount or '运行中' in amount or '结果待追加' in amount:
            continue
        if amount == '见报告':
            rs = records(ROOT / 'runs' / run / 'cache-probe.jsonl')
            value = sum(Decimal(str(r['cost_cny'])) for r in rs).quantize(Decimal('.00000001'))
            category = '日志核算（INDEX指向报告）'
        else:
            match = re.search(r'\d+(?:\.\d+)?', amount)
            if not match:
                raise ValueError(f'unresolved billed amount: {run}')
            value = Decimal(match.group())
            category = '估算' if '约' in amount else 'INDEX实记（含原有取整）'
        if run in selected:
            assert selected[run]['amount'] == str(value), run
        selected[run] = {'run': run, 'card': card, 'amount': str(value), 'category': category}
    # The final attribution entry has a separate six-column format.
    for line in text.splitlines():
        if not line.startswith('| 20261025-T22b-attrib-01 |'):
            continue
        cells = [x.strip() for x in line.split('|')[1:-1]]
        if len(cells) == 6 and '82/82' in cells[2]:
            value = Decimal(cells[4].split()[0])
            selected[cells[0]] = {'run': cells[0], 'card': 'T22b', 'amount': str(value),
                                    'category': 'INDEX实记'}
    assert '20261101-SQL-L1-01' not in selected
    assert '20261025-T22b-attrib-01' in selected
    return list(selected.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rescore-run')
    args = parser.parse_args()
    if args.rescore_run:
        supplement(args.rescore_run)
        return
    meta, commit = metadata()
    all_ids = {q for q, m in meta.items() if not m['judge']}
    main_ids = {q for q in all_ids if not meta[q]['low']}
    scopes = [('主表98', main_ids), ('附表109', all_ids)]
    assert (len(main_ids), len(all_ids)) == (98, 109)
    units, versions = load_units()
    for run in (V3_OLD, V3_NEW):
        manifest = json.loads(read(ROOT / 'runs' / run / 'manifest.json'))
        for name in V.CODE_FILES:
            assert V.sha((ROOT / name).read_bytes()) == manifest['code_sha256'][name], name
    for name, rows in units.items():
        ids = {q for q, _ in rows} & all_ids
        assert ids == (all_ids & {q for q in all_ids if meta[q]['split'] == 'heldout'} if name == 'SQL-L1-T4' else all_ids)
        assert all(sorted(r for q, r in rows if q == qid) == [1, 2, 3] for qid in ids)
        assert all(r['eval_commit'].startswith(commit[:7]) for r in rows.values())
    totals = {name: {label: accuracy(rows, ids) for label, ids in scopes} for name, rows in units.items()}
    lines = ['# T28 中期报告 v3 补数', '',
        f'复现：`{COMMAND}`。题库冻结标签 eval-v1.2=`{commit}`；费用0元；模型调用0、查询执行0。',
        '主数字用v2，v3仅为敏感性分析；主表98题、附表109题均排除judge，主表另排除低区分度。'
        '留出/调优沿用冻结split（主表49/49，附表55/54）。只公开题号、类别、单元、次数及汇总数字。',
        '每节表格与结论均由同一命令生成；来源文件哈希、逐作答来源及执行文件哈希见v3-sources.json、'
        'v3-attempts.csv。人工分类见v3-tuned-categories.csv；免费补评见runs/' + V3_NEW + '/。',
        '跨厂商验收尚未完成；第2、3、5、6、10项交协调会话独立重算，其余抽查。', '']

    def section(number, title, headers, rows, note, conclusion):
        lines.extend([f'## {number}. {title}', '', note, '', *A.table(headers, rows), '',
                      '结论：' + conclusion, '', f'复现：`{COMMAND}`。', ''])

    labels = csv_rows(OUT / 'v3-tuned-categories.csv')
    reviewed = {(r['unit'], r['qid'], int(r['rep'])): r['category'] for r in labels}
    expected = {(c, q, rep) for c in CELLS[-2:] for (q, rep), r in units[c].items()
                if q in main_ids and meta[q]['split'] == 'tuning' and not A.good(r)}
    assert len(reviewed) == len(labels) and set(reviewed) == expected
    assert all(label in CATEGORIES for label in reviewed.values())
    for c, q, rep in reviewed:
        saved_execution(units[c][q, rep])
    detail = [[c, q, rep, f'{hits(units[c], q)}/3', label]
              for (c, q, rep), label in sorted(reviewed.items(), key=lambda x:
                  (x[0][0], int(x[0][1][1:]), x[0][2]))]
    detail += [[c, '合计', sum(k[0] == c for k in reviewed), '—', cat + '：' + str(sum(
        k[0] == c and v == cat for k, v in reviewed.items()))] for c in CELLS[-2:] for cat in CATEGORIES]
    section(1, '调优题残余非正确作答', ['单元', '题号', '次数', '三次正确', '类别'], detail,
        '范围为主表49道调优题。Codex人工逐条比较最终查询、完整保存结果、全部参考与原系统要求；'
        '按T22b五类+单列归类，不调用模型。人工判断不是评分器改判；单列不进五类分母。'
        '标签只保留题号/次数/类别；不把同题其他单元的标签直接套用。',
        f'tuned剩{sum(k[0] == CELLS[-2] for k in reviewed)}次，tuned-instr剩{sum(k[0] == CELLS[-1] for k in reviewed)}次；单列疑点不自动转正。')

    table = []
    for label, ids in scopes:
        for persona in ('管理层', '分析师'):
            group = {q for q in ids if meta[q]['persona'] == persona}
            heldout = {q for q in group if meta[q]['split'] == 'heldout'}
            for c in CELLS:
                table.append([label, persona, len(group), len(heldout), c,
                              accuracy(units[c], group), accuracy(units[c], heldout)])
    section(2, '管理层与分析师', ['范围', '类别', '题数', '留出题数', '单元', '全体准确率', '留出准确率'], table,
        '定义按题库labels.persona：管理层=标为管理层使用场景的问题；分析师=标为分析师使用场景的问题。'
        '这是预先标注的使用者类别，不按本次得分、查询复杂度或职位重新推断。冻结标注未给更细的判别规则，'
        '不补造定义；两类互斥且覆盖全部题。', '两类分别保留原分母；主表管理层45题、分析师53题。')

    codex = {(r['qid'], int(r['rep'])): r['category'] for r in csv_rows(ROOT / 'reports/attribution/l1plus-codex.csv')}
    flash = {(r['qid'], r['rep']): r['labels']['category'] for r in records(
        ROOT / 'runs/20261025-T22b-attrib-01/attribution.jsonl')}
    assert codex.keys() == flash.keys() and len(codex) == 82
    expected_attribution = {key for key, r in units['SQL-L1plus'].items() if not A.good(r)}
    assert codex.keys() == expected_attribution
    read(ROOT / 'reports/attribution/l1plus-codebook.md')
    freeze = json.loads(read(ROOT / 'reports/attribution/l1plus-codex-freeze.json'))
    assert V.sha((ROOT / 'reports/attribution/l1plus-codex.csv').read_bytes()) == freeze['csv_sha256']
    overlap, leftover = [], []
    for label, ids in scopes:
        held = {q for q in ids if meta[q]['split'] == 'heldout'}
        for criterion, limit in [('至少错1次', 3), ('多数次答错', 2)]:
            selected = {q for q in held if hits(units['SQL-L1'], q) < limit}
            grid = Counter()
            for q in sorted(selected, key=lambda q: int(q[1:])):
                plus = hits(units['SQL-L1plus'], q) > hits(units['SQL-L1'], q)
                tuned = hits(units['SQL-L1-tuned'], q) > hits(units['SQL-L1'], q)
                grid[plus, tuned] += 1
                if not plus and not tuned:
                    cats = '；'.join(f'r{rep}:Codex={codex[q, rep]} / Flash={flash[q, rep]}'
                        for rep in (1, 2, 3) if (q, rep) in codex) or 'T22b无非正确作答标签'
                    leftover.append([label, criterion, q, cats])
            overlap.append([label, criterion, len(selected), grid[True, True], grid[True, False],
                            grid[False, True], grid[False, False]])
    section(3, '两条路的修复重叠', ['范围', 'L1筛选', '题数', '都修好', '仅L1plus', '仅tuned', '都没修好'], overlap,
        '只取留出题；修好=该题三次正确次数严格多于L1，不要求三次全对。tuned指SQL-L1-tuned，'
        '与带指令单元区分。旧口径L1多数次答错=0或1次正确；新口径=0、1或2次正确。',
        '放宽纳入范围后，四格仍按同一“正确次数增加”规则计算；未改善不等于一直答错。')
    lines.extend(['两条路都没修好的题及T22b既有类别（按次保留双方分歧）：', '',
                  *A.table(['范围', '筛选', '题号', '类别'], leftover), ''])

    always, always_detail = [], []
    for name, rows in units.items():
        classifications = {}
        for q in sorted({q for q, _ in rows} & all_ids):
            if hits(rows, q):
                continue
            evidence = [saved_execution(rows[q, rep]) for rep in (1, 2, 3)]
            if any(status == '执行报错' for status, _ in evidence):
                cat = '含执行报错'
            elif any(status == '拒答' for status, _ in evidence):
                cat = '含拒答'
            else:
                results = [payload['rows'] for _, payload in evidence]
                cat = '三次行集相同' if same_rows(results[0], results[1]) and same_rows(results[0], results[2]) else '三次行集不全相同'
            classifications[q] = cat
            always_detail.append({'unit': name, 'qid': q, 'category': cat})
        for label, ids in scopes:
            cs = Counter(cat for q, cat in classifications.items() if q in ids)
            actual_scope = label + '的留出子集' if name == 'SQL-L1-T4' else label
            always.append([name, actual_scope, sum(cs.values()), *[cs[k] for k in
                ('三次行集相同', '三次行集不全相同', '含执行报错', '含拒答')]])
    write_csv('v3-always-wrong.csv', always_detail)
    section(4, '三次全错的结果稳定性', ['单元', '范围', '三次全错', '行集相同', '行集不全相同', '含执行报错', '含拒答'], always,
        '非正确包括wrong、exec_error、refused。逐题比较最后一轮完整执行行集：忽略行序和列序、保留重复行，'
        '数值只规范等值表示，不用容差、不删列、不合并标签。报错优先单列，其余拒答再单列。'
        '行集不相同可由取值、投影或数值浮点差别造成，不据此断言业务错因不同；行集相同也不证明推理相同。'
        '逐题类别见v3-always-wrong.csv；旧版单元及T4子集明确单列。',
        '该表衡量三次全错的输出一致性，不能把一致性当准确率。')

    token_rows, thresholds, token_evidence = [], [], {}
    for c in ('SQL-L1', 'SQL-L1plus'):
        for label, ids in scopes:
            stats = token_statistics(units[c], ids)
            token_evidence[c + '/' + label] = stats
            token_rows.append([c, label, f"{stats['auc']:.3f}", f"[{stats['lo']:.3f}, {stats['hi']:.3f}]",
                f"{stats['between_r']:.3f}", stats['mixed'], f"{stats['within_auc']:.3f}",
                f"{stats['longest_wrong']:.1%}", f"{stats['shortest_wrong']:.1%}", f"{stats['wrong']:.1%}"])
            ranked = sorted((r for (q, _), r in units[c].items() if q in ids), key=lambda r:
                (-r['turns'][0]['usage']['reasoning_tokens'], int(r['qid'][1:]), r['rep']))
            for fraction in (.1, .2, .3):
                count = math.ceil(len(ranked) * fraction)
                removed, kept = ranked[:count], ranked[count:]
                thresholds.append([c, label, f'{fraction:.0%}', count,
                    ranked[count-1]['turns'][0]['usage']['reasoning_tokens'],
                    A.pct(sum(A.good(r) for r in kept), len(kept)),
                    A.pct(sum(not A.good(r) for r in removed), len(removed))])
    section(5, '首轮思考token信号', ['单元', '范围', 'AUC', '按题95%区间', '题间r', '不稳定题', '题内AUC', '最长次错率', '最短次错率', '全部错率'], token_rows,
        '不对为正类，首轮reasoning_tokens越大越预测不对。按题有放回抽样10000次（种子20261025），'
        '同题三次一起抽；百分位95%区间。题间r=每题平均token与三次错率的Pearson相关；'
        '题内AUC=在同一不稳定题内比较错次/对次token的胜率，再对题等权平均，平手记0.5。'
        '最长/最短次错率对全部题等权，token并列时取并列次数的平均错率；不是独立样本推断。',
        f"L1主表AUC复现为{token_evidence['SQL-L1/主表98']['auc']:.3f}；题间与题内信号分别报告，不能用总体AUC代替同题判断。")
    lines.extend(['门槛表（事后描述，未验证上线阈值）：去除数向上取整；边界并列按题号数值、rep排序，'
                  '因此token切点并不独自定义全部被去除项。', '',
                  *A.table(['单元', '范围', '去除比例', '去除次数', '边界token', '剩余准确率', '去除中错答占比'], thresholds), ''])

    relaxed = []
    for label, ids in scopes:
        for c in CELLS[1:3]:
            agree = {key for key in codex if codex[key] == flash[key] == '只是呈现不同' and key[0] in ids}
            correct = sum(A.good(r) for (q, _), r in units[c].items() if q in ids)
            bound = A.pct(correct + len(agree), 3*len(ids)) if c == 'SQL-L1plus' else '缺少双方归因，无法计算'
            relaxed.append([c, label, accuracy(units[c], ids), accuracy(versions[c], ids, 'v3'),
                            len(agree) if c == 'SQL-L1plus' else '—', bound])
    section(6, '宽松评分与归因上界', ['单元', '范围', 'v2', 'v3', '双方呈现次数', '归因上界（基于v2）'], relaxed,
        'v3复用既有P1–P4评分器，654条补评写新run，逐原始执行结果SHA256核对。'
        '归因上界只把T22b双方同次均标“只是呈现不同”的v2非正确作答转正；不与v3增益叠加。'
        '上界为人工/模型归因判断，不是评分器结果。用户已确认L3a不套用L1plus标签。',
        '两种宽松数字口径不同，分别展示；L3a上界缺少双方归因，无法计算。')

    tool_summary, tool_detail, flow_detail = [], [], []
    mapping = {'聚合或候选答案核验': '先把答案算一遍（形态代理）',
               '枚举或分组查值': '查枚举值', '明细或样例查值': '查明细样例'}
    for agent, direct in [('SQL-L0-E', 'SQL-L0'), ('SQL-L1-E', 'SQL-L1'), ('SQL-L2-E', 'SQL-L2')]:
        for (q, rep), r in units[agent].items():
            for step in r['steps']:
                for call in step['tool_calls']:
                    if call['name'] == 'run_sql':
                        old = A.purpose(call.get('query'))
                        tool_detail.append({'unit': agent, 'qid': q, 'rep': rep, 'call': step['call'],
                            'k': call['k'], 'category': mapping.get(old, '其他'), 't24_category': old,
                            'source': r['source']})
        for label, ids in scopes:
            cs = Counter(r['category'] for r in tool_detail if r['unit'] == agent and r['qid'] in ids)
            changes = Counter()
            for (q, rep), r in units[agent].items():
                if q not in ids:
                    continue
                a, b = A.good(units[direct][q, rep]), A.good(r)
                if a != b:
                    category = '由对变错' if a else '由错变对'
                    mixed = 0 < hits(units[direct], q) < 3
                    changes[category] += 1
                    changes[category + '不稳定'] += mixed
                    flow_detail.append({'unit': agent, 'scope': label, 'qid': q, 'rep': rep,
                        'category': category, 'direct_stability': '时对时错' if mixed else '全对或全错'})
            tool_summary.append([agent, label, sum(cs.values()), *[cs[k] for k in
                ('查明细样例', '查枚举值', '先把答案算一遍（形态代理）', '其他')],
                changes['由错变对'], changes['由对变错'],
                changes['由错变对不稳定'], changes['由对变错不稳定']])
    write_csv('v3-tools.csv', tool_detail)
    write_csv('v3-flips.csv', flow_detail)
    section(7, 'agent查库用途与配对翻转', ['单元', '范围', '调用', '明细样例', '枚举', '答案计算代理', '其他', '错→对', '对→错', '错→对中直答不稳', '对→错中直答不稳'], tool_summary,
        '沿用T24优先级：结构/计划→聚合/排名→DISTINCT/GROUP BY→COUNT行数→明细；'
        '本表将结构/计划、行数检查、空查询合入其他。包含执行失败、拒绝、超限的尝试；'
        '“先算答案”只是SQL形态代理，不能验证模型用途。错指所有非正确结果。'
        '同题同rep配对，描述性比较，不认为两次采样是相同随机种子的反事实。L2-E保留既定续跑替代规则。',
        '逐档列调用和双向翻转；翻转落在直答不稳定题上的次数另列，不能仅由净提升推断探查有效。')

    confidence = records(ROOT / 'runs/20261023-T19c-confidence-01/confidence.jsonl')
    cross = []
    for label, ids in scopes:
        groups = defaultdict(list)
        for r in confidence:
            q = r['qid']
            if q in ids:
                h = hits(units['SQL-L1'], q)
                stability = '全对' if h == 3 else '全错' if h == 0 else '时对时错'
                groups[r.get('tier') or '未解析', meta[q]['type'], stability].append(units['SQL-L1'][q, r['rep']])
        for key, rs in sorted(groups.items()):
            cross.append([label, *key, len(rs), sum(A.good(r) for r in rs), sum(not A.good(r) for r in rs)])
    section(8, '自评把握 × 题型 × 稳定性', ['范围', '自评', '题型', '稳定性', '次数', '正确', '非正确'], cross,
        'A=肯定对，B=大概对，C=没底；未解析单列。题型取冻结complexity_source.primary，'
        '稳定性取SQL-L1的v2三次结果。只使用T19c已有自评，不新增追问、不更改冻结判定。',
        'A档错答仍集中于全错或不稳定题；三轴联合统计保留各档分母及未解析项。')

    coverage = []
    new = {q for q in meta if 101 <= int(q[1:]) <= 122}
    assert len(new) == 22
    axes = {'复杂度覆盖': 'complexity', '语义依赖覆盖': 'dependency', '主复杂度': 'type',
            'Q级': 'level', '用户类别': 'persona', '汇总层覆盖': 'coverage'}
    for label, ids in [('新增22题全部', new), ('主表新增子集', new & main_ids), ('附表新增子集', new & all_ids)]:
        for axis, field in axes.items():
            counts = Counter()
            for q in ids:
                value = meta[q][field]
                counts.update(value if isinstance(value, list) else [str(value)])
            coverage.extend([label, axis, cat, n] for cat, n in sorted(counts.items()))
    section(9, '新增22题的覆盖类别', ['范围', '标注轴', '类别', '题数'], coverage,
        '范围为Q101–Q122，按冻结题库labels及summary_coverage计数。复杂度/语义依赖items为多标签，'
        '同题可计入多类，不能把这些计数相加当题数。这里描述新增题覆盖，不声称所有类别在原100题中从未出现。',
        '新增题的覆盖按已有标注报告；judge与低区分度剔除后的新增子集另列，避免混用22与主表分母。')

    costs = cost_inventory()
    write_csv('v3-cost-runs.csv', costs)
    by_card = defaultdict(Decimal)
    for r in costs:
        by_card[r['card']] += Decimal(r['amount'])
    total = sum(by_card.values())
    cost_rows = [[card, sum(r['card'] == card for r in costs), f'{value:.2f}'] for card, value in sorted(by_card.items())]
    cost_rows.append(['合计', len(costs), f'{total:.2f}'])
    section(10, '本期全部付费运行费用', ['卡', '付费run数', '元（按记录约值）'], cost_rows,
        '按INDEX逐run汇总，包含冒烟、缓存、试跑、失败、旧版及归因，不仅是准确率主表。'
        '同run的启动/完成/补记不重复相加；忽略HTML注释里的示例行；预算不是实际费用。'
        'T12缓存行“见报告”改由既有cache-probe.jsonl实记cost_cny核算。C13中止run约0.014元是原有估算，'
        '其余多处金额仅保留INDEX原有取整精度；总和不是提供商账单精度。'
        'T22b已返回响应费用与归因计入；run02未返回在途用量无法本地确认，不将其算作0元。',
        f'已记录合计约{total:.2f}元，含原有估算/取整；未确认在途用量仍为未知，不能声称最终账单总额。')

    parallel = []
    for name, rows in units.items():
        note = next(note for n, _, _, note in SPECS if n == name)
        for label, ids in scopes:
            n = len({q for q, _ in rows} & ids)
            parallel.append([name, label, n, accuracy(rows, ids), accuracy(versions[name], ids, 'v3'), note])
    section(11, '全部单元v2 / v3并排', ['单元', '范围', '实际题数', 'v2', 'v3', '版本类别'], parallel,
        '正式单元按T24的定稿来源加T14/T22b；旧L1.5S、旧SQL-L2说明单列。'
        'C13 T4实际仅49/55题，不冒充98/109题。其余v3沿用T23-v3-02；'
        'T22b使用本卡654条补评，各条v2均与既有最终日志核对。',
        'v2继续作为主数字；新增v3判对仍待Claude Code跨厂商复核。')

    attempts = [{'unit': c, 'qid': q, 'rep': rep, 'category': r['final']['outcome'],
                 'source': r['source']} for c, rows in units.items() for (q, rep), r in sorted(rows.items())]
    write_csv('v3-attempts.csv', attempts)
    read(Path(__file__))
    for name in ('reports/midterm/analyze.py', *V.CODE_FILES):
        read(ROOT / name)
    for path, expected_hash in list(SOURCES.items()):
        if not path.startswith('$'):
            assert V.sha((ROOT / path).read_bytes()) == expected_hash['sha256'], path
    (OUT / 'v3-data.md').write_text('\n'.join(lines).rstrip() + '\n')
    dump(OUT / 'v3-sources.json', {'eval_commit': commit, 'sources': SOURCES,
        'raw_execution_sha256': RAW, 'bootstrap': {'seed': 20261025, 'samples': 10000},
        'token_statistics': token_evidence, 'unit_accuracy_v2': totals,
        'fees_recorded_cny': str(total), 'paid_model_calls': 0, 'query_executions': 0})
    print(f'T28: {len(units)} unit versions, {len(attempts)} attempts, {len(RAW)} verified execution files; assertions passed.')


if __name__ == '__main__':
    main()
