"""T26 ontology validation: the checks themselves behave as claimed (no Parquet, no run logs)."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

rdflib = pytest.importorskip("rdflib", reason="uv run --group ontology pytest tests/test_t26_ontology.py")
pyshacl = pytest.importorskip("pyshacl")

from rdflib import RDF, Literal  # noqa: E402

from scripts.t26 import ontology_check as oc  # noqa: E402
from scripts.t26.preregistered import FORMAL, FORMALIZABLE  # noqa: E402

D = oc.D


def test_signatures_compile_and_cover_formal_entries():
    assert set(FORMAL) == {f"E{i:02d}" for i in range(1, 18)} | {f"H{i:02d}" for i in range(1, 14)}
    for pattern in list(FORMAL.values()) + [p for _, p in FORMALIZABLE.values()]:
        re.compile(pattern, re.I)


def test_l3a_parses_and_reasons_clean():
    g = rdflib.Graph()
    g.parse(data=oc.turtle(oc.overlay()), format="turtle")
    assert len(g) == len(oc.EmittedGraph.read(oc.turtle(oc.overlay())).triples)
    assert oc.subclass_cycles(g) == []


def test_subclass_cycle_detector_finds_a_cycle():
    g = rdflib.Graph()
    a, b = D.A, D.B
    g.add((a, rdflib.RDFS.subClassOf, b))
    g.add((b, rdflib.RDFS.subClassOf, a))
    assert oc.subclass_cycles(g)


def _validate(data):
    ok, report, _ = pyshacl.validate(data_graph=data, shacl_graph=oc.data_shapes(), advanced=True, allow_infos=True)
    shapes = {str(report.value(r, oc.SH.sourceShape)) for r in report.subjects(RDF.type, oc.SH.ValidationResult)}
    return ok, shapes, report


def test_data_shapes_fire_on_cycle_orphan_and_case():
    g = rdflib.Graph()
    for k, parent in ((1, 24), (24, 1), (2, 24)):
        g.add((D[f"account/{k}"], RDF.type, D.Account))
        g.add((D[f"account/{k}"], D.parent, D[f"account/{parent}"]))
    g.add((D["osk/9"], RDF.type, D.OnlineSalesProductKey))
    g.add((D["osk/9"], D.refersProduct, D["product/9"]))
    for k, colour in ((1, "Blue"), (2, "blue"), (3, "Red")):
        g.add((D[f"product/{k}"], RDF.type, D.Product))
        g.add((D[f"product/{k}"], D.inTable, D["table/DimProduct"]))
        g.add((D[f"product/{k}"], D.col_ColorName, Literal(colour)))
    ok, shapes, report = _validate(g)
    assert not ok
    assert str(D.AcyclicAccount) in shapes and str(D.Case_DimProduct_ColorName) in shapes
    cyc = {str(report.value(r, oc.SH.focusNode)) for r in report.subjects(RDF.type, oc.SH.ValidationResult)
           if report.value(r, oc.SH.sourceShape) == D.AcyclicAccount}
    assert cyc == {str(D["account/1"]), str(D["account/24"])}  # 2 reaches the cycle but is not on it
    assert any("osk/9" in str(report.value(r, oc.SH.focusNode))
               for r in report.subjects(RDF.type, oc.SH.ValidationResult))


def test_data_shapes_accept_clean_data():
    g = rdflib.Graph()
    g.add((D["entity/1"], RDF.type, D.Entity))
    g.add((D["entity/1"], D.parent, D["entity/1"]))      # self root: Info only
    g.add((D["product/1"], RDF.type, D.Product))
    g.add((D["product/1"], D.inTable, D["table/DimProduct"]))
    g.add((D["product/1"], D.col_ColorName, Literal("Blue")))
    g.add((D["osk/1"], RDF.type, D.OnlineSalesProductKey))
    g.add((D["osk/1"], D.refersProduct, D["product/1"]))
    ok, shapes, _ = _validate(g)
    assert ok
    assert shapes == {str(D.SelfRootInfo)}
