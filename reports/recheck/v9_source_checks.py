"""Read-only source checks for the changed v9 experiment descriptions."""
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT=Path(__file__).resolve().parents[2]
DATA=Path(os.environ['SEMDEBT_DATA_DIR']).resolve()
HASHES={}


def read(path):
    raw=path.read_bytes()
    key='$SEMDEBT_DATA_DIR/'+str(path.relative_to(DATA)) if path.is_relative_to(DATA) else str(path.relative_to(ROOT))
    HASHES[key]=hashlib.sha256(raw).hexdigest()
    return raw.decode()


# The actual frozen contexts and removed item bytes were checked independently
# before opening the report numbers. Here check the remaining metadata/base.
sys.path.insert(0,str(ROOT))
from render.context import render_cell
source=yaml.safe_load(read(ROOT/'semantic/tuning/SQL-L1.yaml'))
filtered=yaml.safe_load(read(ROOT/'semantic/tuning/SQL-L1.combo.yaml'))
sections={'semantics','rewrites','examples'}
metadata_equal={k:v for k,v in source.items() if k not in sections}=={k:v for k,v in filtered.items() if k not in sections}
combo=render_cell('SQL-L1plus-tuned-instr')
combo.pop('tuning')
base_equal=combo==render_cell('SQL-L1plus')
assert metadata_equal and base_equal
frozen=DATA/'t31-v7-census-20261030/frozen-inputs/semantic-v1.6-l1plus'
raw_bases=[]
system_matches={}
mode_by_id={}
for cell,key in [('SQL-L1plus','l1plus'),('SQL-L3a','ontology_turtle')]:
    raw=read(frozen/(cell+'-system.txt'))
    context=raw.split('```yaml\n',1)[1].split('\n```',1)[0]
    if cell=='SQL-L3a':
        turtle=yaml.safe_load(context)['ontology_turtle']
        mode_by_id={m[1]:json.loads(m[2]) for line in turtle.splitlines()
                    if (m:=re.match(r'^:(\w+) :mode (".*") \.$',line))}
    start=re.search('^'+key+':',context,re.M)
    assert start
    raw_bases.append(context[:start.start()])
    log=read(ROOT/'runs/20261025-T22b-l1plus-l3a-03'/(cell+'.jsonl'))
    expected={json.loads(line)['system_sha256'] for line in log.splitlines()}
    system_matches[cell]=expected=={hashlib.sha256(raw.encode()).hexdigest()}
assert raw_bases[0]==raw_bases[1] and all(system_matches.values())
possible=set(json.loads(read(ROOT/'reports/validation/l3a-ontology/missed.json'))['formalizable_annotation_entries'])
assert len(mode_by_id)==109 and len(possible)==16
assert all(mode_by_id[k]=='注解保留' for k in possible)

metric=read(ROOT/'reports/validation/metric-text-vs-impl.md')
assert '69 个指标' in metric and 'L1 里模型看到的文字' in metric
lines=[line for line in metric.splitlines() if '日均销售额' in line]
assert lines and any('写得很清楚' in line for line in lines)
channel_conflict=any('渠道' in line or 'conventions#1' in line for line in lines)
assert not channel_conflict
later=read(ROOT/'reports/results/l1-error-attribution.md')
later_rows=[line for line in later.splitlines() if 'conventions#1' in line and 'metrics.日均销售额' in line]
assert len(later_rows)==2
l1plus_audit=read(ROOT/'semantic/l1plus-audit.md')
assert 'dataset' in l1plus_audit and '约定 1 冲突' in l1plus_audit

# Scope evidence: the later positive-only review is not the whole audit history.
sample=json.loads(read(DATA/'t31-v7-census-20261030/snapshots/20261031-T31-v5-rulings-01/original-sample-bidirectional-audit.json'))
labels=Counter((r['old_label'],r['new_label']) for r in sample)
old_negative=sum(r['old_label']=='内容错误' for r in sample)
assert len(sample)==200 and old_negative==126
rescan=read(ROOT/'reports/validation/t31-v7-rescan.md')
assert '420 次原判对残余' in rescan and '194 次' in rescan
coordination=read(ROOT/'tasks/COORDINATION-HANDOFF.md')
assert '判错的 991 次没有在这一轮复核' in coordination

# Role/history checks concern recorded responsibility, not identity inference.
t10=read(ROOT/'tasks/T10-renderer.md')
t16=read(ROOT/'tasks/T16-metric-layer.md')
assert '负责：Claude Code' in t10 and '模式：**盲**' in t10
assert '负责：Codex' in t16 and 'Postgres 方言' in t16 and 'SQL-L2、JSON-L2' in t16
commits={}
for commit in ['10dfab6','3434837','4d03430']:
    body=subprocess.check_output(['git','show','-s','--format=%B',commit],cwd=ROOT).decode()
    commits[commit]={'claude_recorded': 'Claude' in body,
                     'full_commit':subprocess.check_output(['git','rev-parse',commit],cwd=ROOT).decode().strip()}
# 4d03430 may name Claude only in author metadata, retain a boolean not an email.
author=subprocess.check_output(['git','show','-s','--format=%an','4d03430'],cwd=ROOT).decode()
commits['4d03430']['claude_recorded'] |= 'Claude' in author
assert all(v['claude_recorded'] for v in commits.values())
initial_task=subprocess.check_output(['git','show','10dfab6:tasks/T10-renderer.md'],cwd=ROOT).decode()
assert '模式：**盲**' in initial_task

publication=read(ROOT/'decisions/2026-10-31-publication-choices.md')
assert '2026-11-01 更新' in publication and '6 个单元' in publication
assert '这取代上面第 3 条的范围' in publication and '对照页仍只放 19 个单元' in publication
for name in ['render/context.py','render/l1plus.py','render/combo.py','reports/validation/l1plus-l3a-correspondence.md',
             'reports/validation/l3a-ontology-validation.md','tasks/T30-combo-cell.md','reports/results/combo.md']:
    read(ROOT/name)
result={'model_api_calls':0,'query_executions':0,
    'l3a':{'raw_base_yaml_identical':True,'frozen_system_matches_original':system_matches,
            'formal_and_possible_sets_disjoint':True},
    'combo':{'metadata_unchanged':metadata_equal,'remaining_base_equals_L1plus':base_equal},
    'daily_sales_audit':{'scope_L1_metrics':69,'daily_sales_channel_conflict_listed':channel_conflict,
        'later_document_problem_rows':len(later_rows),'later_qids':['Q29']},
    'original_bidirectional_audit':{'attempts':len(sample),'old_negative_reviewed':old_negative,
        'old_negative_retained':labels['内容错误','内容错误'],
        'old_negative_historically_changed':labels['内容错误','内容正确']},
    'review_scope_warning':'991 negatives were not included in THIS later independent review; not a statement about all history',
    'role_commits':commits,
    'publication':{'response_units':19+6,'comparison_page_units':19,'latest_decision_controls':True},
    'inputs':HASHES}
path=ROOT/'reports/recheck/v9-source-checks.json'
path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('Source checks passed; historical negative reviews:',old_negative)
