"""Generic delivery check (a): every table or column a cell's documentation names must be
visible in that cell, or the cell's documentation must say which visible object implements it.

decisions/2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md §三 3 and the coordinator's plan
for semantic-v1.4. Run on the rendered contexts (``build/contexts/*.yaml``), never on questions
or answers. For each cell:

- **visible**: its datasets, their columns, and (L2 cells) the metric callables, under every
  spelling the cell uses (``db.table``, ``table``, ``table.column``, ``Table[Column]``,
  ``cube.member``, ``[DAX measure]``);
- **named**: what its conventions, metrics and synonyms refer to, from the structured fields
  (``applies_to_datasets``, ``applies_to_columns``, ``dataset``, ``alternate_dataset``,
  ``only_dataset``, ``denominator_dataset``, ``default_dataset``, ``maps_to_column``) and from
  their text (dotted or bracketed references, and bare ``Fact…`` / ``Dim…`` / ``ads_…`` /
  ``dwd_…`` table names);
- a named object that is not visible is **documented** if some visible dataset's own text
  (title, description, grain, cautions, when_to_use, column descriptions) mentions it, and a
  **gap** otherwise.

    uv run python render/check_references.py            # every rendered context; exit 1 on a gap
    uv run python render/check_references.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CONTEXTS = REPO / "build" / "contexts"

TABLE_FIELDS = ("applies_to_datasets", "dataset", "alternate_dataset", "only_dataset", "denominator_dataset",
                "default_dataset")
COLUMN_FIELDS = ("applies_to_columns", "maps_to_column")
TEXT_FIELDS = ("rule", "note", "why", "definition", "default_filters", "numerator", "denominator")
DATASET_TEXT = ("title", "description", "grain", "cautions", "when_to_use", "differs_from")

DOTTED = re.compile(r"(?<![\w.])[A-Za-z_]\w*(?:\.[\w一-鿿]+){1,2}(?![\w(])")
BRACKET = re.compile(r"(?<![\w\]])[A-Za-z_]\w*\[[^\]\n]+\]")
BARE = re.compile(r"(?<![\w.])(?:Fact[A-Z]\w*|Dim[A-Z]\w*|ads_\w+|dwd_\w+)(?![\w.(])")
CALL = re.compile(r"MEASURE\(([\w.]+)\)|^([a-z_]+\.[a-z_]+)$|^(\[[^\]]+\])$")


def norm(ref: str) -> str:
    """``T[C]`` -> ``T.C``; everything else unchanged."""
    m = re.fullmatch(r"([A-Za-z_]\w*)\[([^\]]+)\]", ref)
    return f"{m.group(1)}.{m.group(2)}" if m else ref


def _as_list(v) -> list:
    return [] if v is None else v if isinstance(v, list) else [v]


def visible(ctx: dict) -> set[str]:
    names = set()
    for ds in ctx.get("datasets", []):
        full = ds["name"]
        tables = {full, full.split(".")[-1]}
        names |= tables
        for col in ds.get("columns", []):
            for t in tables:
                names.add(f"{t}.{col['name']}")
    for m in ctx.get("metrics", []):
        for c in m.get("callables") or []:
            call = c.get("call", "") if isinstance(c, dict) else str(c)
            hit = CALL.search(call)
            if hit:
                names.add(next(g for g in hit.groups() if g))
            names.add(call)
    return names


def dataset_text(ctx: dict) -> str:
    parts = []
    for ds in ctx.get("datasets", []):
        parts += [json.dumps(ds.get(k), ensure_ascii=False) for k in DATASET_TEXT if ds.get(k)]
        parts += [c.get("description", "") for c in ds.get("columns", [])]
    return "\n".join(parts)


def named(ctx: dict) -> list[tuple[str, str, str]]:
    """(section, item label, reference) for everything the conventions, metrics and synonyms name."""
    out = []
    for section in ("conventions", "metrics", "synonyms"):
        for item in ctx.get(section, []) or []:
            label = str(item.get("id") or item.get("name") or (item.get("terms") or ["?"])[0])
            for f in TABLE_FIELDS + COLUMN_FIELDS:
                for v in _as_list(item.get(f)):
                    if isinstance(v, str):         # only_dataset is also used as a true/false flag
                        out.append((section, label, v))
            text = "\n".join(json.dumps(item.get(f), ensure_ascii=False) for f in TEXT_FIELDS if item.get(f))
            for rx in (BRACKET, DOTTED, BARE):
                for ref in rx.findall(text):
                    out.append((section, label, ref))
    return out


def resolves(ref: str, seen: set[str]) -> bool:
    r = norm(ref)
    if r in seen:
        return True
    parts = r.split(".")
    # db.table.column / table.column written with or without the database
    return len(parts) == 3 and f"{parts[1]}.{parts[2]}" in seen


def check(ctx: dict) -> dict[str, list[dict]]:
    seen, docs = visible(ctx), dataset_text(ctx)
    gaps, documented = [], []
    for section, label, ref in named(ctx):
        if resolves(ref, seen) or re.fullmatch(r"[\d.]+", ref):
            continue
        r = norm(ref)
        tail = r.split(".")[-1]
        row = {"section": section, "item": label, "name": ref}
        (documented if (r in docs or (len(tail) > 3 and tail in docs and r.split(".")[0] in docs)) else gaps).append(row)
    dedup = lambda rows: [dict(t) for t in dict.fromkeys(tuple(sorted(r.items())) for r in rows)]  # noqa: E731
    return {"gaps": dedup(gaps), "documented": dedup(documented)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", help="write the full result here")
    args = ap.parse_args(argv)
    result, bad = {}, 0
    for path in sorted(CONTEXTS.glob("*.yaml")):
        res = check(yaml.safe_load(path.read_text(encoding="utf-8")))
        result[path.stem] = res
        bad += len(res["gaps"])
        print(f"{path.stem}: {len(res['gaps'])} gap(s), {len(res['documented'])} documented")
        for g in res["gaps"]:
            print(f"  GAP  {g['section']} [{g['item']}] -> {g['name']}")
    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
