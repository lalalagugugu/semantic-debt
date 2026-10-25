"""T22b: lossless presentation, semantic structures and frozen-cell regression."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import cells, prompt, run_direct
from render import context, l1plus
from render.common import REPO, dump_yaml


def test_overlay_and_ontology_share_every_field():
    data = l1plus.overlay()
    assert "rev" not in repr(data)
    rows = l1plus.check(data, l1plus.turtle(data))
    assert len(rows) == sum(len(data[s]) for s in l1plus.SECTIONS)
    assert {mode for _, _, mode in rows} == {"形式化", "注解保留"}
    for name, extra in (("SQL-L1plus", "l1plus"), ("SQL-L3a", "ontology_turtle")):
        rendered = yaml.safe_load(dump_yaml(context.render_cell(name)))
        rendered.pop(extra)
        assert dump_yaml(rendered) == dump_yaml(context.render_cell("SQL-L1"))


@pytest.mark.parametrize("mutation", ["missing", "sql", "mode", "subclass", "shape", "extra"])
def test_correspondence_rejects_corruption(mutation):
    data = l1plus.overlay()
    graph = l1plus.Graph.read(l1plus.turtle(data))
    predicate = {"missing": ":mode", "sql": ":definitionSQL", "mode": ":mode",
                 "subclass": "rdfs:subClassOf", "shape": "sh:maxCount"}.get(mutation)
    if mutation == "extra":
        graph.add(":A999", ":mode", l1plus.literal("注解保留"))
    else:
        triple = next(t for t in sorted(graph.triples) if t[1] == predicate)
        graph.triples.remove(triple)
        if mutation in {"sql", "mode"}:
            graph.add(triple[0], triple[1], l1plus.literal("altered"))
    with pytest.raises(ValueError):
        l1plus.check(data, graph.text())


def test_owl_and_shacl_meanings():
    graph = l1plus.Graph.read(l1plus.turtle(l1plus.overlay()))
    assert (l1plus.iri("class/线上店"), "rdfs:subClassOf", l1plus.iri("class/虚拟门店")) in graph.triples
    assert (l1plus.iri("account/24"), ":parentAccount", l1plus.iri("account/1")) in graph.triples
    assert not graph.objects(l1plus.iri("account/1"), ":parentAccount")
    for predicate in ("sh:minCount", "sh:maxCount"):
        assert graph.one(":H10Scenario", predicate) == "1"
    constraint = l1plus.iri("constraint/H02/实体店")
    assert graph.one(constraint, "sh:hasValue") == l1plus.literal("Store")
    assert graph.one(constraint, "sh:path") == ":StoreType"
    assert not any(p in {"sh:rule", "owl:sameAs"} for _, p, _ in graph.triples)


def test_prompt_and_syntax_equal_l1(tmp_path, monkeypatch):
    monkeypatch.setattr(run_direct, "CONTEXTS", tmp_path)
    systems = {}
    known = {**cells.CELLS, **cells.L1PLUS_CELLS}
    for name in ("SQL-L1", "SQL-L1plus", "SQL-L3a"):
        tmp_path.joinpath(name + ".yaml").write_text(dump_yaml(context.render_cell(name)), encoding="utf-8")
        cell = known[name]
        assert cell.syntax == cells.CELLS["SQL-L1"].syntax
        assert cell.allowed == cells.CELLS["SQL-L1"].allowed
        assert cell.instructions is None
        systems[name] = run_direct.system_for(cell)
    for system in systems.values():
        prefix, rest = system.split(prompt.CONTEXT_HEADER, 1)
        assert prefix == prompt.SYSTEM_PROMPT + "\n\n"
        assert rest.split(prompt.SYNTAX_HEADER, 1)[1] == systems["SQL-L1"].split(prompt.SYNTAX_HEADER, 1)[1]
    assert cells.L1PLUS_CELLS["SQL-L1plus"].skip_judge
    assert cells.L1PLUS_CELLS["SQL-L3a"].skip_judge
    assert not cells.CELLS.keys() & cells.L1PLUS_CELLS.keys()


def test_new_cells_resolve_in_cli_without_paid_calls(capsys):
    from harness.questions import Question

    def load(**kwargs):
        return [Question("Q_SYNTH", "synthetic", refs=[[[1]]], rules={"ordered": False,
                         "top_n": None, "tie_columns": [], "value_kinds": ["count"], "value_types": ["UInt64"],
                         "required_columns": [0]}),
                Question("Q_JUDGE", "synthetic", refs=None, rules=None, scoring="judge")]

    assert run_direct.main(["--cell", "SQL-L1plus", "--cell", "SQL-L3a", "--dry-run"], load=load) == 0
    output = capsys.readouterr().out
    assert "SQL-L1plus" in output and "SQL-L3a" in output


def test_existing_context_bytes_unchanged():
    # Load the actual pre-T22b renderer committed in this clone, using the same
    # frozen sources. Compare every pre-existing output, not just SQL-L1.
    old_source = subprocess.run(["git", "show", "d236e13b719db6fe0c29e5a88af6c127929ac12f:render/context.py"], cwd=REPO,
                                capture_output=True, text=True, check=True).stdout
    namespace = {"__name__": "render._before_t22b", "__package__": "render", "__file__": str(REPO / "render/context.py")}
    exec(compile(old_source, "pre-T22b-context", "exec"), namespace)
    for name in namespace["CELLS"]:
        if name in {"SQL-L1plus", "SQL-L3a"}:
            continue
        old, new = namespace["render_cell"](name), context.render_cell(name)
        assert (None if old is None else dump_yaml(old)) == (None if new is None else dump_yaml(new)), name
