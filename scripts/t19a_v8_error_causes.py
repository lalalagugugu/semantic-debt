"""Aggregate private manual error causes against frozen D1 labels; no API or SQL."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / 'runs/20261031-T31-v5-rulings-01'
EXPECTED = {'SQL-L1': 44, 'SQL-L3a': 21, 'SQL-L1-tuned': 12}
CATEGORIES = ('怎么算（口径或算法读偏）', '是什么、属于谁（对象或范围）', 'SQL 或执行问题', '其他')
REMOVED = 'SQL-L1plus-tuned-instr'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(row):
    return row['cell'], row['qid'], row['rep']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--classifications', type=Path)
    args = parser.parse_args()
    private = Path(os.environ['SEMDEBT_DATA_DIR']) / 't19a-v8-error-causes-20261101'
    path = args.classifications or private / 'classifications.json'
    reviewed = json.loads(path.read_text())
    materials_path = private / 'materials.json'
    assert digest(materials_path) == reviewed['materials_sha256']
    materials = {identity(r): r for r in json.loads(materials_path.read_text())}
    assert len(materials) == sum(EXPECTED.values())
    assert reviewed['model_api_calls'] == reviewed['query_executions'] == 0
    final_paths = sorted(FINAL.glob('*.jsonl'))
    source_hashes = {str(p.relative_to(ROOT)): digest(p) for p in final_paths}
    final = [json.loads(line) for p in final_paths for line in p.read_text().splitlines()]
    main_rows = [r for r in final if r['stratum'] and not r['low']]
    eligible = {identity(r): r for r in main_rows if r['cell'] in EXPECTED and r['content_correct'] == 0}
    assert Counter(r['cell'] for r in eligible.values()) == EXPECTED
    assert set(materials) == set(eligible)
    classifications = reviewed['records']
    assert len(classifications) == len(eligible)
    assert len({identity(r) for r in classifications}) == len(classifications)
    assert {identity(r) for r in classifications} == set(eligible)
    initial = json.loads((private / 'input-hashes.json').read_text())
    for name, value in initial.items():
        assert source_hashes[name] == value
    for r in classifications:
        assert r['category'] in CATEGORIES and r['evidence']
        material = materials[identity(r)]
        raw = json.dumps(material, sort_keys=True, ensure_ascii=False).encode()
        assert hashlib.sha256(raw).hexdigest() == r['material_sha256']
        source = eligible[identity(r)]
        assert source['content_correct'] == material['content_correct'] == 0
        assert source['source_record_sha256'] == material['source_record_sha256']
        assert source['exec_sha256'] == material['exec_sha256']
        if material['answer']['error'] is not None:
            assert r['category'] == 'SQL 或执行问题'

    history_dir = ROOT / 'runs/20261028-T31-v4-rescore-02'
    historical_manifest = json.loads((history_dir / 'manifest.json').read_text())
    final_manifest = json.loads((FINAL / 'manifest.json').read_text())
    history = []
    for name, value in final_manifest['baseline_scores'].items():
        p = ROOT / name
        assert digest(p) == value
        history.extend(json.loads(line) for line in p.read_text().splitlines())
    assert len(history) == historical_manifest['attempts'] == 7379
    units = {r['stratum'] for r in main_rows}
    kept = [r for r in main_rows if r['stratum'] != REMOVED]
    assert len(units) == 19 and len(main_rows) == 5439
    assert len({r['stratum'] for r in kept}) == 18 and len(kept) == 5145
    breakdown = Counter(
        '保留主表单元／主表题' if r['stratum'] and not r['low'] and r['stratum'] != REMOVED else
        '移出单元／主表题' if r['stratum'] and not r['low'] else
        '保留主表单元／低区分度题' if r['stratum'] and r['stratum'] != REMOVED else
        '移出单元／低区分度题' if r['stratum'] else '其他历史可比作答'
        for r in history)
    assert list(breakdown.values()) and sum(breakdown.values()) == len(history)
    assert breakdown == {'保留主表单元／主表题': 5145, '移出单元／主表题': 294,
                         '保留主表单元／低区分度题': 579, '移出单元／低区分度题': 33,
                         '其他历史可比作答': 1328}
    other = [r for r in history if not r['stratum']]
    old = [r for r in other if (r['source_run'], r['cell']) in {
        ('20261018-T13-sql-direct-01', 'SQL-L1.5S'),
        ('20261019-T16-full-v14-sql-old-01', 'SQL-L2-notes-v12')}]
    assert len(old) == 654 and len(other) - len(old) == 674
    lines = ['# T19a v8：定稿错因统计与作答范围分解', '',
        '日期：2026-11-01。依据 `runs/20261031-T31-v5-rulings-01` 的主表内容定稿标签；只统计指定三组内容错误或执行失败，未修改任何已有标签。模型API调用0、SQL执行0、新增费用0。', '',
        '## 每次一个主类', '',
        '按最终SQL、执行结果/报错及既有定稿证据逐次核对；这是对可见错误的人工归类，不从模型思考内容推断心理原因。怎么算涵盖指标口径、聚合、分母、排序、窗口算法；是什么、属于谁涵盖对象身份、分组归属与纳入范围；SQL或执行问题涵盖语法、类型、连接默认值等语言机制或最终执行报错；不足以归入前三类则记其他。多种偏差并存时，取最直接改变所问结果的主要偏差，不重复计数。', '',
        '不能按题号整题套类；同题不同次、不同单元的主要问题可能不同。SQL或执行问题共5次，其中4次为最终执行失败，1次为可执行SQL的语言/连接计数机制问题。内容标签按定稿值筛选，不用历史严格评分的correct/wrong替代。完整逐次证据及原文仅在数据目录。', '',
        '|单元|怎么算（口径或算法读偏）|是什么、属于谁（对象或范围）|SQL 或执行问题|其他|合计|',
        '|---|---:|---:|---:|---:|---:|']
    total = Counter()
    for cell, expected in EXPECTED.items():
        counts = Counter(r['category'] for r in classifications if r['cell'] == cell)
        assert sum(counts.values()) == expected
        total.update(counts)
        lines.append('|' + '|'.join(map(str, [cell, *(counts[c] for c in CATEGORIES), expected])) + '|')
    lines.append('|' + '|'.join(map(str, ['合计', *(total[c] for c in CATEGORIES), sum(EXPECTED.values())])) + '|')
    lines += ['', '## 逐次清单', '', '|题号|单元|次数|类别|', '|---|---|---:|---|']
    for cell in EXPECTED:
        for r in sorted((r for r in classifications if r['cell'] == cell), key=lambda r: (int(r['qid'][1:]), r['rep'])):
            lines.append(f"|{r['qid']}|{r['cell']}|{r['rep']}|{r['category']}|")
    lines += ['', '## 去掉 SQL-L1plus-tuned-instr 后的主表', '',
        '- 原主表：19个单元，5439次作答。移出该单元的98题×3次＝294次后，保留18个单元、5145次。',
        '- 保留单元中，17个单元各98题×3次＝4998次；SQL-L1-T4仅49道调优题×3次＝147次。因此合计5145，不是18×98×3。',
        '- 仅改变本报告的纳入范围，不删除、改写该单元原日志或标签；三组错因范围不受该单元移出影响。', '',
        '## 全部历史可比作答的精确分解', '',
        '历史框固定为T31重评清单的7379次可比作答；不重新遍历所有runs目录来重复计入重评分副本，不把HTTP尝试、纠错回包数或后续U2采集混入。非主表部分并非都完成D1全量内容判定，本节只分解次数。', '',
        '|历史范围类别|作答数|', '|---|---:|']
    for name in ('保留主表单元／主表题', '移出单元／主表题', '保留主表单元／低区分度题', '移出单元／低区分度题', '其他历史可比作答'):
        lines.append(f'|{name}|{breakdown[name]}|')
    lines += ['|全部历史可比作答|7379|', '',
        '7379＝5145＋294＋579＋33＋1328。按旧范围写法即5439＋612＋1328；最后一项是精确1328，不用“约1330”。', '',
        '1328＝654次旧正式版本对照（SQL-L1.5S旧版327、SQL-L2-notes-v12旧版327）＋674次其他试跑、冒烟和被替代前记录。被后次正式结果替代的2次L2-E身份保留在历史附表，不重复进入正式主表。', '',
        '若要求连低区分度题也完全排除该单元，则另一个清晰口径是7379−327＝7052＝5145＋579＋1328。这个7052是排除后的历史视图，不是把原始历史7379条删除成7052条。', '',
        'T31清单另行排除330条非deterministic记录、18条旧题面哈希不匹配记录、183条harness_error事件；这些不是7379分母中的条目，不能再次从7379扣除，也不能都称为额外作答。', '',
        '## 复现与只读核验', '',
        '完整材料和人工分类在 `$SEMDEBT_DATA_DIR/t19a-v8-error-causes-20261101/`。脚本要求77个身份恰好覆盖定稿错例、每次仅一个允许的主类，并核验私有材料、三个定稿输入、历史重评清单的SHA。原始响应和执行结果已在材料准备时按来源SHA逐条核对。', '',
        '```sh', 'uv run --offline python scripts/t19a_v8_error_causes.py', '```', '',
        '该命令只读取标签和私有分类，生成本报告及私有审计清单；不调用模型、不执行SQL、不重评分、不修改任何已有作答标签。公开逐次表仅含题号、单元、次数和类别；不附题面、SQL、结果值或私有解释。', '']
    output = ROOT / 'reports/results/t19a-v8-error-causes.md'
    output.write_text('\n'.join(lines))
    assert source_hashes == {str(p.relative_to(ROOT)): digest(p) for p in final_paths}
    audit = dict(final_labels_sha256=source_hashes, classifications_sha256=digest(path),
                 historical_manifest_sha256=digest(history_dir / 'manifest.json'),
                 report_sha256=digest(output), model_api_calls=0, query_executions=0,
                 error_attempts=sum(EXPECTED.values()), category_counts=dict(total),
                 kept_main_units=18, kept_main_attempts=5145, historical_attempts=7379,
                 historical_breakdown=dict(breakdown))
    (private / 'report-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(attempts=77, category_counts=dict(total), main_units=18,
                          main_attempts=5145, historical_attempts=7379), ensure_ascii=False))


if __name__ == '__main__':
    main()
