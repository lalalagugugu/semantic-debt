"""Lossless L1+ overlay / OWL + SHACL presentation and correspondence audit.

    uv run python -m render.l1plus

No rule engine is run. The small Turtle reader deliberately accepts only the
single-triple, named-node subset emitted here; malformed or duplicate triples fail.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from urllib.parse import quote

import yaml

from render.common import BUILD, REPO, SEMANTIC

SECTIONS = ("general_rules", "clarifications", "concepts", "aliases", "hierarchies")
PREFIXES = {
    "": "urn:semdebt:l1plus:",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "sh": "http://www.w3.org/ns/shacl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}


def without_rev(value):
    if isinstance(value, dict):
        return {k: without_rev(v) for k, v in value.items() if k != "rev"}
    if isinstance(value, list):
        return [without_rev(v) for v in value]
    return value


def overlay() -> dict:
    return without_rev(yaml.safe_load((SEMANTIC / "l1plus.yaml").read_text(encoding="utf-8")))


def literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False).replace("\\b", "\\u0008").replace("\\f", "\\u000c")


def iri(name: str) -> str:
    return "<" + PREFIXES[""] + quote(name, safe="") + ">"


class Graph:
    def __init__(self):
        self.triples: set[tuple[str, str, str]] = set()

    def add(self, subject: str, predicate: str, obj: str):
        self.triples.add((subject, predicate, obj))

    def text(self) -> str:
        headers = [f"@prefix {p}: <{url}> ." for p, url in PREFIXES.items()]
        return "\n".join(headers + [""] + [f"{s} {p} {o} ." for s, p, o in sorted(self.triples)]) + "\n"

    @classmethod
    def read(cls, text: str):
        graph = cls()
        prefixes = {}
        for line in text.splitlines():
            if not line.strip():
                continue
            header = re.fullmatch(r"@prefix (\w*): <([^>]+)> \.", line)
            if header:
                prefixes[header[1]] = header[2]
                continue
            match = re.fullmatch(r'(<[^>]+>|[\w:]+) ([\w:]+) (.+) \.', line)
            if not match:
                raise ValueError(f"Invalid emitted Turtle: {line[:100]}")
            s, p, obj = match.groups()
            if obj.startswith('"'):
                # All source scalars are annotation strings containing JSON.
                json.loads(obj)
            elif not re.fullmatch(r"<[^>]+>|[\w:]+|\d+", obj):
                raise ValueError(f"Invalid Turtle object: {obj}")
            if (s, p, obj) in graph.triples:
                raise ValueError("Duplicate triple")
            graph.add(s, p, obj)
        if prefixes != PREFIXES:
            raise ValueError("Unexpected namespaces")
        return graph

    def objects(self, subject: str, predicate: str) -> list[str]:
        return sorted(o for s, p, o in self.triples if s == subject and p == predicate)

    def one(self, subject: str, predicate: str) -> str:
        values = self.objects(subject, predicate)
        if len(values) != 1:
            raise ValueError(f"Expected one {predicate} on {subject}, got {len(values)}")
        return values[0]


def source_tree(g: Graph, node: str, value):
    """Annotation tree preserves every field, scalar type and list position."""
    if isinstance(value, (dict, list)):
        g.add(node, ":sourceType", literal("mapping" if isinstance(value, dict) else "sequence"))
        items = value.items() if isinstance(value, dict) else enumerate(value)
        for key, child in items:
            target = ":s" + str(len(g.triples)) if isinstance(child, (dict, list)) else literal(json.dumps(child, ensure_ascii=False))
            predicate = ":field_" + str(key) if isinstance(value, dict) else "rdf:_" + str(key + 1)
            g.add(node, predicate, target)
            if isinstance(child, (dict, list)):
                source_tree(g, target, child)
    else:
        g.add(node, ":sourceValue", literal(json.dumps(value, ensure_ascii=False)))


def read_tree(g: Graph, node: str):
    if node.startswith('"'):
        return json.loads(json.loads(node))
    kinds = g.objects(node, ":sourceType")
    if not kinds:
        return json.loads(json.loads(g.one(node, ":sourceValue")))
    kind = json.loads(g.one(node, ":sourceType"))
    fields = [(p, o) for s, p, o in g.triples if s == node and (p.startswith(":field_") or p.startswith("rdf:_"))]
    if kind == "mapping":
        return {p.removeprefix(":field_"): read_tree(g, o) for p, o in fields}
    fields.sort(key=lambda pair: int(pair[0].removeprefix("rdf:_")))
    if [p for p, _ in fields] != [f"rdf:_{i + 1}" for i in range(len(fields))]:
        raise ValueError("Broken sequence")
    return [read_tree(g, o) for _, o in fields]


def class_node(g: Graph, name: str) -> str:
    name = re.sub(r"（H\d+）$", "", name)
    node = iri("class/" + name)
    g.add(node, "rdf:type", "owl:Class")
    g.add(node, "rdfs:label", literal(name))
    return node


def rdf_list(g: Graph, name: str, values: list[str]) -> str:
    if not values:
        return "rdf:nil"
    nodes = [iri(f"list/{name}/{i}") for i in range(len(values))]
    for i, (node, value) in enumerate(zip(nodes, values)):
        g.add(node, "rdf:first", value)
        g.add(node, "rdf:rest", nodes[i + 1] if i + 1 < len(nodes) else "rdf:nil")
    return nodes[0]


def formalize(g: Graph, section: str, item: dict) -> bool:
    entry = ":" + item["id"]
    if section == "aliases":
        selection = class_node(g, "实例别名的取值选择")
        g.add(":value", "rdf:type", "owl:DatatypeProperty")
        for i, mapping in enumerate(item["map"]):
            node = iri(f"alias/{item['id']}/{i}")
            g.add(entry, ":represents", node)
            g.add(node, "rdf:type", "owl:NamedIndividual")
            g.add(node, "rdf:type", selection)
            # Labels belong to a contextual selection, never owl:sameAs between
            # strings, disjunctions, date predicates or different rows.
            for term in mapping["terms"]:
                g.add(node, "rdfs:label", literal(term))
            value = mapping["value"]
            if isinstance(value, (str, int)):
                g.add(node, ":value", literal(str(value)))
            g.add(node, ":column", literal(mapping.get("column", item["column"])))
        return True
    if section != "hierarchies":
        return False
    for cls in item.get("classes", []):
        node = class_node(g, cls["class"])
        g.add(entry, ":represents", node)
        if cls.get("parent"):
            g.add(node, "rdfs:subClassOf", class_node(g, cls["parent"]))
        if "membership" in cls:
            g.add(node, ":membership", literal(cls["membership"]))
            # Only a literal equality at the start of an explicit membership
            # definition is translated. Prose, ranges with dates and SQL stay annotations.
            equality = re.match(r"^(\w+) = ('([^']*)'|(\d+))(?=（|；|$)", cls["membership"])
            if equality:
                field, _, string, number = equality.groups()
                prop = ":" + field
                shape = iri(f"shape/{item['id']}/{cls['class']}")
                constraint = iri(f"constraint/{item['id']}/{cls['class']}")
                g.add(prop, "rdf:type", "owl:DatatypeProperty")
                g.add(prop, ":column", literal(field))
                g.add(shape, "rdf:type", "sh:NodeShape")
                g.add(shape, "sh:targetClass", node)
                g.add(shape, "sh:property", constraint)
                g.add(constraint, "rdf:type", "sh:PropertyShape")
                g.add(constraint, "sh:path", prop)
                g.add(constraint, "sh:hasValue", number if number is not None else literal(string))
                g.add(entry, ":represents", shape)
    for i, rel in enumerate(item.get("relations", [])):
        node = iri(f"relation/{item['id']}/{i}")
        g.add(entry, ":represents", node)
        g.add(node, "rdf:type", "owl:ObjectProperty")
        g.add(node, "rdfs:label", literal(rel["relation"]))
        g.add(node, "rdfs:domain", class_node(g, rel["from"]))
        g.add(node, "rdfs:range", class_node(g, rel["to"]))
        g.add(node, ":column", literal(rel["via"]))
    # H07 is a tree of account individuals, explicitly not a class hierarchy.
    for row in item.get("nodes", []):
        key = re.search(r"（(\d+)）$", row["account"])[1]
        node = iri("account/" + key)
        g.add(entry, ":represents", node)
        g.add(node, "rdf:type", "owl:NamedIndividual")
        g.add(node, "rdfs:label", literal(row["account"]))
        if row.get("parent_account") is not None:
            g.add(node, ":parentAccount", iri("account/" + str(row["parent_account"])))
    if item["id"] == "H07":
        g.add(":parentAccount", "rdf:type", "owl:ObjectProperty")
    if item["id"] == "H10":
        # Explicit H10 constraint: a plan/target row has exactly one of three
        # scenarios. Shapes are presentation only; no SHACL engine is invoked.
        prop = ":ScenarioKey"
        g.add(prop, "rdf:type", "owl:DatatypeProperty")
        g.add(prop, ":column", literal("ScenarioKey"))
        g.add(":H10Shape", "rdf:type", "sh:NodeShape")
        g.add(":H10Shape", "sh:targetClass", class_node(g, "计划、目标记录"))
        g.add(":H10Shape", "sh:property", ":H10Scenario")
        g.add(":H10Scenario", "rdf:type", "sh:PropertyShape")
        g.add(":H10Scenario", "sh:path", prop)
        g.add(":H10Scenario", "sh:minCount", "1")
        g.add(":H10Scenario", "sh:maxCount", "1")
        g.add(":H10Scenario", "sh:in", rdf_list(g, "H10", ["1", "2", "3"]))
        g.add(entry, ":represents", ":H10Shape")
    return True


def turtle(data: dict) -> str:
    g = Graph()
    for name in ("sourceType", "sourceValue", "section", "mode", "definitionSQL", "membership", "column", "represents"):
        g.add(":" + name, "rdf:type", "owl:AnnotationProperty")
    def declare_fields(value):
        if isinstance(value, dict):
            for key, child in value.items():
                g.add(":field_" + key, "rdf:type", "owl:AnnotationProperty")
                declare_fields(child)
        elif isinstance(value, list):
            for child in value:
                declare_fields(child)
    declare_fields(data)
    source_tree(g, ":metadata", {k: v for k, v in data.items() if k not in SECTIONS})
    seen = set()
    for section in SECTIONS:
        for item in data[section]:
            ident = item["id"]
            if ident in seen or not re.fullmatch(r"[ADEHG]\d+[a-z]?", ident):
                raise ValueError(f"Invalid or duplicate entry ID: {ident}")
            seen.add(ident)
            node = ":" + ident
            source_tree(g, node, item)
            g.add(node, ":section", literal(section))
            mode = "形式化" if formalize(g, section, item) else "注解保留"
            g.add(node, ":mode", literal(mode))
            for field in ("rule", "definition", "note"):
                if field in item:
                    g.add(node, "rdfs:comment", literal(item[field]))
            if "sql" in item:
                g.add(node, ":definitionSQL", literal(item["sql"]))
    return g.text()


def check(data: dict, text: str) -> list[tuple[str, str, str]]:
    g = Graph.read(text)
    expected = {":" + item["id"] for section in SECTIONS for item in data[section]}
    actual = {s for s, p, _ in g.triples if p == ":mode"}
    if expected != actual:
        raise ValueError(f"Entry mismatch: missing {expected - actual}, extra {actual - expected}")
    if read_tree(g, ":metadata") != {k: v for k, v in data.items() if k not in SECTIONS}:
        raise ValueError("Metadata mismatch")
    rows = []
    for section in SECTIONS:
        for item in data[section]:
            node = ":" + item["id"]
            if read_tree(g, node) != item:
                raise ValueError(f"Source field mismatch: {item['id']}")
            if json.loads(g.one(node, ":section")) != section:
                raise ValueError(f"Section mismatch: {item['id']}")
            mode = json.loads(g.one(node, ":mode"))
            if mode not in {"形式化", "注解保留"}:
                raise ValueError(f"Invalid mode: {item['id']}")
            if "sql" in item and json.loads(g.one(node, ":definitionSQL")) != item["sql"]:
                raise ValueError(f"SQL mismatch: {item['id']}")
            rows.append((section, item["id"], mode))
    # Also catches deleted/altered OWL relations or shapes, not just intact annotations.
    if g.triples != Graph.read(turtle(data)).triples:
        raise ValueError("Formal structure differs from the source-derived graph")
    return rows


def main():
    from render.common import dump_yaml
    from render.context import render_cell

    data = overlay()
    text = turtle(data)
    rows = check(data, text)
    counts = Counter(mode for _, _, mode in rows)
    BUILD.joinpath("contexts").mkdir(parents=True, exist_ok=True)
    for name in ("SQL-L1plus", "SQL-L3a"):
        BUILD.joinpath("contexts", name + ".yaml").write_text(dump_yaml(render_cell(name)), encoding="utf-8")
    # Audit the actual serialized contexts too, rather than only an in-memory source.
    plus = yaml.safe_load(BUILD.joinpath("contexts/SQL-L1plus.yaml").read_text(encoding="utf-8"))
    l3a = yaml.safe_load(BUILD.joinpath("contexts/SQL-L3a.yaml").read_text(encoding="utf-8"))
    check(plus.pop("l1plus"), l3a.pop("ontology_turtle"))
    if plus != render_cell("SQL-L1") or l3a != plus:
        raise ValueError("L1 base changed")
    lines = ["# L1+ / L3a 逐条对应核对", "", "复现：`uv run python -m render.l1plus`。", "",
             f"共 {len(rows)} 条：形式化 {counts['形式化']} 条；注解保留 {counts['注解保留']} 条。编号集合、节、全部字段（递归去掉 rev）、标量类型与列表顺序一致。",
             "", "形式化按条目计：存在 OWL 结构或 SHACL shape 即归此类；不代表该条全部口径均已形式化。所有条目的原始字段仍完整保留为注解树，复杂定义不转成规则。",
             "", "OWL 表达类、子类、对象属性、数据属性、实例别名和科目实例树；类成员定义开头的明确字面等式用 SHACL hasValue，H10 的单场景要求用 minCount / maxCount / in。未从行数、示例或别名子集推导必填、闭合枚举或范围约束。",
             "", "L3a 测的是「形式化写法对写 SQL 的模型有没有帮助」，不含可执行规则；不运行 SHACL 引擎，不编译查询。可执行形式化放在第二期 L3b。",
             "", "核对器解析生成器使用的 Turtle 子集，并逐字段反解比较；同时比较 OWL / SHACL 结构。它不是通用 RDF 或 OWL 推理器。", "",
             "| 节 | 编号 | 表达方式 |", "|---|---|---|"]
    lines += [f"| {section} | {ident} | {mode} |" for section, ident, mode in rows]
    report = REPO / "reports/validation/l1plus-l3a-correspondence.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} entries checked: {dict(counts)}; {report.relative_to(REPO)}")


if __name__ == "__main__":
    main()
