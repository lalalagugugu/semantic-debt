"""Zero-model generic v1.4 controls against independent physical aggregates.

Run only after explicitly loading the recorded model. The deletion diagnostic
is never treated as acceptance of the unmodified candidate.
"""
import argparse
from datetime import date, timedelta
import json
import math
import os
from pathlib import Path
import subprocess

from data.clickhouse_t16 import query as physical
from harness.executors import CubeJsonExecutor, CubeSqlExecutor


def cases():
    for cube, table in (("sales", "FactSales"), ("online_sales", "FactOnlineSales")):
        for child, dataset, child_key in (("product_subcategory", "DimProductSubcategory", "ProductSubcategoryName"), ("product", "DimProduct", "ProductName")):
            member = cube + ".sales_amount_share_in_category"
            dimensions = ["product_category.ProductCategoryName", child + "." + child_key]
            joins = f"product_category CROSS JOIN {cube} CROSS JOIN {child}"
            ref = f"""SELECT pc.ProductCategoryName,{('ps' if child == 'product_subcategory' else 'p')}.{child_key},
sum(f.SalesAmount)/sum(sum(f.SalesAmount)) OVER(PARTITION BY pc.ProductCategoryName)
FROM retail.{table} f LEFT JOIN retail.DimProduct p ON f.ProductKey=p.ProductKey
LEFT JOIN retail.DimProductSubcategory ps ON p.ProductSubcategoryKey=ps.ProductSubcategoryKey
LEFT JOIN retail.DimProductCategory pc ON ps.ProductCategoryKey=pc.ProductCategoryKey
WHERE f.DateKey>='2007-02-01' AND f.DateKey<'2007-03-01' AND pc.ProductCategoryKey>0
GROUP BY pc.ProductCategoryName,{('ps' if child == 'product_subcategory' else 'p')}.{child_key} ORDER BY 1,2"""
            yield make(cube + "_category_" + child, cube, member, dimensions, joins, ref,
                       filters=[{"member": "product_category.ProductCategoryKey", "operator": "gt", "values": ["0"]}],
                       where="product_category.\"ProductCategoryKey\">0")
    yield make("sales_channel", "sales", "sales.sales_amount_share_in_channel",
               ["channel.ChannelName", "store.StoreName"], "channel CROSS JOIN sales CROSS JOIN store", """
SELECT c.ChannelName,s.StoreName,sum(f.SalesAmount)/sum(sum(f.SalesAmount)) OVER(PARTITION BY c.ChannelName)
FROM retail.FactSales f LEFT JOIN retail.DimChannel c ON f.channelKey=c.ChannelKey
LEFT JOIN retail.DimStore s ON f.StoreKey=s.StoreKey
WHERE f.DateKey>='2007-02-01' AND f.DateKey<'2007-03-01' GROUP BY c.ChannelName,s.StoreName ORDER BY 1,2""")
    for cube, table in (("sales", "FactSales"), ("online_sales", "FactOnlineSales")):
        member = cube + ".sales_amount_qoq_pct"
        ref = f"""WITH p AS (SELECT toStartOfQuarter(DateKey) AS d,sum(SalesAmount) AS a FROM retail.{table} GROUP BY d)
SELECT toString(c.d),(c.a-p.a)/nullIf(p.a,0) FROM p c LEFT JOIN p ON p.d=addQuarters(c.d,-1)
WHERE c.d>='2008-01-01' AND c.d<'2008-10-01' ORDER BY c.d"""
        yield make(cube + "_quarter", cube, member, [], cube, ref, start="2008-01-01", end="2008-09-30", grain="quarter")
    for suffix, column in (("sales_amount_quota", "SalesAmountQuota"), ("sales_quantity_quota", "SalesQuantityQuota"), ("gross_margin_quota", "GrossMarginQuota")):
        for scenario in (None, "Actual", "Forecast"):
            conditions = "" if scenario is None else f" AND s.ScenarioName='{scenario}'"
            ref = f"""SELECT s.ScenarioName,sum(f.{column}) FROM retail.FactSalesQuota f
LEFT JOIN retail.DimScenario s ON f.ScenarioKey=s.ScenarioKey
WHERE f.DateKey>='2007-02-01' AND f.DateKey<'2007-03-01'{conditions} GROUP BY s.ScenarioName ORDER BY 1"""
            yield make(suffix + "_" + str(scenario), "sales_quota", "sales_quota." + suffix + "_by_scenario",
                       ["scenario.ScenarioName"], "sales_quota CROSS JOIN scenario", ref,
                       filters=[] if scenario is None else [{"member": "scenario.ScenarioName", "operator": "equals", "values": [scenario]}],
                       where="" if scenario is None else f"scenario.\"ScenarioName\"='{scenario}'")
    for scenario in (None, "Actual", "Forecast"):
        conditions = "" if scenario is None else f" AND s.ScenarioName='{scenario}'"
        ref = f"""SELECT s.ScenarioName,sum(f.Amount) FROM retail.FactStrategyPlan f
LEFT JOIN retail.DimScenario s ON f.ScenarioKey=s.ScenarioKey
WHERE f.DateKey>='2007-02-01' AND f.DateKey<'2007-03-01' AND f.AccountKey=4{conditions}
GROUP BY s.ScenarioName ORDER BY 1"""
        yield make("plan_" + str(scenario), "strategy_plan", "strategy_plan.plan_revenue_by_scenario",
                   ["scenario.ScenarioName"], "strategy_plan CROSS JOIN scenario", ref,
                   filters=[] if scenario is None else [{"member": "scenario.ScenarioName", "operator": "equals", "values": [scenario]}],
                   where="" if scenario is None else f"scenario.\"ScenarioName\"='{scenario}'")
    for year in (2007, 2008):
        ref = f"""SELECT sum(SalesAmount) FROM retail.FactSales WHERE toYear(DateKey)={year} AND StoreKey IN
(SELECT StoreKey FROM retail.FactSales WHERE toYear(DateKey) IN ({year},{year+1}) GROUP BY StoreKey HAVING uniqExact(toYear(DateKey))=2)"""
        yield make("same_store_base_" + str(year), "sales", "sales.same_store_sales_as_base_year", [], "sales", ref,
                   start=f"{year}-01-01", end=f"{year}-12-31")
    cutoffs = ["2007-02-10", "2007-03-11", "2007-04-13", "2007-05-17", "2007-07-21"]
    for cutoff in cutoffs:
        lower = (date.fromisoformat(cutoff) - timedelta(days=89)).isoformat()
        ref = f"""SELECT '{cutoff}',countIf(first_date>='{lower}' AND first_date<='{cutoff}')
FROM (SELECT CustomerKey,min(DateKey) AS first_date FROM retail.FactOnlineSales GROUP BY CustomerKey)"""
        yield make("new_day_" + cutoff, "online_sales", "online_sales.new_customer_count", [], "online_sales", ref,
                   start=cutoff, end=cutoff, grain="day")
    ref = """WITH firsts AS (SELECT CustomerKey,min(DateKey) AS first_date FROM retail.FactOnlineSales GROUP BY CustomerKey),
cutoffs AS (SELECT toLastDayOfMonth(addMonths(toDate('2007-02-01'),number)) AS cutoff FROM numbers(4))
SELECT toString(toStartOfMonth(c.cutoff)),countIf(f.first_date>=addDays(c.cutoff,-89) AND f.first_date<=c.cutoff)
FROM firsts f CROSS JOIN cutoffs c GROUP BY c.cutoff ORDER BY c.cutoff"""
    yield make("new_month_sliding", "online_sales", "online_sales.new_customer_count", [], "online_sales", ref,
               start="2007-02-01", end="2007-05-31", grain="month")


def make(name, cube, member, dimensions, source, reference, *, start="2007-02-01", end="2007-02-28", grain=None, filters=None, where=""):
    time = {"dimension": cube + ".DateKey", "dateRange": [start, end]}
    output = dimensions.copy()
    columns = [m.split(".")[0] + '."' + m.split(".")[1] + '"' for m in dimensions]
    if grain:
        time["granularity"] = grain
        output.append(cube + ".DateKey." + grain)
        columns.append(f"DATE_TRUNC('{grain}', {cube}.\"DateKey\")")
    request = {"measures": [member], "dimensions": dimensions, "timeDimensions": [time], "limit": 10000}
    if filters:
        request["filters"] = filters
    if output:
        request["order"] = {m: "asc" for m in dimensions} | ({cube + ".DateKey": "asc"} if grain else {})
    next_day = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
    sql = "SELECT " + ", ".join([*columns, f"MEASURE({member}) AS value"]) + f" FROM {source} WHERE {cube}.\"DateKey\">=DATE '{start}' AND {cube}.\"DateKey\"<DATE '{next_day}'"
    if where:
        sql += " AND " + where
    if columns:
        sql += " GROUP BY " + ",".join(str(n + 1) for n in range(len(columns))) + " ORDER BY " + ",".join(str(n + 1) for n in range(len(columns)))
    return {"id": name, "member": member, "json": request, "sql": sql, "output": [*output, member], "physical": reference}


def normalize(value):
    if value is None:
        return None
    value = str(value)
    if len(value) >= 10 and value[4:5] == "-" and value[7:8] == "-":
        return value[:10]
    return value


def note_cases():
    for cube in ("inventory", "sales_quota"):
        member = cube + (".inventory_turnover" if cube == "inventory" else ".quota_attainment_pct")
        if cube == "inventory":
            reference = """WITH daily AS (SELECT DateKey,sum(OnHandQuantity*UnitCost) AS v FROM retail.FactInventory
WHERE DateKey>='2007-02-01' AND DateKey<'2007-04-01' GROUP BY DateKey),
i AS (SELECT toStartOfMonth(DateKey) AS d,avg(v) AS a FROM daily GROUP BY d),
s AS (SELECT toStartOfMonth(DateKey) AS d,sum(TotalCost) AS cost FROM retail.FactSales
WHERE DateKey>='2007-02-01' AND DateKey<'2007-04-01' GROUP BY d)
SELECT toString(i.d),s.cost/nullIf(i.a,0) FROM i LEFT JOIN s ON i.d=s.d ORDER BY i.d"""
        else:
            reference = """WITH q AS (SELECT toStartOfMonth(DateKey) AS d,sum(SalesAmountQuota) AS amount FROM retail.FactSalesQuota
WHERE DateKey>='2007-02-01' AND DateKey<'2007-04-01' AND ScenarioKey=2 GROUP BY d),
s AS (SELECT toStartOfMonth(DateKey) AS d,sum(SalesAmount) AS amount FROM retail.FactSales
WHERE DateKey>='2007-02-01' AND DateKey<'2007-04-01' GROUP BY d)
SELECT toString(q.d),s.amount/nullIf(q.amount,0) FROM q LEFT JOIN s ON q.d=s.d ORDER BY q.d"""
        for owner in (True, False):
            case = make(cube + ("_owner_month" if owner else "_calendar_month"), cube, member, [], cube,
                        reference, start="2007-02-01", end="2007-03-31", grain="month")
            if not owner:
                case["json"]["timeDimensions"][0]["dimension"] = "calendar.DateKey"
                case["json"]["order"] = {"calendar.DateKey": "asc"}
                case["output"][0] = "calendar.DateKey.month"
                case["sql"] = case["sql"].replace('FROM ' + cube + ' WHERE', 'FROM ' + cube + ' CROSS JOIN calendar WHERE').replace(cube + '."DateKey"', 'calendar."DateKey"')
            yield case
    yield make("quota_partial_month_not_prorated", "sales_quota", "sales_quota.sales_amount_quota", [], "sales_quota",
               "SELECT sum(SalesAmountQuota) FROM retail.FactSalesQuota WHERE DateKey>='2007-02-01' AND DateKey<'2007-03-01' AND ScenarioKey=2",
               start="2007-02-01", end="2007-02-14")
    for case in cases():
        if case["id"] in ("sales_amount_quota_None", "sales_quantity_quota_None", "gross_margin_quota_None"):
            case["id"] += "_set"
            case["json"]["filters"] = [{"member": "scenario.ScenarioName", "operator": "set", "values": []}]
            case["sql"] = case["sql"].replace(" GROUP BY", ' AND scenario."ScenarioName" IS NOT NULL GROUP BY')
            yield case


def negative_cases():
    for cube in ("inventory", "sales_quota"):
        member = cube + (".inventory_turnover" if cube == "inventory" else ".quota_attainment_pct")
        case = make(cube + "_extra_fact_date", cube, member, [], cube + " CROSS JOIN sales", "")
        case["json"]["timeDimensions"].append({"dimension": "sales.DateKey", "dateRange": ["2007-02-01", "2007-02-28"]})
        case["sql"] += " AND sales.\"DateKey\">=DATE '2007-02-01' AND sales.\"DateKey\"<DATE '2007-03-01'"
        case["expected_error"] = "join path"
        yield case


def filtered_scope_cases():
    for case in cases():
        if case["id"] not in ("sales_channel", "sales_category_product", "online_sales_category_product"):
            continue
        cube = case["member"].split(".")[0]
        key, limit = ("StoreKey", 3) if case["id"] == "sales_channel" else ("ProductKey", 60)
        case["id"] += "_child_filter"
        case["json"].setdefault("filters", []).append({"member": cube + "." + key, "operator": "lte", "values": [str(limit)]})
        case["sql"] = case["sql"].replace(" GROUP BY", f' AND {cube}."{key}"<={limit} GROUP BY')
        case["physical"] = case["physical"].replace("GROUP BY", f"AND f.{key}<={limit} GROUP BY")
        yield case


def compare(rows, expected):
    observed = {tuple(normalize(v) for v in row[:-1]): row[-1] for row in rows}
    wanted = {tuple(normalize(v) for v in row[:-1]): row[-1] for row in expected}
    if len(observed) != len(rows) or len(wanted) != len(expected) or observed.keys() != wanted.keys():
        return False
    return all((v is None and wanted[k] is None) or (v is not None and wanted[k] is not None and math.isclose(float(v), float(wanted[k]), rel_tol=1e-8, abs_tol=1e-6)) for k, v in observed.items())


def main():
    assert not os.environ.get("DEEPSEEK_API_KEY"), "unset model API key"
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["full", "deletion-diagnostic"])
    parser.add_argument("--suite", choices=["variants", "time-notes", "negative", "scopes"], default="variants")
    parser.add_argument("--audit-dir", type=Path, help="New evidence directory with the same exported candidate and model layout")
    args = parser.parse_args()
    root = args.audit_dir or Path(os.environ["SEMDEBT_DATA_DIR"]) / "interface-probes/t16-v14-86d8826"
    out = root / (args.mode + ("-probes.jsonl" if args.suite == "variants" else "-" + args.suite + ".jsonl"))
    if out.exists():
        raise RuntimeError("refusing to overwrite prior evidence")
    repo = Path(__file__).resolve().parents[1]
    container = subprocess.check_output(["docker", "compose", "ps", "-q", "cube"], cwd=repo, text=True).strip()
    mounts = json.loads(subprocess.check_output(["docker", "inspect", "--format", "{{json .Mounts}}", container], text=True))
    expected_model = root / ("deletion-model" if args.mode == "deletion-diagnostic" else "source/build/cube/model")
    mounted = next(m["Source"] for m in mounts if m["Destination"] == "/cube/conf/model")
    if Path(mounted).resolve() != expected_model.resolve():
        raise RuntimeError("Cube model mount differs from the recorded audit mode")
    for case in {"variants": cases, "time-notes": note_cases, "negative": negative_cases, "scopes": filtered_scope_cases}[args.suite]():
        expected = [] if case.get("expected_error") else json.loads(physical(case["physical"] + " SETTINGS join_use_nulls=1 FORMAT JSONCompact"))["data"]
        for interface in ("json", "sql"):
            executor = CubeJsonExecutor(timeout_s=120) if interface == "json" else CubeSqlExecutor(timeout_s=120)
            result = executor.execute(json.dumps(case[interface]) if interface == "json" else case[interface])
            rows = result.rows
            if result.ok and interface == "json":
                names = [c["name"] for c in result.columns]
                rows = [[row[names.index(m)] for m in case["output"]] for row in rows]
            matched = (case["expected_error"] in (result.error or "")) if case.get("expected_error") else result.ok and compare(rows, expected)
            record = {**case, "mode": args.mode, "interface": interface, "rows": rows, "columns": result.columns,
                      "error": result.error, "detail": result.detail, "expected": expected, "matched": matched,
                      "physical_row_count": len(expected), "model_calls": 0}
            encoded = json.dumps(record, ensure_ascii=False, default=str)
            with out.open("a") as stream:
                stream.write(encoded + "\n")
            print(case["id"], interface, "MATCH" if matched else "ERROR" if result.error else "MISMATCH", str(result.error or "")[:180], flush=True)


if __name__ == "__main__":
    main()
