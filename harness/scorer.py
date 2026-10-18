"""Deterministic result-set scorer.

The scorer is deliberately independent of query execution.  The harness passes
one of three candidate states: rows, ``CANNOT_ANSWER``, or :class:`ExecError`.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time
import warnings
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from itertools import permutations, product
from numbers import Number
from typing import Literal, TypeAlias

from harness.selection import complete_selection, identity, matches_selection, validate_selection
from harness.value_units import KINDS, ValueKind, absolute_tolerance, is_integer_type, quantize_tie


Outcome: TypeAlias = Literal["correct", "wrong", "exec_error", "refused"]
Sensitivity: TypeAlias = Literal[
    "string_or_label_only", "numeric_mismatch", "structure_mismatch", "no_numeric_reference"
]
Cell: TypeAlias = object
Row: TypeAlias = tuple[Cell, ...]
Rows: TypeAlias = tuple[Row, ...]

RELATIVE_TOLERANCE = 0.005
REFUSAL = "CANNOT_ANSWER"
BOUNDARY_TIE_FULL_GROUP = "boundary_tie_full_group"


@dataclass(frozen=True)
class ExecError:
    """An execution failure passed through with its original message."""

    message: str

    def __post_init__(self) -> None:
        if not self.message:
            raise ValueError("ExecError.message must not be empty")


@dataclass(frozen=True)
class ScoreResult:
    """Detailed score used by reporting while ``score`` keeps the card API."""

    outcome: Outcome
    reason: str | None = None
    matched_ref: int | None = None
    sensitivity: Sensitivity | None = None


@dataclass(frozen=True)
class _Rules:
    ordered: bool
    top_n: int | None
    tie_columns: tuple[int, ...]
    value_kinds: tuple[ValueKind, ...] = ()
    use_absolute_tolerance: bool = True
    exact_counts: bool = True
    value_types: tuple[str, ...] = ()
    selection: Mapping[str, object] | None = None
    order_by: tuple[tuple[int, bool], ...] = ()
    required_columns: tuple[int, ...] | None = None
    label_values: tuple[frozenset[str] | None, ...] = ()
    unordered_pairs: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...] = ()


def score(
    candidate_rows: Sequence[Sequence[Cell]] | str | ExecError,
    refs: Sequence[Sequence[Sequence[Cell]]],
    rules: Mapping[str, object],
    *,
    reference_rules: Sequence[Mapping[str, object] | None] | None = None,
) -> Outcome:
    """Return one of the four outcomes required by the frozen scoring rules."""

    return score_detailed(candidate_rows, refs, rules, reference_rules=reference_rules).outcome


def score_detailed(
    candidate_rows: Sequence[Sequence[Cell]] | str | ExecError,
    refs: Sequence[Sequence[Sequence[Cell]]],
    rules: Mapping[str, object],
    *,
    reference_rules: Sequence[Mapping[str, object] | None] | None = None,
) -> ScoreResult:
    """Score a candidate and retain a stable diagnostic reason.

    ``refs`` is a sequence of acceptable result sets.  For Top-N questions, a
    reference must contain the strict prefix followed by the complete boundary
    tie group; it must never be truncated to N rows. ``required_columns`` lists
    zero-based reference columns to compare (nonempty, unique indexes). Hidden
    columns remain available to reference-side ordering and selection. Missing
    metadata warns and requires every reference column.
    """

    if reference_rules is not None:
        if isinstance(reference_rules, (str, bytes)) or not isinstance(reference_rules, Sequence) or len(reference_rules) != len(refs):
            raise ValueError("reference_rules must align with refs")
        if any(item is not None and not isinstance(item, Mapping) for item in reference_rules):
            raise TypeError("reference_rules entries must be mappings or None")
    parsed_rules = tuple(_parse_rules(reference_rules[i] if reference_rules is not None and reference_rules[i] is not None else rules) for i in range(len(refs)))
    if isinstance(candidate_rows, ExecError):
        return ScoreResult("exec_error", candidate_rows.message)
    if isinstance(candidate_rows, str):
        if candidate_rows.strip() == REFUSAL:
            return ScoreResult("refused")
        raise TypeError(f"candidate_rows string must be {REFUSAL!r}")

    candidate = _coerce_rows(candidate_rows, "candidate_rows")
    references = tuple(_coerce_rows(ref, f"refs[{index}]") for index, ref in enumerate(refs))
    if not references:
        raise ValueError("refs must contain at least one acceptable result set")

    mismatch_reasons: list[str] = []
    for index, reference in enumerate(references):
        matched, reason = _matches_reference(candidate, reference, parsed_rules[index])
        if matched:
            return ScoreResult("correct", matched_ref=index)
        mismatch_reasons.append(reason)

    if BOUNDARY_TIE_FULL_GROUP in mismatch_reasons:
        return ScoreResult("wrong", BOUNDARY_TIE_FULL_GROUP, sensitivity="structure_mismatch")
    sensitivities = [_sensitivity(candidate, (reference,), rule) for reference, rule in zip(references, parsed_rules, strict=True)]
    sensitivity = next((kind for kind in ("string_or_label_only", "numeric_mismatch", "no_numeric_reference") if kind in sensitivities), "structure_mismatch")
    return ScoreResult("wrong", mismatch_reasons[0], sensitivity=sensitivity)


def _sensitivity(candidate: Rows, references: tuple[Rows, ...], rules: _Rules) -> Sensitivity:
    """Numeric projection is a reporting diagnostic, never a second verdict.

    Keep row multiplicities, numeric NULLs, order, and Top-N constraints. Missing
    numeric columns remain failures; extra candidate columns are still allowed.
    """
    if rules.selection is not None:
        return "structure_mismatch"
    if not candidate or not any(references):
        return "structure_mismatch"
    expected_counts = {rules.top_n if rules.top_n is not None else len(ref) for ref in references}
    if len(candidate) not in expected_counts:
        return "structure_mismatch"
    saw_numeric = False
    for reference in references:
        if not reference:
            continue
        numeric_ref = tuple(i for i in _comparison_columns(reference[0], rules) if any(_is_numeric(row[i]) for row in reference))
        numeric_candidate = tuple(i for i in range(len(candidate[0])) if any(_is_numeric(row[i]) for row in candidate))
        if not numeric_ref:
            continue
        saw_numeric = True
        if len(numeric_candidate) < len(numeric_ref):
            continue
        if rules.required_columns is None and any(i not in numeric_ref for i in rules.tie_columns):
            continue
        # Keep original reference columns for hidden order and boundary keys.
        projected_rules = replace(rules, required_columns=numeric_ref)
        projected_candidate = tuple(tuple(row[i] for i in numeric_candidate) for row in candidate)
        projected_reference = reference
        if rules.required_columns is None:
            # Missing metadata retains the previous diagnostic projection too.
            projected_order = tuple((numeric_ref.index(i), descending) for i, descending in rules.order_by) if all(i in numeric_ref for i, _ in rules.order_by) else ()
            projected_rules = _Rules(rules.ordered, rules.top_n, tuple(numeric_ref.index(i) for i in rules.tie_columns), tuple(rules.value_kinds[i] for i in numeric_ref) if rules.value_kinds else (), rules.use_absolute_tolerance, rules.exact_counts, tuple(rules.value_types[i] for i in numeric_ref) if rules.value_types else (), order_by=projected_order)
            projected_reference = tuple(tuple(row[i] for i in numeric_ref) for row in reference)
        if _exact_projection_matches(projected_candidate, projected_reference, projected_rules):
            return "string_or_label_only"
        matched, _ = _matches_reference(projected_candidate, projected_reference, projected_rules)
        if matched:
            return "string_or_label_only"
    if not saw_numeric:
        return "no_numeric_reference"
    return "numeric_mismatch"


def _exact_projection_matches(candidate: Rows, reference: Rows, rules: _Rules) -> bool:
    """Prove an exact diagnostic match; otherwise retain the tolerant matcher."""
    if rules.top_n is not None:
        return False

    def key(value: Cell) -> object:
        # Preserve numeric/non-numeric buckets: bool must not hash as 0/1.
        # Unsupported objects and non-finite values keep their original path.
        if type(value) not in (int, float, Decimal, str, bool, type(None)):
            raise TypeError
        if _is_numeric(value):
            if not math.isfinite(float(value)):
                raise ValueError
            return value
        return _nonnumeric_bucket(value)

    try:
        columns = _comparison_columns(reference[0], rules)
        rows = (tuple(key(row[i]) for i in columns) for row in reference)
        expected = tuple(rows) if rules.ordered else Counter(rows)
        for mapping in permutations(range(len(candidate[0])), len(_comparison_columns(reference[0], rules))):
            projected = (tuple(key(row[i]) for i in mapping) for row in candidate)
            if rules.ordered and rules.order_by:
                actual = tuple(projected)
                exact = all(Counter(actual[start:end]) == Counter(expected[start:end])
                            for start, end in _ordered_blocks(reference, rules))
            else:
                exact = (tuple(projected) if rules.ordered else Counter(projected)) == expected
            if exact:
                return True
    except (TypeError, ValueError, OverflowError):
        return False
    return False


def _parse_rules(rules: Mapping[str, object]) -> _Rules:
    if not isinstance(rules, Mapping):
        raise TypeError("rules must be a mapping")
    missing = {"ordered", "top_n"} - rules.keys()
    if missing:
        raise ValueError(f"rules missing required fields: {sorted(missing)}")

    ordered = rules["ordered"]
    top_n = rules["top_n"]
    tie_columns = rules.get("tie_columns", ())
    if not isinstance(ordered, bool):
        raise TypeError("rules['ordered'] must be bool")
    if top_n is not None and (isinstance(top_n, bool) or not isinstance(top_n, int) or top_n <= 0):
        raise ValueError("rules['top_n'] must be None or a positive integer")
    if top_n is not None and not ordered:
        raise ValueError("Top-N rules must also set ordered=true")
    if isinstance(tie_columns, (str, bytes)) or not isinstance(tie_columns, Sequence):
        raise TypeError("rules['tie_columns'] must be a sequence of column indexes")
    if any(isinstance(column, bool) or not isinstance(column, int) or column < 0 for column in tie_columns):
        raise ValueError("rules['tie_columns'] must contain non-negative integers")
    if len(set(tie_columns)) != len(tie_columns):
        raise ValueError("rules['tie_columns'] must not contain duplicates")
    value_kinds = rules.get("value_kinds", ())
    if isinstance(value_kinds, (str, bytes)) or not isinstance(value_kinds, Sequence) or any(k not in KINDS for k in value_kinds):
        raise ValueError("value_kinds must be a sequence of supported reference-column kinds")
    use_absolute = rules.get("use_absolute_tolerance", True)
    exact_counts = rules.get("exact_counts", True)
    if not isinstance(use_absolute, bool) or not isinstance(exact_counts, bool):
        raise TypeError("comparison mode flags must be bool")
    value_types = rules.get("value_types", ())
    if isinstance(value_types, (str, bytes)) or not isinstance(value_types, Sequence) or any(not isinstance(t, str) or not t.strip() for t in value_types):
        raise ValueError("value_types must be a sequence of reference return-type strings")
    selection = rules.get("selection")
    if selection is not None:
        if top_n is not None or tie_columns:
            raise ValueError("selection cannot be combined with flat top_n/tie_columns")
        if not value_kinds or len(value_types) != len(value_kinds):
            raise ValueError("selection requires complete value_kinds and value_types")
        validate_selection(selection, len(value_kinds), ordered=ordered)
    order_by = rules.get("order_by")
    if order_by is None and selection is not None and selection["output_order"]:
        order_by = selection["output_order"]  # Already explicit reference metadata.
    if order_by is not None:
        if not ordered or not isinstance(order_by, list) or not order_by:
            raise ValueError("order_by requires ordered=true and a nonempty list")
        for item in order_by:
            if not isinstance(item, Mapping) or set(item) != {"column", "descending"} or type(item["column"]) is not int or item["column"] < 0 or type(item["descending"]) is not bool:
                raise ValueError("order_by requires nonnegative column and boolean descending")
        positions = [item["column"] for item in order_by]
        if len(set(positions)) != len(positions) or (value_kinds and any(i >= len(value_kinds) for i in positions)) or (value_types and any(i >= len(value_types) for i in positions)):
            raise ValueError("order_by columns must be unique reference positions")
        if selection is not None and order_by != selection["output_order"]:
            raise ValueError("order_by must agree with selection.output_order")
    elif ordered:
        warnings.warn("ordered rules missing order_by; retaining positional comparison", RuntimeWarning, stacklevel=3)
    required_columns = rules.get("required_columns")
    if "required_columns" not in rules:
        warnings.warn("rules missing required_columns; treating all reference columns as required", RuntimeWarning, stacklevel=3)
    elif (isinstance(required_columns, (str, bytes)) or not isinstance(required_columns, Sequence)
          or not required_columns or any(type(i) is not int or i < 0 for i in required_columns)
          or len(set(required_columns)) != len(required_columns)):
        raise ValueError("required_columns must be a nonempty sequence of unique nonnegative column indexes")
    if required_columns is not None:
        for metadata in (value_kinds, value_types):
            if metadata and any(i >= len(metadata) for i in required_columns):
                raise ValueError("required_columns contains an index outside reference metadata")
    unordered_pairs = rules.get("unordered_pairs", [])
    if not isinstance(unordered_pairs, list):
        raise ValueError("unordered_pairs must be a list of left/right column groups")
    parsed_pairs = []
    seen_pair_columns = set()
    for pair in unordered_pairs:
        if not isinstance(pair, Mapping) or set(pair) != {"left", "right"}:
            raise ValueError("unordered_pairs entries require left and right")
        left, right = pair["left"], pair["right"]
        if (not isinstance(left, list) or not isinstance(right, list) or not left or len(left) != len(right)
                or any(type(i) is not int or i < 0 for i in left + right)
                or len(set(left + right)) != len(left + right)
                or seen_pair_columns.intersection(left + right)):
            raise ValueError("unordered_pairs requires disjoint equal-width nonempty column groups")
        for metadata in (value_kinds, value_types):
            if metadata and max(left + right) >= len(metadata):
                raise ValueError("unordered_pairs contains an index outside reference metadata")
        if required_columns is not None:
            if any((a in required_columns) != (b in required_columns) for a,b in zip(left,right)):
                raise ValueError("unordered_pairs requires both sides of each compared attribute")
        seen_pair_columns.update(left + right)
        parsed_pairs.append((tuple(left), tuple(right)))
    parsed_order = tuple((item["column"], item["descending"]) for item in order_by or ())
    return _Rules(ordered, top_n, tuple(tie_columns), tuple(value_kinds), use_absolute, exact_counts, tuple(value_types), selection, parsed_order, tuple(required_columns) if required_columns is not None else None, unordered_pairs=tuple(parsed_pairs))


def _coerce_rows(rows: Sequence[Sequence[Cell]], name: str) -> Rows:
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise TypeError(f"{name} must be a sequence of rows")

    result: list[Row] = []
    width: int | None = None
    for index, row in enumerate(rows):
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence):
            raise TypeError(f"{name}[{index}] must be a sequence of cells")
        converted = tuple(row)
        if width is None:
            width = len(converted)
        elif len(converted) != width:
            raise ValueError(f"{name} must be rectangular")
        result.append(converted)
    return tuple(result)


def _comparison_columns(row: Row, rules: _Rules) -> tuple[int, ...]:
    return rules.required_columns if rules.required_columns is not None else tuple(range(len(row)))


def _reference_labels(reference: Rows, rules: _Rules) -> _Rules:
    if not reference:
        return rules
    labels = []
    for i in range(len(reference[0])):
        values = [row[i] for row in reference]
        is_string = ("String" in rules.value_types[i] if rules.value_types else any(isinstance(v, str) for v in values))
        wildcard = is_string and any(v is None or isinstance(v, str) and not v.strip() for v in values)
        labels.append(frozenset(v.strip() for v in values if isinstance(v, str) and v.strip()) if wildcard else None)
    return replace(rules, label_values=tuple(labels))


def _label_matches(value: Cell, expected: Cell, column: int, rules: _Rules) -> bool:
    labels = rules.label_values[column] if rules.label_values else None
    return (labels is not None and (expected is None or isinstance(expected, str) and not expected.strip())
            and isinstance(value, str) and value.strip() not in labels)


def _candidate_forms(candidate: Rows, minimum_width: int) -> Iterator[Rows]:
    yield candidate
    if not candidate or len(candidate[0]) <= minimum_width:
        return
    # Collapse original adjacent string columns, without reusing either column.
    def forms(start: int, columns: list[tuple[int, ...]]) -> Iterator[Rows]:
        width = len(candidate[0])
        if start == width:
            if any(len(c) == 2 for c in columns) and len(columns) >= minimum_width:
                yield tuple(tuple(" ".join(row[i].strip() for i in col) if len(col) == 2 else row[col[0]] for col in columns) for row in candidate)
            return
        yield from forms(start + 1, columns + [(start,)])
        if start + 1 < width and all(isinstance(row[start], str) and isinstance(row[start+1], str) for row in candidate):
            yield from forms(start + 2, columns + [(start, start + 1)])
    yield from forms(0, [])


def _matches_reference(candidate: Rows, reference: Rows, rules: _Rules) -> tuple[bool, str]:
    # Validate column indexes/metadata before constructing reference label context.
    if reference and rules.value_types and len(rules.value_types) != len(reference[0]):
        raise ValueError("value_types must match reference column count")
    rules = _reference_labels(reference, rules)
    first_reason = None
    minimum = len(_comparison_columns(reference[0], rules)) if reference else 0
    for form in _candidate_forms(candidate, minimum):
        matched, reason = _matches_reference_core(form, reference, rules)
        if matched:
            return True, reason
        if first_reason is None:
            first_reason = reason
    return False, first_reason


def _matches_reference_core(candidate: Rows, reference: Rows, rules: _Rules, fixed_mapping: tuple[int, ...] | None = None) -> tuple[bool, str]:
    if rules.value_kinds and reference and len(rules.value_kinds) != len(reference[0]):
        raise ValueError("value_kinds must match reference column count")
    if rules.value_types and reference and len(rules.value_types) != len(reference[0]):
        raise ValueError("value_types must match reference column count")
    if reference and any(i >= len(reference[0]) for i, _ in rules.order_by):
        raise ValueError("order_by contains an index outside the reference rows")
    if reference and rules.required_columns is not None and any(i >= len(reference[0]) for i in rules.required_columns):
        raise ValueError("required_columns contains an index outside the reference rows")
    if reference and any(i >= len(reference[0]) for pair in rules.unordered_pairs for side in pair for i in side):
        raise ValueError("unordered_pairs contains an index outside reference rows")
    if rules.selection is not None:
        complete, _ = complete_selection(list(reference), rules.selection, rules.value_kinds)
        if len(complete) != len(reference):
            raise ValueError("selection reference contains rows below a boundary")
        return _matches_selection_reference(candidate, reference, rules)
    if rules.top_n is None:
        if len(candidate) != len(reference):
            return False, "row_count"
    else:
        top_error = _validate_top_reference(reference, rules)
        if top_error:
            raise ValueError(top_error)
        if len(candidate) != rules.top_n:
            if _is_complete_boundary_group(candidate, reference, rules):
                return False, BOUNDARY_TIE_FULL_GROUP
            return False, "top_n_row_count"

    if not candidate and not reference:
        return True, "matched"
    if not candidate or not reference:
        return False, "row_count"

    candidate_width = len(candidate[0])
    reference_width = len(_comparison_columns(reference[0], rules))
    if candidate_width < reference_width:
        return False, "missing_columns"

    # A flat reference consumes every row. None only matches None under the
    # scalar comparator, regardless of column permutations or extra columns.
    # Top-N may leave nullable boundary members unselected, so exclude it.
    if (rules.top_n is None
            and any(row[i] is None and (not rules.label_values or rules.label_values[i] is None) for row in reference for i in _comparison_columns(row, rules))
            and not any(cell is None for row in candidate for cell in row)
            and all(type(cell) in (str, bool, int, float, Decimal, list, tuple, dict, bytes)
                    for row in candidate for cell in row)):
        return False, "values"

    for mapping in (permutations(range(candidate_width), reference_width) if fixed_mapping is None else (fixed_mapping,)):
        if rules.top_n is not None:
            if _top_rows_match(candidate, reference, mapping, rules):
                return True, "matched"
        elif rules.ordered:
            if _ordered_rows_match(candidate, reference, mapping, rules):
                return True, "matched"
        elif _rows_match_unordered(candidate, reference, mapping, rules):
            return True, "matched"
    return False, "values"


def _ordered_blocks(reference: Rows, rules: _Rules) -> Iterator[tuple[int, int]]:
    """Contiguous equal reference keys; result tolerance never defines a block."""
    start = 0
    previous = None
    for index, row in enumerate(reference):
        key = tuple(quantize_tie(row[i], rules.value_kinds[i] if rules.value_kinds else "other") for i, _ in rules.order_by)
        if index and key != previous:
            yield start, index
            start = index
        previous = key
    if reference:
        yield start, len(reference)


def _ordered_rows_match(candidate: Rows, reference: Rows, mapping: tuple[int, ...], rules: _Rules) -> bool:
    if not rules.order_by:
        return all(_rows_equal(a, b, mapping, rules) for a, b in zip(candidate, reference))
    for start, end in _ordered_blocks(reference, rules):
        # Retain every old positional match, including custom scalar equality.
        if all(_rows_equal(a, b, mapping, rules) for a, b in zip(candidate[start:end], reference[start:end])):
            continue
        if end - start == 1 or not _rows_match_unordered(candidate[start:end], reference[start:end], mapping, rules):
            return False
    return True


def _matches_selection_reference(candidate: Rows, reference: Rows, rules: _Rules) -> tuple[bool, str]:
    if not reference:
        return (not candidate, "matched" if not candidate else "selection_group_coverage")
    if not candidate:
        return False, "selection_group_coverage"
    if len(candidate[0]) < len(_comparison_columns(reference[0], rules)):
        return False, "missing_columns"
    spec = rules.selection
    stages = spec["stages"]
    identity_columns = sorted({column for stage in stages for column in stage["group_columns"] + stage["object_columns"] + [condition["column"] for condition in stage["where"]]})
    indexed = defaultdict(list)
    for row in reference:
        indexed[identity(row, identity_columns)].append(row)
    parents = {stage["parent"] for stage in stages}
    for index, stage in enumerate(stages):
        if index in parents:
            continue
        identities = [identity(row, stage["group_columns"] + stage["object_columns"]) for row in reference if all(row[c["column"]] == c["equals"] for c in stage["where"])]
        if len(identities) != len(set(identities)):
            raise ValueError("selection reference contains duplicate leaf objects")
    if (rules.required_columns is not None and len(rules.required_columns) < len(reference[0])) or any(v is not None for v in rules.label_values):
        # Recover complete reference rows before validating group/Top-N coverage.
        # Hidden selection keys must never be invented from candidate values.
        columns = _comparison_columns(reference[0], rules)
        visible_identity = [i for i in identity_columns if i in columns]
        reason = "selection_values"
        for mapping in permutations(range(len(candidate[0])), len(columns)):
            candidate_identity = [mapping[columns.index(i)] for i in visible_identity]
            choices = [tuple(ref for ref in reference
                             if all(identity(row, [c]) == identity(ref, [i]) or _label_matches(row[c], ref[i], i, rules) for c,i in zip(candidate_identity,visible_identity))
                             and _rows_equal(row, ref, mapping, rules)) for row in candidate]
            if not all(choices):
                continue
            for matched in product(*choices):
                valid, reason = matches_selection(matched, reference, spec, rules.value_kinds)
                if valid:
                    return True, "matched"
        return False, reason
    reason = "selection_values"
    for mapping in permutations(range(len(candidate[0])), len(_comparison_columns(reference[0], rules))):
        projected = [tuple(row[mapping[_comparison_columns(reference[0], rules).index(i)]] for i in range(len(reference[0]))) for row in candidate]
        matched = []
        for row in projected:
            choices = indexed.get(identity(row, identity_columns), ())
            match = next((ref for ref in choices if _rows_equal(row, ref, _comparison_columns(ref, rules), rules)), None)
            if match is None:
                break
            matched.append(match)
        else:
            valid, reason = matches_selection(matched, reference, spec, rules.value_kinds)
            if valid:
                return True, "matched"
    return False, reason


def _validate_top_reference(reference: Rows, rules: _Rules) -> str | None:
    assert rules.top_n is not None
    if len(reference) < rules.top_n:
        return "Top-N reference contains fewer than N rows"
    if len(reference) == rules.top_n:
        return None
    if not rules.tie_columns:
        return "Top-N reference with boundary ties requires tie_columns"
    width = len(reference[0]) if reference else 0
    if any(column >= width for column in rules.tie_columns):
        return "tie_columns contains an index outside the reference rows"

    boundary = reference[rules.top_n - 1]
    for row in reference[rules.top_n :]:
        if not _tie_keys_equal(row, boundary, rules.tie_columns, rules.value_kinds):
            return "Top-N reference contains rows below the complete boundary tie group"
    return None


def _top_rows_match(
    candidate: Rows,
    reference: Rows,
    mapping: tuple[int, ...],
    rules: _Rules,
) -> bool:
    assert rules.top_n is not None
    if len(reference) == rules.top_n:
        return _ordered_rows_match(candidate, reference, mapping, rules)

    boundary_start = _boundary_start(reference, rules.top_n, rules.tie_columns, rules.value_kinds)
    if not _ordered_rows_match(candidate[:boundary_start], reference[:boundary_start], mapping, rules):
        return False
    return _rows_match_subset(
        candidate[boundary_start:],
        reference[boundary_start:],
        mapping,
        rules,
    )


def _is_complete_boundary_group(candidate: Rows, reference: Rows, rules: _Rules) -> bool:
    assert rules.top_n is not None
    if len(reference) <= rules.top_n or len(candidate) != len(reference):
        return False
    if not candidate or len(candidate[0]) < len(_comparison_columns(reference[0], rules)):
        return False

    boundary_start = _boundary_start(reference, rules.top_n, rules.tie_columns, rules.value_kinds)
    for mapping in permutations(range(len(candidate[0])), len(_comparison_columns(reference[0], rules))):
        prefix_matches = all(
            _rows_equal(candidate[index], reference[index], mapping, rules)
            for index in range(boundary_start)
        )
        if prefix_matches and _rows_match_unordered(
            candidate[boundary_start:], reference[boundary_start:], mapping, rules
        ):
            return True
    return False


def _boundary_start(reference: Rows, top_n: int, tie_columns: tuple[int, ...], value_kinds: tuple[ValueKind, ...] = ()) -> int:
    boundary = reference[top_n - 1]
    start = top_n - 1
    while start > 0 and _tie_keys_equal(reference[start - 1], boundary, tie_columns, value_kinds):
        start -= 1
    return start


def _tie_keys_equal(left: Row, right: Row, columns: tuple[int, ...], value_kinds: tuple[ValueKind, ...] = ()) -> bool:
    # Result tolerance must not enlarge a ranking tie group.
    return all(quantize_tie(left[column], value_kinds[column] if value_kinds else "other") == quantize_tie(right[column], value_kinds[column] if value_kinds else "other") for column in columns)


def _rows_match_unordered(candidate: Rows, reference: Rows, mapping: tuple[int, ...], rules: _Rules) -> bool:
    if len(candidate) != len(reference):
        return False
    return _rows_match_subset(candidate, reference, mapping, rules)


def _rows_match_subset(candidate: Rows, reference: Rows, mapping: tuple[int, ...], rules: _Rules) -> bool:
    if len(candidate) > len(reference):
        return False

    candidate_buckets: dict[tuple[object, ...], list[Row]] = defaultdict(list)
    reference_buckets: dict[tuple[object, ...], list[Row]] = defaultdict(list)
    for row in candidate:
        candidate_buckets[_row_bucket(row, mapping, rules, candidate=True)].append(row)
    for row in reference:
        reference_buckets[_row_bucket(row, mapping, rules, candidate=False)].append(row)

    for bucket, candidate_rows in candidate_buckets.items():
        reference_rows = reference_buckets.get(bucket, [])
        if len(candidate_rows) > len(reference_rows):
            return False
        if not _match_bucket(candidate_rows, reference_rows, mapping, rules):
            return False
    return True


def _row_bucket(row: Row, mapping: tuple[int, ...], rules: _Rules, *, candidate: bool) -> tuple[object, ...]:
    pair_columns = {i for pair in rules.unordered_pairs for side in pair for i in side}
    columns = rules.required_columns if rules.required_columns is not None else tuple(range(len(mapping)))
    values = (row[mapping[position]] if candidate else row[i] for position,i in enumerate(columns)
              if i not in pair_columns and (not rules.label_values or rules.label_values[i] is None))
    return tuple(_nonnumeric_bucket(value) for value in values if not _is_numeric(value))


def _calendar_date(value: Cell) -> date | None:
    if isinstance(value, datetime):
        return value.date() if value.tzinfo is None and value.time() == time() else None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:[ T]00:00:00(?:\.0+)?)?", value.strip())
        if match:
            try:
                return date.fromisoformat(match[1])
            except ValueError:
                pass
    return None


def _nonnumeric_bucket(value: object) -> object:
    day = _calendar_date(value)
    if day is not None:
        return (date, day)
    if isinstance(value, str):
        return (str, value.strip())
    try:
        hash(value)
    except TypeError:
        return (type(value), repr(value))
    return (type(value), value)


def _match_bucket(candidate: list[Row], reference: list[Row], mapping: tuple[int, ...], rules: _Rules) -> bool:
    compatible = [
        [
            reference_index
            for reference_index, reference_row in enumerate(reference)
            if _rows_equal(candidate_row, reference_row, mapping, rules)
        ]
        for candidate_row in candidate
    ]
    if any(not choices for choices in compatible):
        return False

    matched_candidate = [-1] * len(reference)

    def assign(candidate_index: int, seen: set[int]) -> bool:
        for reference_index in compatible[candidate_index]:
            if reference_index in seen:
                continue
            seen.add(reference_index)
            previous = matched_candidate[reference_index]
            if previous == -1 or assign(previous, seen):
                matched_candidate[reference_index] = candidate_index
                return True
        return False

    for candidate_index in sorted(range(len(candidate)), key=lambda index: len(compatible[index])):
        if not assign(candidate_index, set()):
            return False
    return True


def _rows_equal(candidate: Row, reference: Row, mapping: tuple[int, ...], rules: _Rules) -> bool:
    columns = _comparison_columns(reference, rules)
    def equal(column: int, expected_column: int) -> bool:
        value = candidate[mapping[columns.index(column)]]
        expected = reference[expected_column]
        return (_label_matches(value, expected, expected_column, rules)
                or _cells_equal(value, expected, kind=rules.value_kinds[expected_column] if rules.value_kinds else "other",
                                use_absolute=rules.use_absolute_tolerance,
                                exact_counts=rules.exact_counts and bool(rules.value_types) and is_integer_type(rules.value_types[expected_column])))
    paired = set()
    for left,right in rules.unordered_pairs:
        compared = [(a,b) for a,b in zip(left,right) if a in columns and b in columns]
        if not (all(equal(a,a) and equal(b,b) for a,b in compared)
                or all(equal(a,b) and equal(b,a) for a,b in compared)):
            return False
        paired.update(i for pair in compared for i in pair)
    return all(equal(i,i) for i in columns if i not in paired)


def _cells_equal(left: Cell, right: Cell, *, allow_percentage: bool = True, kind: ValueKind = "other", use_absolute: bool = True, exact_counts: bool = False) -> bool:
    if _is_numeric(left) and _is_numeric(right):
        if exact_counts and kind == "count":
            return left == right
        left_number = float(left)
        right_number = float(right)
        if math.isnan(left_number) or math.isnan(right_number):
            return math.isnan(left_number) and math.isnan(right_number)
        if math.isinf(left_number) or math.isinf(right_number):
            return left_number == right_number
        # Retain every pre-A match. Absolute floors apply in the reference unit;
        # zero gives no evidence for choosing a 100x alternative representation.
        if _relative_close(left_number, right_number):
            return True
        if allow_percentage and (_relative_close(left_number * 100.0, right_number) or _relative_close(left_number, right_number * 100.0)):
            return True
        atol = absolute_tolerance(kind) if use_absolute else 0.0
        if _relative_close(left_number, right_number, atol):
            return True
        return allow_percentage and right_number != 0 and kind in {"ratio", "percentage"} and (
            _relative_close(left_number * 100.0, right_number, atol)
            or _relative_close(left_number, right_number * 100.0, atol * 100.0)
        )
    left_day, right_day = _calendar_date(left), _calendar_date(right)
    if left_day is not None and right_day is not None:
        return left_day == right_day
    if isinstance(left, str) and isinstance(right, str):
        return left.strip() == right.strip()
    return left == right


def _is_numeric(value: object) -> bool:
    return isinstance(value, (Number, Decimal)) and not isinstance(value, (bool, complex))


def _relative_close(left: float, right: float, atol: float = 0.0) -> bool:
    if left == right:
        return True
    scale = abs(right)
    rounding_slack = 1e-12 * max(1.0, scale)
    return (scale > 0 or atol > 0) and abs(left - right) <= max(RELATIVE_TOLERANCE * scale, atol) + rounding_slack
