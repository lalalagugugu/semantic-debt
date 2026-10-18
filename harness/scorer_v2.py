"""Specification v2 scorer. No query execution, metadata inference, or diagnostics on the scoring path."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, TypeAlias
from datetime import date, datetime, time
from decimal import Decimal, localcontext
from numbers import Number
import re

from harness.scorer import ExecError, REFUSAL
from harness.selection import validate_selection
from harness.value_units import KINDS, is_integer_type, is_numeric_type, quantize_tie

Outcome: TypeAlias = Literal["correct", "wrong", "exec_error", "refused", "unscored"]
Rows: TypeAlias = Sequence[Sequence[object]]


@dataclass(frozen=True)
class ScoreResult:
    outcome: Outcome
    reason: str | None = None
    matched_ref: int | None = None
    sensitivity: str | None = None


CAP = 1000
_NUM = "number"


def _number(value):
    return isinstance(value, (Number, Decimal)) and not isinstance(value, (bool, complex))


def _norm(value, identifier=False):
    if isinstance(value, str):
        value = value.strip()
        if identifier and re.fullmatch(r"(?:0|[1-9][0-9]*|-[1-9][0-9]*)", value):
            return (_NUM, Decimal(value))
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T]00:00:00(?:\.0+)?)?", value):
            try:
                return ("date", date.fromisoformat(value[:10]))
            except ValueError:
                pass
        return ("text", value)
    if isinstance(value, datetime):
        if value.tzinfo is None and value.time() == time():
            return ("date", value.date())
        return ("datetime", value.isoformat())
    if isinstance(value, date):
        return ("date", value)
    if _number(value):
        number = value if isinstance(value, (int, Decimal)) else Decimal(str(value))
        # Nonfinite values must not compare equal, even to themselves.
        return (_NUM, number) if isinstance(number, int) or number.is_finite() else ("nonfinite", object())
    if isinstance(value, (list, tuple)):
        cells = tuple(_norm(v) for v in value)
        if any(v[0] == "nonfinite" for v in cells):
            return ("nonfinite", object())
        return ("array", cells)
    if value is None:
        return ("null", None)
    if isinstance(value, bool):
        return ("bool", value)
    raise TypeError(f"unsupported cell type: {type(value).__name__}")


def _rows(rows):
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise TypeError("rows must be a sequence of rows")
    width = len(rows[0]) if rows else None
    for row in rows:
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence) or len(row) != width:
            raise ValueError("rows must be rectangular")
    return rows


def _columns(value, width, name, nonempty=False):
    if not isinstance(value, (list, tuple)) or (nonempty and not value) or any(type(i) is not int or not 0 <= i < width for i in value) or len(set(value)) != len(value):
        raise ValueError(f"invalid {name}")
    return tuple(value)


def _validate(rule, rows):
    if not isinstance(rule, Mapping):
        raise ValueError("rules must be a mapping")
    for field in ("required_columns", "value_kinds", "value_types", "ordered", "top_n", "tie_columns"):
        if field not in rule:
            raise ValueError(f"missing {field}")
    if any(k in rule for k in ("use_absolute_tolerance", "exact_counts")):
        raise ValueError("historical scoring switches are not accepted")
    allowed = {"required_columns", "value_kinds", "value_types", "ordered", "top_n", "tie_columns",
               "order_by", "selection", "identifier_columns", "rank_columns", "rankings", "unordered_pairs"}
    if set(rule) - allowed:
        raise ValueError("unknown rules fields")
    width = len(rule["value_types"])
    if not width or any(len(row) != width for row in rows):
        raise ValueError("reference width differs from value_types")
    if len(rule["value_kinds"]) != width or any(k not in KINDS for k in rule["value_kinds"]):
        raise ValueError("invalid value_kinds")
    if any(not isinstance(t, str) or not t for t in rule["value_types"]):
        raise ValueError("invalid value_types")
    required = _columns(rule["required_columns"], width, "required_columns", True)
    if type(rule["ordered"]) is not bool:
        raise ValueError("ordered must be boolean")
    order = rule.get("order_by", [])
    if rule["ordered"] and not order:
        raise ValueError("ordered requires order_by")
    for item in order:
        if not isinstance(item, Mapping) or set(item) != {"column", "descending"} or type(item["descending"]) is not bool:
            raise ValueError("invalid order_by")
    _columns([x["column"] for x in order], width, "order_by")
    for name in ("identifier_columns", "rank_columns", "tie_columns"):
        _columns(rule.get(name, []), width, name)
    top = rule.get("top_n")
    if top is not None:
        if type(top) is not int or top < 1 or not rule.get("tie_columns"):
            raise ValueError("top_n requires positive N, tie_columns and a complete reference domain")
        if len(rows) >= top:
            boundary = _key(rows[top - 1], rule["tie_columns"], rule)
            if any(_key(row, rule["tie_columns"], rule) != boundary for row in rows[top:]):
                raise ValueError("Top-N reference must end with its complete boundary group")
    elif rule.get("tie_columns"):
        raise ValueError("tie_columns requires top_n")
    if rule.get("selection") is not None:
        if top is not None:
            raise ValueError("selection and top_n are mutually exclusive")
        validate_selection(rule["selection"], width, ordered=rule["ordered"])
        for stage in rule["selection"]["stages"]:
            if not set(stage["group_columns"] + stage["object_columns"] + [c["column"] for c in stage["where"]]) <= set(required):
                raise ValueError("selection identity and where columns must be required_columns")
    used = set()
    for pair in rule.get("unordered_pairs", []):
        left = _columns(pair["left"], width, "unordered_pairs.left", True)
        right = _columns(pair["right"], width, "unordered_pairs.right", True)
        if len(left) != len(right) or set(left) & set(right) or used & set(left + right):
            raise ValueError("unordered_pairs must be equally wide and disjoint")
        used.update(left + right)
    for ranking in rule.get("rankings", []):
        if ranking["column"] not in rule.get("rank_columns", []):
            raise ValueError("rankings.column must be in rank_columns")
        _columns(ranking["group_columns"], width, "rankings.group_columns")
        _columns(ranking["object_columns"], width, "rankings.object_columns", True)
        if type(ranking["prefix"]) is not bool:
            raise ValueError("rankings.prefix must be boolean")
        for block in ranking["blocks"]:
            if len(block["group"]) != len(ranking["group_columns"]) or any(type(block[k]) is not int or block[k] < 1 for k in ("rank", "dense", "size")):
                raise ValueError("invalid rankings.blocks")
    return required


@dataclass(frozen=True)
class Part:
    reference: tuple[int, ...]
    candidate: tuple[int, ...]
    reverse: bool = False


def _get(row, cols, reverse=False):
    if len(cols) == 1:
        return row[cols[0]]
    values = [row[i] for i in cols]
    if not all(isinstance(v, str) for v in values):
        return None
    if reverse:
        values.reverse()
    return " ".join(v.strip() for v in values).strip()


def _string_column(rule, i):
    declared = rule["value_types"][i]
    while match := re.fullmatch(r"(?:Nullable|LowCardinality)\((.*)\)", declared):
        declared = match.group(1)
    return re.fullmatch(r"String|FixedString\([0-9]+\)", declared) is not None


def _canonical(cell):
    # Retain string provenance only for the empty-label exception; the date
    # equivalence itself remains shared with native date values.
    return ("date", cell[1]) if cell[0] == "date_string" else cell


def _equal(c, r, kind, exact, labels):
    if c[0] in ("nonfinite", "invalid_join") or r[0] in ("nonfinite", "invalid_join"):
        return False
    if _canonical(c) == _canonical(r):
        return True
    if labels is not None:
        if r == ("text", "") and c == ("null", None):
            return True
        if r in (("null", None), ("text", "")) and c[0] in {"text", "date_string"} and _canonical(c) not in labels:
            return True
    if exact or c[0] != _NUM or r[0] != _NUM:
        return False
    a, b = Decimal(c[1]), Decimal(r[1])
    with localcontext() as ctx:
        ctx.prec = max(50, len(a.as_tuple().digits) + abs(a.adjusted()) + 10,
                       len(b.as_tuple().digits) + abs(b.adjusted()) + 10)
        atol = {"amount": Decimal(".01"), "ratio": Decimal(".0001"), "percentage": Decimal(".01")}.get(kind, Decimal(0))
        limit = max(abs(b) * Decimal(".005"), atol)
        return any(abs(x - b) <= limit for x in ((a,) if b == 0 or kind not in {"other", "ratio", "percentage"} else (a, a * 100, a / 100)))


def _numeric_windows(value, kind):
    value = Decimal(value)
    with localcontext() as ctx:
        ctx.prec = max(50, len(value.as_tuple().digits) + abs(value.adjusted()) + 20)
        atol = {"amount": Decimal(".01"), "ratio": Decimal(".0001"), "percentage": Decimal(".01")}.get(kind, Decimal(0))
        delta = max(abs(value) * Decimal(".005"), atol)
        return [((value - delta) / scale, (value + delta) / scale)
                for scale in ((Decimal(1),) if value == 0 or kind not in {"other", "ratio", "percentage"}
                              else (Decimal(1), Decimal(100), Decimal(".01")))]


class _Flow:
    """Integral capacity matching, with duplicate rows compressed into vertices."""
    def __init__(self, size):
        self.graph = [[] for _ in range(size)]

    def edge(self, a, b, capacity):
        forward = [b, capacity, None]
        reverse = [a, 0, forward]
        forward[2] = reverse
        self.graph[a].append(forward)
        self.graph[b].append(reverse)
        return forward

    def augment(self, source, sink):
        total = 0
        while True:
            level = [-1] * len(self.graph)
            level[source] = 0
            queue = deque([source])
            while queue:
                a = queue.popleft()
                for edge in self.graph[a]:
                    if edge[1] and level[edge[0]] < 0:
                        level[edge[0]] = level[a] + 1
                        queue.append(edge[0])
            if level[sink] < 0:
                return total
            cursor = [0] * len(self.graph)
            while True:
                nodes, path = [source], []
                while nodes and nodes[-1] != sink:
                    a = nodes[-1]
                    while cursor[a] < len(self.graph[a]):
                        edge = self.graph[a][cursor[a]]
                        if edge[1] and level[edge[0]] == level[a] + 1:
                            nodes.append(edge[0])
                            path.append(edge)
                            break
                        cursor[a] += 1
                    else:
                        level[a] = -1
                        nodes.pop()
                        if path:
                            path.pop()
                if not nodes:
                    break
                amount = min(edge[1] for edge in path)
                for edge in path:
                    edge[1] -= amount
                    edge[2][1] += amount
                total += amount


def _edges(candidates, references, metadata, swaps=()):
    """Materialize only the most selective indexed pool, then verify complete rows."""
    indexes, numeric, wildcard = [], [], []
    for d, (_, _, labels) in enumerate(metadata):
        by_key = defaultdict(list)
        numbers, blanks = [], []
        for i, row in enumerate(candidates):
            cell = row[d]
            by_key[cell].append(i)
            if cell[0] == "date_string":
                by_key[_canonical(cell)].append(i)
            if cell[0] == _NUM:
                numbers.append((cell[1], i))
            if labels is not None and cell[0] in {"text", "date_string"} and _canonical(cell) not in labels:
                blanks.append(i)
        numbers.sort()
        indexes.append(by_key)
        numeric.append(([v for v, _ in numbers], [i for _, i in numbers]))
        wildcard.append(blanks)
    partners = {}
    for left, right in swaps:
        partners.update(zip(left, right))
        partners.update(zip(right, left))
    for row in references:
        best, best_size = [], float("inf")
        for d, (kind, exact, labels) in enumerate(metadata):
            cell, sources, size = row[d], [], 0
            for source_dim in sorted({d, partners.get(d, d)}):
                if cell[0] == _NUM and not exact:
                    values, ids = numeric[source_dim]
                    for low, high in _numeric_windows(cell[1], kind):
                        lo, hi = bisect_left(values, low), bisect_right(values, high)
                        size += hi - lo
                        sources.append((ids, lo, hi))
                else:
                    ids = indexes[source_dim].get(_canonical(cell), ())
                    size += len(ids)
                    sources.append((ids, 0, len(ids)))
                    if labels is not None and cell in (("null", None), ("text", "")):
                        ids = wildcard[source_dim]
                        size += len(ids)
                        sources.append((ids, 0, len(ids)))
                        if cell == ("text", ""):
                            ids = indexes[source_dim].get(("null", None), ())
                            size += len(ids)
                            sources.append((ids, 0, len(ids)))
            if size < best_size:
                best_size, best = size, sources
            if not best_size:
                break
        pool = sorted({i for ids, lo, hi in best for i in ids[lo:hi]}) if metadata else range(len(candidates))
        adjacent = []
        for i in pool:
            candidate = candidates[i]
            if not all(_equal(candidate[d], row[d], *metadata[d]) for d in range(len(metadata)) if d not in partners):
                continue
            if all(
                all(_equal(candidate[d], row[d], *metadata[d]) for d in left + right)
                or all(_equal(candidate[partners[d]], row[d], *metadata[d]) for d in left + right)
                for left, right in swaps
            ):
                adjacent.append(i)
        yield adjacent


def _match(candidate, reference, metadata, mandatory=None, swaps=()):
    """Cover every candidate and every mandatory reference, allowing optional boundary rows."""
    cc, rr = Counter(candidate), Counter(reference)
    if mandatory is None and cc == rr and not any(cell[0] in ("nonfinite", "invalid_join") for row in cc for cell in row):
        return True
    required = Counter(reference if mandatory is None else mandatory)
    # Seed the matching with a sorted, fully verified witness. Covering all
    # vertices proves maximum cardinality; a failed witness falls through to flow.
    # This avoids materializing dense tolerance windows for near-identical tables.
    if mandatory is None and sum(cc.values()) == sum(rr.values()) and not swaps and not any(
            cell[0] in ("nonfinite", "invalid_join") for row in cc.keys() | rr.keys() for cell in row):
        left, right = sorted(cc.items()), sorted(rr.items())
        i = j = 0
        a = left[0][1] if left else 0
        b = right[0][1] if right else 0
        while i < len(left) and j < len(right):
            if not all(_equal(c, r, *m) for c, r, m in zip(left[i][0], right[j][0], metadata)):
                break
            amount = min(a, b)
            a -= amount
            b -= amount
            if not a:
                i += 1
                if i < len(left):
                    a = left[i][1]
            if not b:
                j += 1
                if j < len(right):
                    b = right[j][1]
        if i == len(left) and j == len(right):
            return True
        if (len(metadata) == 1 and metadata[0][0] in {"amount", "count"}
                and not metadata[0][1] and all(row[0][0] == _NUM for row in cc.keys() | rr.keys())):
            # These intervals have monotonically increasing lower/upper bounds:
            # sorted pairing is the maximum matching of this convex graph.
            return False
    if not swaps and all(
        (exact or all(row[d][0] != _NUM for row in rr))
        and not (labels is not None and any(row[d] in (("null", None), ("text", "")) for row in rr))
        for d, (_, exact, labels) in enumerate(metadata)
    ) and not any(cell[0] == "date_string" for row in cc.keys() | rr.keys() for cell in row):
        return all(cc[key] >= count for key, count in required.items()) and all(rr[key] >= count for key, count in cc.items())
    if sum(required.values()) > sum(cc.values()) or sum(cc.values()) > sum(rr.values()):
        return False
    ckeys, rkeys = list(cc), list(rr)
    flow = _Flow(len(ckeys) + len(rkeys) + 2)
    source, sink = len(flow.graph) - 2, len(flow.graph) - 1
    offset = len(rkeys)
    for i, key in enumerate(ckeys):
        flow.edge(offset + i, sink, cc[key])
    for j, adjacent in enumerate(_edges(ckeys, rkeys, metadata, swaps)):
        if required[rkeys[j]] and not adjacent:
            return False
        for i in adjacent:
            flow.edge(j, offset + i, min(rr[rkeys[j]], cc[ckeys[i]]))
    for j, key in enumerate(rkeys):
        flow.edge(source, j, required[key])
    done = flow.augment(source, sink)
    if done != sum(required.values()):
        return False
    for j, key in enumerate(rkeys):
        flow.edge(source, j, rr[key] - required[key])
    return done + flow.augment(source, sink) == sum(cc.values())


def _cover_required(candidate, reference, metadata, required_candidate, required_reference):
    """Feasibility with lower bounds on both sides (optional zero-row marginals)."""
    cc, rr = Counter(candidate), Counter(reference)
    need_c, need_r = Counter(required_candidate), Counter(required_reference)
    if not need_c and not need_r:
        return True
    if need_r == rr and len(candidate) == len(reference):
        return _match(candidate, reference, metadata)
    if need_c == cc:
        return _match(candidate, reference, metadata, required_reference)
    if not metadata[0][1] and metadata[0][2] is not None and not any(
            row[0] in (("null", None), ("text", "")) for row in rr) and not any(
                row[0][0] == "date_string" for row in cc.keys() | rr.keys()):
        return all(rr[key] >= n for key, n in need_c.items()) and all(cc[key] >= n for key, n in need_r.items())
    ckeys, rkeys = list(cc), list(rr)
    source = len(ckeys) + len(rkeys)
    sink, super_source, super_sink = source + 1, source + 2, source + 3
    flow = _Flow(source + 4)
    demand = [0] * (source + 2)
    def lower_edge(a, b, lower, upper):
        flow.edge(a, b, upper - lower)
        demand[a] -= lower
        demand[b] += lower
    offset = len(rkeys)
    for j, key in enumerate(rkeys):
        lower_edge(source, j, need_r[key], rr[key])
    for i, key in enumerate(ckeys):
        lower_edge(offset + i, sink, need_c[key], cc[key])
    for j, adjacent in enumerate(_edges(ckeys, rkeys, metadata)):
        for i in adjacent:
            flow.edge(j, offset + i, min(rr[rkeys[j]], cc[ckeys[i]]))
    flow.edge(sink, source, len(candidate) + len(reference))
    total = 0
    for node, amount in enumerate(demand):
        if amount > 0:
            flow.edge(super_source, node, amount)
            total += amount
        elif amount < 0:
            flow.edge(node, super_sink, -amount)
    return flow.augment(super_source, super_sink) == total


def _reference_zero_flags(reference, rule, required):
    identifiers = set(rule.get("identifier_columns", [])) | set(rule.get("rank_columns", []))
    counts = [i for i in required if rule["value_kinds"][i] == "count" and i not in identifiers]
    numbers = [i for i in required if is_numeric_type(rule["value_types"][i]) and i not in identifiers]
    return [bool(counts) and all(_number(row[i]) and row[i] == 0 for i in counts)
            and all(row[i] is None or (_number(row[i]) and row[i] == 0) for i in numbers)
            for row in reference]


def _metadata(rule, parts, reference):
    ids = set(rule.get("identifier_columns", [])) | set(rule.get("rank_columns", []))
    if rule.get("selection"):
        for stage in rule["selection"]["stages"]:
            ids.update(stage["group_columns"] + stage["object_columns"])
    out = []
    for p in parts:
        col = p.reference[0]
        labels = None
        if len(p.reference) == 1 and _string_column(rule, col) and col not in ids:
            labels = {_norm(_get(row, p.reference)) for row in reference}
        out.append((rule["value_kinds"][col], any(i in ids for i in p.reference) or is_integer_type(rule["value_types"][col]), labels))
    return out


def _project(rows, parts, candidate, rule):
    identifiers = set(rule.get("identifier_columns", []))
    out, cache = [], {}
    for row in rows:
        key = id(row)
        if key not in cache:
            cells = []
            for part in parts:
                columns = part.candidate if candidate else part.reference
                value = _get(row, columns, part.reverse if len(columns) == 2 else False)
                cell = (("invalid_join", object()) if len(columns) == 2 and value is None
                        else _norm(value, part.reference[0] in identifiers))
                if cell[0] == "date" and isinstance(value, str) and _string_column(rule, part.reference[0]):
                    cell = ("date_string", cell[1])
                cells.append(cell)
            projected = tuple(cells)
            if len(cache) < 4096:
                cache[key] = projected
        else:
            projected = cache[key]
        out.append(projected)
    return out


def _zero(row, parts, rule):
    counts = []
    ignored = set(rule.get("identifier_columns", [])) | set(rule.get("rank_columns", []))
    for d, part in enumerate(parts):
        col = part.reference[0]
        if col in ignored:
            continue
        cell = row[d]
        if rule["value_kinds"][col] == "count":
            counts.append(cell == (_NUM, 0))
        if is_numeric_type(rule["value_types"][col]) and cell not in ((_NUM, 0), ("null", None)):
            return False
    return bool(counts) and all(counts)


def _key(row, columns, rule):
    return tuple(quantize_tie(row[i], rule["value_kinds"][i]) if _number(row[i]) else _norm(row[i])[1]
                 for i in columns)


def _blocks(rows, rule):
    order = rule.get("order_by", [])
    columns = [o["column"] for o in order]
    out, last, block = [], object(), -1
    for row in rows:
        key = _key(row, columns, rule)
        if key != last:
            block += 1
            last = key
        out.append(block)
    return out


def _selection_filter(candidate, reference, parts, rule):
    """Check chosen identities parent first; all ranking values come from the reference domain."""
    spec = rule["selection"]
    positions = {p.reference[0]: d for d, p in enumerate(parts) if len(p.reference) == 1}
    def identity_parts(cols):
        ordered = []
        for col in cols:
            for d, part in enumerate(parts):
                if col in part.reference and d not in ordered:
                    ordered.append(d)
        return [(d, parts[d]) for d in ordered]
    def cid(row, cols):
        return tuple(_canonical(row[d]) for d, p in identity_parts(cols))
    def rid(row, cols):
        values = []
        for d, part in identity_parts(cols):
            value = _get(row, part.reference, part.reverse if len(part.reference) == 2 else False)
            values.append(_norm(value, part.reference[0] in rule.get("identifier_columns", [])))
        return tuple(values)
    selected = []
    leaves = set(range(len(spec["stages"]))) - {s["parent"] for s in spec["stages"]}
    covered, allowed = set(), set()
    for index, stage in enumerate(spec["stages"]):
        identity_cols = stage["group_columns"] + stage["object_columns"]
        parent = stage["parent"]
        parent_cols = [] if parent is None else spec["stages"][parent]["group_columns"] + spec["stages"][parent]["object_columns"]
        domain = [(j, row) for j, row in enumerate(reference)
                  if all(row[c["column"]] == c["equals"] for c in stage["where"])
                  and (parent is None or rid(row, parent_cols) in selected[parent])]
        groups = defaultdict(dict)
        eligible = defaultdict(set)
        for j, row in domain:
            group, obj = rid(row, stage["group_columns"]), rid(row, stage["object_columns"])
            key = _key(row, [o["column"] for o in stage["order_by"]], rule)
            if any(v is None for v in key):
                raise ValueError("selection ranking keys must not be NULL")
            if obj in groups[group] and groups[group][obj] != key:
                raise ValueError("selection object has inconsistent ranking values")
            groups[group][obj] = key
            eligible[rid(row, identity_cols)].add(j)
        chosen = defaultdict(set)
        offered = []
        for j, row in enumerate(candidate):
            identity = cid(row, identity_cols)
            where_dims = [d for d, part in enumerate(parts)
                          if set(part.reference) & {c["column"] for c in stage["where"]}]
            if identity in eligible and any(
                all(_canonical(row[d]) == _norm(_get(reference[k], parts[d].reference,
                                        parts[d].reverse if len(parts[d].reference) == 2 else False),
                                    parts[d].reference[0] in rule.get("identifier_columns", []))
                    for d in where_dims) for k in eligible[identity]
            ):
                chosen[cid(row, stage["group_columns"])].add(cid(row, stage["object_columns"]))
                offered.append((j, identity))
        if set(chosen) != set(groups):
            return None
        members = set()
        for group, objects in groups.items():
            # Stable comparison also supports descending string keys.
            from functools import cmp_to_key
            def compare(a, b):
                for x, y, item in zip(objects[a], objects[b], stage["order_by"]):
                    if x != y:
                        return (-1 if x < y else 1) * (-1 if item["descending"] else 1)
                return 0
            ranked = sorted(objects, key=cmp_to_key(compare))
            count = min(stage["n"], len(ranked))
            boundary = objects[ranked[count - 1]]
            strict = {obj for obj in ranked if compare(obj, ranked[count - 1]) < 0}
            tied = {obj for obj in ranked if objects[obj] == boundary}
            if len(chosen[group]) != count or not strict <= chosen[group] or not chosen[group] <= strict | tied:
                return None
            members.update(group + obj for obj in chosen[group])
        selected.append(members)
        if index in leaves:
            identities = [identity for _, identity in offered]
            if len(identities) != len(set(identities)):
                return None
            covered.update(j for j, _ in offered)
            allowed.update(j for identity in members for j in eligible[identity])
    if covered != set(range(len(candidate))):
        return None
    return sorted(allowed)


def _rank_variants(candidate, reference, parts, rule):
    """Three whole-answer modes; position ranks checked by interval counts, never searched."""
    rankings = rule.get("rankings", [])
    if not rankings:
        yield candidate, reference, []
        return
    positions = {p.reference[0]: d for d, p in enumerate(parts) if len(p.reference) == 1}
    for style in ("competition", "dense", "position"):
        crows, rrows = list(candidate), list(reference)
        extra = []
        valid = True
        for ranking in rankings:
            col = ranking["column"]
            if col not in positions:
                continue
            d = positions[col]
            groups = ranking["group_columns"]
            if any(g not in positions for g in groups):
                raise ValueError("rank group columns must be required to count candidate ranks")
            blocks = {(tuple(_norm(v) for v in b["group"]), b["rank"]): b for b in ranking["blocks"]}
            by_group = defaultdict(list)
            for (group, _), block in blocks.items():
                by_group[group].append(block)
            for group in by_group:
                by_group[group].sort(key=lambda b: b["rank"])
            starts = {g: [b["rank"] for b in bs] for g, bs in by_group.items()}
            used = defaultdict(Counter)
            for i, row in enumerate(crows):
                group = tuple(_canonical(row[positions[g]]) for g in groups)
                value = row[d]
                if value[0] != _NUM or value[1] != int(value[1]):
                    valid = False
                    break
                rank = int(value[1])
                if style == "position":
                    index = bisect_right(starts.get(group, []), rank) - 1
                    if index < 0:
                        valid = False
                        break
                    b = by_group[group][index]
                    if rank >= b["rank"] + b["size"]:
                        valid = False
                        break
                    used[(group, b["rank"])][rank] += 1
                    crows[i] = row[:d] + ((_NUM, Decimal(b["rank"])),) + row[d + 1:]
            if style == "position":
                for (group, rank), counts in used.items():
                    size = sum(counts.values())
                    if set(counts.values()) != {1} or (ranking["prefix"] and set(counts) != set(range(rank, rank + size))):
                        valid = False
            if not valid:
                break
            if style == "dense":
                for i, row in enumerate(rrows):
                    group = tuple(_canonical(row[positions[g]]) for g in groups)
                    b = blocks.get((group, int(row[d][1])))
                    if b is None:
                        raise ValueError("rankings missing reference block")
                    rrows[i] = row[:d] + ((_NUM, Decimal(b["dense"])),) + row[d + 1:]
            extra.append(style)
        if valid:
            yield crows, rrows, extra


def _check_mapping(candidate, reference, parts, rule):
    c = _project(candidate, parts, True, rule)
    r = _project(reference, parts, False, rule)
    meta = _metadata(rule, parts, reference)
    dimensions = {p.reference[0]: d for d, p in enumerate(parts) if len(p.reference) == 1}
    swaps = []
    for pair in rule.get("unordered_pairs", []):
        both = [(left, right) for left, right in zip(pair["left"], pair["right"])
                if left in dimensions and right in dimensions]
        if both:
            swaps.append((tuple(dimensions[left] for left, _ in both), tuple(dimensions[right] for _, right in both)))
    active = list(range(len(reference)))
    top = rule.get("top_n")
    selection = rule.get("selection")
    if selection:
        active = _selection_filter(c, reference, parts, rule)
        if active is None:
            return "selection"
    optional_zero = top is None and not selection
    if optional_zero:
        c = [row for row in c if not _zero(row, parts, rule)]
        active = [i for i in active if not _zero(r[i], parts, rule)]
    r = [r[i] for i in active]
    raw = [reference[i] for i in active]
    if top is None and len(c) != len(r):
        return "values"
    strict_count = 0
    if top is not None:
        n = min(top, len(reference))
        if len(reference) < top:
            strict_count = len(reference)
        else:
            boundary = _key(reference[n - 1], rule["tie_columns"], rule)
            strict_count = next(i for i, row in enumerate(reference) if _key(row, rule["tie_columns"], rule) == boundary)
    reason = "values"
    for cv, rv, styles in _rank_variants(c, r, parts, rule):
        # Metadata for rank columns remains exact after transforming a whole-answer mode.
        mandatory = None if top is None else rv[:strict_count]
        if not _match(cv, rv, meta, mandatory, swaps):
            continue
        if not rule["ordered"]:
            return None
        blocks = _blocks(raw, rule)
        counts = Counter(blocks)
        expected = []
        remaining = len(cv)
        for block in dict.fromkeys(blocks):
            count = min(counts[block], remaining)
            expected.extend([block] * count)
            remaining -= count
        cm = [row + (("block", block),) for row, block in zip(cv, expected)]
        rm = [row + (("block", block),) for row, block in zip(rv, blocks)]
        mm = meta + [("other", True, None)]
        required = None if top is None else rm[:strict_count]
        if _match(cm, rm, mm, required, swaps):
            return None
        reason = "order"
    if rule.get("rankings") and reason == "values":
        rank_dims = {i for i, p in enumerate(parts) if p.reference[0] in rule.get("rank_columns", [])}
        if _match([tuple(x for d, x in enumerate(row) if d not in rank_dims) for row in c],
                  [tuple(x for d, x in enumerate(row) if d not in rank_dims) for row in r],
                  [m for d, m in enumerate(meta) if d not in rank_dims],
                  None if top is None else [tuple(x for d, x in enumerate(row) if d not in rank_dims) for row in r[:strict_count]]):
            return "rank"
    return reason


def _rank_marginal(candidate, reference, metadata, rule, column):
    blocks = [b for ranking in rule.get("rankings", []) if ranking["column"] == column for b in ranking["blocks"]]
    if not blocks:
        return _match(candidate, reference, metadata,
                      [] if rule.get("top_n") is not None or rule.get("selection") else None)
    counts = Counter()
    for (cell,) in candidate:
        if cell[0] != _NUM or cell[1] != int(cell[1]):
            return False
        counts[int(cell[1])] += 1
    competition, dense = Counter(), Counter()
    for block in blocks:
        competition[block["rank"]] += block["size"]
        dense[block["dense"]] += block["size"]
    starts = sorted(b["rank"] for b in blocks)
    ends = sorted(b["rank"] + b["size"] for b in blocks)
    # A necessary marginal only; whole-answer mode consistency is checked later.
    return all(max(competition[value], dense[value],
                   bisect_right(starts, value) - bisect_right(ends, value)) >= count
               for value, count in counts.items())


def _mappings(candidate, reference, rule, required):
    """Exact-cover column correspondence after marginal multiset feasibility filtering."""
    width = len(candidate[0]) if candidate else 0
    required = tuple(sorted(required))
    cache = {}
    pairs = rule.get("unordered_pairs", [])
    no_join = set(rule.get("identifier_columns", [])) | set(rule.get("rank_columns", []))
    no_join.update(i for pair in pairs for i in pair["left"] + pair["right"])
    zeros = rule.get("top_n") is None and not rule.get("selection") and any(rule["value_kinds"][i] == "count" for i in required)
    reference_optional = _reference_zero_flags(reference, rule, required) if zeros else []
    candidate_optional = [any(_number(v) and v == 0 for v in row) for row in candidate] if zeros else []
    # Pair orientation is checked per row by the indexed matcher.
    def options(col):
        if col in cache:
            return cache[col]
        groups = [(col,)]
        if col not in no_join and col + 1 not in no_join and col + 1 in required and _string_column(rule, col) and _string_column(rule, col + 1):
            groups.append((col, col + 1))
        out = []
        for group in groups:
            for j in range(width):
                choices = [(j,)]
                if col not in no_join and len(group) == 1 and _string_column(rule, col) and j + 1 < width and all(isinstance(row[j], str) and isinstance(row[j + 1], str) for row in candidate):
                    choices.append((j, j + 1))
                for cols in choices:
                    for reverse in ((False, True) if len(group) == 2 or len(cols) == 2 else (False,)):
                        part = Part(group, cols, reverse)
                        if (len(group) == 1 and col not in rule.get("identifier_columns", [])
                                and is_numeric_type(rule["value_types"][col])
                                and all(row[col] is None or _number(row[col]) for row in reference)
                                and any(_get(row, cols) is not None and not _number(_get(row, cols)) for row in candidate)):
                            continue
                        cp = _project(candidate, [part], True, rule)
                        rp = _project(reference, [part], False, rule)
                        meta = _metadata(rule, [part], reference)
                        # Rank representations and optional zero rows change column marginals.
                        # Pair orientation is per-row; a separate union marginal is required.
                        paired = next((p for p in pairs if col in p["left"] + p["right"]), None)
                        if col in rule.get("rank_columns", []) and any(r["column"] == col for r in rule.get("rankings", [])):
                            feasible = _rank_marginal(cp, rp, meta, rule, col)
                        elif paired:
                            partners = dict(zip(paired["left"], paired["right"]))
                            partners.update(zip(paired["right"], paired["left"]))
                            alternate = tuple(partners.get(i, i) for i in group)
                            alternate_rows = [(_norm(_get(row, alternate, reverse), col in rule.get("identifier_columns", [])),) for row in reference]
                            feasible = _match(cp, rp + alternate_rows, meta, [])
                        elif zeros:
                            feasible = _cover_required(cp, rp, meta,
                                [row for row, optional in zip(cp, candidate_optional) if not optional],
                                [row for row, optional in zip(rp, reference_optional) if not optional])
                        elif rule.get("top_n") is not None or rule.get("selection"):
                            feasible = _match(cp, rp, meta, [])
                        else:
                            feasible = _match(cp, rp, meta)
                        if feasible:
                            out.append(part)
        cache[col] = out
        return out
    feasibility = {}
    def can_cover(remaining, used):
        state = (frozenset(remaining), frozenset(used))
        if state in feasibility:
            return feasibility[state]
        choices = [part for col in sorted(remaining) for part in options(col)
                   if set(part.reference) <= remaining and not used & set(part.candidate)]
        covered = {i for part in choices for i in part.reference}
        available = {i for part in choices for i in part.candidate}
        merges = {part.reference for part in choices if len(part.reference) == 2}
        paired, saving = set(), 0
        for pair in sorted(merges):
            if not paired & set(pair):
                paired.update(pair)
                saving += 1
        possible = covered == remaining and len(available) >= len(remaining) - saving
        if possible and not merges:
            # Hall feasibility prunes dead column assignments before enumerating
            # complete correspondences. Two-column candidate joins are relaxed
            # to either constituent here, so this cannot reject a real solution.
            rcols, ccols = sorted(remaining), sorted(available)
            ri = {v:i for i,v in enumerate(rcols)}
            ci = {v:len(rcols)+i for i,v in enumerate(ccols)}
            source = len(rcols)+len(ccols)
            sink = source+1
            flow = _Flow(sink+1)
            for col in rcols:
                flow.edge(source, ri[col], 1)
            for col in ccols:
                flow.edge(ci[col], sink, 1)
            for col in rcols:
                for target in sorted({j for part in choices if part.reference == (col,) for j in part.candidate}):
                    flow.edge(ri[col], ci[target], 1)
            possible = flow.augment(source,sink) == len(rcols)
        if len(feasibility) < 4096:
            feasibility[state] = possible
        return possible
    def visit(remaining, used, parts):
        if not remaining:
            yield tuple(parts)
            return
        if not can_cover(remaining, used):
            return
        col = min(remaining)
        for part in options(col):
            if not set(part.reference) <= remaining or used & set(part.candidate):
                continue
            yield from visit(remaining - set(part.reference), used | set(part.candidate), parts + [part])
    yield from visit(set(required), set(), [])


def _one(candidate, reference, rule, required):
    top = rule.get("top_n")
    if not reference:
        return ScoreResult("correct") if not candidate else ScoreResult("wrong", "row_count")
    if top is not None and len(candidate) != min(top, len(reference)):
        return ScoreResult("wrong", "top_n_full_group" if len(candidate) == len(reference) > top else "row_count")
    zeros = top is None and not rule.get("selection") and any(rule["value_kinds"][i] == "count" for i in required)
    if not zeros and not rule.get("selection") and top is None and len(candidate) != len(reference):
        return ScoreResult("wrong", "row_count")
    if zeros and len(candidate) < len(reference):
        if len(candidate) < sum(not optional for optional in _reference_zero_flags(reference, rule, required)):
            return ScoreResult("wrong", "row_count")
    if not candidate and not reference:
        return ScoreResult("correct")
    minimum, i = 0, 0
    no_join = set(rule.get("identifier_columns", [])) | set(rule.get("rank_columns", []))
    no_join.update(i for pair in rule.get("unordered_pairs", []) for i in pair["left"] + pair["right"])
    ordered_required = sorted(required)
    while i < len(ordered_required):
        col = ordered_required[i]
        i += 1
        if col not in no_join and col + 1 not in no_join and i < len(ordered_required) and ordered_required[i] == col + 1 and _string_column(rule, col) and _string_column(rule, col + 1):
            i += 1
        minimum += 1
    if candidate and len(candidate[0]) < minimum:
        return ScoreResult("wrong", "missing_columns")
    if not candidate:
        dummy = tuple(Part((col,), (col,)) for col in required)
        projected = _project(reference, dummy, False, rule)
        return ScoreResult("correct") if zeros and all(_zero(row, dummy, rule) for row in projected) else ScoreResult("wrong", "row_count")
    # A direct correspondence can be proved by lossless full-row hashes without
    # constructing per-column indexes. A miss is not a rejection.
    if (not rule["ordered"] and top is None and not rule.get("selection") and not rule.get("rankings")
            and candidate and max(required) < len(candidate[0])):
        identifiers = set(rule.get("identifier_columns", []))
        def lossless(rows):
            return Counter(tuple(_norm(row[col], col in identifiers) for col in required) for row in rows)
        if lossless(candidate) == lossless(reference):
            return ScoreResult("correct")
    reason = "values"
    for count, parts in enumerate(_mappings(candidate, reference, rule, required)):
        if count == CAP:
            return ScoreResult("unscored", "mapping_cap")
        failure = _check_mapping(candidate, reference, parts, rule)
        if failure is None:
            return ScoreResult("correct")
        priority = {"values": 0, "order": 1, "selection": 2, "rank": 3}
        if priority.get(failure, 0) > priority[reason]:
            reason = failure
    if reason == "values" and rule.get("rankings"):
        nonrank = tuple(i for i in required if i not in rule.get("rank_columns", []))
        if nonrank:
            projected_rule = {**rule, "required_columns": list(nonrank), "rankings": []}
            if _one(candidate, reference, projected_rule, nonrank).outcome == "correct":
                reason = "rank"
        else:
            reason = "rank"
    return ScoreResult("wrong", reason)


def score(
    candidate_rows: Rows | str | ExecError,
    refs: Sequence[Rows],
    rules: Mapping[str, object],
    *,
    reference_rules: Sequence[Mapping[str, object] | None] | None = None,
) -> Outcome:
    return score_detailed(candidate_rows, refs, rules, reference_rules=reference_rules).outcome


def score_detailed(
    candidate_rows: Rows | str | ExecError,
    refs: Sequence[Rows],
    rules: Mapping[str, object],
    *,
    reference_rules: Sequence[Mapping[str, object] | None] | None = None,
) -> ScoreResult:
    if not refs:
        raise ValueError("refs must contain at least one result set")
    if reference_rules is not None and len(reference_rules) != len(refs):
        raise ValueError("reference_rules must align with refs")
    effective = [rules if reference_rules is None or reference_rules[i] is None else reference_rules[i] for i in range(len(refs))]
    validated = [_validate(rule, _rows(ref)) for rule, ref in zip(effective, refs)]
    if isinstance(candidate_rows, ExecError):
        return ScoreResult("exec_error", candidate_rows.message)
    if isinstance(candidate_rows, str):
        if candidate_rows.strip() != REFUSAL:
            raise TypeError("candidate string must be CANNOT_ANSWER")
        return ScoreResult("refused")
    candidate = _rows(candidate_rows)
    results = []
    for i, (ref, rule, required) in enumerate(zip(refs, effective, validated)):
        result = _one(candidate, ref, rule, required)
        if result.outcome == "correct":
            return ScoreResult("correct", matched_ref=i)
        results.append(result)
    return next((r for r in results if r.outcome == "unscored"), results[0])


def diagnose_sensitivity(candidate_rows, refs, rules, *, reference_rules=None, time_limit=2.0):
    """Bounded numeric-projection diagnosis; never invoked by score or score_detailed."""
    # A process boundary provides an actual time limit, including mapping and matching.
    from multiprocessing import get_context
    if time_limit <= 0:
        return "not_diagnosed"
    context = get_context("fork")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=_diagnose_worker, args=(send, candidate_rows, refs, rules, reference_rules))
    process.start()
    send.close()
    try:
        if receive.poll(time_limit):
            result = receive.recv()
            if isinstance(result, Exception):
                raise result
            return result
        return "not_diagnosed"
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        receive.close()


def _diagnose_worker(send, candidate, refs, rules, reference_rules):
    try:
        if isinstance(candidate, (str, ExecError)):
            send.send("structure_mismatch")
            return
        projected_rules = []
        for i, ref in enumerate(refs):
            rule = rules if reference_rules is None or reference_rules[i] is None else reference_rules[i]
            if rule.get("selection"):
                send.send("structure_mismatch")
                return
            numeric = [j for j in rule["required_columns"] if is_numeric_type(rule["value_types"][j])]
            if not numeric:
                send.send("no_numeric_reference")
                return
            projected_rules.append({**rule, "required_columns": numeric})
        result = score(candidate, refs, rules, reference_rules=projected_rules)
        send.send("string_or_label_only" if result == "correct" else "not_diagnosed" if result == "unscored" else "numeric_mismatch")
    except Exception as error:
        send.send(error)
    finally:
        send.close()
