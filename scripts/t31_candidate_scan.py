"""Offline, unapproved candidate-rule experiments over hash-verified saved answers.

No question-specific rule branches, model calls, SQL execution, or scorer edits.
Each rule is measured independently against v2. Output is private evidence only.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness import scorer_v2 as V2, scorer_v3 as V3
from harness.value_units import is_numeric_type
from scripts.rescore_t23 import frozen_bank, saved_turn

RULES = {
    'R1': '期间无损归一；只有题面唯一年份证据时可补齐/省略恒定年份',
    'R2': '由枚举列头唯一识别的可逆长宽表，完整保留分组和数值',
    'R3': '保留实体键，合并姓名；仅缺失/占位姓名允许编码回退',
    'R4': '客户状态的说明性客户后缀，不合并不同状态',
    'R5': '非数值分类的NULL与明确未知标签，不扩展到数值空值',
    'R6': '列头明确为减少量时，正数减少额与带符号变化等价',
    'R7': '题面未要求排序且没有Top-N/排名/选择约束时忽略行序',
    'R8': '名称与键一一对应且可唯一识别时，不强制额外编码列',
    'R9': '完整互斥分组金额已给且合计可验证时，省略重复总分母列',
    'R10': '折后额和折扣率可唯一还原折前分母时，省略显式折前额',
    'R11': '一行比较指标与可验证的比较组/基准组两行布局等价',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def name(column):
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', column['name'].rsplit('.', 1)[-1].lower())


def close(a, b, kind='amount'):
    return V2._equal(V2._norm(a), V2._norm(b), kind, kind == 'count', None)


def numeric(column):
    return is_numeric_type(column['type'])


def key(value):
    return V2._norm(value, True)


def correct(c, r, rule):
    return V2.score_detailed(c, [r], rule).outcome == 'correct'


def numeric_null_needs_ruling(candidate, reference, rule, columns):
    """Do not inherit v2's empty-group marginals when loosening a different rule.

Without a declared column/identity mapping, be conservative and retain review.
This guard does not revoke any originally correct v2 verdict.
"""
    missing = any(row[i] is None for i, col in enumerate(columns) if numeric(col) for row in candidate)
    zero = any(row[j] == 0 for j in rule['required_columns']
               if is_numeric_type(rule['value_types'][j]) for row in reference)
    return missing and zero


def variants(code, candidate, reference, rule, cc, rc, text):
    if any(isinstance(v, (list, tuple, dict)) for table in (candidate, reference) for row in table for v in row):
        return
    c, r, m = deepcopy(candidate), deepcopy(reference), deepcopy(rule)
    if code == 'R1':
        if m.get('selection') or m.get('rankings') or m.get('top_n') is not None or m.get('unordered_pairs'):
            return
        a, b = V3._periods(c, cc), V3._periods(r, rc, m)
        if not a or not b:
            return
        if a[3] != b[3]:
            years = set(re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)', text))
            if len(years) != 1 or Counter(x[0] for x in a[3].elements()) != Counter(x[0] for x in b[3].elements()):
                return
            wanted = f'__period_year:{next(iter(years))}'
            for table, info in ((a[0], a[4]), (b[0], b[4])):
                for part in info:
                    yi = part['year_column']
                    if yi is not None and any(row[yi] != wanted for row in table):
                        return
        yield a[0], b[0], b[2]
    elif code == 'R2':
        original = V3._p2(c, r, m, cc, rc)
        if original:
            yield original[0], r, m
        if len(rc) != 3 or m.get('selection') or m.get('rankings') or m.get('top_n') is not None:
            return
        aliases = {'Actual': ('actual', '实际'), 'Budget': ('budget', '预算'), 'Forecast': ('forecast', '预测')}
        choices = []
        for measure in range(3):
            if not numeric(rc[measure]):
                continue
            for axis in range(3):
                if axis == measure or numeric(rc[axis]):
                    continue
                group = next(i for i in range(3) if i not in (axis, measure))
                members = {row[axis] for row in r}
                if len(members) < 2 or not all(isinstance(v, str) and v for v in members):
                    continue
                group_values = {key(row[group]) for row in r}
                group_cols = [i for i in range(len(cc)) if {key(row[i]) for row in c} == group_values]
                if len(group_cols) != 1 or len({key(row[group_cols[0]]) for row in c}) != len(c):
                    continue
                mapping, suffixes = {}, set()
                for member in members:
                    prefixes = aliases.get(member, (re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', member.lower()),))
                    hits = [(i, name(col)[len(p):]) for i, col in enumerate(cc) if numeric(col)
                            for p in prefixes if name(col).startswith(p)]
                    hits = list(set(hits))
                    if len(hits) != 1:
                        break
                    mapping[member] = hits[0][0]
                    suffixes.add(hits[0][1])
                else:
                    if len(set(mapping.values())) != len(members) or len(suffixes) != 1:
                        continue
                    used = set(mapping.values()) | {group_cols[0]}
                    valid_extras = True
                    for extra, col in enumerate(cc):
                        if extra in used:
                            continue
                        if any(all(row[extra] == row[i] for row in c) for i in used):
                            continue
                        if not numeric(col) or set(mapping) != {'Actual', 'Budget'} or not re.search(r'variance|difference|diff|差异|差额', name(col)):
                            valid_extras = False
                            break
                        for row in c:
                            difference = Decimal(str(row[mapping['Actual']])) - Decimal(str(row[mapping['Budget']]))
                            kind = 'amount'
                            if re.search(r'rate|pct|percent|率', name(col)):
                                base = Decimal(str(row[mapping['Budget']]))
                                difference, kind = (difference / base if base else None), 'ratio'
                            if not close(row[extra], difference, kind):
                                valid_extras = False
                    if not valid_extras:
                        continue
                    rows = []
                    for row in c:
                        for member, index in mapping.items():
                            target = [None] * 3
                            target[group], target[axis], target[measure] = row[group_cols[0]], member, row[index]
                            rows.append(target)
                    choices.append(rows)
        if len(choices) == 1:
            yield choices[0], r, m
    elif code in ('R3', 'R8'):
        ids = m.get('identifier_columns', [])
        if len(ids) != 1 or not r:
            return
        ri = ids[0]
        identity = name(rc[ri])
        aliases = {'customerkey': ('customerkey', '客户编码', '客户键'),
                   'storekey': ('storekey', '门店编码', '门店键'),
                   'productkey': ('productkey', '产品编码', '产品键'),
                   'employeekey': ('employeekey', 'managerkey', '员工编码', '经理编码')}
        ci = [i for i, col in enumerate(cc) if name(col) in aliases.get(identity, (identity,))]
        cname = [i for i, col in enumerate(cc) if not numeric(col)
                 and re.search(r'name|姓名|名称|门店$|经理$', name(col))]
        first = [i for i, col in enumerate(rc) if name(col) == 'firstname']
        last = [i for i, col in enumerate(rc) if name(col) == 'lastname']
        single = [i for i, col in enumerate(rc) if i != ri and not numeric(col)
                  and re.search(r'name|manager$|姓名|名称', name(col))]
        merged = bool(first and last)
        if merged:
            rn = first[0]
            for row in r:
                row[rn] = f'{row[first[0]]} {row[last[0]]}'
            m['required_columns'] = [i for i in m['required_columns'] if i != last[0]]
        elif len(single) == 1:
            rn = single[0]
        else:
            return
        if len(cname) != 1:
            return
        cn = cname[0]
        fallback = set()
        for row in r:
            if row[rn] is None or row[rn] == '' or 'Not Provided' in str(row[rn]):
                fallback.add(key(row[ri]))
                row[rn] = str(int(Decimal(str(row[ri]))))
        if code == 'R3':
            if len(ci) != 1:
                return
            for row in c:
                if key(row[ci[0]]) in fallback and (row[cn] is None or row[cn] == '' or 'Not Provided' in str(row[cn])
                        or key(row[cn]) == key(row[ci[0]])):
                    row[cn] = str(int(Decimal(str(row[ci[0]]))))
        else:
            if m.get('selection') or m.get('rankings') or m.get('top_n') is not None:
                return
            names = [row[rn] for row in r]
            if len(set(names)) != len(names):
                return
            for row in c:
                match = re.fullmatch(r'(?:CustomerKey|StoreKey|ProductKey|EmployeeKey)\s+(\d+)', str(row[cn]))
                if match and key(int(match[1])) in fallback:
                    row[cn] = match[1]
            m['required_columns'] = [i for i in m['required_columns'] if i != ri]
            m['identifier_columns'] = []
        yield c, r, m
    elif code == 'R4':
        for i, column in enumerate(cc):
            if numeric(column) or not re.search(r'status|segment|分层|状态', name(column)):
                continue
            for j, refcol in enumerate(rc):
                if numeric(refcol):
                    continue
                labels = {row[j] for row in r}
                values = {row[i] for row in c}
                mapped = {v: v[:-2] if isinstance(v, str) and v.endswith('客户') else v for v in values}
                if len(set(mapped.values())) == len(mapped) and set(mapped.values()) <= labels and any(k != v for k, v in mapped.items()):
                    out = deepcopy(c)
                    for row in out:
                        row[i] = mapped[row[i]]
                    yield out, r, m
    elif code == 'R5':
        out, changed = deepcopy(c), False
        for j, column in enumerate(rc):
            if numeric(column) or None not in {row[j] for row in r}:
                continue
            labels = {row[j] for row in r if row[j] is not None}
            hits = [i for i, col in enumerate(cc) if not numeric(col)
                    and '未知' in {row[i] for row in c}
                    and {row[i] for row in c} <= labels | {None, '未知'}
                    and (name(col) == name(column) or bool({row[i] for row in c} & labels))]
            if len(hits) == 1:
                for row in out:
                    if row[hits[0]] == '未知':
                        row[hits[0]], changed = None, True
        if changed:
            yield out, r, m
    elif code == 'R6':
        for i, col in enumerate(cc):
            if numeric(col) and re.search(r'decrease|减少额|减少量|降幅', name(col)):
                out = deepcopy(c)
                if not all(row[i] is None or Decimal(str(row[i])) >= 0 for row in out):
                    continue
                for row in out:
                    if row[i] is not None:
                        row[i] = -Decimal(str(row[i]))
                yield out, r, m
    elif code == 'R7':
        if not m.get('ordered') or m.get('selection') or m.get('rankings') or m.get('top_n') is not None:
            return
        if re.search(r'排序|排名|从高到低|从低到高|升序|降序|前\s*\d+|最高|最低|top\s*\d+|rank|sort', text, re.I):
            return
        m['ordered'] = False
        m.pop('order_by', None)
        yield c, r, m
    elif code == 'R9':
        if len(r) < 2 or len(r) != len(c) or m.get('selection') or m.get('top_n') is not None:
            return
        totals = [j for j in m['required_columns'] if m['value_kinds'][j] == 'amount'
                  and re.search(r'total|总', name(rc[j])) and len({row[j] for row in r}) == 1]
        amounts = [j for j, kind in enumerate(m['value_kinds']) if kind == 'amount' and j not in totals]
        for total in totals:
            for amount in amounts:
                target = r[0][total]
                if target is None or Decimal(str(target)) <= 0 or not close(sum(Decimal(str(row[amount])) for row in r), target):
                    continue
                hits = [i for i, col in enumerate(cc) if numeric(col) and re.search(r'sales|amount|revenue|销售额|营收', name(col))
                        and all(row[i] is not None for row in c) and close(sum(Decimal(str(row[i])) for row in c), target)]
                dimensions = [j for j, col in enumerate(rc) if not numeric(col)
                              and len({key(row[j]) for row in r}) == len(r)]
                proven = False
                if len(hits) == 1:
                    for dimension in dimensions:
                        expected = {key(row[dimension]): row[amount] for row in r}
                        identities = [i for i, col in enumerate(cc) if not numeric(col)
                                      and len({key(row[i]) for row in c}) == len(c)
                                      and {key(row[i]) for row in c} == set(expected)]
                        if len(identities) == 1 and all(close(row[hits[0]], expected[key(row[identities[0]])]) for row in c):
                            proven = True
                if proven:
                    reduced = deepcopy(m)
                    reduced['required_columns'].remove(total)
                    yield c, r, reduced
    elif code == 'R10':
        totals = [j for j in m['required_columns'] if m['value_kinds'][j] == 'amount'
                  and re.search(r'original.*amount|original.*sales|折前|原价', name(rc[j]))]
        revenues = [j for j, col in enumerate(cc) if numeric(col) and re.search(r'revenue|营收|salesamount', name(col))]
        rates = [j for j, col in enumerate(cc) if numeric(col) and re.search(r'discount.*(?:pct|rate|ratio)|折扣.*(?:率|比例)', name(col))]
        if len(r) != len(c) or len(revenues) != 1 or len(rates) != 1:
            return
        for total in totals:
            # Single-result comparisons are sufficient; multi-row roles need explicit identity metadata.
            if len(r) != 1:
                continue
            net, rate = c[0][revenues[0]], c[0][rates[0]]
            for scale in (Decimal(1), Decimal(100)):
                fraction = Decimal(str(rate)) / scale
                if fraction < 0 or fraction >= 1:
                    continue
                if close(Decimal(str(net)) / (1 - fraction), r[0][total]):
                    ref_net = [j for j, col in enumerate(rc) if m['value_kinds'][j] == 'amount'
                               and re.search(r'revenue|营收|salesamount', name(col)) and j != total]
                    if len(ref_net) != 1 or not close(net, r[0][ref_net[0]]):
                        continue
                    reduced = deepcopy(m)
                    reduced['required_columns'].remove(total)
                    yield c, r, reduced
    elif code == 'R11':
        if len(r) != 1 or len(c) != 2 or any(not numeric(col) for col in rc) or len(rc) != 2:
            return
        delta = [i for i, col in enumerate(cc) if numeric(col) and re.search(r'diff|difference|差额', name(col))
                 and not re.search(r'pct|percent|rate|率|比', name(col))]
        rates = [i for i, col in enumerate(cc) if numeric(col) and re.search(r'pct|percent|rate|率|比', name(col))]
        bases = [i for i, col in enumerate(cc) if numeric(col) and re.search(r'avgdailysales|日均', name(col))
                 and not re.search(r'ordinary|基|上|去年', name(col))]
        if len(delta) != 1 or len(rates) != 1 or len(bases) != 1:
            return
        di, pi, ai = delta[0], rates[0], bases[0]
        ref_delta = [j for j, kind in enumerate(m['value_kinds']) if kind == 'amount']
        if len(ref_delta) != 1:
            return
        for row in c:
            baseline = next(other for other in c if other is not row)
            if row[di] is None or row[pi] is None or baseline[ai] in (None, 0):
                continue
            if baseline[di] is not None and not close(baseline[di], 0):
                continue
            if not close(Decimal(str(row[ai])) - Decimal(str(baseline[ai])), row[di]):
                continue
            if not close(row[di], r[0][ref_delta[0]]):
                continue
            if not close(row[pi], Decimal(str(row[di])) / Decimal(str(baseline[ai])), 'ratio'):
                continue
            yield [row], r, m


def zero_amount_variant(c, r, m, cc, rc):
    """Unapproved NULL/zero alternative; only empty additive amount with a zero count."""
    counts = [i for i, kind in enumerate(m['value_kinds']) if kind == 'count']
    amounts = [i for i, kind in enumerate(m['value_kinds']) if kind == 'amount']
    if len(counts) != 1 or len(amounts) != 1 or not all(row[amounts[0]] == 0 for row in r if row[counts[0]] == 0):
        return None
    ccnt = [i for i, col in enumerate(cc) if numeric(col) and re.search(r'count|stores|数量|家数', name(col))]
    camt = [i for i, col in enumerate(cc) if numeric(col) and re.search(r'gap|shortfall|缺口', name(col))]
    if len(ccnt) != 1 or len(camt) != 1:
        return None
    out, changed = deepcopy(c), False
    for row in out:
        if row[ccnt[0]] == 0 and row[camt[0]] is None:
            row[camt[0]], changed = 0, True
    return out if changed else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or ROOT == args.output.resolve() or ROOT in args.output.resolve().parents:
        raise ValueError('choose a new output outside the repository')
    data = Path(os.environ['SEMDEBT_DATA_DIR'])
    audit = json.loads((data / 't31-content-audit-reviewed.json').read_text())
    seen = {(r['raw_run'], r['cell'], r['qid'], r['rep']) for r in audit['attempts']}
    sources, caches = {}, {}
    for root in args.source_root:
        for path in sorted((root / 'runs').glob('*/*.jsonl')):
            for rawline in path.read_bytes().splitlines():
                if not rawline.strip():
                    continue
                rec = json.loads(rawline)
                if isinstance(rec.get('final'), dict) and 'v2' in rec['final']:
                    k = rec.get('source_run'), rec.get('cell'), rec.get('qid'), rec.get('rep')
                    if rec.get('source_log_sha256') and rec['final'].get('exec_raw_sha256'):
                        caches[k] = (rec['source_log_sha256'], rec['final'])
            if not path.name.startswith(('SQL-', 'JSON-', 'DAX-')) or 'rescore' in path.parent.name:
                continue
            raw = path.read_bytes()
            key_source = path.parent.name, path.stem
            if key_source in sources:
                old = sources[key_source][1]
                if old.startswith(raw):
                    continue
                if not raw.startswith(old):
                    raise ValueError(f'divergent original logs: {key_source}')
            sources[key_source] = path, raw
    rows, exclusions, manifest = [], Counter(), {}
    with frozen_bank(Path(os.environ['SEMDEBT_EVAL_DIR'])) as (qs, columns, commit, archive):
        for (run, cell), (path, raw) in sorted(sources.items()):
            digest = sha(raw)
            manifest[str(path)] = digest
            latest = {}
            for line in raw.splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get('status') != 'done':
                    exclusions['source_status:' + rec.get('status', 'missing')] += 1
                    continue
                if 'turns' not in rec or 'qid' not in rec:
                    exclusions['not_answer_record'] += 1
                    continue
                k = rec['qid'], rec['rep']
                if k in latest:
                    raise ValueError('duplicate completed attempt in original log')
                latest[k] = rec
            for (qid, rep), rec in sorted(latest.items()):
                if qid not in qs or qs[qid].scoring != 'deterministic':
                    exclusions['not_frozen_deterministic_question'] += 1
                    continue
                q = qs[qid]
                if rec.get('question_sha256') != sha(q.text.encode()):
                    exclusions['changed_or_missing_question_hash'] += 1
                    continue
                candidate, cc, exec_sha = saved_turn(rec['turns'][-1], data / 'runs-raw' / run / cell, qid, rep)
                cache = caches.get((run, cell, qid, rep))
                if cache and cache[0] == digest and cache[1]['exec_raw_sha256'] == exec_sha:
                    baseline = cache[1]['v2']['outcome']
                else:
                    baseline = V2.score_detailed(candidate, q.refs, q.rules, reference_rules=q.ref_rules).outcome
                if baseline not in ('correct', 'wrong', 'exec_error', 'refused'):
                    exclusions['no_v2_verdict'] += 1
                    continue
                item = {'source_run': run, 'cell': cell, 'qid': qid, 'rep': rep,
                        'v2_correct': baseline == 'correct', 'v2_outcome': baseline, 'rules': [], 'withheld_numeric_null_rules': [],
                        'seen_error': (run, cell, qid, rep) in seen,
                        'source_log': str(path), 'exec_sha256': exec_sha,
                        'exec_path': str(data / 'runs-raw' / run / cell / f"{qid}_r{rep}_t{rec['turns'][-1]['turn']}.exec.json"),
                        'reference_material': {'eval_tag': 'eval-v1.2', 'qid': qid, 'all_reference_indices': list(range(len(q.refs)))},
                        'question_material': {'eval_commit': commit, 'qid': qid, 'sha256': rec['question_sha256']},
                        'system_material': {'sha256': rec.get('system_sha256'), 'semantic_tag': rec.get('semantic_tag')},
                        'null_zero_reject': baseline == 'correct', 'null_zero_accept': baseline == 'correct'}
                if baseline == 'wrong' and isinstance(candidate, list) and cc:
                    for code in RULES:
                        hit = False
                        for index, ref in enumerate(q.refs):
                            metadata = q.ref_rules[index] if q.ref_rules and q.ref_rules[index] is not None else q.rules
                            for c, r, m in variants(code, candidate, ref, metadata, cc, columns[qid][index], q.text):
                                if correct(c, r, m):
                                    hit = True
                                    break
                            if hit:
                                break
                        if hit:
                            if any(numeric_null_needs_ruling(candidate, ref,
                                    q.ref_rules[i] if q.ref_rules and q.ref_rules[i] is not None else q.rules, cc)
                                   for i, ref in enumerate(q.refs)):
                                item['withheld_numeric_null_rules'].append(code)
                            else:
                                item['rules'].append(code)
                    for index, ref in enumerate(q.refs):
                        metadata = q.ref_rules[index] if q.ref_rules and q.ref_rules[index] is not None else q.rules
                        zeroed = zero_amount_variant(candidate, ref, metadata, cc, columns[qid][index])
                        if zeroed is None:
                            continue
                        for c, r, m in [(zeroed, ref, metadata), *variants('R8', zeroed, ref, metadata, cc, columns[qid][index], q.text)]:
                            if correct(c, r, m):
                                item['null_zero_accept'] = True
                item['candidate_content_correct'] = item['v2_correct'] or bool(item['rules'])
                item['null_zero_reject'] = item['candidate_content_correct']
                item['null_zero_accept'] = item['null_zero_accept'] or item['candidate_content_correct']
                assert not item['v2_correct'] or item['candidate_content_correct'], 'v4 must not revoke v2'
                assert item['null_zero_accept'] >= item['null_zero_reject'] >= item['v2_correct']
                rows.append(item)
            print(f'audited {run}/{cell}: {len(latest)} saved answers', flush=True)
    assert sum(r['candidate_content_correct'] for r in rows) >= sum(r['v2_correct'] for r in rows)
    counts = {code: {'definition': text,
                     'changed': sum(code in r['rules'] for r in rows),
                     'not_in_reviewed_errors': sum(code in r['rules'] and not r['seen_error'] for r in rows)}
              for code, text in RULES.items()}
    result = {'eval_commit': commit, 'archive_sha256': archive, 'source_sha256': manifest,
              'script_sha256': sha(Path(__file__).read_bytes()),
              'attempts': rows, 'exclusions': dict(exclusions), 'per_rule': counts,
              'model_calls': 0, 'cost_cny': 0, 'rule_counts_are_independent': True,
              'status': 'Unapproved conservative experiments, not deployed v4. Unrecognized meanings remain for review.'}
    with args.output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({'eligible_attempts': len(rows), 'per_rule': counts,
                      'exclusions': dict(exclusions)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
