"""T34: the whole semantic layer as an ontology (SQL-L3a-full)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import cells, prompt, run_direct
from render import context, l3a_full as L
from render.common import REPO, dump_yaml
from render.l1plus import SECTIONS, overlay

# Last commit before T34: every context that existed then must render byte-identically.
BEFORE_T34 = "96abbed2da316608d15ee608bbba6a8f5169531b"


@pytest.fixture(scope="module")
def source():
    ctx, data = L.l1_context(), overlay()
    return ctx, data, L.turtle(ctx, data)


@pytest.fixture(scope="module")
def parsed(source):
    return L.check(*source)


def test_round_trip_and_counts(source, parsed):
    ctx, data, _ = source
    c = L.counts(ctx, data, parsed)
    assert len(c["entries"]) == sum(len(data[s]) for s in SECTIONS) == 109
    assert {e[1] for e in c["entries"]} == {item["id"] for s in SECTIONS for item in data[s]}
    assert {e[2] for e in c["entries"]} == {L.FORMAL, L.ANNOTATED}
    assert c["annotation"] + c["formal"] == c["triples"]
    columns = [s for s in parsed.order if parsed.opt(s, ":sqlType") is not None]
    assert len(columns) == sum(len(ds["columns"]) for ds in ctx["datasets"])
    assert sum(len(parsed.all(s, ":enumValue")) for s in parsed.order) == sum(
        len(col.get("values", [])) for ds in ctx["datasets"] for col in ds["columns"])
    assert len([s for s in parsed.order if parsed.opt(s, ":joinFrom") is not None]) == len(ctx["relationships"])
    assert len(parsed.typed(":Metric")) == len(ctx["metrics"]) == 69


@pytest.mark.parametrize("mutation", [
    ("drop a column", "retail:FactOnlineSales.DateKey a owl:DatatypeProperty", "retail:FactOnlineSales.DateKeyX a owl:DatatypeProperty"),
    ("alter a description", "订单日期。粒度到天", "订单日期。粒度到月"),
    ("drop a ref", ":ref :约定2 , ", ":ref "),
    ("drop the case-insensitive flag", 'sh:pattern "^Blue$" ; sh:flags "i"', 'sh:pattern "^Blue$"'),
    ("drop a class shape", 'sh:property [ sh:path retail:DimEntity.EntityType ; sh:hasValue "Group" ]',
     'rdfs:comment "x"'),
    ("drop an enum value", ' , [ :code 307 ;', ' , [ :codeX 307 ;'),
])
def test_check_rejects_corruption(source, mutation):
    ctx, data, text = source
    _, old, new = mutation
    assert old in text
    with pytest.raises(ValueError):
        L.check(ctx, data, text.replace(old, new, 1))


def test_formal_meanings(parsed):
    p = parsed
    e07 = {L.text_of(p.one(b, ":value")): b for b in p.all(":E07", ":map")}
    blue = e07["Blue"]
    shape = p.one(blue, ":selects")
    assert p.one(shape, "sh:path") == "retail:DimProduct.ColorName"
    assert L.text_of(p.one(shape, "sh:pattern")) == "^Blue$" and L.text_of(p.one(shape, "sh:flags")) == "i"
    assert L.text_of(p.one(blue, ":filter")) == "lower(ColorName) = 'blue'"
    assert all(L.text_of(p.one(p.one(b, ":selects"), "sh:flags")) == "i" for b in e07.values())
    # H05: memberships written as "EntityType = 'Group'，3 个" are formalized too.
    for cls, value in (("class:集团级实体", "Group"), ("class:国家_地区级实体", "Country/Region"),
                       ("class:州级实体", "State"), ("class:门店实体", "Store")):
        prop = p.one(cls, "sh:property")
        assert p.one(prop, "sh:path") == "retail:DimEntity.EntityType"
        assert L.text_of(p.one(prop, "sh:hasValue")) == value
    # E09: conditions are conditions, lists are sh:in, names are equalities on PromotionName.
    e09 = p.all(":E09", ":map")
    no_discount = next(b for b in e09 if p.opt(b, ":condition") and L.text_of(p.one(b, ":condition")) == "PromotionKey = 1")
    assert L.value_of(p.one(p.one(no_discount, ":selects"), "sh:hasValue")) == 1
    discount = next(b for b in e09 if p.opt(b, ":condition") and L.text_of(p.one(b, ":condition")) == "PromotionKey != 1")
    assert isinstance(p.one(p.one(discount, ":selects"), "sh:not"), L.BNode)
    spring = next(b for b in e09 if "春促" in [L.text_of(x) for x in p.all(b, "skos:altLabel")])
    assert len(p.one(p.one(spring, ":selects"), "sh:in").items) == 3
    # Partitions, keys, account tree.
    assert len(p.all("class:门店", "owl:disjointUnionOf")) == 2
    assert [x for x in p.one("class:城市", "owl:hasKey").items] == ["retail:DimGeography.GeographyKey"]
    assert p.one("account:24", ":parentAccount") == "account:1"
    assert not p.all("account:1", ":parentAccount")
    assert len(p.one("account:3", ":leafAccounts").items) == 15
    # Hierarchy-only facts that are explicitly not rules stay text (H12).
    assert p.all("class:零库存组合", "rdfs:subClassOf") == ["class:门店产品组合"]   # not ⊑ 低于安全库存组合


def test_prompt_and_syntax_equal_l1plus(tmp_path, monkeypatch):
    monkeypatch.setattr(run_direct, "CONTEXTS", tmp_path)
    for name in ("SQL-L1plus", L.CELL):
        tmp_path.joinpath(name + ".yaml").write_text(dump_yaml(context.render_cell(name)), encoding="utf-8")
    full, plus = cells.L1PLUS_CELLS[L.CELL], cells.L1PLUS_CELLS["SQL-L1plus"]
    assert (full.syntax, full.allowed, full.instructions, full.skip_judge, full.split, full.stack) == \
        (plus.syntax, plus.allowed, plus.instructions, plus.skip_judge, plus.split, plus.stack)
    a, b = run_direct.system_for(full), run_direct.system_for(plus)
    head_a, rest_a = a.split(prompt.CONTEXT_HEADER, 1)
    head_b, rest_b = b.split(prompt.CONTEXT_HEADER, 1)
    assert head_a == head_b == prompt.SYSTEM_PROMPT + "\n\n"
    assert rest_a.split(prompt.SYNTAX_HEADER, 1)[1] == rest_b.split(prompt.SYNTAX_HEADER, 1)[1]
    assert L.CELL not in cells.CELLS          # opt-in only; --cell all keeps its scope
    ctx = yaml.safe_load(tmp_path.joinpath(L.CELL + ".yaml").read_text(encoding="utf-8"))
    assert list(ctx) == ["ontology_turtle"]   # the whole context is the ontology


def test_cli_resolves_cell_without_paid_calls(capsys):
    from harness.questions import Question

    def load(**kwargs):
        return [Question("Q_SYNTH", "synthetic", refs=[[[1]]], rules={"ordered": False,
                         "top_n": None, "tie_columns": [], "value_kinds": ["count"], "value_types": ["UInt64"],
                         "required_columns": [0]})]

    context.main([L.CELL])
    assert run_direct.main(["--cell", L.CELL, "--dry-run"], load=load) == 0
    assert L.CELL in capsys.readouterr().out


def test_existing_context_bytes_unchanged():
    old_source = subprocess.run(["git", "show", f"{BEFORE_T34}:render/context.py"], cwd=REPO,
                                capture_output=True, text=True, check=True).stdout
    namespace = {"__name__": "render._before_t34", "__package__": "render", "__file__": str(REPO / "render/context.py")}
    exec(compile(old_source, "pre-T34-context", "exec"), namespace)
    assert set(namespace["CELLS"]) == set(context.CELLS) - {L.CELL}
    for name in namespace["CELLS"]:
        old, new = namespace["render_cell"](name), context.render_cell(name)
        assert (None if old is None else dump_yaml(old)) == (None if new is None else dump_yaml(new)), name


def test_generic_turtle_parser_agrees(source, parsed):
    rdflib = pytest.importorskip("rdflib")
    graph = rdflib.Graph()
    graph.parse(data=source[2], format="turtle")
    assert len(graph) == len(parsed.triples())
