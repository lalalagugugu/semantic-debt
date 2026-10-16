"""Render the semantic context of every cell → build/contexts/<cell>.yaml.

All cells share one structure (model / conventions / synonyms / datasets /
relationships / multi_path_defaults / metrics / data_quality); tiers differ only in
content, stacks only in physical names (common.Namer) and in how a metric is called.

    uv run python render/context.py            # all cells
    uv run python render/context.py SQL-L1     # one cell

Tier contents (task card T10):
    R      table names, column names, types; no description, no relationship
    L0     L0 names, types, kept relationships, technical columns; nothing else
    L1     all of source.yaml except widetables and callables; technical columns hidden
    L1.5W  L1 + the widetables section (dwd views)
    L1.5S  ads summary tables + ads dimension views, enum meanings, synonyms,
           conventions, metric text; no detail fact table
    L2     L1 + each metric's callables, only this stack's syntax
    tuned  base tier + semantic/tuning/<base cell>.yaml under `tuning:`

L0 and R are checked for leaks before they are written (check_l0 / check_r);
a failure raises and nothing is written for that cell.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from render.common import (  # noqa: E402
    BUILD,
    SEMANTIC,
    Namer,
    dump_yaml,
    l0_map,
    metric_callables,
    metrics_file,
    physical_schema,
    source,
    summary,
    tuning_file,
)

OUT_DIR = BUILD / "contexts"

# cell → (stack, tier, tuning file name or None)
CELLS: dict[str, tuple[str, str, str | None]] = {
    "SQL-R": ("sql", "R", None),
    "SQL-L0": ("sql", "L0", None),
    "SQL-L1": ("sql", "L1", None),
    "SQL-L1.5W": ("sql", "L1.5W", None),
    "SQL-L1.5S": ("sql", "L1.5S", None),
    "SQL-L1-tuned": ("sql", "L1", "SQL-L1"),
    "SQL-L2": ("cube_sql", "L2", None),
    "JSON-L2": ("cube_json", "L2", None),
    "DAX-L0": ("dax", "L0", None),
    "DAX-L1": ("dax", "L1", None),
    "DAX-L2": ("dax", "L2", None),
    "DAX-L2-tuned": ("dax", "L2", "DAX-L2"),
}


class LeakError(Exception):
    """A degraded tier (L0 / R) would show something it must not."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _put(d: dict, key: str, value) -> None:
    if value not in (None, [], {}, ""):
        d[key] = value


def _deep_text(obj, namer: Namer):
    if isinstance(obj, str):
        return namer.text(obj)
    if isinstance(obj, list):
        return [_deep_text(x, namer) for x in obj]
    if isinstance(obj, dict):
        return {k: _deep_text(v, namer) for k, v in obj.items()}
    return obj


def _model_header() -> dict:
    s = source()
    return {k: s[k] for k in ("title", "description", "as_of_date", "currency", "grain_note")}


def _retail_types(table: str) -> dict[str, str]:
    return dict(physical_schema()["retail"][table])


# ---------------------------------------------------------------------------
# R
# ---------------------------------------------------------------------------
def render_r(n: Namer) -> dict:
    datasets = []
    for ds in source()["datasets"]:
        types = _retail_types(ds["name"])
        cols = [{"name": c["name"], "type": n.type(types[c["name"]])}
                for c in ds["columns"] if not c.get("technical")]
        datasets.append({"name": n.table(ds["name"]), "columns": cols})
    return {"datasets": datasets}


# ---------------------------------------------------------------------------
# L0
# ---------------------------------------------------------------------------
def _l0_names() -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    m = l0_map()
    tables = {t["source"]: t["l0"] for t in m["tables"]}
    cols = {(t["source"], src): l0 for t in m["tables"] for src, l0 in t["columns"].items()}
    return tables, cols


def render_l0(n: Namer) -> dict:
    tables, cols = _l0_names()
    schema = physical_schema()["l0"]
    datasets = []
    for t in l0_map()["tables"]:
        name = t["l0"]
        datasets.append({
            "name": n.table(name, "l0"),
            "columns": [{"name": c, "type": n.type(ty)} for c, ty in schema[name]],
        })

    def l0_ref(dotted: str) -> str:
        table, col = dotted.split(".", 1)
        return n.column(tables[table], cols[(table, col)], "l0")

    rels = [{"from": l0_ref(r["from"]), "to": l0_ref(r["to"])} for r in l0_map()["relationships"]["kept"]]
    return {"datasets": datasets, "relationships": rels}


# ---------------------------------------------------------------------------
# L1 / L1.5W / L2
# ---------------------------------------------------------------------------
def _conventions(n: Namer) -> list[dict]:
    out = []
    for c in source()["conventions"]:
        d = {"id": c["id"], "group": c["group"], "rule": c["rule"]}
        _put(d, "applies_to_datasets", [n.ref(x) for x in c.get("applies_to_datasets", [])])
        _put(d, "applies_to_columns", [n.ref(x) for x in c.get("applies_to_columns", [])])
        _put(d, "metrics", c.get("metrics"))
        _put(d, "note", c.get("note"))
        out.append(d)
    return out


def _synonyms(n: Namer) -> list[dict]:
    out = []
    for s in source()["synonyms"]:
        d = {"terms": s["terms"]}
        _put(d, "maps_to_metric", s.get("maps_to_metric"))
        if s.get("maps_to_column"):
            d["maps_to_column"] = n.ref(s["maps_to_column"])
        if s.get("default_dataset"):
            d["default_dataset"] = n.ref(s["default_dataset"])
        _put(d, "why", s.get("why"))
        out.append(d)
    return out


def _datasets(n: Namer) -> list[dict]:
    out = []
    for ds in source()["datasets"]:
        types = _retail_types(ds["name"])
        d = {"name": n.table(ds["name"])}
        for k in ("title", "kind", "rows", "grain", "description", "when_to_use"):
            _put(d, k, ds.get(k))
        if ds.get("differs_from"):
            d["differs_from"] = [{"dataset": n.ref(x["dataset"]), "how": x["how"]} for x in ds["differs_from"]]
        _put(d, "date_column", ds.get("date_column"))
        _put(d, "cautions", ds.get("cautions"))
        cols = []
        for c in ds["columns"]:
            if c.get("technical"):
                continue
            cd = {"name": c["name"], "type": n.type(types[c["name"]]), "description": c["description"]}
            for k in ("unit", "role", "values", "value_semantics"):
                _put(cd, k, c.get(k))
            cols.append(cd)
        d["columns"] = cols
        out.append(d)
    return out


def _relationships(n: Namer) -> list[dict]:
    out = []
    for r in source()["relationships"]:
        d = {"from": n.ref(r["from"]), "to": n.ref(r["to"])}
        for k in ("cardinality", "orphan_rows", "use", "caution"):
            _put(d, k, r.get(k))
        out.append(d)
    return out


def _metrics_l1(n: Namer, with_callables: bool) -> list[dict]:
    l2 = {m["name"]: m for m in metrics_file()["metrics"]}
    out = []
    for m in source()["metrics"]:
        d = {"name": m["name"]}
        for k in ("aliases", "definition", "expression", "numerator", "denominator", "additivity", "unit"):
            _put(d, k, m.get(k))
        for k in ("dataset", "alternate_dataset", "denominator_dataset"):
            if m.get(k):
                d[k] = n.ref(m[k])
        _put(d, "only_dataset", m.get("only_dataset"))
        for k in ("default_filters", "conventions", "note"):
            _put(d, k, m.get(k))
        if with_callables:
            d["callables"] = [{"dataset": n.ref(ds), "call": n.call(dax, cube)}
                              for ds, dax, cube in metric_callables(l2[m["name"]])]
        out.append(d)
    return out


def _data_quality() -> list[dict]:
    # open_question points into decisions/open-questions.md — process bookkeeping, not content
    return [{k: v for k, v in q.items() if k != "open_question"} for q in source()["data_quality"]]


def _widetables(n: Namer) -> dict:
    wt = source()["widetables"]
    db = wt["database"]
    schema = physical_schema()[db]
    shared = {c for s in wt["shared_column_meanings"] for c in s["columns"]}
    views = []
    for v in wt["views"]:
        listed = {c["name"]: c for c in v["columns"]}
        d = {"name": n.table(v["name"], db)}
        for k in ("title", "subject"):
            d[k] = v[k]
        d["base"] = n.ref(v["base"].split(".", 1)[1])
        for k in ("grain", "rows", "row_count_equals_fact", "row_count_note", "description", "cautions"):
            _put(d, k, v.get(k))
        cols = []
        for name, ty in schema[v["name"]]:
            cd = {"name": name, "type": n.type(ty)}
            c = listed.get(name)
            if c is None and name not in shared:
                raise ValueError(f"{v['name']}.{name} 在 source.yaml 的 widetables 节里没有描述")
            if c is not None:
                if c.get("source"):
                    cd["source"] = n.ref(c["source"])
                _put(cd, "derived", c.get("derived"))
                _put(cd, "metric", c.get("metric"))
                cd["description"] = c["description"]
            cols.append(cd)
        d["columns"] = cols
        views.append(d)
    return {"shared_column_meanings": wt["shared_column_meanings"], "views": views}


def render_l1(n: Namer, *, widetables: bool = False, callables: bool = False) -> dict:
    ctx = {
        "model": _model_header(),
        "conventions": _conventions(n),
        "synonyms": _synonyms(n),
        "datasets": _datasets(n),
        "relationships": _relationships(n),
        "multi_path_defaults": source()["multi_path_defaults"],
        "metrics": _metrics_l1(n, callables),
        "data_quality": _data_quality(),
    }
    if widetables:
        ctx["widetables"] = _widetables(n)
    return _deep_text(ctx, n)


# ---------------------------------------------------------------------------
# L1.5S
# ---------------------------------------------------------------------------
_VIEW_RE = re.compile(
    r"CREATE OR REPLACE VIEW ads\.(?P<view>dim_\w+) AS\s+SELECT\s+(?P<select>.*?)\s+FROM retail\.(?P<base>\w+)"
    r"(?:\s+AS\s+(?P<alias>\w+))?(?P<rest>.*?);",
    re.S,
)
_JOIN_RE = re.compile(r"JOIN retail\.(\w+)\s+AS\s+(\w+)")
_ITEM_RE = re.compile(r"^(?P<expr>.+?)\s+AS\s+`(?P<name>[^`]+)`$", re.S)


def _split_select(select: str) -> list[str]:
    items, depth, cur = [], 0, ""
    for ch in select:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            items.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        items.append(cur.strip())
    return items


def ads_dimension_views() -> list[dict]:
    """Parse the ads.dim_* views in summary.sql: [{view, base, columns: [{name, expr, sources}]}]."""
    sql = (SEMANTIC / "summary" / "summary.sql").read_text(encoding="utf-8")
    sql = re.sub(r"--[^\n]*", "", sql)
    retail = physical_schema()["retail"]
    out = []
    for m in _VIEW_RE.finditer(sql):
        aliases = {m.group("alias") or m.group("base"): m.group("base")}
        aliases.update({a: t for t, a in _JOIN_RE.findall(m.group("rest"))})
        default_table = m.group("base")
        cols = []
        for item in _split_select(m.group("select")):
            im = _ITEM_RE.match(item)
            expr = " ".join(im.group("expr").split())
            sources = []
            for alias, col in re.findall(r"\b(\w+)\.(\w+)\b", expr):
                if alias in aliases:
                    sources.append(f"{aliases[alias]}.{col}")
            if not sources:
                names = {c for c, _ in retail[default_table]}
                sources = [f"{default_table}.{w}" for w in re.findall(r"\b\w+\b", expr) if w in names]
            direct = re.fullmatch(r"(?:\w+\.)?\w+", expr) is not None and len(sources) == 1
            cols.append({"name": im.group("name"), "expr": expr, "sources": sources, "direct": direct})
        out.append({"view": m.group("view"), "base": default_table, "columns": cols})
    return out


def _source_columns() -> dict[str, dict]:
    return {f"{ds['name']}.{c['name']}": c for ds in source()["datasets"] for c in ds["columns"]}


def _ads_column_descriptions() -> dict[str, str]:
    """Same-named columns in the ads summary tables, then in the dwd wide tables."""
    out: dict[str, str] = {}
    for t in summary()["tables"]:
        for c in t["columns"]:
            out.setdefault(c["name"], c["description"])
    wt = source()["widetables"]
    for v in wt["views"]:
        for c in v["columns"]:
            out.setdefault(c["name"], c["description"])
    for s in wt["shared_column_meanings"]:
        for c in s["columns"]:
            out.setdefault(c, s["description"])
    return out


def render_l15s(n: Namer) -> dict:
    s = summary()
    db = s["database"]
    schema = physical_schema()[db]
    src_cols = _source_columns()
    by_name = _ads_column_descriptions()
    titles = {ds["name"]: ds["title"] for ds in source()["datasets"]}

    datasets = []
    for t in s["tables"]:
        meta = {c["name"]: c for c in t["columns"]}
        cols = []
        for name, ty in schema[t["name"]]:
            c = meta[name]
            cd = {"name": name, "type": n.type(ty), "description": c["description"], "additivity": c["additivity"]}
            _put(cd, "metric", c.get("metric"))
            cols.append(cd)
        datasets.append({"name": n.table(t["name"], db), "kind": "summary", "title": t["title"],
                         "grain": t["grain"], "description": t["description"], "columns": cols})

    column_home: dict[str, str] = {}  # retail Table.Column → ads view column (for synonyms)
    views = {v["view"]: v for v in ads_dimension_views()}
    if set(views) != set(s["dimension_views"]):
        raise ValueError(f"summary.sql 的维度视图 {sorted(views)} 与 summary.yaml 的 {s['dimension_views']} 不一致")
    for vname in s["dimension_views"]:
        v = views[vname]
        meta = {c["name"]: c for c in v["columns"]}
        cols = []
        for name, ty in schema[vname]:
            c = meta[name]
            src = src_cols.get(c["sources"][0]) if c["direct"] else None
            desc = by_name.get(name) or (src or {}).get("description")
            if not desc:
                raise ValueError(f"ads.{vname}.{name} 找不到描述")
            cd = {"name": name, "type": n.type(ty), "description": desc}
            if src:
                _put(cd, "values", src.get("values"))
            cols.append(cd)
            for ref in c["sources"]:
                column_home.setdefault(ref, n.column(vname, name, db))
        datasets.append({"name": n.table(vname, db), "kind": "dimension", "title": titles[v["base"]],
                         "columns": cols})

    synonyms = []
    for syn in source()["synonyms"]:
        d = {"terms": syn["terms"]}
        if syn.get("maps_to_metric"):
            d["maps_to_metric"] = syn["maps_to_metric"]
        elif syn.get("maps_to_column") in column_home:
            d["maps_to_column"] = column_home[syn["maps_to_column"]]
        else:
            continue  # the column is not in the summary layer
        _put(d, "why", syn.get("why"))
        synonyms.append(d)

    metrics = []
    for m in source()["metrics"]:
        d = {"name": m["name"]}
        for k in ("aliases", "definition", "numerator", "denominator", "additivity", "unit", "default_filters"):
            _put(d, k, m.get(k))
        metrics.append(d)

    return {
        "model": _model_header(),
        "conventions": [{"id": c["id"], "group": c["group"], "rule": c["rule"]} for c in source()["conventions"]],
        "synonyms": synonyms,
        "datasets": datasets,
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# Leak checks for the degraded tiers
# ---------------------------------------------------------------------------
_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[^\x00-\x7f]+")
_CJK = re.compile(r"[　-鿿＀-￯]")


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for x in obj:
            yield from _strings(x)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _strings(v)


def business_names() -> set[str]:
    """Every database, table and column name in retail / dwd / ads."""
    snap = physical_schema()
    names = {"retail", "dwd", "ads"}
    for db in ("retail", "dwd", "ads"):
        for table, cols in snap[db].items():
            names.add(table)
            names.update(c for c, _ in cols)
    return names


def check_l0(ctx: dict, n: Namer) -> None:
    """L0 must not show a single retail / dwd / ads name, nor any description."""
    problems = []
    if set(ctx) != {"datasets", "relationships"}:
        problems.append(f"顶层键应只有 datasets、relationships，实际 {sorted(ctx)}")
    forbidden = business_names()
    snap = physical_schema()["l0"]
    allowed = {"l0"} | set(snap) | {c for cols in snap.values() for c, _ in cols}
    for d in ctx.get("datasets", []):
        if set(d) != {"name", "columns"}:
            problems.append(f"{d.get('name')} 的键应只有 name、columns，实际 {sorted(d)}")
        for c in d.get("columns", []):
            if set(c) != {"name", "type"}:
                problems.append(f"{d.get('name')}.{c.get('name')} 的键应只有 name、type")
    for r in ctx.get("relationships", []):
        if set(r) != {"from", "to"}:
            problems.append(f"关系 {r} 的键应只有 from、to")
    for s in _strings(ctx):
        if _CJK.search(s):
            problems.append(f"出现中文（L0 不得有任何描述）：{s[:60]!r}")
        for tok in _TOKEN.findall(s):
            if tok in forbidden:
                problems.append(f"漏出原名 {tok!r}（在 {s[:60]!r} 里）")
    for d in ctx.get("datasets", []):
        for name in [d["name"]] + [c["name"] for c in d["columns"]]:
            for tok in _TOKEN.findall(name):
                if tok not in allowed:
                    problems.append(f"名字 {tok!r} 不是 l0 库里的表名或列名")
    if problems:
        raise LeakError(f"L0（{n.stack}）泄漏校验未通过：\n  " + "\n  ".join(sorted(set(problems))[:50]))


def check_r(ctx: dict, n: Namer) -> None:
    """R shows only retail names and types: no description, no relationship, no other database."""
    problems = []
    if set(ctx) != {"datasets"}:
        problems.append(f"顶层键应只有 datasets，实际 {sorted(ctx)}")
    retail = physical_schema()["retail"]
    allowed = {"retail"} | set(retail) | {c for cols in retail.values() for c, _ in cols}
    for d in ctx.get("datasets", []):
        if set(d) != {"name", "columns"}:
            problems.append(f"{d.get('name')} 的键应只有 name、columns，实际 {sorted(d)}")
        for c in d.get("columns", []):
            if set(c) != {"name", "type"}:
                problems.append(f"{d.get('name')}.{c.get('name')} 的键应只有 name、type")
        for name in [d["name"]] + [c["name"] for c in d.get("columns", [])]:
            for tok in _TOKEN.findall(name):
                if tok not in allowed:
                    problems.append(f"名字 {tok!r} 不是 retail 库里的表名或列名")
    for s in _strings(ctx):
        if _CJK.search(s):
            problems.append(f"出现中文（R 不得有任何描述）：{s[:60]!r}")
    if problems:
        raise LeakError(f"R（{n.stack}）泄漏校验未通过：\n  " + "\n  ".join(sorted(set(problems))[:50]))


# ---------------------------------------------------------------------------
# Cells
# ---------------------------------------------------------------------------
def render_cell(cell: str) -> dict | None:
    """The context of one cell; None for a tuned cell whose tuning file does not exist yet."""
    stack, tier, tuning = CELLS[cell]
    n = Namer(stack)
    if tier == "R":
        ctx = render_r(n)
        check_r(ctx, n)
    elif tier == "L0":
        ctx = render_l0(n)
        check_l0(ctx, n)
    elif tier == "L1":
        ctx = render_l1(n)
    elif tier == "L1.5W":
        ctx = render_l1(n, widetables=True)
    elif tier == "L1.5S":
        ctx = render_l15s(n)
    elif tier == "L2":
        ctx = render_l1(n, callables=True)
    else:
        raise ValueError(tier)
    if tuning:
        path = tuning_file(tuning)
        if not path.exists():
            return None
        import yaml

        ctx["tuning"] = _deep_text(yaml.safe_load(path.read_text(encoding="utf-8")), n)
    return ctx


def main(argv: list[str]) -> None:
    cells = argv or list(CELLS)
    unknown = [c for c in cells if c not in CELLS]
    if unknown:
        sys.exit(f"未知单元：{unknown}；可选 {list(CELLS)}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for cell in cells:
        ctx = render_cell(cell)
        target = OUT_DIR / f"{cell}.yaml"
        if ctx is None:
            print(f"{cell}: 跳过（还没有 {tuning_file(CELLS[cell][2]).relative_to(SEMANTIC.parent)}）")
            continue
        text = dump_yaml(ctx)
        target.write_text(text, encoding="utf-8")
        print(f"{cell}: {target.relative_to(BUILD.parent)}（{len(text):,} 字符）")


if __name__ == "__main__":
    main(sys.argv[1:])
