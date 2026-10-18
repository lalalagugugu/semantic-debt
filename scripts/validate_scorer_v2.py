"""Offline v2/legacy corpus comparison; only identifiers and verdicts enter reports."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import scorer, scorer_v2
from datetime import date, datetime
from decimal import Decimal


def decode_value(value):
    if isinstance(value, list):
        return [decode_value(v) for v in value]
    if isinstance(value, dict):
        if len(value) != 1:
            raise ValueError("invalid corpus typed value")
        tag, text = next(iter(value.items()))
        parsers = {"$date": date.fromisoformat, "$datetime": datetime.fromisoformat,
                   "$decimal": Decimal, "$float": float}
        if tag == "$array":
            return tuple(decode_value(v) for v in text)
        if tag not in parsers:
            raise ValueError("unknown corpus typed value")
        return parsers[tag](text)
    return value


def decode_candidate(value):
    return scorer.ExecError(value["exec_error"]) if isinstance(value, dict) else decode_value(value)


@contextmanager
def deadline(seconds):
    def expired(*_):
        raise TimeoutError('scoring deadline exceeded')
    handler = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, handler)


def run(paths, output, report, old_timeout=2, eval_tag=None):
    records, fingerprints = [], {}
    for path in paths:
        digest = hashlib.sha256()
        with path.open('rb') as source:
            for raw in source:
                digest.update(raw)
                case = json.loads(raw)
                if eval_tag is not None and case.get('bank', '').split('@')[0] != eval_tag:
                    raise ValueError(f'{case["case_id"]}: real reconciliation requires bank {eval_tag}')
                rec = {k: case[k] for k in ('case_id','source','question_id','turn','bank') if k in case}
                rec['phase'] = 't0' if case['case_id'].endswith('/t0') else 'final'
                if case.get('judge'):
                    rec['status'] = 'judge'
                    records.append(rec)
                    continue
                candidate = decode_candidate(case['candidate'])
                refs = decode_value(case['refs'])
                kwargs = {'reference_rules':case['rules']}
                rows = max([len(candidate) if isinstance(candidate,list) else 0] + [len(r) for r in refs])
                start = perf_counter()
                try:
                    with deadline(2 if rows <= 10000 else 30):
                        result = scorer_v2.score_detailed(candidate, refs, {}, **kwargs)
                    rec.update(status='scored', outcome=result.outcome, reason=result.reason if result.outcome!='exec_error' else 'execution_failed')
                    if result.outcome=='exec_error':
                        rec['execution_error_sha256']=hashlib.sha256(result.reason.encode()).hexdigest()
                except (ValueError, TypeError) as error:
                    rec.update(status='invalid_input', error=type(error).__name__, error_sha256=hashlib.sha256(str(error).encode()).hexdigest())
                except TimeoutError:
                    rec.update(status='timeout')
                rec['seconds'] = perf_counter() - start
                start = perf_counter()
                try:
                    with deadline(old_timeout):
                        result = scorer.score_detailed(candidate, refs, {}, **kwargs)
                    rec.update(old_outcome=result.outcome, old_reason=result.reason if result.outcome!='exec_error' else 'execution_failed')
                    if result.outcome=='exec_error':
                        rec['old_execution_error_sha256']=hashlib.sha256(result.reason.encode()).hexdigest()
                except TimeoutError:
                    rec['old_outcome'] = 'timeout'
                except (ValueError, TypeError) as error:
                    rec.update(old_outcome='invalid_input', old_error=type(error).__name__, old_error_sha256=hashlib.sha256(str(error).encode()).hexdigest())
                rec['old_seconds'] = perf_counter() - start
                if 'unscored' in (rec.get('outcome'), rec.get('old_outcome')):
                    rec['difference_class']='cap_separate'
                elif rec.get('outcome') is not None and rec['outcome'] != rec['old_outcome']:
                    if rec['old_outcome'] == 'timeout':
                        rec['difference_class'] = 'legacy_incomplete'
                        rec['explanation'] = '旧评分器超时，未得到判定；不计作判定翻转'
                    elif rec['outcome'] == 'correct':
                        # Inspect the new scorer's witness, never the legacy matching logic.
                        ref_index = scorer_v2.score_detailed(candidate, refs, {}, **kwargs).matched_ref
                        rule = case['rules'][ref_index]
                        for parts in scorer_v2._mappings(candidate, refs[ref_index], rule, rule['required_columns']):
                            if scorer_v2._check_mapping(candidate, refs[ref_index], parts, rule) is None:
                                rec['mapping_witness'] = [dict(reference=list(p.reference), candidate=list(p.candidate), reverse=p.reverse) for p in parts]
                                rec['difference_class'] = 'legacy_bug' if any(len(p.reference)>1 for p in parts) else 'needs_review'
                                rec['explanation'] = ('旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功'
                                                      if rec['difference_class']=='legacy_bug' else '待审核匹配见证')
                                break
                    else:
                        rec['difference_class'] = 'needs_review'
                        rec['explanation'] = '待审核新旧判定'
                records.append(rec)
        fingerprints[path.name] = digest.hexdigest()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
    counts = Counter(r.get('outcome',r['status']) for r in records)
    slow = sorted((r for r in records if 'seconds' in r),key=lambda r:r['seconds'],reverse=True)[:10]
    changes = [r for r in records if r.get('difference_class') in ('legacy_bug','needs_review')]
    incomplete = [r for r in records if r.get('old_outcome')=='timeout']
    invalid = [r for r in records if r['status']=='invalid_input']
    lines = ['# T02 评分器 v2 验证', '', '语料只读；不执行查询、不调用模型。judge 单列，不进入评分器。', '',
             f'- 输入行数：{len(records)}；分类：`{dict(counts)}`。',
             f'- unscored：{counts["unscored"]}；新评分超时：{counts["timeout"]}；输入不合法：{len(invalid)}。',
             f'- 旧评分超时上限：{old_timeout} 秒；判定差异：{len(changes)}；旧评分未完成：{len(incomplete)}。',
             '- 完整逐条耗时和原因：`scorer_v2_cases.jsonl`。', '', '## 输入指纹', '']
    lines += [f'- {name}：`{digest}`' for name,digest in fingerprints.items()]
    lines += ['', '## final 与 /t0 分开统计', '', '| 阶段 | 输入 | 分类 | 翻转 | invalid_input | unscored | 总秒数 | 最慢秒数 |', '|---|---:|---|---:|---:|---:|---:|---:|']
    for phase in ('final', 't0'):
        group = [r for r in records if r['phase'] == phase]
        distribution = Counter(r.get('outcome', r['status']) for r in group)
        flips = sum(r.get('difference_class') in ('legacy_bug', 'needs_review') for r in group)
        times = [r['seconds'] for r in group if 'seconds' in r]
        lines.append(f'| {phase} | {len(group)} | {dict(distribution)} | {flips} | {distribution["invalid_input"]} | {distribution["unscored"]} | {sum(times):.6f} | {max(times, default=0):.6f} |')
    lines += ['', '## 最慢 10 条', '', '| case_id | 秒 | 状态 / 判定 |', '|---|---:|---|']
    lines += [f'| {r["case_id"]} | {r["seconds"]:.6f} | {r.get("outcome",r["status"])} |' for r in slow]
    lines += ['', '## 逐条新旧判定差异', '', '| case_id | 旧 | 新 | 归因 |', '|---|---|---|---|']
    lines += [f'| {r["case_id"]} | {r["old_outcome"]} | {r["outcome"]} | {r["explanation"]} |' for r in changes]
    lines += ['', '## 旧评分器未完成（不计为判定翻转）', '', '| case_id | v2 状态 / 判定 | 秒 |', '|---|---|---:|']
    lines += [f'| {r["case_id"]} | {r.get("outcome",r["status"])} | {r["seconds"]:.6f} |' for r in incomplete]
    lines += ['', '## 输入不合法', '', '| case_id | 错误 |', '|---|---|']
    lines += [f'| {r["case_id"]} | {r["error"]} |' for r in invalid]
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text('\n'.join(lines)+'\n')
    print(json.dumps({'counts':dict(counts),'differences':len(changes),'slowest':slow[:3]},ensure_ascii=False))
    return 1 if counts['unscored'] or counts['timeout'] or invalid or any(r.get('difference_class') in ('needs_review','cap_separate') for r in records) else 0


def run_shared(path, output, report):
    """Read independent expected cases and report caps separately (spec 12.7)."""
    records = []
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for raw in source:
            digest.update(raw)
            case = json.loads(raw)
            candidate = decode_candidate(case['candidate'])
            refs = decode_value(case['refs'])
            size = max([len(candidate) if isinstance(candidate, list) else 0] + [len(r) for r in refs])
            limit = 2 if size <= 10000 else 30
            rec = {'case_id': case['case_id'], 'expected': case['expected'], 'limit_seconds': limit}
            start = perf_counter()
            try:
                with deadline(limit):
                    result = scorer_v2.score_detailed(candidate, refs, {}, reference_rules=case['rules'])
                rec.update(outcome=result.outcome, reason=result.reason if result.outcome!='exec_error' else 'execution_failed')
                if result.outcome=='exec_error':
                    rec['execution_error_sha256']=hashlib.sha256(result.reason.encode()).hexdigest()
            except (ValueError, TypeError) as error:
                rec.update(outcome='error', error=type(error).__name__, error_sha256=hashlib.sha256(str(error).encode()).hexdigest())
            except TimeoutError:
                rec['outcome'] = 'timeout'
            except Exception as error:
                rec.update(outcome='exception', error=type(error).__name__, error_sha256=hashlib.sha256(str(error).encode()).hexdigest())
            rec['seconds'] = perf_counter() - start
            expected = rec['expected']
            rec['cap_separate'] = 'unscored' in (expected['outcome'], rec['outcome'])
            rec['differs'] = not rec['cap_separate'] and (
                rec['outcome'] != expected['outcome'] or
                (expected.get('reason') is not None and expected['reason'] != rec.get('reason')))
            records.append(rec)
    input_sha = digest.hexdigest()
    if hashlib.sha256(path.read_bytes()).hexdigest() != input_sha:
        raise ValueError('shared corpus changed while validating')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records))
    differences = [r for r in records if r['differs']]
    separate = [r for r in records if r['cap_separate']]
    slowest = sorted(records, key=lambda r: r['seconds'], reverse=True)[:10]
    lines = ['# T02 v2 第十二节共用用例验证', '',
             '仅运行只读的 T05b 数据文件，未导入或读取独立检查器代码。正式真实语料对账等待 eval-v1.2 重新导出。', '',
             f'- 共 {len(records)} 条；判定 / 原因差异 {len(differences)} 条。',
             f'- 任一侧 unscored 单列 {len(separate)} 条；不计入分歧（第十二节第 7 条）。',
             f'- 输入 SHA256：`{input_sha}`；验证前后文件哈希一致。',
             f'- 评分器 SHA256：`{hashlib.sha256(Path(scorer_v2.__file__).read_bytes()).hexdigest()}`。',
             '- 逐条耗时及预期 / 实际结果：`scorer_v2_independent.jsonl`。', '',
             '## 最慢 10 条', '', '| 用例 | 秒 | 上限 | 判定 |', '|---|---:|---:|---|']
    lines += [f'| {r["case_id"]} | {r["seconds"]:.6f} | {r["limit_seconds"]} | {r["outcome"]} |' for r in slowest]
    lines += ['', '## 判定 / 原因差异', '', '| 用例 | 预期 | 实际 |', '|---|---|---|']
    lines += [f'| {r["case_id"]} | {r["expected"]} | {r.get("reason", r.get("error", r["outcome"]))} |' for r in differences]
    lines += ['', '## unscored 单列', '', '| 用例 | 预期 | 实际 |', '|---|---|---|']
    lines += [f'| {r["case_id"]} | {r["expected"]["outcome"]} | {r["outcome"]} |' for r in separate]
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'cases':len(records), 'differences':len(differences), 'cap_separate':len(separate),
                      'slowest':slowest[:3]}, ensure_ascii=False))
    return int(bool(differences) or any(r['outcome'] == 'timeout' for r in records))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus',type=Path,action='append')
    parser.add_argument('--shared',type=Path,help='read-only expected cases; skips legacy scorer')
    parser.add_argument('--output',type=Path,default=Path('reports/validation/scorer_v2_cases.jsonl'))
    parser.add_argument('--report',type=Path,default=Path('reports/validation/scorer_v2_check.md'))
    parser.add_argument('--old-timeout',type=float,default=2)
    parser.add_argument('--eval-tag',default='eval-v1.2',help='required bank tag for real reconciliation')
    args=parser.parse_args()
    if args.shared:
        return run_shared(args.shared,args.output,args.report)
    paths=args.corpus
    if not paths:
        if not os.environ.get('SEMDEBT_DATA_DIR'):
            parser.error('SEMDEBT_DATA_DIR or --corpus is required')
        root=Path(os.environ['SEMDEBT_DATA_DIR'])/'scorer-corpus'
        paths=[root/'pilot288.jsonl',root/'t13.jsonl']
    return run(paths,args.output,args.report,args.old_timeout,args.eval_tag)


if __name__=='__main__':
    raise SystemExit(main())
