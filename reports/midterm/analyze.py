"""Recompute T24 from frozen verdicts; no model calls or database sessions.

Run from the card checkout: uv run python reports/midterm/analyze.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from harness.cells import PEAK_MULTIPLIER, PRICES_OFFPEAK

DIRECT = "20261018-T13-sql-direct-01-rescore-01"
EXPLORER = "20261019-T15-explorer-01-rescore-01"
L2 = "20261019-T16-full-v14-sql-new-01-rescore-01"
L2E = ["20261020-T15-explorer-l2e-02", "20261020-T15-explorer-l2e-03"]
SPECS = [(c, c, [DIRECT], "定稿") for c in ("SQL-L0", "SQL-R", "SQL-L1", "SQL-L1c", "SQL-L1.5W")]
SPECS += [("SQL-L1.5S", "SQL-L1.5S", ["20261019-T13-l15s-v14-01"], "定稿 semantic-v1.4"),
          ("SQL-L0-E", "SQL-L0-E", [EXPLORER], "定稿"),
          ("SQL-L1-E", "SQL-L1-E", [EXPLORER], "定稿"),
          ("SQL-L2", "SQL-L2", [L2], "定稿 新说明"),
          ("JSON-L2", "JSON-L2", ["20261019-T16-full-v14-json-01-rescore-01"], "定稿"),
          ("SQL-L2-E", "SQL-L2-E", L2E, "定稿 续跑合并"),
          *[(c, c, ["20261019-C13-ladder-02"], "定稿；T4 仅留出题")
            for c in ("SQL-L1-T2", "SQL-L1-T3", "SQL-L1-T4")],
          ("SQL-L1.5S-old", "SQL-L1.5S", [DIRECT], "旧版；被 SQL-L1.5S semantic-v1.4 替代"),
          ("SQL-L2-notes-v12", "SQL-L2-notes-v12", ["20261019-T16-full-v14-sql-old-01-rescore-01"],
           "旧说明；被 SQL-L2 新说明替代")]
# The 19 main-table ids identified in metric-text-vs-impl.md, excluding judge Q45
# and low-discrimination Q79/Q85. Keep this fixed for both 98/109 sensitivity tables.
METRIC19 = {f"Q{i:02}" for i in (9, 20, 21, 27, 31, 34, 38, 49, 50, 52, 70, 73, 77, 87,
                                111, 112, 113, 114, 117)}
COMMAND = "uv run python reports/midterm/analyze.py"
SOURCES = {}


def track(path):
    path = Path(path)
    raw = path.read_bytes()
    SOURCES[str(path.relative_to(ROOT))] = {"sha256": hashlib.sha256(raw).hexdigest(),
                                          "lines": len(raw.splitlines())}
    return raw.decode()


def write(name, lines):
    (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def table(headers, rows):
    return ["| " + " | ".join(map(str, headers)) + " |", "|" + "---|" * len(headers),
            *["| " + " | ".join(str(v).replace("|", " / ").replace("\n", " ") for v in row) + " |" for row in rows]]


def pct(k, n):
    return f"{k}/{n}（{100*k/n:.1f}%）" if n else "—"


def good(r):
    return r["final"]["outcome"] == "correct"


def bank():
    root = os.environ["SEMDEBT_EVAL_DIR"]
    commit = subprocess.check_output(["git", "-C", root, "rev-parse", "eval-v1.2^{commit}"], text=True).strip()
    result = {}
    files = subprocess.check_output(["git", "-C", root, "ls-tree", "--name-only", "eval-v1.2:questions"], text=True)
    for name in files.splitlines():
        if name == "pilot.yaml" or not name.endswith(".yaml"):
            continue
        raw = subprocess.check_output(["git", "-C", root, "show", f"eval-v1.2:questions/{name}"], text=True)
        for q in yaml.safe_load(raw)["questions"]:
            labels = q["labels"]
            result[q["id"]] = {"judge": q.get("scoring", "deterministic") == "judge",
                                 "low": bool(labels["low_discrimination"]["criteria"]),
                                 "type": labels["complexity_source"]["primary"]}
    assert len(result) == 122
    return result, commit


def load(cell, runs):
    pairs, replaced, all_rows = {}, [], []
    for run in runs:
        path = ROOT / "runs" / run / f"{cell}.jsonl"
        for n, line in enumerate(track(path).splitlines(), 1):
            r = json.loads(line)
            r["source"] = f"{path.relative_to(ROOT)}:{n}"
            all_rows.append(r)
            assert r["status"] == "done", r["source"]
            key = (r["qid"], r["rep"])
            if key in pairs:
                assert runs == L2E and key in {("Q80", 2), ("Q81", 1)}, key
                replaced.append(pairs[key]["source"])
            pairs[key] = r
    return list(pairs.values()), all_rows, replaced


def stability(rs):
    groups = defaultdict(list)
    for r in rs:
        groups[r["qid"]].append(r)
    assert all(sorted(r["rep"] for r in v) == [1, 2, 3] for v in groups.values())
    return {q: ("全对" if sum(map(good, v)) == 3 else "全错" if not any(map(good, v)) else "时对时错")
            for q, v in groups.items()}


def bootstrap(a, b):
    da, db = defaultdict(list), defaultdict(list)
    for r in a:
        da[r["qid"]].append(int(good(r)))
    for r in b:
        db[r["qid"]].append(int(good(r)))
    assert da.keys() == db.keys() and da
    diffs = [sum(da[q])/3 - sum(db[q])/3 for q in sorted(da)]
    rng = random.Random(20261020)
    draws = sorted(sum(rng.choices(diffs, k=len(diffs)))/len(diffs) for _ in range(10000))
    return f"{100*sum(diffs)/len(diffs):+.1f}", f"[{100*draws[250]:+.1f}, {100*draws[9749]:+.1f}]"


def purpose(sql):
    """Observable SQL shapes, not inferred user intent; mutually exclusive priority."""
    s = (sql or "").lower()
    if not s.strip():
        return "无可解析查询"
    if re.search(r"\b(show|describe|explain)\b|information_schema|system\.", s):
        return "结构或执行计划"
    if re.search(r"\b(sum(?:if)?|avg(?:if)?|min(?:if)?|max(?:if)?|uniq\w*|measure|rank|dense_rank|row_number|"
                 r"quantile\w*|median\w*|stddev\w*|varpop|varsamp|corr|argmax|argmin|any|groupuniqarray)\s*\(", s):
        return "聚合或候选答案核验"
    if re.search(r"\bdistinct\b|\bgroup\s+by\b", s):
        return "枚举或分组查值"
    if re.search(r"\bcount(?:if|distinct)?\s*\(", s):
        return "行数或存在性检查"
    return "明细或样例查值"


def cost(r, cold=False):
    u, p = r["usage"], PRICES_OFFPEAK[r["model_requested"]]
    hit, miss = (0, u["prompt_tokens"]) if cold else (u["cache_hit_tokens"], u["cache_miss_tokens"])
    return (PEAK_MULTIPLIER if r.get("peak") else 1) * (hit*p["hit"] + miss*p["miss"] + u["completion_tokens"]*p["output"])/1e6


def verify_raw(rows):
    evidence = []
    for r in rows:
        turn = r["turns"][-1]
        run = r.get("rescored_from", {}).get("run_id", r["run_id"])
        stem = f"runs-raw/{run}/{r['cell']}/{r['qid']}_r{r['rep']}_t{turn['turn']}"
        for suffix, expected in ((".json", turn["raw_sha256"]),
                                 (".exec.json", turn["exec"]["exec_raw_sha256"])):
            relative = stem + suffix
            path = Path(os.environ["SEMDEBT_DATA_DIR"]) / relative
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual == expected, relative
            evidence.append({"qid": r["qid"], "rep": r["rep"], "source": r["source"],
                             "raw_path": "$SEMDEBT_DATA_DIR/" + relative, "sha256": actual})
    return evidence


def main():
    qs, commit = bank()
    judge = {q for q, m in qs.items() if m["judge"]}
    low = {q for q, m in qs.items() if m["low"]}
    main_ids = set(qs) - judge - low
    all_ids = set(qs) - judge
    assert (len(main_ids), len(all_ids), len(METRIC19)) == (98, 109, 19)
    datasets, billed, st = {}, {}, {}
    provenance, attempts = [], []
    base = [f"复现：`{COMMAND}`。题库标签 eval-v1.2 = `{commit}`；仅通过 git show 读取冻结对象，不使用题库当前工作树。", ""]
    stability_rows, cost_rows = [], []
    for name, cell, runs, note in SPECS:
        rs, physical, replaced = load(cell, runs)
        datasets[name], billed[name] = rs, physical
        present = {r["qid"] for r in rs if r["qid"] not in judge}
        assert (len(present) == 55 and present <= all_ids) if name == "SQL-L1-T4" else present == all_ids, name
        assert all(r["eval_commit"].startswith(commit[:7]) for r in rs)
        for r in rs:
            assert r["final"]["outcome"] in {"correct", "wrong", "exec_error", "refused", "pending"}
            assert r["final"].get("pending") != "score_timeout"
            if r["qid"] not in judge:
                assert r["final"]["outcome"] in {"correct", "wrong", "exec_error", "refused"}
            u = r["usage"]
            assert u["prompt_tokens"] == u["cache_hit_tokens"] + u["cache_miss_tokens"]
            assert u["reasoning_tokens"] <= u["completion_tokens"]
            attempts.append({"unit": name, "qid": r["qid"], "rep": r["rep"], "outcome": r["final"]["outcome"],
                             "source": r["source"], "first": r["first"], "low": r["qid"] in low,
                             "judge": r["qid"] in judge})
        provenance.append([name, note, " + ".join(f"runs/{r}/{cell}.jsonl" for r in runs),
                           len(rs), ", ".join(replaced) or "无"])
        for label, ids in (("主表98", main_ids), ("附表109", all_ids)):
            selected = [r for r in rs if r["qid"] in ids]
            ss = stability(selected)
            if name == "SQL-L1":
                st[label] = ss
            n, counts = len(ss), Counter(ss.values())
            stability_rows.append([name, label if n == len(ids) else label + "的实际留出子集", n,
                                   *[pct(counts[k], n) for k in ("全对", "全错", "时对时错")], note])
        for label, ids in (("主表98", main_ids), ("附表109", all_ids), ("运行全体含judge", set(qs))):
            selected = [r for r in rs if r["qid"] in ids]
            n = len(selected)
            means = [f"{sum(r['usage'][k] for r in selected)/n:,.1f}" for k in
                     ("prompt_tokens", "cache_hit_tokens", "cache_miss_tokens", "completion_tokens", "reasoning_tokens")]
            cost_rows.append([name, label, n, *means, f"{sum(cost(r) for r in selected)/n:.5f}",
                              f"{sum(cost(r, True) for r in selected)/n:.5f}", f"{sum(cost(r) for r in selected):.5f}"])
    write("stability.md", ["# 三次作答稳定性", "", *base,
          "稳定性指标 = 时对时错题数 / 三次作答齐全的题数，越低越稳定；稳定不代表正确。全错包括错答、执行失败、拒答。",
          "同题三次只衡量本次模型采样的波动，不能外推为模型长期稳定性。旧版单列；T4 不扩充为完整题集。", "",
          *table(["单元", "范围", "实际题数", "三次全对", "三次全错", "时对时错", "版本"], stability_rows), "",
          *table(["待补单元", "状态"], [[n, "运行完成且最终判定核定后补入本表及费用表"] for n in
                                      ("SQL-L1调优", "SQL-L1调优+指令", "SQL-L1plus", "SQL-L3a")])])
    write("tokens-cost.md", ["# Token 与费用", "", *base,
          "费用按原调用 usage 与 peak 标志、harness/cells.py 的历史运行价格重算；rescore 的 cost_cny=0 是重评费用，不是原作答费用。",
          "Flash 错峰每百万 token：缓存命中 0.02 元、未命中 1 元、输出 4 元；高峰乘 2。这里复核历史实验费用，不把当前官网价格套回旧运行。",
          "输出 token 已包含思考 token，不能再加一次。每题费用指一次作答（含修正与全部探查模型调用）；每题做三次的费用约为其三倍。",
          "全冷缓存估计仅把同一输入 token 全部按未命中计价，保持输出与调用数不变；不是重新调用模型的预测。",
          "缓存命中依赖服务端已缓存相同消息前缀；不是每条请求都保证命中，须以 usage 实报为准。相同前缀失效或未预热时，低命中价不成立。", "",
          *table(["单元", "范围", "作答数", "平均输入", "平均命中", "平均未命中", "平均输出含思考", "其中思考", "元/作答", "全冷元/作答", "合计元"], cost_rows), "",
          "L2-E 上表只含有效作答。两条被替代作答的已记账费用仍应计入实花，见下表；未写日志的在途调用无法由这些行重建，INDEX 的预算总额另作财务口径。", "",
          *table(["单元", "有效作答费用", "全部物理日志费用", "替代条数"], [["SQL-L2-E",
                f"{sum(map(cost, datasets['SQL-L2-E'])):.5f}", f"{sum(map(cost, billed['SQL-L2-E'])):.5f}",
                len(billed['SQL-L2-E'])-len(datasets['SQL-L2-E'])]])])
    comparisons = []
    for label, ids in (("主表98", main_ids), ("附表109", all_ids)):
        for exclude in (False, True):
            kept = ids - METRIC19 if exclude else ids
            for a, b in (("SQL-L2", "SQL-L1"), ("JSON-L2", "SQL-L1"), ("SQL-L2-E", "SQL-L1"),
                         ("JSON-L2", "SQL-L2"), ("SQL-L2-E", "SQL-L2")):
                aa, bb = [[r for r in datasets[n] if r["qid"] in kept] for n in (a, b)]
                diff, interval = bootstrap(aa, bb)
                comparisons.append([label, "不含19题" if exclude else "含19题", len(kept), f"{a} − {b}",
                                    pct(sum(map(good, aa)), len(aa)), pct(sum(map(good, bb)), len(bb)), diff, interval])
    write("l1-l2.md", ["# L1 / L2：含与不含19题", "", *base,
          "固定排除集合来自 reports/validation/metric-text-vs-impl.md 的主表19题：" + "、".join(sorted(METRIC19)) + "。",
          "原初筛22题中的 Q45 是 judge，Q79/Q85 是低区分度；按任务卡的同一19题集合做两张表，109题附表仍保留 Q79/Q85，不把排除集合悄悄扩大成21题。",
          "每题先计算三次正确率；同题配对差，再按题有放回自助抽样10000次（种子20261020），95%百分位区间。",
          "区间只反映题目抽样波动，三次 rep 不是相同随机种子的反事实对照；这些题是指标相关性初筛，不等于已证实由歧义导致失分。", "",
          *table(["范围", "筛选", "题数", "比较", "前者正确", "后者正确", "差/百分点", "95%区间/百分点"], comparisons)])
    flows, tools, tool_rows = [], [], []
    for e, d in (("SQL-L0-E", "SQL-L0"), ("SQL-L1-E", "SQL-L1"), ("SQL-L2-E", "SQL-L2")):
        em, dm = [{(r["qid"], r["rep"]): r for r in datasets[n]} for n in (e, d)]
        for label, ids in (("主表98", main_ids), ("附表109", all_ids)):
            counts = Counter((dm[k]["final"]["outcome"], em[k]["final"]["outcome"]) for k in em if k[0] in ids)
            for a in ("correct", "wrong", "exec_error", "refused"):
                for b in ("correct", "wrong", "exec_error", "refused"):
                    flows.append([e + " vs " + d, label, a, b, counts[a, b]])
        for r in datasets[e]:
            for step in r["steps"]:
                for call in step["tool_calls"]:
                    if call["name"] != "run_sql":
                        continue
                    tool_rows.append({"unit": e, "qid": r["qid"], "rep": r["rep"], "source": r["source"],
                                      "call": step["call"], "k": call["k"], "purpose": purpose(call.get("query")),
                                      "query_sha256": hashlib.sha256((call.get("query") or "").encode()).hexdigest(),
                                      "status": call["status"], "exec_status": call.get("exec", {}).get("status")})
        for label, ids in (("主表98", main_ids), ("附表109", all_ids), ("运行全体含judge", set(qs))):
            subset = [r for r in tool_rows if r["unit"] == e and r["qid"] in ids]
            for key, n in sorted(Counter(r["purpose"] for r in subset).items()):
                tools.append([e, label, key, pct(n, len(subset))])
    write("explorer.md", ["# 探查带来的结果流向与调用用途", "", *base,
          "流向按 (题号, rep) 配对，四类互斥；下表列出全部16种流向（含0）。wrong→correct、correct→wrong、exec_error→correct、exec_error→wrong 可直接读取。",
          "报错指直答最终执行失败，不是首轮报错；拒答另列。该配对是描述性比较，不能证明具体一次探查修复了对应直答。", "",
          *table(["对照", "范围", "直答结果", "探查结果", "作答数"], flows), "",
          "## 调用用途", "",
          "采用可复算的SQL形态代理分类，不读取思考、不臆测意图。互斥优先级：结构/计划 → 含数值聚合或排名的候选答案核验 → DISTINCT/GROUP BY枚举 → COUNT行数 → 其余明细样例。",
          "例如带 GROUP BY 的 SUM 归聚合核验，枚举值附带 COUNT 归枚举。被拒、超限和执行报错的调用也计入分母，不能把尝试数称为成功查值数。",
          "逐调用分类在 tool-audit.csv，可凭 source、call、k 回查原SQL；这是操作形态分类，不能区分同一SUM究竟用于试答还是验证。", "",
          *table(["单元", "范围", "形态代理用途", "调用数及占比"], tools)])
    conf = [json.loads(s) for s in track(ROOT / "runs/20261023-T19c-confidence-01/confidence.jsonl").splitlines()]
    attrs = list(csv.DictReader(track(ROOT / "reports/attribution/codex.csv").splitlines()))
    attr = {(r["question_id"], int(r["round"])): r for r in attrs}
    lm = {(r["qid"], r["rep"]): r for r in datasets["SQL-L1"] if r["qid"] in all_ids}
    assert len(conf) == len(lm) == 327
    assert len({(r["qid"], r["rep"]) for r in conf}) == 327
    cross, wrong_a, joint = [], [], []
    for label, ids in (("主表98", main_ids), ("附表109", all_ids)):
        selected = [r for r in conf if r["qid"] in ids and r.get("tier") == "A"]
        for axis in ("题型", "稳定性", "根因类别"):
            groups = defaultdict(list)
            for r in selected:
                key = (r["qid"], r["rep"])
                source = lm[key]
                assert r["source"]["outcome"] == source["final"]["outcome"]
                a = attr.get(key)
                group = (qs[r["qid"]]["type"] if axis == "题型" else st[label][r["qid"]] if axis == "稳定性"
                         else "正确作答（无错因标注）" if good(source) else a["root_cause"])
                groups[group].append(source)
            for group, rows in sorted(groups.items()):
                cross.append([label, axis, group, len(rows), sum(map(good, rows)),
                              len(rows)-sum(map(good, rows)), pct(sum(map(good, rows)), len(rows))])
        joint_counts = Counter((qs[r["qid"]]["type"], st[label][r["qid"]],
                                attr[(r["qid"], r["rep"])]["root_cause"])
                               for r in selected if not good(lm[(r["qid"], r["rep"])]))
        joint.extend([label, *key, n] for key, n in sorted(joint_counts.items()))
    for r in conf:
        key = (r["qid"], r["rep"])
        if r.get("tier") == "A" and not good(lm[key]):
            a = attr[key]
            wrong_a.append([r["qid"], r["rep"], "低区分度" if r["qid"] in low else "主表",
                            qs[r["qid"]]["type"], st["附表109"][r["qid"]], a["category"], a["root_cause"],
                            lm[key]["source"], a["note"]])
    write("confidence.md", ["# 自评肯定对的错误分布", "", *base,
          "自评A=肯定对；本表仅对A档交叉，不改变 T19c 冻结判定。题型取冻结题库 complexity_source.primary，稳定性取三次最终判定。",
          "根因采用 reports/attribution/codex.csv 的既有独立复核意见，不把它当作无争议真值：1文档没写；2文档歧义；3模型没理解/没用上；4题面歧义；5参考或评分可疑。",
          "根因只有错答才有标注；正确作答单列，不能用错误根因分组的分母算总体校准率。T19b 两家根因分歧较大，需随表披露。", "",
          *table(["范围", "交叉轴", "分组", "A档数", "正确", "错误", "A档正确率"], cross), "",
          "## 题型 × 稳定性 × 根因（仅A档错答）", "",
          *table(["范围", "题型", "稳定性", "根因", "错误作答数"], joint), "",
          "主表A档59次中错10次：7次来自三次全错题，3次来自不稳定题。Codex既有复核将其中6次归为参考/评分可疑、2次题面歧义、2次模型未理解；不宜把这10次都归咎于模型自信失准。", "",
          "## A档错答逐条", "",
          *table(["题号", "次", "范围", "题型", "稳定性", "错因类别", "根因", "日志位置", "既有复核说明"], wrong_a)])
    review = json.loads(track(OUT / "review.json"))
    mixed = {q for q, s in st["附表109"].items() if s == "时对时错"}
    assert mixed == set(review) and len(mixed) == 20
    raw_checks = verify_raw([r for r in datasets["SQL-L1"] if r["qid"] in mixed])
    assert len(raw_checks) == 120
    write_csv("raw-check.csv", raw_checks)
    detail, class_counts = [], Counter()
    for q in sorted(mixed, key=lambda q: int(q[1:])):
        rows = sorted((r for r in datasets["SQL-L1"] if r["qid"] == q), key=lambda r: r["rep"])
        item = review[q]
        class_counts[item["category"]] += 1
        detail.append([q, "低区分度" if q in low else "主表", item["category"],
                       "；".join(f"r{r['rep']}:{r['first']}→{r['final']['outcome']}({r['final'].get('reason') or '—'})" for r in rows),
                       item["difference"], "；".join(r["source"] for r in rows)])
    write("unstable-l1.md", ["# SQL-L1 20道不稳定题逐题比较", "", *base,
          "范围为109题（含低区分度Q79）；主表98题中有19道。按三次最终判定取0<正确次数<3。",
          "人工比较三次最终SQL、执行状态和已有T19b复核意见；主类每题唯一，多处变化在说明中保留。这里解释判定变化，不自行改判或修改冻结内容。",
          "已校验60次最终作答的原始响应与执行文件共120份SHA256，均与日志一致；文件路径、哈希和日志行见raw-check.csv。未把原始响应或数据行复制入库。",
          "呈现类只说明表面写法及既有复核指出的可疑点，不宣称重新执行后已证明等价；旧评分器的呈现问题由T23处理。", "",
          *table(["主类", "题数及占比"], [[k, pct(v, 20)] for k, v in sorted(class_counts.items())]), "",
          *table(["题号", "范围", "主类", "三次首轮→最终", "三次差异与限制", "日志行"], detail)])
    write_csv("attempts.csv", attempts)
    write_csv("tool-audit.csv", tool_rows)
    for path in (Path(__file__), OUT / "quality.py", ROOT / "harness/cells.py", ROOT / "runs/INDEX.md"):
        track(path)
    if (OUT / "quality-evidence.json").exists():
        track(OUT / "quality-evidence.json")
    manifest = {"eval_commit": commit, "bootstrap": {"seed": 20261020, "samples": 10000},
                "sources": SOURCES, "units": provenance}
    (OUT / "sources.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    write("numbers.md", ["# 数字来源表", "", *base,
          "来源快照与SHA256见 sources.json；每次作答的确切来源文件/行、最终结果见 attempts.csv；逐探查调用见 tool-audit.csv。",
          "报告所有表格由同一命令生成；按以下行号可定位每个数字，表内范围及单元是数字的唯一键。", "",
          *table(["单元", "取用/替代关系", "来源文件（行号见attempts.csv）", "有效作答", "被覆盖来源行"], provenance), "",
          "L1.5S v1.4、C13及L2-E无rescore目录：INDEX记载其当场评分即harness-v1.1/v2最终判定；其余正式单元用最终rescore。没有把旧harness-v1的暂定分混入。", "",
          "## 输出数字逐行定位", "",
          *table(["报告文件", "含数字的表行", "复算命令"], [[f"reports/midterm/{p.name}", n,
                 "uv run python reports/midterm/quality.py" if p.name == "dataset-quality.md" else COMMAND]
                 for p in sorted(OUT.glob("*.md")) if p.name != "numbers.md"
                 for n, line in enumerate(p.read_text().splitlines(), 1) if line.startswith("|") and re.search(r"\d", line)]), "",
          "数据质量数字由 quality.py 生成；其来源为本地Parquet与DDL，见 dataset-quality.md，查询与受影响行数逐项列出。",
          "跨厂商验收尚待协调会话独立重算稳定性、L1/L2配对和费用，并抽查逐题及探查分类；本脚本的完整性断言不替代独立验收。"])
    print(f"T24: {len(SPECS)} unit versions; {len(attempts)} sourced attempts; {len(tool_rows)} tool calls; 20 mixed L1 questions. Assertions passed.")


if __name__ == "__main__":
    main()
