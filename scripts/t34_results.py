"""T34 offline evidence export. No model calls or query execution.

uv run python scripts/t34_results.py prepare --source RUN --cell SQL-L1
Full questions, references and responses stay in SEMDEBT_DATA_DIR.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness import scorer_v2 as V2
from harness import run_direct as H
from scripts.rescore_t23 import frozen_bank, saved_turn
from scripts.t31_v4_recompute import approved_rules, paired_interval

CELLS = ('SQL-L1', 'SQL-L1-onto', 'SQL-L1plus', 'SQL-L3a-full')
EVAL_TAG = 'eval-v1.3'
EVAL_COMMIT = '5b65e0c450ba36d83707c00dc9443be16b08d086'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, default=str) + '\n').encode()


def new_or_same(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f'{path.name}: existing artifact differs; preserve it and use a new output id')
    else:
        with path.open('xb') as out:
            out.write(data)


def prepare(source, cell, output):
    data = Path(os.environ['SEMDEBT_DATA_DIR']).resolve()
    bank = Path(os.environ['SEMDEBT_EVAL_DIR'])
    src = ROOT / 'runs' / source / (cell + '.jsonl')
    raw = src.read_bytes()
    all_records = [(line, json.loads(line)) for line in raw.splitlines() if line.strip()]
    records = [(line, r) for line, r in all_records if r.get('status') == 'done']
    identities = [(r['qid'], r['rep']) for _, r in records]
    if len(identities) != len(set(identities)):
        raise ValueError('duplicate completed identity')
    preflight = json.loads((ROOT / 'runs' / source / 'preflight.json').read_text())
    expected = {(qid, rep) for qid in preflight['question_sha256_by_id'] for rep in (1, 2, 3)}
    if len(records) != 327 or set(identities) != expected:
        raise ValueError('prepare requires exactly the frozen 109 questions x repetitions 1, 2, 3')
    fingerprints = {t.get('system_fingerprint') for _, r in records for t in r['turns']}
    if fingerprints != {preflight['fingerprint']['new_run_baseline']}:
        raise ValueError('source fingerprint differs or is missing')
    private = data / 't34-run-20261104' / 'codex' / output / cell
    public = ROOT / 'runs' / output
    raw_dir = data / 'runs-raw' / source / cell
    delivered = H.system_for(({**H.CELLS, **H.L1PLUS_CELLS})[cell])
    if {r['system_sha256'] for _, r in records} != {sha(delivered.encode())}:
        raise ValueError('delivered system message differs from source records')
    new_or_same(private / 'system.txt', delivered.encode())
    rows = []
    materials = []
    with frozen_bank(bank, EVAL_TAG) as (questions, reference_columns, commit, archive_sha):
        if commit != EVAL_COMMIT:
            raise ValueError('unexpected D1 reference commit')
        for line, rec in records:
            qid, rep = rec['qid'], rec['rep']
            q = questions[qid]
            if rec['question_sha256'] != sha(q.text.encode()):
                raise ValueError('question text changed')
            turn = rec['turns'][-1]
            candidate, columns, execution_sha = saved_turn(turn, raw_dir, qid, rep)
            api_path = raw_dir / f"{qid}_r{rep}_t{turn['turn']}.json"
            response_bytes = api_path.read_bytes()
            if sha(response_bytes) != turn['raw_sha256']:
                raise ValueError('response checksum mismatch')
            for t in rec['turns']:
                api = raw_dir / f"{qid}_r{rep}_t{t['turn']}.json"
                if sha(api.read_bytes()) != t['raw_sha256']:
                    raise ValueError('earlier response checksum mismatch')
            verdict = V2.score_detailed(candidate, q.refs, q.rules, reference_rules=q.ref_rules).outcome
            rules = approved_rules(candidate, columns, q, reference_columns[qid]) if verdict == 'wrong' else []
            lower = verdict == 'correct' or bool(rules)
            if verdict not in ('correct', 'wrong', 'exec_error', 'refused'):
                raise ValueError('unscored attempt')
            has_result = isinstance(candidate, list)
            label = True if lower else None if has_result else False
            row = dict(source_run=source, cell=cell, qid=qid, rep=rep,
                       source_record_sha256=sha(line), question_sha256=rec['question_sha256'],
                       system_sha256=rec['system_sha256'], exec_sha256=execution_sha,
                       response_sha256=turn['raw_sha256'], low=bool(q.meta['low_discrimination']),
                       split=q.meta['split'], v2_outcome=verdict, rules=rules,
                       content_lower=int(lower), has_result=has_result,
                       content_correct=label, wrong_cause='SQL' if verdict == 'exec_error' else None,
                       codex_basis='v2' if verdict == 'correct' else 'R1-R11' if rules else
                                   'execution failure' if verdict == 'exec_error' else
                                   'refusal' if verdict == 'refused' else 'pending full-result content review',
                       independent_correct_review='pending' if label else 'not_yet_applicable')
            refs = []
            for i, values in enumerate(q.refs):
                rule = q.ref_rules[i] if q.ref_rules and q.ref_rules[i] is not None else q.rules
                refs.append(dict(index=i, columns=reference_columns[qid][i], rows=values, rules=rule))
            payload = json.loads((raw_dir / f"{qid}_r{rep}_t{turn['turn']}.exec.json").read_text()) if execution_sha else None
            response = json.loads(response_bytes)['choices'][0]['message'].get('content') or ''
            material = dict(**row, question=q.text, meta=q.meta, refs=refs,
                            query=turn.get('query'), response=response, answer=payload)
            row['material_sha256'] = sha(encoded(material))
            material['material_sha256'] = row['material_sha256']
            new_or_same(private / 'attempts' / f'{qid}-r{rep}.json', encoded(material))
            rows.append(row)
            materials.append(material)
    new_or_same(private / 'materials.json', encoded(materials))
    new_or_same(public / (cell + '.jsonl'), b''.join(encoded(r) for r in rows))
    code_paths = ['harness/scorer_v2.py', 'scripts/t31_v4_recompute.py',
                  'scripts/t31_candidate_scan.py', 'scripts/t34_results.py']
    manifest = dict(source_run=source, cell=cell, eval_tag=EVAL_TAG, eval_commit=commit,
                    reference_archive_sha256=archive_sha, source_log_sha256=sha(raw),
                    materials_sha256=sha(encoded(materials)),
                    automatic_credit_is_not_final_review=True,
                    attempts=len(rows), main_attempts=sum(not r['low'] for r in rows),
                    pending_content=sum(r['content_correct'] is None for r in rows),
                    pending_independent_correct=sum(r['content_correct'] is True for r in rows),
                    model_calls=0, query_executions=0,
                    code_sha256={p: sha((ROOT / p).read_bytes()) for p in code_paths})
    new_or_same(public / (cell + '-manifest.json'), encoded(manifest))
    print(json.dumps({k: manifest[k] for k in ['cell', 'attempts', 'main_attempts',
                                             'pending_content', 'pending_independent_correct',
                                             'model_calls', 'query_executions']}, ensure_ascii=False))


def export_review(output):
    """Export rule/manual positives, excluding v2 passes as in the main table."""
    data = Path(os.environ['SEMDEBT_DATA_DIR']) / 't34-run-20261104'
    private = data / 'codex' / output
    target = data / 'claude-review'
    if target.exists():
        raise ValueError('review directory exists; preserve the issued packet')
    positives, locks, public_labels = [], {}, []
    credit_counts = {}
    for cell in CELLS:
        base = private / cell
        ledger_bytes = (base / 'codex-decisions.json').read_bytes()
        ledger = json.loads(ledger_bytes)
        materials = json.loads((base / 'materials.json').read_text())
        main = [m for m in materials if not m['low']]
        if len(main) != 294 or len({(m['qid'], m['rep']) for m in main}) != 294:
            raise ValueError('incomplete main98 identities')
        locks[cell] = sha(ledger_bytes)
        counts = Counter(v2=0, rules=0, manual=0)
        for m in main:
            original_material = {k: v for k, v in m.items() if k != 'material_sha256'}
            if sha(encoded(original_material)) != m['material_sha256']:
                raise ValueError('private material checksum mismatch')
            verdict = ledger['records'][f"{m['qid']}:r{m['rep']}"]
            if (verdict['material_sha256'] != m['material_sha256'] or
                    type(verdict['correct']) is not bool):
                raise ValueError('missing verdict or material binding')
            if not verdict['correct'] and verdict['cause'] not in ('怎么算', '是什么/属于谁', 'SQL'):
                raise ValueError('missing primary wrong cause')
            public_labels.append(dict(cell=cell, qid=m['qid'], rep=m['rep'],
                                      content_correct=verdict['correct'], wrong_cause=verdict['cause'],
                                      material_sha256=m['material_sha256'],
                                      independent_review='pending', final=False))
            if verdict['correct']:
                kind = 'v2' if m['v2_outcome'] == 'correct' else 'rules' if m['rules'] else 'manual'
                counts[kind] += 1
                if kind != 'v2':
                    positives.append((cell, m))
        credit_counts[cell] = dict(counts)
    secrets.SystemRandom().shuffle(positives)
    files, mapping, cases = {}, {}, []
    for index, (cell, m) in enumerate(positives, 1):
        anon = f'T34V2R{index:04d}'
        context = (private / cell / 'system.txt').read_bytes()
        if sha(context) != m['system_sha256']:
            raise ValueError('review context differs from delivered context')
        context_file = f'context-{sha(context)}.txt'
        files[context_file] = context
        cases.append(dict(anonymous_id=anon, question=m['question'],
                          context_file=context_file, query=m['query'],
                          response=m['response'], answer=m['answer'], references=m['refs']))
        mapping[anon] = dict(cell=cell, qid=m['qid'], rep=m['rep'],
                             material_sha256=m['material_sha256'])
    entries = []
    for start in range(0, len(cases), 40):
        batch = cases[start:start + 40]
        name = f'cases-{start // 40 + 1:03d}.json'
        files[name] = encoded(batch)
        entries.append(dict(file=name, count=len(batch), first=batch[0]['anonymous_id'],
                            last=batch[-1]['anonymous_id']))
    policy = '''# T34 independent content review

Use an ordinary local Claude Code session. Read only this packet, not sibling
Codex ledgers, source logs, repository final labels or identity mappings.
Review every anonymous attempt independently against the delivered context,
question, complete executed result and allowed references. Do not execute any
model API client or rerun collection.
Do not put private materials in the repository or send them to a cloud coordinator.
This is edition non-v2-v2, matching the main-table review scope: v2 direct passes
are excluded. Review all rule-released and manually credited attempts in this
packet. Earlier T34R identifiers belong to the superseded all-positive packet;
do not reuse earlier results against these T34V2R identifiers.

Use the unchanged main-table D1 rules: enterprise meaning controls; an unstated
alternative interpretation is insufficient. Missing unknown/unassigned nonzero
groups is wrong. An explicit delivered-document rule that contradicts a reference
can justify credit; identify that rule. Equivalent labels, layouts and harmless
auxiliary columns are allowed. Unasked reference columns are not required.
One unambiguous arithmetic step may recover a requested value only if no explicit
requested value contradicts it. Summing detail requires complete rows, explicit
group membership and no truncation. Multi-period cumulative reconstruction is
not allowed. NULL differs from zero; extra nonzero groups are not zero groups.
Check every requested value and period. Use the frozen scorer_v2 numeric
comparison and reference-specific rules: the tolerance is the larger of 0.5%
of the reference magnitude and the absolute floor (amount 0.01, percentage
0.01 percentage point, ratio 0.0001). Preserve exact comparisons where required.
The scorer permits ratio/percentage scale normalization; do not invent new
tolerances. D1 still rejects explicit contradictory requested answers.

Write results.json here as an array with exactly one object per anonymous_id:
{"anonymous_id":"T34V2R0001","correct":true,"note":"independent evidence"}
correct must be a JSON boolean. Explain each rejection or document-reference
conflict in note. Include no original identity guesses. Read full rows rather
than previews. Do not edit packet inputs. Return results for every listed entry.
'''
    files['REVIEW.md'] = policy.encode()
    inventory = [dict(file=name, sha256=sha(blob), bytes=len(blob))
                 for name, blob in sorted(files.items())]
    public = dict(directory='$SEMDEBT_DATA_DIR/t34-run-20261104/claude-review/',
                  output='results.json', audit_id=output, entries=len(cases),
                  anonymous_first=cases[0]['anonymous_id'] if cases else None,
                  anonymous_last=cases[-1]['anonymous_id'] if cases else None,
                  batches=entries, files=inventory,
                  edition='non-v2-v2',
                  supersedes='all-positive packet issued at commit 2259845',
                  credit_counts_by_cell=credit_counts,
                  credit_counts_total=dict(sum((Counter(v) for v in credit_counts.values()), Counter())),
                  scope='main-table policy: R1-R11 and manual positives only; v2 direct passes excluded',
                  review_instructions='REVIEW.md', model_calls=0)
    new_or_same(private / 'locked-verdicts.json', encoded(locks))
    new_or_same(private / 'review-identity-map-non-v2-v2.json', encoded(mapping))
    new_or_same(ROOT / 'runs' / output / 'codex-verdicts.jsonl',
                b''.join(encoded(r) for r in public_labels))
    for name, blob in files.items():
        new_or_same(target / name, blob)
    (ROOT / 'reports/validation/t34-claude-review-manifest.json').write_bytes(encoded(public))
    print(json.dumps(dict(entries=len(cases), files=len(files), model_calls=0)))


def usage_audit(source):
    """Read returned usage only; never launch, resume or control collection."""
    root = Path(os.environ['SEMDEBT_DATA_DIR']) / 'runs-raw' / source
    by, seen, fingerprints = {}, set(), Counter()
    incomplete = 0
    for path in sorted(root.rglob('*.json')):
        if path.name.endswith('.exec.json'):
            continue
        try:
            raw = path.read_bytes()
            response = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            incomplete += 1
            continue
        if not isinstance(response, dict) or not isinstance(response.get('usage'), dict):
            continue
        identity = response.get('id') or sha(raw)
        if identity in seen:
            continue
        seen.add(identity)
        u = response['usage']
        hit = int(u.get('prompt_cache_hit_tokens') or 0)
        miss = int(u.get('prompt_cache_miss_tokens') or 0)
        prompt = int(u.get('prompt_tokens') or 0)
        if hit + miss == 0:
            miss = prompt
        if hit + miss != prompt:
            raise ValueError('input token accounting does not balance')
        completion = int(u.get('completion_tokens') or 0)
        cost = (Decimal(hit) * Decimal('.02') + miss + completion * 4) / 1000000
        z = by.setdefault(path.parent.name, Counter())
        z.update(calls=1, prompt_tokens=prompt, hit_tokens=hit, miss_tokens=miss,
                 completion_tokens=completion, cost_cny=cost)
        fingerprints[str(response.get('system_fingerprint'))] += 1
    totals = {cell: {k: str(v) if isinstance(v, Decimal) else v for k, v in z.items()}
              for cell, z in by.items()}
    return dict(source=source, per_cell=totals, fingerprints=dict(fingerprints),
                returned_calls=len(seen), incomplete_files=incomplete,
                total_cost_cny=str(sum((z['cost_cny'] for z in by.values()), Decimal(0))),
                prices_cny_per_million=dict(input_hit='.02', input_miss='1', output='4'),
                pricing='offpeak; frozen collection pricing; completion includes reasoning',
                model_calls=0)


def summary(source, output):
    private = Path(os.environ['SEMDEBT_DATA_DIR']) / 't34-run-20261104/codex' / output
    labels, stats = {}, {}
    for cell in CELLS:
        ledger = json.loads((private / cell / 'codex-decisions.json').read_text())
        records = [r for r in ledger['records'].values() if r['in_scope']]
        if len(records) != 294 or any(type(r['correct']) is not bool for r in records):
            raise ValueError('incomplete content labels')
        by_question = {}
        for r in records:
            by_question.setdefault(r['qid'], []).append(int(r['correct']))
        if len(by_question) != 98 or any(len(v) != 3 for v in by_question.values()):
            raise ValueError('incomplete question repetitions')
        labels[cell] = by_question
        native = [json.loads(line) for line in
                  (ROOT / 'runs' / source / (cell + '.jsonl')).read_text().splitlines()]
        main = [r for r in native if r.get('status') == 'done' and r['qid'] in by_question]
        if len(main) != 294:
            raise ValueError('source collection incomplete')
        stats[cell] = dict(attempts=294, correct=sum(sum(v) for v in by_question.values()),
                           stability=dict(all_correct=sum(sum(v) == 3 for v in by_question.values()),
                                          all_wrong=sum(sum(v) == 0 for v in by_question.values()),
                                          mixed=sum(0 < sum(v) < 3 for v in by_question.values())),
                           first_turn_exec_errors=sum(r['first'] == 'exec_error' for r in main),
                           wrong_causes=dict(Counter(r['cause'] for r in records if not r['correct'])),
                           first_turn_prompt_tokens=sum(r['turns'][0]['usage']['prompt_tokens'] for r in main))
    def comparison(left, right):
        if set(left) != set(right):
            raise ValueError('paired question sets differ')
        differences = [sum(right[q]) / 3 - sum(left[q]) / 3 for q in sorted(left)]
        mean, lo, hi = paired_interval(differences, B=5000, seed=0)
        return dict(delta=mean, lo=lo, hi=hi, contains_zero=lo <= 0 <= hi, questions=98)
    pairs = {f'{right} minus {left}': comparison(labels[left], labels[right])
             for left, right in [('SQL-L1', 'SQL-L1-onto'), ('SQL-L1plus', 'SQL-L3a-full')]}
    drift = {}
    for cell in ('SQL-L1', 'SQL-L1plus'):
        old = [json.loads(line) for line in
               (ROOT / 'runs/20261031-T31-v5-rulings-01' / (cell + '.jsonl')).read_text().splitlines()]
        old_labels = {}
        for r in old:
            if not r['low']:
                old_labels.setdefault(r['qid'], []).append(int(r['content_correct']))
        if any(len(v) != 3 for v in old_labels.values()):
            raise ValueError('historical repetitions differ')
        drift[cell] = comparison(old_labels, labels[cell])
    result = dict(source=source, content_audit=output, independent_review='pending',
                  final=False, main98=stats, paired_effects=pairs, historical_drift=drift,
                  bootstrap=dict(unit='question, average of three repetitions', resamples=5000, seed=0),
                  collection_usage=usage_audit(source), model_calls=0)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--source', required=True)
    p.add_argument('--cell', choices=CELLS, required=True)
    p.add_argument('--output', help='new offline audit id; defaults to SOURCE-content-01')
    p = commands.add_parser('export-review')
    p.add_argument('--output', required=True, help='completed offline audit id')
    p = commands.add_parser('usage')
    p.add_argument('--source', required=True)
    p = commands.add_parser('summary')
    p.add_argument('--source', required=True)
    p.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.source, args.cell, args.output or args.source + '-content-01')
    elif args.action == 'export-review':
        export_review(args.output)
    elif args.action == 'usage':
        print(json.dumps(usage_audit(args.source), ensure_ascii=False))
    elif args.action == 'summary':
        summary(args.source, args.output)


if __name__ == '__main__':
    main()
