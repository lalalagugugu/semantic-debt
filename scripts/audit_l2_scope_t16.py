"""Generic cross-fact time-filter controls; no model or scorer invocation."""
import json
import os
from pathlib import Path

from harness.executors import CubeJsonExecutor, CubeSqlExecutor


def main():
    if os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("unset DEEPSEEK_API_KEY for this audit")
    cases = []
    for cube, measures in (
        ("inventory", ["inventory_turnover", "average_on_hand_value"]),
        ("sales_quota", ["quota_attainment_pct", "sales_amount_quota"]),
    ):
        for scope in ("owner", "calendar", "extra_fact"):
            date = f"{cube}.DateKey" if scope != "calendar" else "calendar.DateKey"
            query = {"measures": [f"{cube}.{m}" for m in measures],
                     "dimensions": [f"{cube}.StoreKey"],
                     "timeDimensions": [{"dimension": date, "dateRange": ["2007-02-01", "2007-02-28"]}],
                     "order": {f"{cube}.StoreKey": "asc"}, "limit": 4}
            if scope == "extra_fact":
                query["timeDimensions"].append({"dimension": "sales.DateKey", "dateRange": ["2007-02-01", "2007-02-28"]})
            source = cube + (" CROSS JOIN calendar" if scope == "calendar" else " CROSS JOIN sales" if scope == "extra_fact" else "")
            where = f"{date} >= '2007-02-01' AND {date} < '2007-03-01'"
            if scope == "extra_fact":
                where += " AND sales.DateKey >= '2007-02-01' AND sales.DateKey < '2007-03-01'"
            sql = f"SELECT {cube}.StoreKey, " + ", ".join(f"MEASURE({cube}.{m})" for m in measures)
            sql += f" FROM {source} WHERE {where} GROUP BY {cube}.StoreKey ORDER BY {cube}.StoreKey LIMIT 4"
            for interface, request in (("json", query), ("sql", sql)):
                executor = CubeJsonExecutor(timeout_s=120) if interface == "json" else CubeSqlExecutor(timeout_s=120)
                result = executor.execute(json.dumps(request) if interface == "json" else request)
                cases.append({"id": f"{cube}_{scope}_{interface}", "query": request,
                              "rows": result.rows, "columns": result.columns,
                              "error": result.error, "detail": result.detail})
                print(cases[-1]["id"], "ERROR" if result.error else "OK", flush=True)
    output = Path(os.environ["SEMDEBT_DATA_DIR"]) / "interface-probes" / "t16-cross-fact-time-20261019.json"
    with output.open("x") as stream:
        json.dump({"model_calls": 0, "cases": cases}, stream, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    main()
