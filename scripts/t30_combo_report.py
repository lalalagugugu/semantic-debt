"""T30 offline report: verified saved results, paired questions, no API or SQL calls."""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.rescore_t23 import Source, frozen_bank, rescore_source
from scripts.t30_run_on_chdb_copy import BudgetBoundary

REPO = Path(__file__).resolve().parents[1]
CELL = "SQL-L1plus-tuned-instr"
SYSTEM_SHA = "16f3b0e2cc3b3ae547328c9c918f78be6acffac961c39becb4d54e477a6e6445"
FINGERPRINT = "e72d3c7f663d3e1383b00b3884cb4501"
BASELINES = {
    "SQL-L1plus": "20261025-T22b-l1plus-l3a-03",
    "SQL-L1-tuned-instr": "20261025-T14-tuned-01",
}
VERSIONS = ("v2", "v3")
CODE_FILES = ("scripts/t30_combo_report.py", "scripts/rescore_t23.py",
              "harness/scorer_v2.py", "harness/scorer_v3.py")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate(rows, ids):
    counts = Counter((r["qid"], r["rep"]) for r in rows)
    expected = {(qid, rep) for qid in ids for rep in (1, 2, 3)}
    if set(counts) != expected or any(n != 1 for n in counts.values()):
        raise ValueError("Missing, extra or duplicate attempts")
    if any(r["status"] != "done" or r["final"][v]["outcome"] not in
           {"correct", "wrong", "exec_error", "refused"} for r in rows for v in VERSIONS):
        raise ValueError("Incomplete or unscored attempts")


def metrics(rows, ids, version):
    selected = [r for r in rows if r["qid"] in ids]
    validate(selected, ids)
    hits = Counter({qid: 0 for qid in ids})
    outcomes = Counter()
    for row in selected:
        outcome = row["final"][version]["outcome"]
        outcomes[outcome] += 1
        hits[row["qid"]] += outcome == "correct"
    return {"questions": len(ids), "attempts": len(selected), "correct": sum(hits.values()),
            "accuracy": sum(hits.values()) / len(selected),
            "all_correct": sum(n == 3 for n in hits.values()),
            "mixed": sum(0 < n < 3 for n in hits.values()),
            "all_wrong": sum(n == 0 for n in hits.values()),
            "all_wrong_ids": sorted(qid for qid, n in hits.items() if n == 0),
            "outcomes": dict(outcomes)}


def paired(baseline, combo, ids, version):
    def by_question(rows):
        hits = Counter({qid: 0 for qid in ids})
        for row in rows:
            if row["qid"] in ids:
                hits[row["qid"]] += row["final"][version]["outcome"] == "correct"
        return hits

    validate([r for r in baseline if r["qid"] in ids], ids)
    validate([r for r in combo if r["qid"] in ids], ids)
    a, b = by_question(baseline), by_question(combo)
    differences = [(b[q] - a[q]) / 3 for q in sorted(ids)]
    rng = random.Random(0)
    bootstrap = sorted(sum(rng.choice(differences) for _ in differences) / len(differences)
                       for _ in range(5000))
    return {"questions": len(ids), "diff_pp": 100 * sum(differences) / len(differences),
            "lo_pp": 100 * bootstrap[125], "hi_pp": 100 * bootstrap[4874],
            "better": sum(x > 0 for x in differences), "worse": sum(x < 0 for x in differences)}


def reconcile_receipts(rows, raw_dir):
    cost = Decimal(0)
    recorded = set()
    usage = Counter()
    fingerprints = Counter()
    for row in rows:
        subtotal = Decimal(0)
        if row.get("peak") is not False:
            raise ValueError("Expected off-peak receipts only")
        for turn in row["turns"]:
            path = raw_dir / f"{row['qid']}_r{row['rep']}_t{turn['turn']}.json"
            raw = path.read_bytes()
            if digest(raw) != turn["raw_sha256"]:
                raise ValueError(f"Receipt hash mismatch: {path.name}")
            payload = json.loads(raw)
            subtotal += BudgetBoundary.receipt_cost(raw)
            fingerprints[payload.get("system_fingerprint")] += 1
            for key in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens"):
                usage[key] += payload["usage"][key]
            recorded.add(path.name)
        if abs(subtotal - Decimal(str(row["cost_cny"]))) > Decimal("0.0000000001"):
            raise ValueError(f"Log/receipt cost mismatch: {row['qid']}/r{row['rep']}")
        cost += subtotal
    if recorded != {p.name for p in raw_dir.glob("*_r*_t[01].json")}:
        raise ValueError("Unlogged API receipts need reconciliation")
    if set(fingerprints) != {FINGERPRINT}:
        raise ValueError("Unexpected model fingerprint")
    return {"cost_cny": str(cost), "calls": len(recorded), "usage": dict(usage),
            "fingerprints": dict(fingerprints),
            "transport_retries": sum(t.get("transport_retries", 0) for r in rows for t in r["turns"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--scored-run", required=True)
    args = parser.parse_args(argv)
    for name in (args.run, args.scored_run):
        if Path(name).name != name or name in {".", ".."}:
            parser.error("Run IDs must be single directory names")
    target = REPO / "runs" / args.scored_run
    if target.exists():
        raise FileExistsError("Append-only logs: select a new scored-run ID")
    code_hashes = {name: digest((REPO / name).read_bytes()) for name in CODE_FILES}
    raw_root = Path(os.environ["SEMDEBT_DATA_DIR"]) / "runs-raw"
    sources = {}
    for cell, run in {CELL: args.run, **BASELINES}.items():
        path = REPO / "runs" / run / f"{cell}.jsonl"
        sources[cell] = Source(path, "repo", path.read_bytes())
    raw_rows = [json.loads(line) for line in sources[CELL].data.splitlines() if line.strip()]
    if any(r.get("status") != "done" for r in raw_rows):
        raise ValueError("Run contains non-done attempts; reconcile before reporting completion")
    if {r["system_sha256"] for r in raw_rows} != {SYSTEM_SHA}:
        raise ValueError("Combo system message changed")
    if {r.get("semantic_tag") for r in raw_rows} != {"semantic-combo-v1"}:
        raise ValueError("Unexpected combo semantic tag")
    receipts = reconcile_receipts(raw_rows, raw_root / args.run / CELL)
    if Decimal(receipts["cost_cny"]) > 8:
        raise ValueError("Budget exceeded; do not report a successful full run")
    with frozen_bank(Path(os.environ["SEMDEBT_EVAL_DIR"])) as (questions, columns, commit, archive_hash):
        all_ids = {q.qid for q in questions.values() if q.scoring == "deterministic"}
        main_ids = {qid for qid in all_ids if not questions[qid].meta["low_discrimination"]}
        groups = {"主表": main_ids,
                  "留出": {qid for qid in main_ids if questions[qid].meta["split"] == "heldout"},
                  "调优": {qid for qid in main_ids if questions[qid].meta["split"] == "tuning"}}
        if [len(all_ids), *(len(ids) for ids in groups.values())] != [109, 98, 49, 49]:
            raise ValueError("Unexpected question strata")
        scored, inventory = {}, []
        for cell, source in sources.items():
            scored[cell], other = rescore_source(source, questions, columns, raw_root, args.scored_run, commit)
            if other:
                raise ValueError(f"Unexpected non-done source records: {cell}: {other}")
            validate(scored[cell], all_ids)
            inventory.append({"cell": cell, "run": source.run, "log_sha256": digest(source.data)})
            print(f"{cell}: {len(scored[cell])} attempts rescored", flush=True)
        totals = {cell: {v: {g: metrics(rows, ids, v) for g, ids in {**groups, "含低区分度": all_ids}.items()}
                         for v in VERSIONS} for cell, rows in scored.items()}
        comparisons = [{"version": v, "baseline": base, "group": g,
                        **paired(scored[base], scored[CELL], ids, v)}
                       for v in VERSIONS for base in BASELINES for g, ids in groups.items()]
    if any(source.path.read_bytes() != source.data for source in sources.values()):
        raise ValueError("Source logs changed while reporting")
    if code_hashes != {name: digest((REPO / name).read_bytes()) for name in CODE_FILES}:
        raise ValueError("Scoring code changed while reporting")
    target.mkdir()
    for cell, rows in scored.items():
        with (target / f"{sources[cell].run}--{cell}.jsonl").open("x") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {"eval_tag": "eval-v1.2", "eval_commit": commit, "bank_archive_sha256": archive_hash,
                "sources": inventory, "code_sha256": code_hashes, "system_sha256": SYSTEM_SHA,
                "receipts": receipts, "metrics": totals, "comparisons": comparisons,
                "bootstrap_samples": 5000, "bootstrap_seed": 0}
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    lines = ["# T30 叠加单元", "", f"单元：`{CELL}`；109 题 × 3 次；付费运行 `{args.run}`。",
             f"离线重评：`{args.scored_run}`；v2 主数字，v3 敏感性分析；judge 类别不运行，低区分度类别不进主表。",
             f"实际费用（已返回 usage 核算）：{receipts['cost_cny']} 元 / 8 元；API 调用 {receipts['calls']} 次；传输重试 {receipts['transport_retries']} 次。",
             f"系统消息 SHA-256：`{SYSTEM_SHA}`。", "",
             "两个 combo tag 均为 `2f2d6446af17acca1bb15bf7779bb1d859a3e85b`；题库 `eval-v1.2=" + commit + "`。",
             "费用按每个原始回包哈希与 token 核算，执行结果按原始哈希离线重评；无额外模型或 SQL 调用。", "",
             "| 类别 | 单元 | 主表（98 × 3） | 留出（49 × 3） | 调优（49 × 3） |", "|---|---|---:|---:|---:|"]
    if receipts["transport_retries"]:
        lines[7:7] = ["传输失败请求未返回的 usage 无法从本地核实，未把未知费用计为零；费用守卫按已返回回包累计。", ""]
    for v in VERSIONS:
        for cell in ("SQL-L1plus", "SQL-L1-tuned-instr", CELL):
            values = [totals[cell][v][g] for g in groups]
            lines.append(f"| {v} | {cell} | " + " | ".join(
                f"{100 * m['accuracy']:.1f}%（{m['correct']}/{m['attempts']}）" for m in values) + " |")
    lines += ["", "## 按题配对", "", "每题先算 3 次正确率，再对题自助抽样 5,000 次，种子 0；区间为 95%。差为叠加单元减对照单元。", "",
              "| 类别 | 对照单元 | 题类别 | 题数 | 差（百分点） | 95% 区间 | 变好 / 变差题数 |",
              "|---|---|---|---:|---:|---|---:|"]
    for r in comparisons:
        lines.append(f"| {r['version']} | {r['baseline']} | {r['group']} | {r['questions']} | "
                     f"{r['diff_pp']:+.1f} | [{r['lo_pp']:+.1f}, {r['hi_pp']:+.1f}] | {r['better']} / {r['worse']} |")
    lines += ["", "## 叠加单元的作答类别（109 × 3）", "",
              "| 评分类别 | 单元 | 作答类别 | 次数 |", "|---|---|---|---:|"]
    for v in VERSIONS:
        for outcome in ("correct", "wrong", "exec_error", "refused"):
            count = totals[CELL][v]["含低区分度"]["outcomes"].get(outcome, 0)
            lines.append(f"| {v} | {CELL} | {outcome} | {count} |")
    lines += ["", "## 叠加单元的三次稳定性", "", "| 类别 | 题类别 | 题数 | 3 次全对 | 有对有错 | 3 次全错 |", "|---|---|---:|---:|---:|---:|"]
    for v in VERSIONS:
        for group, m in totals[CELL][v].items():
            lines.append(f"| {v} | {group} | {m['questions']} | {m['all_correct']} | {m['mixed']} | {m['all_wrong']} |")
    lines += ["", "## 叠加单元的三次全错题号", "", "| 类别 | 题类别 | 题号 |", "|---|---|---|"]
    for v in VERSIONS:
        for group in groups:
            lines.append(f"| {v} | {group} | {', '.join(totals[CELL][v][group]['all_wrong_ids']) or '—'} |")
    lines += ["", "## 解读限制", "", "按预登记规则删除 12 条冲突条目，其中 9 条为示例 SQL；叠加单元因此偏吃亏，结果作为叠加效果的下限。",
              "留出题与调优题共用指标口径和约定，留出结果不能代表对未见指标的泛化；v3 只作敏感性分析。", "",
              f"复算：`uv run python scripts/t30_combo_report.py --run {args.run} --scored-run <新的离线run编号>`。"]
    (REPO / "reports/results/combo.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"receipts": receipts, "combo_metrics": totals[CELL]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
