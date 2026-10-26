"""Free T29 D: three final row multisets, no new query execution or API calls."""
import hashlib
from itertools import combinations
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.questions import load_questions, verify_eval_tag
from harness.selective_v2 import result_equivalent

SOURCE = "20261025-T22b-l1plus-l3a-03"
SCORES = ROOT / "runs/20261025-T22b-l1plus-l3a-03-rescore-01/SQL-L1plus.jsonl"


def consistent(payloads):
    if any(p is None or p.get("error") is not None for p in payloads):
        return "execution_error_or_refusal"
    verdicts = [result_equivalent(a, b) for a, b in combinations(payloads, 2)]
    if False in verdicts:
        return "inconsistent"
    return "mapping_cap" if None in verdicts else "consistent"


def main():
    verify_eval_tag("eval-v1.2")
    questions = {q.qid: q for q in load_questions(lang="zh") if q.scoring == "deterministic"}
    records = [json.loads(s) for s in SCORES.read_text().splitlines()]
    assert len(records) == 327 and len({(r['qid'], r['rep']) for r in records}) == 327
    raw = Path(os.environ["SEMDEBT_DATA_DIR"]) / "runs-raw" / SOURCE / "SQL-L1plus"
    by_id = {}
    hashes = {}
    for r in records:
        assert r["status"] == "done" and r["rep"] in (1, 2, 3)
        turn = r["turns"][-1]
        payload = None
        if turn["exec"]["status"] == "ok":
            name = f"{r['qid']}_r{r['rep']}_t{turn['turn']}.exec.json"
            b = (raw / name).read_bytes()
            hashes[name] = hashlib.sha256(b).hexdigest()
            assert hashes[name] == turn["exec"]["exec_raw_sha256"]
            payload = json.loads(b)
        by_id.setdefault(r["qid"], {})[r["rep"]] = (payload, r["final"]["outcome"] == "correct")
    assert set(by_id) == set(questions)
    rows = []
    for qid in sorted(by_id):
        reps = by_id[qid]
        category = consistent([reps[i][0] for i in (1, 2, 3)])
        rows.append(dict(qid=qid, category=category, answered=category == "consistent",
                         correct_if_answered=reps[1][1], baseline_accuracy=sum(reps[i][1] for i in (1, 2, 3))/3))
    old = set(json.loads((ROOT / "reports/validation/t29-pilot-preflight.json").read_text())["pilot_qids"])
    scopes = dict(tuning20=old,
                  main98={q for q, v in questions.items() if not v.meta.get("low_discrimination")},
                  heldout49={q for q, v in questions.items() if not v.meta.get("low_discrimination") and v.meta.get("split") == "heldout"},
                  all109=set(questions))
    result = dict(source_run=SOURCE, source_scores_sha256=hashlib.sha256(SCORES.read_bytes()).hexdigest(),
                  execution_hashes=hashes, rows=rows, scopes={})
    for name, ids in scopes.items():
        selected = [r for r in rows if r["qid"] in ids]
        kept = [r for r in selected if r["answered"]]
        result["scopes"][name] = dict(questions=len(selected), answered=len(kept), coverage=len(kept)/len(selected),
                                    correct=sum(r["correct_if_answered"] for r in kept),
                                    accuracy_answered=sum(r["correct_if_answered"] for r in kept)/len(kept) if kept else None,
                                    baseline_accuracy=sum(r["baseline_accuracy"] for r in selected)/len(selected),
                                    categories={c: sum(r["category"] == c for r in selected) for c in sorted({r["category"] for r in selected})})
    out = ROOT / "reports/validation/t29-consistency-audit.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    lines = ["# T29 D：三次结果一致才作答（免费）", "", "读取既有SQL-L1plus三次最终执行结果，使用冻结v2通用数值容差与列映射，无序但保留重复行；三次两两等价才作答，按第1次主评分计算。任次最终执行错误或拒答不作答。没有新执行SQL或API调用。", "", "|范围|题数|作答|作答比例|作答部分正确|作答部分准确率|原三次逐题平均准确率|", "|---|---:|---:|---:|---:|---:|---:|"]
    for name, m in result["scopes"].items():
        lines.append(f"|{name}|{m['questions']}|{m['answered']}|{m['coverage']:.1%}|{m['correct']}|{m['accuracy_answered']:.1%}|{m['baseline_accuracy']:.1%}|")
    lines += ["", "该机械规则仅作离线对照；不能把在已观察样本上的准确率当成正式运行的效果结论。逐题类别与源执行哈希见`t29-consistency-audit.json`，不含题面、SQL、假设或结果值。", ""]
    (out.parent / "t29-consistency.md").write_text("\n".join(lines))
    print(json.dumps(result["scopes"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
