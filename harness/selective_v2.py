"""Frozen T29 expanded-pilot prompt variants and offline screening rules."""
from __future__ import annotations

import math
import random
import re

from harness import prompt as P

THRESHOLDS = {1: "50%", 3: "75%", 5: "83%", 10: "91%", 20: "95%", 100: "99%"}
CONFIDENCE_RULE = "作答格式仍按上述要求；作答时另起一行输出「把握：0–100」，用0到100之间的数表示你判断本次答对的概率。只输出一个把握值。只输出 CANNOT_ANSWER 时不需要把握行。"
U2_CONFIDENCE_RULE = CONFIDENCE_RULE + "有作答时，把握行必须放在整份回复的最后一行。"
OLD_FOUR = "4. 如果根据语义上下文无法回答这个问题，只输出 CANNOT_ANSWER，不要输出其他内容。"
NEW_FOUR = "4. 无法回答或没有把握时只输出 CANNOT_ANSWER"
GATES = (50, 75, 90)


def scoring_rule(k: int) -> str:
    if k not in THRESHOLDS:
        raise ValueError(f"unsupported selective weight: {k}")
    return (f"计分规则：每道题独立计分。答对得 1 分，答错扣 {k} 分，只输出 CANNOT_ANSWER 得 0 分。"
            f"请让本题的期望得分最高：只有当你判断自己答对的可能性高于 {THRESHOLDS[k]} 时才作答，"
            "否则只输出 CANNOT_ANSWER。题面有歧义时，可以在「假设：」里写明你采用的理解再作答。")


def system_variant(base: str, variant: str, k: int | None) -> str:
    if variant == "uncertainty":
        if k is not None or base.count(OLD_FOUR) != 1:
            raise ValueError("U2 requires the frozen fourth instruction and no scoring rule")
        return base.replace(OLD_FOUR, NEW_FOUR) + "\n" + U2_CONFIDENCE_RULE + "\n"
    if variant == "front":
        if base.count(OLD_FOUR) != 1:
            raise ValueError("the frozen fourth instruction changed")
        return scoring_rule(k) + "\n\n" + base.replace(OLD_FOUR, NEW_FOUR)
    if variant == "confidence":
        if k is not None:
            raise ValueError("confidence variant must not include a scoring rule")
        return base + "\n" + CONFIDENCE_RULE + "\n"
    raise ValueError(f"unknown selective variant: {variant}")


def u2_confidence_record(content: str, final: dict) -> dict:
    parsed = confidence_record(content, final)
    value = parsed["value"]
    if parsed["native_refusal"]:
        status, value = "native_refusal", None
    elif value is not None:
        status = "valid"
    else:
        lines = re.findall(r"^\s*把握\s*[:：](.*?)$", content, re.MULTILINE)
        status = "missing" if not lines or (len(lines) == 1 and not lines[0].strip()) else "duplicate" if len(lines) > 1 else "invalid_format"
        if len(lines) == 1:
            try:
                number = float(lines[0].strip())
            except ValueError:
                pass
            else:
                if not math.isfinite(number) or not 0 <= number <= 100:
                    status = "out_of_range"
    # Missing confidence does not turn an attempted answer into native refusal.
    return {"value": value, "status": status, "format_error": parsed["format_error"],
            "native_refusal": parsed["native_refusal"],
            "gate90": {"answered": not parsed["native_refusal"] and value is not None and value >= 90}}


def confidence_record(content: str, final: dict) -> dict:
    native_refusal = P.parse_response(content).refused
    lines = re.findall(r"^\s*把握\s*[:：](.*?)$", content, re.MULTILINE)
    value = None
    if len(lines) == 1 and re.fullmatch(r"\s*(?:\d+(?:\.\d+)?|\.\d+)\s*", lines[0]):
        value = float(lines[0])
        if not math.isfinite(value) or not 0 <= value <= 100:
            value = None
    invalid = value is None and not native_refusal
    gates = {}
    for threshold in GATES:
        deliver = not native_refusal and value is not None and value >= threshold
        gates[str(threshold)] = {"answered": deliver, "final": final if deliver else {"outcome": "refused"}}
    return {"value": value, "format_error": invalid, "native_refusal": native_refusal, "gates": gates}


def screening(rows: list[dict], baseline: dict[str, float]) -> dict:
    """Each row is one question; baseline is the original three-answer mean."""
    ids = [r["qid"] for r in rows]
    if not rows or len(ids) != len(set(ids)) or any(q not in baseline for q in ids):
        raise ValueError("screening requires unique questions with baseline means")
    answered = [r for r in rows if r["answered"]]
    rejected = [r for r in rows if not r["answered"]]
    accuracy = sum(r["correct"] for r in answered) / len(answered) if answered else None
    base = sum(baseline[q] for q in ids) / len(ids)
    kept_base = sum(baseline[r["qid"]] for r in answered) / len(answered) if answered else None
    rejected_base = sum(baseline[r["qid"]] for r in rejected) / len(rejected) if rejected else None
    coverage = len(answered) / len(rows)
    eligible = (coverage >= .5 and accuracy is not None and accuracy > base
                and rejected_base is not None and rejected_base < kept_base)
    return {"questions": len(rows), "answered": len(answered), "coverage": coverage,
            "accuracy_answered": accuracy, "baseline_accuracy": base,
            "baseline_answered": kept_base, "baseline_rejected": rejected_base,
            "score_k3": sum((1 if r["correct"] else -3) if r["answered"] else 0 for r in rows) / len(rows),
            "eligible": eligible}


def best_group(groups: dict[str, dict]) -> dict:
    eligible = [name for name, metrics in groups.items() if metrics["eligible"]]
    if not eligible:
        return {"best": [], "reason": "no_eligible_group"}
    maximum = max((groups[n]["score_k3"], groups[n]["coverage"]) for n in eligible)
    best = sorted(n for n in eligible if (groups[n]["score_k3"], groups[n]["coverage"]) == maximum)
    # The user specified no further tie-break. Preserve a true tie for review.
    return {"best": best, "reason": "tie_requires_user" if len(best) > 1 else "screening_only"}


def confidence_auc(rows: list[tuple[float, bool]], *, draws=10_000, seed=20261019) -> dict:
    from harness.confidence import auc

    def compute(sample):
        return auc([v for v, correct in sample if correct], [v for v, correct in sample if not correct])
    value = compute(rows)
    if value is None:
        return {"n": len(rows), "auc": None, "lo": None, "hi": None, "indistinguishable": None}
    rng = random.Random(seed)
    boot = []
    for _ in range(draws):
        a = compute([rng.choice(rows) for _ in rows])
        if a is not None:
            boot.append(a)
    if not boot:
        raise ValueError("no estimable AUC bootstrap sample")
    boot.sort()
    lo, hi = boot[int(.025 * len(boot))], boot[max(0, int(.975 * len(boot)) - 1)]
    return {"n": len(rows), "auc": value, "lo": lo, "hi": hi,
            "bootstrap_valid": len(boot), "bootstrap_draws": draws, "seed": seed,
            "indistinguishable": lo <= .5 <= hi}


def result_equivalent(a: dict, b: dict) -> bool | None:
    """Symmetric v2 column matching and numeric tolerance, strict row multiset.

    Each output serves as the other's reference. No golden answer, selection,
    ranking, optional zero-row, or required-column projection is used here.
    None means the frozen scorer's column-mapping resource cap was reached.
    """
    from collections import Counter
    from harness import scorer_v2 as S
    from harness.value_units import infer_value_kind, is_integer_type

    if a.get("error") is not None or b.get("error") is not None:
        return False
    ar, br = a["rows"], b["rows"]
    width = len(a["columns"])
    if len(ar) != len(br) or width != len(b["columns"]):
        return False
    if any(len(row) != width for row in ar + br):
        raise ValueError("result metadata width mismatch")
    if not ar:
        return True
    if Counter(tuple(S._norm(v) for v in row) for row in ar) == Counter(tuple(S._norm(v) for v in row) for row in br):
        return True

    def direction(candidate, reference):
        cols = reference["columns"]
        rule = {"ordered": False, "top_n": None, "tie_columns": [], "required_columns": list(range(width)),
                "value_types": [c["type"] for c in cols],
                "value_kinds": ["count" if is_integer_type(c["type"]) else infer_value_kind(c["name"], c["type"]) for c in cols]}
        cr, rr = candidate["rows"], reference["rows"]
        for count, parts in enumerate(S._mappings(cr, rr, rule, tuple(range(width)))):
            if count == S.CAP:
                return None
            cp, rp = S._project(cr, parts, True, rule), S._project(rr, parts, False, rule)
            if S._match(cp, rp, S._metadata(rule, parts, rr), []):
                return True
        return False
    forward, backward = direction(a, b), direction(b, a)
    if forward is False or backward is False:
        return False
    return None if forward is None or backward is None else True
