"""T22b offline attribution audit and count report; no API or SQL execution."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import attribute_l1plus as A  # noqa: E402
from harness import client as C  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
LABELS = (*A.CATEGORIES, A.SUSPICIOUS)


def validate_labels(label: dict) -> dict:
    parsed, why = A.parse_labels(json.dumps(label, ensure_ascii=False))
    if parsed is None:
        raise ValueError(f"invalid classification: {why}")
    return parsed


def paired_rows(items: list[dict], flash: list[dict], codex: list[dict]) -> list[dict]:
    expected = [(r['qid'], int(r['rep'])) for r in items]
    if len(expected) != len(set(expected)):
        raise ValueError('duplicate preflight item')
    def index(rows):
        out = {}
        for row in rows:
            key = (row['qid'], int(row['rep']))
            if key in out:
                raise ValueError('duplicate classification item')
            out[key] = row
        if set(out) != set(expected):
            raise ValueError('classification coverage differs from fixed input')
        return out
    fs, cs = index(flash), index(codex)
    pairs = []
    for key in expected:
        f, c = fs[key], cs[key]
        if f['status'] != 'done':
            raise ValueError('incomplete Flash attribution; do not report as completed')
        fl = validate_labels(f['labels'])
        flag = c['data_quality_related']
        if flag not in ('true', 'false'):
            raise ValueError('Codex auxiliary flag must be true or false')
        cl = validate_labels({'category': c['category'], 'data_quality_related': flag == 'true'})
        pairs.append({'qid': key[0], 'rep': key[1], 'flash': fl, 'codex': cl})
    return pairs


def kappa(a: list, b: list) -> float:
    if not a or len(a) != len(b):
        raise ValueError('empty or unequal agreement vectors')
    ca, cb = Counter(a), Counter(b)
    po = sum(x == y for x, y in zip(a, b)) / len(a)
    pe = sum(ca[k] * cb[k] for k in ca.keys() | cb.keys()) / len(a) ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def counts(pairs: list[dict], side: str) -> dict:
    cat = Counter(r[side]['category'] for r in pairs)
    return {'categories': {label: cat[label] for label in LABELS},
            'five_class_total': sum(cat[label] for label in A.CATEGORIES),
            'single_total': cat[A.SUSPICIOUS], 'unparsed': 0,
            'data_quality_related': sum(r[side]['data_quality_related'] for r in pairs)}


def load(run_id: str) -> tuple[list[dict], dict]:
    folder = REPO / 'runs' / run_id
    manifest = json.loads((folder / 'manifest.json').read_text())
    summary = json.loads((folder / 'summary.json').read_text())
    preflight_path = REPO / 'reports/attribution/l1plus-dry-run-dq.json'
    preflight = json.loads(preflight_path.read_text())
    freeze = json.loads((REPO / 'reports/attribution/l1plus-codex-freeze.json').read_text())
    if datetime.fromisoformat(freeze['frozen_at']) >= datetime.fromisoformat(manifest['started_at']):
        raise ValueError('Codex labels were not frozen before Flash started')
    codex_path = REPO / 'reports/attribution/l1plus-codex.csv'
    if A.R.sha256(codex_path.read_bytes()) != freeze['csv_sha256']:
        raise ValueError('independent Codex CSV changed after freeze')
    if A.R.sha256(preflight_path.read_bytes()) != freeze['preflight_sha256']:
        raise ValueError('preflight changed after independent freeze')
    for key in ('codebook_sha256', 'system_sha256'):
        if freeze[key] != preflight[key]:
            raise ValueError('Codex codebook or system differs from preflight')
    for key, value in preflight.items():
        if key not in ('dry_run', 'paid_calls', 'budget_cny', 'est_output_tokens', 'est_hit_ratio', 'estimated_cost_cny'):
            if manifest.get(key) != value:
                raise ValueError(f'run differs from preflight: {key}')
    if A.R.sha256(A.CODEBOOK.read_bytes()) != manifest['codebook_sha256']:
        raise ValueError('codebook changed after first call')
    if A.R.sha256(Path(A.__file__).read_bytes()) != manifest['runner_sha256']:
        raise ValueError('attribution runner changed after first call')
    source = REPO / 'runs' / manifest['source_run'] / f"{manifest['cell']}.jsonl"
    if A.R.sha256(source.read_bytes()) != manifest['source_sha256']:
        raise ValueError('source outcomes changed')
    raw_dir = A.R.raw_root() / run_id
    if A.R.sha256((raw_dir / 'system.txt').read_text()) != manifest['system_sha256']:
        raise ValueError('raw attribution system changed')
    lines = [json.loads(s) for s in (folder / 'attribution.jsonl').read_text().splitlines() if s.strip()]
    codex = list(csv.DictReader(codex_path.open(encoding='utf-8', newline='')))
    pairs = paired_rows(manifest['items'], lines, codex)
    cost = 0.0
    expected_items = {(i['qid'], i['rep']): i for i in manifest['items']}
    for rec in lines:
        key = (rec['qid'], rec['rep'])
        if (rec['run_id'] != run_id or rec['system_sha256'] != manifest['system_sha256']
                or rec['codebook_sha256'] != manifest['codebook_sha256']
                or rec['user_sha256'] != expected_items[key]['user_sha256']
                or rec['system_fingerprint'] != A.A.FINGERPRINT or rec['transport_retries'] != 0
                or rec['finish_reason'] != 'stop' or rec['peak']):
            raise ValueError('run identity, fingerprint or response anomaly')
        user_path = raw_dir / 'inputs' / f"{key[0]}_r{key[1]}.txt"
        if A.R.sha256(user_path.read_text()) != rec['user_sha256']:
            raise ValueError('raw user material changed')
        raw = (raw_dir / f"{key[0]}_r{key[1]}.json").read_bytes()
        if A.R.sha256(raw) != rec['raw_sha256']:
            raise ValueError('raw response hash mismatch')
        reply = C._reply(raw, 0, 0)
        labels, why = A.parse_labels(reply.content)
        if labels != rec['labels'] or why or reply.usage != rec['usage'] or reply.system_fingerprint != A.A.FINGERPRINT:
            raise ValueError('raw labels, usage or fingerprint mismatch')
        actual = A.R.cost_cny(A.A.MODEL, reply.usage, False)
        if not math.isclose(actual, rec['cost_cny'], abs_tol=1e-10):
            raise ValueError('recorded cost differs from raw usage')
        cost += actual
        if not math.isclose(cost, rec['cumulative_cost_cny'], abs_tol=1e-9):
            raise ValueError('cumulative cost inconsistent')
    requests = [json.loads(s) for s in (raw_dir / 'requests.jsonl').read_text().splitlines() if s.strip()]
    if [(r['qid'], r['rep']) for r in requests] != [(i['qid'], i['rep']) for i in manifest['items']]:
        raise ValueError('request count/order differs from completed calls')
    if (summary['stopped'] or summary['uncertain_cost_bound_cny'] != 0
            or not math.isclose(cost, summary['known_cost_cny'], abs_tol=1e-9) or cost > 3):
        raise ValueError('stopped run, uncertain expense or over budget')
    meta = {'run_id': run_id, 'attempts': len(pairs), 'questions': len({p['qid'] for p in pairs}),
            'calls': len(requests), 'cost_cny': round(cost, 8), 'budget_cny': 3,
            'uncertain_cost_bound_cny': 0, 'source_run': manifest['source_run'],
            'semantic_tag': manifest['semantic_tag'], 'semantic_commit': manifest['semantic_commit'],
            'eval_tag': manifest['eval_tag'], 'eval_commit': manifest['eval_commit'],
            'codebook_sha256': manifest['codebook_sha256'], 'system_sha256': manifest['system_sha256'],
            'codex_csv_sha256': freeze['csv_sha256'], 'codex_frozen_at': freeze['frozen_at'],
            'flash': counts(pairs, 'flash'), 'codex': counts(pairs, 'codex'),
            'category_agreement': sum(p['flash']['category'] == p['codex']['category'] for p in pairs),
            'category_kappa': kappa([p['flash']['category'] for p in pairs], [p['codex']['category'] for p in pairs]),
            'flag_agreement': sum(p['flash']['data_quality_related'] == p['codex']['data_quality_related'] for p in pairs),
            'data_quality_both': sum(p['flash']['data_quality_related'] and p['codex']['data_quality_related'] for p in pairs),
            'data_quality_either': sum(p['flash']['data_quality_related'] or p['codex']['data_quality_related'] for p in pairs)}
    return pairs, meta


def render(pairs: list[dict], m: dict) -> str:
    n = m['attempts']
    md = ['# SQL-L1plus 残余歧义归因', '',
          f"- run-id：`{m['run_id']}`；{n} 条作答 / {m['questions']} 题；{m['calls']} 次 Flash 调用，实际 {m['cost_cny']:.8f} 元，预算 3 元，无待核算请求。",
          '- 主分类：五类 + 单列疑点；数据质量标记独立，不改变主分类。不改参考答案、评分或语义文档。',
          '- 方法：Flash 初判与 Codex 全量独立复核；先因出站审批阻塞完成并冻结 Codex 标签，后经用户明确出站授权运行 Flash。Codex 未见 Flash 标签与思考；规则和材料一致。',
          '- 材料含完整原系统消息（作答要求和语法说明）；不含原作答思考。结果摘要前 10 行、每值最多 200 字符，归因受摘要信息限制；Flash 自评仍有偏差风险。',
          '- 只报告两家独立标签，不强行合并分歧。分类计数按作答次数；五类构成分母排除单列及未解析，另报全体分母。',
          f"- Codex 标签冻结：`{m['codex_csv_sha256']}`；时间 `{m['codex_frozen_at']}`。", '',
          '| 类别 | Flash 条数 | Codex 条数 |', '|---|---:|---:|']
    for label in LABELS:
        md.append(f"| {label} | {m['flash']['categories'][label]} | {m['codex']['categories'][label]} |")
    for key, title in (('five_class_total','五类合计'),('single_total','单列合计'),('unparsed','未解析'),('data_quality_related','涉及数据质量问题：是')):
        md.append(f"| {title} | {m['flash'][key]} | {m['codex'][key]} |")
    md += ['', f"- 第 1 类占五类：Flash {m['flash']['categories'][A.CATEGORIES[0]]}/{m['flash']['five_class_total']}；Codex {m['codex']['categories'][A.CATEGORIES[0]]}/{m['codex']['five_class_total']}。全体分母均为 {n}。",
           f"- 主分类一致 {m['category_agreement']}/{n}，Cohen's κ={m['category_kappa']:.4f}；辅助标记一致 {m['flag_agreement']}/{n}。两家均标是 {m['data_quality_both']}，至少一家标是 {m['data_quality_either']}。", '',
           '## 逐条标签', '', '| 题号 / 次数 | Flash 类别 | 数据质量 | Codex 类别 | 数据质量 |', '|---|---|---|---|---|']
    for p in sorted(pairs, key=lambda r: (int(r['qid'][1:]), r['rep'])):
        md.append(f"| {p['qid']} r{p['rep']} | {p['flash']['category']} | {'是' if p['flash']['data_quality_related'] else '否'} | {p['codex']['category']} | {'是' if p['codex']['data_quality_related'] else '否'} |")
    md += ['', '## 单列：转题库负责方核对', '', '| 题号 | 类别 | 标注方 |', '|---|---|---|']
    for qid in sorted({p['qid'] for p in pairs if any(p[s]['category'] == A.SUSPICIOUS for s in ('flash','codex'))}, key=lambda q: int(q[1:])):
        sides = [s for s in ('flash','codex') if any(p['qid'] == qid and p[s]['category'] == A.SUSPICIOUS for p in pairs)]
        md.append(f"| {qid} | {A.SUSPICIOUS} | {' / '.join(sides)} |")
    md += ['', '## 复现', '', '```sh', f"uv run python scripts/l1plus_attribution_report.py --run-id {m['run_id']}", '```', '']
    return '\n'.join(md)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-id', required=True)
    args = ap.parse_args()
    pairs, meta = load(args.run_id)
    output = REPO / 'reports/results/l1plus-error-attribution'
    output.with_suffix('.md').write_text(render(pairs, meta), encoding='utf-8')
    output.with_suffix('.json').write_text(json.dumps({**meta, 'items': pairs}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in meta.items() if k in ('run_id','attempts','calls','cost_cny','flash','codex','category_agreement','flag_agreement')}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
