"""Question-independent, read-only Cube 1.8.6 syntax capability probes.

No question bank, candidate query, reference answer or model client is loaded.
Freeze the manifest before auditing pilot errors. Results are append-only run
directories; unsupported statements are observations, not test-suite failures.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.executors import CubeJsonExecutor, _pg_readonly  # noqa: E402

PERIOD = 'sales."DateKey" >= DATE \'2007-02-01\' AND sales."DateKey" < DATE \'2007-03-01\''
BASE = f'SELECT sales."channelKey" AS k, MEASURE(sales.sales_amount) AS v FROM sales WHERE {PERIOD} GROUP BY 1'
DOCS = ("render/syntax/cube_sql.md", "render/syntax/cube_json.md")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest() -> list[dict]:
    out = []

    def sql(id, claim, query, note=""):
        assert _pg_readonly(query), id
        out.append(dict(id=id, interface="sql", claim=claim, query=query, note=note))

    def rest(id, claim, body, note=""):
        out.append(dict(id=id, interface="json", claim=claim, query=body, note=note))

    sql("S01", "SQL-1/2/3/5", BASE + " ORDER BY k LIMIT 4", "只读 SELECT、cube/成员、MEASURE、GROUP BY、双引号")
    sql("S02", "SQL-3", f'SELECT MEASURE(sales.sales_amount), MEASURE(sales.sales_quantity) FROM sales WHERE {PERIOD}')
    sql("S03", "SQL-3", f'SELECT SUM(MEASURE(sales.sales_amount)) FROM sales WHERE {PERIOD}', "文档明确禁止的反例")
    sql("S04", "SQL-5", 'SELECT sales.channelKey, MEASURE(sales.sales_amount) FROM sales GROUP BY 1 LIMIT 1', "大写成员未加引号的反例")
    for i, grain in enumerate(("day", "week", "month", "quarter", "year")):
        sql(f"S10{i}", "SQL-6", f"SELECT DATE_TRUNC('{grain}', sales.\"DateKey\") AS p, MEASURE(sales.sales_amount) AS v FROM sales WHERE {PERIOD} GROUP BY 1 ORDER BY 1 LIMIT 4")
    sql("S11", "SQL-6", f'SELECT EXTRACT(YEAR FROM sales."DateKey") AS y, MEASURE(sales.sales_amount) FROM sales WHERE {PERIOD} GROUP BY 1')
    predicates = {
        "eq": 'sales."channelKey" = 1', "ne": 'sales."channelKey" <> 1',
        "in": 'sales."channelKey" IN (1, 2)', "between": 'sales."channelKey" BETWEEN 1 AND 2',
        "null": 'sales."channelKey" IS NULL',
        "and_or": '(sales."channelKey" = 1 OR sales."channelKey" = 2) AND sales."channelKey" <> 4',
    }
    for name, predicate in predicates.items():
        sql("S20_" + name, "SQL-7", BASE.replace(" GROUP BY", " AND " + predicate + " GROUP BY") + " ORDER BY k LIMIT 4")
    sql("S20_like", "SQL-7", 'SELECT channel."ChannelName", MEASURE(sales.sales_amount) FROM sales CROSS JOIN channel WHERE channel."ChannelName" LIKE \'%o%\' GROUP BY 1 ORDER BY 1 LIMIT 4')
    sql("S21", "SQL-7/8", BASE + " HAVING MEASURE(sales.sales_amount) > 0 ORDER BY v DESC LIMIT 2")
    sql("S30", "SQL-9", f"WITH a AS ({BASE}) SELECT k, v FROM a ORDER BY k")
    sql("S31", "SQL-9", f"SELECT k, v FROM ({BASE}) a ORDER BY k")
    for name, source in (("cte", f"WITH a AS ({BASE}) "), ("subquery", "")):
        table = "a" if name == "cte" else f"({BASE}) a"
        sql("S32_" + name, "SQL-9", source + f"SELECT SUM(v) AS total FROM {table}", "MEASURE 结果外层再聚合")
        sql("S33_" + name, "SQL-9", source + f"SELECT CASE WHEN k IN (1,2) THEN 'a' ELSE 'b' END AS g, SUM(v) AS total FROM {table} GROUP BY 1 ORDER BY 1")
    other = BASE.replace("sales.sales_amount", "sales.sales_quantity")
    for name, join in (("inner", "a JOIN b ON a.k = b.k"), ("left", "a LEFT JOIN b ON a.k = b.k"), ("cross_filter", "a CROSS JOIN b WHERE a.k = b.k")):
        sql("S34_" + name, "SQL-9", f"WITH a AS ({BASE}), b AS ({other}) SELECT a.k, a.v, b.v FROM {join} ORDER BY a.k", "两个含 MEASURE 的 CTE 互连")
    for fn in ("ROW_NUMBER", "RANK"):
        for cast in (False, True):
            expr = f"{fn}() OVER (ORDER BY v DESC)"
            if cast:
                expr = f"CAST({expr} AS BIGINT)"
            sql(f"S35_{fn}_{'bigint' if cast else 'native'}", "SQL-9/CAST", f"WITH a AS ({BASE}) SELECT k, v, {expr} AS n FROM a ORDER BY k", "记录 PostgreSQL OID、Python 类型与原始报错")
        sql(f"S36_{fn}", "SQL-9", f"WITH a AS ({BASE}) SELECT k, {fn}() OVER (PARTITION BY k ORDER BY v DESC) AS n FROM a ORDER BY k")
    sql("S37", "SQL-9", f"WITH a AS ({BASE}) SELECT k, v, SUM(v) OVER (ORDER BY k ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running FROM a ORDER BY k")
    sql("S38", "SQL-9/10/11", f"WITH a AS ({BASE}) SELECT k, CAST(v AS DOUBLE PRECISION)/NULLIF(v,0), CASE WHEN v > 0 THEN 'positive' ELSE 'other' END, COALESCE(v,0) FROM a ORDER BY k")
    sql("S40", "SQL-10", "SELECT 5 / 2 AS integer_division, CAST(5 AS DOUBLE PRECISION) / 2 AS floating_division, 5 / NULLIF(0,0) AS zero_guard")
    sql("S41", "SQL-11/12", f"WITH a AS ({BASE}) SELECT k, ROUND(v,2), ROUND(v/NULLIF(v,0)*100,2), COALESCE(NULL,v) FROM a ORDER BY k")
    for name, cast_type in (("double", "DOUBLE PRECISION"), ("bigint", "BIGINT"), ("integer", "INTEGER"), ("numeric", "NUMERIC"), ("decimal", "DECIMAL(20,2)"), ("text", "TEXT")):
        sql("S42_" + name, "CAST", f"WITH a AS ({BASE}) SELECT k, CAST(v AS {cast_type}) AS converted FROM a ORDER BY k")
    for dims in (("store", "channel"), ("store", "channel", "calendar")):
        orderings = list(itertools.permutations(("sales",) + dims)) if len(dims) == 2 else [
            ("sales",) + p for p in itertools.permutations(dims)
        ] + [("store", "sales", "channel", "calendar"), ("store", "channel", "sales", "calendar"), ("store", "channel", "calendar", "sales")]
        fields = 'store."StoreKey", channel."ChannelName"' + (', calendar."CalendarYear"' if len(dims) == 3 else "")
        group = "1,2,3" if len(dims) == 3 else "1,2"
        for order in orderings:
            sql("S50_" + "_".join(order), "SQL-4", f"SELECT {fields}, MEASURE(sales.sales_amount) AS v FROM {' CROSS JOIN '.join(order)} WHERE {PERIOD} GROUP BY {group} ORDER BY {group} LIMIT 4", "同一组选中成员，只有 FROM 顺序变化")
    sql("S51", "SQL-4", f'SELECT store."StoreKey", channel."ChannelName", MEASURE(sales.sales_amount) AS v FROM sales CROSS JOIN store CROSS JOIN sales CROSS JOIN channel WHERE {PERIOD} GROUP BY 1,2 ORDER BY 1,2 LIMIT 4', "重复事实 cube 是否可作为路径提示；不作为推荐写法")
    for order in itertools.permutations(("sales", "online_sales", "calendar")):
        sql("S52_" + "_".join(order), "SQL-4/two-facts", f'SELECT calendar."CalendarYear", MEASURE(sales.sales_amount) AS a, MEASURE(online_sales.sales_amount) AS b FROM {" CROSS JOIN ".join(order)} WHERE calendar."CalendarYear" = 2007 GROUP BY 1 ORDER BY 1')
    sql("S53", "SQL-4/two-facts", 'SELECT MEASURE(sales.sales_amount), MEASURE(online_sales.sales_amount) FROM sales CROSS JOIN online_sales')
    sql("S60", "PERCENTILE_CONT", f"WITH a AS ({BASE}) SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY v) FROM a")
    sql("S61", "PERCENTILE_CONT", "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x) FROM (VALUES (1.0), (2.0), (3.0)) AS a(x)", "纯 SQL 控制，无 cube/MEASURE")
    sql("S62", "PERCENTILE_CONT", f'SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sales."SalesAmount") FROM sales WHERE {PERIOD}')
    sql("S63", "SQL-9", "SELECT ROW_NUMBER() OVER (ORDER BY x), RANK() OVER (ORDER BY x) FROM (VALUES (1),(2)) a(x)", "纯 SQL 窗口控制")
    sql("S64", "SQL-9/CAST", "SELECT CAST(ROW_NUMBER() OVER (ORDER BY x) AS BIGINT), CAST(RANK() OVER (ORDER BY x) AS BIGINT) FROM (VALUES (1),(2)) a(x)")

    basic = {"measures": ["sales.sales_amount"], "dimensions": ["sales.channelKey"], "order": {"sales.channelKey": "asc"}, "limit": 4}
    rest("J01", "JSON-1/2/3/4", basic)
    rest("J02", "JSON-1", {"measures": ["sales.not_a_member"]}, "只允许模型中已定义的成员；反例")
    rest("J03", "JSON-4", {"measures": ["sales.sales_amount"], "dimensions": ["store.StoreKey", "channel.ChannelName"], "limit": 4})
    rest("J04", "JSON-4", {"measures": ["sales.sales_amount", "online_sales.sales_amount"], "dimensions": ["calendar.CalendarYear"], "filters": [{"member": "calendar.CalendarYear", "operator": "equals", "values": ["2007"]}]})
    rest("J05", "JSON-4", {"measures": ["sales.sales_amount"], "dimensions": ["store.StoreKey"], "join": "store.StoreKey=sales.StoreKey", "limit": 4}, "任意连接键不会被执行为连接条件")
    for grain in ("day", "week", "month", "quarter", "year", None):
        td = {"dimension": "sales.DateKey", "dateRange": ["2007-02-01", "2007-02-28"]}
        if grain:
            td["granularity"] = grain
        rest("J10_" + str(grain), "JSON-5", {"measures": ["sales.sales_amount"], "timeDimensions": [td], "limit": 4})
    string_ops = {"equals": ["Store"], "notEquals": ["Store"], "contains": ["o"], "notContains": ["o"], "set": [], "notSet": []}
    for op, values in string_ops.items():
        rest("J20_" + op, "JSON-6", {"measures": ["sales.sales_amount"], "dimensions": ["channel.ChannelName"], "filters": [{"member": "channel.ChannelName", "operator": op, "values": values}], "limit": 4})
    for op in ("gt", "gte", "lt", "lte"):
        rest("J20_" + op, "JSON-6", {**basic, "filters": [{"member": "sales.channelKey", "operator": op, "values": ["2"]}]})
    for op, values in (("inDateRange", ["2007-02-01", "2007-02-28"]), ("beforeDate", ["2007-02-02"]), ("afterDate", ["2007-02-27"])):
        rest("J20_" + op, "JSON-6", {**basic, "filters": [{"member": "sales.DateKey", "operator": op, "values": values}]})
    conditions = [{"member": "sales.channelKey", "operator": "equals", "values": [str(i)]} for i in (1, 2)]
    for op in ("or", "and"):
        rest("J21_" + op, "JSON-6", {**basic, "filters": [{op: conditions}]})
    rest("J21_default", "JSON-6", {**basic, "filters": conditions})
    rest("J22", "JSON-7", {**basic, "filters": [{"member": "sales.sales_amount", "operator": "gt", "values": ["0"]}]})
    rest("J23", "JSON-8", {**basic, "order": [["sales.sales_amount", "desc"], ["sales.channelKey", "asc"]]})
    rest("J24", "JSON-6", {**basic, "filters": [{"member": "sales.channelKey", "operator": "equals", "values": [1]}]}, "非字符串 values 反例")
    rest("J30", "JSON-9", {"measures": ["sales.sales_amount + sales.sales_quantity"]}, "任意计算成员反例")
    rest("J31", "JSON-9", {"measures": ["sales.sales_amount"], "dimensions": ["CAST(sales.channelKey AS TEXT)"]}, "临时维度表达式反例")
    rest("J32", "JSON-9", {**basic, "expression": "ROW_NUMBER() OVER (ORDER BY sales.sales_amount)"}, "额外 expression 键是否拒绝或静默忽略")
    rest("J33", "JSON-9", {"measures": ["sales.average_unit_price"], "limit": 1}, "模型里已定义计算指标的正例")
    return out


def followup_manifest() -> list[dict]:
    """Controls isolating phenomena found by the first generic manifest.

    Different aliases, explicit casts, join shapes and constant expressions;
    never import or adapt a pilot candidate.
    """
    out = []

    def add(id, claim, query, note=""):
        assert _pg_readonly(query), id
        out.append(dict(id=id, interface="sql", claim=claim, query=query, note=note))

    add("F01", "SQL-9/reference", f'SELECT sales."channelKey" AS k, MEASURE(sales.sales_amount) AS amount, MEASURE(sales.sales_quantity) AS quantity FROM sales WHERE {PERIOD} GROUP BY 1 ORDER BY 1')
    amount = BASE.replace(" AS v", " AS amount")
    quantity = BASE.replace("sales.sales_amount", "sales.sales_quantity").replace(" AS v", " AS quantity")
    for name, a, b, av, bv in (("same_alias", BASE, BASE.replace("sales.sales_amount", "sales.sales_quantity"), "v", "v"), ("distinct_alias", amount, quantity, "amount", "quantity")):
        add("F02_" + name, "SQL-9", f"WITH a AS ({a}), b AS ({b}) SELECT a.k, a.{av} AS a_value, b.{bv} AS b_value FROM a JOIN b ON a.k=b.k ORDER BY a.k", "与 F01 按键比较两列数值，不只检查是否报错")
    add("F03", "SQL-9", f"WITH a AS ({amount}), b AS ({quantity}) SELECT a.k, a.amount, b.quantity FROM a FULL OUTER JOIN b ON a.k=b.k ORDER BY a.k")
    add("F04", "SQL-9", f"WITH a AS ({amount}), b AS ({quantity}), c AS (SELECT k, SUM(quantity) AS qty FROM b GROUP BY k) SELECT a.k,a.amount,c.qty FROM a JOIN c ON a.k=c.k ORDER BY a.k")
    add("F05", "SQL-9", f"WITH a AS ({BASE}), b AS (SELECT k FROM a GROUP BY k HAVING COUNT(*) > 0) SELECT a.k,SUM(a.v) FROM a JOIN b ON a.k=b.k GROUP BY a.k ORDER BY a.k")
    add("F06", "SQL-9", f"WITH a AS ({BASE}), b AS (SELECT k FROM a GROUP BY k HAVING COUNT(*) > 0) SELECT k,SUM(v) FROM a WHERE k IN (SELECT k FROM b) GROUP BY k ORDER BY k")
    for fn in ("ROW_NUMBER", "RANK"):
        add("F10_" + fn, "SQL-9", f"WITH a AS ({BASE}), b AS (SELECT k,v,{fn}() OVER (ORDER BY v DESC) AS n FROM a) SELECT k,v FROM b WHERE n <= 2 ORDER BY k", "窗口值只筛选、不作为输出列")
        add("F11_" + fn, "SQL-9/CAST", f"WITH a AS ({BASE}), b AS (SELECT k,v,CAST({fn}() OVER (ORDER BY v DESC) AS BIGINT) AS n FROM a) SELECT k,v,n FROM b WHERE n <= 2 ORDER BY k")
    for name, expr in (("round", "ROUND(v,2)"), ("pct", "ROUND(v/NULLIF(v,0)*100,2)"), ("coalesce", "COALESCE(NULL,v)"), ("coalesce_cast", "COALESCE(CAST(NULL AS DOUBLE PRECISION),v)")):
        add("F20_" + name, "SQL-11/12", f"WITH a AS ({BASE}) SELECT k,{expr} AS x FROM a ORDER BY k")
    add("F21", "SQL-6", "SELECT EXTRACT(YEAR FROM DATE '2007-02-01')")
    add("F22", "SQL-6", f'WITH a AS (SELECT DATE_TRUNC(\'year\',sales."DateKey") AS p, MEASURE(sales.sales_amount) AS v FROM sales WHERE {PERIOD} GROUP BY 1) SELECT EXTRACT(YEAR FROM p),v FROM a')
    add("F23", "SQL-6", f'SELECT calendar."CalendarYear", MEASURE(sales.sales_amount) FROM sales CROSS JOIN calendar WHERE {PERIOD} GROUP BY 1')
    add("F24", "SQL-5", 'SELECT sales.channelkey, sales."channelKey", MEASURE(sales.sales_amount) FROM sales GROUP BY 1,2 LIMIT 1')
    for order in itertools.permutations(("sales", "store", "channel", "calendar")):
        add("F30_" + "_".join(order), "SQL-4", f'SELECT store."StoreKey",channel."ChannelName",calendar."CalendarYear",MEASURE(sales.sales_amount) FROM {" CROSS JOIN ".join(order)} WHERE {PERIOD} GROUP BY 1,2,3 ORDER BY 1,2,3 LIMIT 4')
    add("F31", "SQL-4", f'SELECT store."StoreKey",channel."ChannelName",calendar."CalendarYear",MEASURE(sales.sales_amount) FROM (store CROSS JOIN sales) CROSS JOIN (channel CROSS JOIN calendar) WHERE {PERIOD} GROUP BY 1,2,3 ORDER BY 1,2,3 LIMIT 4')
    add("F32", "SQL-4", f'SELECT store."StoreKey",channel."ChannelName",calendar."CalendarYear",MEASURE(sales.sales_amount) FROM store CROSS JOIN (channel CROSS JOIN (sales CROSS JOIN calendar)) WHERE {PERIOD} GROUP BY 1,2,3 ORDER BY 1,2,3 LIMIT 4')
    add("F33", "SQL-4", f'SELECT store."StoreKey",MEASURE(sales.sales_amount) FROM sales JOIN store ON sales."StoreKey"=store."StoreKey" WHERE {PERIOD} GROUP BY 1 LIMIT 4', "明确违反说明中 cube 连接不写 ON 的反例")
    add("F34", "SQL-9", f'WITH a AS ({BASE}) SELECT a.k,a.v,channel."ChannelName" FROM a LEFT JOIN channel ON a.k=channel."ChannelKey" ORDER BY a.k', "聚合 CTE 后连接原始维度 cube")
    add("F40", "PERCENTILE_CONT", 'SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x) FROM (VALUES (1),(2),(3)) a(x)', "整数排序输入")
    add("F41", "PERCENTILE_CONT", 'SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY CAST(x AS DOUBLE PRECISION)) FROM (VALUES (1),(2),(3)) a(x)', "显式 Float64 排除参数类型问题")
    add("F42", "CAST", "SELECT AVG(DATE '2007-02-02' - DATE '2007-02-01') FROM (VALUES (1),(2)) a(x)", "日期差默认是 interval，AVG 的类型限制")
    add("F43", "CAST", "SELECT CAST(DATE '2007-02-02' - DATE '2007-02-01' AS DOUBLE PRECISION)", "interval 转浮点")
    return out


def boundary_manifest() -> list[dict]:
    """Small controls for result correctness and observed planner boundaries."""
    out = []

    def add(id, claim, query, note=""):
        assert _pg_readonly(query), id
        out.append(dict(id=id, interface="sql", claim=claim, query=query, note=note))

    a = f'SELECT sales."StoreKey" AS k, MEASURE(sales.sales_amount) AS av FROM sales WHERE {PERIOD} GROUP BY 1'
    b = 'SELECT online_sales."StoreKey" AS k, MEASURE(online_sales.sales_amount) AS bv FROM online_sales WHERE online_sales."DateKey" >= DATE \'2007-02-01\' AND online_sales."DateKey" < DATE \'2007-03-01\' GROUP BY 1'
    add('B01', 'SQL-4/9/two-facts', f'WITH a AS ({a}), b AS ({b}) SELECT COALESCE(a.k,b.k) AS k,a.av,b.bv FROM a FULL OUTER JOIN b ON a.k=b.k ORDER BY 1 LIMIT 4')
    add('B02', 'SQL-4/9/two-facts', f'WITH a AS ({a}), b AS ({b}) SELECT a.k,a.av,b.bv FROM a JOIN b ON a.k=b.k ORDER BY a.k LIMIT 4')
    add('B03', 'SQL-4/two-facts', 'SELECT calendar."CalendarYear",MEASURE(sales.sales_amount),MEASURE(online_sales.sales_amount) FROM sales CROSS JOIN (calendar CROSS JOIN online_sales) WHERE calendar."CalendarYear"=2007 GROUP BY 1')
    for cast in (False, True):
        for qualified in (False, True):
            value='RANK() OVER (PARTITION BY k ORDER BY v DESC)'
            if cast:
                value=f'CAST({value} AS BIGINT)'
            fields='r.k,r.label,r.v' if qualified else 'k,label,v'
            add(f'B10_{cast}_{qualified}', 'SQL-9', f'WITH a AS (SELECT store."StoreType" AS k,channel."ChannelName" AS label,MEASURE(sales.sales_amount) AS v FROM store CROSS JOIN sales CROSS JOIN channel WHERE {PERIOD} GROUP BY 1,2),r AS (SELECT k,label,v,{value} AS n FROM a) SELECT {fields} FROM r WHERE n=1 ORDER BY 1,2', '两个字符串分组列，排名只用于筛选')
    add('B11', 'SQL-9', f'WITH a AS ({BASE}), b AS (SELECT k,v,ROW_NUMBER() OVER (ORDER BY v DESC) AS n FROM a) SELECT n AS position,k AS grouping_key,v AS amount FROM b ORDER BY n LIMIT 2', '外层重命名窗口列')
    add('B12', 'SQL-9/CAST', f'WITH a AS ({BASE}), b AS (SELECT k,v,CAST(ROW_NUMBER() OVER (ORDER BY v DESC) AS BIGINT) AS n FROM a) SELECT n AS position,k AS grouping_key,v AS amount FROM b ORDER BY n LIMIT 2')
    add('B20', 'SQL-6/CAST', "SELECT AVG(b-a) FROM (VALUES (TIMESTAMP '2007-02-01 00:00:00',TIMESTAMP '2007-02-03 00:00:00'),(TIMESTAMP '2007-02-02 00:00:00',TIMESTAMP '2007-02-03 00:00:00')) t(a,b)")
    add('B21', 'SQL-6/CAST', "SELECT AVG(CAST(b-a AS DOUBLE PRECISION)) FROM (VALUES (TIMESTAMP '2007-02-01 00:00:00',TIMESTAMP '2007-02-03 00:00:00'),(TIMESTAMP '2007-02-02 00:00:00',TIMESTAMP '2007-02-03 00:00:00')) t(a,b)")
    add('B22', 'SQL-11', 'SELECT COALESCE(CAST(NULL AS DOUBLE PRECISION),x) FROM (VALUES (1.0),(2.0)) a(x)')
    add('B23', 'SQL-11', f'WITH a AS ({BASE}) SELECT k,CASE WHEN v IS NULL THEN 0 ELSE v END FROM a ORDER BY k')
    add('B24', 'SQL-9', f'WITH a AS ({BASE}) SELECT k,AVG(v),MIN(v),MAX(v),COUNT(*) FROM a GROUP BY k ORDER BY k')
    add('B25', 'SQL-9', f'WITH a AS ({BASE}),b AS (SELECT k,v FROM a) SELECT a.k,a.v AS av,b.v AS bv FROM a JOIN b ON a.k=b.k ORDER BY a.k')
    add('B26', 'SQL-9', f'WITH a AS ({BASE}),b AS (SELECT k,v FROM a WHERE k <= 2) SELECT a.k,a.v AS av,b.v AS bv FROM a JOIN b ON a.k=b.k ORDER BY a.k')
    add('B27', 'SQL-9', f'WITH a AS ({BASE}) SELECT SUM(CASE WHEN k <= 2 THEN v ELSE 0 END) AS lo,SUM(CASE WHEN k > 2 THEN v ELSE 0 END) AS hi FROM a')
    return out


def type_control_manifest() -> list[dict]:
    out = []

    def add(id, claim, query, note=""):
        assert _pg_readonly(query), id
        out.append(dict(id=id, interface='sql', claim=claim, query=query, note=note))

    dates="(VALUES ('2007-02-01','2007-02-03'),('2007-02-02','2007-02-03')) t(a,b)"
    add('T01', 'CAST/interval', f'SELECT AVG(CAST(b AS TIMESTAMP)-CAST(a AS TIMESTAMP)) FROM {dates}', '先从文本 VALUES cast，避开 typed TIMESTAMP literal 的 VALUES 限制')
    add('T02', 'CAST/interval', f'SELECT AVG(CAST(CAST(b AS TIMESTAMP)-CAST(a AS TIMESTAMP) AS DOUBLE PRECISION)) FROM {dates}')
    add('T03', 'SQL-5/9', f'WITH a AS ({BASE}) SELECT k AS "探针维度", v AS "探针数值" FROM a ORDER BY k')
    add('T04', 'SQL-5/9', f'WITH a AS ({BASE}) SELECT k AS "probe_key", v AS "probe_value" FROM a ORDER BY k')
    add('T05', 'SQL-5/9/CAST', f'WITH a AS ({BASE}) SELECT k AS "探针维度", v AS "探针数值", CAST(ROW_NUMBER() OVER (ORDER BY v DESC) AS BIGINT) AS "探针序号" FROM a ORDER BY k')
    add('T06', 'SQL-5', f'SELECT sales."channelKey" AS "探针维度",MEASURE(sales.sales_amount) AS "探针数值" FROM sales WHERE {PERIOD} GROUP BY 1 ORDER BY 1')
    add('T07', 'SQL-5', f'SELECT sales."channelKey" AS "probe_key",MEASURE(sales.sales_amount) AS "probe_value" FROM sales WHERE {PERIOD} GROUP BY 1 ORDER BY 1')
    return out


async def sql_result(query: str, timeout_s: int) -> dict:
    import psycopg

    start = time.monotonic()
    try:
        async def execute():
            conn = await psycopg.AsyncConnection.connect(
                host=os.environ.get("CUBE_SQL_HOST", "127.0.0.1"),
                port=int(os.environ.get("CUBE_SQL_PORT", "15432")),
                user=os.environ.get("CUBE_SQL_USER", "cube"),
                password=os.environ.get("CUBE_SQL_PASSWORD") or secrets.token_urlsafe(),
                dbname=os.environ.get("CUBE_SQL_DATABASE", "cube"), autocommit=True, connect_timeout=10,
            )
            async with conn:
                async with conn.cursor() as cur:
                    await cur.execute(query)
                    cols = [{"name": c.name, "pg_oid": c.type_code} for c in cur.description]
                    rows = await cur.fetchmany(1001)
                    if len(rows) > 1000:
                        raise ValueError("Probe exceeded 1000 rows; reduce the generic query")
                    return {"ok": True, "columns": cols, "rows": rows,
                            "python_types": [type(v).__name__ for v in rows[0]] if rows else []}
        result = await asyncio.wait_for(execute(), timeout_s)
    except psycopg.OperationalError as exc:
        if not exc.sqlstate:
            raise RuntimeError("Cube SQL transport failure; stop the capability run") from None
        result = {"ok": False, "error": str(exc), "sqlstate": exc.sqlstate}
    except psycopg.Error as exc:
        result = {"ok": False, "error": str(exc), "sqlstate": exc.sqlstate}
    except TimeoutError:
        result = {"ok": False, "error": "Probe deadline exceeded", "timeout": True}
    return {**result, "elapsed_s": round(time.monotonic() - start, 3)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--manifest-only", action="store_true")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--suite", choices=("base", "followup", "boundary", "types"), default="base")
    args = ap.parse_args()
    target = ROOT / "reports" / "validation" / args.run_id
    target.mkdir(exist_ok=False)
    cases = {'base': manifest, 'followup': followup_manifest, 'boundary': boundary_manifest,
             'types': type_control_manifest}[args.suite]()
    assert len({c['id'] for c in cases}) == len(cases)
    payload = json.dumps(cases, ensure_ascii=False, indent=2).encode()
    (target / "manifest.json").write_bytes(payload)
    meta = {"started_utc": datetime.now(timezone.utc).isoformat(), "manifest_sha256": digest(payload),
            "script_sha256": digest(Path(__file__).read_bytes()),
            "syntax_sha256": {p: digest((ROOT / p).read_bytes()) for p in DOCS},
            "model_sha256": {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in sorted((ROOT / 'build/cube/model').rglob('*.yml'))},
            "commit": subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            "independence": "Only syntax documents and deployed model used; no evaluation-bank or model-response input."}
    (target / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    print(f"manifest: {len(cases)} cases, sha256={digest(payload)}", flush=True)
    if args.manifest_only:
        return
    with (target / "results.jsonl").open('x') as stream:
        for i, case in enumerate(cases, 1):
            if case['interface'] == 'sql':
                result = asyncio.run(sql_result(case['query'], args.timeout))
            else:
                r = CubeJsonExecutor(timeout_s=args.timeout).execute(json.dumps(case['query']))
                if r.error_class == 'transport_error':
                    raise RuntimeError('Cube REST transport failure; stop the capability run')
                result = dict(ok=r.ok, columns=r.columns, rows=r.rows, error=r.error,
                              detail=r.detail, executor_error_class=r.error_class, elapsed_s=r.elapsed_s)
            record = {**case, 'result': result}
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
            stream.flush()
            print(f"[{i}/{len(cases)}] {case['id']}: {'OK' if result['ok'] else 'ERROR'}", flush=True)


if __name__ == '__main__':
    main()
