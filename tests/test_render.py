"""Renderer checks (T10). No database: everything renders from semantic/ and the
committed type snapshot render/physical_schema.json.

The Cube measures' SQL is checked against chDB separately:

    uv run python render/verify_cube.py
"""

from __future__ import annotations

import copy
import re
import sys
from functools import cache
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from data.ddl import tables as ddl_tables  # noqa: E402
from render import check_equivalence  # noqa: E402
from render.common import CUBE_NAMES, Namer, metric_callables, metrics_file, physical_schema, source  # noqa: E402
from render.context import CELLS, LeakError, business_names, check_l0, check_r, render_cell  # noqa: E402
from render.cube import build_model  # noqa: E402
from render.measures import cube_measures, dax_measures  # noqa: E402
from render.tmdl import Project  # noqa: E402

SYNTAX = REPO / "render" / "syntax"


@cache
def ctx(cell: str) -> dict:
    return render_cell(cell)


# ---------------------------------------------------------------------------
# L0 and R must not leak (user requirement, 2026-10-16; extends the T09 ruling)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cell", ["SQL-L0", "DAX-L0"])
def test_l0_passes_leak_check(cell: str) -> None:
    check_l0(ctx(cell), Namer(CELLS[cell][0]))


@pytest.mark.parametrize("cell", ["SQL-L0", "DAX-L0"])
def test_l0_shows_no_business_name_anywhere(cell: str) -> None:
    text = repr(ctx(cell))
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text))
    assert not tokens & business_names()


def test_l0_names_never_collide_with_business_names() -> None:
    """Otherwise the leak check could not tell an L0 name from a leaked one."""
    l0 = physical_schema()["l0"]
    names = set(l0) | {c for cols in l0.values() for c, _ in cols}
    assert not names & business_names()


@pytest.mark.parametrize("leak", [
    lambda c: c["datasets"][0]["columns"].append({"name": "SalesAmount", "type": "Float64"}),
    lambda c: c["datasets"].__setitem__(0, {**c["datasets"][0], "name": "FactOnlineSales"}),
    lambda c: c["relationships"].append({"from": "retail.FactSales.StoreKey", "to": "l0.d_str.stk"}),
    lambda c: c["datasets"][0]["columns"][0].__setitem__("description", "行的代理键"),
    lambda c: c.__setitem__("conventions", [{"rule": "x"}]),
    lambda c: c["datasets"][1]["columns"].append({"name": "宽表列", "type": "String"}),
])
def test_l0_leak_check_fails_hard(leak) -> None:
    bad = copy.deepcopy(ctx("SQL-L0"))
    leak(bad)
    with pytest.raises(LeakError):
        check_l0(bad, Namer("sql"))


def test_r_passes_leak_check() -> None:
    check_r(ctx("SQL-R"), Namer("sql"))


@pytest.mark.parametrize("leak", [
    lambda c: c.__setitem__("relationships", [{"from": "a", "to": "b"}]),
    lambda c: c["datasets"][0].__setitem__("description", "线上销售明细"),
    lambda c: c["datasets"][0]["columns"][0].__setitem__("description", "x"),
    lambda c: c["datasets"].append({"name": "dwd.wide_online_sales", "columns": []}),
    lambda c: c["datasets"][0]["columns"].append({"name": "amt1", "type": "Float64"}),
])
def test_r_leak_check_fails_hard(leak) -> None:
    bad = copy.deepcopy(ctx("SQL-R"))
    leak(bad)
    with pytest.raises(LeakError):
        check_r(bad, Namer("sql"))


def test_r_has_no_technical_columns() -> None:
    tech = {c["name"] for ds in source()["datasets"] for c in ds["columns"] if c.get("technical")}
    shown = {c["name"] for d in ctx("SQL-R")["datasets"] for c in d["columns"]}
    assert not tech & shown


def test_l0_pbip_has_no_business_name_outside_power_query() -> None:
    """The DAX-L0 model itself: only the Power Query rename step may name the source columns."""
    p = Project("L0")
    forbidden = business_names() - {"retail"}
    for ds in source()["datasets"]:
        text = p.table_file(ds, [])
        text = text.split("\tpartition ")[0]
        found = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)) & forbidden
        assert not found, f"{ds['name']}: {found}"
    rels = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", p.relationships_file())) & forbidden
    assert not rels


# ---------------------------------------------------------------------------
# Tier contents
# ---------------------------------------------------------------------------
def test_l1_hides_technical_columns_and_callables() -> None:
    c = ctx("SQL-L1")
    tech = {(ds["name"], col["name"]) for ds in source()["datasets"] for col in ds["columns"] if col.get("technical")}
    shown = {(d["name"].split(".", 1)[1], col["name"]) for d in c["datasets"] for col in d["columns"]}
    assert not tech & shown
    assert all("callables" not in m for m in c["metrics"])
    assert "widetables" not in c


def test_l15w_adds_widetables_only() -> None:
    w, l1 = ctx("SQL-L1.5W"), ctx("SQL-L1")
    assert {k: v for k, v in w.items() if k != "widetables"} == l1
    assert [v["name"] for v in w["widetables"]["views"]] == [f"dwd.{v['name']}" for v in source()["widetables"]["views"]]


def test_l15s_has_no_detail_fact_table() -> None:
    c = ctx("SQL-L1.5S")
    assert all(d["name"].startswith("ads.") for d in c["datasets"])
    assert {d["kind"] for d in c["datasets"]} == {"summary", "dimension"}
    assert not any(d["name"].split(".", 1)[1] in CUBE_NAMES for d in c["datasets"])
    ads = set(physical_schema()["ads"])
    assert {d["name"].split(".", 1)[1] for d in c["datasets"]} == ads


def test_l15s_synonym_columns_exist_in_ads() -> None:
    ads = physical_schema()["ads"]
    for s in ctx("SQL-L1.5S")["synonyms"]:
        if "maps_to_column" in s:
            _, view, col = s["maps_to_column"].split(".", 2)
            assert col in dict(ads[view]), s


def test_l2_each_stack_shows_only_its_own_call_syntax() -> None:
    for cell, pattern in [("SQL-L2", r"^MEASURE\(\w+\.\w+\)$"), ("JSON-L2", r"^\w+\.\w+$"), ("DAX-L2", r"^\[[^\]]+\]$")]:
        for m in ctx(cell)["metrics"]:
            for c in m["callables"]:
                assert re.match(pattern, c["call"]), (cell, c)


def test_dual_dataset_metrics_have_two_callables() -> None:
    by_name = {m["name"]: m for m in ctx("DAX-L2")["metrics"]}
    for m in metrics_file()["metrics"]:
        primary = [c for c in by_name[m["name"]]["callables"] if not c.get("scope")]   # variants carry a scope
        assert len(primary) == (2 if m.get("alternate_dataset") else 1)


def test_tuned_cells_merge_tuning_file(tmp_path, monkeypatch) -> None:
    import render.context as context

    (tmp_path / "SQL-L1.yaml").write_text("notes:\n  - 补充说明 FactSales\n", encoding="utf-8")
    monkeypatch.setattr(context, "tuning_file", lambda cell: tmp_path / f"{cell}.yaml")
    c = context.render_cell("SQL-L1-tuned")
    assert c["tuning"] == {"notes": ["补充说明 FactSales"]}
    assert {k: v for k, v in c.items() if k != "tuning"} == ctx("SQL-L1")
    assert context.render_cell("DAX-L2-tuned") is None


# ---------------------------------------------------------------------------
# Equivalence across stacks
# ---------------------------------------------------------------------------
def test_equivalence_holds() -> None:
    assert check_equivalence.run(load=ctx) == []


def test_equivalence_detects_a_difference() -> None:
    def tampered(cell: str) -> dict:
        c = copy.deepcopy(ctx(cell))
        if cell == "DAX-L1":
            c["datasets"][0]["columns"][1]["description"] += "（多一句）"
        return c

    assert check_equivalence.run(load=tampered)


def test_equivalence_detects_a_wrong_call() -> None:
    def tampered(cell: str) -> dict:
        c = copy.deepcopy(ctx(cell))
        if cell == "JSON-L2":
            c["metrics"][0]["callables"][0]["call"] = "sales.sales_amount"
        return c

    assert check_equivalence.run(load=tampered)


# ---------------------------------------------------------------------------
# Syntax notes
# ---------------------------------------------------------------------------
def _syntax_files() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(SYNTAX.glob("*.md"))}


def test_syntax_note_lengths(record_property) -> None:
    """Lengths of the four syntax notes (characters, whitespace removed).

    Stacks may differ in length (decisions/2026-10-19-self-built-p-and-cube-notes.md §五,
    open question T12-4): the target is teaching depth 2, rules plus conditions and pitfalls.
    The two Cube notes are at depth 2 and are exempt from the old equal-length rule (T10:
    within 10 %). ClickHouse (depth 1 in phase 1) and DAX are still held to it until DAX is
    raised to depth 2 before it runs; then this check goes too. All four lengths are recorded
    as test properties (``--junitxml``) and in the failure message."""
    files = _syntax_files()
    assert set(files) == {"clickhouse_sql.md", "cube_sql.md", "dax.md", "cube_json.md"}
    sizes = {name: len(re.sub(r"\s", "", text)) for name, text in files.items()}
    for name, n in sizes.items():
        record_property(f"syntax_chars_{name}", n)
    a, b = sizes["clickhouse_sql.md"], sizes["dax.md"]
    assert max(a, b) / min(a, b) <= 1.10, sizes


def test_syntax_notes_say_nothing_about_this_dataset() -> None:
    names = business_names() | set(CUBE_NAMES.values()) | {m["name"] for m in metrics_file()["metrics"]}
    names -= {"retail", "dwd", "ads"}
    for f, text in _syntax_files().items():
        tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)) | set(re.findall(r"[^\x00-\x7f]+", text))
        assert not tokens & names, (f, tokens & names)
        assert "2009" not in text and "2007" not in text, f
        assert "CANNOT_ANSWER" not in text, f


# ---------------------------------------------------------------------------
# Measures, Cube model, PBIP
# ---------------------------------------------------------------------------
def _callables() -> set[tuple[str, str]]:
    from render.common import variant_callables, variant_key
    return ({(m["name"], ds) for m in metrics_file()["metrics"] for ds, _, _ in metric_callables(m)}
            | {(variant_key(m["name"], vid), ds) for m in metrics_file()["metrics"]
               for vid, ds, _, _, _ in variant_callables(m)})


def test_every_callable_has_a_dax_and_a_cube_implementation() -> None:
    assert set(dax_measures()) == _callables()
    assert set(cube_measures()) == _callables()


def test_cube_model_carries_every_cube_member() -> None:
    model = build_model()
    members = {f"{c}.{m['name']}" for c, b in model.items() for m in b.get("measures", []) if m.get("public", True)}
    from render.common import variant_callables
    want = {cube for m in metrics_file()["metrics"] for _, _, cube in metric_callables(m)}
    want |= {cube for m in metrics_file()["metrics"] for _, _, _, cube, _ in variant_callables(m)}
    assert members == want
    assert set(model) == set(CUBE_NAMES.values())


def test_l2_pbip_defines_every_dax_measure_once() -> None:
    p = Project("L2")
    defined = []
    for ds in source()["datasets"]:
        from render.tmdl import dax_measures as impl  # same module the writer uses

        measures = [(dax[1:-1], expr, "") for m in metrics_file()["metrics"]
                    for d, dax, _ in metric_callables(m) for home, expr in [impl()[(m["name"], d)]] if home == ds["name"]]
        text = p.table_file(ds, measures)
        defined += re.findall(r"^\tmeasure (.+?) =", text, re.M)
    names = [n.strip("'").replace("''", "'") for n in defined]
    want = [dax[1:-1] for m in metrics_file()["metrics"] for _, dax, _ in metric_callables(m)]
    assert sorted(names) == sorted(want)


def test_pbip_relationship_counts() -> None:
    assert len(Project("L0").relationships()) == len([r for r in source()["relationships"]]) - 16
    self_joins = sum(1 for r in source()["relationships"] if r["from"].split(".")[0] == r["to"].split(".")[0])
    rels = Project("L1").relationships()
    assert len(rels) == len(source()["relationships"]) - self_joins
    assert sum(1 for *_, active in rels if not active) == 2


# ---------------------------------------------------------------------------
# Type snapshot
# ---------------------------------------------------------------------------
def test_snapshot_retail_types_match_the_ddl() -> None:
    snap = physical_schema()["retail"]
    for t in ddl_tables():
        assert snap[t.name] == list(t.columns), t.name


def test_snapshot_covers_every_rendered_object() -> None:
    snap = physical_schema()
    assert {ds["name"] for ds in source()["datasets"]} == set(snap["retail"])
    assert {v["name"] for v in source()["widetables"]["views"]} == set(snap["dwd"])
    assert len(snap["l0"]) == 25


def test_ladder_notes_t2_t3_say_nothing_about_this_dataset() -> None:
    """C13 (decisions/2026-10-19-phase1-replan.md §三): levels 2 and 3 carry no hint about this
    dataset or any question; level 4's few-shot examples come from tuning-split questions and are
    checked in tests/test_harness.py."""
    names = business_names() | set(CUBE_NAMES.values()) | {m["name"] for m in metrics_file()["metrics"]}
    names -= {"retail", "dwd", "ads"}
    for f in ("clickhouse_sql_t2.md", "clickhouse_sql_t3.md"):
        text = (REPO / "harness" / "syntax_ladder" / f).read_text(encoding="utf-8")
        tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)) | set(re.findall(r"[^\x00-\x7f]+", text))
        assert not tokens & names, (f, tokens & names)
        assert "2009" not in text and "2007" not in text and "2008" not in text, f
        assert "CANNOT_ANSWER" not in text, f


# ---------------------------------------------------------------------------
# Generic delivery check (a): names in conventions / metrics / synonyms are visible or mapped
# ---------------------------------------------------------------------------
def test_reference_check_flags_invisible_names_and_accepts_documented_ones() -> None:
    from render import check_references as CR
    ctx = {"datasets": [{"name": "ads.dim_store", "columns": [
               {"name": "面积", "description": "来自 DimStore.SellingAreaSize。"}]},
                        {"name": "ads.t", "columns": [{"name": "c"}]}],
           "metrics": [{"name": "m1", "definition": "看 DimStore.SellingAreaSize 与 ads.t.c", "only_dataset": True},
                       {"name": "m2", "definition": "看 DimStore.EmployeeCount", "dataset": "FactSales"}],
           "synonyms": [{"terms": ["x"], "maps_to_column": "t.c"}, {"terms": ["y"], "maps_to_column": "t.nope"}]}
    res = CR.check(ctx)
    assert {g["name"] for g in res["gaps"]} == {"DimStore.EmployeeCount", "FactSales", "t.nope"}
    assert {d["name"] for d in res["documented"]} == {"DimStore.SellingAreaSize"}
    dax = {"datasets": [{"name": "DimProduct", "columns": [{"name": "UnitPrice"}]}],
           "metrics": [{"name": "m", "callables": [{"call": "[Sales Amount]"}]}],
           "synonyms": [{"terms": ["p"], "maps_to_column": "DimProduct[UnitPrice]"},
                        {"terms": ["q"], "maps_to_column": "DimProduct[Nope]"}]}
    assert [g["name"] for g in CR.check(dax)["gaps"]] == ["DimProduct[Nope]"]


def test_every_rendered_context_names_only_visible_or_documented_objects() -> None:
    from render import check_references as CR
    contexts = sorted((REPO / "build" / "contexts").glob("*.yaml"))
    if not contexts:
        pytest.skip("contexts not rendered")
    gaps = {p.stem: CR.check(yaml.safe_load(p.read_text(encoding="utf-8")))["gaps"] for p in contexts}
    assert not {k: v for k, v in gaps.items() if v}, gaps


# ---------------------------------------------------------------------------
# Generic delivery check (b): coverage tables
# ---------------------------------------------------------------------------
def test_convention_citations_parse_lists_and_ranges_of_words() -> None:
    from render import check_conventions as CC
    assert CC.cites("按约定 1 和 2 选表；约定 5、约定 7 另说；约定12") == {1, 2, 5, 7, 12}
    assert CC.cites({"a": ["约定 2 + 约定 5"]}) == {2, 5}
    assert CC.logical("retail.FactSales") == "FactSales" and CC.logical("online_sales") == "FactOnlineSales"


def test_convention_row_verdicts_and_table_choice() -> None:
    from render import check_conventions as CC
    lin = {"ads_a": {"FactOnlineSales"}, "ads_b": {"FactSales"}}
    conv = {"id": 1, "applies_to_datasets": ["FactOnlineSales"]}
    ctx = {"conventions": [{"id": 1}],
           "datasets": [{"name": "ads.ads_a", "description": "电商。", "columns": []},
                        {"name": "ads.ads_b", "description": "全渠道（约定 2）。", "columns": []}],
           "metrics": [{"name": "m", "default_filters": ["约定 1"]}]}
    row = CC.convention_row(conv, "SQL-L1.5S", ctx, lin, {})
    assert row["verdict"] == "仅指标" and row["anchors"] == "1/1"
    assert [t["ok"] for t in CC.table_choice(ctx, lin)] == [False, True]
    ctx["datasets"][0]["columns"] = [{"name": "c", "description": "线上销售（约定 1）"}]
    assert CC.convention_row(conv, "SQL-L1.5S", ctx, lin, {})["verdict"] == "对象"
    assert all(t["ok"] for t in CC.table_choice(ctx, lin))
    ctx["metrics"] = []
    ctx["datasets"][0]["columns"] = []
    assert CC.convention_row(conv, "SQL-L1.5S", ctx, lin, {})["verdict"] == "仅条文"
    # outside L1.5S a visible anchor is enough
    l1 = {"conventions": [{"id": 1}], "datasets": [{"name": "retail.FactOnlineSales", "columns": []}], "metrics": []}
    assert CC.convention_row(conv, "SQL-L1", l1, lin, {})["verdict"] == "对象"


def test_every_sales_summary_table_says_which_sales_it_comes_from() -> None:
    from render import check_conventions as CC
    if not (REPO / "build" / "contexts" / "SQL-L1.5S.yaml").exists():
        pytest.skip("contexts not rendered")
    r = CC.run()
    assert len(r["table_choice"]) == 12 and all(t["ok"] for t in r["table_choice"]), r["table_choice"]
    for n in (1, 2):
        assert all(x["verdict"] == "对象" for x in r["conventions"] if x["convention"] == n)
    assert all(x["dax"] and x["cube"] and x["contexts_agree"] for x in r["dax_vs_cube"])


# ---------------------------------------------------------------------------
# semantic-v1.4: metric variants the L1 text states (range/variant check)
# ---------------------------------------------------------------------------
def test_variant_audit_quotes_l1_and_every_variant_has_both_engines() -> None:
    from render.check_conventions import VARIANT_TEXT, variant_audit
    from render.common import variant_callables
    texts = {m["name"]: " ".join(" ".join(str(m.get(k) or "") for k in ("definition", "note", "default_filters")).split())
             for m in source()["metrics"]}
    for name, (quote, _) in VARIANT_TEXT.items():
        assert quote in texts[name], (name, quote)                 # the quote is the L1 text itself
    rows = variant_audit()
    assert len(rows) == len(metrics_file()["metrics"]) == 69
    assert all(v["dax"] and v["cube"] for x in rows for v in x["variants"])
    with_variants = {m["name"] for m in metrics_file()["metrics"] if variant_callables(m)}
    assert with_variants <= set(VARIANT_TEXT)                       # a variant only where L1 states one


def test_variant_callables_reach_every_l2_context_with_their_scope() -> None:
    from render.common import variant_callables
    want = {(m["name"], ds, scope) for m in metrics_file()["metrics"] for _, ds, _, _, scope in variant_callables(m)}
    for cell in ("SQL-L2", "JSON-L2", "DAX-L2"):
        path = REPO / "build" / "contexts" / f"{cell}.yaml"
        if not path.exists():
            pytest.skip("contexts not rendered")
        ctx = yaml.safe_load(path.read_text(encoding="utf-8"))
        got = {(m["name"], c["scope"]) for m in ctx["metrics"] for c in m.get("callables") or [] if c.get("scope")}
        assert got == {(n, s) for n, _, s in want}, cell
    for cell in ("SQL-L1", "SQL-L1.5W", "SQL-L1.5S"):               # L1-series contexts carry no callables
        path = REPO / "build" / "contexts" / f"{cell}.yaml"
        if path.exists():
            assert "scope:" not in path.read_text(encoding="utf-8").split("metrics:", 1)[-1], cell


def test_cube_variant_members_are_multi_stage_where_they_need_the_engine() -> None:
    from render.common import variant_key
    from render.measures import cube_measures
    cube = cube_measures()
    for vid in ("渠道内", "品类内"):
        for (key, ds), specs in cube.items():
            if key == variant_key("销售额占比", vid):
                helper = specs[1]
                assert helper["multi_stage"] and helper["reduce_by"] and helper["public"] is False
    shifted = [s for (key, _), specs in cube.items() if key == variant_key("销售额环比增长率", "按季") for s in specs[1:]]
    assert shifted and all(s["time_shift"][0]["interval"] == "1 quarter" for s in shifted)
