"""Pre-registered U2 content-accuracy statistics; never infer labels from v2."""
from collections import defaultdict
import math
import random


def _auc(rows):
    buckets = defaultdict(lambda: [0, 0])
    for r in rows:
        if not r["refused"] and r["confidence"] is not None:
            buckets[r["confidence"]][0 if r["correct"] else 1] += 1
    positive = sum(v[0] for v in buckets.values())
    negative = sum(v[1] for v in buckets.values())
    if not positive or not negative:
        return None
    wins, preceding_negative = 0, 0
    for score in sorted(buckets):
        p, n = buckets[score]
        wins += p * (preceding_negative + .5*n)
        preceding_negative += n
    return wins / (positive*negative)


def _difference(rows, baseline_error):
    rejected = [baseline_error[r["qid"]] for r in rows if r["refused"]]
    answered = [baseline_error[r["qid"]] for r in rows if not r["refused"]]
    if not rejected or not answered:
        return None
    return sum(rejected)/len(rejected) - sum(answered)/len(answered)


def _interval(values):
    if not values:
        return None
    values = sorted(values)
    return [values[int(.025*len(values))], values[max(0, int(.975*len(values))-1)]]


def analyze_cell(attempts, baseline, *, d1_complete=False, draws=10_000,
                 seed=20261019, expected_questions=98):
    """One cell, exactly three attempts per question; baseline holds three D1 bools.

    The caller must supply final D1 content labels for the baseline and the
    same adjudication for treatment answers. No sampled/extrapolated labels.
    Native refusal alone defines rejection; confidence errors do not.
    """
    if not d1_complete:
        raise ValueError("analysis waits for completed D1 full content adjudication")
    if draws <= 0 or len(baseline) != expected_questions:
        raise ValueError("invalid bootstrap or question scope")
    if any(len(v) != 3 or any(type(x) is not bool for x in v) for v in baseline.values()):
        raise ValueError("baseline requires three final content verdicts per question")
    grouped = defaultdict(list)
    seen = set()
    for r in attempts:
        key = r["qid"], r["rep"]
        if key in seen or r["qid"] not in baseline or r["rep"] not in (1, 2, 3):
            raise ValueError("duplicate, unknown or invalid treatment identity")
        if type(r["refused"]) is not bool or (not r["refused"] and type(r["correct"]) is not bool):
            raise ValueError("treatment requires final content verdicts for every attempted answer")
        score = r["confidence"]
        if score is not None and (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 100):
            raise ValueError("invalid confidence must be recorded as missing, never imputed")
        seen.add(key)
        grouped[r["qid"]].append(r)
    if set(grouped) != set(baseline) or any(len(v) != 3 for v in grouped.values()):
        raise ValueError("treatment scope incomplete")
    rows = list(attempts)
    baseline_error = {q: 1-sum(v)/3 for q, v in baseline.items()}
    answered = [r for r in rows if not r["refused"]]
    refused = len(rows)-len(answered)
    refusal_rate = refused/len(rows)
    compare_refusal = refusal_rate >= .05
    delta = _difference(rows, baseline_error) if compare_refusal else None
    auc = _auc(rows)
    gate90 = [r for r in answered if r["confidence"] is not None and r["confidence"] >= 90]
    rng = random.Random(seed)
    qids = sorted(grouped)
    differences, aucs = [], []
    for _ in range(draws):
        # Resample question clusters, preserving all three repeats and their
        # shared baseline error rate, including missing-confidence patterns.
        sample = [r for q in rng.choices(qids, k=len(qids)) for r in grouped[q]]
        if delta is not None:
            d = _difference(sample, baseline_error)
            if d is not None:
                differences.append(d)
        if auc is not None:
            a = _auc(sample)
            if a is not None:
                aucs.append(a)
    delta_ci, auc_ci = _interval(differences), _interval(aucs)
    return dict(questions=len(qids), attempts=len(rows), refused=refused, refusal_rate=refusal_rate,
                baseline_error_refused=(sum(baseline_error[r["qid"]] for r in rows if r["refused"])/refused)
                if delta is not None else None,
                baseline_error_answered=(sum(baseline_error[r["qid"]] for r in answered)/len(answered))
                if delta is not None else None,
                refusal_error_difference=delta, refusal_error_difference_ci=delta_ci,
                refusal_success=bool(delta_ci and delta_ci[0] > 0),
                refusal_conclusion="该单元未见取舍" if not compare_refusal else "无法比较" if delta is None
                else "拒答偏向基线易错题" if delta_ci and delta_ci[0] > 0 else "未达到拒答判据",
                answered=len(answered), accuracy_answered=sum(r["correct"] for r in answered)/len(answered) if answered else None,
                confidence_missing=sum(r["confidence"] is None and r.get("confidence_status", "missing") == "missing" for r in answered),
                confidence_invalid=sum(r["confidence"] is None and r.get("confidence_status", "missing") != "missing" for r in answered),
                confidence_valid=sum(r["confidence"] is not None for r in answered),
                auc=auc, auc_ci=auc_ci, confidence_success=bool(auc_ci and auc_ci[0] > .5),
                gate90=dict(answered=len(gate90), coverage=len(gate90)/len(rows),
                            accuracy_answered=sum(r["correct"] for r in gate90)/len(gate90) if gate90 else None),
                bootstrap=dict(unit="question", draws=draws, seed=seed,
                               difference_valid=len(differences), auc_valid=len(aucs)))
