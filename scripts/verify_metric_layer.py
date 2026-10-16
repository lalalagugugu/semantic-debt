"""Verify T10's multi-stage members through both real Cube interfaces.

    uv run python scripts/verify_metric_layer.py

No question bank or model API is used. Expected values are ordinary ClickHouse
aggregates over the imported facts, independent of the generated Cube measures.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from data.clickhouse_t16 import query as clickhouse
from harness.executors import CubeJsonExecutor, CubeSqlExecutor, INTERFACE_LIMITATION


def cases():
    for cube, table, dimension in (("sales", "FactSales", "channelKey"),
                                    ("online_sales", "FactOnlineSales", "StoreKey")):
        for metric, grain, interval in (("sales_amount_yoy_pct", "month", "1 year"),
                                         ("sales_amount_mom_pct", "month", "1 month"),
                                         ("sales_amount_share", None, None)):
            member = f"{cube}.{metric}"
            td = {"dimension": f"{cube}.DateKey", "dateRange": ["2009-01-01", "2009-12-31"]}
            if grain:
                td["granularity"] = grain
            body = {"measures": [member], "timeDimensions": [td]}
            if grain:
                body["order"] = {f"{cube}.DateKey": "asc"}
                dim = f"DATE_TRUNC('{grain}', {cube}.\"DateKey\")"
                reference = (
                    f"WITH periods AS (SELECT toStartOfMonth(DateKey) AS period, sum(SalesAmount) AS amount "
                    f"FROM retail.{table} GROUP BY period) "
                    f"SELECT toString(cur.period), (cur.amount - prev.amount) / nullIf(prev.amount, 0) "
                    f"FROM periods cur LEFT JOIN periods prev ON prev.period = cur.period - INTERVAL {interval} "
                    "WHERE cur.period >= '2009-01-01' AND cur.period < '2010-01-01' ORDER BY cur.period"
                )
            else:
                body["dimensions"] = [f"{cube}.{dimension}"]
                body["order"] = {f"{cube}.{dimension}": "asc"}
                dim = f'{cube}."{dimension}"'
                reference = (
                    f"SELECT toString({dimension}), sum(SalesAmount) / "
                    f"(SELECT sum(SalesAmount) FROM retail.{table} WHERE toYear(DateKey) = 2009) "
                    f"FROM retail.{table} WHERE toYear(DateKey) = 2009 GROUP BY {dimension} ORDER BY {dimension}"
                )
            sql = (f"SELECT {dim} AS period, MEASURE({member}) AS value FROM {cube} "
                   f"WHERE {cube}.\"DateKey\" >= DATE '2009-01-01' AND {cube}.\"DateKey\" < DATE '2010-01-01' "
                   "GROUP BY 1 ORDER BY 1")
            yield member, sql, body, reference
    member = "sales.same_store_sales_growth_pct"
    yield member, (
        f"SELECT DATE_TRUNC('year', sales.\"DateKey\") AS period, MEASURE({member}) AS value FROM sales "
        "WHERE sales.\"DateKey\" >= DATE '2009-01-01' AND sales.\"DateKey\" < DATE '2010-01-01' GROUP BY 1 ORDER BY 1"
    ), {
        "measures": [member],
        "timeDimensions": [{"dimension": "sales.DateKey", "granularity": "year", "dateRange": ["2009-01-01", "2009-12-31"]}],
        "order": {"sales.DateKey": "asc"},
    }, (
        "WITH same_stores AS (SELECT StoreKey FROM retail.FactSales WHERE toYear(DateKey) IN (2008, 2009) "
        "GROUP BY StoreKey HAVING uniqExact(toYear(DateKey)) = 2) "
        "SELECT '2009-01-01', (sumIf(SalesAmount, toYear(DateKey) = 2009) - sumIf(SalesAmount, toYear(DateKey) = 2008)) "
        "/ nullIf(sumIf(SalesAmount, toYear(DateKey) = 2008), 0) FROM retail.FactSales "
        "WHERE StoreKey IN same_stores AND toYear(DateKey) IN (2008, 2009)"
    )


def keyed(rows):
    def key(value):
        text = str(value)
        return text[:10] if len(text) >= 10 and text[4] == "-" else str(int(float(text)))
    result = {key(row[0]): None if row[1] is None else float(row[1]) for row in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate grouping keys in result")
    return result


def image_identity(service):
    container = subprocess.check_output(["docker", "compose", "ps", "-q", service], cwd=REPO, text=True).strip()
    image_id = subprocess.check_output(["docker", "inspect", "--format", "{{.Image}}", container], text=True).strip()
    return json.loads(subprocess.check_output(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", image_id], text=True))


def main():
    entries = []
    for member, sql, body, reference in cases():
        expected = keyed(json.loads(clickhouse(reference + " FORMAT JSONCompact"))["data"])
        for executor, request in ((CubeSqlExecutor(), sql), (CubeJsonExecutor(), json.dumps(body))):
            result = executor.execute(request)
            got = keyed(result.rows) if result.ok else {}
            equal = result.ok and got.keys() == expected.keys() and all(
                (want is None and got[key] is None) or
                (want is not None and got[key] is not None and math.isclose(got[key], want, rel_tol=1e-8, abs_tol=1e-8))
                for key, want in expected.items()
            )
            entry = {"member": member, "interface": executor.name, "query": request, "reference_sql": reference,
                     "expected": expected, "actual": got, "passed": equal,
                     "error": result.error, "error_class": result.error_class}
            entries.append(entry)
            print(f"{executor.name}: {member}: {'PASS' if equal else result.error or 'MISMATCH'}", flush=True)
    cube_version = subprocess.check_output(
        ["docker", "compose", "exec", "-T", "cube", "node", "-p", "require('@cubejs-backend/server/package.json').version"],
        cwd=REPO, text=True,
    ).strip()
    versions = {"cube": cube_version, "clickhouse": clickhouse("SELECT version()"),
                "images": {service: image_identity(service) for service in ("cube", "clickhouse")}}
    target = REPO / "reports" / "validation"
    (target / "metric_layer_t16.json").write_text(json.dumps({"versions": versions, "checks": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# T16 Cube 接口与多阶段指标验证", "",
             "复现：`uv run python scripts/verify_metric_layer.py`。不读题库、不调用模型。", "",
             f"- Cube Core / Cube SQL / Cube Store：`{versions['cube']}`；ClickHouse：`{versions['clickhouse']}`。",
             "- 两种接口查询冻结的 T10 模型，未改语义层或渲染器；Tesseract 已开启。",
             "- 基线独立使用导入事实表的普通 SQL；2009 月同比、月环比、渠道/门店占比、2009 对 2008 同店增长。",
             "- 同比、环比、占比有线上与全渠道两个调用名，故四类指标共 7 个成员、14 项接口核对。",
             "- 比较行数、完整分组键集合及每个数值，容差 `rel_tol=abs_tol=1e-8`；这仅用于部署核验，不改变实验评分。",
             f"- 通过 {sum(e['passed'] for e in entries)}/{len(entries)}；明确接口限制 {sum(e['error_class'] == INTERFACE_LIMITATION for e in entries)} 项。", "",
             "| 接口 | 指标 | 行数 | 结果 | 错误分类 |", "|---|---|---:|---|---|"]
    lines += [f"| {e['interface']} | `{e['member']}` | {len(e['actual'])} | {'通过' if e['passed'] else '未通过'} | {e['error_class'] or '—'} |" for e in entries]
    lines += ["", "完整查询、基线与实际值见同目录 `metric_layer_t16.json`。本报告只证明这些验证查询可执行且结果一致，",
              "不代表任意 SQL/JSON 查询均被支持；未运行题集，未估算或填写实验准确率、拒答率、20% 接口限制门槛。", "",
              "## 镜像标识", "", *[f"- {service}: `{digest}`" for service, digests in versions["images"].items() for digest in digests], ""]
    (target / "metric_layer_t16.md").write_text("\n".join(lines), encoding="utf-8")
    if any(not e["passed"] for e in entries):
        raise SystemExit("Some interface checks failed; see reports/validation/metric_layer_t16.json")


if __name__ == "__main__":
    main()
