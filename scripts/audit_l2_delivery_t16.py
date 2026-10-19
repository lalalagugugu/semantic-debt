"""Offline L2 delivery audit. Never calls a model or changes frozen inputs.

Question-specific diagnostics and rows stay outside Git; committed summaries
contain IDs, categories and generic controls only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import urllib.request

import yaml

from harness.executors import CubeJsonExecutor, CubeSqlExecutor

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "20261019-T16-pilot-v13-02"

# Capability codes, not question statements. A query must return the required
# result directly; fetching rows for external computation is a different stack.
JSON_PROFILE = {
    "Q100": (["online_sales.order_count", "online_sales.average_order_value"], ["I-RANK", "I-INTERSECT"]),
    "Q117": (["sales.same_store_sales_growth_pct", "sales.same_store_sales_amount"], ["I-NEST", "I-RANK", "I-SCOPE"]),
    "Q70": (["sales.sales_amount", "store.SellingAreaSize"], ["I-AGG"]),
    "Q71": (["online_sales.sales_amount"], ["I-NEST"]),
    "Q73": (["inventory.current_on_hand_quantity", "inventory.current_safety_stock_quantity"], ["I-EXPR", "I-RANK"]),
    "Q74": (["sales.sales_amount", "sales.sales_amount_share"], ["I-NEST", "I-RANK", "I-SCOPE"]),
    "Q76": (["online_sales.order_count", "online_sales.sales_amount"], ["I-COHORT", "I-EXPR"]),
    "Q80": (["online_sales.customer_recency_months", "online_sales.DateKey"], ["I-REAGG"]),
    "Q81": (["online_sales.sales_per_customer", "online_sales.customer_count"], ["I-REAGG", "I-DERIVED"]),
    "Q82": (["employee.EmployeeKey", "employee.ParentEmployeeKey", "employee.HireDate"], ["I-SELF", "I-AGG", "I-EXPR"]),
}

CAPABILITIES = {
    "I-RANK": "无已定义排名/分位成员；不能动态产生名次、百分位筛选阈值。",
    "I-INTERSECT": "不能求两个由聚合结果动态排名产生的集合的交集。",
    "I-NEST": "limit作用于整个结果；没有分组内Top-N或父子两阶段选择。",
    "I-SCOPE": "没有所需分母作用域/差额占比成员；现有share的group_by为空，不能临时改成按父组归约。",
    "I-AGG": "缺少所需预定义聚合度量；维度存在不代表可以临时对它写AVG/COUNT。",
    "I-EXPR": "缺少所需预定义计算成员；JSON不能临时写算术或日期差表达式。",
    "I-COHORT": "缺少所需聚合后群组判定再重聚合的计算成员；对当前分组的指标做filter不是先按另一粒度选集合。",
    "I-REAGG": "缺少所需两级聚合成员；JSON不能先按实体聚合、再对实体结果重新分组/平均。",
    "I-DERIVED": "所需派生分组键没有定义为维度；不能把MIN等聚合表达式临时用作维度。",
    "I-SELF": "缺少所需预定义自关联关系和度量；不能临时声明第二个cube别名及ON条件。",
}


def report(raw):
    from decimal import Decimal
    from data.clickhouse_t16 import query as physical
    from harness.questions import load_questions, verify_eval_tag
    from harness.run_direct import score_question

    assert verify_eval_tag("eval-v1.2") == "90e13b385a639a9164ac78430c50c11a7859f976"
    questions = {q.qid: q for q in load_questions()}
    inv = json.loads((raw / "inventory.json").read_text())
    # Visibility in /meta is not query authorization in this deployment:
    # J_hidden_key/J_hidden_measure directly verify both kinds are queryable.
    members_by_name = {m["name"]: m for c in inv["live"]["cubes"]
                       for group in ("measures", "dimensions") for m in c[group]}
    source_members = {c["name"] + "." + m["name"] for c in inv["cubes"]
                      for group in ("measures", "dimensions") for m in c.get(group, [])}
    assert source_members == set(members_by_name)
    assert not any(c["segments"] for c in inv["live"]["cubes"])
    json_log = ROOT / "runs" / SOURCE / "JSON-L2.jsonl"
    sql_source = {r["qid"]: r for r in map(json.loads, (ROOT / "runs" / SOURCE / "SQL-L2.jsonl").read_text().splitlines())}
    refusals = [r for r in map(json.loads, json_log.read_text().splitlines()) if r["final"]["outcome"] == "refused"]
    assert {r["qid"] for r in refusals} == set(JSON_PROFILE)
    for r in refusals:
        for t in r["turns"]:
            path = Path(os.environ["SEMDEBT_DATA_DIR"]) / "runs-raw" / SOURCE / "JSON-L2" / f"{r['qid']}_r{r['rep']}_t{t['turn']}.json"
            assert digest(path.read_bytes()) == t["raw_sha256"]
    results = {}
    summaries = list(map(json.loads, (raw / "summary.jsonl").read_text().splitlines()))
    assert len({r["id"] for r in summaries}) == len(summaries)
    for r in summaries:
        data = (raw / (r["id"] + ".json")).read_bytes()
        assert digest(data) == r["raw_sha256"]
        results[r["id"]] = json.loads(data)
    for case in ("G_date_chain_unicode", "G_date_chain_alias_order", "G_join_aggregate_unicode",
                 "G_self_alias_unicode", "G_single_cte_unicode", "G_single_cte_alias_order",
                 "J_ad_hoc_aggregate", "J_arithmetic_member", "J_window_expression",
                 "J_dynamic_group", "J_self_join_key", "J_expression_array_form",
                 "J_expression_serialized_form", "J_patch_measure_form"):
        assert results[case]["result"]["error"], case
    for case in ("J_defined_baseline", "J_hidden_key", "J_hidden_measure"):
        assert not results[case]["result"]["error"], case

    refs = {
        "date": "SELECT ChannelName,round(avg(days),2) FROM (SELECT f.StoreKey,c.ChannelName,dateDiff('day',min(f.DateKey),max(f.DateKey)) AS days FROM retail.FactSales f LEFT JOIN retail.DimChannel c ON f.channelKey=c.ChannelKey WHERE c.ChannelName<>'' GROUP BY f.StoreKey,c.ChannelName) GROUP BY ChannelName ORDER BY ChannelName",
        "join": "SELECT channelKey,sum(SalesAmount),sum(SalesQuantity) FROM retail.FactSales GROUP BY channelKey ORDER BY channelKey",
        "single": "SELECT channelKey,sum(SalesAmount) FROM retail.FactSales GROUP BY channelKey ORDER BY channelKey",
        "self": "SELECT l.ChannelKey,r.ChannelKey,l.ChannelName,r.ChannelName FROM retail.DimChannel l CROSS JOIN retail.DimChannel r WHERE r.ChannelKey=l.ChannelKey+1 ORDER BY 1",
    }
    reference_rows = {k: json.loads(physical(q + " FORMAT JSONCompact"))["data"] for k, q in refs.items()}
    (raw / "physical-references.json").write_text(json.dumps({"queries": refs, "rows": reference_rows}, ensure_ascii=False, indent=2))

    def equal_rows(a, b):
        def eq(x, y):
            if x is None or y is None:
                return x is y
            try:
                return math.isclose(float(x), float(y), rel_tol=1e-8, abs_tol=1e-6)
            except (ValueError, TypeError):
                return x == y
        return len(a) == len(b) and all(len(x) == len(y) and all(eq(v, w) for v, w in zip(x, y)) for x, y in zip(a, b))

    checks = {}
    for case, reference in [("G_date_chain_ascii", "date"), ("G_date_chain_no_order", "date"),
                            ("G_join_aggregate_ascii", "join"), ("G_single_cte_ascii", "single"),
                            ("G_single_cte_no_order", "single"), ("G_dimension_self_aggregated", "self")]:
        observed = results[case]["result"]["rows"]
        if case.endswith("no_order"):
            observed = sorted(observed, key=lambda x: x[0])
        checks[case] = equal_rows(observed, reference_rows[reference])
    assert all(checks.values()), checks
    assert not results["G_dimension_self_direct"]["result"]["rows"]
    assert len(reference_rows["self"]) == 3
    sql_checks = []
    for qid in ("Q50", "Q76", "Q80", "Q82"):
        assert results[qid + "_original"]["query"] == sql_source[qid]["turns"][-1]["query"]
        assert results[qid + "_ascii_only"]["query"] == ascii_aliases(results[qid + "_original"]["query"])
        original = results[qid + "_original"]["result"]
        ascii_result = results[qid + "_ascii_only"]["result"]
        assert original["error"] and not ascii_result["error"]
        case = qid + ("_two_aggregated_ctes" if qid == "Q82" else "_ascii_only")
        result = results[case]["result"]
        candidate = [[Decimal(v) if isinstance(v, str) and col.get("type") == "pg:1700" else v
                      for v, col in zip(row, result["columns"])] for row in result["rows"]]
        score = score_question(candidate, questions[qid])
        assert score["outcome"] == "correct", (qid, score)
        sql_checks.append({"qid": qid, "category": "写法说明缺口", "original_error_reproduced": True,
                           "ascii_only_executable": True, "verified_correct_case": case,
                           "verification": score, "rows": len(candidate)})
    # Catalog and query grammar jointly establish missing capabilities. Returning
    # partial columns/rows, hardcoding reference values or client-side work does
    # not establish a correct query in the frozen direct-answer JSON cell.
    json_checks = []
    for qid, (members, codes) in JSON_PROFILE.items():
        assert all(m in members_by_name for m in members), qid
        json_checks.append({"qid": qid, "correct_single_json_with_existing_members": False,
                            "category": "接口限制（当前冻结交付）", "capability_codes": codes,
                            "existing_related_members": members, "material_defect_if_expressible": None})

    generic = []
    for s in summaries:
        r = results[s["id"]]
        if r.get("generic"):
            generic.append({**s, "query": r["query"], "numeric_baseline_match": checks.get(s["id"])})
    payload = {"source": SOURCE, "eval_tag": "eval-v1.2", "semantic_tag": "semantic-v1.3",
               "model_calls": 0, "script_sha256": digest(Path(__file__).read_bytes()),
               "defined_member_names": sorted(members_by_name), "capabilities": CAPABILITIES,
               "json_refusals": json_checks, "sql_failures": sql_checks,
               "generic_probes": generic, "physical_checks": checks,
               "source_log_sha256": {cell: digest((ROOT / "runs" / SOURCE / (cell + ".jsonl")).read_bytes())
                                      for cell in ("SQL-L2", "JSON-L2")},
               "private_diagnostics": [{k: v for k, v in s.items() if k not in {"error", "query"}}
                                       for s in summaries if not results[s["id"]].get("generic")],
               "inventory_sha256": digest((raw / "inventory.json").read_bytes())}
    target = ROOT / "reports/validation/t16_l2_delivery_audit.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print("report", len(json_checks), "JSON refusals;", len(sql_checks), "SQL failures;", len(generic), "generic controls; checks", checks)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ascii_aliases(query):
    names = list(dict.fromkeys(re.findall(r'"[^"\n]*[^\x00-\x7f][^"\n]*"', query)))
    for i, name in enumerate(names):
        query = query.replace(name, f"output_{i}")
    return query


def execute(case, raw):
    executor = CubeSqlExecutor(timeout_s=120) if case["interface"] == "sql" else CubeJsonExecutor(timeout_s=120)
    query = case["query"] if isinstance(case["query"], str) else json.dumps(case["query"])
    result = executor.execute(query)
    payload = {**case, "result": {"rows": result.rows, "columns": result.columns,
                                "error": result.error, "error_class": result.error_class,
                                "elapsed_s": result.elapsed_s}}
    data = json.dumps(payload, ensure_ascii=False, default=str).encode()
    path = raw / (case["id"] + ".json")
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.write_bytes(data)
    summary = {k: v for k, v in case.items() if k != "query"}
    summary.update(ok=result.ok, row_count=len(result.rows or []), error=result.error,
                   raw_sha256=digest(data))
    with (raw / "summary.jsonl").open("a") as out:
        out.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(case["id"], "ok" if result.ok else "ERROR", str(result.error or "")[:170], flush=True)


def localize():
    records = [json.loads(x) for x in (ROOT / "runs" / SOURCE / "SQL-L2.jsonl").read_text().splitlines()]
    cases = []
    for qid in ("Q50", "Q76", "Q80", "Q82"):
        query = next(x for x in records if x["qid"] == qid)["turns"][-1]["query"]
        cases += [{"id": qid + "_original", "qid": qid, "interface": "sql", "query": query},
                  {"id": qid + "_ascii_only", "qid": qid, "interface": "sql", "query": ascii_aliases(query)}]
    return cases


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=["inventory", "localize", "external", "generic", "report"], required=True)
    ap.add_argument("--cases", type=Path, help="private diagnostic cases outside the repository")
    ap.add_argument("--audit-id", default="t16-l2-delivery-audit-20261019")
    args = ap.parse_args()
    if os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("Run this no-model audit with env -u DEEPSEEK_API_KEY")
    raw = Path(os.environ["SEMDEBT_DATA_DIR"]) / "interface-probes" / args.audit_id
    raw.mkdir(parents=True, exist_ok=True)
    for f in ("harness/prompt.py", "harness/scorer.py", "harness/scorer_v2.py", "harness/score_guard.py"):
        assert (ROOT / f).read_bytes() == subprocess.check_output(["git", "show", "d2801b1:" + f], cwd=ROOT)
    assert not subprocess.check_output(["git", "diff", "semantic-v1.3", "--", "semantic", "render"], cwd=ROOT)
    if args.stage == "report":
        report(raw)
        return
    if args.stage == "inventory":
        cubes = [c for p in sorted((ROOT / "build/cube/model/cubes").glob("*.yml"))
                 for c in yaml.safe_load(p.read_text())["cubes"]]
        with urllib.request.urlopen("http://127.0.0.1:14000/cubejs-api/v1/meta", timeout=30) as response:
            live = json.loads(response.read())
        (raw / "inventory.json").write_text(json.dumps({"cubes": cubes, "live": live}, ensure_ascii=False, indent=2))
        print("inventory", len(cubes), "cubes; live", len(live["cubes"]), flush=True)
        return
    if args.stage == "localize":
        cases = localize()
    elif args.stage == "generic":
        recorded = json.loads((ROOT / "reports/validation/t16_l2_delivery_audit.json").read_text())
        cases = [{k: r[k] for k in ("id", "interface", "query", "generic")} for r in recorded["generic_probes"]]
    else:
        assert args.cases and not args.cases.resolve().is_relative_to(ROOT)
        cases = json.loads(args.cases.read_text())
    for case in cases:
        execute(case, raw)


if __name__ == "__main__":
    main()
