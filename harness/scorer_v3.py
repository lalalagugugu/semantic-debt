"""Conservative, evidence-based presentation sensitivity analysis over frozen v2.

Column evidence comes from saved execution results / the reference MANIFEST, never
from a question ID, query, answer magnitude, or an inferred business synonym.
Unsupported or ambiguous representations retain the original v2 verdict.
"""
from __future__ import annotations

from calendar import month_name
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
import re

from harness import scorer_v2 as V2
from harness.value_units import is_numeric_type

ExecError, REFUSAL = V2.ExecError, V2.REFUSAL


@dataclass(frozen=True)
class ScoreResult(V2.ScoreResult):
    transformations: tuple[dict, ...] = ()


def _name(column):
    # SQL's table qualifier does not change a returned column's name.
    return column['name'].rsplit('.', 1)[-1].strip()


def _columns(columns, rows):
    if columns is None:
        return False
    if not isinstance(columns, (list, tuple)) or any(
            not isinstance(c, dict) or not isinstance(c.get('name'), str)
            or not isinstance(c.get('type'), str) for c in columns):
        raise ValueError('column evidence must contain name and type')
    if rows and len(columns) != len(rows[0]):
        raise ValueError('column evidence width differs from rows')
    return True


def _role(column):
    name = _name(column)
    name = re.sub(r'([a-z])([A-Z])', r'\1_\2', name).lower()
    match = re.fullmatch(r'(?:(.*?)_)?(year|month|quarter)(?:_label)?', name)
    if match:
        context = match[1] or ''
        return ('' if context == 'calendar' else context, match[2])
    match = re.fullmatch(r'(.*?)(年份|月份|季度|年|月)', name)
    if match:
        return match[1], {'年份': 'year', '年': 'year', '月份': 'month',
                         '月': 'month', '季度': 'quarter'}[match[2]]
    return None


def _integer(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    number = Decimal(str(value))
    return int(number) if number.is_finite() and number == number.to_integral_value() else None


def _period(value, unit):
    """(year, ordinal), retaining every year supplied by a fused representation."""
    number = _integer(value)
    text = value.strip() if isinstance(value, str) else ''
    if unit == 'year':
        match = re.fullmatch(r'(?:Year\s+)?([0-9]{4})(?:年)?', text, re.I)
        year = number if number is not None else int(match[1]) if match else None
        return (year, None) if year is not None and 1 <= year <= 9999 else None
    limit = 12 if unit == 'month' else 4
    if number is not None:
        return (None, number) if 1 <= number <= limit else None
    if isinstance(value, datetime):
        if value.tzinfo is not None or value.time() != time():
            return None
        value = value.date()
    if isinstance(value, date):
        day = value
    elif re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[ T]00:00:00(?:\.0+)?)?', text):
        try:
            day = date.fromisoformat(text[:10])
        except ValueError:
            return None
    else:
        day = None
    if day is not None:
        if day.day != 1 or (unit == 'quarter' and day.month not in (1, 4, 7, 10)):
            return None
        return day.year, day.month if unit == 'month' else (day.month - 1) // 3 + 1
    if unit == 'month':
        match = re.fullmatch(r'(?:([0-9]{4})[-年/])?([0-9]{1,2})(?:月)?', text)
        if match and 1 <= int(match[2]) <= 12:
            return int(match[1]) if match[1] else None, int(match[2])
        for ordinal, label in enumerate(month_name):
            if ordinal:
                match = re.fullmatch(rf'{label}(?:\s+([0-9]{{4}}))?', text, re.I)
                if match:
                    return int(match[1]) if match[1] else None, ordinal
    else:
        match = re.fullmatch(r'(?:([0-9]{4})[- 年]*)?[Qq]([1-4])', text)
        if match:
            return int(match[1]) if match[1] else None, int(match[2])
        match = re.fullmatch(r'(?:([0-9]{4})年)?第?([1-4一二三四])季度', text)
        if match:
            ordinal = int(match[2]) if match[2].isdigit() else '一二三四'.index(match[2]) + 1
            return int(match[1]) if match[1] else None, ordinal
    return None


def _periods(rows, columns, rule=None):
    """Normalize a whole table, splitting fused periods losslessly when necessary."""
    if not rows:
        return None
    groups = defaultdict(dict)
    for index, column in enumerate(columns):
        role = _role(column)
        if role is None:
            continue
        if rule is not None and (index not in rule['required_columns']
                or rule['value_kinds'][index] != 'other'
                or index in rule.get('identifier_columns', []) + rule.get('rank_columns', [])):
            continue
        context, unit = role
        if unit in groups[context]:
            return None
        groups[context][unit] = index
    output = [list(row) for row in rows]
    names = list(columns)
    metadata = deepcopy(rule)
    profile, evidence = [], []
    for context, axes in groups.items():
        units = set(axes) - {'year'}
        if len(units) > 1:
            return None
        unit = next(iter(units), 'year')
        index = axes[unit]
        parsed = [_period(row[index], unit) for row in rows]
        if any(p is None for p in parsed):
            return None
        years = [p[0] for p in parsed]
        year_index = axes.get('year') if unit != 'year' else index
        if year_index is not None and unit != 'year':
            explicit = [_period(row[year_index], 'year') for row in rows]
            if any(y is None or (p[0] is not None and p[0] != y[0])
                   for p, y in zip(parsed, explicit)):
                return None
            years = [y[0] for y in explicit]
        if any(y is None for y in years) and any(y is not None for y in years):
            return None
        has_year = all(y is not None and 1 <= y <= 9999 for y in years)
        if any(y is not None and not 1 <= y <= 9999 for y in years):
            return None
        profile.append((unit, has_year))
        appended = unit != 'year' and has_year and year_index is None
        if appended:
            year_index = len(names)
            names.append({'name': f'{context + "_" if context else ""}year', 'type': 'UInt16'})
            for row in output:
                row.append(None)
            if metadata is not None:
                metadata['required_columns'].append(year_index)
                metadata['value_types'].append('UInt16')
                metadata['value_kinds'].append('other')
                # Preserve chronological sorting of the original fused period.
                order = []
                for item in metadata.get('order_by', []):
                    if item['column'] == index:
                        order.append({**item, 'column': year_index})
                    order.append(item)
                metadata['order_by'] = order
        for n, (row, part) in enumerate(zip(output, parsed)):
            row[index] = f'__period_{unit}:{(part[0] if unit == "year" else part[1]):04d}'
            if unit != 'year' and year_index is not None:
                row[year_index] = f'__period_year:{years[n]:04d}'
        evidence.append({'column': index, 'unit': unit, 'year_column': year_index,
                         'appended_year': appended})
    return (output, names, metadata, Counter(profile), evidence) if profile else None


def _p1(candidate, reference, rule, ccols, rcols):
    # Literal identities in these contracts need a separate proof-preserving
    # rewrite. Their absence is not permission to discard a selection constraint.
    if rule.get('selection') or rule.get('rankings') or rule.get('top_n') is not None or rule.get('unordered_pairs'):
        return None
    left, right = _periods(candidate, ccols), _periods(reference, rcols, rule)
    if left is None or right is None or left[3] != right[3]:
        return None
    return left[0], right[0], right[2], left[1], right[1], {
        'rule': 'P1', 'candidate': left[4], 'reference': right[4]}


def _wide_spec(wide_cols, long_rows, long_cols, long_rule=None):
    """Only exact member headers (or member__measure), with one numeric measure."""
    if not long_rows or len({_name(c) for c in wide_cols}) != len(wide_cols):
        return None
    if any(isinstance(cell, (list, tuple)) for row in long_rows for cell in row):
        return None
    if len({_name(c) for c in long_cols}) != len(long_cols):
        return None
    if long_rule is not None and set(long_rule['required_columns']) != set(range(len(long_cols))):
        return None
    choices = []
    for category in range(len(long_cols)):
        if any(not isinstance(row[category], str) or not row[category] for row in long_rows):
            continue
        members = {row[category] for row in long_rows if isinstance(row[category], str) and row[category]}
        if len(members) < 2 or any(row[category] not in members for row in long_rows):
            continue
        for measure, column in enumerate(long_cols):
            if measure == category or not is_numeric_type(column['type']) or _role(column):
                continue
            if long_rule is not None and measure in long_rule.get('identifier_columns', []) + long_rule.get('rank_columns', []):
                continue
            group = [i for i in range(len(long_cols)) if i not in (category, measure)]
            names = {_name(c): i for i, c in enumerate(wide_cols)}
            if any(_name(long_cols[i]) not in names for i in group):
                continue
            group_map = {i: names[_name(long_cols[i])] for i in group}
            member_map = {}
            for member in members:
                headers = {member, f'{member}__{_name(column)}', f'{_name(column)}__{member}'}
                found = [names[h] for h in headers if h in names and is_numeric_type(wide_cols[names[h]]['type'])]
                if len(found) != 1:
                    break
                member_map[member] = found[0]
            else:
                used = list(group_map.values()) + list(member_map.values())
                if len(set(used)) == len(used) == len(wide_cols):
                    keys = [tuple(row[i] for i in group + [category]) for row in long_rows]
                    if len(set(keys)) == len(keys):
                        choices.append((category, measure, group_map, member_map))
    return choices[0] if len(choices) == 1 else None


def _p2(candidate, reference, rule, ccols, rcols):
    if not candidate or not reference:
        return None
    if any(isinstance(cell, (list, tuple)) for rows in (candidate, reference) for row in rows for cell in row):
        return None
    variants = []
    spec = _wide_spec(ccols, reference, rcols, rule)
    if spec:
        category, measure, groups, members = spec
        keys = [tuple(row[i] for i in groups.values()) for row in candidate]
        if len(set(keys)) == len(keys):
            rows = []
            for source in candidate:
                for label, index in sorted(members.items(), key=lambda item: item[1]):
                    row = [None] * len(rcols)
                    for target, origin in groups.items():
                        row[target] = source[origin]
                    row[category], row[measure] = label, source[index]
                    rows.append(row)
            variants.append((rows, rcols, {'rule': 'P2', 'direction': 'wide_to_long',
                'category_column': category, 'measure_column': measure,
                'member_columns': sorted(members.values())}))
    spec = _wide_spec(rcols, candidate, ccols)
    if spec:
        category, measure, groups, members = spec
        grouped = {}
        valid = True
        for source in candidate:
            key = tuple(source[i] for i in groups)
            values = grouped.setdefault(key, {})
            label = source[category]
            if label in values:
                valid = False
                break
            values[label] = source[measure]
        if valid and all(set(values) == set(members) for values in grouped.values()):
            rows = []
            for key, values in grouped.items():
                row = [None] * len(rcols)
                for value, index in zip(key, groups.values()):
                    row[index] = value
                for label, index in members.items():
                    row[index] = values[label]
                rows.append(row)
            variants.append((rows, rcols, {'rule': 'P2', 'direction': 'long_to_wide',
                'category_column': category, 'measure_column': measure,
                'member_columns': sorted(members.values())}))
    return variants[0] if len(variants) == 1 else None


def _p3(candidate, reference, rule, ccols, rcols):
    ids = rule.get('identifier_columns', [])
    if len(ids) != 1 or ids[0] not in rule['required_columns']:
        return None
    identity = ids[0]
    names = defaultdict(list)
    for index, column in enumerate(ccols):
        names[_name(column)].append(index)
    candidates = names[_name(rcols[identity])]
    if len(candidates) != 1:
        return None
    candidate_id = candidates[0]
    output, changes = [list(row) for row in candidate], []
    for label in rule['required_columns']:
        if label in ids or not V2._string_column(rule, label):
            continue
        target = names[_name(rcols[label])]
        if len(target) != 1 or target[0] == candidate_id:
            continue
        blank_keys, normal_keys = set(), set()
        for row in reference:
            key = V2._norm(row[identity], True)
            (blank_keys if row[label] is None or row[label] == '' else normal_keys).add(key)
        blank_keys -= normal_keys
        changed = False
        for row in output:
            key = V2._norm(row[candidate_id], True)
            if (key in blank_keys and key[0] == 'number'
                    and V2._norm(row[target[0]], True) == key):
                row[target[0]] = ''
                changed = True
        if changed:
            changes.append({'reference_column': label, 'candidate_column': target[0],
                            'reference_identifier': identity, 'candidate_identifier': candidate_id})
    return (output, {'rule': 'P3', 'columns': changes}) if changes else None


def score_detailed(candidate_rows, refs, rules, *, reference_rules=None,
                   candidate_columns=None, reference_columns=None):
    baseline = V2.score_detailed(candidate_rows, refs, rules, reference_rules=reference_rules)
    original = ScoreResult(baseline.outcome, baseline.reason, baseline.matched_ref, baseline.sensitivity)
    if baseline.outcome != 'wrong' or not _columns(candidate_columns, candidate_rows) or reference_columns is None:
        return original
    if len(reference_columns) != len(refs):
        raise ValueError('reference column evidence must align with refs')
    for index, ref in enumerate(refs):
        if not _columns(reference_columns[index], ref):
            continue
        rule = rules if reference_rules is None or reference_rules[index] is None else reference_rules[index]
        variants = [(candidate_rows, candidate_columns, [])]
        shaped = _p2(candidate_rows, ref, rule, candidate_columns, reference_columns[index])
        if shaped:
            variants.append((shaped[0], shaped[1], [shaped[2]]))
        for candidate, ccols, steps in variants:
            options = [(candidate, ref, rule, ccols, reference_columns[index], steps)]
            calendar = _p1(candidate, ref, rule, ccols, reference_columns[index])
            if calendar:
                options.append((*calendar[:5], steps + [calendar[5]]))
            for crows, rrows, metadata, cinfo, rinfo, evidence in options:
                names = _p3(crows, rrows, metadata, cinfo, rinfo)
                if names:
                    crows, proof = names
                    evidence = evidence + [proof]
                if not evidence:
                    continue
                result = V2.score_detailed(crows, [rrows], metadata)
                if result.outcome == 'correct':
                    return ScoreResult('correct', matched_ref=index,
                        sensitivity='+'.join(step['rule'] for step in evidence),
                        transformations=tuple(evidence))
    return original


def score(candidate_rows, refs, rules, **kwargs):
    return score_detailed(candidate_rows, refs, rules, **kwargs).outcome
