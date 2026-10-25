"""T26: independent quality validation of the L3a ontology (OWL + SHACL Turtle).

    uv run --group ontology python -m scripts.t26.ontology_check [step ...]

Steps: syntax reason model shacl data missed (default: all). Each step writes
reports/validation/l3a-ontology/<step>.json. Free: no model calls. Reads the
L3a Turtle from the renderer (render/l1plus.py, unchanged) and checks it equals
the serialized SQL-L3a context; step 5 reads $SEMDEBT_DATA_DIR/parquet through
chDB without a data directory; step 6 reads the existing run logs and the
question bank's reference SQL (only question ids are written out).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote, unquote

import rdflib
import yaml
from rdflib import RDF, RDFS, OWL, Literal, Namespace, URIRef

from render.common import BUILD, REPO
from render.l1plus import PREFIXES, SECTIONS, Graph as EmittedGraph, overlay, turtle

OUT = REPO / "reports/validation/l3a-ontology"
L = Namespace(PREFIXES[""])
SH = Namespace("http://www.w3.org/ns/shacl#")
D = Namespace("urn:semdebt:t26:data:")
HERE = Path(__file__).resolve().parent
RUN = "20261025-T22b-l1plus-l3a-03-rescore-01"
CELLS = ("SQL-L3a", "SQL-L1plus")
SOURCE_TREE = {":sourceType", ":sourceValue", ":section", ":mode", "rdfs:comment", ":definitionSQL"}


def short(term) -> str:
    text = str(term)
    for p, url in PREFIXES.items():
        if text.startswith(url):
            return (p + ":" if p else ":") + unquote(text[len(url):])
    return text


def write(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                      encoding="utf-8")


def l3a_text() -> str:
    text = turtle(overlay())
    ctx = BUILD / "contexts/SQL-L3a.yaml"
    if not ctx.exists():
        raise SystemExit("run `uv run python -m render.l1plus` first (builds the SQL-L3a context)")
    if yaml.safe_load(ctx.read_text(encoding="utf-8"))["ontology_turtle"] != text:
        raise SystemExit("renderer output differs from the serialized SQL-L3a context")
    return text


def l3a_graph() -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(data=l3a_text(), format="turtle")
    return g


# ------------------------------------------------------------------ step 1
def step_syntax() -> dict:
    text = l3a_text()
    g = rdflib.Graph()
    g.parse(data=text, format="turtle")
    nt = g.serialize(format="nt")
    again = rdflib.Graph()
    again.parse(data=nt, format="nt")
    declared = dict(re.findall(r"^@prefix (\w*): <([^>]+)> \.$", text, re.MULTILINE))
    used = Counter()
    for triple in g:
        for term in triple:
            if isinstance(term, URIRef):
                ns = next((p for p, url in PREFIXES.items() if str(term).startswith(url)), None)
                used[ns if ns is not None else str(term)] += 1
    literals = [o for o in g.objects() if isinstance(o, Literal)]
    result = {
        "parser": f"rdflib {rdflib.__version__} (turtle)",
        "bytes_utf8": len(text.encode("utf-8")),
        "triples": len(g),
        "emitted_lines_parsed_by_generator_reader": len(EmittedGraph.read(text).triples),
        "ntriples_roundtrip_triples": len(again),
        "roundtrip_isomorphic": again.isomorphic(g),
        "declared_prefixes": declared,
        "iri_uses_by_namespace": dict(used),
        "literal_datatypes": dict(Counter(str(o.datatype) if o.datatype else ("lang" if o.language else "plain")
                                          for o in literals)),
        "parse_errors": [],
    }
    write("syntax", result)
    return result


# ------------------------------------------------------------------ step 2
def subclass_cycles(g: rdflib.Graph) -> list[list[str]]:
    edges = defaultdict(set)
    for s, o in g.subject_objects(RDFS.subClassOf):
        if s != o:
            edges[s].add(o)
    cycles, state = [], {}

    def visit(node, stack):
        state[node] = 1
        stack.append(node)
        for nxt in edges[node]:
            if state.get(nxt) == 1:
                cycles.append([short(x) for x in stack[stack.index(nxt):]])
            elif nxt not in state:
                visit(nxt, stack)
        stack.pop()
        state[node] = 2

    for n in list(edges):
        if n not in state:
            visit(n, [])
    return cycles


def step_reason() -> dict:
    import owlrl
    from owlrl.Namespaces import ERRNS

    g = l3a_graph()
    asserted_types = set(g.triples((None, RDF.type, None)))
    closure = rdflib.Graph()
    for t in g:
        closure.add(t)
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, axiomatic_triples=False, datatype_axioms=False).expand(closure)
    errors = [str(m) for e in closure.subjects(RDF.type, ERRNS.ErrorMessage) for m in closure.objects(e, ERRNS.error)]
    classes = set(g.subjects(RDF.type, OWL.Class))
    builtin = {OWL.Thing, OWL.Nothing, RDFS.Resource, OWL.NamedIndividual, RDFS.Class, OWL.Class}
    new_types = sorted(
        (short(s), short(o)) for s, p, o in closure.triples((None, RDF.type, None))
        if (s, p, o) not in asserted_types and o in classes and o not in builtin)
    # Mutual subsumption between distinct named classes in the closure = cycle or equivalence.
    sub = {(s, o) for s, o in closure.subject_objects(RDFS.subClassOf) if s in classes and o in classes and s != o}
    equivalent = sorted({tuple(sorted((short(a), short(b)))) for a, b in sub if (b, a) in sub})
    unsat = sorted(short(c) for c in classes if (c, RDFS.subClassOf, OWL.Nothing) in closure
                   or (c, OWL.equivalentClass, OWL.Nothing) in closure)
    individuals = set(g.subjects(RDF.type, OWL.NamedIndividual))
    punned = sorted(short(x) for x in classes & individuals)
    # OWL 2 DL structural notes: properties used without a declaration.
    declared = {s for s, o in g.subject_objects(RDF.type)
                if o in (OWL.AnnotationProperty, OWL.ObjectProperty, OWL.DatatypeProperty)}
    builtin_props = {RDF.type, RDFS.label, RDFS.comment, RDFS.subClassOf, RDFS.domain, RDFS.range, RDF.first, RDF.rest}
    undeclared = Counter(short(p) if not str(p).startswith(str(RDF)) or not re.search(r"#_\d+$", str(p)) else "rdf:_n"
                         for p in g.predicates() if p not in declared and p not in builtin_props)
    java = shutil.which("java")
    if java and subprocess.run([java, "-version"], capture_output=True).returncode != 0:
        java = None  # macOS ships a /usr/bin/java stub that fails without a JRE
    result = {
        "reasoner": f"owlrl {owlrl.__version__} OWL-RL closure (axiomatic and datatype axioms off)",
        "asserted_triples": len(g), "closure_triples": len(closure),
        "inconsistency_messages": errors,
        "owl_Nothing_members": sorted(short(x) for x in closure.subjects(RDF.type, OWL.Nothing)),
        "unsatisfiable_named_classes": unsat,
        "asserted_subclass_cycles": subclass_cycles(g),
        "equivalent_named_class_pairs_in_closure": equivalent,
        "new_named_class_memberships": new_types,
        "named_classes": len(classes), "named_individuals": len(individuals),
        "class_and_individual_punning": punned,
        "undeclared_predicates_used": dict(undeclared),
        "dl_reasoner": ("java found at " + java) if java else
        "not run: no Java runtime on this machine (HermiT / Pellet need one); not installed by this card",
    }
    write("reason", result)
    return result


# ------------------------------------------------------------------ step 3
EQ = re.compile(r"^(\w+) = ('([^']*)'|(\d+))(?=（|；|$)")   # the generator's rule
EQ_LOOSE = re.compile(r"^(\w+) = ('([^']*)'|(\d+))")


def iri(name: str) -> URIRef:
    return URIRef(PREFIXES[""] + quote(name, safe=""))


def class_iri(name: str) -> URIRef:
    return iri("class/" + re.sub(r"（H\d+）$", "", name))


def step_model() -> dict:
    data = overlay()
    g = l3a_graph()
    rep = lambda ident: set(g.objects(L[ident], L.represents))  # noqa: E731
    entries = {}
    label_owner = defaultdict(set)
    for item in data["aliases"]:
        ident, rows = item["id"], []
        nodes = rep(ident)
        for i, m in enumerate(item["map"]):
            node = iri(f"alias/{ident}/{i}")
            labels = {str(x) for x in g.objects(node, RDFS.label)}
            values = [str(x) for x in g.objects(node, L.value)]
            cols = [str(x) for x in g.objects(node, L.column)]
            for t in m["terms"]:
                label_owner[t].add((ident, i))
            v = m["value"]
            expected_value = [str(v)] if isinstance(v, (str, int)) else []
            rows.append({
                "i": i, "in_represents": node in nodes,
                "labels_equal_terms": labels == set(m["terms"]),
                "value_ok": values == expected_value,
                "value_kind": type(v).__name__,
                "value_is_predicate": isinstance(v, str) and bool(re.search(r"\s(=|!=)\s", v)),
                "column_ok": cols == [m.get("column", item["column"])],
                "dropped_fields": sorted(set(m) - {"terms", "value", "column"}),
            })
        entries[ident] = {
            "section": "aliases", "mappings": len(rows),
            "all_labels_equal": all(r["labels_equal_terms"] for r in rows),
            "all_values_ok": all(r["value_ok"] for r in rows),
            "all_columns_ok": all(r["column_ok"] for r in rows),
            "no_formal_value": [r["i"] for r in rows if r["value_kind"] in ("list", "dict")],
            "predicate_values": [r["i"] for r in rows if r["value_is_predicate"]],
            "dropped_fields": sorted({f for r in rows for f in r["dropped_fields"]}),
            "dropped_item_fields": sorted(set(item) - {"id", "entity", "column", "map", "note", "rev"}),
            "note_only_in_comment": "note" in item,
        }
    collisions = {t: sorted(f"{a}/{b}" for a, b in owners) for t, owners in label_owner.items() if len(owners) > 1}
    class_owner = defaultdict(set)
    for item in data["hierarchies"]:
        ident = item["id"]
        nodes = rep(ident)
        classes, memberships, relations = [], [], []
        for cls in item.get("classes", []):
            node = class_iri(cls["class"])
            class_owner[node].add(ident)
            parents = set(g.objects(node, RDFS.subClassOf))
            expect_parent = {class_iri(cls["parent"])} if cls.get("parent") else set()
            classes.append({"class": cls["class"], "in_represents": node in nodes,
                            "parent_ok": parents == expect_parent})
            if "membership" in cls:
                mem = cls["membership"]
                strict, loose = EQ.match(mem), EQ_LOOSE.match(mem)
                shape = iri(f"shape/{ident}/{cls['class']}")
                has_shape = (shape, RDF.type, SH.NodeShape) in g
                kind = ("equality-formalized" if strict else
                        "equality-missed-by-generator" if loose else
                        "other-operator" if re.match(r"^\w+ (!=|<|>|IN)", mem) else "prose")
                value_ok = None
                if has_shape:
                    con = next(g.objects(shape, SH.property))
                    hv = next(g.objects(con, SH.hasValue))
                    want = strict[3] if strict[3] is not None else int(strict[4])
                    value_ok = hv.toPython() == want and short(next(g.objects(con, SH.path))) == ":" + strict[1]
                memberships.append({"class": cls["class"], "kind": kind, "shape": has_shape, "shape_ok": value_ok})
        for i, rel in enumerate(item.get("relations", [])):
            node = iri(f"relation/{ident}/{i}")
            relations.append({
                "relation": rel["relation"], "via": rel["via"],
                "domain_ok": set(g.objects(node, RDFS.domain)) == {class_iri(rel["from"])},
                "range_ok": set(g.objects(node, RDFS.range)) == {class_iri(rel["to"])},
                "is_object_property": (node, RDF.type, OWL.ObjectProperty) in g})
        tree = None
        if item.get("nodes"):
            mism = []
            for row in item["nodes"]:
                key = re.search(r"（(\d+)）$", row["account"])[1]
                parents = [short(o) for o in g.objects(iri("account/" + key), L.parentAccount)]
                want = [":account/" + str(row["parent_account"])] if row.get("parent_account") is not None else []
                if parents != want:
                    mism.append(key)
            tree = {"nodes": len(item["nodes"]), "parent_mismatches": mism,
                    "kind_leaf_fields_formal": False}
        constraints = item.get("constraints", [])
        entries[ident] = {
            "section": "hierarchies", "classes": classes, "memberships": memberships, "relations": relations,
            "account_tree": tree,
            "constraints_mentioning_disjoint_or_covering": sum(("互斥" in c or "覆盖" in c) for c in constraints),
            "constraints_total": len(constraints),
        }
    shared_classes = {short(c): sorted(o) for c, o in class_owner.items() if len(o) > 1}
    rel_by_via = defaultdict(list)
    for item in data["hierarchies"]:
        for i, rel in enumerate(item.get("relations", [])):
            via = rel["via"].split("（")[0]
            rel_by_via[via].append(f"{item['id']}/{i} {rel['from']}→{rel['to']}")
    same_column_relations = {k: v for k, v in rel_by_via.items() if len(v) > 1}
    dprops = sorted(set(g.subjects(RDF.type, OWL.DatatypeProperty)) | set(g.subjects(RDF.type, OWL.ObjectProperty)))
    no_domain_range = sorted(short(p) for p in dprops
                             if not str(p).startswith(str(L) + "relation") and
                             not (set(g.objects(p, RDFS.domain)) and set(g.objects(p, RDFS.range))))
    path_users = defaultdict(set)
    for con in g.subjects(RDF.type, SH.PropertyShape):
        for shape in g.subjects(SH.property, con):
            for tc in g.objects(shape, SH.targetClass):
                path_users[short(next(g.objects(con, SH.path)))].add(short(tc))
    multi_typed = sorted(short(s) for s in set(g.subjects(RDF.type, None))
                         if len(set(g.objects(s, RDF.type)) - {OWL.NamedIndividual}) > 1)
    plan_class = class_iri("计划、目标记录")
    scen = [class_iri(n) for n in ("Actual", "Budget", "Forecast")]
    result = {
        "entries": entries,
        "alias_label_collisions": collisions,
        "class_iri_shared_by_entries": shared_classes,
        "relations_on_same_column": same_column_relations,
        "inverse_or_equivalent_property_axioms": len(list(g.subject_objects(OWL.inverseOf))) +
        len(list(g.subject_objects(OWL.equivalentProperty))),
        "disjointness_axioms": len(list(g.subject_objects(OWL.disjointWith))) +
        len(list(g.subjects(RDF.type, OWL.AllDisjointClasses))) + len(list(g.subject_objects(OWL.disjointUnionOf))),
        "properties_without_domain_or_range": no_domain_range,
        "shape_paths_shared_across_target_classes": {k: sorted(v) for k, v in path_users.items() if len(v) > 1},
        "nodes_with_more_than_one_class_type": multi_typed,
        "H10_scenario_classes_subclass_of_plan_record": [((c, RDFS.subClassOf, plan_class) in g) for c in scen],
        "account_individuals_typed_with_a_class": sum(
            1 for s in g.subjects(L.parentAccount, None)
            if set(g.objects(s, RDF.type)) - {OWL.NamedIndividual}),
        "label_predicate": "rdfs:label holds every synonym term (no skos:altLabel / language tag)",
    }
    write("model", result)
    return result


# ------------------------------------------------------------------ step 4
def step_shacl() -> dict:
    import pyshacl

    g = l3a_graph()
    meta = pyshacl.validate(data_graph=rdflib.Graph(), shacl_graph=g, meta_shacl=True, advanced=True)
    shapes = sorted(set(g.subjects(RDF.type, SH.NodeShape)))
    probes = []
    for shape in shapes:
        target = next(g.objects(shape, SH.targetClass))
        for con in g.objects(shape, SH.property):
            path = next(g.objects(con, SH.path))
            hv = next(g.objects(con, SH.hasValue), None)
            allowed = list(rdflib.collection.Collection(g, next(g.objects(con, SH["in"]), RDF.nil)))
            good = hv if hv is not None else allowed[0]
            bad = Literal("__probe__")
            res = {}
            for label, value in (("good", good), ("bad", bad), ("missing", None)):
                data = rdflib.Graph()
                x = D["probe"]
                data.add((x, RDF.type, target))
                if value is not None:
                    data.add((x, path, value))
                res[label] = pyshacl.validate(data_graph=data, shacl_graph=g)[0]
            probes.append({"shape": short(shape), "target": short(target), "path": short(path),
                           "kind": "hasValue" if hv is not None else "in+count", **res})
    result = {
        "engine": f"pyshacl {pyshacl.__version__}",
        "meta_shacl_conforms": meta[0],
        "node_shapes": len(shapes),
        "property_shapes": len(set(g.subjects(RDF.type, SH.PropertyShape))),
        "probes": probes,
        "every_shape_accepts_good": all(p["good"] for p in probes),
        "every_shape_rejects_bad": all(not p["bad"] for p in probes),
        "every_shape_rejects_missing": all(not p["missing"] for p in probes),
        "on_l3a_itself_as_data": pyshacl.validate(data_graph=g, shacl_graph=g, inference="rdfs")[0],
    }
    write("shacl", result)
    return result


# ------------------------------------------------------------------ step 5
CASE_COLUMNS = {
    "DimAccount": ["AccountName", "AccountType", "ValueType"],
    "DimEmployee": ["Title", "Gender", "PayFrequency", "DepartmentName", "Status", "SalaryStatus",
                    "IsSalesPerson", "IsMarried"],
    "DimProduct": ["ProductName", "Manufacturer", "BrandName", "ClassName", "StyleName", "ColorName",
                   "WeightUnitMeasureID", "UnitOfMeasureName", "StockTypeName", "Status"],
    "DimProductSubcategory": ["ProductSubcategoryName"],
}


def parquet(table: str) -> str:
    return f"file('{os.environ['SEMDEBT_DATA_DIR']}/parquet/{table}.parquet', 'Parquet')"


def rows(sql: str) -> list[dict]:
    import chdb
    return json.loads(str(chdb.query(sql, "JSON")))["data"]


def node(kind: str, key) -> URIRef:
    return D[f"{kind}/{int(float(key))}"]


def instance_graph() -> tuple[rdflib.Graph, dict]:
    g = rdflib.Graph()
    stats = {}

    def add_dim(table, cls, kind, key, parent=None, extra=()):
        cols = [key] + ([parent] if parent else []) + list(extra) + CASE_COLUMNS.get(table, [])
        data = rows(f"SELECT {', '.join(dict.fromkeys(cols))} FROM {parquet(table)}")
        tnode = D["table/" + table]
        for r in data:
            x = node(kind, r[key])
            g.add((x, RDF.type, D[cls]))
            g.add((x, D.inTable, tnode))
            if parent and r[parent] is not None:
                g.add((x, D.parent, node(kind, r[parent])))
            for c in CASE_COLUMNS.get(table, []):
                if r[c] is not None:
                    g.add((x, D["col_" + c], Literal(r[c])))
        stats[table] = len(data)
        return data

    add_dim("DimAccount", "Account", "account", "AccountKey", "ParentAccountKey")
    add_dim("DimEmployee", "Employee", "employee", "EmployeeKey", "ParentEmployeeKey")
    add_dim("DimEntity", "Entity", "entity", "EntityKey", "ParentEntityKey")
    add_dim("DimProductSubcategory", "Subcategory", "subcategory", "ProductSubcategoryKey")
    products = add_dim("DimProduct", "Product", "product", "ProductKey", extra=["ProductSubcategoryKey"])
    for r in products:
        if r["ProductSubcategoryKey"] is not None:
            g.add((node("product", r["ProductKey"]), D.subcategory, node("subcategory", r["ProductSubcategoryKey"])))
    # Fact rows compressed to one instance per distinct ProductKey, carrying its exact row count.
    keys = rows(f"SELECT ProductKey, count() AS n FROM {parquet('FactOnlineSales')} GROUP BY ProductKey")
    for r in keys:
        x = node("osk", r["ProductKey"])
        g.add((x, RDF.type, D.OnlineSalesProductKey))
        g.add((x, D.refersProduct, node("product", r["ProductKey"])))
        g.add((x, D.rowCount, Literal(int(r["n"]))))
    stats["FactOnlineSales distinct ProductKey"] = len(keys)
    stats["FactOnlineSales rows"] = sum(int(r["n"]) for r in keys)
    return g, stats


def data_shapes() -> rdflib.Graph:
    text = (HERE / "data-shapes.ttl").read_text(encoding="utf-8")
    template = re.search(r'sh:select """(SELECT \$this \?value \?other.*?)"""', text, re.S)[1]
    extra = ["@prefix : <urn:semdebt:t26:data:> .", "@prefix sh: <http://www.w3.org/ns/shacl#> ."]
    for table, cols in CASE_COLUMNS.items():
        for c in cols:
            q = template.replace("$PATH", ":col_" + c)
            extra.append(f':Case_{table}_{c} a sh:NodeShape ; sh:targetNode <urn:semdebt:t26:data:table/{table}> ;'
                         f' sh:sparql [ a sh:SPARQLConstraint ; sh:prefixes :prefixDecl ;'
                         f' sh:message "{table}.{c}: same value in different letter case" ;'
                         f' sh:select """{q}""" ] .')
    g = rdflib.Graph()
    g.parse(data=text, format="turtle")
    g.parse(data="\n".join(extra), format="turtle")
    return g


def step_data() -> dict:
    import pyshacl

    inst, stats = instance_graph()
    shapes = data_shapes()
    conforms, report, _ = pyshacl.validate(data_graph=inst, shacl_graph=shapes, advanced=True, allow_infos=True)
    found = defaultdict(list)
    for r in report.subjects(RDF.type, SH.ValidationResult):
        src = report.value(r, SH.sourceShape)
        shape = next((short(s) for s in shapes.subjects(SH.property, src)), None) or short(src)
        shape = shape.replace("urn:semdebt:t26:data:", "")
        focus = str(report.value(r, SH.focusNode)).replace("urn:semdebt:t26:data:", "")
        val = report.value(r, SH.value)
        sev = short(report.value(r, SH.resultSeverity)).split("#")[-1]
        found[shape].append({"focus": focus, "value": None if val is None else str(val).replace(
            "urn:semdebt:t26:data:", ""), "severity": sev})
    for v in found.values():
        v.sort(key=lambda x: (x["focus"], str(x["value"])))
    orphan_keys = [x["focus"] for x in found.get("FKOnlineSalesProduct", [])]
    orphan_rows = sum(int(inst.value(D[k], D.rowCount)) for k in orphan_keys)
    case_rows = {}
    for shape, hits in found.items():
        if shape.startswith("Case_"):
            _, table, col = shape.split("_", 2)
            others = set()
            for h in hits:
                others |= {o for o in inst.objects(None, D["col_" + col])
                           if str(o).lower() == str(h["value"]).lower()}
            case_rows[shape] = {str(o): sum(1 for _ in inst.subjects(D["col_" + col], o)) for o in others}
    # L3a's own formal content against the raw data: the account tree (H07) vs ParentAccountKey,
    # and the L3a H10 scenario shape on plan / quota rows (one instance per distinct key).
    l3a = l3a_graph()
    acc = rows(f"SELECT AccountKey, ParentAccountKey FROM {parquet('DimAccount')}")
    raw_parent = {str(r["AccountKey"]): (None if r["ParentAccountKey"] is None else str(int(r["ParentAccountKey"])))
                  for r in acc}
    onto_parent = {}
    for s in set(l3a.subjects(RDF.type, OWL.NamedIndividual)):
        name = short(s)
        if name.startswith(":account/"):
            p = l3a.value(s, L.parentAccount)
            onto_parent[name.split("/")[1]] = None if p is None else short(p).split("/")[1]
    tree_diff = sorted(k for k in set(raw_parent) | set(onto_parent) if raw_parent.get(k) != onto_parent.get(k))
    plan = rdflib.Graph()
    for table in ("FactStrategyPlan", "FactSalesQuota"):
        for r in rows(f"SELECT ScenarioKey, count() AS n FROM {parquet(table)} GROUP BY ScenarioKey"):
            x = D[f"{table}/scenario/{r['ScenarioKey']}"]
            plan.add((x, RDF.type, class_iri("计划、目标记录")))
            plan.add((x, L.ScenarioKey, Literal(int(r["ScenarioKey"]))))
    h10 = pyshacl.validate(data_graph=plan, shacl_graph=l3a)
    result = {
        "instances": stats, "instance_triples": len(inst),
        "sampling": "none: every row of the four dimension tables; FactOnlineSales compressed to one instance per "
                    "distinct ProductKey with its exact row count (orphan rows = sum over violating keys)",
        "parent_columns": "raw ParentAccountKey / ParentEmployeeKey / ParentEntityKey, before L1+ breaks cycles",
        "conforms": conforms,
        "results_by_shape": {k: {"count": len(v), "results": v[:60]} for k, v in sorted(found.items())},
        "orphan_product_keys": len(orphan_keys), "orphan_fact_rows": orphan_rows,
        "case_value_rows": case_rows,
        "l3a_account_tree_vs_raw_parent_diff": {k: {"raw": raw_parent.get(k), "l3a": onto_parent.get(k)}
                                                for k in tree_diff},
        "l3a_H10_shape_on_plan_scenario_keys": {"conforms": h10[0], "instances": len(set(plan.subjects()))},
    }
    write("data", result)
    return result


# ------------------------------------------------------------------ step 6
def ref_sql() -> dict[str, list[str]]:
    from harness.questions import eval_dir, question_files

    out = {}
    for path in question_files(eval_dir()):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for rec in data["questions"] if isinstance(data, dict) else data:
            out[str(rec["id"])] = [r.get("sql") or "" for r in rec["refs"]]
    return out


def outcomes() -> dict[str, dict[str, int]]:
    res = {}
    for cell in CELLS:
        per = defaultdict(int)
        seen = Counter()
        for line in (REPO / "runs" / RUN / f"{cell}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            seen[r["qid"]] += 1
            per[r["qid"]] += r["final"]["outcome"] == "correct"
        assert set(seen.values()) == {3}, cell
        res[cell] = dict(per)
    return res


def step_missed() -> dict:
    from harness.questions import load_questions, verify_eval_tag

    from scripts.t26.preregistered import FORMAL, FORMALIZABLE

    verify_eval_tag("eval-v1.2")
    qs = load_questions()
    all_ids = {q.qid for q in qs if q.scoring != "judge"}
    main_ids = {q.qid for q in qs if q.qid in all_ids and not q.meta["low_discrimination"]}
    assert len(all_ids) == 109 and len(main_ids) == 98
    sql = ref_sql()
    out = outcomes()
    assert set(out["SQL-L3a"]) == all_ids

    def involve(pattern):
        rx = re.compile(pattern, re.I)
        return sorted(q for q in all_ids if any(rx.search(s) for s in sql[q]))

    def summary(ids):
        ids = sorted(ids)
        row = {"questions": ids, "n": len(ids), "n_main": len(set(ids) & main_ids)}
        for cell in CELLS:
            tag = "l3a" if cell == "SQL-L3a" else "l1plus"
            row[f"{tag}_wrong"] = sorted(q for q in ids if out[cell][q] < 3)
            row[f"{tag}_all_wrong"] = sorted(q for q in ids if out[cell][q] == 0)
            row[f"{tag}_correct_attempts"] = sum(out[cell][q] for q in ids)
        row["l3a_wrong_main"] = sorted(set(row["l3a_wrong"]) & main_ids)
        return row

    formal = {e: summary(involve(p)) for e, p in FORMAL.items()}
    shallow = {e: {"construct": c, **summary(involve(p))} for e, (c, p) in FORMALIZABLE.items()}
    union = set().union(*(set(v["questions"]) for v in shallow.values()))
    result = {
        "run": RUN, "rules": "scripts/t26/preregistered.py (committed before outcomes were read)",
        "questions": len(all_ids), "main": len(main_ids),
        "overall": summary(all_ids),
        "formal_entries": formal, "formalizable_annotation_entries": shallow,
        "formalizable_union": summary(union),
    }
    write("missed", result)
    return result


STEPS = {"syntax": step_syntax, "reason": step_reason, "model": step_model, "shacl": step_shacl,
         "data": step_data, "missed": step_missed}


def main(argv: list[str]) -> None:
    for name in argv or list(STEPS):
        result = STEPS[name]()
        brief = {k: v for k, v in result.items() if not isinstance(v, (dict, list)) or len(json.dumps(v)) < 300}
        print(name, json.dumps(brief, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main(sys.argv[1:])
