"""Independent cross-vendor check of the T31 v4 candidate flips (Claude Code side).

For every bundle directory in ``$SEMDEBT_DATA_DIR/t31-claude-review-20261027`` this
script re-derives, from the raw answer result and the reference results only,
whether the answer matches the reference *in content* once the representation
changes allowed by the rules it hit (R1-R11, see
``reports/validation/reference-and-presentation-review.md``) are applied.

It deliberately does not import or reuse anything from ``scripts/t31_*.py`` and
does not read Codex's intermediate outputs: the hit rules are treated as claims
to verify. Each rule only unlocks its own transformation; everything else uses
the v2 baseline (0.5% relative tolerance, percentage x100 / /100, extra answer
columns ignored, row order ignored unless the reference is ordered). Numeric
NULL never equals 0 (``decisions/2026-10-27-t31-null-strict.md``).

Cases the matcher cannot confirm, and question-level guards that need a human
look, are printed for manual adjudication; the manual verdicts live in
``reports/validation/t31-v4-claude-review-manual.csv`` and are merged into the
final CSV. The public CSV holds only row number, qid, cell, rep, rules, verdict
and a short note.

    uv run --offline python scripts/review_v4_flips_claude.py \
        --out reports/validation/t31-v4-claude-review.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import itertools
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

REL_TOL = 0.005
# v2 absolute floors per value kind (reference unit); "other" has none.
ABS_FLOOR = {"amount": 0.01, "ratio": 0.0001, "percentage": 0.01}
ABS_TOL = 1e-9
PLACEHOLDER_NAMES = {"not provided", "", "unknown", "n/a", "na", "none", "null"}
MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"])}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
DECREASE_HEADER = re.compile(r"减少|下降|降幅|缺口|decrease|decline|drop|reduction", re.I)
SORT_WORDS = re.compile(r"前\s*\d|前[一二三四五六七八九十]|排名|排序|名次|从高到低|从低到高|由高到低|由低到高|"
                        r"最高|最低|最多|最少|降序|升序|依次|top", re.I)
# Enum header aliases stated in the semantic layer itself (source.yaml, scenario column).
SCENARIO_ALIASES = {"Actual": ["实际"], "Budget": ["预算"], "Forecast": ["预测"]}
STATUS_SUFFIX = re.compile(r"(客户|customers?)$", re.I)


# ---------------------------------------------------------------- values
def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def num_eq(a, b, kind: str = "other") -> bool:
    if a is None or b is None:
        return a is None and b is None  # NULL never equals 0
    if not (is_num(a) and is_num(b)):
        return False
    if kind == "count":
        return abs(a - b) < 0.5
    return abs(a - b) <= max(REL_TOL * abs(b), ABS_FLOOR.get(kind, 0.0), ABS_TOL)


def norm_str(v) -> str | None:
    if v is None:
        return None
    if is_num(v) and float(v).is_integer():
        v = int(v)
    return re.sub(r"\s+", " ", str(v)).strip().casefold()


# ---------------------------------------------------------------- periods
def header_gran(name: str) -> str | None:
    n = name.casefold()
    if re.search(r"数|count|num|months\b|consecutive|连续", n):
        return None  # a count of months/quarters is a number, not a period
    if "quarter" in n or "季" in n:
        return "Q"
    if "month" in n or "月" in n:
        return "M"
    if "year" in n or "年" in n:
        return "Y"
    return None


def parse_period(v, hint: str | None):
    """Return (gran, year|None, idx|None) or None. Only lossless forms."""
    if v is None:
        return None
    if is_num(v):
        if not float(v).is_integer():
            return None
        v = int(v)
        if hint == "Y" and 1900 <= v <= 2100:
            return ("Y", v, None)
        if hint == "M" and 1 <= v <= 12:
            return ("M", None, v)
        if hint == "Q" and 1 <= v <= 4:
            return ("Q", None, v)
        return None
    s = str(v).strip()
    sl = s.casefold()
    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[ t]00:00:00)?", sl):
        y, mo, d = map(int, m.groups())
        if hint == "Y" and mo == 1 and d == 1:
            return ("Y", y, None)
        if hint == "Q" and d == 1 and mo in (1, 4, 7, 10):
            return ("Q", y, (mo - 1) // 3 + 1)
        if d == 1:
            return ("M", y, mo)
        return None
    if m := re.fullmatch(r"(\d{4})[-/](\d{1,2})", sl):
        return ("M", int(m[1]), int(m[2]))
    if m := re.fullmatch(r"(\d{4})\s*年\s*(\d{1,2})\s*月", sl):
        return ("M", int(m[1]), int(m[2]))
    if m := re.fullmatch(r"(\d{1,2})\s*月", sl):
        return ("M", None, int(m[1]))
    if sl in MONTHS:
        return ("M", None, MONTHS[sl])
    if m := re.fullmatch(r"([a-z]+)\s+(\d{4})", sl):
        if m[1] in MONTHS:
            return ("M", int(m[2]), MONTHS[m[1]])
    if m := re.fullmatch(r"(\d{4})\s*[- ]?\s*q([1-4])", sl):
        return ("Q", int(m[1]), int(m[2]))
    if m := re.fullmatch(r"q([1-4])", sl):
        return ("Q", None, int(m[1]))
    if m := re.fullmatch(r"(?:第)?([1-4])\s*季度?", sl):
        return ("Q", None, int(m[1]))
    if m := re.fullmatch(r"(\d{4})\s*年?\s*第?([1-4])\s*季度", sl):
        return ("Q", int(m[1]), int(m[2]))
    if m := re.fullmatch(r"(?:year\s*)?(\d{4})\s*年?", sl):
        return ("Y", int(m[1]), None)
    if hint and re.fullmatch(r"\d{1,2}", sl):
        return parse_period(int(sl), hint)
    return None


def period_column(name: str, values: list):
    hint = header_gran(name)
    toks = [parse_period(v, hint) for v in values]
    present = [t for t in toks if t is not None]
    if not present or any(v is not None and t is None for v, t in zip(values, toks)):
        return None
    if len({t[0] for t in present}) != 1:
        return None
    # A bare number column only counts as a period when the header says so.
    if all(is_num(v) for v in values if v is not None) and hint is None:
        return None
    return toks


def question_years(text: str) -> set[int]:
    return {int(y) for y in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text)}


# ---------------------------------------------------------------- table views
class Col:
    """One comparable column: values + comparator kind."""

    def __init__(self, label, values, kind, covers=(), note=""):
        self.label, self.values, self.kind, self.covers, self.note = label, values, kind, tuple(covers), note


NUMERIC_TEXT = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def coerce_numeric_text(acols, arows):
    """The JSON executor returns numbers as text; a column whose every value is numeric text is numeric."""
    rows = [list(r) for r in arows]
    for i, c in enumerate(acols):
        vals = [r[i] for r in rows]
        if any(isinstance(v, str) for v in vals) and all(
                v is None or (isinstance(v, str) and NUMERIC_TEXT.fullmatch(v)) for v in vals) \
                and c.get("type") in ("number", "Float64", "Nullable(Float64)"):
            for r in rows:
                if isinstance(r[i], str) and NUMERIC_TEXT.fullmatch(r[i]):
                    r[i] = float(r[i])
    return rows


def answer_views(acols, arows, hits):
    views = []
    n = len(acols)
    colvals = [[r[i] for r in arows] for i in range(n)]
    for i, c in enumerate(acols):
        vals = colvals[i]
        if all(v is None or is_num(v) for v in vals):
            views.append(Col(c["name"], vals, "num"))
            if "R6" in hits and DECREASE_HEADER.search(c["name"]):
                views.append(Col(c["name"] + "[neg]", [None if v is None else -v for v in vals], "num",
                                 note="R6 正数减少量取负"))
        views.append(Col(c["name"], vals, "str"))
        if "R4" in hits and any(isinstance(v, str) and STATUS_SUFFIX.search(v.strip()) for v in vals):
            views.append(Col(c["name"] + "[nosuffix]",
                             [STATUS_SUFFIX.sub("", v.strip()).strip() if isinstance(v, str) else v for v in vals],
                             "str", note="R4 去客户后缀"))
    if "R1" in hits:
        pcols = {}
        for i, c in enumerate(acols):
            toks = period_column(c["name"], colvals[i])
            if toks:
                pcols[i] = toks
        years = [i for i, t in pcols.items() if all(x is None or x[0] == "Y" for x in t)]
        for i, toks in pcols.items():
            views.append(Col(acols[i]["name"] + "[period]", toks, "period"))
            if toks and all(x is None or (x[0] != "Y" and x[1] is None) for x in toks):
                for y in years:
                    comb = [None if (t is None or yy is None) else (t[0], yy[1], t[2])
                            for t, yy in zip(toks, pcols[y])]
                    views.append(Col(f"{acols[y]['name']}+{acols[i]['name']}[period]", comb, "period"))
    return views


def ref_targets(rcols, rrows, rules, hits):
    """Columns of the reference that the answer must reproduce.

    Returns (targets, notes). Each target covers one or more reference column indices.
    """
    req = list(rules.get("required_columns") or range(len(rcols)))
    kinds = rules.get("value_kinds") or ["other"] * len(rcols)
    rank_cols = set(rules.get("rank_columns") or [])
    colvals = [[r[i] for r in rrows] for i in range(len(rcols))]
    targets, covered, notes = [], set(), []

    if "R1" in hits:
        pc = {i: t for i in range(len(rcols)) if (t := period_column(rcols[i]["name"], colvals[i]))}
        years = [i for i, t in pc.items() if all(x is None or x[0] == "Y" for x in t)]
        subs = [i for i in pc if i not in years]
        for s in subs:
            if s not in req and not any(y in req for y in years):
                continue
            if years:
                y = years[0]
                comb = [None if (t is None or yy is None) else (t[0], yy[1], t[2]) for t, yy in zip(pc[s], pc[y])]
                targets.append(Col(f"{rcols[y]['name']}+{rcols[s]['name']}", comb, "period", covers=(y, s)))
                covered |= {y, s}
            else:
                targets.append(Col(rcols[s]["name"], pc[s], "period", covers=(s,)))
                covered.add(s)
        for y in years:
            if y not in covered and y in req:
                targets.append(Col(rcols[y]["name"], pc[y], "period", covers=(y,)))
                covered.add(y)

    if "R3" in hits or "R8" in hits:
        ident = (rules.get("identifier_columns") or [None])[0]
        namey = [i for i in range(len(rcols)) if i in req and i not in covered and i != ident
                 and (re.search(r"first|last|name|姓|名", rcols[i]["name"], re.I) or ident is not None)
                 and all(v is None or isinstance(v, str) for v in colvals[i])
                 and any(isinstance(v, str) for v in colvals[i])]
        first = [i for i in namey if re.search(r"first|名", rcols[i]["name"], re.I) and not re.search(r"last|姓", rcols[i]["name"], re.I)]
        last = [i for i in namey if re.search(r"last|姓", rcols[i]["name"], re.I)]
        if first and last:
            f, l = first[0], last[0]
            vals = []
            for r in rrows:
                fv, lv = r[f], r[l]
                placeholder = norm_str(fv) in PLACEHOLDER_NAMES or norm_str(lv) in PLACEHOLDER_NAMES or fv is None or lv is None
                vals.append(("NAME", norm_str(f"{fv or ''} {lv or ''}"), norm_str(f"{lv or ''} {fv or ''}"),
                             norm_str(r[ident]) if ident is not None else None, placeholder))
            targets.append(Col(f"{rcols[f]['name']}+{rcols[l]['name']}", vals, "name", covers=(f, l)))
            covered |= {f, l}
        elif namey:
            i = namey[0]
            vals = []
            for r in rrows:
                v = r[i]
                s = norm_str(v)
                placeholder = v is None or s in PLACEHOLDER_NAMES or all(p in PLACEHOLDER_NAMES for p in (s or "").split("  ")) \
                    or bool(re.fullmatch(r"(not provided ?)+", s or ""))
                vals.append(("NAME", s or "", s or "", norm_str(r[ident]) if ident is not None else None, placeholder))
            targets.append(Col(rcols[i]["name"], vals, "name", covers=(i,)))
            covered.add(i)

    for i in req:
        if i in covered or i in rank_cols:
            continue
        kind = kinds[i] if i < len(kinds) else "other"
        vals = colvals[i]
        t = "num" if all(v is None or is_num(v) for v in vals) else "str"
        targets.append(Col(rcols[i]["name"], vals, t, covers=(i,)))
        targets[-1].vkind = kind
    for t in targets:
        if not hasattr(t, "vkind"):
            t.vkind = "other"
    return targets, notes


# ---------------------------------------------------------------- comparators
def cmp_factory(target: Col, view: Col, qyears: set[int]):
    """Return (compare(refval, ansval)->bool, label) or None if types are incompatible."""
    if target.kind == "num" and view.kind == "num":
        if target.vkind in ("percentage", "ratio", "other", "amount"):
            scales = [1.0]
            if target.vkind in ("percentage", "ratio", "other"):
                scales = [1.0, 100.0, 0.01]
            return [(lambda r, a, s=s, k=target.vkind: num_eq(None if a is None else a * s, r, k), f"x{s:g}")
                    for s in scales]
        return [(lambda r, a, k=target.vkind: num_eq(a, r, k), "x1")]
    if target.kind == "str" and view.kind == "str":
        labels = {norm_str(x) for x in target.values if x not in (None, "")}

        def se(r, a):
            if norm_str(r) == norm_str(a):
                return True
            # v2 baseline: a NULL/empty reference label matches a text label that is not another member.
            return r in (None, "") and isinstance(a, str) and norm_str(a) not in labels
        return [(se, "str")]
    if target.kind == "period" and view.kind == "period":
        single = next(iter(qyears)) if len(qyears) == 1 else None

        def pe(r, a):
            if r is None or a is None:
                return r is None and a is None
            if r[0] != a[0] or r[2] != a[2]:
                return False
            if r[1] == a[1]:
                return True
            # R1: a constant year may be added/omitted only with a unique year in the question.
            if single is None:
                return False
            return (r[1] is None and a[1] == single) or (a[1] is None and r[1] == single)
        return [(pe, "period")]
    if target.kind == "name" and view.kind == "str":
        def ne(r, a):
            _, full, rev, key, placeholder = r
            s = norm_str(a)
            if s is None:
                return False
            if s in (full, rev) or s.replace(" ", "") in (full.replace(" ", ""), rev.replace(" ", "")):
                return True
            return placeholder and key is not None and s == key
        return [(ne, "name")]
    return None


def bucket_key(target: Col, r):
    if target.kind == "str":
        return {norm_str(r)}
    if target.kind == "name":
        _, full, rev, key, placeholder = r
        ks = {full, rev, full.replace(" ", ""), rev.replace(" ", "")}
        if placeholder and key is not None:
            ks.add(key)
        return ks
    return None


def ans_bucket(target: Col, a):
    if target.kind == "name":
        s = norm_str(a)
        return s if s is None or s in () else s
    return norm_str(a)


# ---------------------------------------------------------------- matching
def bipartite(n_a, n_r, adj):
    match_r = [-1] * n_r

    def try_a(a, seen):
        for r in adj[a]:
            if r in seen:
                continue
            seen.add(r)
            if match_r[r] == -1 or try_a(match_r[r], seen):
                match_r[r] = a
                return True
        return False

    sys.setrecursionlimit(10000)
    size = 0
    for a in range(n_a):
        if try_a(a, set()):
            size += 1
    match_a = [-1] * n_a
    for r, a in enumerate(match_r):
        if a >= 0:
            match_a[a] = r
    return size, match_a


def row_match(targets, chosen, nA, nR):
    """chosen: list of (view, cmp). Returns (size, match_a)."""
    # bucket on the first target with hashable keys
    bidx = next((k for k, t in enumerate(targets) if t.kind == "name"
                 or (t.kind == "str" and None not in t.values and "" not in t.values)), None)
    index = None
    if bidx is not None:
        index = {}
        for r in range(nR):
            for key in bucket_key(targets[bidx], targets[bidx].values[r]):
                index.setdefault(key, set()).add(r)
    adj = []
    for a in range(nA):
        cands = range(nR)
        if index is not None:
            view = chosen[bidx][0]
            ak = norm_str(view.values[a])
            cands = sorted(index.get(ak, set()) | index.get((ak or "").replace(" ", ""), set()))
        row = []
        for r in cands:
            if all(cmp(t.values[r], v.values[a]) for t, (v, cmp) in zip(targets, chosen)):
                row.append(r)
        adj.append(row)
    return bipartite(nA, nR, adj)


def search(targets, views, nA, nR, qyears, pool):
    """Try column assignments; return best (ok, mapping, match_a)."""
    options = []
    for t in targets:
        opts = []
        for v in views:
            fs = cmp_factory(t, v, qyears)
            if not fs:
                continue
            for cmp, lab in fs:
                if not pool:
                    # prefilter: every answer value must equal some reference value (multiset size equal)
                    if t.kind == "num":
                        ra = sorted([x for x in t.values if x is not None])
                        aa = [x for x in v.values if x is not None]
                        if len(ra) != len(aa):
                            continue
                        rs = sorted(ra)
                        try:
                            aa2 = sorted(aa)
                        except TypeError:
                            continue
                        # scale-aware check on sorted order (scales are positive)
                        if not all(cmp(r, a) for r, a in zip(rs, aa2)):
                            # negative scaling / mixed signs fall through to full matching
                            pass_sorted = False
                        else:
                            pass_sorted = True
                        if not pass_sorted:
                            continue
                    elif t.kind == "str" and None not in t.values and "" not in t.values:
                        if Counter(norm_str(x) for x in t.values) != Counter(norm_str(x) for x in v.values):
                            continue
                opts.append((v, cmp, lab))
        options.append(opts)
    if any(not o for o in options):
        missing = [t.label for t, o in zip(targets, options) if not o]
        return False, None, None, f"无可映射列: {missing}"
    best = None
    count = 0
    for combo in itertools.product(*options):
        ids = [id(v) for v, _, _ in combo]
        base = [v.label.split("[")[0] for v, _, _ in combo]
        if len(set(ids)) != len(ids):
            continue
        count += 1
        if count > 20000:
            break
        chosen = [(v, cmp) for v, cmp, _ in combo]
        size, match_a = row_match(targets, chosen, nA, nR)
        full = size == nA and (pool or nA == nR)
        if full:
            return True, combo, match_a, ""
        if best is None or size > best[0]:
            best = (size, combo, match_a)
    if best is None:
        return False, None, None, "无可行列组合"
    return False, best[1], best[2], f"行匹配 {best[0]}/{nA}（参考 {nR} 行）"


# ---------------------------------------------------------------- per case
def check_case(d: Path, meta: dict) -> dict:
    a = json.loads((d / "answer-result.json").read_text())
    ref = json.loads((d / "reference-results.json").read_text())
    q = json.loads((d / "question.json").read_text())
    hits = set(json.loads((d / "hit-rules.json").read_text()))
    qtext = q["text"]
    qyears = question_years(qtext)
    rules = ref["rules"]
    out = {"ok": False, "detail": "", "flags": []}
    if a.get("error"):
        out["detail"] = "作答执行报错"
        return out
    acols = a["columns"]
    arows = coerce_numeric_text(acols, a["rows"])
    results = []
    for k, (rrows, rcols) in enumerate(zip(ref["references"], ref["columns"])):
        results.append(check_against(acols, arows, rcols, rrows, rules, hits, qtext, qyears))
    ok = [r for r in results if r["ok"]]
    return ok[0] if ok else results[0]


def check_against(acols, arows, rcols, rrows, rules, hits, qtext, qyears):
    flags = []
    rules = dict(rules)
    req = list(rules.get("required_columns") or range(len(rcols)))
    kinds = rules.get("value_kinds") or ["other"] * len(rcols)
    colvals = [[r[i] for r in rrows] for i in range(len(rcols))]

    # R2: long -> wide pivot of the reference, columns identified by enum header text.
    if "R2" in hits:
        res = pivot_reference(acols, arows, rcols, rrows, req, kinds)
        if res is None:
            return {"ok": False, "detail": "R2: 无法唯一识别枚举列头", "flags": flags}
        rcols, rrows, req, kinds, pflags = res
        flags += pflags
        rules["required_columns"], rules["value_kinds"] = req, kinds
        rules["ordered"] = False
        colvals = [[r[i] for r in rrows] for i in range(len(rcols))]

    # R11: one-row comparison reference vs two-row (comparison + baseline) answer
    if "R11" in hits and len(rrows) == 1 and len(arows) == 2:
        return check_r11(acols, arows, rcols, rrows, req, kinds)

    extra_req = []
    # R9: a constant total column may be omitted when it equals the sum of a group amount column.
    if "R9" in hits:
        for i in list(req):
            vals = colvals[i]
            if not vals or not all(is_num(v) for v in vals) or len({round(v, 2) for v in vals}) != 1:
                continue
            for p in range(len(rcols)):
                if p == i or not all(is_num(v) for v in colvals[p]):
                    continue
                if num_eq(sum(colvals[p]), vals[0], "amount"):
                    req.remove(i)
                    extra_req.append(p)
                    flags.append(f"R9: 总分母列省略，需各组金额且合计={rcols[p]['name']}")
                    break
    # R10: original amount omitted when revenue and discount rate reproduce it row by row.
    if "R10" in hits:
        for i in list(req):
            if kinds[i] != "amount" or not all(is_num(v) for v in colvals[i]):
                continue
            found = False
            for v_ in range(len(rcols)):
                for d_ in range(len(rcols)):
                    if len({i, v_, d_}) < 3 or kinds[v_] != "amount" or kinds[d_] not in ("percentage", "ratio") \
                            or not all(is_num(x) for x in colvals[v_] + colvals[d_]):
                        continue
                    for sc in (1.0, 0.01):
                        if all(num_eq(r[v_] / (1 - r[d_] * sc), r[i], "amount") for r in rrows if r[d_] * sc < 1):
                            found = (v_, d_)
                            break
                    if found:
                        break
                if found:
                    break
            if found:
                req.remove(i)
                for x in found:
                    if x not in req:
                        extra_req.append(x)
                flags.append("R10: 折前额由折后额与折扣率逐行还原")
    # R8: identifier column may be omitted when the name is unique per row.
    omit_ident = None
    ident = (rules.get("identifier_columns") or [None])[0]
    rules["required_columns"] = req + extra_req
    targets, _ = ref_targets(rcols, rrows, rules, hits)
    for t in targets:
        if t.covers and t.covers[0] in extra_req:
            t.vkind = kinds[t.covers[0]]
    views = answer_views(acols, arows, hits)
    nA, nR = len(arows), len(rrows)
    top_n = rules.get("top_n")
    pool = bool((top_n or rules.get("selection")) and nR > nA)

    ok, combo, match_a, why = search(targets, views, nA, nR, qyears, pool)
    if not ok and "R8" in hits and ident is not None:
        tt = [t for t in targets if ident not in t.covers]
        name_t = [t for t in tt if t.kind in ("name", "str")]
        if name_t and len(tt) < len(targets):
            keys = [tuple((x[1] if t.kind == "name" else norm_str(x)) for t in name_t for x in [t.values[r]]) for r in range(nR)]
            if len(set(keys)) == nR:
                ok, combo, match_a, why = search(tt, views, nA, nR, qyears, pool)
                if ok:
                    targets = tt
                    omit_ident = rcols[ident]["name"]
                    flags.append("R8: 省略编码列，名称在参考中唯一")
            else:
                why += "；R8: 参考名称不唯一"
    if not ok:
        return {"ok": False, "detail": why, "flags": flags}

    # name targets: report how placeholder rows were delivered
    for t, (v, _, lab) in zip(targets, combo):
        if t.kind == "name":
            fb = sum(1 for ai, ri in enumerate(match_a) if ri >= 0 and t.values[ri][4]
                     and norm_str(v.values[ai]) == t.values[ri][3])
            if fb:
                flags.append(f"占位姓名用编码回退 {fb} 行")
        if t.kind == "period":
            yrs = {t.values[ri][1] for ri in match_a if ri >= 0 and t.values[ri]} ^ set()
            ays = {v.values[ai][1] for ai in range(nA) if v.values[ai]}
            if yrs != ays:
                flags.append(f"期间年份由题面唯一年份补齐/省略 {sorted(qyears)}")
        if v.note:
            flags.append(v.note)

    # pool (Top-N with tie candidates): every reference row strictly inside N must be present.
    if pool:
        res = check_pool(rules, rcols, rrows, match_a, nA)
        if res:
            return {"ok": False, "detail": res, "flags": flags}
        flags.append("参考为并列候选池，作答取其子集")

    # ordering
    if rules.get("ordered") and rules.get("order_by"):
        okord = order_ok(rules["order_by"], rrows, match_a, kinds)
        if not okord:
            if "R7" in hits:
                flags.append("R7: 忽略行序")
                if SORT_WORDS.search(qtext) or top_n or rules.get("selection"):
                    return {"ok": False, "detail": "R7 守卫：题面含排序/Top-N 要求", "flags": flags}
            else:
                return {"ok": False, "detail": "行序与参考不符", "flags": flags}
    elif "R7" in hits:
        flags.append("R7 命中但参考未要求排序")

    # rank columns
    for rc in rules.get("rank_columns") or []:
        if rc not in req:
            continue
        msg = rank_ok(rules, rc, rrows, acols, arows, match_a)
        if msg.startswith("FAIL"):
            return {"ok": False, "detail": msg, "flags": flags}
        if msg:
            flags.append(msg)

    # R6 guard: negation only with an explicit decrease header (enforced in views); report header use
    return {"ok": True, "detail": "", "flags": flags,
            "mapping": [(t.label, v.label, lab) for t, (v, _, lab) in zip(targets, combo)]}


def order_ok(order_by, rrows, match_a, kinds):
    seq = [rrows[r] for r in match_a]
    for i in range(len(seq) - 1):
        for ob in order_by:
            c, desc = ob["column"], ob.get("descending", False)
            x, y = seq[i][c], seq[i + 1][c]
            if is_num(x) and is_num(y):
                if num_eq(x, y, "other"):
                    continue
                if (x > y) != desc:
                    return False
                break
            if x == y:
                continue
            try:
                if (x > y) != desc:
                    return False
            except TypeError:
                return False
            break
    return True


def check_pool(rules, rcols, rrows, match_a, nA):
    rk = (rules.get("rank_columns") or [None])[0]
    if rk is None:
        return "并列候选池但无名次列，无法判定必含行"
    groups = (rules.get("rankings") or [{}])[0].get("group_columns") or []
    n = rules.get("top_n") or (rules.get("selection") or {}).get("stages", [{}])[0].get("n")
    matched = set(match_a)
    by_group = {}
    for i, r in enumerate(rrows):
        by_group.setdefault(tuple(r[g] for g in groups), []).append(i)
    for g, idx in by_group.items():
        cnt = Counter(rrows[i][rk] for i in idx)
        for i in idx:
            rank = rrows[i][rk]
            if rank + cnt[rank] - 1 <= n and i not in matched:
                return f"并列候选池中必含行缺失（组 {g!r}）"
        got = sum(1 for i in idx if i in matched)
        if got < min(n, len(idx)):
            return f"组 {g!r} 行数不足 {got}<{min(n, len(idx))}"
    return ""


def rank_ok(rules, rc, rrows, acols, arows, match_a):
    """Find an integer answer column consistent with the reference ranking."""
    ranking = next((x for x in rules.get("rankings") or [] if x["column"] == rc), {})
    groups = ranking.get("group_columns") or []
    ref_rank = [rrows[r][rc] for r in match_a]
    gkey = [tuple(rrows[r][g] for g in groups) for r in match_a]
    for i, c in enumerate(acols):
        vals = [row[i] for row in arows]
        if not all(is_num(v) and float(v).is_integer() for v in vals):
            continue
        if all(v == r for v, r in zip(vals, ref_rank)):
            return ""
        # row_number style: within each group, answer ranks are 1..k and refine the reference ranks
        okk = True
        per = {}
        for v, r, g in zip(vals, ref_rank, gkey):
            per.setdefault(g, []).append((v, r))
        for g, pairs in per.items():
            pairs.sort()
            if [p[0] for p in pairs] != list(range(1, len(pairs) + 1)):
                okk = False
                break
            # ref ranks must be non-decreasing in answer rank order, and the answer rank
            # of each row must lie inside its reference tie block
            refs = [p[1] for p in pairs]
            if refs != sorted(refs):
                okk = False
                break
            cnt = Counter(refs)
            if any(not (r <= v <= r + cnt[r] - 1) for v, r in pairs):
                okk = False
                break
        if okk:
            return "名次列为连续编号（并列者拆开），名次落在参考并列块内"
    return "FAIL 名次列与参考不符"


def pivot_reference(acols, arows, rcols, rrows, req, kinds):
    flags = []
    strcols = [i for i in req if all(isinstance(r[i], str) for r in rrows)]
    numcols = [i for i in req if all(is_num(r[i]) or r[i] is None for r in rrows)]
    for e in strcols:
        enums = sorted({r[e] for r in rrows})
        if len(enums) < 2:
            continue
        heads = {}
        for ev in enums:
            names = [ev.casefold()] + SCENARIO_ALIASES.get(ev, [])
            hit = [i for i, c in enumerate(acols) if any(n in c["name"].casefold() for n in names)
                   and all(is_num(row[i]) or row[i] is None for row in arows)]
            hit = [i for i in hit if not re.search(r"diff|差|变化|rate|率|pct|%", acols[i]["name"], re.I)]
            if len(hit) != 1:
                break
            heads[ev] = hit[0]
        else:
            groups = [i for i in strcols if i != e]
            if len(numcols) != 1:
                continue
            v = numcols[0]
            wide = {}
            for r in rrows:
                wide.setdefault(tuple(r[g] for g in groups), {})[r[e]] = r[v]
            if any(len(x) != len(enums) for x in wide.values()):
                return None
            ncols = [rcols[g] for g in groups] + [{"name": f"{ev}"} for ev in enums]
            nrows = [list(k) + [wide[k][ev] for ev in enums] for k in sorted(wide)]
            nreq = list(range(len(ncols)))
            nkinds = [kinds[g] for g in groups] + [kinds[v]] * len(enums)
            # verify identifiable extra difference / rate columns in the answer
            ia, ib = heads[enums[0]], heads[enums[1]]
            for i, c in enumerate(acols):
                if i in heads.values() or not re.search(r"diff|差|变化|variance", c["name"], re.I):
                    continue
                vals = [row[i] for row in arows]
                diffs = [(row[ia] - row[ib]) if row[ia] is not None and row[ib] is not None else None for row in arows]
                cand = {
                    "a-b": diffs, "b-a": [None if x is None else -x for x in diffs],
                    "(a-b)/b": [None if x is None or not row[ib] else x / row[ib] for x, row in zip(diffs, arows)],
                    "(b-a)/b": [None if x is None or not row[ib] else -x / row[ib] for x, row in zip(diffs, arows)],
                    "(a-b)/a": [None if x is None or not row[ia] else x / row[ia] for x, row in zip(diffs, arows)],
                }
                good = []
                for name, cv in cand.items():
                    for sc in (1.0, 100.0):
                        if all(num_eq(x, None if y is None else y * sc, "other") or
                               (x is not None and y is not None and abs(x - y * sc) <= 0.00051 * sc)
                               for x, y in zip(vals, cv)):
                            good.append(name)
                if not good:
                    flags.append(f"R2: 附加列 {c['name']} 无法核验")
                else:
                    flags.append(f"R2: 附加列 {c['name']} = {good[0]}")
            flags.append("R2: 参考长表按枚举列头转宽表")
            return ncols, nrows, nreq, nkinds, flags
    return None


def check_r11(acols, arows, rcols, rrows, req, kinds):
    target = [(i, rrows[0][i]) for i in req]
    for ri, row in enumerate(arows):
        used = set()
        okk = True
        for i, v in target:
            sc = [1.0, 100.0, 0.01] if kinds[i] in ("percentage", "ratio") else [1.0]
            j = next((j for j, x in enumerate(row) if j not in used and is_num(x)
                      and any(num_eq(x * s, v, kinds[i]) for s in sc)), None)
            if j is None:
                okk = False
                break
            used.add(j)
        if not okk:
            continue
        other = arows[1 - ri]
        # verify: some numeric column differs between the two rows by the reference amount difference
        amt = [v for i, v in target if kinds[i] == "amount"]
        verified = any(is_num(row[j]) and is_num(other[j]) and num_eq(row[j] - other[j], amt[0], "amount")
                       for j in range(len(row))) if amt else False
        pct = [v for i, v in target if kinds[i] == "percentage"]
        pverified = any(is_num(row[j]) and is_num(other[j]) and other[j]
                        and any(num_eq((row[j] - other[j]) / other[j] * s, pct[0], "other") for s in (1.0, 100.0))
                        for j in range(len(row))) if pct else True
        if verified and pverified:
            return {"ok": True, "detail": "", "flags": ["R11: 比较组行含全部比较指标，与基准组两行可逆算"]}
        return {"ok": False, "detail": "R11: 比较指标存在但无法由两行逆算", "flags": []}
    return {"ok": False, "detail": "R11: 找不到含全部比较指标的行", "flags": []}


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", default=os.path.join(os.environ.get("SEMDEBT_DATA_DIR", ""), "t31-claude-review-20261027"))
    ap.add_argument("--manual", default="reports/validation/t31-v4-claude-review-manual.csv")
    ap.add_argument("--out", default="reports/validation/t31-v4-claude-review.csv")
    ap.add_argument("--details", help="optional JSON with mappings and flags (write outside the repo)")
    ap.add_argument("--only", nargs="*", help="bundle directories to check (debug)")
    args = ap.parse_args()

    bundle = Path(args.bundle)
    index = json.loads((bundle / "index.json").read_text())
    cases = [f for f in index["all_flips"] if f.get("bundle_directory")]
    if args.only:
        cases = [f for f in cases if f["bundle_directory"] in args.only]
    manual = {}
    if os.path.exists(args.manual):
        with open(args.manual, newline="") as fh:
            for row in csv.DictReader(fh):
                manual[int(row["row"])] = row

    out_rows, details, pending = [], {}, []
    for f in cases:
        d = bundle / f["bundle_directory"]
        res = check_case(d, f)
        row = int(f["csv_data_row"])
        rules = "+".join(f["rules"])
        details[f["bundle_directory"]] = {"row": row, "qid": f["qid"], "cell": f["cell"], "rep": f["rep"], **res}
        needs_eye = (not res["ok"]) or any("守卫" in x or "无法核验" in x or "名次列" in x
                                           or "R7 命中" in x for x in res.get("flags", []))
        if row in manual:
            m = manual[row]
            verdict, note = m["verdict"], m["note"]
        elif not needs_eye:
            verdict, note = "放行正确", auto_note(f["rules"], res)
        else:
            verdict, note = "待人工", res["detail"] or "；".join(res.get("flags", []))[:30]
            pending.append((row, f["bundle_directory"], f["qid"], f["cell"], f["rep"], rules, res))
        out_rows.append({"row": row, "qid": f["qid"], "cell": f["cell"], "rep": f["rep"],
                         "rules": rules, "verdict": verdict, "note": note[:30], "auto": res["ok"]})

    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["row", "qid", "cell", "rep", "rules", "verdict", "note"], extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(out_rows, key=lambda r: r["row"]))
    if args.details:
        Path(args.details).write_text(json.dumps(details, ensure_ascii=False, indent=1, default=str))
    c = Counter(r["verdict"] for r in out_rows)
    print(f"cases={len(out_rows)} auto_pass={sum(bool(r['auto']) for r in out_rows)} verdicts={dict(c)}")
    for p in pending:
        print("PENDING", p[0], p[1], p[2], p[3], f"r{p[4]}", p[5], "|", p[6]["detail"], "|", p[6].get("flags"))
    return 0


def auto_note(rules, res):
    flags = res.get("flags", [])
    if "R1" in rules:
        return "期间无损归一后逐行一致" + ("；年份依题面" if any("年份" in x for x in flags) else "")
    if rules == ["R8"] and any("省略编码列" in x for x in flags):
        return "名称唯一，可省编码列" + ("；空名给编码" if any("编码回退" in x for x in flags) else "")
    if "R3" in rules or "R8" in rules:
        fb = any("编码回退" in x for x in flags)
        return "姓名合并后逐行一致" + ("；占位名用编码" if fb else "")
    return {"R2": "长宽转换后逐组一致，差额可核", "R4": "去客户后缀后各组一致",
            "R6": "减少量列头明确，取负后一致", "R7": "题面未要求排序，内容一致",
            "R9": "各组金额合计=总额，可省总分母", "R10": "折前额可由折后额与折扣率还原",
            "R11": "两行布局可逆算出比较指标"}.get(rules[0], "规则变换后一致")


if __name__ == "__main__":
    sys.exit(main())
