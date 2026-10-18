"""Summarize independent Cube probes and audit the existing pilot errors.

This script never executes a model query or a pilot query. It executes only
fixed read-only ClickHouse validation aggregates, then reads recorded probes
and the original run's error files. No question bank is loaded.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from data.clickhouse_t16 import query as clickhouse  # noqa: E402
from scripts.probe_cube_interfaces_t16 import (  # noqa: E402
    manifest, followup_manifest, boundary_manifest, type_control_manifest,
)

VALIDATION = ROOT / 'reports/validation'
RUN = '20261019-T16-pilot-01'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + '\n')


def close(a, b):
    if a is None or b is None:
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=1e-8, abs_tol=1e-6)
    try:
        return math.isclose(float(a), float(b), rel_tol=1e-8, abs_tol=1e-6)
    except (TypeError, ValueError):
        return a == b


def equal(actual, expected):
    return len(actual) == len(expected) and all(len(a) == len(b) and all(close(x,y) for x,y in zip(a,b)) for a,b in zip(actual,expected))


def main():
    cases, manifests = {}, []
    for i, build_manifest in enumerate((manifest,followup_manifest,boundary_manifest,type_control_manifest),1):
        directory = VALIDATION / f't16-cube-capabilities-20261019-{i:02d}'
        manifest_bytes = (directory/'manifest.json').read_bytes()
        frozen_manifest = json.loads(manifest_bytes)
        assert frozen_manifest == build_manifest(), 'Current script must exactly reproduce each frozen query manifest'
        meta = json.loads((directory/'metadata.json').read_text())
        assert sha(manifest_bytes) == meta['manifest_sha256']
        results = [json.loads(s) for s in (directory/'results.jsonl').read_text().splitlines()]
        assert [r['id'] for r in results] == [r['id'] for r in frozen_manifest]
        for m,r in zip(frozen_manifest,results):
            assert all(r[k] == v for k,v in m.items())
            assert r['id'] not in cases
            cases[r['id']] = r
        manifests.append(dict(directory=str(directory.relative_to(ROOT)), cases=len(results), metadata=meta,
                              results_sha256=sha((directory/'results.jsonl').read_bytes())))

    # Independent aggregate baselines; all periods/member choices come from the probe manifest.
    where="DateKey >= '2007-02-01' AND DateKey < '2007-03-01'"
    queries={
        'channel_month':f'SELECT channelKey,sum(SalesAmount),sum(SalesQuantity) FROM retail.FactSales WHERE {where} GROUP BY channelKey ORDER BY channelKey',
        'store_month':f'SELECT StoreKey,sum(SalesAmount) FROM retail.FactSales WHERE {where} GROUP BY StoreKey ORDER BY StoreKey',
        'online_store_month':f'SELECT StoreKey,sum(SalesAmount) FROM retail.FactOnlineSales WHERE {where} GROUP BY StoreKey ORDER BY StoreKey',
        'channel_all':'SELECT channelKey,sum(SalesAmount) FROM retail.FactSales GROUP BY channelKey ORDER BY channelKey',
        'year_both':"SELECT 2007,(SELECT sum(SalesAmount) FROM retail.FactSales WHERE toYear(DateKey)=2007),(SELECT sum(SalesAmount) FROM retail.FactOnlineSales WHERE toYear(DateKey)=2007)",
        'star_month':"SELECT f.StoreKey,c.ChannelName,toYear(f.DateKey),sum(f.SalesAmount) FROM retail.FactSales f LEFT JOIN retail.DimChannel c ON f.channelKey=c.ChannelKey WHERE f.DateKey >= '2007-02-01' AND f.DateKey < '2007-03-01' GROUP BY 1,2,3 ORDER BY 1,2,3 LIMIT 4",
        'daily_month':f'SELECT toString(toDate(DateKey)),sum(SalesAmount) FROM retail.FactSales WHERE {where} GROUP BY 1 ORDER BY 1',
        'before_strict':"SELECT channelKey,sum(SalesAmount) FROM retail.FactSales WHERE DateKey < '2007-02-02' GROUP BY 1 ORDER BY 1",
        'before_inclusive':"SELECT channelKey,sum(SalesAmount) FROM retail.FactSales WHERE DateKey <= '2007-02-02' GROUP BY 1 ORDER BY 1",
        'after_strict':"SELECT channelKey,sum(SalesAmount) FROM retail.FactSales WHERE DateKey > '2007-02-27' GROUP BY 1 ORDER BY 1",
        'after_inclusive':"SELECT channelKey,sum(SalesAmount) FROM retail.FactSales WHERE DateKey >= '2007-02-27' GROUP BY 1 ORDER BY 1",
    }
    references={name:json.loads(clickhouse(q+' FORMAT JSONCompact'))['data'] for name,q in queries.items()}
    month=references['channel_month']
    simple=[[r[0],r[1]] for r in month]
    total=sum(r[1] for r in month)
    checks={}

    def check(id, expected, basis):
        r=cases[id]['result']
        checks[id]=dict(ok=r['ok'] and equal(r.get('rows') or [],expected), expected=expected, basis=basis)

    for id in ('S01','S30','S31','F06','B23'):
        check(id,simple,'ClickHouse channel_month')
    check('S02',[[total,sum(r[2] for r in month)]],'ClickHouse channel_month totals')
    for id in ('S32_cte','S32_subquery'):
        check(id,[[total]],'sum of complete grouped baseline')
    for id in ('S33_cte','S33_subquery'):
        check(id,[['a',sum(r[1] for r in month if r[0] in (1,2))],['b',sum(r[1] for r in month if r[0] not in (1,2))]],'regroup baseline keys')
    for id in ('S34_inner','S34_left','S34_cross_filter','F01','F02_same_alias','F02_distinct_alias','F03','F04'):
        check(id,month,'ClickHouse channel_month: amount and quantity must remain distinct')
    check('F05',simple,'one row per key in both inputs: join + group must preserve per-key totals')
    for id in ('S35_ROW_NUMBER_bigint','S35_RANK_bigint'):
        check(id,[[r[0],r[1],i] for i,r in enumerate(month,1)],'descending metric baseline has no ties; pg_oid=20')
    for fn in ('ROW_NUMBER','RANK'):
        check('F10_'+fn,simple[:2],'top two baseline values; window used only as filter')
        check('F11_'+fn,[[r[0],r[1],i] for i,r in enumerate(month[:2],1)],'top two with cast rank')
    check('S40',[[2,2.5,None]],'constant arithmetic')
    for op,pred in [('eq',lambda k:k==1),('ne',lambda k:k!=1),('in',lambda k:k in (1,2)),('between',lambda k:1<=k<=2),('null',lambda k:False),('and_or',lambda k:k in (1,2))]:
        check('S20_'+op,[r for r in simple if pred(r[0])],'independent grouped predicate')
    check('S21',sorted(simple,key=lambda r:-r[1])[:2],'HAVING all positive + alias DESC + LIMIT2')
    check('S37',[[r[0],r[1],sum(v[1] for v in month[:i+1])] for i,r in enumerate(month)],'cumulative sum over independent ordered groups')
    check('S38',[[r[0],1.0,'positive',r[1]] for r in month],'division, NULLIF, CASE and COALESCE(v,0)')
    check('F20_round',[[r[0],round(r[1],2)] for r in month],'numeric ROUND')
    check('F20_pct',[[r[0],100] for r in month],'metric divided by itself times 100')
    check('F22',[[2007,total]],'EXTRACT in outer materialized time bucket')
    check('F23',[[2007,total]],'calendar dimension alternative')
    check('F32',references['star_month'],'independent physical star join')
    for id in ('T03','T04','T06','T07'):
        check(id,simple,'ASCII/non-ASCII aliases do not change baseline values without window projection')
    sales=dict(references['store_month']); online=dict(references['online_store_month'])
    check('B01',[[k,sales.get(k),online.get(k)] for k in sorted(set(sales)|set(online))[:4]],'two separately aggregated fact baselines, FULL OUTER JOIN')
    check('B02',[[k,sales[k],online[k]] for k in sorted(set(sales)&set(online))[:4]],'two separately aggregated fact baselines, INNER JOIN')
    check('B25',[[r[0],r[1],r[1]] for r in month],'self CTE projection join')
    check('B26',[[r[0],r[1],r[1]] for r in month[:2]],'self CTE filtered branch join')
    check('B27',[[sum(r[1] for r in month[:2]),sum(r[1] for r in month[2:])]],'conditional SUM partitions')
    check('J01',references['channel_all'],'REST grouping and order vs independent physical aggregate')
    # REST annotation order need not equal requested member order. Match by member names.
    columns=[c['name'] for c in cases['J04']['result']['columns']]
    wanted=['calendar.CalendarYear','sales.sales_amount','online_sales.sales_amount']
    reordered=[[row[columns.index(name)] for name in wanted] for row in cases['J04']['result']['rows']]
    checks['J04']=dict(ok=equal(reordered,references['year_both']),expected=references['year_both'],
                      observed_column_order=columns,basis='independent fact totals, aligned by REST member annotation')

    # Native REST validation: inspect rows/keys/types without inventing new interface operations.
    names={1:'Store',2:'Online',3:'Catalog',4:'Reseller'}
    for op,pred in [('equals',lambda s:s=='Store'),('notEquals',lambda s:s!='Store'),('contains',lambda s:'o' in s.lower()),('notContains',lambda s:'o' not in s.lower()),('set',lambda s:s is not None),('notSet',lambda s:s is None)]:
        r=cases['J20_'+op]['result']; observed={x[0]:x[1] for x in r.get('rows') or []}
        expected={names[int(k)]:v for k,v in references['channel_all'] if pred(names[int(k)])}
        checks['J20_'+op]=dict(ok=r['ok'] and observed.keys()==expected.keys() and all(close(observed[k],v) for k,v in expected.items()),basis='independent channel totals and Python predicate')
    for op,pred in [('gt',lambda k:k>2),('gte',lambda k:k>=2),('lt',lambda k:k<2),('lte',lambda k:k<=2)]:
        check('J20_'+op,[r for r in references['channel_all'] if pred(r[0])],'independent numeric predicate')
    check('J21_or',references['channel_all'][:2],'OR of two disjoint equality filters')
    check('J21_and',[],'AND of two disjoint equality filters')
    check('J21_default',[],'default conjunction')
    check('J22',references['channel_all'],'measure HAVING > 0')
    check('J23',sorted(references['channel_all'],key=lambda r:(-r[1],r[0])),'array order semantics')
    check('J20_inDateRange',simple,'inclusive date interval vs independent physical aggregate')
    for id,variants in [('J20_beforeDate',('before_strict','before_inclusive')),('J20_afterDate',('after_strict','after_inclusive'))]:
        r=cases[id]['result']
        matches=[name for name in variants if equal(r['rows'],references[name])]
        checks[id]=dict(ok=r['ok'] and len(matches)==1,boundary_matches=matches,basis='compare strict and inclusive boundary independently')
    for grain in ('day','week','month','quarter','year',None):
        totals={}
        for stamp,value in references['daily_month']:
            d=datetime.fromisoformat(stamp)
            bucket=d if grain=='day' else d-timedelta(days=d.weekday()) if grain=='week' else d.replace(day=1) if grain=='month' else d.replace(month=1,day=1)
            key=bucket.strftime('%Y-%m-%d')
            totals[key]=totals.get(key,0)+value
        id='J10_'+str(grain); r=cases[id]['result']
        if grain is None:
            ok=equal(r['rows'],[[total]])
        else:
            ok=len(r['rows'])==min(4,len(totals)) and all(str(row[0])[:10] in totals and close(row[1],totals[str(row[0])[:10]]) for row in r['rows'])
        checks[id]=dict(ok=r['ok'] and ok,basis='independent daily fact totals, Python buckets, including partial boundary bucket')
        if grain:
            sql_id={'day':'S100','week':'S101','month':'S102','quarter':'S103','year':'S104'}[grain]
            result=cases[sql_id]['result']
            expected_keys=sorted(totals)[:4]
            actual=[[str(row[0])[:10],row[1]] for row in result['rows']]
            checks[sql_id]=dict(ok=equal(actual,[[k,totals[k]] for k in expected_keys]),basis='DATE_TRUNC grouping independently reconstructed from daily fact totals')
    baseline_archive=Path(os.environ['SEMDEBT_DATA_DIR'])/'interface-probes'/'t16-20261019'
    baseline_archive.mkdir(parents=True,exist_ok=True)
    save(baseline_archive/'independent-baselines.json',dict(queries=queries,rows=references))

    # Coverage is the actual numbered list in each frozen document (12 SQL, 9 JSON).
    coverage=[
        ('SQL-1','只读单条 SELECT','成立','S01','探针只发送只读 SELECT/WITH；写操作未执行，执行器边界另有既有测试。'),
        ('SQL-2','cube/成员对象','成立','S01,S02','已定义成员可查询；不能据此推断任意物理 SQL 也支持。'),
        ('SQL-3','MEASURE 与 GROUP BY','成立','S01,S02,S03','直接粒度的指标查询成立；SUM(MEASURE()) 同层嵌套反例失败，与说明一致。'),
        ('SQL-4','多个 cube 的 CROSS JOIN','有条件成立','S50_*,F30_*,F32,F33,S52_*,B01,B02,J03,J04','必须有可用模型路径，且 SQL 的树形括号/顺序影响路径；两个维度 6 种平铺仅2种成功；三个维度24种平铺均失败，右嵌套 F32 数值正确。双事实直接平铺失败，但分别聚合 CTE 后 B01/B02 可且数值正确。普通 ON 原始 cube 失败。'),
        ('SQL-5','Postgres 标识符与大小写','有条件成立','S01,S04,F24,T03,T04,T05,T06,T07','双引号大写成员和普通中文别名成立；大小写成员混合重复投影可失败。中文输出别名+窗口后处理 T05 生成空标识符，不能承诺全部遵循 Postgres。'),
        ('SQL-6','DATE/DATE_TRUNC/EXTRACT','有条件成立','S100,S101,S102,S103,S104,S11,F21,F22,F23','五粒度 DATE_TRUNC 与 DATE 字面量成立；EXTRACT 常量/外层桶成立，与 MEASURE 直接分组 S11 却触发引擎生成的未分组列错误。'),
        ('SQL-7','维度筛选/HAVING','成立','S20_*,S21','列举的维度运算、AND/OR、HAVING 在独立案例成立；组合到有缺陷的 CTE 不在此保证。'),
        ('SQL-8','ORDER BY 别名/LIMIT','成立','S01,S21','按指标别名排序及 LIMIT 成立。'),
        ('SQL-9','子查询/CTE 后算术、再聚合、排名、累计','有条件成立','S30,S31,S32_*,S33_*,S34_*,F01,F02_*,F03,F04,F05,F06,S35_*,F10_*,F11_*,S37,B01,B02,B24,T05','简单再聚合/累计成立；双 CTE 必须核对输出别名及数值，S34_inner/left 执行成功却把数量列替换为金额，cross_filter 数值正确；F05 再聚合得到每组总和而不是组内值。UInt64 窗口输出需 BIGINT；仅筛选不输出可成立。不能无限外推普通 SQL 组合。'),
        ('SQL-10','整数除法、DOUBLE、NULLIF','成立','S38,S40,S42_double','5/2=2，显式 DOUBLE=2.5，NULLIF 零分母得到 NULL。'),
        ('SQL-11','CASE/COALESCE','有条件成立','S38,F20_coalesce,F20_coalesce_cast,B22,B23','CASE 和 COALESCE(v,0) 成立；COALESCE(NULL,v) 即使 NULL 显式类型也触发数组长度错误，纯 VALUES 亦复现。'),
        ('SQL-12','ROUND 与乘100','成立','F20_round,F20_pct','数值舍入与百分比运算独立核验通过；S41 联合失败来自 COALESCE，而不是 ROUND。'),
        ('JSON-1','一个对象及已有成员','成立','J01,J02','模型成员正例通过，未知成员反例报错。'),
        ('JSON-2','列举的查询键','成立','J01,J10_*,J20_*,J23','列举键均接受；额外 join/expression 键被拒绝。'),
        ('JSON-3','示例对象结构','成立','J01,J20_equals,J23','使用部署中真实通用成员替代甲乙占位符，结构成立。'),
        ('JSON-4','分组及多 cube 自动连接','有条件成立','J01,J03,J04,J05','已有可连路径的维度星形与双事实成功；不能写任意 join 条件。多成员允许不等于所有无路径 cube 都可连接。'),
        ('JSON-5','时间维度、五粒度、不写粒度','成立','J10_*','五粒度及只区间过滤均对独立每日事实聚合重新分桶核验，含周/季度/年起始桶越出筛选区间的部分桶。'),
        ('JSON-6','13个过滤运算、字符串 values、AND/OR','成立','J20_*,J21_*,J24','全部运算正例和分组值对独立基线核验；contains 的 o 也匹配 Online，按本次观测不区分大小写。日期前/后边界对严格与含边界两份物理聚合独立辨别。服务端还接受数值 values 数组，不影响文档的更严格客户端规范。'),
        ('JSON-7','指标 filters/HAVING','成立','J22','指标正数过滤与独立汇总一致。'),
        ('JSON-8','对象/数组 order','成立','J01,J23','两种排序实际行序均与独立基线一致。'),
        ('JSON-9','不能临时表达式；只能定义好的计算','成立','J30,J31,J32,J33','临时指标表达式、临时维度、额外窗口表达式键均拒绝；预定义计算指标可执行。'),
        ('PERCENTILE_CONT','用户追加核验','不成立','S60,S61,S62,F40,F41','整数参数先被类型守卫拒绝；Float64 参数在纯 VALUES 中仍明确 execution is not implemented。仅指该函数实现，不证明分位数业务完全不可表达。'),
        ('CAST','用户追加核验','有条件成立','S42_*,S35_*_bigint,F11_*,S64,T01,T02','数字/文本及窗口 UInt64->BIGINT 成立；Interval(MonthDayNano)->Float64 明确不支持。'),
        ('AVG(interval)','审计类型对照','不成立','T01,T02,F42,F43','时间戳列之差的 AVG、转 Float64 不成立；DATE 常量被优化为天数时成立，不能以常量正例替代列类型测试。'),
    ]
    errors=[dict(id=x['id'],interface=x['interface'],error=x['result']['error'],sqlstate=x['result'].get('sqlstate')) for x in cases.values() if not x['result']['ok']]
    version=subprocess.check_output(['docker','compose','exec','-T','cube','node','-p',"require('@cubejs-backend/server/package.json').version"],cwd=ROOT,text=True).strip()
    versions=dict(cube=version,clickhouse=clickhouse('SELECT version()'))
    assert version=='1.8.6'
    result=dict(versions=versions,manifests=manifests,counts=dict(Counter(x['interface'] for x in cases.values())),
                probe_script_sha256=sha((ROOT/'scripts/probe_cube_interfaces_t16.py').read_bytes()),
                report_script_sha256=sha(Path(__file__).read_bytes()),
                all_frozen_manifests_reproduced=True,
                accepted=sum(x['result']['ok'] for x in cases.values()),errors=len(errors),
                correctness_checks=checks,coverage=[dict(id=i,claim=c,status=s,probes=p,conditions=n) for i,c,s,p,n in coverage],
                all_errors_verbatim=errors,baseline_queries=queries,
                baseline_archive='$SEMDEBT_DATA_DIR/interface-probes/t16-20261019/independent-baselines.json')
    save(VALIDATION/'t16_cube_capabilities.json',result)
    lines=['# T16 Cube 1.8.6 接口能力实测','',
           '本轮无模型调用，未执行任何题目查询；180 条探针全部来自语法说明、部署模型及通用控制。首批105条清单在读取18次冒烟报错前冻结；后续只隔离首批发现的类型、连接树、投影与数值问题。未改 render/、语义层、提示或评分器。','',
           f"- 版本：Cube `{version}`；ClickHouse `{versions['clickhouse']}`；Tesseract 已开启，配置未变。",
           f"- 共 {len(cases)} 个探针，SQL 146 / JSON 34；接受 {result['accepted']}、报错 {result['errors']}。接受不是正确性的同义词，独立数值对照见下文。",
           '- SQL 原始错误直接由 psycopg 捕获，保留完整 str(exception) 与 SQLSTATE，未使用运行器错误分类来决定能力；JSON 沿用现有执行器，其 error/detail 为收到的服务端错误。每个原始查询、结果及 OID 见四个目录的 manifest.json/results.jsonl。',
           '- 所有“成立”均限定为所列探针与条件，不是 SQL 语法全集证明；JSON 时间桶、日期边界、过滤、排序及双事实结果已对独立物理聚合核验。REST 列序按注解成员名对齐，不把列重排误判为错值。','',
           '## 逐条说明核验','', '| 条目 | 写法 | 判定 | 条件与证据 |','|---|---|---|---|']
    lines += [f'| {i} | {c} | **{s}** | {n} 证据：`{p}` |' for i,c,s,p,n in coverage]
    lines += ['', '## 执行成功但数值错误的反例','',
              '独立基线为 ClickHouse 原始事实表的通用聚合（2007-02，渠道分组），不是题库参考。容差 rel_tol=1e-8、abs_tol=1e-6，仅用于部署能力核验，不改实验评分。',
              '- `S34_inner/left`：两个 CTE 都把不同指标叫 v，且输出两个同名 v 时，第二列应为数量，却重复金额；cross_filter 数值正确，`F02_same_alias` 显式区分输出名后数值正确，`F02_distinct_alias` 也正确。因此不是“一概不能互连”。',
              '- `F05`：聚合 CTE 与其按键派生 CTE 互连后再 SUM，每组误得全部渠道合计；等价 IN 半连接 `F06` 数值正确。不能把执行成功当成有效 SQL 后处理。',
              '- `B01/B02` 跨事实的独立聚合 CTE 可互连且数值与物理事实表一致，故不得把直接多事实 CROSS JOIN 的失败外推为“两个事实永远无法同查”。','',
              '| 独立数值检查 | 通过 | 依据 |','|---|---|---|']
    lines += [f"| `{id}` | {'是' if check['ok'] else '**否**'} | {check['basis']} |" for id,check in checks.items()]
    lines += ['', '## 清单冻结与复现','',
              '探针脚本不导入 questions、client 或任何 runs/ 输入。清单与源码哈希、冻结语法文档哈希、模型文件哈希见各目录 metadata.json。脚本在本轮工作区分阶段扩展，metadata.commit 是仓库基线而不是新增脚本的提交号；各次源码哈希分别记录。最终脚本已逐个精确再生成四份冻结清单，报告 JSON 另记最终两份脚本哈希。逐轮审计由另一个脚本读取既有错误文件，绝不把模型查询作为探针执行。','', '```sh',
              'uv run python scripts/probe_cube_interfaces_t16.py --run-id <新的目录名> --suite base',
              '# 同法分别以 --suite followup / boundary / types 执行到不同的新目录',
              'uv run python scripts/report_cube_capabilities_t16.py','```','',
              '报告脚本默认读取本次四个固定目录，并只执行固定 ClickHouse SELECT 基线。新的探针 run-id 不得覆盖旧目录。原始基线行集另存数据目录 interface-probes，不入库。','',
              '## 逐条报错原文','', '成功查询无错误。以下为每个失败探针的完整错误文本，未按长度截断；成功结果、列 OID 和 Python 类型在 results.jsonl。','']
    for e in errors:
        lines += [f"### {e['id']}", '',f"SQLSTATE：`{e.get('sqlstate')}`。",'', '```text',e['error'],'```','']
    (VALIDATION/'t16_cube_capabilities.md').write_text('\n'.join(lines)+'\n')

    audit(cases)
    print(json.dumps({'probes':len(cases),'accepted':result['accepted'],'errors':result['errors'],
                      'numeric_checks':len(checks),'numeric_counterexamples':[k for k,v in checks.items() if not v['ok']]},ensure_ascii=False))


def audit(cases):
    doc='写法说明错误'; hard='接口确实做不到'; model='模型写错'
    # Primary attribution is local to the observed error; not a business impossibility proof.
    mapping={
        ('Q100',0):(hard,['F40','F41'],'PERCENTILE_CONT 的整数排序输入缺少隐式类型支持；显式 Float64 仍执行未实现。函数不在说明列举项内，不能将该错误归为模型没有遵守说明。'),
        ('Q100',1):(hard,['S60','S61','F41'],'已经显式 Float64，仍报 percentile_cont execution is not implemented；纯 SQL VALUES 同错，排除题目与 Cube 模型口径。'),
        ('Q102',0):(doc,['S50_sales_store_channel','F30_sales_store_channel_calendar','F32'],'说明 SQL-4 直接推荐多个 cube 平铺 CROSS JOIN，但未说明邻接边/连接树限制。该轮是同类 join-path 失败，不能据此指责模型或说业务无解。'),
        ('Q117',0):(doc,['S50_sales_store_channel','F30_sales_calendar_store_channel','F32'],'事实后相邻两个维度的平铺顺序在部署图上不能形成计划；文档未说明须调整树形。'),
        ('Q117',1):(doc,['S11','F22','F05','S35_ROW_NUMBER_bigint'],'该轮按说明使用 EXTRACT+MEASURE、多层 CTE 再聚合与窗口，却报不能识别 Cube 查询；独立探针证明这些组合有未说明的边界。不是精确最小复现，不能唯一定位复杂查询中首个失败节点，也不能声称没有合法替代形态。'),
        ('Q34',0):(doc,['B01','B02','F34','F33'],'文档 SQL-9 将聚合 CTE 后处理说成普通 SQL，但聚合 CTE 再接原始维度/维度 CTE 会被重写为 Cube 连接。双事实 CTE 本身在 B01/B02 成立，不能笼统归为多事实接口不支持；该复杂组合的因果定位为中等置信度。'),
        ('Q34',1):(doc,['S52_sales_online_sales_calendar','B03','B01','J04'],'两个事实加维度按 SQL-4 平铺，报 join path；通用控制证实平铺不可据任意顺序自动连接，而先分别聚合或用 REST 存在成功例。说明缺少连接形态条件，不能推出该业务一定不可做。'),
        ('Q50',0):(doc,['F05','F06','F34'],'聚合 CTE 与其派生键集合 JOIN 被规划器当成 Cube 原始连接，要求隐藏 join field；文档 SQL-9 未说明这种不再等价于普通关系 SQL 的重写边界。F05 同类通用连接甚至静默错值。'),
        ('Q50',1):(doc,['S11','F22','F23'],'输入按说明 EXTRACT(year,time) 与 MEASURE 分组，服务端生成 SQL 却引用未分组 saleskey；S11 在通用查询复现同类未分组内部列。输入并未选择该内部键，不是模型漏 GROUP BY 该列。'),
        ('Q71',0):(doc,['T05','T03','T04','F11_RANK'],'原输入的窗口 CTE 与带引号中文输出别名符合 SQL-5/9；错误中的空反引号标识符出现在服务端生成 SQL。T05 用通用中文别名+窗口独立复现同型错误；普通中文别名与 ASCII/CAST 窗口正例可用。'),
        ('Q73',0):(doc,['T05','B11','B12'],'服务端生成窗口投影的空标识符语法错误；通用 T05 复现，不是把模型输入 SQL 的语法错误误当执行器错误。中文别名/窗口组合和 UInt64 是可先后遮蔽的两个限制。'),
        ('Q73',1):(doc,['S35_ROW_NUMBER_native','S35_ROW_NUMBER_bigint','B11','B12'],'ROW_NUMBER 按说明输出，返回 UInt64 不能转 PostgreSQL 协议；显式 BIGINT 同类查询数值正确、OID20。文档没有要求这个必要转换，不能视为业务不可实现或模型无端写错。'),
        ('Q74',0):(doc,['S50_sales_store_channel','F30_sales_store_channel_calendar','F32'],'相邻维度的平铺 CROSS JOIN 找不到路径，属于 SQL-4 未说明的顺序/括号条件。'),
        ('Q74',1):(doc,['S35_ROW_NUMBER_native','S35_ROW_NUMBER_bigint'],'返回排名 UInt64 的响应变换失败，与通用窗口输出复现一致；BIGINT 正例说明不能按一条 unsupported 字符串认定接口整体无法排名。'),
        ('Q75',0):(doc,['S11','F22','F23'],'MEASURE 与 EXTRACT 分组触发内部 onlinesaleskey 未分组错误，模型输入没有引用该内部键。通用销售 cube 同样复现，说明 SQL-6/9 过宽。'),
        ('Q75',1):(doc,['F34','B01','B02','F02_distinct_alias'],'双聚合 CTE 再联接维度 CTE 报要求隐藏 __cubeJoinField；单纯双 CTE 并不总失败，问题在与原始维度拼接的混合计划形态。说明缺少此边界，未以题目查询作改写实测，归因机制为中等置信度。'),
        ('Q80',0):(hard,['T01','T02','F42','F43'],'时间戳列之差形成 Interval(MonthDayNano)，当前 AVG 不接受该类型，转 Float64 也不支持。纯字符串 VALUES 转 timestamp 独立复现；DATE 常量可优化为天数，不能反证列类型支持。仅认定该算子/类型组合做不到，不表示天数业务无其他写法。'),
        ('Q82',0):(model,['F33','F34'],'该轮对原始 employee cube 写普通 JOIN ... ON（另一侧是 CTE），违反 SQL-4 明示的 cube 连接不写 ON；通用直接 ON 与 CTE 接原始 cube 控制均被拒绝。这个主归类仅针对明确的写法约束违反，并不证明其余日期/聚合表达式没有接口边界。'),
    }
    log=ROOT/'runs'/RUN/'SQL-L2.jsonl'
    raw_root=Path(os.environ['SEMDEBT_DATA_DIR'])/'runs-raw'/RUN/'SQL-L2'
    source_hash=sha(log.read_bytes())
    assert source_hash=='60f2566162dcc895567a3eb5e445563027ccee03a9e76c1f5a6ff07822f28355'
    entries=[]
    for row in map(json.loads,log.read_text().splitlines()):
        for t in row['turns']:
            if t['exec']['status']!='error':
                continue
            key=(row['qid'],t['turn']); category,evidence,reason=mapping[key]
            file=f"{row['qid']}_r{row['rep']}_t{t['turn']}.exec.json"
            data=(raw_root/file).read_bytes()
            assert sha(data)==t['exec']['exec_raw_sha256']
            raw=json.loads(data)
            assert all(id in cases for id in evidence)
            entries.append(dict(qid=row['qid'],rep=row['rep'],turn=t['turn'],
                                original_error_class=t['exec']['error_class'],attribution=category,
                                evidence=evidence,reason=reason,error_verbatim=raw['error'],detail_verbatim=raw['detail'],
                                exec_raw_file=file,exec_sha256=sha(data),query_sha256=sha(t['query'].encode()),
                                final_attempt=row['final']['outcome'],confidence='中' if key in [('Q117',1),('Q34',0),('Q75',1)] else '高'))
    assert len(entries)==18 and set(mapping)=={(e['qid'],e['turn']) for e in entries}
    counts=dict(Counter(e['attribution'] for e in entries))
    audit=dict(source_run=RUN,source_log_sha256=source_hash,model_calls_added=0,count=18,counts=counts,
               policy='Only the immediate observed failure is classified. A document defect can describe a real engine restriction with a workable alternative; it is not counted as a proof of business impossibility.',
               entries=entries)
    save(VALIDATION/'t16_sql_pilot_error_audit.json',audit)
    lines=['# T16 SQL 冒烟18次执行报错重新归因','',
           '用户 2026-10-19 要求先实测，不选择保留或移至第二期。原日志只读、未改；本轮未重跑原题或原候选，也没有模型调用。以下依据冻结的通用探针及原始错误重归因，不改变评分器判定。','',
           '## 归因口径与汇总','',
           '- **写法说明错误**：包括明确不成立或遗漏必要条件、将有限 SQL 后处理泛化为普通 SQL。底层可以确有 bug 或限制，但如果可用条件/替代形态存在且说明未提示，不能直接计成“业务接口做不到”或模型错。',
           '- **接口确实做不到**：仅限已实测的函数实现或算子/类型组合，不是对整个业务任务的不可表达证明。',
           '- **模型写错**：有明确说明约束且实际输入违反；不因出现 not supported、生成 SQL 语法错误或引擎内部 GROUP BY 错误就归罪模型。',
           f"- 首要归因（互斥，仅用于这18次原始错误）：{counts}。复杂组合中存在多种潜在问题，表中列出置信度和因果边界。", 
           '- 最终失败的7条仍原样保留；其中6条的最终错误首要归因是说明/条件缺失，1条为 PERCENTILE_CONT 实现缺失。**原先自动分类的 4/7=57.1% 不再视为已经证实的能力限制比例，也不据新的主归类比例自动放行实验。** 用户尚未裁决，JSON 冒烟与全量暂停。',
           '- 后续正式运行固定使用用户指定的 eval-v1.2；旧 eval-v1.1 冒烟只作诊断，不能混入新版本正式结果。未修改 render/、语义层、提示或评分器；语法说明的任何更正须由 Claude Code 经用户裁决处理。','',
           '## 逐轮审计','', '| 题号/轮次 | 原自动类 | 首要归因 | 证据 | 依据与边界 | 置信度 |','|---|---|---|---|---|---|']
    lines += [f"| {e['qid']} / t{e['turn']} | {e['original_error_class']} | **{e['attribution']}** | `{','.join(e['evidence'])}` | {e['reason']} | {e['confidence']} |" for e in entries]
    lines += ['', '## 原始错误与哈希','',
              f'源日志 SHA-256：`{source_hash}`。以下 error 文本逐字取自 runs-raw 执行文件；JSON 同时保留 detail。未抄题面、参考答案或候选完整 SQL 作为独立探针；错误原文本身若包含 QUERY，则按用户要求保留其原文，不代表该查询被重新执行。','']
    for e in entries:
        lines += [f"### {e['qid']} t{e['turn']}", '',f"原执行文件：`{e['exec_raw_file']}`；SHA-256：`{e['exec_sha256']}`。",'', '```text',e['error_verbatim'],'```','']
    (VALIDATION/'t16_sql_pilot_error_audit.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(audit_errors=18,counts=counts,source_log_unchanged=source_hash),ensure_ascii=False))


if __name__=='__main__':
    main()
