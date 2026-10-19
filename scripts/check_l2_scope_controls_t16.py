"""Verify generic controls and smoke numbers without invoking any scorer/model."""
import hashlib
import json
import math
import os
from pathlib import Path

from data.clickhouse_t16 import query as physical
from harness.executors import CubeJsonExecutor
from harness.questions import load_questions

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "20261019-T16-pilot-v13-02"


def close(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-8, abs_tol=1e-5)


def main():
    assert not os.environ.get("DEEPSEEK_API_KEY"), "unset model key"
    data = Path(os.environ["SEMDEBT_DATA_DIR"])
    probes = json.loads((data / "interface-probes" / "t16-cross-fact-time-20261019.json").read_text())
    baselines = {
        "inventory": """WITH inv AS (
SELECT StoreKey,DateKey,sum(OnHandQuantity*UnitCost) AS v
FROM retail.FactInventory WHERE DateKey>='2007-02-01' AND DateKey<'2007-03-01' GROUP BY StoreKey,DateKey),
i AS (SELECT StoreKey,avg(v) AS avg_v FROM inv GROUP BY StoreKey),
s AS (SELECT StoreKey,sum(TotalCost) AS c FROM retail.FactSales
WHERE DateKey>='2007-02-01' AND DateKey<'2007-03-01' GROUP BY StoreKey)
SELECT i.StoreKey,coalesce(s.c,0)/nullIf(i.avg_v,0),i.avg_v
FROM i LEFT JOIN s ON i.StoreKey=s.StoreKey ORDER BY i.StoreKey LIMIT 4 FORMAT JSONCompact""",
        "sales_quota": """WITH q AS (SELECT StoreKey,sum(SalesAmountQuota) AS quota
FROM retail.FactSalesQuota WHERE DateKey>='2007-02-01' AND DateKey<'2007-03-01' AND ScenarioKey=2 GROUP BY StoreKey),
s AS (SELECT StoreKey,sum(SalesAmount) AS actual FROM retail.FactSales
WHERE DateKey>='2007-02-01' AND DateKey<'2007-03-01' GROUP BY StoreKey)
SELECT q.StoreKey,s.actual/nullIf(q.quota,0),q.quota
FROM q LEFT JOIN s ON q.StoreKey=s.StoreKey ORDER BY q.StoreKey LIMIT 4 FORMAT JSONCompact""",
    }
    for cube, sql in baselines.items():
        expected = json.loads(physical(sql))["data"]
        for case in probes["cases"]:
            if not case["id"].startswith(cube + "_"):
                continue
            if "extra_fact" in case["id"]:
                assert "join path" in case["error"]
                case["classification"] = "条件不符：加入无连接路径的事实 Cube"
                continue
            assert not case["error"]
            if case["id"].endswith("json"):
                order = [cube + ".StoreKey", cube + (".inventory_turnover" if cube == "inventory" else ".quota_attainment_pct"), cube + (".average_on_hand_value" if cube == "inventory" else ".sales_amount_quota")]
                names = [c["name"] for c in case["columns"]]
                rows = [[row[names.index(name)] for name in order] for row in case["rows"]]
            else:
                rows = case["rows"]
            assert len(rows) == len(expected)
            assert all(close(v, w) for row, ref in zip(rows, expected) for v, w in zip(row, ref))
            case["classification"] = "成立（本模型连接、同一整月范围）"
            case["physical_baseline_match"] = True
        probes.setdefault("physical_baselines", {})[cube] = {"query": sql, "rows": expected}
    day_sql = """SELECT toYear(DateKey),toQuarter(DateKey),count(),countIf(sales<>0)
FROM (SELECT d.DateKey,coalesce(sum(f.SalesAmount),0) AS sales
FROM retail.DimDate d LEFT JOIN retail.FactOnlineSales f ON d.DateKey=f.DateKey
WHERE d.DateKey >= (SELECT min(DateKey) FROM retail.FactOnlineSales)
AND d.DateKey <= (SELECT max(DateKey) FROM retail.FactOnlineSales)
GROUP BY d.DateKey) GROUP BY toYear(DateKey),toQuarter(DateKey)
ORDER BY 1,2 FORMAT JSONCompact"""
    days = json.loads(physical(day_sql))["data"]
    probes["calendar_day_check"] = {"query": day_sql, "rows": days,
                                    "all_calendar_days_have_nonzero_sales": all(int(r[2]) == int(r[3]) for r in days)}
    probes["dimension_extrema_controls"] = []
    for member, table, column in (("product.UnitCost", "DimProduct", "UnitCost"), ("sales.ReturnAmount", "FactSales", "ReturnAmount")):
        request = {"dimensions": [member], "order": {member: "desc"}, "limit": 1}
        result = CubeJsonExecutor(timeout_s=120).execute(json.dumps(request))
        baseline = f"SELECT max({column}) FROM retail.{table} FORMAT JSONCompact"
        expected = json.loads(physical(baseline))["data"][0][0]
        assert not result.error and len(result.rows) == 1 and close(result.rows[0][0], expected)
        probes["dimension_extrema_controls"].append({"query": request, "physical_query": baseline, "value": result.rows[0][0], "baseline": expected, "matches": True})
    (ROOT / "reports/validation/t16_cross_fact_time_controls.json").write_text(json.dumps(probes, ensure_ascii=False, indent=2, default=str) + "\n")
    questions = {q.qid: q for q in load_questions()}
    records = []
    for qid in ("Q17", "Q69"):
        for cell in ("SQL-L2", "JSON-L2"):
            source_log = [json.loads(line) for line in (ROOT / "runs" / SOURCE / (cell + ".jsonl")).read_text().splitlines()]
            turn = next(r for r in source_log if r["qid"] == qid)["turns"][0]
            raw_file = data / "runs-raw" / SOURCE / cell / f"{qid}_r1_t0.exec.json"
            assert hashlib.sha256(raw_file.read_bytes()).hexdigest() == turn["exec"]["exec_raw_sha256"]
        raw = {cell: json.loads((data / "runs-raw" / SOURCE / cell / f"{qid}_r1_t0.exec.json").read_text()) for cell in ("SQL-L2", "JSON-L2")}
        candidate = raw["JSON-L2"]
        reference = questions[qid].refs[0]
        checks = []
        for row in candidate["rows"]:
            ref = next(r for r in reference if r[0] == row[0])
            amount = float(row[1])
            ratio = float(row[2])
            ratio_index = 2 if qid == "Q17" else 3
            checks.append({"group": row[0], "json_amount": amount, "reference_amount": float(ref[1]),
                           "json_ratio": ratio, "reference_ratio": float(ref[ratio_index]) / 100,
                           "reference_base": float(ref[-1]),
                           "amount_matches": close(amount, ref[1]), "ratio_matches": close(ratio, float(ref[ratio_index]) / 100)})
            assert checks[-1]["amount_matches"] and checks[-1]["ratio_matches"]
            if qid == "Q17":
                checks[-1]["inferred_json_base"] = amount / ratio
                assert close(amount / ratio, ref[-1])
        record = {"qid": qid, "original_scores_preserved": True, "required_columns": questions[qid].rules["required_columns"],
                  "missing_base_ref_index": 3 if qid == "Q17" else 4, "numeric_checks": checks,
                  "category": "d：必答基数无上下文暴露成员" if qid == "Q17" else "模型未遵循展示约定",
                  "sql_columns": raw["SQL-L2"]["columns"], "json_columns": candidate["columns"]}
        if qid == "Q69":
            log = [json.loads(line) for line in (ROOT / "runs" / SOURCE / "JSON-L2.jsonl").read_text().splitlines()]
            request = next(r for r in log if r["qid"] == qid)["turns"][-1]["query"]
            request = json.loads(request) if isinstance(request, str) else request
            request["measures"].append("online_sales.list_amount_before_discount")
            result = CubeJsonExecutor(timeout_s=120).execute(json.dumps(request))
            assert not result.error
            names = [c["name"] for c in result.columns]
            observed = result.rows[0][names.index("online_sales.list_amount_before_discount")]
            assert close(observed, reference[0][-1])
            # Query and complete rows remain outside Git. This is a local DB
            # diagnostic, not a model answer or a change to official scoring.
            packet = {"query": request, "rows": result.rows, "columns": result.columns}
            private = data / "interface-probes" / "t16-Q69-base-check.json"
            private.write_text(json.dumps(packet, ensure_ascii=False, default=str))
            record["visible_base_member"] = "online_sales.list_amount_before_discount"
            record["base_from_visible_member"] = observed
            record["diagnostic_sha256"] = hashlib.sha256(private.read_bytes()).hexdigest()
        records.append(record)
    for qid in ("Q50", "Q76", "Q80", "Q82"):
        original = json.loads((data / "interface-probes/t16-l2-delivery-audit-20261019" / (qid + "_original.json")).read_text())
        log = [json.loads(line) for line in (ROOT / "runs" / SOURCE / "SQL-L2.jsonl").read_text().splitlines()]
        turn = next(r for r in log if r["qid"] == qid)["turns"][-1]
        assert original["query"] == turn["query"]
        raw_file = data / "runs-raw" / SOURCE / "SQL-L2" / f"{qid}_r1_t{turn['turn']}.exec.json"
        assert hashlib.sha256(raw_file.read_bytes()).hexdigest() == turn["exec"]["exec_raw_sha256"]
        error = json.loads(raw_file.read_text())["error"]
        assert "Syntax error" in error and "``" in error
        records.append({"qid": qid, "failure_category": "引擎限制：Cube 生成 ClickHouse SQL 语法错误（空标识符）",
                        "task_expressibility": "其他通用写法可执行；不等于整题 SQL 不可表达",
                        "source_turn": turn["turn"], "source_exec_sha256": turn["exec"]["exec_raw_sha256"],
                        "error_verbatim": error, "original_scores_preserved": True})
    (ROOT / "reports/validation/t16_smoke_scope_numeric_checks.json").write_text(json.dumps({"model_calls": 0, "scorer_calls": 0, "records": records}, ensure_ascii=False, indent=2, default=str) + "\n")
    print("8 positive controls match independent physical baselines; 4 path failures; smoke numbers checked; no rescoring")


if __name__ == "__main__":
    main()
