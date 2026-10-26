"""T29 B2: audit private manual mappings against frozen B1 and original v2 results."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.questions import load_questions, verify_eval_tag
from harness.scorer_v2 import score_detailed
from harness.value_units import infer_value_kind, is_integer_type

SOURCE = ROOT / "runs/20261025-T22b-l1plus-l3a-03-rescore-01/SQL-L1plus.jsonl"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verdict(primary, category, contradiction, excluded_reference, result_matches):
    if primary:
        if contradiction:
            return False, "revoked_declared_contradiction"
        if excluded_reference:
            return False, "excluded_reference_l1plus"
        return True, "retained_primary"
    if category in ("mapped", "no_assumption_single") and result_matches:
        return True, "newly_recognized"
    return False, "not_recognized"


def main():
    verify_eval_tag("eval-v1.2")
    data = Path(os.environ["SEMDEBT_DATA_DIR"])
    private = data / "t29-b2-review"
    bank = data / "t29-b1-eval"
    provenance = json.loads((private / "sources.json").read_text())
    labels = json.loads((private / "manual-labels.json").read_text())
    b1_bytes = (bank / "audit/T29-b1.json").read_bytes()
    assert digest(b1_bytes) == provenance["b1_sha256"]
    assert digest(SOURCE.read_bytes()) == provenance["scores_sha256"]
    assert digest((private / "manual-labels.json").read_bytes()) == provenance["manual_labels_sha256"]
    b1 = {q["qid"]: q for q in json.loads(b1_bytes)["records"]}
    questions = {q.qid: q for q in load_questions(lang="zh") if q.scoring == "deterministic"}
    records = {(r["qid"], r["rep"]): r for r in (json.loads(s) for s in SOURCE.read_text().splitlines())}
    assert len(labels) == len(records) == 327 and {(x["qid"], x["rep"]) for x in labels} == set(records)
    raw = data / "runs-raw/20261025-T22b-l1plus-l3a-03/SQL-L1plus"
    rows, details = [], []
    for label in labels:
        qid, rep = label["qid"], label["rep"]
        r, q = records[qid, rep], questions[qid]
        t = r["turns"][-1]
        assert digest((t["assumption"] or "").encode()) == label["source_assumption_sha256"]
        assert digest((t["query"] or "").encode()) == label["source_sql_sha256"]
        rb = (raw / f"{qid}_r{rep}_t{t['turn']}.json").read_bytes()
        assert digest(rb) == label["source_final_raw_sha256"] == t["raw_sha256"]
        assert json.loads(rb)["choices"][0]["message"]["content"]
        candidate = None
        if t["exec"]["status"] == "ok":
            eb = (raw / f"{qid}_r{rep}_t{t['turn']}.exec.json").read_bytes()
            assert digest(eb) == t["exec"]["exec_raw_sha256"]
            candidate = json.loads(eb)["rows"]
        target = next((i for i in b1[qid]["interpretations"] if i["id"] == label["interpretation_id"]), None)
        match = False
        score = None
        if target and target["b2_eligible"] and candidate is not None:
            result = bank / target["result"]["path"]
            assert digest(result.read_bytes()) == target["result"]["sha256"]
            if target["existing_reference"]:
                idx = int(target["id"].rsplit("-", 1)[1])-1
                rule = q.ref_rules[idx] if q.ref_rules and q.ref_rules[idx] is not None else q.rules
                refs = q.refs[idx]
            else:
                payload = json.loads(result.read_text())
                columns, refs = payload["columns"], payload["rows"]
                # Preserve the original question's required business fields:
                # Q65: manager identity/name; Q82: name, count and tenure (title optional).
                required = {"Q65-b1-1": [0, 1], "Q82-b1-1": [0, 2, 3]}.get(target["id"], list(range(len(columns))))
                rule = dict(ordered=False, top_n=None, tie_columns=[], required_columns=required,
                            value_types=[c["type"] for c in columns],
                            value_kinds=["count" if is_integer_type(c["type"]) else infer_value_kind(c["name"], c["type"]) for c in columns])
                if qid == "Q65":
                    rule["identifier_columns"] = [0]
            score = score_detailed(candidate, [refs], rule)
            match = score.outcome == "correct"
        primary = r["final"]["outcome"] == "correct"
        matched = r["final"].get("matched_ref")
        old_ref = next((i for i in b1[qid]["interpretations"] if i["id"] == f"{qid}-existing-{matched+1}"), None) if matched is not None else None
        excluded = bool(old_ref and not old_ref["b2_eligible"] and label["category"] == "excluded_l1plus")
        correct, category = verdict(primary, label["category"], label["declared_contradiction"], excluded, match)
        extra = not primary and label["category"] == "underspecified_multiple" and match
        rows.append(dict(qid=qid, rep=rep, cell="SQL-L1plus", declaration_category=label["category"],
                         category=category, primary_correct=primary, b2_correct=correct,
                         upper_bound_extra=extra))
        details.append(dict(label=label, result_matches=match, score=score.__dict__ if score is not None else None))
    (private / "result-checks.json").write_text(json.dumps(details, ensure_ascii=False, indent=2, default=str)+"\n")
    summary = dict(attempts=len(rows), primary_correct=sum(r["primary_correct"] for r in rows),
                   b2_correct=sum(r["b2_correct"] for r in rows),
                   categories={c: sum(r["category"] == c for r in rows) for c in sorted({r["category"] for r in rows})},
                   no_assumption_single=sum(r["declaration_category"] == "no_assumption_single" for r in rows),
                   no_assumption_multiple=sum(r["declaration_category"] == "no_assumption_multiple" for r in rows),
                   underspecified_multiple=sum(r["declaration_category"] == "underspecified_multiple" for r in rows),
                   upper_bound_extra=sum(r["upper_bound_extra"] for r in rows))
    result = dict(source=provenance, summary=summary, rows=rows)
    out = ROOT / "reports/validation"
    (out / "t29-assumptions-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
