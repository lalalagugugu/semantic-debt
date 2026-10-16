#!/usr/bin/env python
"""Re-execute the public benchmark and compare deterministic verdicts.

The output contains verdict diagnostics and reference-column unit/type metadata.
Questions and SQL remain in ``SEMDEBT_EVAL_DIR``.
"""

from __future__ import annotations

import argparse
import subprocess
import types
import hashlib
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness.scorer import ExecError, score_detailed  # noqa: E402
from harness.value_units import infer_value_kind, is_integer_type, is_numeric_type, quantize_tie  # noqa: E402


RUN_ID = "paper-2026-04-22"
EXCLUDED_QUESTION_IDS = {33}
ORDERED_QUESTION_IDS = {
    7, 25, 27, 33, 45, 46, 67, 69, 73, 74, 78, 79, 85, 87, 88,
    92, 94, 97, 98,
}
TOP_N_RULES = {
    7: (10, (1,)),
    25: (1, (1,)),
    27: (10, (3,)),
    46: (1, (1,)),
    73: (10, (3,)),
    79: (10, (3,)),
    87: (20, (3,)),
    88: (20, (1,)),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    data_dir = os.environ.get("SEMDEBT_DATA_DIR")
    eval_dir = os.environ.get("SEMDEBT_EVAL_DIR")
    if not data_dir or not eval_dir:
        raise SystemExit("SEMDEBT_DATA_DIR and SEMDEBT_EVAL_DIR must be set")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-dir", type=Path, default=Path(data_dir) / "chdb-eval")
    parser.add_argument("--eval-dir", type=Path, default=Path(eval_dir))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="write the complete ID-only validation report")
    parser.add_argument("--previous-results", type=Path, help="compare every verdict with the preceding 600-record run")
    parser.add_argument(
        "--session-bug-baseline",
        type=Path,
        help="list verdict changes from a 600-record run that reused chDB after execution errors",
    )
    return parser.parse_args(argv)


def question_rules(question_id: int, reference_sql: str) -> dict[str, object]:
    top_rule = TOP_N_RULES.get(question_id)
    return {
        "ordered": question_id in ORDERED_QUESTION_IDS and final_order_clause(reference_sql) is not None,
        "top_n": top_rule[0] if top_rule else None,
        "tie_columns": list(top_rule[1]) if top_rule else [],
    }


def final_order_clause(sql: str) -> str | None:
    """Find an outer ORDER BY, excluding comments, strings and nested queries."""
    masked = re.sub(r"--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`[^`]*`", lambda m: " " * len(m.group()), sql, flags=re.DOTALL)
    depth = 0
    start = None
    for token in re.finditer(r"\(|\)|\bORDER\s+BY\b", masked, re.IGNORECASE):
        if token.group() == "(":
            depth += 1
        elif token.group() == ")":
            depth -= 1
        elif depth == 0:
            start = token.end()
    if start is None:
        return None
    return re.split(r"\bLIMIT\b", sql[start:], maxsplit=1, flags=re.IGNORECASE)[0].strip().rstrip(";")


def extend_boundary_ties(sql: str, question_id: int) -> str:
    """Fetch the complete ranked domain; cut the exact boundary in Python."""
    top_rule = TOP_N_RULES.get(question_id)
    if not top_rule:
        return sql
    pattern = re.compile(rf"\bLIMIT\s+{top_rule[0]}\s*;?\s*$", re.IGNORECASE)
    extended, replacements = pattern.subn("", sql)
    if replacements != 1 or final_order_clause(sql) is None:
        raise ValueError(f"q{question_id:02d}: cannot extend Top-N reference boundary")
    return extended


def complete_boundary(rows: list[list[object]], rules: dict[str, object], descending: bool) -> list[list[object]]:
    top_n = rules["top_n"]
    columns = rules["tie_columns"]
    kinds = rules.get("value_kinds", ())
    def tie_key(row):
        return tuple(quantize_tie(row[i], kinds[i] if kinds else "other") for i in columns)
    if top_n is None:
        return rows
    if len(rows) < top_n:
        raise ValueError("Top-N reference contains fewer than N rows")
    # Use the reference's projected values, including its existing ROUND precision.
    # The row encoding breaks ties reproducibly without discarding tied members.
    ordered = sorted(rows, key=lambda row: json.dumps(row, ensure_ascii=False))
    ordered.sort(key=tie_key, reverse=descending)
    boundary = tie_key(ordered[top_n - 1])
    end = top_n
    while end < len(ordered) and tie_key(ordered[end]) == boundary:
        end += 1
    return ordered[:end]


def reference_digest(rows: list[list[object]]) -> str:
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def boundary_hash_versions() -> dict[str, str]:
    """Identify both the unit policy and the boundary/encoding implementation."""
    return {
        "unit_policy_sha256": hashlib.sha256((REPO / "harness/value_units.py").read_bytes()).hexdigest(),
        "boundary_policy_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "serialization_version": "json-compact-utf8-v1",
    }


def verify_reference_digests(digests: list[str], question_id: int) -> None:
    if len(digests) != 3 or len(set(digests)) != 1:
        raise RuntimeError(f"q{question_id:02d}: reference boundary is not reproducible")


def reference_value_kinds(sql: str, columns: list[dict[str, str]]) -> list[str]:
    # Only a complete COUNT select item supplies count provenance. A denominator
    # ending in count() must not reclassify an AOV/percentage expression as count.
    pattern = r"(?:\bSELECT\s+|,)\s*(?:count|countDistinct|countIf|uniqExact)\s*\([^)]*\)\s+(?:AS\s+)?([A-Za-z_]\w*)"
    count_aliases = {match.group(1).lower() for match in re.finditer(pattern, sql, re.IGNORECASE)}
    return ["count" if column["name"].lower() in count_aliases else infer_value_kind(column["name"], column["type"]) for column in columns]


def stable_reference(sess: Any, sql: str, question_id: int, rules: dict[str, object]) -> tuple[list[list[object]], dict[str, object] | None, list[list[object]]]:
    expanded = extend_boundary_ties(sql, question_id)
    payload = json.loads(str(sess.query(expanded, "JSONCompact")))
    rows = payload["data"]
    rules["value_kinds"] = reference_value_kinds(sql, payload["meta"])
    rules["value_types"] = [column["type"] for column in payload["meta"]]
    rules["reference_columns"] = payload["meta"]
    if isinstance(rows, ExecError):
        raise RuntimeError(f"q{question_id:02d} reference failed: {rows.message}")
    if rules["top_n"] is None:
        return rows, None, rows
    descending = not bool(re.search(r"\bASC\s*$", final_order_clause(sql) or "", re.IGNORECASE))
    legacy = sorted(rows, key=lambda row: json.dumps(row, ensure_ascii=False))
    legacy.sort(key=lambda row: tuple(row[i] for i in rules["tie_columns"]), reverse=descending)
    n = rules["top_n"]
    key = tuple(legacy[n - 1][i] for i in rules["tie_columns"])
    end = n
    while end < len(legacy) and tuple(legacy[end][i] for i in rules["tie_columns"]) == key:
        end += 1
    legacy = legacy[:end]
    rows = complete_boundary(rows, rules, descending)
    digests = [reference_digest(rows)]
    for _ in range(2):
        repeated = execute_rows(sess, expanded)
        if isinstance(repeated, ExecError):
            raise RuntimeError(f"q{question_id:02d} repeated reference failed: {repeated.message}")
        digests.append(reference_digest(complete_boundary(repeated, rules, descending)))
    verify_reference_digests(digests, question_id)
    return rows, {"question_id": question_id, "row_count": len(rows), "sha256": digests[0], **boundary_hash_versions(), "repeat_checks": 3, "tie_columns": rules["tie_columns"], "descending": descending, "criterion": "Decimal ROUND_HALF_EVEN: amount=2 digits; ratio/fraction=6; other=6", "value_kinds": rules["value_kinds"]}, legacy


def execute_rows(sess: Any, sql: str) -> list[list[object]] | ExecError:
    try:
        output = str(sess.query(sql, "JSONCompactEachRow"))
        rows = [json.loads(line) for line in output.splitlines() if line.strip()]
    except Exception as error:
        return ExecError(str(error))
    return rows


def open_session(session_module: Any, db_dir: Path) -> Any:
    """Open a clean chDB session with the validation execution settings."""
    sess = session_module.Session(str(db_dir))
    try:
        sess.query("SET max_execution_time = 30")
        sess.query("SET max_threads = 1")
    except Exception:
        sess.close()
        raise
    return sess


def reset_session(sess: Any, session_module: Any, db_dir: Path) -> Any:
    """Discard a failed chDB session before another query can observe its output."""
    sess.close()
    return open_session(session_module, db_dir)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_outcomes(path: Path, systems: list[str], questions: dict[int, Any]) -> dict[tuple[str, int], str]:
    records = load_json(path)["records"]
    outcomes = {(r["system"], r["question_id"]): r["our_outcome"] for r in records}
    expected_keys = {(system, qid) for system in systems for qid in questions}
    if set(outcomes) != expected_keys or len(records) != 600:
        raise ValueError(f"{path} must contain exactly the same 600 system/question keys")
    return outcomes


SYSTEM_LABELS = {
    "claude_claude_opus_4_7_raw": "O-R", "claude_claude_opus_4_7_semantic": "O-S",
    "claude_claude_sonnet_4_6_raw": "S-R", "claude_claude_sonnet_4_6_semantic": "S-S",
    "codex_gpt_5_4_raw": "G-R", "codex_gpt_5_4_semantic": "G-S",
}
INTENTIONAL_BROADER = {
    ("G-R", 7): "边界并列", ("O-S", 27): "边界并列", ("S-S", 27): "边界并列",
    ("S-R", 37): "百分数等价", ("S-S", 64): "百分数等价", ("G-S", 64): "百分数等价",
    ("O-R", 96): "百分数等价", ("O-S", 96): "百分数等价", ("G-R", 96): "百分数等价", ("G-S", 96): "百分数等价",
}


def reviewed_categories() -> dict[tuple[str, int], tuple[str, str]]:
    reviewed = {}
    for line in (REPO / "reports/validation/scorer_check_review.md").read_text().splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 6 and cells[0] in SYSTEM_LABELS.values() and re.fullmatch(r"Q\d+", cells[1]):
            reviewed[(cells[0], int(cells[1][1:]))] = (cells[3], cells[5])
    if len(reviewed) != 68:
        raise ValueError("expected the reviewed 68-case category ledger")
    return reviewed


def verify_count_transition(system: str, question_id: int, before: str, after: str) -> None:
    if before != after and (SYSTEM_LABELS[system], question_id, before, after) != ("S-S", 83, "correct", "wrong"):
        raise RuntimeError(f"unexpected flip: {SYSTEM_LABELS[system]} Q{question_id:02d} {before} -> {after}; stop for user review")


def reference_column_report(columns: list[dict[str, Any]]) -> list[str]:
    active = [c for c in columns if c["question_id"] not in EXCLUDED_QUESTION_IDS]
    lines = ["", "## 参考列量纲覆盖与整数类型守卫", "", "每道参考查询只计一次，按列位置计数，不乘六个系统。99题的类型来自本次参考查询JSONCompact元数据；Q33只通过DESCRIBE TABLE取列结构，仍排除评分。", "", f"| 量纲 | 99题列数 | 占{len(active)}列 | 100题列数 | 占{len(columns)}列 |", "|---|---:|---:|---:|---:|"]
    for kind in ("other", "count", "amount", "percentage", "ratio"):
        n = sum(c["kind"] == kind for c in active)
        all_n = sum(c["kind"] == kind for c in columns)
        lines.append(f"| {kind} | {n} | {n/len(active):.2%} | {all_n} | {all_n/len(columns):.2%} |")
    lines += [f"| 合计 | {len(active)} | 100% | {len(columns)} | 100% |", "", "### 数值类型却判为other", ""]
    for label, group in (("参与评分99题", active), ("全部100题", columns)):
        numeric = [c for c in group if is_numeric_type(c["type"])]
        unknown = [c for c in numeric if c["kind"] == "other"]
        lines.append(f"- {label}：**{len(unknown)}列**；占{len(numeric)}个数值列的**{len(unknown)/len(numeric):.2%}**，占全部{len(group)}列的{len(unknown)/len(group):.2%}。")
    lines += ["", "这是数值列未获量纲atol覆盖的比例；其中也可能有年份、标识等本就不应享受atol的维度列，不等于已确认的金额/比率语义漏判率。", "", "### count但参考类型非整数：继续按0.5%相对容差", "", "以下按题号和列位置列全；不按值是否整除、大小或候选类型决定。整数守卫只接受Int/UInt8/16/32/64/128/256（含Nullable/LowCardinality包装）。", "", "| 题号 | 列位置（1起） | 参考列名 | 返回类型 |", "|---|---:|---|---|"]
    skipped = [c for c in columns if c["kind"] == "count" and not is_integer_type(c["type"])]
    if not skipped:
        lines.append("| — | — | 无 | — |")
    for c in skipped:
        lines.append(f"| Q{c['question_id']:02d} | {c['position']} | `{c['name']}` | `{c['type']}` |")
    lines += ["", f"共{len(skipped)}个列位置、{len({c['name'] for c in skipped})}个去重列名。", "", "### count去重列名（全部100题）", ""]
    lines += [f"- `{name}`" for name in sorted({c["name"] for c in columns if c["kind"] == "count"})]
    return lines


def report_from_results(output: dict[str, Any], path: Path) -> None:
    reviewed = reviewed_categories()
    records = output["records"]
    comparable = [r for r in records if r["our_outcome"] != "excluded"]
    differences = []
    unexplained = []
    for record in comparable:
        if (record["our_outcome"] == "correct") == (record["strict"] == "pass"):
            continue
        label = SYSTEM_LABELS[record["system"]]
        key = (label, record["question_id"])
        if record.get("relative_only_outcome") == "wrong" and record["our_outcome"] == "correct":
            category, notes = "量纲绝对容差", "2026-10-15规则第2条A裁决；量纲由全局参考列名称/类型规则自动识别。"
        elif key in INTENTIONAL_BROADER:
            category, notes = INTENTIONAL_BROADER[key], "冻结规则第4/5/2条有意更宽（按类别）。"
        elif key in reviewed:
            category, notes = reviewed[key]
        else:
            unexplained.append(key)
            category, notes = "原因不明", "需要逐条复核，不能标记完成。"
        differences.append({**record, "label": label, "category": category, "notes": notes})
    broad = sum((r["label"], r["question_id"]) in INTENTIONAL_BROADER or r["category"] == "量纲绝对容差" for r in differences)
    correct = sum(r["our_outcome"] == "correct" for r in comparable)
    format_only = sum(r["our_outcome"] == "wrong" and r["sensitivity"] == "string_or_label_only" for r in comparable)
    wrong_tags = Counter(r["sensitivity"] for r in comparable if r["our_outcome"] == "wrong")
    current_counts = Counter(r["category"] for r in differences if (r["label"], r["question_id"]) not in INTENTIONAL_BROADER and r["category"] != "量纲绝对容差")
    strict_agreements = output["strict_agreements"]
    total = len(comparable)
    date = datetime.now(ZoneInfo("Asia/Singapore")).date()
    lines = ["# T02 评分器对齐检查", "", f"- 重跑日期：{date}", "- 外部 run：`paper-2026-04-22`", "- 执行库：`$SEMDEBT_DATA_DIR/chdb-eval`；没有打开主库。", f"- 已执行 {len(records)} 条；Q33 六条因公开参考不可用而单列，不进入594条的比率分母。", "", "## 历史数字（G0/G4 必须保留）", "", "修复前 strict 为 **515/594（86.7%）**；排除11条有意更宽差异后为 **515/583（88.3%）**。原68条复核主分类为：参考列缺失28、标签或列组合14、额外候选行9、公开工件/重执行差异7、舍入/相对误差4、行序与验证流程3、执行环境不兼容2、参考度量缺失1。8条改类完整保留于 `scorer_check_review.md`；历史类别账本不能被本次剩余差异数覆盖。", "", "## 本次结果", "", f"- strict 一致：**{strict_agreements}/{total}（{strict_agreements / total:.1%}）**。", f"- 排除本次仍存在的 {broad} 条有意更宽差异：**{strict_agreements}/{total - broad}（{strict_agreements / (total - broad):.1%}）**。", f"- analytical 一致：{output['analytical_agreements']}/{total}（{output['analytical_agreement_rate']:.1%}）。", f"- 原因不明：{len(unexplained)}。", "", "| 系统 | 可比较 | strict一致 | 我们更宽 | 我们更严 |", "|---|---:|---:|---:|---:|"]
    for system, label in SYSTEM_LABELS.items():
        group = [r for r in comparable if r["system"] == system]
        agreed = sum((r["our_outcome"] == "correct") == (r["strict"] == "pass") for r in group)
        wider = sum(r["our_outcome"] == "correct" and r["strict"] != "pass" for r in group)
        stricter = sum(r["our_outcome"] != "correct" and r["strict"] == "pass" for r in group)
        lines.append(f"| {label} | {len(group)} | {agreed} | {wider} | {stricter} |")
    lines += ["", "## 三条缺陷的修复证据", "", "1. `ordered` 要求元数据与最终外层 ORDER BY 同时成立；窗口/子查询的排序不作为最终排序。O-R/O-S Q22现按无序完整行集比较，结果见全量表。", "2. 固定单线程运行，Top-N从完整排序域构造参考。使用按全局固定精度量化的参考排序值识别并列；所有题统一使用量纲量化规则，不采用Q88特例。行编码固定同值前缀行序，每个参考三次成员哈希必须一致，否则报错停止。0.5%结果容差不再扩大并列组。", "3. 舍入差异实测：S-S Q24约0.70%/0.53%；O-S Q90最高约2.10%；G-S Q29约12.40%；S-S Q99最高约17.13%。不能统称小于1%。问题#7已裁决A，本次应用量纲绝对下限；历史实测偏差保留用于解释。", "", f"运行条件：`{output['runtime']}`。", "", "| 题号 | 完整边界参考行数 | 三次哈希一致 | SHA256 |", "|---|---:|---|---|"]
    for check in output["boundary_checks"]:
        lines.append(f"| Q{check['question_id']:02} | {check['row_count']} | 是（{check['repeat_checks']}次） | `{check['sha256']}` |")
    lines += ["", "每个边界哈希的版本信息如下。历史记录没有版本时明确标为未记录；跨版本或跨会话须比较量化后的完整成员集合，不能用原始浮点行编码哈希代替。", "", "| 题号 | unit_policy_sha256 | boundary_policy_sha256 | 编码版本 |", "|---|---|---|---|"]
    for check in output["boundary_checks"]:
        lines.append(f"| Q{check['question_id']:02} | `{check.get('unit_policy_sha256', '未记录')}` | `{check.get('boundary_policy_sha256', '未记录')}` | {check.get('serialization_version', '未记录')} |")
    lines += ["", "## 本次剩余主分类与系统性影响", "", "主分类按裁决后的68条逐项账本固定，先记录具名主因，再保留复合次因；不是机械按评分器首个失败码归类。历史Q22问题修复后如已一致，移出本次差异但保留历史账本。", "", "| 类别 | 本次条数 | 系统性影响/规则依据 |", "|---|---:|---|"]
    impacts = {"参考列缺失": "第3条：所有单元缺参考列均判错，包含问句未要求的辅助列；会系统性降低输出较简洁单元的严格准确率。", "标签或列组合": "第2/3条：只去字符串首尾空格，不拼姓名、不翻译标签；对所有单元施加格式敏感性。", "额外候选行": "第1/4条：完整结果集与Top-N行数约束；输出超集的单元均受罚，缺列等复合次因另记。", "公开工件/重执行差异": "属于外部基线的抽样/执行差异，不是全部单元的评分规则变化；六条Q14已由抽样解释，只有G-R Q30根因交T03跟进。", "舍入/相对误差": "第2条：按已裁决A口径增加量纲绝对下限，未被下限覆盖的舍入差异仍可能影响全部单元。", "行序与验证流程": "第4条：修掉任意参考物理行序；同值前缀的严格行序仍可能影响所有Top-N单元，边界成员按确定性精确并列组验证。", "执行环境不兼容": "按本地执行态记exec_error；特定函数生成风格的单元会受本地能力限制，T11/T19须单列环境不兼容。", "参考度量缺失": "第3条：额外派生量不能替代参考度量；各单元必须输出全部参考度量。"}
    for category, impact in impacts.items():
        lines.append(f"| {category} | {current_counts[category]} | {impact} |")
    lines += ["", "## 格式敏感性（不改变判定）", "", f"严格准确率为 **{correct}/{total}（{correct / total:.1%}）**；加上数值投影匹配的 {format_only} 条判错结果，格式敏感性上界为 **{correct + format_only}/{total}（{(correct + format_only) / total:.1%}）**。这不是与外部judge的一致率。", "", f"wrong标记计数：`{dict(wrong_tags)}`。exec_error/refused/excluded不被格式放宽挽回。", "", "数值投影保留联合行匹配、完整行数、NULL、排序、Top-N及每一数值参考列；删除非数值列只产生报告层上界，不证明标签指向同一实体。数字编码的维度（如月份）也视为数值列：改成文字时保守地不算纯格式挽回；没有角色元数据时不猜业务含义。纯文本参考标为no_numeric_reference，结构不符单列，不当作数值计算错。", "", "## 全部strict差异与次因", "", "| 系统 | 题号 | 我们 | strict | 主分类 | 说明/次因 |", "|---|---|---|---|---|---|"]
    for r in differences:
        lines.append(f"| {r['label']} | Q{r['question_id']:02} | {r['our_outcome']} | {r['strict']} | {r['category']} | {r['notes']} |")
    lines += ["", "## 全部600条判定（含analytical与敏感性）", "", "| 系统 | 题号 | 我们 | strict | analytical | 原因 | 敏感性 |", "|---|---|---|---|---|---|---|"]
    for r in records:
        lines.append(f"| {SYSTEM_LABELS[r['system']]} | Q{r['question_id']:02} | {r['our_outcome']} | {r['strict']} | {r['analytical']} | {r['our_reason'] or 'matched'} | {r['sensitivity'] or '—'} |")
    lines += ["", "## 复现与验收边界", "", "```bash", "uv run pytest", "uv run python scripts/validate_scorer.py --output /tmp/t02-scorer-check-ruling.json --report reports/validation/scorer_check.md", "```", "", "运行前设置SEMDEBT_EVAL_DIR、SEMDEBT_DATA_DIR；固定本报告的运行版本，单进程独占chdb-eval。所有候选原样执行，重执行或参考失败不静默重试。", "", "T03只跟进G-R Q30；其余Q14不是未解释的数据漂移。T05/T05b/T06落实跨执行器可复现边界组要求，不能用本卡三次SQL重复取代跨厂商独立重算。G0/G4须同时披露历史低一致率、当前数字、系统性影响和敏感性上界，不能声称跨厂商独立核对已完成。"]
    failed_candidates = [r for r in records if r["reexec_error"] is not None]
    failed_outcomes = Counter(r["our_outcome"] for r in failed_candidates)
    session_changes = [] if not output["session_bug_baseline_compared"] else [
        r for r in records if r["session_bug_baseline_outcome"] != r["our_outcome"]
    ]
    lines += [
        "",
        "## chDB 失败会话污染修复（G0 无需重新确认）",
        "",
        f"候选查询执行失败后立即关闭并重建 chDB session，重新应用固定执行设置。本轮发生 **{output['session_resets']}** 次重置：最终归类为 exec_error {failed_outcomes['exec_error']} 条，另有排除评分的 Q33 失败 {failed_outcomes['excluded']} 条。",
        f"是否与修复前600条脏会话基线逐条比较：{output['session_bug_baseline_compared']}；判定变化 **{len(session_changes)}** 条。",
        "用户于2026-10-16确认：会话修复已收到，0条判定变化，G0无需重新确认。Q79成员复现性属于eval-v1冻结条件。",
        "",
        "| 系统 | 题号 | 修复前 | 修复后 |",
        "|---|---|---|---|",
    ]
    for r in session_changes:
        lines.append(f"| {SYSTEM_LABELS[r['system']]} | Q{r['question_id']:02d} | {r['session_bug_baseline_outcome']} | {r['our_outcome']} |")
    if not session_changes:
        lines.append("| — | — | 无变化 | 无变化 |")
    flipped = [r for r in comparable if r.get("baseline_outcome") == "wrong" and r["our_outcome"] == "correct"]
    atol_flipped = [r for r in comparable if r.get("relative_only_outcome") == "wrong" and r["our_outcome"] == "correct"]
    count_flipped = [r for r in comparable if r.get("before_count_outcome") != r["our_outcome"]]
    lines += ["", "## 2026-10-15 A裁决与计数收紧", "", f"旧提交{output.get('baseline_ref')}到本次wrong→correct：{len(flipped)}条；固定本次并列参考、仅加atol的wrong→correct：{len(atol_flipped)}条；A裁决历史为7条wrong→correct、0条反向（strict520/594；排除12条有意更宽后520/582）。本轮另按#8收紧计数，见下表。", "", "| 系统 | 题号 | 旧判定 | 新判定 | 量纲向量 |", "|---|---|---|---|---|"]
    for r in flipped:
        lines.append(f"| {SYSTEM_LABELS[r['system']]} | Q{r['question_id']:02} | wrong | correct | {r['value_kinds']} |")
    lines += ["", f"#8正式裁决：exact_counts=True，仅count且参考返回整数型时候选==参考；不使用相对容差、atol或百分数换算。与同批关闭开关的结果相比共{len(count_flipped)}条翻转。每条均检查方向；预期外翻转立即停止。", "", f"是否同时与上一轮600条记录逐条核对：{output['previous_results_compared']}。", "", "| 系统 | 题号 | 收紧前 | 正式判定 |", "|---|---|---|---|"]
    for r in count_flipped:
        lines.append(f"| {SYSTEM_LABELS[r['system']]} | Q{r['question_id']:02} | {r['before_count_outcome']} | {r['our_outcome']} |")
    lines += ["", "## 自动量纲与并列量化契约", "", "参考列名按CamelCase/下划线拆词、忽略大小写，固定优先级：百分比(pct/percent/percentage/percentile/pp) → 比率(ratio/rate/correlation/corr) → 计数(count/countDistinct/num/n/customers/orders/stores/brands/employees/observations/reports/units/returns、cohort size、returned) → 金额(amount/amt/revenue/sales/spend/spent/cost/cogs/price/profit/income/budget/quota/ltv/dollars/discount/margin、lifetime value) → other。整数类型的sales聚合且名称不含amount/price/revenue时归count。不读取候选列名，COUNT/countDistinct/countIf/uniqExact表达式的输出别名优先标为count；不按数值大小或题号猜单位；别名必须表达单位，不能识别时atol=0。外部旧题由适配器推断；T05新题显式声明value_kinds，infer_value_kind仅交叉校验，不一致告警。harness还须透传参考返回类型value_types。", "", "比率atol=1e-4；百分比按小数形式归一后atol=1e-4（原百分比数值单位相当于0.01）；金额atol=0.01；其余0。只增加结果匹配边，不进入并列键。金额并列键Decimal保留2位、比率小数形式6位、其他数值6位；ROUND_HALF_EVEN一次固定，不逐题指定。名称推断有覆盖边界：不是语义证明，未知列不享受额外容差。", "", "| 题号 | 自动参考列量纲（顺序对应参考列） |", "|---|---|"]
    seen = set()
    for r in records:
        if r['question_id'] not in seen:
            lines.append(f"| Q{r['question_id']:02} | {r.get('value_kinds', [])} |")
            seen.add(r['question_id'])
    lines += ["", "## 历史运行记录保留", "", "- A轮之前：strict519/594（87.4%），排除9条有意更宽后519/585（88.7%）。", "- A轮：correct252、wrong303、exec_error39、excluded6；strict520/594（87.5%），排除12条有意更宽后520/582（89.3%）；7条wrong→correct、0条反向。", "- A轮首次预跑因COUNT识别器回归测试发现问题而中止；中止时旧查询未结束，首次重启遇到chdb-eval锁；确认旧进程退出后才完成验收运行。预跑和连接失败未混入候选结果。", "- 当时#8仅做反事实，估算S-S Q83一条correct→wrong；本轮按用户裁决正式执行，并增加参考整数类型守卫。"]
    lines += reference_column_report(output["reference_columns"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if unexplained:
        raise RuntimeError(f"unexplained strict differences: {unexplained}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    benchmark_path = args.eval_dir / "vendor/cube/text_to_sql_benchmark.json"
    run_root = args.eval_dir / "vendor/cube/published-runs" / RUN_ID
    benchmark = load_json(benchmark_path)
    questions = {int(item["id"]): item for item in benchmark["questions"]}
    systems = sorted(
        path.name
        for path in run_root.iterdir()
        if path.is_dir() and path.name not in {"reference", "scoring"}
    )
    if len(questions) != 100 or len(systems) != 6:
        raise SystemExit(f"expected 100 questions and 6 systems, got {len(questions)} and {len(systems)}")

    from chdb import session

    sess = open_session(session, args.db_dir)
    previous = None
    if args.previous_results is not None:
        previous = load_outcomes(args.previous_results, systems, questions)
    session_bug_baseline = None
    if args.session_bug_baseline is not None:
        session_bug_baseline = load_outcomes(args.session_bug_baseline, systems, questions)
    records: list[dict[str, object]] = []
    reference_columns = []
    references: dict[int, list[list[object]] | ExecError] = {}
    legacy_references = {}
    baseline_ref = "ad0b767"
    baseline_source = subprocess.run(["git", "show", f"{baseline_ref}:harness/scorer.py"], cwd=REPO, check=True, capture_output=True, text=True).stdout
    baseline = types.ModuleType("_t02_baseline")
    sys.modules[baseline.__name__] = baseline
    exec(compile(baseline_source, "<baseline scorer>", "exec"), baseline.__dict__)
    rules_by_id = {qid: question_rules(qid, q["expected_sql"]) for qid, q in questions.items()}
    boundary_checks = []
    session_resets = 0
    try:
        runtime_version = str(sess.query("SELECT version()", "CSV")).strip()
        for question_id, question in sorted(questions.items()):
            if question_id in EXCLUDED_QUESTION_IDS:
                references[question_id] = ExecError("published reference excluded")
                schema = json.loads(str(sess.query("DESCRIBE TABLE (" + question["expected_sql"].strip().rstrip(";") + ")", "JSONCompact")))
                meta = [{"name": row[0], "type": row[1]} for row in schema["data"]]
                kinds = reference_value_kinds(question["expected_sql"], meta)
                reference_columns.extend({"question_id": question_id, "position": i + 1, **column, "kind": kind} for i, (column, kind) in enumerate(zip(meta, kinds)))
                continue
            references[question_id], check, legacy_references[question_id] = stable_reference(sess, question["expected_sql"], question_id, rules_by_id[question_id])
            rule = rules_by_id[question_id]
            reference_columns.extend({"question_id": question_id, "position": i + 1, **column, "kind": kind} for i, (column, kind) in enumerate(zip(rule["reference_columns"], rule["value_kinds"])))
            if check is not None:
                boundary_checks.append(check)

        completed = 0
        for system in systems:
            print(f"executing {system}", flush=True)
            for question_id in sorted(questions):
                candidate_record = load_json(run_root / system / f"q{question_id:02d}.json")
                candidate = execute_rows(sess, candidate_record["sql"])
                if isinstance(candidate, ExecError):
                    sess = reset_session(sess, session, args.db_dir)
                    session_resets += 1
                strict_record = load_json(run_root / "scoring" / system / f"q{question_id:02d}.json")
                reference = references[question_id]

                if question_id in EXCLUDED_QUESTION_IDS:
                    result_outcome = "excluded"
                    result_reason = "published_reference_unavailable"
                    reference_count = None
                    sensitivity = None
                    old_outcome = exact_outcome = tolerance_baseline = before_count = "excluded"
                elif isinstance(reference, ExecError):
                    raise AssertionError("unexpected reference error")
                else:
                    rules = rules_by_id[question_id]
                    old_candidate = baseline.ExecError(candidate.message) if isinstance(candidate, ExecError) else candidate
                    old_outcome = baseline.score(old_candidate, [legacy_references[question_id]], rules)
                    tolerance_baseline = score_detailed(candidate, [reference], {**rules, "exact_counts": False, "use_absolute_tolerance": False}).outcome
                    before_count = score_detailed(candidate, [reference], {**rules, "exact_counts": False}).outcome
                    result = score_detailed(candidate, [reference], {**rules, "exact_counts": True})
                    exact_outcome = result.outcome
                    verify_count_transition(system, question_id, before_count, result.outcome)
                    result_outcome = result.outcome
                    result_reason = ("execution_environment_incompatible" if "UNKNOWN_FUNCTION" in candidate.message else "execution_error") if isinstance(candidate, ExecError) else result.reason
                    reference_count = len(reference)
                    sensitivity = result.sensitivity

                if previous is not None:
                    verify_count_transition(system, question_id, previous[(system, question_id)], result_outcome)
                    if previous[(system, question_id)] != before_count:
                        raise RuntimeError(f"{SYSTEM_LABELS[system]} Q{question_id:02d}: pre-count verdict differs from prior run; stop for user review")
                records.append(
                    {
                        "system": system,
                        "question_id": question_id,
                        "our_outcome": result_outcome,
                        "our_reason": result_reason,
                        "sensitivity": sensitivity,
                        "baseline_outcome": old_outcome,
                        "relative_only_outcome": tolerance_baseline,
                        "exact_count_outcome": exact_outcome,
                        "before_count_outcome": before_count,
                        "previous_outcome": previous[(system, question_id)] if previous is not None else None,
                        "session_bug_baseline_outcome": session_bug_baseline[(system, question_id)] if session_bug_baseline is not None else None,
                        "value_types": rules_by_id[question_id].get("value_types", []),
                        "value_kinds": rules_by_id[question_id].get("value_kinds", []),
                        "ordered": rules_by_id[question_id]["ordered"],
                        "strict": strict_record["verdict"],
                        "analytical": strict_record["analytical_verdict"],
                        "candidate_row_count": None if isinstance(candidate, ExecError) else len(candidate),
                        "reference_row_count": reference_count,
                        "reexec_error": ("execution_environment_incompatible" if "UNKNOWN_FUNCTION" in candidate.message else "execution_error") if isinstance(candidate, ExecError) else None,
                    }
                )
                completed += 1
                if completed % 10 == 0:
                    print(f"executed {completed}/600", flush=True)
    finally:
        sess.close()

    flips = [r for r in records if r["before_count_outcome"] != r["our_outcome"]]
    if len(flips) != 1 or (SYSTEM_LABELS[flips[0]["system"]], flips[0]["question_id"]) != ("S-S", 83):
        raise RuntimeError("expected exactly one S-S Q83 correct -> wrong flip; stop for user review")
    strict_comparable = [record for record in records if record["our_outcome"] != "excluded"]
    strict_agreements = sum(
        (record["our_outcome"] == "correct") == (record["strict"] == "pass")
        for record in strict_comparable
    )
    analytical_agreements = sum(
        (record["our_outcome"] == "correct") == (record["analytical"] == "pass")
        for record in strict_comparable
    )
    output = {
        "run_id": RUN_ID,
        **boundary_hash_versions(),
        "baseline_ref": baseline_ref,
        "runtime": {"version": runtime_version, "max_threads": 1, "max_execution_time": 30},
        "boundary_checks": boundary_checks,
        "systems": systems,
        "executed_candidates": len(records),
        "excluded_records": len(records) - len(strict_comparable),
        "strict_agreements": strict_agreements,
        "strict_comparable": len(strict_comparable),
        "strict_agreement_rate": strict_agreements / len(strict_comparable),
        "analytical_agreements": analytical_agreements,
        "analytical_agreement_rate": analytical_agreements / len(strict_comparable),
        "records": records,
        "reference_columns": reference_columns,
        "exact_counts": True,
        "previous_results_compared": previous is not None,
        "session_bug_baseline_compared": session_bug_baseline is not None,
        "session_resets": session_resets,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.report is not None:
        report_from_results(output, args.report)
    print(
        f"strict agreement: {strict_agreements}/{len(strict_comparable)} "
        f"({strict_agreements / len(strict_comparable):.1%})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
