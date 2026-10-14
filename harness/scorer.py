"""Deterministic result-set scorer.

The scorer is deliberately independent of query execution.  The harness passes
one of three candidate states: rows, ``CANNOT_ANSWER``, or :class:`ExecError`.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from itertools import permutations
from numbers import Number
from typing import Literal, TypeAlias


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


def score(
    candidate_rows: Sequence[Sequence[Cell]] | str | ExecError,
    refs: Sequence[Sequence[Sequence[Cell]]],
    rules: Mapping[str, object],
) -> Outcome:
    """Return one of the four outcomes required by the frozen scoring rules."""

    return score_detailed(candidate_rows, refs, rules).outcome


def score_detailed(
    candidate_rows: Sequence[Sequence[Cell]] | str | ExecError,
    refs: Sequence[Sequence[Sequence[Cell]]],
    rules: Mapping[str, object],
) -> ScoreResult:
    """Score a candidate and retain a stable diagnostic reason.

    ``refs`` is a sequence of acceptable result sets.  For Top-N questions, a
    reference must contain the strict prefix followed by the complete boundary
    tie group; it must never be truncated to N rows.
    """

    parsed_rules = _parse_rules(rules)
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
        matched, reason = _matches_reference(candidate, reference, parsed_rules)
        if matched:
            return ScoreResult("correct", matched_ref=index)
        mismatch_reasons.append(reason)

    if BOUNDARY_TIE_FULL_GROUP in mismatch_reasons:
        return ScoreResult("wrong", BOUNDARY_TIE_FULL_GROUP, sensitivity="structure_mismatch")
    return ScoreResult("wrong", mismatch_reasons[0], sensitivity=_sensitivity(candidate, references, parsed_rules))


def _sensitivity(candidate: Rows, references: tuple[Rows, ...], rules: _Rules) -> Sensitivity:
    """Numeric projection is a reporting diagnostic, never a second verdict.

    Keep row multiplicities, numeric NULLs, order, and Top-N constraints. Missing
    numeric columns remain failures; extra candidate columns are still allowed.
    """
    if not candidate or not any(references):
        return "structure_mismatch"
    expected_counts = {rules.top_n if rules.top_n is not None else len(ref) for ref in references}
    if len(candidate) not in expected_counts:
        return "structure_mismatch"
    saw_numeric = False
    for reference in references:
        if not reference:
            continue
        numeric_ref = tuple(i for i in range(len(reference[0])) if any(_is_numeric(row[i]) for row in reference))
        numeric_candidate = tuple(i for i in range(len(candidate[0])) if any(_is_numeric(row[i]) for row in candidate))
        if not numeric_ref:
            continue
        saw_numeric = True
        if len(numeric_candidate) < len(numeric_ref):
            continue
        if any(i not in numeric_ref for i in rules.tie_columns):
            continue
        projected_rules = _Rules(rules.ordered, rules.top_n, tuple(numeric_ref.index(i) for i in rules.tie_columns))
        projected_candidate = tuple(tuple(row[i] for i in numeric_candidate) for row in candidate)
        projected_reference = tuple(tuple(row[i] for i in numeric_ref) for row in reference)
        matched, _ = _matches_reference(projected_candidate, projected_reference, projected_rules)
        if matched:
            return "string_or_label_only"
    if not saw_numeric:
        return "no_numeric_reference"
    return "numeric_mismatch"


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
    return _Rules(ordered=ordered, top_n=top_n, tie_columns=tuple(tie_columns))


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


def _matches_reference(candidate: Rows, reference: Rows, rules: _Rules) -> tuple[bool, str]:
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
    reference_width = len(reference[0])
    if candidate_width < reference_width:
        return False, "missing_columns"

    for mapping in permutations(range(candidate_width), reference_width):
        if rules.top_n is not None:
            if _top_rows_match(candidate, reference, mapping, rules):
                return True, "matched"
        elif rules.ordered:
            if all(_rows_equal(candidate_row, reference_row, mapping) for candidate_row, reference_row in zip(candidate, reference)):
                return True, "matched"
        elif _rows_match_unordered(candidate, reference, mapping):
            return True, "matched"
    return False, "values"


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
        if not _tie_keys_equal(row, boundary, rules.tie_columns):
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
        return all(
            _rows_equal(candidate_row, reference_row, mapping)
            for candidate_row, reference_row in zip(candidate, reference)
        )

    boundary_start = _boundary_start(reference, rules.top_n, rules.tie_columns)
    if not all(
        _rows_equal(candidate[index], reference[index], mapping)
        for index in range(boundary_start)
    ):
        return False
    return _rows_match_subset(
        candidate[boundary_start:],
        reference[boundary_start:],
        mapping,
    )


def _is_complete_boundary_group(candidate: Rows, reference: Rows, rules: _Rules) -> bool:
    assert rules.top_n is not None
    if len(reference) <= rules.top_n or len(candidate) != len(reference):
        return False
    if not candidate or len(candidate[0]) < len(reference[0]):
        return False

    boundary_start = _boundary_start(reference, rules.top_n, rules.tie_columns)
    for mapping in permutations(range(len(candidate[0])), len(reference[0])):
        prefix_matches = all(
            _rows_equal(candidate[index], reference[index], mapping)
            for index in range(boundary_start)
        )
        if prefix_matches and _rows_match_unordered(
            candidate[boundary_start:], reference[boundary_start:], mapping
        ):
            return True
    return False


def _boundary_start(reference: Rows, top_n: int, tie_columns: tuple[int, ...]) -> int:
    boundary = reference[top_n - 1]
    start = top_n - 1
    while start > 0 and _tie_keys_equal(reference[start - 1], boundary, tie_columns):
        start -= 1
    return start


def _tie_keys_equal(left: Row, right: Row, columns: tuple[int, ...]) -> bool:
    # Result tolerance must not enlarge a ranking tie group.
    return all(left[column] == right[column] for column in columns)


def _rows_match_unordered(candidate: Rows, reference: Rows, mapping: tuple[int, ...]) -> bool:
    if len(candidate) != len(reference):
        return False
    return _rows_match_subset(candidate, reference, mapping)


def _rows_match_subset(candidate: Rows, reference: Rows, mapping: tuple[int, ...]) -> bool:
    if len(candidate) > len(reference):
        return False

    candidate_buckets: dict[tuple[object, ...], list[Row]] = defaultdict(list)
    reference_buckets: dict[tuple[object, ...], list[Row]] = defaultdict(list)
    for row in candidate:
        candidate_buckets[_row_bucket(row, mapping, candidate=True)].append(row)
    for row in reference:
        reference_buckets[_row_bucket(row, mapping, candidate=False)].append(row)

    for bucket, candidate_rows in candidate_buckets.items():
        reference_rows = reference_buckets.get(bucket, [])
        if len(candidate_rows) > len(reference_rows):
            return False
        if not _match_bucket(candidate_rows, reference_rows, mapping):
            return False
    return True


def _row_bucket(row: Row, mapping: tuple[int, ...], *, candidate: bool) -> tuple[object, ...]:
    values = (row[mapping[index]] if candidate else row[index] for index in range(len(mapping)))
    return tuple(_nonnumeric_bucket(value) for value in values if not _is_numeric(value))


def _nonnumeric_bucket(value: object) -> object:
    if isinstance(value, str):
        return (str, value.strip())
    try:
        hash(value)
    except TypeError:
        return (type(value), repr(value))
    return (type(value), value)


def _match_bucket(candidate: list[Row], reference: list[Row], mapping: tuple[int, ...]) -> bool:
    compatible = [
        [
            reference_index
            for reference_index, reference_row in enumerate(reference)
            if _rows_equal(candidate_row, reference_row, mapping)
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


def _rows_equal(candidate: Row, reference: Row, mapping: tuple[int, ...]) -> bool:
    return all(
        _cells_equal(candidate[mapping[reference_index]], reference_value)
        for reference_index, reference_value in enumerate(reference)
    )


def _cells_equal(left: Cell, right: Cell, *, allow_percentage: bool = True) -> bool:
    if _is_numeric(left) and _is_numeric(right):
        left_number = float(left)
        right_number = float(right)
        if math.isnan(left_number) or math.isnan(right_number):
            return math.isnan(left_number) and math.isnan(right_number)
        if math.isinf(left_number) or math.isinf(right_number):
            return left_number == right_number
        if _relative_close(left_number, right_number):
            return True
        return allow_percentage and (
            _relative_close(left_number * 100.0, right_number)
            or _relative_close(left_number, right_number * 100.0)
        )
    if isinstance(left, str) and isinstance(right, str):
        return left.strip() == right.strip()
    return left == right


def _is_numeric(value: object) -> bool:
    return isinstance(value, (Number, Decimal)) and not isinstance(value, (bool, complex))


def _relative_close(left: float, right: float) -> bool:
    if left == right:
        return True
    scale = abs(right)
    rounding_slack = 1e-12 * max(1.0, scale)
    return scale > 0 and abs(left - right) <= RELATIVE_TOLERANCE * scale + rounding_slack
