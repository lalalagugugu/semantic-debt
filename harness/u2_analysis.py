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


def _difference(rows, baseline_error_counts):
    rejected = [baseline_error_counts[r["qid"]] for r in rows if r["refused"]]
    answered = [baseline_error_counts[r["qid"]] for r in rows if not r["refused"]]
    if not rejected or not answered:
        return None
    # Three baseline repeats: compare integer error totals before dividing so
    # a true zero cannot turn into a positive CI bound through roundoff.
    return (sum(rejected)*len(answered)-sum(answered)*len(rejected))/(3*len(rejected)*len(answered))


def _interval(values):
    if not values:
        return None
    values = sorted(values)
    return [values[int(.025*len(values))], values[max(0, int(.975*len(values))-1)]]


def compare_refusal_arms(unpenalized, penalty, *, d1_complete=False, draws=10_000,
                         seed=20261019, expected_questions=98):
    """Paired question-cluster CI for penalty minus unpenalized native refusal.

    The individual-arm <5% rule does not suppress this registered contrast.
    Both arms' three repeats stay together in each resampled question.
    """
    if not d1_complete:
        raise ValueError("analysis waits for completed D1 full content adjudication")
    if draws <= 0:
        raise ValueError("invalid bootstrap")
    arms = []
    for rows in (unpenalized, penalty):
        by_id = {}
        for r in rows:
            key = r["qid"], r["rep"]
            if key in by_id or r["rep"] not in (1, 2, 3) or type(r["refused"]) is not bool:
                raise ValueError("duplicate or invalid arm identity/refusal")
            by_id[key] = r["refused"]
        qids = {q for q, rep in by_id}
        if len(qids) != expected_questions or set(by_id) != {(q, rep) for q in qids for rep in (1, 2, 3)}:
            raise ValueError("arm scope incomplete")
        arms.append(by_id)
    if set(arms[0]) != set(arms[1]):
        raise ValueError("paired arms must have identical question/repeat identities")
    qids = sorted({q for q, rep in arms[0]})
    differences = {q: sum(int(arms[1][q, rep])-int(arms[0][q, rep]) for rep in (1, 2, 3)) for q in qids}
    rng = random.Random(seed)
    boot = [sum(differences[q] for q in rng.choices(qids, k=len(qids)))/(3*len(qids)) for _ in range(draws)]
    return dict(questions=len(qids), attempts_per_arm=3*len(qids),
                unpenalized_refusal_rate=sum(arms[0].values())/len(arms[0]),
                penalty_refusal_rate=sum(arms[1].values())/len(arms[1]),
                penalty_minus_unpenalized=sum(differences.values())/(3*len(qids)),
                ci95=_interval(boot), bootstrap=dict(unit="paired_question", draws=draws, seed=seed))


def analyze_cell(attempts, baseline, *, baseline_fingerprint=None, treatment_fingerprint=None,
                 baseline_run_id=None, treatment_run_id=None, d1_complete=False, draws=10_000,
                 seed=20261019, expected_questions=98):
    """One cell, exactly three attempts per question; same-run baseline holds three D1 bools.

    The caller must supply final D1 content labels for the baseline and the
    same adjudication for treatment answers. No sampled/extrapolated labels.
    Native refusal alone defines rejection; confidence errors do not.
    """
    if not d1_complete:
        raise ValueError("analysis waits for completed D1 full content adjudication")
    if (baseline_fingerprint != "bc19ba97cbe016479903222bb1578db6"
            or treatment_fingerprint != baseline_fingerprint or not baseline_run_id
            or baseline_run_id != treatment_run_id
            or baseline_run_id in ("20261030-T29-u2-01", "20261018-T13-sql-direct-01")):
        raise ValueError("U2 baseline and treatment must come from the same new run and approved fingerprint")
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
    baseline_error_counts = {q: 3-sum(v) for q, v in baseline.items()}
    answered = [r for r in rows if not r["refused"]]
    refused = len(rows)-len(answered)
    refusal_rate = refused/len(rows)
    compare_refusal = refusal_rate >= .05
    delta = _difference(rows, baseline_error_counts) if compare_refusal else None
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
            d = _difference(sample, baseline_error_counts)
            if d is not None:
                differences.append(d)
        if auc is not None:
            a = _auc(sample)
            if a is not None:
                aucs.append(a)
    delta_ci, auc_ci = _interval(differences), _interval(aucs)
    return dict(questions=len(qids), attempts=len(rows), refused=refused, refusal_rate=refusal_rate,
                baseline_error_refused=(sum(baseline_error_counts[r["qid"]] for r in rows if r["refused"])/(3*refused))
                if delta is not None else None,
                baseline_error_answered=(sum(baseline_error_counts[r["qid"]] for r in answered)/(3*len(answered)))
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


def compare_baseline_accuracy(old, new, *, d1_complete=False, draws=10_000,
                              seed=20261019, expected_questions=98):
    """Descriptive new-minus-old baseline accuracy drift, paired by question.

    Each value is the three final content verdicts; no success threshold.
    These historical labels never feed the U2 refusal criterion.
    """
    if not d1_complete:
        raise ValueError("analysis waits for completed D1 full content adjudication")
    if draws <= 0 or len(old) != expected_questions or set(old) != set(new):
        raise ValueError("paired baseline scope incomplete")
    if any(len(v) != 3 or any(type(x) is not bool for x in v) for data in (old, new) for v in data.values()):
        raise ValueError("baselines require three final content verdicts per question")
    qids = sorted(old)
    differences = {q: sum(new[q])-sum(old[q]) for q in qids}
    rng = random.Random(seed)
    boot = [sum(differences[q] for q in rng.choices(qids, k=len(qids)))/(3*len(qids)) for _ in range(draws)]
    return dict(questions=len(qids), attempts_per_baseline=3*len(qids),
                old_accuracy=sum(sum(v) for v in old.values())/(3*len(qids)),
                new_accuracy=sum(sum(v) for v in new.values())/(3*len(qids)),
                new_minus_old=sum(differences.values())/(3*len(qids)), ci95=_interval(boot),
                descriptive_only=True, bootstrap=dict(unit="paired_question", draws=draws, seed=seed))
