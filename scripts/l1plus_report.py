"""Offline T22b results; no model calls and no query execution.

    uv run python scripts/l1plus_report.py --run 20261025-T22b-l1plus-l3a-03 \
        --scored-run 20261025-T22b-l1plus-l3a-03-rescore-01
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.questions import load_questions, verify_eval_tag
from harness.cells import PRICES_OFFPEAK
from scripts.hypothesis_splits import paired, per_question

REPO = Path(__file__).resolve().parents[1]
CELLS = ('SQL-L1plus', 'SQL-L3a')
BASELINE = '20261018-T13-sql-direct-01-rescore-01'


def records(run: str, cell: str) -> list[dict]:
    return [json.loads(line) for line in (REPO/'runs'/run/(cell+'.jsonl')).read_text().splitlines() if line]


def validate(rows: list[dict], ids: set[str]) -> None:
    seen = Counter((r['qid'], r['rep']) for r in rows)
    expected = {(qid, rep) for qid in ids for rep in (1, 2, 3)}
    if set(seen) != expected or any(n != 1 for n in seen.values()):
        raise ValueError('Missing, extra or duplicate (question, rep)')
    if any(r['status'] != 'done' or r['final'].get('pending') or r['final']['outcome'] == 'unscored' for r in rows):
        raise ValueError('Incomplete or unscored attempt')


def metrics(rows: list[dict], ids: set[str]) -> dict:
    kept = [r for r in rows if r['qid'] in ids]
    validate(kept, ids)
    hits = Counter({qid: 0 for qid in ids})
    for row in kept:
        hits[row['qid']] += row['final']['outcome'] == 'correct'
    return {'questions': len(ids), 'attempts': len(kept), 'correct': sum(hits.values()),
            'accuracy': sum(hits.values())/len(kept),
            'all_correct': sum(n == 3 for n in hits.values()),
            'all_wrong': sum(n == 0 for n in hits.values()),
            'mixed': sum(0 < n < 3 for n in hits.values())}


def receipt_cost(rows: list[dict], raw_dir: Path) -> float:
    """Reconcile every saved API response against its log hash and token cost."""
    prices = PRICES_OFFPEAK['deepseek-flash']
    total = 0.0
    for row in rows:
        cost = 0.0
        for turn in row['turns']:
            path = raw_dir / f"{row['qid']}_r{row['rep']}_t{turn['turn']}.json"
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != turn['raw_sha256']:
                raise ValueError(f'API raw hash mismatch: {path.name}')
            u = json.loads(payload)['usage']
            cost += (u['prompt_cache_hit_tokens']*prices['hit'] + u['prompt_cache_miss_tokens']*prices['miss']
                     + u['completion_tokens']*prices['output'])/1e6 * (2 if row['peak'] else 1)
        if not math.isclose(cost, row['cost_cny'], abs_tol=1e-10):
            raise ValueError(f"Cost mismatch: {row['qid']} r{row['rep']}")
        total += cost
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--scored-run', required=True)
    args = parser.parse_args()
    commit = verify_eval_tag('eval-v1.2')
    questions = load_questions()
    all_ids = {q.qid for q in questions if q.scoring != 'judge'}
    main_ids = {q.qid for q in questions if q.qid in all_ids and not q.meta['low_discrimination']}
    assert len(all_ids) == 109 and len(main_ids) == 98
    raw = {c: records(args.run, c) for c in CELLS}
    for c in CELLS:
        validate(raw[c], all_ids)
    # Reuse the frozen offline scoring helper directly: the older rescore CLI
    # registry predates these explicit-opt-in cells. Do not change the harness.
    from harness.questions import eval_commit
    from harness.rescore import rescore_line

    by_id = {q.qid: q for q in questions}
    for c in CELLS:
        target = REPO/'runs'/args.scored_run/(c+'.jsonl')
        if not target.exists():
            source_dir = Path(os.environ['SEMDEBT_DATA_DIR'])/'runs-raw'/args.run/c
            rescored = [rescore_line(r, by_id[r['qid']], source_dir, args.scored_run,
                                    eval_commit(), eval_tag='eval-v1.2') for r in raw[c]]
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('x') as stream:
                for row in rescored:
                    stream.write(json.dumps(row, ensure_ascii=False)+'\n')
    scored = {c: records(args.scored_run, c) for c in CELLS}
    for c in CELLS:
        validate(scored[c], all_ids)
    baseline = [r for r in records(BASELINE, 'SQL-L1') if r['qid'] in all_ids]
    validate(baseline, all_ids)
    bank = Path(os.environ['SEMDEBT_EVAL_DIR'])
    expanded_commits = {}
    for rows in raw.values():
        for row in rows:
            short = row['eval_commit']
            if short not in expanded_commits:
                expanded_commits[short] = subprocess.check_output(
                    ['git', '-C', str(bank), 'rev-parse', '--verify', short+'^{commit}'], text=True).strip()
            expanded = expanded_commits[short]
            assert expanded == commit and row['semantic_tag'] == 'semantic-v1.6-l1plus'
    mapping = (REPO/'reports/validation/metric-text-vs-impl.md').read_text()
    affected_all = set(re.findall(r'^\| (Q\d+) \|', mapping, re.MULTILINE))
    affected = affected_all & main_ids
    assert len(affected_all) == 22 and len(affected) == 19
    totals = {c: {label: metrics(scored[c], ids) for label, ids in [('98',main_ids),('109',all_ids)]} for c in CELLS}
    raw_root = Path(os.environ['SEMDEBT_DATA_DIR'])/'runs-raw'/args.run
    costs = {c: receipt_cost(raw[c], raw_root/c) for c in CELLS}
    prior_known = .0353178
    fingerprints = Counter(t.get('system_fingerprint') for rows in raw.values() for r in rows for t in r['turns'])
    transport_retries = sum(t.get('transport_retries', 0) for rows in raw.values() for r in rows for t in r['turns'])
    assert set(fingerprints) == {'e72d3c7f663d3e1383b00b3884cb4501'}
    contexts = {c: sorted({r['system_sha256'] for r in raw[c]}) for c in CELLS}
    assert all(len(v) == 1 for v in contexts.values())
    preflight = json.loads((raw_root/'preflight.json').read_text())
    assert all(contexts[c] == [preflight['system_sha256'][c]] for c in CELLS)
    lines = ['# L1+ 与 L3a 运行结果', '',
             'L1+ 的默认读法对照参考答案确定，代表「一轮系统性歧义审查、业务方逐条拍板」的乐观估计，不是上限。', '',
             'L3a 测的是「形式化写法对写 SQL 的模型有没有帮助」，不含可执行规则；OWL / SHACL 仅放入上下文，不运行形式化引擎。可执行形式化留在第二期 L3b。形式化 30 条，注解保留 79 条；形式化条目的复杂部分仍以注解完整保留。', '',
             f'- 正式运行：`{args.run}`；离线重评：`{args.scored_run}`（冻结评分器 v2，无模型调用、无 SQL 执行）。',
             f'- 题库：`eval-v1.2={commit}`；语义：`semantic-v1.6-l1plus=866004b3b1e55950139ba87f728d3f7f13f26433`。',
             '- 原样直接调用 harness，未套自写监控脚本。judge 13 题跳过，主表去掉低区分度 11 题。',
             f'- 本 run 费用：{sum(costs.values()):.8f} 元；加前两次已返回响应 {prior_known:.8f} 元，已知累计 {sum(costs.values())+prior_known:.8f} 元。run 02 未返回的在途请求用量仍不能从本地确认，未记为零。',
             '- 已逐 API 响应验证原始哈希与 token 费用，逐执行结果哈希由离线重评核对。',
             f'- 调用次数：{sum(r["n_calls"] for rows in raw.values() for r in rows)}；指纹：{dict(fingerprints)}。',
             f'- 原 harness 自动传输重试共 {transport_retries} 次，均保留在日志中；未改重试逻辑。费用按已返回响应 usage 核算，不把未返回用量当成零。',
             f'- 复现：`uv run python scripts/l1plus_report.py --run {args.run} --scored-run {args.scored_run}`。', '',
             '| 单元 | 题数 | 正确 / 作答 | 准确率 | 三次全对 | 三次全错 | 时对时错 |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for c in CELLS:
        for label in ('98','109'):
            m=totals[c][label]
            lines.append(f'| {c} | {m["questions"]} | {m["correct"]}/{m["attempts"]} | {m["accuracy"]:.1%} | {m["all_correct"]} | {m["all_wrong"]} | {m["mixed"]} |')
    lines += ['', '准确率按三次作答合计：主表分母 294，附表分母 327。三次全错指三次均未判正确（含执行失败或拒答）；稳定性三类按题计数。', '',
              '## 同题配对与歧义题敏感性', '',
              '每题取三次正确率（0、1/3、2/3、1），按题配对做差；复用既有 hypothesis_splits 的 10,000 次百分位自助法与固定种子 20261019，报 95% 区间。未将三次作答当作独立题目。', '',
              '受 14 个歧义口径影响的主表 19 题沿用 metric-text-vs-impl.md 的已冻结筛查结果：'+', '.join(sorted(affected))+ '。这是既有筛查标签，不是本次按结果重新归因。', '',
              '| 范围 | 对比 | 题数 | 差（百分点） | 95% 区间 |', '|---|---|---:|---:|---|']
    pq = {'SQL-L1': per_question(baseline, all_ids), **{c:per_question(scored[c],all_ids) for c in CELLS}}
    comparisons=[]
    for label,ids in [('主表，含歧义题',main_ids),('主表，不含19题',main_ids-affected),
                      ('附表，109题',all_ids),('附表，不含19题',all_ids-affected)]:
        for a,b in [('SQL-L1','SQL-L1plus'),('SQL-L1plus','SQL-L3a')]:
            result=paired(pq[a],pq[b],ids)
            comparisons.append({'scope':label,'a':a,'b':b,**result})
            lines.append(f'| {label} | {b} − {a} | {result["n"]} | {result["diff"]:+.1f} | [{result["lo"]:+.1f}, {result["hi"]:+.1f}] |')
    lines += ['', '## 费用与判定核对', '', '| 单元 | 费用（元） | 暂定 → 离线重评翻转数 |', '|---|---:|---:|']
    for c in CELLS:
        before={(r['qid'],r['rep']):r['final']['outcome'] for r in raw[c]}
        flips=sum(before[(r['qid'],r['rep'])]!=r['final']['outcome'] for r in scored[c])
        lines.append(f'| {c} | {costs[c]:.8f} | {flips} |')
    lines += ['', '系统消息 SHA-256：', '']
    lines += [f'- {c}：`{contexts[c][0]}`。' for c in CELLS]
    lines += ['', '两个先前中止 run 均保留，INDEX 只追加中止说明和费用补记。第二次在途用量尚无本地追加响应，未虚构提供商最终账单。', '',
              '## 残余歧义归因', '', '尚未执行。需另做归因 dry-run；预算另限 3 元。当前准确率与稳定性统计不依赖归因结果。']
    path=REPO/'reports/results/l1plus-l3a.md'
    path.write_text('\n'.join(lines)+'\n')
    path.with_suffix('.json').write_text(json.dumps({'run_id':args.run,'scored_run':args.scored_run,'metrics':totals,'costs':costs,'prior_known_cost':prior_known,'comparisons':comparisons},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'metrics':totals,'costs':costs},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
