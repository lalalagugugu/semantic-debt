"""Review an immutable Cube syntax-notes branch using only generic probes.

No question bank, model client, original candidate query or scoring is used.
The three newly composed claims have their own end-to-end numeric probes.
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import hashlib
import itertools
import json
import math
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.probe_cube_interfaces_t16 import (  # noqa: E402
    BASE, PERIOD, manifest, followup_manifest, boundary_manifest, type_control_manifest, sql_result,
)
from harness.executors import CubeJsonExecutor, _pg_readonly  # noqa: E402

FILES = ('render/syntax/cube_sql.md','render/syntax/cube_json.md','reports/validation/syntax-syllabus.md',
         'decisions/2026-10-19-self-built-p-and-cube-notes.md')


def digest(b):
    return hashlib.sha256(b).hexdigest()


def additions(notes):
    cases=[]

    def sql(id, query, purpose):
        assert _pg_readonly(query), id
        cases.append(dict(id=id,interface='sql',claim=purpose,query=query,note='new direct generic control'))

    def rest(id, body, purpose, endpoint='load'):
        cases.append(dict(id=id,interface='json',claim=purpose,query=body,endpoint=endpoint,note='new direct generic control'))

    # End-to-end period comparisons: no original question/query input.
    for grain in ('year','month'):
        if grain=='year':
            windows=(('2007-01-01','2008-01-01'),('2008-01-01','2009-01-01'))
            values=('2007','2008')
            keys=(('calendar', 'calendar."CalendarYear"', 'sales CROSS JOIN calendar'),
                  ('outer_extract', 'EXTRACT(YEAR FROM p)', 'sales'))
        else:
            windows=(('2007-02-01','2007-03-01'),('2007-03-01','2007-04-01'))
            values=("DATE '2007-02-01'","DATE '2007-03-01'")
            keys=(('month_bucket', 'p', 'sales'),)
        for label,key,source in keys:
            interval=f'sales."DateKey" >= DATE \'{windows[0][0]}\' AND sales."DateKey" < DATE \'{windows[1][1]}\''
            if label=='calendar':
                first=f'SELECT sales."channelKey" AS group_key,{key} AS period_key,MEASURE(sales.sales_amount) AS period_value FROM {source} WHERE {interval} GROUP BY 1,2'
                prefix=f'WITH periods AS ({first})'
            else:
                first=f'SELECT sales."channelKey" AS group_key,DATE_TRUNC(\'{grain}\',sales."DateKey") AS p,MEASURE(sales.sales_amount) AS period_value FROM sales WHERE {interval} GROUP BY 1,2'
                prefix=f'WITH buckets AS ({first}), periods AS (SELECT group_key,{key} AS period_key,period_value FROM buckets)'
            split=f"SELECT group_key,SUM(CASE WHEN period_key={values[0]} THEN period_value ELSE 0 END) AS older_value,SUM(CASE WHEN period_key={values[1]} THEN period_value ELSE 0 END) AS newer_value FROM periods GROUP BY group_key"
            query=prefix+f', split_values AS ({split}) SELECT group_key,older_value,newer_value,CAST(newer_value AS DOUBLE PRECISION)/NULLIF(older_value,0) AS ratio,(CAST(newer_value AS DOUBLE PRECISION)-older_value)/NULLIF(older_value,0) AS growth FROM split_values ORDER BY group_key'
            sql('R_period_case_'+grain+'_'+label,query,'SQL L52: period group → conditional sums → outer division, direct end-to-end check')
        a=f'SELECT sales."channelKey" AS older_key,MEASURE(sales.sales_amount) AS older_value FROM sales WHERE sales."DateKey" >= DATE \'{windows[0][0]}\' AND sales."DateKey" < DATE \'{windows[0][1]}\' GROUP BY 1'
        b=f'SELECT sales."channelKey" AS newer_key,MEASURE(sales.sales_amount) AS newer_value FROM sales WHERE sales."DateKey" >= DATE \'{windows[1][0]}\' AND sales."DateKey" < DATE \'{windows[1][1]}\' GROUP BY 1'
        for join in ('JOIN','FULL OUTER JOIN'):
            sql('R_period_join_'+grain+'_'+join.replace(' ','_'),f'WITH older AS ({a}),newer AS ({b}) SELECT COALESCE(older_key,newer_key) AS group_key,older_value,newer_value,CAST(newer_value AS DOUBLE PRECISION)/NULLIF(older_value,0) AS ratio,(CAST(newer_value AS DOUBLE PRECISION)-older_value)/NULLIF(older_value,0) AS growth FROM older {join} newer ON older_key=newer_key ORDER BY group_key','SQL L53: distinct-period CTEs with disjoint output names + join + division')
    for grouped in (True,False):
        select='sales."channelKey" AS k,' if grouped else ''
        group=' GROUP BY 1' if grouped else ''
        key='k,' if grouped else ''
        sql('R_ratio_'+str(grouped),f'WITH a AS (SELECT {select}MEASURE(sales.sales_amount) AS numerator,MEASURE(sales.sales_quantity) AS denominator FROM sales WHERE {PERIOD}{group}) SELECT {key}numerator,denominator,CAST(numerator AS DOUBLE PRECISION)/NULLIF(denominator,0) AS quotient FROM a'+(' ORDER BY k' if grouped else ''),'SQL L45: two different measures in one CTE → division, end-to-end')

    # Generic graph topologies from deployed model definitions, never from an evaluation item.
    for perm in itertools.permutations(('store','channel','calendar')):
        a,b,c=perm
        sql('R_star_right_'+'_'.join(perm),f'SELECT store."StoreKey",channel."ChannelName",calendar."CalendarYear",MEASURE(sales.sales_quantity) FROM {a} CROSS JOIN ({b} CROSS JOIN (sales CROSS JOIN {c})) WHERE {PERIOD} GROUP BY 1,2,3 ORDER BY 1,2,3 LIMIT 4','SQL L20: all six right-nested three-leaf star permutations')
    fields='product."ProductKey",product_subcategory."ProductSubcategoryKey",product_category."ProductCategoryKey",MEASURE(sales.sales_quantity)'
    sql('R_chain_flat',f'SELECT {fields} FROM sales CROSS JOIN product CROSS JOIN product_subcategory CROSS JOIN product_category WHERE {PERIOD} GROUP BY 1,2,3 ORDER BY 1,2,3 LIMIT 4','SQL L20/L66: connected three-dimension chain, flat form')
    sql('R_chain_reverse',f'SELECT {fields} FROM product_category CROSS JOIN product_subcategory CROSS JOIN product CROSS JOIN sales WHERE {PERIOD} GROUP BY 1,2,3 ORDER BY 1,2,3 LIMIT 4','SQL L66: reverse connected chain')
    sql('R_chain_right',f'SELECT {fields} FROM product CROSS JOIN (product_subcategory CROSS JOIN (sales CROSS JOIN product_category)) WHERE {PERIOD} GROUP BY 1,2,3 ORDER BY 1,2,3 LIMIT 4','SQL L20: same right nesting on non-star topology')
    for source in ('sales CROSS JOIN product CROSS JOIN product_subcategory','product_subcategory CROSS JOIN sales CROSS JOIN product'):
        sql('R_two_dims_'+('end' if source.startswith('sales') else 'middle'),f'SELECT product."ProductKey",product_subcategory."ProductSubcategoryKey",MEASURE(sales.sales_quantity) FROM {source} WHERE {PERIOD} GROUP BY 1,2 ORDER BY 1,2 LIMIT 4','SQL L19/L66: chain topology with two dimensions')
    sql('R_one_dim_indirect',f'SELECT product_category."ProductCategoryKey",MEASURE(sales.sales_quantity) FROM sales CROSS JOIN product_category WHERE {PERIOD} GROUP BY 1 ORDER BY 1 LIMIT 4','SQL L18: a model path may include unlisted intermediate cubes')

    for join in ('JOIN','LEFT JOIN'):
        sql('R_same_cte_alias_'+join.replace(' ','_'),f'WITH a AS ({BASE}),b AS ({BASE.replace("sales.sales_amount","sales.sales_quantity")}) SELECT a.k AS selected_key,a.v AS amount_value,b.v AS quantity_value FROM a {join} b ON a.k=b.k ORDER BY a.k','SQL L61: shared inner names, distinct outer names')
    sql('R_derived_key_renamed',f'WITH a AS ({BASE}),b AS (SELECT k AS selected_key FROM a GROUP BY k HAVING COUNT(*)>0) SELECT a.k,SUM(a.v) AS amount FROM a JOIN b ON a.k=b.selected_key GROUP BY a.k ORDER BY a.k','SQL L62: rename derived key only')
    sql('R_count_measure',f'SELECT COUNT(MEASURE(sales.sales_amount)) FROM sales WHERE {PERIOD}','SQL L9/L64: COUNT nested around MEASURE')
    sql('R_missing_group',f'SELECT sales."channelKey",MEASURE(sales.sales_amount) FROM sales WHERE {PERIOD}','SQL L9: selected dimensions must be grouped')
    sql('R_coalesce_actual_null',f'WITH a AS ({BASE}) SELECT k,COALESCE(CASE WHEN k=1 THEN CAST(NULL AS DOUBLE PRECISION) ELSE v END,0) AS filled FROM a ORDER BY k','SQL L55: column expression actually contains NULL')
    sql('R_case_actual_null',f'WITH a AS ({BASE}),b AS (SELECT k,CASE WHEN k=1 THEN CAST(NULL AS DOUBLE PRECISION) ELSE v END AS x FROM a) SELECT k,CASE WHEN x IS NULL THEN 0 ELSE x END FROM b ORDER BY k','SQL L55: CASE fill-zero actually takes NULL branch')
    sql('R_cumulative_unicode',f'WITH a AS ({BASE}) SELECT k AS "探针键",SUM(v) OVER (ORDER BY k ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS "探针累计" FROM a ORDER BY k','SQL L12/L48/L69: cumulative window + Chinese aliases')
    for fn in ('ROW_NUMBER','RANK'):
        first=f'SELECT sales."channelKey" AS group_key,sales."PromotionKey" AS item_key,MEASURE(sales.sales_quantity) AS value FROM sales WHERE {PERIOD} GROUP BY 1,2'
        for emit in (False,True):
            expression=f'{fn}() OVER (PARTITION BY group_key ORDER BY value DESC,item_key)'
            if emit:
                expression=f'CAST({expression} AS BIGINT)'
            fields='group_key,item_key,value'+(',n AS position' if emit else '')
            sql(f'R_per_group_{fn}_{emit}',f'WITH a AS ({first}),r AS (SELECT group_key,item_key,value,{expression} AS n FROM a) SELECT {fields} FROM r WHERE n<=2 ORDER BY group_key,n','SQL L38/L48: multiple genuine rows per group, with/without returned rank')

    # Parse literal skeleton, then substitute only placeholders; never invent a solved example.
    skeleton_line=next(line for line in notes['render/syntax/cube_json.md'].splitlines() if line.startswith('- 例：'))
    raw_skeleton=skeleton_line.split('`',2)[1]
    skeleton=json.loads(raw_skeleton)
    mapping={'甲.指标':'sales.sales_amount','乙.维度':'channel.ChannelName','某值':'Store'}
    def substitute(value):
        if isinstance(value,str):
            return mapping.get(value,value)
        if isinstance(value,list):
            return [substitute(v) for v in value]
        if isinstance(value,dict):
            return {mapping.get(k,k):substitute(v) for k,v in value.items()}
        return value
    rest('R_json_skeleton',substitute(skeleton),'JSON L7: exact skeleton with placeholder-only substitution')
    rest('R_json_skeleton_literal',skeleton,'JSON L7: literal placeholders should be rejected, not a claim they execute')
    basic={'measures':['sales.sales_amount'],'dimensions':['sales.channelKey'],'order':{'sales.channelKey':'asc'},'limit':2}
    for key,value in (('offset',1),('timezone','UTC'),('join','x'),('expression','x'),('aliases',{'sales.sales_amount':'renamed'})):
        rest('R_json_extra_'+key,{**basic,key:value},'JSON L6/L9: other keys, actual allowed schema and aliases')
    rest('R_json_alias_member',{'measures':[{'name':'sales.sales_amount','alias':'renamed'}]},'JSON L8/L9: cannot alias a member via object element')
    rest('R_json_limit_float',{**basic,'limit':1.5},'JSON L6: limit integer type')
    rest('R_json_limit_string',{**basic,'limit':'2'},'JSON L6: numeric string coercion vs stated client type')
    rest('R_json_limit_group',{'measures':['sales.sales_quantity'],'dimensions':['sales.channelKey','sales.PromotionKey'],'order':{'sales.channelKey':'asc','sales.sales_quantity':'desc'},'limit':2},'JSON L17: global result limit, not N for each group')
    rest('R_json_limit_per_group',{**basic,'limitPerGroup':2},'JSON L17: unsupported per-group limit field')
    rest('R_json_set_nonempty',{**basic,'filters':[{'member':'sales.channelKey','operator':'set','values':['1']}]},'JSON L13: is empty values a required condition or safe convention?')
    for op in ('beforeDate','afterDate','inDateRange'):
        values=['2007-02-02'] if op!='inDateRange' else ['2007-02-01','2007-02-02']
        rest('R_json_compiled_'+op,{**basic,'filters':[{'member':'sales.DateKey','operator':op,'values':values}]},'JSON L13: inspect compiled temporal boundaries without adding data',endpoint='sql')
    return cases,dict(literal=raw_skeleton,parsed=skeleton,substitution=mapping,substituted=substitute(skeleton))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ref',default='origin/T12-cube-notes')
    ap.add_argument('--run-id',required=True)
    ap.add_argument('--timeout',type=int,default=120)
    ap.add_argument('--report-only',action='store_true')
    args=ap.parse_args()
    if args.report_only:
        report(ROOT/'reports/validation'/args.run_id)
        return
    commit=subprocess.check_output(['git','rev-parse',args.ref+'^{commit}'],cwd=ROOT,text=True).strip()
    target=ROOT/'reports/validation'/args.run_id
    target.mkdir(exist_ok=False)
    notes={p:subprocess.check_output(['git','show',commit+':'+p],cwd=ROOT).decode() for p in FILES}
    for path,content in notes.items():
        (target/Path(path).name).write_text(content)
    extra,skeleton=additions(notes)
    cases=manifest()+followup_manifest()+boundary_manifest()+type_control_manifest()+extra
    assert len({c['id'] for c in cases})==len(cases)
    payload=json.dumps(cases,ensure_ascii=False,indent=2).encode()
    (target/'manifest.json').write_bytes(payload)
    meta=dict(notes_ref=args.ref,notes_commit=commit,manifest_sha256=digest(payload),
              notes_sha256={p:digest(t.encode()) for p,t in notes.items()},skeleton=skeleton,
              script_sha256=digest(Path(__file__).read_bytes()),
              deployed_model_sha256={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted((ROOT/'build/cube/model').rglob('*.yml'))},
              counts=dict(legacy=180,new=len(extra),total=len(cases)),model_calls=0)
    (target/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    print(f'notes={commit}; legacy=180 new={len(extra)} total={len(cases)}; manifest={digest(payload)}',flush=True)
    with (target/'results.jsonl').open('x') as stream:
        for i,case in enumerate(cases,1):
            if case['interface']=='sql':
                result=asyncio.run(sql_result(case['query'],args.timeout))
            elif case.get('endpoint')=='sql':
                req=urllib.request.Request('http://127.0.0.1:14000/cubejs-api/v1/sql',data=json.dumps({'query':case['query']}).encode(),headers={'Content-Type':'application/json'})
                try:
                    with urllib.request.urlopen(req,timeout=args.timeout) as response:
                        result=dict(ok=True,payload=json.load(response))
                except urllib.error.HTTPError as exc:
                    result=dict(ok=False,error=exc.read().decode(),status=exc.code)
            else:
                r=CubeJsonExecutor(timeout_s=args.timeout).execute(json.dumps(case['query']))
                if r.error_class=='transport_error':
                    raise RuntimeError('Local REST transport failed; stop review')
                result=dict(ok=r.ok,rows=r.rows,columns=r.columns,error=r.error,detail=r.detail,error_class=r.error_class)
            stream.write(json.dumps({**case,'result':result},ensure_ascii=False,default=str)+'\n')
            stream.flush()
            print(f'[{i}/{len(cases)}] {case["id"]}: {"OK" if result["ok"] else "ERROR"}',flush=True)


def report(target):
    from data.clickhouse_t16 import query as physical

    metadata=json.loads((target/'metadata.json').read_text())
    frozen=json.loads((target/'manifest.json').read_text())
    rows=[json.loads(s) for s in (target/'results.jsonl').read_text().splitlines()]
    assert len(rows)==len(frozen)==229
    assert digest((target/'manifest.json').read_bytes())==metadata['manifest_sha256']
    assert all(all(row[k]==value for k,value in case.items()) for row,case in zip(rows,frozen))
    data={row['id']:row for row in rows}
    notes={p:(target/Path(p).name).read_text() for p in FILES}
    extra,skeleton=additions(notes)
    assert frozen==manifest()+followup_manifest()+boundary_manifest()+type_control_manifest()+extra
    assert all(digest(notes[p].encode())==h for p,h in metadata['notes_sha256'].items())

    def eq(a,b):
        if a is None or b is None:
            return a is b
        try:
            return math.isclose(float(a),float(b),rel_tol=1e-8,abs_tol=1e-6)
        except (TypeError,ValueError):
            return a==b

    def eqrows(a,b):
        return len(a)==len(b) and all(len(x)==len(y) and all(eq(v,w) for v,w in zip(x,y)) for x,y in zip(a,b))

    where="DateKey >= '2007-02-01' AND DateKey < '2007-03-01'"
    queries={
        'year':"SELECT channelKey,toYear(DateKey),sum(SalesAmount) FROM retail.FactSales WHERE DateKey >= '2007-01-01' AND DateKey < '2009-01-01' GROUP BY 1,2 ORDER BY 1,2",
        'month':"SELECT channelKey,toMonth(DateKey),sum(SalesAmount) FROM retail.FactSales WHERE DateKey >= '2007-02-01' AND DateKey < '2007-04-01' GROUP BY 1,2 ORDER BY 1,2",
        'ratio':f'SELECT channelKey,sum(SalesAmount),sum(SalesQuantity) FROM retail.FactSales WHERE {where} GROUP BY 1 ORDER BY 1',
        'star':"SELECT f.StoreKey,c.ChannelName,toYear(f.DateKey),sum(f.SalesQuantity) FROM retail.FactSales f LEFT JOIN retail.DimChannel c ON f.channelKey=c.ChannelKey WHERE f.DateKey >= '2007-02-01' AND f.DateKey < '2007-03-01' GROUP BY 1,2,3 ORDER BY 1,2,3 LIMIT 4",
        'chain':"SELECT p.ProductKey,s.ProductSubcategoryKey,c.ProductCategoryKey,sum(f.SalesQuantity) FROM retail.FactSales f LEFT JOIN retail.DimProduct p ON f.ProductKey=p.ProductKey LEFT JOIN retail.DimProductSubcategory s ON p.ProductSubcategoryKey=s.ProductSubcategoryKey LEFT JOIN retail.DimProductCategory c ON s.ProductCategoryKey=c.ProductCategoryKey WHERE f.DateKey >= '2007-02-01' AND f.DateKey < '2007-03-01' GROUP BY 1,2,3 ORDER BY 1 ASC NULLS LAST,2 ASC NULLS LAST,3 ASC NULLS LAST LIMIT 4 SETTINGS join_use_nulls=1",
        'promotions':f'SELECT channelKey,PromotionKey,sum(SalesQuantity) FROM retail.FactSales WHERE {where} GROUP BY 1,2 ORDER BY 1,3 DESC,2',
        'json_limit':'SELECT channelKey,PromotionKey,sum(SalesQuantity) FROM retail.FactSales GROUP BY 1,2 ORDER BY 1,3 DESC LIMIT 2',
        'store_total':"SELECT sum(SalesAmount) FROM retail.FactSales WHERE channelKey=1",
    }
    refs={k:json.loads(physical(q+' FORMAT JSONCompact'))['data'] for k,q in queries.items()}
    baseline_dir=Path(os.environ['SEMDEBT_DATA_DIR'])/'interface-probes'/target.name
    baseline_dir.mkdir(parents=True,exist_ok=True)
    (baseline_dir/'references.json').write_text(json.dumps(dict(queries=queries,rows=refs),ensure_ascii=False,indent=2)+'\n')
    checks={}

    def check(id,expected,basis):
        result=data[id]['result']
        checks[id]=dict(ok=result['ok'] and eqrows(result.get('rows') or [],expected),expected=expected,basis=basis)

    for kind,periods in [('year',(2007,2008)),('month',(2,3))]:
        grouped={}
        for k,p,v in refs[kind]:grouped.setdefault(k,{})[p]=v
        expected=[]
        for k,values in sorted(grouped.items()):
            a,b=values.get(periods[0],0),values.get(periods[1],0)
            expected.append([k,a,b,None if not a else b/a,None if not a else (b-a)/a])
        for id in data:
            if id.startswith('R_period_case_'+kind) or id.startswith('R_period_join_'+kind):
                check(id,expected,'independent physical '+kind+' aggregates; both values, ratio and growth')
    ratio=refs['ratio'];simple=[[r[0],r[1]] for r in ratio]
    check('R_ratio_True',[[k,a,b,a/b if b else None] for k,a,b in ratio],'two distinct physical aggregates, grouped division')
    a,b=sum(r[1] for r in ratio),sum(r[2] for r in ratio)
    check('R_ratio_False',[[a,b,a/b]],'global ratio of separate totals, not average of per-group ratios')
    for id in data:
        if id.startswith('R_star_right_'):check(id,refs['star'],'independent physical star, generic quantity metric')
    for id in ('R_chain_flat','R_chain_right'):check(id,refs['chain'],'independent physical chain')
    for id in ('R_two_dims_end','R_two_dims_middle'):check(id,[[r[0],r[1],r[3]] for r in refs['chain']],'same chain with final dimension omitted')
    for id in ('R_same_cte_alias_JOIN','R_same_cte_alias_LEFT_JOIN'):check(id,ratio,'inner duplicate names with distinct outer output names')
    check('R_derived_key_renamed',simple,'renamed derived key preserves grouped sum')
    for id in ('R_coalesce_actual_null','R_case_actual_null'):check(id,[[k,0 if k==1 else a] for k,a,b in ratio],'actual NULL branch filled with zero')
    ranked=[]
    groups={}
    for k,p,v in refs['promotions']:groups.setdefault(k,[]).append([k,p,v])
    for k,group in sorted(groups.items()):
        ranked.extend([r+[i+1] for i,r in enumerate(sorted(group,key=lambda r:(-r[2],r[1]))[:2])])
    for fn in ('ROW_NUMBER','RANK'):
        check('R_per_group_'+fn+'_True',ranked,'independent groups with unique ordering keys, actual top2 + returned rank')
        check('R_per_group_'+fn+'_False',[r[:3] for r in ranked],'same top2 with native rank only used as filter')
    check('R_json_skeleton',[['Store',refs['store_total'][0][0]]],'literal skeleton parsed; only placeholder names substituted')
    check('R_json_limit_group',refs['json_limit'],'two global rows, not two for each channel')
    # Inspect compiled filters to check the whole-day wording, not merely midnight data.
    for op,params in [('beforeDate',['2007-02-02T00:00:00.000Z']),('afterDate',['2007-02-02T23:59:59.999Z']),('inDateRange',['2007-02-01T00:00:00.000Z','2007-02-02T23:59:59.999Z'])]:
        id='R_json_compiled_'+op
        actual=data[id]['result']['payload']['sql']['sql']
        checks[id]=dict(ok=actual[1]==params,parameters=actual[1],basis='compiled UTC boundary parameters, preserved SQL in raw result')
    # Replay all old numeric expectations that were persisted, using current results.
    previous=json.loads((ROOT/'reports/validation/t16_cube_capabilities.json').read_text())
    for id,c in previous['correctness_checks'].items():
        if 'expected' not in c:continue
        result=data[id]['result'];observed=result.get('rows') or []
        if id=='J04':
            cols=[x['name'] for x in result['columns']]
            observed=[[r[cols.index(n)] for n in ['calendar.CalendarYear','sales.sales_amount','online_sales.sales_amount']] for r in observed]
        checks['repeat_'+id]=dict(ok=result['ok'] and eqrows(observed,c['expected']),expected_bad=not c['ok'],basis='repeat persisted independent baseline expectation')
    assert all(x['ok'] for id,x in checks.items() if id.startswith('R_period_') or id.startswith('R_ratio_'))

    # Line numbers refer to the immutable note snapshots; each Chinese sentence gets its own row.
    sql_evidence={
        3:(['S01','S34_inner','R_chain_flat'],'条件不符','整体范围声明尚未满足：下列条目存在反例，不能整体签收。'),
        7:(['S01','S30'],'成立','只读约束；没有执行任何修改数据的语句。'),
        8:(['S01','S02'],'成立','当前模型中已有 cube/成员；未把任意物理表当 cube。'),
        9:(['S01','S03','R_count_measure','R_missing_group'],'成立','MEASURE 直接聚合正确；SUM/COUNT 嵌套及遗漏GROUP BY反例均报错。'),
        10:(['S01','F24'],'成立','只选一种标识符写法是安全规范；混写反例报错，不宣称所有无引号写法都不能执行。'),
        11:(['S01','S40'],'成立','字符串/DATE 字面量成立。'),
        12:(['T03','T04','T05','R_cumulative_unicode'],'成立','普通英文/中文投影成立；窗口输出中文别名的例外实际报错。'),
        16:(['F33','F34','R_chain_flat'],'成立','有预定义连接路径；原始cube普通ON被拒。'),
        17:(['S50_sales_store_channel','F32'],'成立','连接树和顺序确实影响路径。'),
        18:(['S20_like','R_one_dim_indirect'],'成立','已有路径；中间节点可以由引擎自动补齐。'),
        19:(['S50_store_sales_channel','S50_channel_sales_store','R_two_dims_middle'],'成立','这是已证实可用的充分写法，不是必要条件；链式图的事实放一端也有成功例。'),
        20:(['R_star_right_store_channel_calendar','R_chain_right','R_chain_flat'],'成立','右嵌套正例成立；同一行关于平铺的断言另列为不成立。'),
        21:(['F01','R_ratio_True'],'成立','同一事实的两个不同指标同层，数值核验。'),
        22:(['S52_sales_calendar_online_sales','S53','B01','B02'],'成立','部署中两销售事实的直接同层查询失败；分开聚合后按共有键JOIN/FULL JOIN值正确。仅作已验图形的说明，不是所有自定义模型的不可能性定理。'),
        23:(['J03','S50_store_sales_channel','R_chain_flat'],'成立','维度属性在MEASURE层带入，符合已验证的连接条件。'),
        27:(['S100','S101','S102','S103','S104'],'成立','五种时间分桶已复跑。'),
        28:(['F22','F23','R_period_case_year_calendar','R_period_case_year_outer_extract'],'成立','两种年份来源直接用到完整比较中核验。'),
        29:(['F23','R_period_case_year_calendar'],'成立','年份维度与MEASURE同层成立。'),
        30:(['F22','R_period_case_year_outer_extract'],'成立','先按年桶聚合再外层EXTRACT，并完成两年比较，数值一致。'),
        34:(['S01','R_period_join_month_JOIN'],'成立','>=起点、<下一起点的过滤值独立核验。'),
        35:(['S20_eq','S20_ne','S20_in','S20_between','S20_like','S20_null','S20_and_or'],'成立','列举的谓词与布尔组合复跑。'),
        36:(['S21'],'成立','HAVING MEASURE正例。'),
        37:(['S21'],'成立','别名排序、LIMIT与独立行序一致。'),
        38:(['R_per_group_ROW_NUMBER_True','R_per_group_ROW_NUMBER_False','R_per_group_RANK_True','R_per_group_RANK_False'],'成立','真实多行分组，外层名次筛选；含仅筛选/返回BIGINT两个变体，独立逐组排序核验。'),
        42:(['S30','S31','S32_cte','S32_subquery'],'成立','适用后续所列有限形态；不宣称任意普通SQL均可。'),
        44:(['S38','F20_round','F20_pct'],'成立','算术、CASE、ROUND百分比正例。'),
        45:(['R_ratio_True','R_ratio_False'],'成立','补齐直接组合：两个不同指标在一个CTE，再相除；分组及全局均核验。'),
        46:(['S32_cte','S33_cte','B24','B27','R_period_case_year_calendar'],'成立','SUM/AVG/MIN/MAX/COUNT、CASE重分组、条件聚合均有正例。'),
        47:(['S37'],'成立','累计窗口有数值正确的正例；无需转BIGINT。'),
        48:(['S35_ROW_NUMBER_native','S35_ROW_NUMBER_bigint','S35_RANK_native','S35_RANK_bigint','B11','B12','R_per_group_ROW_NUMBER_True','R_per_group_RANK_True','R_cumulative_unicode'],'成立','排名需BIGINT输出，纯筛选可不转；有无PARTITION与外层改名均直接核验，英文别名条件成立。'),
        49:(['F02_distinct_alias','R_period_join_year_JOIN'],'成立','两边及外层列名不同是足够安全的规范；不是必要条件，不能据此说所有同名都一定错。'),
        50:(['F06'],'成立','IN半连接保留组内汇总值。'),
        51:(['R_period_case_year_calendar','R_period_case_month_month_bucket','R_period_join_year_JOIN','R_period_join_month_JOIN'],'成立','二种组合均完成年、月真实时期比较，遵守独立列名。'),
        52:(['R_period_case_year_calendar','R_period_case_year_outer_extract','R_period_case_month_month_bucket'],'成立','直接完整条件聚合拆列、再相除，两个值及比值/增长率均对独立事实表。'),
        53:(['R_period_join_year_JOIN','R_period_join_month_JOIN','R_period_join_year_FULL_OUTER_JOIN'],'成立','两个CTE各取不同期间，按相同含义但不同列名键连接；两列、比值及增长率正确。'),
        54:(['S40','R_ratio_True'],'成立','整数截断、DOUBLE、NULLIF零保护与组合除法成立。'),
        55:(['R_coalesce_actual_null','R_case_actual_null'],'成立','不是只测非NULL输入，实际NULL分支填0正确。'),
        56:(['S42_bigint','S42_integer','S42_numeric','S42_decimal','S42_double','S42_text'],'成立','所列转换类型的标量形态均可用；不覆盖已明示禁忌的interval转换。'),
        60:(['S34_inner','F05'],'条件不符','该分组的两条禁忌都省略必要条件，有正反例，不可当作无条件断言。'),
        61:(['S34_inner','S34_left','R_same_cte_alias_JOIN','R_same_cte_alias_LEFT_JOIN'],'不成立','内层同名但外层给不同别名时两列都正确；原句没有这个条件，断言第二列必变成第一列不成立。'),
        62:(['F05','F06','R_derived_key_renamed'],'不成立','派生键不改名时确有错值，但只把派生键改名后JOIN再SUM可正确；原文无条件归纳不成立。'),
        63:(['S03','R_chain_flat','S37'],'条件不符','分组中的部分“会报错”断言过宽，须逐条看下列结论。'),
        64:(['S03','R_count_measure'],'成立','SUM和COUNT包MEASURE均实际报错。'),
        65:(['F33','F34'],'成立','原始cube的普通ON与聚合CTE接原始cube都报错。'),
        66:(['R_chain_flat','R_two_dims_end','F30_sales_store_channel_calendar'],'不成立','三维链式图平铺可成功；两维链式图事实放一端也可成功。星形图失败不可外推全部图形。'),
        67:(['S52_sales_online_sales_calendar','S52_sales_calendar_online_sales','S52_online_sales_sales_calendar','S52_online_sales_calendar_sales','S52_calendar_sales_online_sales','S52_calendar_online_sales_sales','S53','B03'],'成立','当前两销售事实直接同层的所有已列顺序/嵌套均失败；不外推未部署模型。'),
        68:(['S11','F22'],'成立','同层EXTRACT+MEASURE失败，外层EXTRACT正例成立。'),
        69:(['S37','S35_ROW_NUMBER_native','S35_RANK_native','T05','R_cumulative_unicode'],'不成立','前半句泛称窗口函数需BIGINT，SUM累计窗口无需转且正确；后半句中文窗口别名禁忌成立，分开记录。'),
        70:(['F20_coalesce','F20_coalesce_cast','B22'],'成立','NULL常量第一参数反例持续报错。'),
        71:(['S61','F41'],'成立','Float64纯SQL控制仍明确execution未实现。'),
        72:(['T01','T02'],'成立','时间戳之差AVG与CAST到Float64均直接失败。'),
    }
    json_evidence={
        3:(['J01','R_json_extra_offset'],'条件不符','全局实测承诺未满足，存在额外键断言反例。'),
        5:(['J01','J02','J30','J31','R_json_skeleton_literal'],'成立','这是成员各部分的命名及模型存在性规则，点号是cube/member分隔符；占位骨架须替换名字。'),
        6:(['J01','R_json_limit_float','R_json_limit_string','R_json_extra_offset','R_json_extra_timezone','R_json_extra_join','R_json_extra_expression'],'成立','列举键及limit整数规则成立；关于所有其他键的第二句单列为不成立。'),
        7:(['R_json_skeleton','R_json_skeleton_literal'],'成立','原文骨架可JSON解析，替换占位名称及占位值后原结构原样通过且值正确；文字占位本身不是模型成员，预期报错不否定格式定义。'),
        8:(['J01','J21_or','J21_and','R_json_alias_member'],'成立','普通过滤元素结构成立；or/and容器由后文单列，不能把本句泛化成禁止那些容器。'),
        9:(['R_json_extra_aliases','R_json_alias_member','R_json_skeleton'],'成立','额外aliases键/成员别名对象被拒；返回以注解成员名命名。'),
        10:(['J01','J10_day','J10_month'],'成立','维度及时间桶分组正例。'),
        11:(['J03','J04','J05'],'成立','以模型已有连接路径为前提，双事实共享维度及多维正例成立；任意join键被拒。'),
        12:(['J10_day','J10_week','J10_month','J10_quarter','J10_year','J10_None'],'成立','复跑五粒度与无粒度；部分桶用旧独立日级基线核验，结果起点可越出筛选区间但值只来自区间。'),
        13:(['J20_equals','J20_notEquals','J20_contains','J20_notContains','J20_gt','J20_gte','J20_lt','J20_lte','J20_set','J20_notSet','J20_inDateRange','J20_beforeDate','J20_afterDate','R_json_compiled_beforeDate','R_json_compiled_afterDate','R_json_compiled_inDateRange'],'成立','13种运算；大小写例、字符串/空数组为安全客户端规范。编译SQL日期参数证明包含区间两端，before/after排除整天（UTC）；服务端也允许set非空数组，不影响此安全规范。'),
        14:(['J21_or','J21_and','J21_default'],'成立','默认AND、显式AND/OR的返回与谓词一致。'),
        15:(['J22'],'成立','指标filters正例。'),
        16:(['J01','J23'],'成立','对象及有序数组的行序正例。'),
        17:(['R_json_limit_group','R_json_limit_per_group'],'成立','实际多分组数据只返回全局2行；limitPerGroup被拒，不能用普通limit表达逐组N。'),
        18:(['J20_set','J20_notSet'],'成立','有值/无值筛选正例；当前字段非NULL，notSet为空符合基线。'),
        19:(['J30','J31','J32','J33'],'成立','临时指标、维度、expression键拒绝，预定义计算指标接受。'),
        20:(['J30','J31','J32','J33','R_json_limit_per_group'],'成立','只允许调用已定义成员；这里不是创造缺失的排名指标。表达能力结论限于一条既定成员JSON对象。'),
    }
    items=[]
    for path,evidence_map in [('render/syntax/cube_sql.md',sql_evidence),('render/syntax/cube_json.md',json_evidence)]:
        for line,text in enumerate(notes[path].splitlines(),1):
            if not text.strip() or text.startswith('#') or text.startswith('**'):continue
            assert line in evidence_map,(path,line,text)
            ids,status,reason=evidence_map[line]
            fragments=text.split('。')
            for n,sentence in enumerate(fragments,1):
                if not sentence:
                    continue
                state,why=status,reason
                if path.endswith('cube_sql.md') and line==20 and '平铺' in sentence:
                    state='不成立';why='链式三维图R_chain_flat平铺成功且数值正确；断言平铺都失败超出星形探针条件。'
                if path.endswith('cube_sql.md') and line==62 and sentence.startswith('要这样筛选'):
                    state='成立';why='IN写法成立，但为避免删除前句后留下无所指代的句子，删项补丁删除整条，不改写。'
                if path.endswith('cube_json.md') and line==6 and '其他键' in sentence:
                    state='不成立';why='offset和timezone都是未列出的键，但实际被接受；join/expression被拒不等于所有其他键都被拒。'
                assert all(id in data for id in ids)
                items.append(dict(file=path,line=line,sentence=n,text=sentence+('。' if n<len(fragments) else ''),status=state,evidence=ids,reason=why))
    deletions={
        'render/syntax/cube_sql.md':[
            '平铺的写法都找不到路径。',
            '- 能执行但算出错误的数（不报错，要特别避开）：\n'
            '  - 两个含 `MEASURE()` 的 CTE 用同一个输出列名（例如都叫 `v`），外层再用 `JOIN … ON` 或 `LEFT JOIN … ON` 连起来同时选出这两列：第二列会变成第一列的值。\n'
            '  - 一个聚合 CTE，和由它派生出来的 CTE（例如从它取出的键集合）`JOIN` 之后再 `SUM` / `GROUP BY`：每组得到的是全部的合计，不是本组的值。要这样筛选时改用上面的 `IN (SELECT …)`。\n',
            '  - 三个维度 cube 平铺 `CROSS JOIN`（任何顺序都不行）；两个维度 cube 时把它们写在相邻位置、事实 cube 放在一端。\n',
            '窗口函数的结果不转 `BIGINT` 就作为输出列；',
        ],
        'render/syntax/cube_json.md':['其他键（例如 `"join"`、`"expression"`）会被拒绝。'],
    }
    patches=[];candidates={}
    for path,chunks in deletions.items():
        candidate=notes[path]
        for text in chunks:
            assert candidate.count(text)==1,(path,text)
            candidate=candidate.replace(text,'',1)
        candidates[path]=candidate
        (target/(Path(path).stem+'.deletions-only.md')).write_text(candidate)
        patches.extend(difflib.unified_diff(notes[path].splitlines(True),candidate.splitlines(True),fromfile='a/'+path,tofile='b/'+path,n=0))
    (target/'deletions-only.patch').write_text(''.join(patches))
    # Apart from replacing the same physical line after substring deletion, no new rule text is introduced.
    from collections import Counter
    version=subprocess.check_output(['docker','compose','exec','-T','cube','node','-p',"require('@cubejs-backend/server/package.json').version"],cwd=ROOT,text=True).strip()
    assert version=='1.8.6'
    result=dict(notes_commit=metadata['notes_commit'],model_calls=0,probe_count=229,new_probes=49,
                versions=dict(cube=version,clickhouse=physical('SELECT version()')),
                report_script_sha256=digest(Path(__file__).read_bytes()),manifest_reproduced_by_final_script=True,
                error_text_redacted=False,
                statement_count=len(items),counts=dict(Counter(x['status'] for x in items)),items=items,
                numeric_checks=checks,required_combinations=[id for id in checks if id.startswith('R_period_') or id.startswith('R_ratio_')],
                deletion_candidates=deletions,review_passed=False,
                pending='The immutable reviewed revision still contains unsupported statements; apply deletion-only patch on T12 branch and recheck latest before semantic-v1.3.',
                results_sha256=digest((target/'results.jsonl').read_bytes()))
    (target/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# Cube 深度2写法说明逐句复核','',f"复核提交：`{metadata['notes_commit']}`（T12-cube-notes，包含已补回的格式骨架）。**该提交尚未复核通过，不应据此合并或打 semantic-v1.3。**",'',
           f"部署版本：Cube {version}，ClickHouse {result['versions']['clickhouse']}。本轮0模型调用。229个通用探针：180个原探针复跑、49个补充探针；不读题库、不取用任何作答。全文原始错误在results.jsonl，不脱敏、不截断。",
           f"逐句{len(items)}项：{result['counts']}。成立均限于注明模型/类型条件；条件不符用于整体声明尚有未满足前提，不把元声明当单条SQL探针。",'',
           '## 三个重点组合的直接验证','',
           '以下每个探针都直接执行完整组合，不再由单独探针拼接推断。独立基线为原始FactSales的年/月/数量与金额聚合，核对键集合、两列值、比值和增长率；tol=1e-8相对/1e-6绝对仅用于接口核验，不改评分器。',
           '| 探针 | 数值核对 | 依据 |','|---|---|---|']
    lines += [f"| `{id}` | {'通过' if checks[id]['ok'] else '**失败**'} | {checks[id]['basis']} |" for id in result['required_combinations']]
    lines += ['', '## 不成立项与删除方案','',
              '1. SQL连接部分“平铺的写法都找不到路径”：三个维度形成链时可平铺，星形图失败不能泛化。',
              '2. SQL同名CTE必然错值：外层明确不同别名后，内层同名仍可得到两列正确值。',
              '3. SQL聚合CTE与派生CTE互连再SUM必然全组误汇总：派生键改名的同类查询数值正确。',
              '4. SQL禁忌中“三维平铺任意顺序都不行、二维相邻且事实在一端不行”：链式图都有直接正例。',
              '5. SQL禁忌中所有窗口输出都要BIGINT：累计SUM的Float64窗口输出无需BIGINT，数值正确；ROW_NUMBER/RANK的已述规则仍成立。',
              '6. JSON“其他键都会拒绝”：offset/timezone被接受。只删除这个概括，不新增或教授额外键。','',
              'deletions-only.patch只删除上述内容；同名CTE/派生CTE小组删除后不保留空标题或悬空指代，没有改写成更窄规则。补丁为零上下文格式，先用 git apply --unidiff-zero --check，再用 git apply --unidiff-zero 应用；仅适用所录提交，最新内容有变化须重新核对。两份 *.deletions-only.md 是删除后的候选全文，不是已修改远端分支的证明。应用位置应为PR #130的T12-cube-notes，待并发修改协调。',
              '格式骨架保留原文：文字甲乙占位不是可执行成员；逐字JSON解析成立，替换占位名和值后按同一结构执行及数值核验通过。','',
              '## 逐句结论','', '| 文件:行/句 | 判定 | 原文 | 证据与条件 |','|---|---|---|']
    lines += [f"| {Path(x['file']).name}:{x['line']}/{x['sentence']} | **{x['status']}** | {x['text'].replace('|','&#124;')} | `{','.join(x['evidence'])}`；{x['reason']} |" for x in items]
    lines += ['', '## 独立数值与类型检查','', '| 项目 | 结果 | 依据 |','|---|---|---|']
    lines += [f"| `{id}` | {'通过' if x['ok'] else '已复现原有错值反例' if x.get('expected_bad') else '**未通过**'} | {x['basis']} |" for id,x in checks.items()]
    lines += ['', '## 固定证据与后续','',
              '- metadata.json记被审提交、两份说明及大纲/裁决哈希、部署模型哈希和格式骨架。manifest.json/results.jsonl固定本轮通用查询与完整响应；只读ClickHouse基线在外部数据目录interface-probes下。',
              '- 本脚本有--report-only入口，读取现有固定结果并重做独立物理聚合，绝不执行题目或模型调用。',
              '- 删除后应再核对T12分支最新提交；本报告不等于批准semantic-v1.3。用户合并、打tag之后，才以eval-v1.2+semantic-v1.3先dry-run、等批准、错峰重跑SQL/JSON冒烟。','']
    (target/'review.md').write_text('\n'.join(lines).rstrip()+'\n')
    print(json.dumps(dict(commit=metadata['notes_commit'],statements=len(items),counts=result['counts'],required_combinations=len(result['required_combinations']),required_all_passed=True,deletion_patch=str(target/'deletions-only.patch')),ensure_ascii=False))


if __name__=='__main__':
    main()
