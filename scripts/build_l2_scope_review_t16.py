"""Publish ID-only static coverage; never read question text into the output.

This is a preregistration, not an executable answer key. Bindings must be
checked again against the delivered v1.4 context before any full run.
"""
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from harness.questions import load_questions, verify_eval_tag
from render.context import render_cell

ROOT = Path(__file__).resolve().parents[1]

# IDs, semantic capability categories, and exposed member names only.
COVERED = {
    2: "online_sales.sales_amount", 3: "online_sales.customer_count",
    4: "product.ProductKey product.ProductName product.BrandName", 6: "online_sales.sales_amount online_sales.DateKey",
    8: "employee.EmployeeKey employee.FirstName employee.LastName employee.IsSalesPerson", 9: "product.unit_cost",
    11: "online_sales.sales_amount product_category.ProductCategoryName",
    12: "online_sales.sales_amount calendar.MonthNumber online_sales.DateKey",
    13: "sales.sales_amount sales.average_unit_price sales.sales_quantity store.StoreName",
    15: "online_sales.sales_amount geography.RegionCountryName",
    16: "online_sales.sales_amount calendar.CalendarYear online_sales.DateKey",
    18: "online_sales.discount_amount promotion.PromotionType",
    19: "online_sales.average_order_value customer.Gender",
    21: "inventory.current_on_hand_quantity store.StoreName",
    24: "online_sales.return_rate online_sales.sales_quantity product_category.ProductCategoryName",
    25: "online_sales.average_daily_sales_amount calendar.NorthAmericaSeason geography.ContinentName",
    28: "sales.average_unit_price channel.ChannelName",
    31: "strategy_plan.plan_amount product_category.ProductCategoryName scenario.ScenarioName account.AccountName strategy_plan.DateKey",
    34: "inventory.inventory_turnover inventory.average_on_hand_value inventory.ProductKey product.ProductName inventory.DateKey",
    41: "online_sales.sales_amount online_sales.DateKey",
    43: "online_sales.gross_margin geography.ContinentName",
    52: "product.UnitPrice",
    53: "online_sales.order_count online_sales.DateKey", 54: "online_sales.return_amount",
    58: "online_sales.SalesAmount",
    61: "online_sales.sales_amount product_subcategory.ProductSubcategoryName",
    62: "online_sales.sales_amount online_sales.sales_quantity product.BrandName",
    63: "online_sales.average_order_value customer.Occupation",
    64: "online_sales.gross_margin online_sales.gross_margin_pct online_sales.sales_amount calendar.MonthNumber online_sales.DateKey",
    65: "sales.sales_amount store.StoreName store.EmployeeKey employee.FirstName employee.LastName",
    66: "online_sales.discount_amount calendar.CalendarQuarterLabel online_sales.DateKey",
    68: "online_sales.order_count online_sales.sales_amount calendar.IsHoliday online_sales.DateKey",
    69: "online_sales.discounted_sales_amount online_sales.discount_rate online_sales.list_amount_before_discount promotion.PromotionCategory promotion.PromotionKey",
    75: "online_sales.sales_amount_yoy_pct customer.FirstName customer.LastName online_sales.CustomerKey online_sales.DateKey",
    101: "online_sales.sales_amount online_sales.DateKey",
    102: "online_sales.net_sales_amount product_category.ProductCategoryName online_sales.DateKey",
    105: "sales.sales_amount store.StoreName",
    108: "online_sales.sales_amount online_sales.order_count geography.RegionCountryName online_sales.DateKey",
}

GROUPS = {
    ("a", "dimension_aggregate_not_defined"): [1, 5, 10, 47, 51, 55, 56, 57, 59, 60, 70],
    ("a", "stock_gap_not_defined"): [20, 73],
    ("a", "cohort_metric_not_defined"): [26, 76, 81, 83, 89, 96, 115, 116],
    ("a", "quantile_metric_not_defined"): [37, 100],
    ("a", "business_formula_not_defined"): [38, 78, 84, 87, 107, 112, 120, 121, 122],
    ("a", "span_metric_not_defined"): [80],
    ("a", "hr_metric_not_defined"): [82],
    ("b", "quarter_shift_variant_not_encoded"): [94],
    ("b", "new_customer_cohort_reading_mismatch"): [114],
    ("c", "aggregate_then_reaggregate"): [14, 32, 103],
    ("c", "group_top_n_or_nested_selection"): [22, 71, 74, 85, 88, 98, 118, 119],
    ("c", "dynamic_arithmetic_or_window"): [23, 29, 30, 72, 90, 99, 104, 109, 110, 111, 113],
    ("c", "self_join_or_recursive_rollup"): [35, 49],
    ("c", "wide_metrics_cannot_return_labeled_rows"): [36],
    ("c", "multi_stage_attribution"): [117],
    ("d", "mandatory_rank_column"): [7, 27, 67, 79, 92],
    ("d", "mandatory_growth_amount_column"): [50, 77, 106],
    ("d", "mandatory_denominator_not_exposed"): [17],
}


def main():
    assert not os.environ.get("DEEPSEEK_API_KEY"), "unset model key"
    assert verify_eval_tag("eval-v1.2") == "90e13b385a639a9164ac78430c50c11a7859f976"
    context = render_cell("JSON-L2")
    measures = {x["call"] for m in context["metrics"] for x in m.get("callables", [])}
    dimensions = {d["name"] + "." + c["name"] for d in context["datasets"] for c in d["columns"]}
    catalog = json.loads((Path(os.environ["SEMDEBT_DATA_DIR"]) / "interface-probes" / "t16-l2-delivery-audit-20261019" / "inventory.json").read_text())
    actual = {c["name"] + "." + m["name"] for c in catalog["cubes"] for k in ("measures", "dimensions") for m in c.get(k, [])}
    rows = []
    classifications = {n: (category, code) for (category, code), ids in GROUPS.items() for n in ids}
    questions = load_questions()
    for question in sorted(questions, key=lambda q: int(q.qid[1:])):
        if question.scoring == "judge":
            continue
        n = int(question.qid[1:])
        row = {"qid": question.qid, "stratum": "low_discrimination" if question.meta.get("low_discrimination") else "primary"}
        if n in COVERED:
            members = sorted(set(COVERED[n].split()))
            assert set(members) <= actual, (question.qid, set(members) - actual)
            assert set(members) <= measures | dimensions, (question.qid, set(members) - measures - dimensions)
            row.update(category="covered", capability="exposed_members", standard_member_set=members,
                       measures=[m for m in members if m in measures], dimensions_and_filter_time_members=[m for m in members if m not in measures])
        else:
            category, code = classifications[n]
            row.update(category=category, capability=code, standard_member_set=None)
        rows.append(row)
    assert len(rows) == 109
    assert len(COVERED) + len(classifications) == len(rows)
    hidden = []
    for cube in catalog["cubes"]:
        for member in cube.get("measures", []):
            name = cube["name"] + "." + member["name"]
            if name in measures:
                continue
            suffix = member["name"]
            metric, line = (
                ("销售额占比", 2751) if suffix == "sales_amount_in_scope" else
                ("销售额同比增长率", 2734) if suffix == "sales_amount_prior_year" else
                ("销售额环比增长率", 2743) if suffix == "sales_amount_prior_month" else
                ("折扣率", 2478) if suffix == "discounted_list_amount" else
                ("同店销售额／同店销售额增长率", 2759)
            )
            hidden.append({"member": name, "exposed": False, "counts_as_coverage": False,
                           "l1_existing_promise": metric, "source": f"semantic/source.yaml:{line}",
                           "standalone_callable_promised": False,
                           "handoff": "T12 范围或变体检查：判断暴露辅助成员或另建可调用变体；不是自动全部公开"})
    payload = {"model_calls": 0, "scorer_calls": 0, "eval_tag": "eval-v1.2", "semantic_basis": "semantic-v1.3 plus approved M-SHARE scope variants (bindings pending v1.4)",
               "context_sha256": hashlib.sha256(json.dumps(context, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
               "status": "pre-v1.4 static preregistration; rebind and freeze commit before full run",
               "category_counts": dict(Counter(r["category"] for r in rows)), "rows": rows, "hidden_measures": hidden}
    out = ROOT / "reports" / "validation" / "t16_l2_scope_coverage.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    lines = ["# T16 JSON-L2 静态覆盖标注（v1.4 交付前）", "",
             "只计模型上下文暴露的成员。109 个非 judge 题；低区分度单列。零模型调用、零评分调用。", "",
             "本表按 #142 与用户后续裁决取代旧分类报告中的‘常用指标应补’建议。a/b/c/d 是覆盖分类，不修改原分。", "",
             "v1.4 尚未交付，M-SHARE 的名称与范围、是否交付分母成员须由 T12 确定；当前标注不能作为已验收 v1.4 的声明。Q17 若获交付基数成员，须在全量前改成 covered 并固定新提交；其余父组占比题仍有嵌套选择障碍。", "",
             "成员集包含度量、输出维度以及筛选/排序/时间成员；比较时将各位置引用去重为集合，时间粒度、筛选值和输出形状另记。仅对错答拆因：执行错误优先；集合不同归选错成员；集合相同归读法/筛选/形状差异。该归类不声称集合不同就必然语义错误，也不替代评分。全量前冻结版本，不在看答案后补集合。", "",
             "a：L1 未定义所需口径；b：已有 L1 承诺但当前交付未编码；c：现有调用对象下无法一步组合；d：核心可答，仅必答展示列无可见成员。多障碍时表中记主障碍，不把 a/b 混算为纯接口限制。", "",
             "维表 COUNT/AVG/MAX 与事实表去重数或平均值不是同一口径；即使当前数据偶然相等，也不当作正确实现。b 的季度和新客读法交 T12 按 L1 复核，不能自行加入新口径。", "",
             "| 题号 | 分层 | 类别 | 能力类别 / 标准成员集 |", "|---|---|---|---|"]
    for row in rows:
        detail = ", ".join(row["standard_member_set"]) if row["category"] == "covered" else row["capability"]
        lines.append(f"| {row['qid']} | {row['stratum']} | {row['category']} | {detail} |")
    lines += ["", "## 去掉名次列的专项检查", "",
              "| 题号 | 结论 | 类别 |", "|---|---|---|",
              "| Q71 | 仍不能；参考本来没有名次必答列，剩余为组内选择 | c |",
              "| Q73 | 仍不能；缺少可见差额成员及对应选择能力 | a（另有 c） |",
              "| Q74 | 仍不能；即使补父组占比，仍需要组内 Top-N | c |",
              "| Q100 | 仍不能；参考本来没有名次必答列，缺分位筛选及交集能力 | a（另有 c） |", "",
              "## 未暴露的辅助指标（全部不计能答）", "",
              "下列成员均服务已有 L1 口径；这不等于 L1 单独承诺过每个辅助成员可调用。无对应 L1 口径的隐藏度量本次目录中为 0；不建议公开不对应的实现细节。", "",
              "| 隐藏成员 | 对应 L1 口径 | 依据 | 交付处置 |", "|---|---|---|---|"]
    for member in hidden:
        lines.append(f"| {member['member']} | {member['l1_existing_promise']} | {member['source']} | T12 范围或变体检查决定 |")
    (out.with_suffix(".md")).write_text("\n".join(lines) + "\n")
    print(payload["category_counts"], "hidden", len(hidden))


if __name__ == "__main__":
    main()
