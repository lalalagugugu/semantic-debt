"""Offline eval-v1.3 delivery/content audit; no model or query execution.

uv run --offline python scripts/t31_v4_recompute.py --run-id <new-id>
Only append new runs. Raw material stays in SEMDEBT_DATA_DIR.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from itertools import combinations
import json
import math
import os
from pathlib import Path
import random
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness import scorer_v2 as V2
from scripts.rescore_t23 import frozen_bank, git, saved_turn, sha
from scripts.t31_candidate_scan import RULES, correct, numeric_null_needs_ruling, variants
from scripts.t31_residual_sample import STRATA

TAG = 'eval-v1.3'
COMMIT = '5b65e0c450ba36d83707c00dc9443be16b08d086'
VALID = {'correct', 'wrong', 'exec_error', 'refused'}


def read_csv(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def identity(r):
    return r['source_run'], r['cell'], r['qid'], int(r['rep'])


def residual(r):
    return r['v2_outcome'] == 'wrong' and r['has_result'] and not r['rules']


def approved_rules(candidate, cc, q, columns):
    hits = []
    if not isinstance(candidate, list) or not cc:
        return hits
    for code in RULES:
        for i, ref in enumerate(q.refs):
            m = q.ref_rules[i] if q.ref_rules and q.ref_rules[i] is not None else q.rules
            if any(correct(c, r, rule) for c, r, rule in
                   variants(code, candidate, ref, m, cc, columns[i], q.text)):
                # Strict numeric NULL policy; never replace an unknown amount with zero.
                if not any(numeric_null_needs_ruling(candidate, other,
                           q.ref_rules[j] if q.ref_rules and q.ref_rules[j] is not None else q.rules, cc)
                           for j, other in enumerate(q.refs)):
                    hits.append(code)
                break
    return hits


def discover(roots):
    found = {}
    for root in roots:
        for p in sorted((root / 'runs').glob('*/*.jsonl')):
            if 'rescore' in p.parent.name or not p.name.startswith(('SQL-', 'JSON-', 'DAX-')):
                continue
            raw = p.read_bytes()
            k = p.parent.name, p.stem
            if k in found:
                old = found[k][1]
                if old.startswith(raw):
                    continue
                if not raw.startswith(old):
                    raise ValueError(f'divergent original logs: {k}')
            found[k] = p, raw
    return found


def reuse_scores(directory, sources, data):
    """Reuse scoring only after verifying frozen scorer and all original inputs."""
    manifest = json.loads((directory/'manifest.json').read_text())
    assert manifest['eval_commit'] == COMMIT
    for file in ('harness/scorer_v2.py', 'harness/scorer_v3.py',
                 'scripts/t31_candidate_scan.py', 'scripts/rescore_t23.py'):
        assert manifest['inputs'][file] == sha((ROOT/file).read_bytes())
    expected = {(r['source_run'],r['cell']):r['sha256'] for r in manifest['source_logs']}
    assert expected == {k:sha(raw) for k, (_,raw) in sources.items()}
    rows = [json.loads(line) for p in sorted(directory.glob('*.jsonl'))
            for line in p.read_text().splitlines()]
    assert len(rows) == manifest['attempts']
    for r in rows:
        _, source = sources[r['source_run'],r['cell']]
        matches = [json.loads(line) for line in source.splitlines()
                   if sha(line) == r['source_record_sha256']]
        assert len(matches) == 1
        original = matches[0]
        _, _, digest = saved_turn(original['turns'][-1], data/'runs-raw'/r['source_run']/r['cell'],
                                  r['qid'],r['rep'])
        assert digest == r['exec_sha256']
        assert r['content_lower'] == r['a']+r['b'] >= r['a']
    return rows, manifest['exclusions'], manifest['source_logs']


def rescore(sources, qs, columns, data, persona):
    rows, exclusions, manifest = [], Counter(), []
    for (run, cell), (path, raw) in sorted(sources.items()):
        digest = sha(raw)
        counts = Counter()
        seen = set()
        for line in raw.splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get('status') != 'done':
                counts['status:' + rec.get('status', 'missing')] += 1
                continue
            if 'turns' not in rec or 'qid' not in rec:
                counts['not_answer_record'] += 1
                continue
            qid, rep = rec['qid'], rec['rep']
            if (qid, rep) in seen:
                raise ValueError(f'duplicate done attempt: {run}/{cell}/{qid}/{rep}')
            seen.add((qid, rep))
            if qid not in qs or qs[qid].scoring != 'deterministic':
                counts['not_deterministic'] += 1
                continue
            q = qs[qid]
            if rec.get('question_sha256') != sha(q.text.encode()):
                counts['changed_or_missing_question_hash'] += 1
                continue
            c, cc, execution = saved_turn(rec['turns'][-1], data / 'runs-raw' / run / cell, qid, rep)
            outcome = V2.score_detailed(c, q.refs, q.rules, reference_rules=q.ref_rules).outcome
            if outcome not in VALID:
                raise ValueError(f'no v2 verdict: {run}/{cell}/{qid}/{rep}: {outcome}')
            rules = approved_rules(c, cc, q, columns[qid]) if outcome == 'wrong' else []
            r = dict(source_run=run, cell=cell, qid=qid, rep=rep, v2_outcome=outcome,
                     a=int(outcome == 'correct'), b=int(bool(rules)), rules=rules,
                     content_lower=int(outcome == 'correct' or bool(rules)), has_result=isinstance(c, list),
                     low=bool(q.meta['low_discrimination']), q_level=q.meta['q_level'],
                     persona=persona[qid], split=q.meta['split'],
                     stratum=STRATA.get((run, cell)), source_log_sha256=digest,
                     source_record_sha256=sha(line), exec_sha256=execution,
                     historical_outcome=rec.get('final', {}).get('outcome'))
            assert r['content_lower'] == r['a'] + r['b'] >= r['a']
            rows.append(r)
            counts['eligible'] += 1
        exclusions.update({k: v for k, v in counts.items() if k != 'eligible'})
        manifest.append(dict(source_run=run, cell=cell, sha256=digest, counts=dict(counts)))
        print(f'{run}/{cell}: {counts["eligible"]} eligible', flush=True)
    assert len({identity(r) for r in rows}) == len(rows)
    return rows, dict(exclusions), manifest


def sample_update(rows, samples, labels):
    indexed = {identity(r): r for r in rows}
    labelmap = {identity(r): r['label'] for r in labels}
    assert len(samples) == len(labels) == len(labelmap) == 200
    assert {identity(r) for r in samples} == set(labelmap)
    assert set(labelmap.values()) <= {'内容正确', '内容错误'}
    out = []
    for s in samples:
        k = identity(s)
        r = indexed[k]
        assert r['stratum'] == s['stratum'] and not r['low']
        state = 'retained' if residual(r) else 'v2_pass' if r['a'] else 'rule_pass' if r['b'] else 'no_result'
        assert state != 'no_result', 'previous sample result disappeared'
        out.append(dict(stratum=s['stratum'], source_run=k[0], cell=k[1], qid=k[2], rep=k[3],
                        label=labelmap[k], state=state))
    return out


def canonical_formal(rows):
    """Later L2-E completion replaces the earlier transport-error attempt."""
    latest = {}
    for r in sorted(rows, key=lambda r: r['source_run']):
        if r['stratum']:
            key = r['stratum'], r['qid'], r['rep']
            if key in latest:
                old = latest[key]
                assert old['cell'] == 'SQL-L2-E' and not old['has_result']
                old['stratum'] = None
                old['superseded_in_formal'] = True
            latest[key] = r
    return rows


def mark_known_errors(rows, approved):
    """User-approved certainty stratum; no question-specific scoring branches."""
    keys = {identity(r) for r in approved}
    assert len(keys) == len(approved)
    found = set()
    for r in rows:
        r['known_content_error'] = identity(r) in keys
        if r['known_content_error']:
            assert residual(r) and r['stratum'] and not r['low']
            assert r['content_lower'] == 0
            found.add(identity(r))
    assert found == keys, 'approved certainty cases must still be formal residuals'
    return rows


def hypergeom_interval(N, n, x, alpha=.05):
    """Equal-tail exact finite-population CI for the number of accepted residuals.

Hypergeometric inversion includes the finite population correction intrinsically;
works for x=0/n and census samples, unlike a degenerate Wald interval.
"""
    if N == 0:
        return 0, 0
    if not 0 < n <= N or not 0 <= x <= n:
        raise ValueError('invalid finite-population sample')
    denom = math.comb(N, n)

    def tail(K, upper):
        lo, hi = max(0, n - (N-K)), min(n, K)
        values = range(max(lo, x), hi+1) if upper else range(lo, min(hi, x)+1)
        return sum(math.comb(K, j)*math.comb(N-K, n-j) for j in values)/denom

    valid = [K for K in range(x, N-n+x+1)
             if tail(K, True) >= alpha/2 and tail(K, False) >= alpha/2]
    return min(valid), max(valid)


def estimate(N, sample):
    if not N:
        assert not sample, 'sample cannot exceed an empty residual population'
        return dict(n=0, x=0, c=0., c_lo=0., c_hi=0., p=0.)
    n, x = len(sample), sum(s['label'] == '内容正确' for s in sample)
    if n == 0:
        return dict(n=0, x=0, c=None, c_lo=None, c_hi=None, p=None)
    lo, hi = hypergeom_interval(N, n, x)
    return dict(n=n, x=x, c=N*x/n, c_lo=lo, c_hi=hi, p=x/n)


def summaries(rows, samples):
    out = []
    strata = sorted({r['stratum'] for r in rows if r['stratum']})
    historical = sorted({(r['source_run'], r['cell']) for r in rows})
    groups = [('formal', s, [r for r in rows if r['stratum'] == s]) for s in strata]
    groups += [('historical', run+'/'+cell, [r for r in rows if (r['source_run'], r['cell']) == (run, cell)])
               for run, cell in historical]
    for kind, cell, pool in groups:
        for scope in ('main98', 'all109'):
            base = [r for r in pool if scope == 'all109' or not r['low']]
            for dimension, values in [('all', ['all']), ('q_level', ['Q1', 'Q2', 'Q3']),
                                      ('persona', ['管理层', '分析师']), ('split', ['tuning', 'heldout'])]:
                for value in values:
                    selected = [r for r in base if dimension == 'all' or r[dimension] == value]
                    if not selected:
                        continue
                    ids = {identity(r) for r in selected}
                    a, b, total = sum(r['a'] for r in selected), sum(r['b'] for r in selected), len(selected)
                    eligible = [r for r in selected if residual(r)]
                    certain = [r for r in eligible if r.get('known_content_error')]
                    covered = [r for r in eligible if not r['low'] and r['stratum']
                               and not r.get('known_content_error')]
                    ss = [s for s in samples if identity(s) in ids and s['state'] == 'retained']
                    e = estimate(len(covered), ss) if kind == 'formal' else dict(n=0,x=0,c=None,c_lo=None,c_hi=None,p=None)
                    uncovered = len(eligible)-len(covered)-len(certain) if kind == 'formal' else len(eligible)
                    # all109 has no point estimate; show partial-identification bounds instead.
                    can_estimate = kind == 'formal' and scope == 'main98' and e['c'] is not None
                    lo_bound = (a+b+e['c'])/total if kind == 'formal' and e['c'] is not None else None
                    hi_bound = (a+b+e['c']+uncovered)/total if lo_bound is not None else None
                    out.append(dict(kind=kind, cell=cell, scope=scope, dimension=dimension, group=value,
                        questions=len({r['qid'] for r in selected}), attempts=total, a=a, b=b,
                        delivery=a/total, lower=(a+b)/total, residual=len(eligible),
                        covered_residual=len(covered), known_errors=len(certain), uncovered_residual=uncovered,
                        sample_n=e['n'], sample_correct=e['x'],
                        c=e['c'] if can_estimate else None,
                        estimate=(a+b+e['c'])/total if can_estimate else None,
                        lo=(a+b+e['c_lo'])/total if can_estimate else None,
                        hi=(a+b+e['c_hi'])/total if can_estimate else None,
                        uncovered_zero=lo_bound if scope == 'all109' else None,
                        uncovered_all=hi_bound if scope == 'all109' else None,
                        boundary_lo=(a+b+e['c_lo'])/total if scope == 'all109' and lo_bound is not None else None,
                        boundary_hi=(a+b+e['c_hi']+uncovered)/total if scope == 'all109' and lo_bound is not None else None))
                    assert a+b >= a
    return out


def paired_interval(differences, B=5000, seed=0):
    if not differences:
        return None, None, None
    rng = random.Random(seed)
    n = len(differences)
    boot = sorted(sum(rng.choice(differences) for _ in range(n))/n for _ in range(B))
    # Match explorer_report.py / t30_combo_report.py, including endpoint indices.
    return tuple(0. if abs(x) < 1e-12 else x for x in
                 (sum(differences)/n, boot[int(.025*B)], boot[int(.975*B)-1]))


def robustness(d, c):
    if d[0]*c[0] < 0:
        return '依赖交付口径'
    if (d[0] > 0)-(d[0] < 0) != (c[0] > 0)-(c[0] < 0):
        return '强弱依口径而定'
    return '稳健' if (d[1] <= 0 <= d[2]) == (c[1] <= 0 <= c[2]) else '强弱依口径而定'


def comparisons(rows, samples, include_estimate=True):
    cells = sorted(set(STRATA.values()))
    core = ['SQL-L0', 'SQL-R', 'SQL-L1', 'SQL-L1c', 'SQL-L1.5W', 'SQL-L1.5S', 'SQL-L2', 'JSON-L2']
    pairs = set(combinations(core, 2))
    pairs.update((a, a+'-E') for a in ('SQL-L0','SQL-L1','SQL-L2'))
    pairs.update([('SQL-L1','SQL-L1plus'),('SQL-L1plus','SQL-L3a'),
        ('SQL-L1','SQL-L1-tuned'),('SQL-L1','SQL-L1-tuned-instr'),
        ('SQL-L1-tuned','SQL-L1-tuned-instr'),('SQL-L1plus','SQL-L1plus-tuned-instr')])
    # Include the instruction ladder, beyond the minimum preregistered list.
    pairs.update(combinations(['SQL-L1','SQL-L1-T2','SQL-L1-T3','SQL-L1-T4'],2))
    rates = {}
    for cell in cells:
        pool = [r for r in rows if r['stratum'] == cell and not r['low'] and residual(r)
                and not r.get('known_content_error')]
        ss = [s for s in samples if s['stratum'] == cell and s['state'] == 'retained']
        rates[cell] = estimate(len(pool), ss)['p']
    out = []
    for scope in ('main98','all109'):
        for split in ('all','tuning','heldout'):
            stats = defaultdict(lambda: defaultdict(list))
            for r in rows:
                if r['stratum'] and (scope == 'all109' or not r['low']) and (split == 'all' or r['split'] == split):
                    p = rates[r['stratum']]
                    sens = r['content_lower'] + (p if residual(r) and p is not None
                                                and not r.get('known_content_error') else 0)
                    stats[r['stratum']][r['qid']].append((r['a'], r['content_lower'], sens))
            for left, right in sorted(pairs):
                ids = sorted(set(stats[left]) & set(stats[right]))
                if not ids:
                    continue
                intervals = []
                for i in range(3):
                    diffs = [sum(x[i] for x in stats[right][q])/len(stats[right][q])
                             -sum(x[i] for x in stats[left][q])/len(stats[left][q]) for q in ids]
                    intervals.append(paired_interval(diffs))
                # c has no coverage of the eleven low-discrimination questions.
                sensitivity = include_estimate and scope == 'main98' and rates[left] is not None and rates[right] is not None
                r = dict(left=left,right=right,scope=scope,split=split,questions=len(ids),
                         label=robustness(intervals[0], intervals[1]))
                for prefix, triple in zip(('delivery','lower','sensitivity'),intervals):
                    for suffix, v in zip(('delta','lo','hi'),triple):
                        r[prefix+'_'+suffix] = v if prefix != 'sensitivity' or sensitivity else None
                r['sensitivity_label'] = robustness(intervals[0], intervals[2]) if sensitivity else '不可估计'
                out.append(r)
    return out


def t29_summary(rows, root):
    """Keep the historical answer decisions; only re-evaluate their correctness."""
    from scripts.t29_consistency_report import consistent
    data = Path(os.environ['SEMDEBT_DATA_DIR'])
    base = [r for r in rows if r['stratum'] == 'SQL-L1plus']
    pilot = set(json.loads((root/'reports/validation/t29-pilot-preflight.json').read_text())['pilot_qids'])
    out = []

    def emit(name, pool, answered):
        for scope in ('observed','main98','all109','tuning20','heldout49'):
            selected = [r for r in pool if scope in ('observed','all109') or
                        scope == 'main98' and not r['low'] or scope == 'tuning20' and r['qid'] in pilot or
                        scope == 'heldout49' and not r['low'] and r['split'] == 'heldout']
            if not selected:
                continue
            kept = [r for r in selected if answered[identity(r)]]
            qs = {r['qid'] for r in selected}
            for metric, key in [('delivery','a'),('accuracy_lower','content_lower')]:
                baseline = [r for r in base if r['qid'] in qs]
                value = sum(r[key] for r in kept)
                out.append(dict(cell=name,scope=scope,metric=metric,attempts=len(selected),answered=len(kept),
                    answer_rate=len(kept)/len(selected),correct_answered=value,
                    accuracy_answered=value/len(kept) if kept else None,
                    baseline=sum(r[key] for r in baseline)/len(baseline) if baseline else None,c='不可估计'))

    for (run, cell) in sorted({(r['source_run'],r['cell']) for r in rows if '-T29-' in r['source_run']}):
        pool = [r for r in rows if (r['source_run'],r['cell']) == (run,cell)]
        if cell.endswith('-confidence'):
            categories = { (r['qid'],int(r['rep'])): r['confidence_category'] for r in
                          read_csv(root/'reports/validation/t29-expanded-attempts.csv') if r['cell'] == cell}
            for gate, allowed in [(50,{'ge90','75_to_90','50_to_75'}),(75,{'ge90','75_to_90'}),(90,{'ge90'})]:
                emit(cell+f'-ge{gate}',pool,{identity(r):categories[r['qid'],r['rep']] in allowed for r in pool})
        else:
            emit(cell,pool,{identity(r):r['v2_outcome'] != 'refused' for r in pool})
    by_q = defaultdict(list)
    for r in base:
        by_q[r['qid']].append(r)
    pool, answered = [], {}
    for qid, reps in by_q.items():
        assert {r['rep'] for r in reps} == {1,2,3}
        payloads = []
        for r in sorted(reps,key=lambda r:r['rep']):
            if r['exec_sha256'] is None or not r['has_result']:
                payloads.append(None)
                continue
            directory = data/'runs-raw'/r['source_run']/r['cell']
            matches = [p for p in directory.glob(f'{qid}_r{r["rep"]}_t*.exec.json') if sha(p.read_bytes()) == r['exec_sha256']]
            assert len(matches) == 1
            payloads.append(json.loads(matches[0].read_bytes()))
        r = next(r for r in reps if r['rep'] == 1)
        pool.append(r)
        answered[identity(r)] = consistent(payloads) == 'consistent'
    emit('SQL-L1plus-three-consistent',pool,answered)
    return out


def write_csv(path, rows):
    if not rows:
        raise ValueError(f'empty output: {path.name}')
    with path.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def percent(v):
    return '不可估计' if v is None else f'{100*v:.1f}%'


def report(summary, comps, t29, manifest, sample, run_id):
    lines=['# v4 双口径离线重评（待跨厂商独立核对）','',
        '**本文件是核对交接稿。Claude Code 从原始日志独立重算通过前，不将本轮数字纳入正式报告。**','',
        '## 方法与局限','',
        f'题库固定 `{TAG} = {COMMIT}`；题库 PR #22、主仓库 PR #199 已合并。评分器 v2、冻结语义、系统提示及历史日志均未修改。新 run：`{run_id}`。模型调用、SQL 执行、费用均为 0。',
        '依据：`decisions/2026-10-26-accuracy-vs-delivery.md`、`decisions/2026-10-26-instruction-following-hypotheses.md`第三节、`decisions/2026-10-28-residual-content-principles.md`、`decisions/2026-10-28-reference-rulings-five-questions.md`；规则独立复核见 `reports/validation/t31-v4-claude-review.*`。Claude最终标签为74次内容正确、126次内容错误；与Codex按裁定转换后200/200一致的证据见Claude复核报告，原Codex CSV保留原始三标签，不覆盖它。',
        '按约定交付率 a 为 v2 在新参考下的判对次数；b 为 v2 判错、经已审定 R1–R11 放行的次数（并集，不重复计数）。准确率确定下限为 (a+b)/N；逐次及各汇总断言 a+b≥a。Q30 新参考可撤销旧版本的判对，此处单调性相对于 eval-v1.3 的 v2。',
        'c 只估计主表 98 题内19个正式单元已有作答。残余总体为 v2 判错、有执行结果且未被规则放行。原样本中已变成 a 或 b 的条目移出；其余使用 Claude 最终标签。15次框外已知错误按用户本轮裁定单列：Q30有14次、Q96有1次，c贡献固定为0；公共身份清单为 `reports/validation/t31-v4-certain-errors.csv`。每单元 c=M×x/n，其中 M 是总残余扣除已知错误后的可抽样总体。总残余、已知错误、M、n、x 均逐项公开。原抽样在单元内等概率，条件于仍属可抽样残余后仍为简单随机样本。',
        '95% 区间使用超几何分布双尾反演，直接考虑有限总体、不放回抽样，包含有限总体修正；极端 x=0 或 x=n 不使用退化的正态区间。Q 级、用户类别和调优/留出子域在域内用同法估计，域内无样本而有残余时标不可估计。',
        '109 题不报 c 点估计。另列覆盖部分估计固定、未覆盖 11 题的残余认可率分别取 0% / 100% 的识别边界；已确定 a+b 始终保留。边界不是置信区间，同时给出覆盖部分 95% 区间端点合并后的外边界。低区分度题因与主表性质不同而单列，不宜套用主表的认可率。不做外推；T29 和历史试跑等未覆盖范围 c 均不可估计。',
        '内容只看结果，不因声明的假设矛盾撤销正确数值；NULL 不等于 0。A/B/C 原则及五题裁定用于最终抽样标签，未按题号新增规则。R1–R11 原样复用已审定候选实现，不实现抽样中发现的新呈现规则。303 次规则放行的独立复核已全部通过；这不替代本轮新参考下的数字独立核对。',
        '统计仅涵盖有匹配题面哈希的 deterministic 历史作答；judge 单列不评分。失败事件、旧题面不匹配和未完成日志的计数保存在 manifest，未静默删除；同一完成作答前的启动失败不是额外作答。正式单元按原抽样清单映射，旧版与试跑仅附表，不混入正式单元分母。',
        'SQL-L2-E按原报告合并两次run：后次完成替代前次2条传输失败身份，历史附表仍保留前次。SQL-L1-T4原来只跑55道deterministic题（主表49题），不补造未运行作答；与它的比较只用共有题，留出无样本的比较不生成。',
        '规则与人工判定均看过错例后形成，只测一个模型。抽样区间只表示有限残余总体的抽样不确定性，不包含参考/人工标签错误或模型重新生成的变异。分组区间分别为 95%，不是同时置信区间。',
        '', '## 全部正式单元','',
        '表中 a、b 分别列出；c 为估计新增次数，可为小数。完整历史与 Q 级/管理层/分析师/调优留出表见后文及配套 CSV。','']
    def table(title, entries):
        lines.extend([f'### {title}','','|单元|分组|题数/作答|a|b|交付率|a+b 下限|c|估计 [95% 区间]|11题0% / 100% 边界|',
                      '|---|---|---:|---:|---:|---:|---:|---:|---|---|'])
        for r in entries:
            est=percent(r['estimate'])+(f" [{percent(r['lo'])}, {percent(r['hi'])}]" if r['estimate'] is not None else '')
            bounds=f"{percent(r['uncovered_zero'])} / {percent(r['uncovered_all'])}" if r['scope']=='all109' else '—'
            lines.append(f"|{r['cell']}|{r['group']}|{r['questions']}/{r['attempts']}|{r['a']}|{r['b']}|{percent(r['delivery'])}|{percent(r['lower'])}|{r['c']:.2f}|{est}|{bounds}|" if r['c'] is not None else
                         f"|{r['cell']}|{r['group']}|{r['questions']}/{r['attempts']}|{r['a']}|{r['b']}|{percent(r['delivery'])}|{percent(r['lower'])}|不可估计|{est}|{bounds}|")
        lines.append('')
    for scope in ('main98','all109'):
        for dim in ('all','q_level','persona','split'):
            table(scope+' / '+dim,[r for r in summary if r['kind']=='formal' and r['scope']==scope and r['dimension']==dim])
    lines.extend(['## 残余总体与样本更新','','|单元|总残余|已知错误|可抽样 M|保留 n|内容正确 x|移入 a|移入 b|','|---|---:|---:|---:|---:|---:|---:|---:|'])
    for r in summary:
        if r['kind']=='formal' and r['scope']=='main98' and r['dimension']=='all':
            ss=[s for s in sample if s['stratum']==r['cell']]
            lines.append(f"|{r['cell']}|{r['residual']}|{r['known_errors']}|{r['covered_residual']}|{r['sample_n']}|{r['sample_correct']}|{sum(s['state']=='v2_pass' for s in ss)}|{sum(s['state']=='rule_pass' for s in ss)}|")
    lines.extend(['','## 跨单元稳健性','',
        '差值为右单元减左单元，按题先平均已有作答，再配对题目 bootstrap 5,000 次，种子 0，经验分位点（索引125与4874）95% 区间。八个核心单元全 28 对覆盖预登记主比较，另列直答/探查、L1/L1+、L1+/L3a、调优/叠加及指令梯度。只用两侧共有题；Q 级与用户类别表不替代这一配对。',
        '标签严格按预登记方向与区间是否含 0 给出；一侧差值恰为 0 而另一侧非 0 时保守记强弱依口径而定。准确率主检验用 a+b。敏感性用 a+b+c 的单元残余比例插补到残余题后做同样的按题 bootstrap，其区间条件于已估认可率，不另包含认可率估计误差，因此不能作为联合置信区间。109 题没有 c 敏感性。正式结论待独立核对后再写。',''])
    for scope in ('main98','all109'):
        for split in ('all','tuning','heldout'):
            lines.extend([f'### {scope} / {split}','','|左 → 右|配对题数|交付差 [95%]|a+b 差 [95%]|标签|估计敏感性差 [95%]|敏感性标签|','|---|---:|---|---|---|---|---|'])
            for r in comps:
                if r['scope']!=scope or r['split']!=split:
                    continue
                def interval(k):
                    return '不可估计' if r[k+'_delta'] is None else f"{100*r[k+'_delta']:+.1f} [{100*r[k+'_lo']:+.1f}, {100*r[k+'_hi']:+.1f}]"
                lines.append(f"|{r['left']} → {r['right']}|{r['questions']}|{interval('delivery')}|{interval('lower')}|{r['label']}|{interval('sensitivity')}|{r['sensitivity_label']}|")
            lines.append('')
    lines.extend(['## T29 取舍单元','','沿用冻结的拒答、把握门槛和三次一致选择，不因新得分改变选择。三次一致保留第1次作答，执行报错仍算已尝试回答；自评格式缺失按原门槛拒答。只报交付与 a+b，不估计 c。完整范围在 CSV 中；下表列实际观察范围及一致性主表/附表。','',
        '|单元|范围|口径|作答/总数|作答率|已答判对|已答正确率|同题三次基线|','|---|---|---|---:|---:|---:|---:|'])
    for r in t29:
        if r['scope']=='observed' or r['cell'].endswith('three-consistent') and r['scope'] in ('main98','all109','heldout49','tuning20'):
            lines.append(f"|{r['cell']}|{r['scope']}|{r['metric']}|{r['answered']}/{r['attempts']}|{percent(r['answer_rate'])}|{r['correct_answered']}|{percent(r['accuracy_answered'])}|{percent(r['baseline'])}|")
    lines.extend(['','## 历史单元附表',''])
    for scope in ('main98','all109'):
        table(scope,[r for r in summary if r['kind']=='historical' and r['scope']==scope and r['dimension']=='all'])
    lines.extend(['## 可复现与核对交接','',
        '设置 `SEMDEBT_EVAL_DIR`、`SEMDEBT_DATA_DIR`、`SEMDEBT_MAIN_DIR` 后，在本卡目录运行；路径只在 shell 导出，不写入文件。新 run-id 必须不存在；通过参数指定新的输出目录可重复生成，不改本次 run。','',
        '```sh',f'uv run --offline python scripts/t31_v4_recompute.py --run-id <new-run-id> --report-dir "$SEMDEBT_DATA_DIR/t31-v4-reproduction"',
        'uv run --offline pytest tests/test_t31_v4_recompute.py tests/test_t31_content_audit.py tests/test_repo_layout.py','```','',
        '逐单元/分组：`accuracy-v4-cells.csv`；配对比较：`accuracy-v4-comparisons.csv`；T29：`accuracy-v4-t29.csv`；样本更新：`accuracy-v4-sample.csv`。109题边界外层区间在 cells CSV 的 boundary_lo/boundary_hi。',
        '核对者从原始 run JSONL 与 `$SEMDEBT_DATA_DIR/runs-raw/` 独立读取最终执行结果，使用指定题库 tag、已审定 R1–R11、Claude 最终标签及抽样清单。manifest 记录来源/代码/裁定/标签哈希、排除计数、零调用与单调性检查；不需要出站题面、SQL 或数值。跨厂商复核通过前不更新中期/终版报告。',''])
    lines.extend(['原身份抽样框为仓库外 `$SEMDEBT_DATA_DIR/t31-final-review-list-strict.json`；脚本校验其按单元计数与公共frame CSV完全相等，确认新增可抽样残余没有落在原抽样框外。该文件只读、只记录哈希，不复制内容入库。可选 `--reuse-scoring-run runs/<earlier-rescore-id>` 可复用评分阶段，但会重新校验全部源日志、执行包哈希与冻结评分代码；所有聚合重新计算。',''])
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--report-dir',type=Path,default=ROOT/'reports/results')
    parser.add_argument('--reuse-scoring-run',type=Path,
                        help='Optional verified previous scoring pass; aggregates are always recomputed')
    args=parser.parse_args()
    if Path(args.run_id).name != args.run_id or 'rescore' not in args.run_id:
        raise ValueError('use a new rescore run id without path components')
    out=ROOT/'runs'/args.run_id
    if out.exists():
        raise FileExistsError('runs are append-only; choose a new run id')
    reportdir=args.report_dir
    names=['accuracy-v4.md','accuracy-v4-cells.csv','accuracy-v4-comparisons.csv','accuracy-v4-t29.csv','accuracy-v4-sample.csv']
    if any((reportdir/n).exists() for n in names):
        raise FileExistsError('choose a fresh report directory')
    bank=Path(os.environ['SEMDEBT_EVAL_DIR'])
    data=Path(os.environ['SEMDEBT_DATA_DIR'])
    roots=[ROOT,Path(os.environ['SEMDEBT_MAIN_DIR'])]
    assert git(bank,'rev-parse',TAG+'^{commit}').decode().strip()==COMMIT
    assert git(ROOT,'merge-base','--is-ancestor','efb3badc3166916cd2bfb28cf8be2125848a1723','HEAD')==b''
    sources=discover(roots)
    personas={}
    for file in ('cube_100.yaml','new.yaml'):
        payload=yaml.safe_load(git(bank,'show',f'{COMMIT}:questions/{file}'))
        for q in payload['questions'] if isinstance(payload,dict) else payload:
            personas[q['id']]=q['labels']['persona']
    with frozen_bank(bank,TAG) as (qs,columns,commit,archive):
        if args.reuse_scoring_run:
            rows,exclusions,source_manifest=reuse_scores(args.reuse_scoring_run,sources,data)
        else:
            rows,exclusions,source_manifest=rescore(sources,qs,columns,data,personas)
    rows=canonical_formal(rows)
    validation=ROOT/'reports/validation'
    reviewed=read_csv(validation/'t31-v4-claude-review.csv')
    assert len(reviewed)==303 and all(r['verdict']=='放行正确' for r in reviewed)
    certain_file=validation/'t31-v4-certain-errors.csv'
    rows=mark_known_errors(rows,read_csv(certain_file))
    # The old identity frame remains private; its public count file is cross-checked.
    frame_file=data/'t31-final-review-list-strict.json'
    frame=json.loads(frame_file.read_text())['ready_for_later_authorization']
    frame_keys={identity(r) for r in frame}
    indexed={identity(r):r for r in rows}
    old_counts=Counter(indexed[k]['stratum'] for k in frame_keys
                       if k in indexed and indexed[k]['stratum'] and not indexed[k]['low'])
    assert old_counts == Counter({r['stratum']:int(r['frame_attempts'])
                                  for r in read_csv(validation/'t31-residual-frame.csv')})
    for r in rows:
        if r['stratum'] and not r['low'] and residual(r) and not r['known_content_error']:
            assert identity(r) in frame_keys, 'uncovered residual requires a new user ruling'
    sample=sample_update(rows,read_csv(validation/'t31-residual-sample.csv'),read_csv(validation/'t31-residual-sample-claude.csv'))
    summary=summaries(rows,sample)
    comps=comparisons(rows,sample)
    t29=t29_summary(rows,ROOT)
    assert sum(r['content_lower'] for r in rows)>=sum(r['a'] for r in rows)
    inputfiles=[validation/n for n in ('t31-residual-sample.csv','t31-residual-frame.csv','t31-residual-sample-codex.csv','t31-residual-sample-claude.csv','t31-v4-claude-review.csv','t31-v4-claude-review-manual.csv','t31-v4-certain-errors.csv','t29-expanded-attempts.csv','t29-pilot-preflight.json')]
    codefiles=[ROOT/n for n in ('scripts/t31_v4_recompute.py','scripts/t31_candidate_scan.py','scripts/rescore_t23.py','harness/scorer_v2.py','harness/scorer_v3.py')]
    manifest=dict(eval_tag=TAG,eval_commit=commit,archive_sha256=archive,model_calls=0,query_executions=0,cost_cny=0,
        source_logs=source_manifest,exclusions=exclusions,attempts=len(rows),
        a=sum(r['a'] for r in rows),b=sum(r['b'] for r in rows),monotonicity=True,
        formal_superseded=sum(r.get('superseded_in_formal',False) for r in rows),
        known_content_errors=sum(r['known_content_error'] for r in rows),
        private_identity_frame_sha256=sha(frame_file.read_bytes()),
        reused_scoring_manifest_sha256=sha((args.reuse_scoring_run/'manifest.json').read_bytes()) if args.reuse_scoring_run else None,
        inputs={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in inputfiles+codefiles},
        sample_update=dict(Counter(s['state'] for s in sample)),status='pending independent cross-vendor recomputation')
    # Compute and validate everything before creating immutable run artifacts.
    out.mkdir()
    by_source=defaultdict(list)
    for r in rows:
        by_source[r['source_run']+'--'+r['cell']].append(r)
    for name, values in by_source.items():
        with (out/(name+'.jsonl')).open('x') as f:
            for r in values:
                f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
    with (out/'manifest.json').open('x') as f:
        json.dump(manifest,f,ensure_ascii=False,indent=2)
        f.write('\n')
    reportdir.mkdir(parents=True,exist_ok=True)
    for name,values in [('cells',summary),('comparisons',comps),('t29',t29),('sample',sample)]:
        write_csv(reportdir/f'accuracy-v4-{name}.csv',values)
    with (reportdir/'accuracy-v4.md').open('x') as f:
        f.write(report(summary,comps,t29,manifest,sample,args.run_id))
    print(json.dumps({k:manifest[k] for k in ('attempts','a','b','exclusions','sample_update')},ensure_ascii=False))


if __name__=='__main__':
    main()
