"""Explicit grouped and nested selection; no query or benchmark inference."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from functools import cmp_to_key

from harness.value_units import quantize_tie


def validate_selection(spec, width, *, ordered=False):
    if not isinstance(spec, Mapping) or set(spec) != {"version", "stages", "output_order"} or type(spec["version"]) is not int or spec["version"] != 1:
        raise ValueError("selection requires version=1, stages and output_order")
    stages = spec["stages"]
    if not isinstance(stages, list) or not stages:
        raise ValueError("selection.stages must be nonempty")

    def columns(values, nonempty=False):
        if not isinstance(values, list) or (nonempty and not values) or any(type(i) is not int or not 0 <= i < width for i in values) or len(set(values)) != len(values):
            raise ValueError("selection columns must be unique reference positions")

    def ordering(items, nonempty=False):
        if not isinstance(items, list) or (nonempty and not items):
            raise ValueError("selection order must be an explicit list")
        for item in items:
            if not isinstance(item, Mapping) or set(item) != {"column", "descending"} or type(item["descending"]) is not bool:
                raise ValueError("selection order requires column and descending")
        columns([item["column"] for item in items], nonempty)

    for index, stage in enumerate(stages):
        if not isinstance(stage, Mapping) or set(stage) != {"parent", "where", "group_columns", "object_columns", "order_by", "n"}:
            raise ValueError("invalid selection stage fields")
        parent = stage["parent"]
        if parent is not None and (type(parent) is not int or not 0 <= parent < index):
            raise ValueError("selection parent must identify an earlier stage")
        if type(stage["n"]) is not int or stage["n"] < 1:
            raise ValueError("selection n must be positive")
        columns(stage["group_columns"])
        columns(stage["object_columns"], True)
        if set(stage["group_columns"]) & set(stage["object_columns"]):
            raise ValueError("selection group and object columns must be disjoint")
        if parent is not None:
            identity = set(stages[parent]["group_columns"] + stages[parent]["object_columns"])
            if not identity <= set(stage["group_columns"]):
                raise ValueError("child groups must retain their parent identity")
        ordering(stage["order_by"], True)
        if not isinstance(stage["where"], list):
            raise ValueError("selection where must be a list")
        for condition in stage["where"]:
            if not isinstance(condition, Mapping) or set(condition) != {"column", "equals"} or not isinstance(condition["equals"], (str, int, float, bool, type(None))):
                raise ValueError("selection where requires a scalar equality")
            columns([condition["column"]])
    ordering(spec["output_order"], ordered)
    if not ordered and spec["output_order"]:
        raise ValueError("unordered selection must not declare output_order")


def identity(row, columns):
    # IDs are exact, not result values subject to relative/percentage tolerance.
    return tuple(row[i].strip() if isinstance(row[i], str) else row[i] for i in columns)


def order_key(row, order, kinds):
    values = tuple(quantize_tie(row[item["column"]], kinds[item["column"]]) for item in order)
    if any(value is None for value in values):
        raise ValueError("selection ranking keys must not be NULL")
    return values


def compare_keys(left, right, order):
    for a, b, item in zip(left, right, order, strict=True):
        if a != b:
            result = -1 if a < b else 1
            return -result if item["descending"] else result
    return 0


def _domain(rows, stage, kinds):
    groups = defaultdict(dict)
    for row in rows:
        group = identity(row, stage["group_columns"])
        obj = identity(row, stage["object_columns"])
        key = order_key(row, stage["order_by"], kinds)
        if obj in groups[group] and groups[group][obj] != key:
            raise ValueError("selection object has inconsistent ranking values")
        groups[group][obj] = key
    return groups


def _eligible(rows, stage, stages, selected):
    parent = stage["parent"]
    for row in rows:
        if any(row[c["column"]] != c["equals"] for c in stage["where"]):
            continue
        if parent is not None:
            ancestor = stages[parent]
            if identity(row, ancestor["group_columns"] + ancestor["object_columns"]) not in selected[parent]:
                continue
        yield row


def _boundary(objects, stage):
    order = stage["order_by"]
    ranked = sorted(objects, key=cmp_to_key(lambda a, b: compare_keys(objects[a], objects[b], order)))
    count = min(stage["n"], len(ranked))
    if not count:
        return set(), set(), 0
    boundary = objects[ranked[count - 1]]
    strict = {obj for obj in ranked if compare_keys(objects[obj], boundary, order) < 0}
    tied = {obj for obj in ranked if objects[obj] == boundary}
    return strict, tied, count


def complete_selection(rows, spec, kinds):
    """Select strict prefixes and entire boundaries from a complete SQL domain."""
    validate_selection(spec, len(kinds), ordered=bool(spec["output_order"]))
    selected, stage_rows, checks = [], [], []
    stages = spec["stages"]
    for stage in stages:
        eligible = list(_eligible(rows, stage, stages, selected))
        groups = _domain(eligible, stage, kinds)
        members = set()
        group_checks = []
        for group, objects in groups.items():
            strict, tied, count = _boundary(objects, stage)
            members.update(group + obj for obj in strict | tied)
            group_checks.append({"group": list(group), "objects": len(objects), "required": count, "strict": len(strict), "boundary": len(tied)})
        selected.append(members)
        stage_rows.append([row for row in eligible if identity(row, stage["group_columns"] + stage["object_columns"]) in members])
        checks.append(group_checks)
    parents = {stage["parent"] for stage in stages}
    leaves = [index for index in range(len(stages)) if index not in parents]
    # Keep SQL order unless the contract declares a global output order.
    wanted = {tuple(row) for index in leaves for row in stage_rows[index]}
    output = [row for row in rows if tuple(row) in wanted]
    if spec["output_order"]:
        order = spec["output_order"]
        output.sort(key=cmp_to_key(lambda a, b: compare_keys(order_key(a, order, kinds), order_key(b, order, kinds), order)))
    return output, checks


def matches_selection(candidate, reference, spec, kinds):
    """Rows are already mapped and matched to exact reference identities."""
    stages = spec["stages"]
    selected, leaf_coverage = [], set()
    parents = {stage["parent"] for stage in stages}
    for index, stage in enumerate(stages):
        domain = list(_eligible(reference, stage, stages, selected))
        offered = list(_eligible(candidate, stage, stages, selected))
        groups = _domain(domain, stage, kinds)
        candidate_groups = _domain(offered, stage, kinds)
        if set(groups) != set(candidate_groups):
            return False, "selection_group_coverage"
        members = set()
        for group, objects in groups.items():
            strict, tied, count = _boundary(objects, stage)
            chosen = set(candidate_groups[group])
            if len(chosen) != count:
                return False, "selection_object_count"
            if not strict <= chosen or not chosen <= strict | tied:
                return False, "selection_members"
            members.update(group + obj for obj in chosen)
        selected.append(members)
        if index not in parents:
            identities = [identity(row, stage["group_columns"] + stage["object_columns"]) for row in offered]
            if len(identities) != len(set(identities)):
                return False, "selection_duplicate_object"
            leaf_coverage.update(tuple(row) for row in offered)
    if any(tuple(row) not in leaf_coverage for row in candidate):
        return False, "selection_uncovered_row"
    if spec["output_order"]:
        keys = [order_key(row, spec["output_order"], kinds) for row in candidate]
        if any(compare_keys(a, b, spec["output_order"]) > 0 for a, b in zip(keys, keys[1:])):
            return False, "selection_output_order"
    return True, "matched"
