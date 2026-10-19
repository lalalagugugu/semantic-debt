"""Freeze the ID-only JSON registry after complete v1.4 candidate validation.

Uses only exposed context members. No model, scorer, source renderer mutation,
or query execution takes place here. Historical preregistrations stay intact.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess

import yaml

from harness.questions import load_questions, verify_eval_tag

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = "883611029a65c12d8cc507bc363dda84a4db10b1"
BASELINE = "9a3a4a6"


def main():
    assert not os.environ.get("DEEPSEEK_API_KEY"), "unset model key"
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-dir", required=True, type=Path)
    args = parser.parse_args()
    raw = args.audit_dir
    assert verify_eval_tag("eval-v1.2") == "90e13b385a639a9164ac78430c50c11a7859f976"
    assert subprocess.check_output(["git", "rev-parse", CANDIDATE], cwd=ROOT, text=True).strip() == CANDIDATE
    probes = [json.loads(line) for line in (raw / "full-round2.jsonl").read_text().splitlines()]
    assert len(probes) == 72 and all(r["mode"] == "full" and r["matched"] for r in probes)
    assert len({(r["id"], r["interface"]) for r in probes}) == 72
    assert json.loads((raw / "full-meta.json").read_text())["status"] == 200
    checks = json.loads((raw / "static-checks.json").read_text())
    assert checks["new_customer_rendered_yaml_byte_identical"] and checks["new_customer_source_line_byte_identical"]
    context_bytes = (raw / "source/build/contexts/JSON-L2.yaml").read_bytes()
    context = yaml.safe_load(context_bytes)
    metrics = yaml.safe_load((raw / "source/semantic/metrics.yaml").read_text())
    measures = {c["call"] for m in context["metrics"] for c in m.get("callables", [])}
    dimensions = {d["name"] + "." + c["name"] for d in context["datasets"] for c in d["columns"]}
    for metric in metrics["metrics"]:
        for variant in metric.get("variants", []):
            member = variant["cube_member"]
            assert member in measures
            assert {r["interface"] for r in probes if r["member"] == member and not r.get("expected_error")} == {"json", "sql"}
    actual = set()
    hidden = []
    model_hashes = {}
    for path in sorted((raw / "source/build/cube/model/cubes").glob("*.yml")):
        model_hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        cube = yaml.safe_load(path.read_text())["cubes"][0]
        for kind in ("measures", "dimensions"):
            for member in cube.get(kind, []):
                name = cube["name"] + "." + member["name"]
                actual.add(name)
                if member.get("public") is False:
                    assert name not in measures | dimensions
                    hidden.append({"member": name, "kind": kind, "publication": "不公开", "counts_as_coverage": False})
    source_hashes = {}
    for name in ("render/common.py", "render/cube.py", "render/measures.py", "render/context.py", "render/syntax/cube_json.md", "render/syntax/cube_sql.md", "semantic/metrics.yaml", "semantic/source.yaml"):
        body = (raw / "source" / name).read_bytes()
        assert body == subprocess.check_output(["git", "show", CANDIDATE + ":" + name], cwd=ROOT)
        source_hashes[name] = hashlib.sha256(body).hexdigest()
    baseline_path = "reports/validation/t16_l2_scope_coverage.json"
    baseline_bytes = subprocess.check_output(["git", "show", BASELINE + ":" + baseline_path], cwd=ROOT)
    baseline = json.loads(baseline_bytes)
    rows = baseline["rows"]
    by_id = {r["qid"]: r for r in rows}
    members = ["sales.DateKey", "sales.sales_amount_qoq_pct", "store.StoreName"]
    by_id["Q94"].update(category="covered", capability="exposed_quarter_shift_variant",
                        standard_member_set=members, measures=["sales.sales_amount_qoq_pct"],
                        dimensions_and_filter_time_members=["sales.DateKey", "store.StoreName"], time_granularity="quarter")
    by_id["Q114"].update(category="c", capability="engine_limit_full_90_day_cohort_not_delivered", standard_member_set=None)
    questions = load_questions()
    assert set(by_id) == {q.qid for q in questions if q.scoring != "judge"}
    assert len(rows) == 109
    for row in rows:
        if row["category"] == "covered":
            assert set(row["standard_member_set"]) <= actual & (measures | dimensions), row["qid"]
    counts = dict(Counter(r["category"] for r in rows))
    assert counts == {"a": 34, "covered": 39, "d": 9, "c": 27}
    counts["b"] = 0
    payload = {"freeze_id": "T16-json-l2-v14-8836110", "status": "fixed; identify by the Git commit containing this registry",
               "candidate_commit": CANDIDATE, "semantic_tag": None, "semantic_tag_note": "v1.4 candidate commit; tag not assumed",
               "eval_tag": "eval-v1.2", "eval_commit": "90e13b385a639a9164ac78430c50c11a7859f976",
               "baseline_registry_commit": BASELINE, "baseline_registry_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
               "model_calls": 0, "scorer_calls": 0, "context_sha256": hashlib.sha256(context_bytes).hexdigest(),
               "probe_file_sha256": hashlib.sha256((raw / "full-round2.jsonl").read_bytes()).hexdigest(),
               "candidate_source_sha256": source_hashes, "model_sha256": model_hashes,
               "category_counts": counts, "strata": dict(Counter(r["stratum"] for r in rows)),
               "changes_from_preregistration": [{"qid": "Q94", "from": "b", "to": "covered"}, {"qid": "Q114", "from": "b", "to": "c"}],
               "mechanical_rule": "execution error first; otherwise compare deduplicated selected/filter/order/time members to the fixed standard set; different sets / same set different result remain separate descriptive categories",
               "rows": rows, "hidden_members": hidden,
               "known_engine_limit_evidence": "reports/validation/t16-v14-86d8826/results.json (12 full-cohort rolling-window failures); current member restored byte-identically to main"}
    folder = ROOT / "reports/validation/t16-v14-8836110"
    folder.mkdir(exist_ok=True)
    output = folder / "coverage.json"
    if output.exists():
        raise RuntimeError("refusing to overwrite a fixed registry")
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    lines = ["# JSON-L2 v1.4 标准成员集与静态分类", "",
             f"固定候选 `{CANDIDATE}`；题库 eval-v1.2；登记版本以包含本表的 Git 提交号标识。尚未假设 semantic-v1.4 tag 已打，后续 tag 必须与本候选交付内容相符。", "",
             "109 个非 judge：主表 98、低区分度 11。能答 39；a 34、b 0、c 27、d 9。仅 Q94 从 b 转能答；Q114 从 b 转已证实接口限制 c，没有伪装成修好。原分数不改，不重评、不估全量。", "",
             "只计 L2 上下文暴露的成员。标准集含输出、筛选、排序、时间成员，去重比较；执行报错优先，其后分别登记‘成员集不同’与‘成员集相同但结果不同’。这不是对所有等价查询的语义证明；不得在全量结果出来后悄悄修改标准集。", "",
             "沿用原来已正确的成员组合；新等价调用名不强制替换既有标准。Q94 的时间粒度须为 quarter。Q114 的 main 原成员仍存在且可调用，但不实现完整截止日前90日客户集合，因此不能计为正确覆盖。", "",
             "a：L1 未写口径；b：L1 承诺但交付未编码；c：已交付对象下的接口表达/实现限制；d：仅展示必答列无法输出。隐藏辅助成员全部不公开，不计能答。", "",
             "| 题号 | 分层 | 类别 | 能力类别 / 标准成员集 |", "|---|---|---|---|"]
    for row in rows:
        detail = ", ".join(row["standard_member_set"]) if row["category"] == "covered" else row["capability"]
        lines.append(f"| {row['qid']} | {row['stratum']} | {row['category']} | {detail} |")
    lines += ["", "## 隐藏成员", "", "15 个辅助度量、8 个技术键维度均不公开。", "",
              "| 成员 | 类型 | 公开状态 | 计覆盖 |", "|---|---|---|---|"]
    for member in hidden:
        lines.append(f"| {member['member']} | {member['kind']} | 不公开 | 否 |")
    output.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("Fixed candidate", CANDIDATE, counts, "hidden", len(hidden))


if __name__ == "__main__":
    main()
