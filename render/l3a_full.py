"""T34: the whole semantic layer (L1 + the 109 L1+ entries) as one OWL + SHACL ontology.

    uv run python -m render.l3a_full

Input: the SQL-L1 context (render.context.render_l1, i.e. semantic/source.yaml) and
semantic/l1plus.yaml (render.l1plus.overlay). Output: build/contexts/SQL-L3a-full.yaml
(a single `ontology_turtle` key, like the old SQL-L3a) and
reports/validation/l3a-full-correspondence.md.

Every source field is carried by a named predicate, so `decode` rebuilds the SQL-L1
context and the L1+ overlay from the parsed Turtle; `check` requires both to be equal
to the source. Formal axioms (OWL classes, properties, keys, partitions, individuals,
SHACL shapes) are added next to the annotations; the original text always stays.
No reasoner or SHACL engine is run.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass

from render.common import BUILD, REPO
from render.l1plus import SECTIONS, overlay

CELL = "SQL-L3a-full"
REPORT = REPO / "reports/validation/l3a-full-correspondence.md"

PREFIXES = {
    "": "urn:semdebt:l3a-full:",
    "retail": "urn:semdebt:retail:",
    "rel": "urn:semdebt:relationship:",
    "metric": "urn:semdebt:metric:",
    "class": "urn:semdebt:class:",
    "account": "urn:semdebt:account:",
    "dq": "urn:semdebt:data-quality:",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "sh": "http://www.w3.org/ns/shacl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
}

# Vocabulary of this ontology: name → (kind, Chinese gloss). kind: class / ann
# (owl:AnnotationProperty, text kept verbatim) / obj (owl:ObjectProperty) / data
# (owl:DatatypeProperty). Annotation triples are the "注解" side of the counts.
VOCAB = {
    "FactTable": ("class", "事实表（类的实例是表里的行）"),
    "DimensionTable": ("class", "维度表（类的实例是表里的行）"),
    "Convention": ("class", "企业约定"),
    "Synonym": ("class", "同义词"),
    "MultiPathDefault": ("class", "多路径时的默认路径"),
    "Metric": ("class", "指标"),
    "DataQualityIssue": ("class", "数据质量问题"),
    "GeneralRule": ("class", "L1+ 通则"),
    "Clarification": ("class", "L1+ 歧义澄清"),
    "Concept": ("class", "L1+ 业务概念"),
    "AliasSet": ("class", "L1+ 实例别名（说法 → 取值）"),
    "Hierarchy": ("class", "L1+ 层级"),
    "asOfDate": ("data", "数据截止日（今天）"),
    "currency": ("data", "币种"),
    "version": ("data", "版本"),
    "base": ("ann", "基于"),
    "grainNote": ("ann", "粒度提示"),
    "group": ("ann", "分组"),
    "rule": ("ann", "规则原文"),
    "note": ("ann", "说明"),
    "appliesToDataset": ("obj", "适用的表"),
    "appliesToColumn": ("obj", "适用的字段"),
    "metric": ("obj", "相关指标"),
    "why": ("ann", "理由"),
    "mapsToMetric": ("obj", "落到的指标"),
    "mapsToColumn": ("obj", "落到的字段"),
    "defaultDataset": ("obj", "默认的表"),
    "rows": ("data", "行数"),
    "grain": ("ann", "粒度"),
    "whenToUse": ("ann", "何时使用"),
    "differsFrom": ("obj", "与另一张表的区别"),
    "dataset": ("obj", "表"),
    "how": ("ann", "区别在哪"),
    "dateColumn": ("obj", "日期字段"),
    "caution": ("ann", "注意"),
    "sqlType": ("data", "ClickHouse 类型（写 SQL 时以此为准）"),
    "unit": ("ann", "单位"),
    "role": ("ann", "角色"),
    "enumValue": ("obj", "枚举取值（个体：code 是库里的取值，meaning 是含义）"),
    "code": ("data", "库里的取值"),
    "meaning": ("ann", "取值的含义"),
    "valueSemantics": ("ann", "取值的语义"),
    "joinFrom": ("obj", "连接起点字段"),
    "joinTo": ("obj", "连接终点字段"),
    "cardinality": ("ann", "基数"),
    "orphanRows": ("data", "连不上的行数"),
    "use": ("ann", "何时走这条关系"),
    "pair": ("ann", "起止"),
    "path": ("obj", "候选路径"),
    "route": ("ann", "路径原文"),
    "hops": ("obj", "路径经过的关系（有序；owl:inverseOf 表示反向走）"),
    "default": ("ann", "默认路径"),
    "definition": ("ann", "定义原文"),
    "sqlExpression": ("ann", "SQL 表达式"),
    "numerator": ("ann", "分子"),
    "denominator": ("ann", "分母"),
    "additivity": ("ann", "可加性"),
    "alternateDataset": ("obj", "备选表"),
    "denominatorDataset": ("obj", "分母所在的表"),
    "onlyDataset": ("data", "只能用 dataset 这张表"),
    "defaultFilter": ("ann", "默认筛选"),
    "convention": ("obj", "依据的约定"),
    "severity": ("ann", "严重程度"),
    "detail": ("ann", "详情"),
    "impact": ("ann", "影响"),
    "workaround": ("ann", "处理办法"),
    "topic": ("ann", "主题"),
    "ref": ("obj", "引用的 L1 内容（无法解析成节点的引用保留原文）"),
    "appliesWhen": ("ann", "适用条件"),
    "exception": ("ann", "例外"),
    "sql": ("ann", "SQL 片段"),
    "column": ("ann", "字段原文"),
    "onColumn": ("obj", "作用的字段"),
    "map": ("obj", "说法 → 取值（个体，skos:altLabel 是说法）"),
    "value": ("data", "取值"),
    "key": ("data", "键值"),
    "level": ("ann", "层级"),
    "op": ("data", "比较运算"),
    "filter": ("ann", "筛选的 SQL 写法"),
    "selects": ("obj", "选中的行（SHACL 形状）"),
    "account": ("obj", "对应的科目"),
    "noExactMapping": ("obj", "库里分不出的说法"),
    "within": ("data", "只能区分到的取值"),
    "noExactMappingRule": ("ann", "分不出时怎么办"),
    "class": ("obj", "层级里的类"),
    "membership": ("ann", "成员定义原文"),
    "identity": ("ann", "身份原文"),
    "relation": ("obj", "层级里的关系"),
    "via": ("ann", "经由原文"),
    "viaRelationship": ("obj", "经由的 L1 关系"),
    "constraint": ("ann", "约束原文"),
    "node": ("obj", "树上的节点"),
    "parentAccount": ("obj", "上级科目"),
    "kind": ("ann", "科目类别"),
    "leaf": ("data", "是叶子科目"),
    "leafAccounts": ("obj", "子树的全部叶子科目"),
    "breakCycle": ("obj", "断环"),
    "root": ("obj", "根"),
    "ignoreParentOf": ("obj", "忽略其上级的节点"),
    "rootKey": ("data", "根的键值"),
    "axiom": ("obj", "公理"),
    "storeTypeChannel": ("obj", "门店类型与渠道的对应"),
    "storeType": ("data", "门店类型"),
    "channelKey": ("data", "渠道键"),
    "definedBy": ("obj", "定义见"),
    "defaultScope": ("obj", "默认范围"),
    "exceptionScope": ("obj", "例外时的范围"),
    "dataRange": ("obj", "事实表的数据区间"),
    "table": ("obj", "表"),
    "firstDateKey": ("data", "最早的 DateKey"),
    "lastDateKey": ("data", "最晚的 DateKey"),
    "timeTerm": ("obj", "相对时间词（区间含两端）"),
    "start": ("data", "起始日"),
    "end": ("data", "截止日"),
    "seasonColumn": ("obj", "大洲 → 季节字段"),
    "continent": ("data", "大洲"),
    "rowScope": ("obj", "只算这类行"),
    "defaultMetric": ("obj", "默认给的指标"),
    "defaultGroupBy": ("obj", "默认分组字段"),
    "alsoShow": ("obj", "同时列出的字段"),
    "requiresLeftJoin": ("obj", "必须用左连接的关系"),
    "defines": ("obj", "定义的类"),
    "geoPath": ("obj", "地理上卷路径（有序）"),
    "planRowAccounts": ("obj", "战略计划表有行的科目（叶子）"),
    "termTarget": ("obj", "说法 → 落点"),
    "target": ("obj", "落点"),
    "useRelationship": ("obj", "使用的关系"),
    "notRelationship": ("obj", "不使用的关系"),
    "groupBy": ("obj", "分组字段（有序）"),
    "asserts": ("obj", "断言（按数据）"),
    "subcategoryKey": ("data", "子类键"),
    "subcategoryName": ("data", "子类名"),
    "inCategory": ("data", "所属品类名"),
    "rootAccount": ("obj", "根科目"),
    "band": ("obj", "分档（区间个体）"),
    "bandOf": ("obj", "分档依据的字段"),
    "objectClass": ("obj", "对象类"),
    "sentinel": ("obj", "哨兵值"),
    "defaultWindow": ("obj", "默认窗口"),
    "component": ("obj", "组成部分"),
    "sumOfAccounts": ("obj", "这些科目的 Amount 正向相加"),
    "derived": ("obj", "派生科目（显式减法）"),
    "result": ("obj", "结果科目"),
    "plus": ("obj", "被减数"),
    "minus": ("obj", "减数"),
    "defaultScenario": ("obj", "默认场景"),
    "defaultAccount": ("obj", "默认科目"),
    "numeratorScenario": ("obj", "分子的场景"),
    "denominatorScenario": ("obj", "分母的场景"),
    "denominatorAccount": ("obj", "分母的科目"),
    "sqlExpressionOf": ("ann", "派生值的 SQL 写法"),
    "condition": ("ann", "筛选条件原文"),
    "numeratorMetric": ("obj", "分子是这个指标"),
    "denominatorMetric": ("obj", "分母是这个指标"),
    "decisionList": ("obj", "按顺序取第一条满足的规则"),
    "scenarioTerm": ("obj", "说法 → 场景"),
    "comparisonWindow": ("obj", "默认对比期"),
}
ANNOTATION_PREDICATES = {"rdfs:label", "rdfs:comment", "skos:altLabel"} | {
    ":" + k for k, (kind, _) in VOCAB.items() if kind == "ann"}
FORMAL, ANNOTATED = "形式化", "注解"
TYPE_MAP = {"String": "xsd:string", "Int32": "xsd:int", "Float64": "xsd:double", "Date": "xsd:date"}


# ---------------------------------------------------------------------------
# Terms and literals
# ---------------------------------------------------------------------------
def _pn_ok(ch: str) -> bool:
    o = ord(ch)
    return (ch.isascii() and (ch.isalnum() or ch in "_-")) or 0xC0 <= o <= 0xD6 or 0xD8 <= o <= 0xF6 \
        or 0xF8 <= o <= 0x2FF or 0x370 <= o <= 0x37D or 0x37F <= o <= 0x1FFF or 0x2070 <= o <= 0x218F \
        or 0x2C00 <= o <= 0x2FEF or 0x3001 <= o <= 0xD7FF or 0xF900 <= o <= 0xFDCF or 0xFDF0 <= o <= 0xFFFD


def local(name: str) -> str:
    """A Turtle PN_LOCAL for a name: disallowed characters become `_`; dots stay inside."""
    out = re.sub(r"_+", "_", "".join(ch if _pn_ok(ch) or ch == "." else "_" for ch in name)).strip("_.")
    if not out or out[0] == "-":
        raise ValueError(f"No local name for {name!r}")
    return out


def lit(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        text = repr(value)
        if not re.fullmatch(r"-?\d+\.\d+(e[+-]?\d+)?|-?\d+e[+-]?\d+", text):
            raise ValueError(f"Unsupported float {value!r}")
        return text
    if not isinstance(value, str):
        raise TypeError(f"Unsupported literal {value!r}")
    if "\n" in value and '"' not in value[-1:] and '"""' not in value and "\\" not in value and "\r" not in value:
        return '"""' + value + '"""'
    return json.dumps(value, ensure_ascii=False)


def date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(value)
    return f'"{value}"^^xsd:date'


def bnode(*pairs) -> str:
    grouped: dict[str, list[str]] = {}
    for p, o in pairs:
        grouped.setdefault("a" if p == "rdf:type" else p, []).append(o)
    return "[ " + " ; ".join(f"{p} {' , '.join(objs)}" for p, objs in grouped.items()) + " ]"


def coll(items) -> str:
    return "( " + " ".join(items) + " )"


# ---------------------------------------------------------------------------
# Graph: ordered blocks; the same subject may appear in several blocks (Turtle allows it)
# ---------------------------------------------------------------------------
class Graph:
    def __init__(self):
        self.blocks: list[tuple[str | None, str, list[tuple[str, str]], str]] = []  # (comment, subject, props, owner)

    def add(self, subject: str, props: list[tuple[str, str]], owner: str, comment: str | None = None):
        props = [(p, o) for p, o in props if o is not None]
        if props:
            self.blocks.append((comment, subject, props, owner))

    def text(self) -> str:
        lines = [f"@prefix {p}: <{u}> ." for p, u in PREFIXES.items()]
        for comment, subject, props, owner in self.blocks:
            if owner != "vocab" or comment:
                lines.append("")
            if comment:
                lines.append(f"# {comment}")
            grouped: dict[str, list[str]] = {}
            for p, o in props:
                grouped.setdefault("a" if p == "rdf:type" else p, []).append(o)
            items = [f"{p} {' , '.join(objs)}" for p, objs in grouped.items()]
            sep = " ; " if owner == "vocab" else " ;\n    "   # vocabulary: one line per term
            lines.append(subject + " " + sep.join(items) + " .")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Parser for the Turtle subset this module emits (prefixed names, literals,
# blank-node property lists, collections). Keeps document order.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Lit:
    value: object
    datatype: str | None = None


@dataclass
class BNode:
    props: list


@dataclass
class Coll:
    items: list


_DELIM = r"\s;,.\[\](){}\"<>#\\"
_TOKEN = re.compile(
    r'(?P<ws>\s+|#[^\n]*)'
    r'|(?P<long>"""(?:[^"\\]|"(?!""))*""")'
    r'|(?P<short>"(?:[^"\\\n]|\\.)*")'
    r'|(?P<dt>\^\^)'
    r'|(?P<prefix>@prefix)'
    r'|(?P<iri><[^>\s]*>)'
    r'|(?P<num>[+-]?(?:\d+\.\d+(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+|\d+))(?![^' + _DELIM + r'])'
    r'|(?P<pname>(?:[A-Za-z][\w-]*)?:(?:[^' + _DELIM + r':]|\.(?=[^' + _DELIM + r']))*)'
    r'|(?P<word>a|true|false)(?![^' + _DELIM + r'])'
    r'|(?P<punct>[.;,\[\]()])'
)


def _tokens(text: str):
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ValueError(f"Bad Turtle near {text[pos:pos + 60]!r}")
        pos = m.end()
        if m.lastgroup != "ws":
            yield m.lastgroup, m.group()


class Parsed:
    def __init__(self, text: str):
        self.toks = list(_tokens(text))
        self.i = 0
        self.prefixes: dict[str, str] = {}
        self.order: list[str] = []
        self.props: dict[str, list] = {}
        self.statements = 0
        while self.i < len(self.toks):
            if self.peek() == ("prefix", "@prefix"):
                self.i += 1
                name = self.take("pname")[:-1]
                self.prefixes[name] = self.take("iri")[1:-1]
                self.expect(".")
                continue
            subject = self.take("pname")
            if subject not in self.props:
                self.order.append(subject)
                self.props[subject] = []
            self.props[subject] += self.pred_objects("]")
            self.expect(".")
            self.statements += 1
        if self.prefixes != PREFIXES:
            raise ValueError("Unexpected namespaces")

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self, kind):
        k, v = self.peek()
        if k != kind:
            raise ValueError(f"Expected {kind}, got {v!r} at token {self.i}")
        self.i += 1
        return v

    def expect(self, punct):
        if self.peek() != ("punct", punct):
            raise ValueError(f"Expected {punct!r}, got {self.peek()[1]!r} at token {self.i}")
        self.i += 1

    def pred_objects(self, closer):
        out = []
        while True:
            k, v = self.peek()
            pred = "rdf:type" if (k, v) == ("word", "a") else self.take("pname")
            if (k, v) == ("word", "a"):
                self.i += 1
            out.append((pred, self.obj()))
            while self.peek() == ("punct", ","):
                self.i += 1
                out.append((pred, self.obj()))
            if self.peek() != ("punct", ";"):
                return out
            self.i += 1
            if self.peek() in (("punct", "."), ("punct", closer)):
                return out

    def obj(self):
        k, v = self.peek()
        self.i += 1
        if k == "pname":
            return v
        if k in ("short", "long"):
            value = json.loads(v) if k == "short" else v[3:-3]
            if self.peek()[0] == "dt":
                self.i += 1
                return Lit(value, self.take("pname"))
            return Lit(value)
        if k == "num":
            return Lit(float(v) if re.search(r"[.eE]", v) else int(v), "num")
        if k == "word" and v in ("true", "false"):
            return Lit(v == "true", "bool")
        if (k, v) == ("punct", "["):
            props = [] if self.peek() == ("punct", "]") else self.pred_objects("]")
            self.expect("]")
            return BNode(props)
        if (k, v) == ("punct", "("):
            items = []
            while self.peek() != ("punct", ")"):
                items.append(self.obj())
            self.i += 1
            return Coll(items)
        raise ValueError(f"Unexpected object {v!r}")

    # --- accessors -------------------------------------------------------
    def all(self, subject, pred):
        return [o for p, o in (subject.props if isinstance(subject, BNode) else self.props.get(subject, [])) if p == pred]

    def one(self, subject, pred):
        values = self.all(subject, pred)
        if len(values) != 1:
            raise ValueError(f"Expected one {pred} on {subject}, got {len(values)}")
        return values[0]

    def opt(self, subject, pred):
        values = self.all(subject, pred)
        if len(values) > 1:
            raise ValueError(f"Expected at most one {pred} on {subject}")
        return values[0] if values else None

    def typed(self, cls):
        return [s for s in self.order if cls in self.all(s, "rdf:type")]

    def triples(self):
        """Flattened (subject, predicate, object-kind) triples, collections as rdf:first/rest."""
        out = []

        def walk(subject, props):
            for p, o in props:
                out.append((subject, p, o))
                expand(o)

        def expand(o):
            if isinstance(o, BNode):
                walk(o, o.props)
            elif isinstance(o, Coll):
                for item in o.items:
                    out.append((o, "rdf:first", item))
                    out.append((o, "rdf:rest", None))
                    expand(item)
        for s in self.order:
            walk(s, self.props[s])
        return out


def text_of(o) -> str:
    if not isinstance(o, Lit) or o.datatype not in (None, "xsd:date"):
        raise ValueError(f"Expected a string literal, got {o!r}")
    return o.value


def value_of(o):
    if isinstance(o, Lit):
        return o.value
    raise ValueError(f"Expected a literal, got {o!r}")


# ---------------------------------------------------------------------------
# Name maps
# ---------------------------------------------------------------------------
class Names:
    def __init__(self, ctx: dict, plus: dict):
        self.tables = {ds["name"].split(".", 1)[1] for ds in ctx["datasets"]}
        self.columns = {f"{ds['name'].split('.', 1)[1]}.{c['name']}" for ds in ctx["datasets"] for c in ds["columns"]}
        self.metric_iri = self._unique({m["name"]: "metric:" + local(m["name"]) for m in ctx["metrics"]})
        self.dq = {q["id"] for q in ctx["data_quality"]}
        self.rels = {}
        for r in ctx["relationships"]:
            ft, fc = r["from"].split(".")[1:]
            tt, _ = r["to"].split(".")[1:]
            self.rels[(r["from"], r["to"])] = f"rel:{ft}.{fc}-{tt}"
        self._unique({k: v for k, v in self.rels.items()})
        self.classes: dict[str, str] = {}      # class label → IRI
        self.class_home: dict[str, str] = {}   # class label → defining hierarchy id
        self.endpoint_only: set[str] = set()   # classes named only as a relation endpoint

    @staticmethod
    def _unique(mapping):
        if len(set(mapping.values())) != len(mapping):
            raise ValueError("IRI collision")
        return mapping

    def ref(self, physical: str) -> str:
        """retail.T or retail.T.C → IRI."""
        db, rest = physical.split(".", 1)
        if db != "retail":
            raise ValueError(physical)
        return "retail:" + rest

    def column(self, table_col: str) -> str:
        if table_col not in self.columns:
            raise ValueError(f"Unknown column {table_col}")
        return "retail:" + table_col

    def rel(self, ft, fc, tt, tc) -> str:
        return self.rels[(f"retail.{ft}.{fc}", f"retail.{tt}.{tc}")]

    def class_iri(self, label: str) -> str:
        if label not in self.classes:
            iri = "class:" + local(label)
            if iri in self.classes.values():
                raise ValueError(f"Class IRI collision: {label}")
            self.classes[label] = iri
        return self.classes[label]


def unprefix(iri: str, prefix: str) -> str:
    if not iri.startswith(prefix + ":"):
        raise ValueError(f"{iri} is not in {prefix}:")
    return iri[len(prefix) + 1:]


# ---------------------------------------------------------------------------
# Encoding: L1
# ---------------------------------------------------------------------------
def encode_l1(g: Graph, ctx: dict, n: Names):
    m = ctx["model"]
    g.add(":model", [("rdf:type", "owl:Ontology"), ("rdfs:label", lit(m["title"])),
                     ("rdfs:comment", lit(m["description"])), (":asOfDate", date(m["as_of_date"])),
                     (":currency", lit(m["currency"])), (":grainNote", lit(m["grain_note"]))],
          "model", "L1：模型")

    for i, c in enumerate(ctx["conventions"]):
        g.add(f":约定{c['id']}", [
            ("rdf:type", ":Convention"), (":group", lit(c["group"])), (":rule", lit(c["rule"])),
            *[(":appliesToDataset", n.ref(x)) for x in c.get("applies_to_datasets", [])],
            *[(":appliesToColumn", n.ref(x)) for x in c.get("applies_to_columns", [])],
            *[(":metric", n.metric_iri[x]) for x in c.get("metrics", [])],
            (":note", lit(c["note"]) if "note" in c else None),
        ], f"convention:{c['id']}", "L1：企业约定（conventions）" if i == 0 else None)

    for i, s in enumerate(ctx["synonyms"]):
        g.add(f":同义词{i + 1}", [
            ("rdf:type", ":Synonym"), *[("skos:altLabel", lit(t)) for t in s["terms"]],
            (":mapsToMetric", n.metric_iri[s["maps_to_metric"]] if "maps_to_metric" in s else None),
            (":mapsToColumn", n.ref(s["maps_to_column"]) if "maps_to_column" in s else None),
            (":defaultDataset", n.ref(s["default_dataset"]) if "default_dataset" in s else None),
            (":why", lit(s["why"]) if "why" in s else None),
        ], f"synonym:{i + 1}", "L1：同义词（synonyms）" if i == 0 else None)

    for i, ds in enumerate(ctx["datasets"]):
        t = n.ref(ds["name"])
        table = unprefix(t, "retail")
        kind = {"fact": ":FactTable", "dimension": ":DimensionTable"}[ds["kind"]]
        g.add(t, [
            ("rdf:type", "owl:Class"), ("rdf:type", kind), ("rdfs:label", lit(ds["title"])),
            (":rows", lit(ds["rows"])), (":grain", lit(ds["grain"])), ("rdfs:comment", lit(ds["description"])),
            (":whenToUse", lit(ds["when_to_use"])),
            *[(":differsFrom", bnode((":dataset", n.ref(x["dataset"])), (":how", lit(x["how"]))))
              for x in ds.get("differs_from", [])],
            (":dateColumn", n.column(f"{table}.{ds['date_column']}") if "date_column" in ds else None),
            *[(":caution", lit(x)) for x in ds.get("cautions", [])],
        ], f"table:{table}", "L1：表与字段（datasets）。表是 OWL 类，行是它的实例；字段是数据属性，IRI 即物理名" if i == 0 else None)
        for c in ds["columns"]:
            base = re.fullmatch(r"(?:Nullable\()?(\w+)\)?", c["type"])[1]
            g.add(n.column(f"{table}.{c['name']}"), [
                ("rdf:type", "owl:DatatypeProperty"), ("rdfs:domain", t), ("rdfs:range", TYPE_MAP[base]),
                (":sqlType", lit(c["type"])), ("rdfs:comment", lit(c["description"])),
                (":unit", lit(c["unit"]) if "unit" in c else None),
                (":role", lit(c["role"]) if "role" in c else None),
                *[(":enumValue", bnode((":code", lit(v["value"])), (":meaning", lit(v["meaning"])),
                                        *([(":rows", lit(v["rows"]))] if "rows" in v else [])))
                  for v in c.get("values", [])],
                (":valueSemantics", lit(c["value_semantics"]) if "value_semantics" in c else None),
            ], f"column:{table}.{c['name']}")

    for i, r in enumerate(ctx["relationships"]):
        ft, fc = r["from"].split(".")[1:]
        tt, tc = r["to"].split(".")[1:]
        types = ["owl:ObjectProperty", "owl:FunctionalProperty"]
        if r["cardinality"] == "一对一":
            types.append("owl:InverseFunctionalProperty")
        elif r["cardinality"] != "多对一":
            raise ValueError(r["cardinality"])
        g.add(n.rel(ft, fc, tt, tc), [
            *[("rdf:type", x) for x in types], ("rdfs:domain", f"retail:{ft}"), ("rdfs:range", f"retail:{tt}"),
            (":joinFrom", n.ref(r["from"])), (":joinTo", n.ref(r["to"])),
            (":cardinality", lit(r["cardinality"])), (":orphanRows", lit(r["orphan_rows"])),
            (":use", lit(r["use"])), (":caution", lit(r["caution"]) if "caution" in r else None),
        ], f"relationship:{n.rel(ft, fc, tt, tc)}",
            "L1：关系（relationships）。外键是对象属性：多对一 = owl:FunctionalProperty，一对一再加 owl:InverseFunctionalProperty" if i == 0 else None)

    for i, mp in enumerate(ctx["multi_path_defaults"]):
        paths = []
        for p in mp["paths"]:
            hops = path_hops(p["path"], n)
            paths.append(bnode((":route", lit(p["path"])), (":meaning", lit(p["meaning"])),
                               *([(":hops", coll(hops))] if hops else [])))
        g.add(f":多路径{i + 1}", [
            ("rdf:type", ":MultiPathDefault"), (":pair", lit(mp["pair"])), *[(":path", x) for x in paths],
            (":default", lit(mp["default"])), (":why", lit(mp["why"])),
        ], f"multi_path:{i + 1}", "L1：多路径默认（multi_path_defaults）" if i == 0 else None)

    for i, m in enumerate(ctx["metrics"]):
        g.add(n.metric_iri[m["name"]], [
            ("rdf:type", ":Metric"), ("rdfs:label", lit(m["name"])),
            *[("skos:altLabel", lit(a)) for a in m.get("aliases", [])],
            (":definition", lit(m["definition"])),
            (":sqlExpression", lit(m["expression"]) if "expression" in m else None),
            (":numerator", lit(m["numerator"]) if "numerator" in m else None),
            (":denominator", lit(m["denominator"]) if "denominator" in m else None),
            (":numeratorMetric", n.metric_iri.get(m.get("numerator"))),
            (":denominatorMetric", n.metric_iri.get(m.get("denominator"))),
            (":additivity", lit(m["additivity"])), (":unit", lit(m["unit"]) if "unit" in m else None),
            (":dataset", n.ref(m["dataset"])),
            (":alternateDataset", n.ref(m["alternate_dataset"]) if "alternate_dataset" in m else None),
            (":denominatorDataset", n.ref(m["denominator_dataset"]) if "denominator_dataset" in m else None),
            (":onlyDataset", lit(m["only_dataset"]) if "only_dataset" in m else None),
            *[(":defaultFilter", lit(x)) for x in m.get("default_filters", [])],
            *[(":convention", f":约定{x}") for x in m.get("conventions", [])],
            (":note", lit(m["note"]) if "note" in m else None),
        ], f"metric:{m['name']}", "L1：指标（metrics）" if i == 0 else None)

    for i, q in enumerate(ctx["data_quality"]):
        g.add("dq:" + local(q["id"]), [
            ("rdf:type", ":DataQualityIssue"), (":severity", lit(q["severity"])), ("rdfs:label", lit(q["title"])),
            (":detail", lit(q["detail"])), (":impact", lit(q["impact"])), (":workaround", lit(q["workaround"])),
        ], f"dq:{q['id']}", "L1：数据质量（data_quality）" if i == 0 else None)


def path_hops(path: str, n: Names) -> list[str] | None:
    """`A → B ← C.Col` into ordered relationship IRIs; None when any hop is ambiguous."""
    parts = re.split(r"\s*(→|←)\s*", path)
    nodes, arrows = parts[0::2], parts[1::2]
    if any("/" in x for x in nodes):
        return None
    parsed = [x.split(".") for x in nodes]
    hops = []
    for (a, b), arrow in zip(zip(parsed, parsed[1:]), arrows):
        src, dst = (a, b) if arrow == "→" else (b, a)
        found = [(k, iri) for k, iri in n.rels.items()
                 if k[0].split(".")[1] == src[0] and k[1].split(".")[1] == dst[0]
                 and (len(src) == 1 or k[0].split(".")[2] == src[1]) and (len(dst) == 1 or k[1].split(".")[2] == dst[1])]
        if len(found) != 1:
            return None
        hops.append(found[0][1] if arrow == "→" else bnode(("owl:inverseOf", found[0][1])))
    return hops


# ---------------------------------------------------------------------------
# Encoding: L1+
# ---------------------------------------------------------------------------
def ref_object(ref: str, n: Names) -> str:
    """A refs string becomes a node when it names one; otherwise the text stays."""
    m = re.fullmatch(r"conventions\[(\d+)\]", ref)
    if m:
        return f":约定{m[1]}"
    m = re.fullmatch(r"datasets\.(\w+)", ref)
    if m and m[1] in n.tables:
        return "retail:" + m[1]
    m = re.fullmatch(r"datasets\.(\w+)\.columns\.(\w+)", ref)
    if m and f"{m[1]}.{m[2]}" in n.columns:
        return f"retail:{m[1]}.{m[2]}"
    m = re.fullmatch(r"metrics\.(.+)", ref)
    if m and m[1] in n.metric_iri:
        return n.metric_iri[m[1]]
    m = re.fullmatch(r"data_quality\.(.+)", ref)
    if m and m[1] in n.dq:
        return "dq:" + local(m[1])
    return lit(ref)


def ref_text(o, n: Names) -> str:
    if isinstance(o, Lit):
        return text_of(o)
    if o.startswith(":约定"):
        return f"conventions[{o[3:]}]"
    if o.startswith("retail:"):
        rest = unprefix(o, "retail")
        return "datasets." + (rest.replace(".", ".columns.", 1) if "." in rest else rest)
    if o.startswith("metric:"):
        return "metrics." + {v: k for k, v in n.metric_iri.items()}[o]
    if o.startswith("dq:"):
        return "data_quality." + {"dq:" + local(x): x for x in n.dq}[o]
    raise ValueError(o)


# Columns an alias set acts on (its `column` text, resolved by hand and checked).
ALIAS_COLUMNS = {
    "E01": ["DimChannel.ChannelName", "FactSales.channelKey"],
    "E02": ["DimStore.StoreKey", "FactOnlineSales.StoreKey"],
    "E03": ["DimGeography.ContinentName"],
    "E04": ["DimGeography.RegionCountryName"],
    "E05": ["DimProductCategory.ProductCategoryName", "DimProductSubcategory.ProductSubcategoryName"],
    "E06": ["DimProduct.BrandName"],
    "E07": ["DimProduct.ColorName"],
    "E08": ["DimProduct.ClassName", "DimProduct.StockTypeName"],
    "E09": ["DimPromotion.PromotionKey", "DimPromotion.PromotionName"],
    "E10": ["DimDate.NorthAmericaSeason", "DimDate.EuropeSeason", "DimDate.AsiaSeason"],
    "E11": ["DimScenario.ScenarioName"],
    "E12": ["DimAccount.AccountKey", "DimAccount.AccountName"],
    "E13": ["DimCustomer.Gender", "DimCustomer.MaritalStatus", "DimCustomer.Education", "DimCustomer.Occupation",
            "DimCustomer.HouseOwnerFlag"],
    "E14": [],  # the table DimDate; each mapping names its own column
    "E15": ["DimStore.Status"],
    "E16": ["DimMachine.MachineType"],
    "E17": ["DimEmployee.Title"],
}
ALIAS_TABLE = {"E14": "DimDate", "E08": "DimProduct", "E13": "DimCustomer"}  # bare per-mapping column names


def alias_value(value, item_table: str | None) -> str:
    if isinstance(value, list):
        return coll(lit(v) for v in value)
    if isinstance(value, dict):
        return bnode(*[(f"retail:{item_table}.{k}", lit(v)) for k, v in value.items()])
    return lit(value)


def selection_shape(entry: dict, item: dict, n: Names) -> str | None:
    """SHACL shape for a selection that is not a plain equality on the entry's column."""
    value, ident = item["value"], entry["id"]
    if ident == "E07":
        # E07 note / A36: colour filters are case-insensitive; grouping keeps the raw value.
        return bnode(("sh:path", n.column("DimProduct.ColorName")),
                     ("sh:pattern", lit("^" + re.escape(value).replace("\\ ", " ") + "$")), ("sh:flags", lit("i")))
    if ident == "E09":
        m = re.fullmatch(r"PromotionKey (=|!=) (\d+)", value) if isinstance(value, str) else None
        path = n.column("DimPromotion.PromotionKey" if m else "DimPromotion.PromotionName")
        if m:
            has = ("sh:hasValue", m[2])
            return bnode(("sh:path", path), has if m[1] == "=" else ("sh:not", bnode(has)))
        if isinstance(value, list):
            return bnode(("sh:path", path), ("sh:in", coll(lit(v) for v in value)))
        return bnode(("sh:path", path), ("sh:hasValue", lit(value)))
    if isinstance(value, list):
        col = {"E04": "DimGeography.RegionCountryName", "E16": "DimMachine.MachineType"}.get(ident)
        if ident == "E05":
            col = {"品类": "DimProductCategory.ProductCategoryName",
                   "子类": "DimProductSubcategory.ProductSubcategoryName"}[item["level"]]
        return bnode(("sh:path", n.column(col)), ("sh:in", coll(lit(v) for v in value)))
    return None


def encode_alias(g: Graph, item: dict, n: Names):
    ident = item["id"]
    table = ALIAS_TABLE.get(ident)
    maps = []
    for mp in item["map"]:
        props = [("skos:altLabel", lit(t)) for t in mp["terms"]]
        if ident == "E09" and isinstance(mp["value"], str) and mp["value"].startswith("PromotionKey "):
            props.append((":condition", lit(mp["value"])))
        else:
            props.append((":value", alias_value(mp["value"], "DimDate")))
        if "key" in mp:
            props.append((":key", lit(mp["key"])))
            if ident == "E12":
                props.append((":account", f"account:{mp['key']}"))
        if "level" in mp:
            props.append((":level", lit(mp["level"])))
        if "column" in mp:
            props.append((":onColumn", n.column(f"{table}.{mp['column']}")))
        if "op" in mp:
            props.append((":op", lit(mp["op"])))
        if "filter" in mp:
            props.append((":filter", lit(mp["filter"])))
        shape = selection_shape(item, mp, n)
        if shape:
            props.append((":selects", shape))
        maps.append(bnode(*props))
    no_exact = [bnode(*[("skos:altLabel", lit(t)) for t in x["terms"]], (":within", lit(x["within"])))
                for x in item.get("no_exact_mapping", [])]
    on = [n.column(c) for c in ALIAS_COLUMNS[ident]] or [f"retail:{table}"]
    g.add(":" + ident, [
        ("rdf:type", ":AliasSet"), ("rdfs:label", lit(item["entity"])), (":column", lit(item["column"])),
        *[(":onColumn", c) for c in on], (":note", lit(item["note"]) if "note" in item else None),
        *[(":map", x) for x in maps], *[(":noExactMapping", x) for x in no_exact],
        (":noExactMappingRule", lit(item["no_exact_mapping_rule"]) if "no_exact_mapping_rule" in item else None),
    ], ident)


# Tables for hierarchy classes whose membership names no table and whose column is not unique.
CLASS_PATH_OVERRIDE = {
    "PromotionKey": ["FactOnlineSales.PromotionKey", "FactSales.PromotionKey"],
    "ScenarioKey": ["FactSalesQuota.ScenarioKey", "FactStrategyPlan.ScenarioKey"],
}
_COND = re.compile(r"^(\w+) (?:(=|!=|>|<) ('[^']*'|\d+|\w+)|IN \(([^)]*)\))(?=$|（|；|，| 的)")


def membership_shape(cls: dict, by_label: dict, ctx_cols: dict[str, list[str]], n: Names) -> list[tuple[str, str]]:
    """OWL / SHACL for a hierarchy class's membership text; [] if it is prose."""
    text = cls.get("membership", "")
    m = re.fullmatch(r"(\w+)(?: 的一行.*|，.*|)", text)
    if m and m[1] in n.tables:
        return [("owl:equivalentClass", "retail:" + m[1])]
    m = _COND.match(text)
    if not m:
        return []
    col, op, value, in_list = m.groups()
    table = None
    node = cls
    while node is not None and table is None:   # nearest ancestor whose membership names a table
        found = [t for t in re.findall(r"\b(\w+)\b", node.get("membership", "")) if t in n.tables]
        table = found[0] if found else None
        node = by_label.get(node.get("parent"))
    if not (table and col in ctx_cols.get(table, [])):
        homes = [t for t, cs in ctx_cols.items() if col in cs]
        table = homes[0] if len(homes) == 1 else None
    if table:
        path = n.column(f"{table}.{col}")
    elif col in CLASS_PATH_OVERRIDE:
        path = bnode(("sh:alternativePath", coll(n.column(c) for c in CLASS_PATH_OVERRIDE[col])))
    else:
        return []

    def term(v):
        return lit(v[1:-1]) if v.startswith("'") else v

    if in_list is not None:
        cons = ("sh:in", coll(term(v.strip()) for v in in_list.split(",")))
    elif op == "=":
        cons = ("sh:hasValue", term(value))
    elif op == "!=":
        cons = ("sh:not", bnode(("sh:hasValue", term(value))))
    elif op == ">":
        cons = ("sh:minExclusive", term(value))
    elif table and value in ctx_cols[table]:
        cons = ("sh:lessThan", n.column(f"{table}.{value}"))
    else:
        cons = ("sh:maxExclusive", term(value))
    return [("rdf:type", "sh:NodeShape"), ("sh:property", bnode(("sh:path", path), cons))]


def encode_hierarchy(g: Graph, item: dict, n: Names, ctx_cols: dict[str, list[str]]):
    ident = item["id"]
    classes = item.get("classes", [])
    by_label = {c["class"]: c for c in classes}
    g.add(":" + ident, [
        ("rdf:type", ":Hierarchy"), ("rdfs:label", lit(item["name"])), (":note", lit(item["note"]) if "note" in item else None),
        *[(":class", n.class_iri(c["class"])) for c in classes],
        *[(":relation", f":{ident}.{local(r['relation'])}") for r in item.get("relations", [])],
        *[(":node", "account:" + account_key(x["account"])) for x in item.get("nodes", [])],
        *[(":constraint", lit(c)) for c in item["constraints"]],
    ], ident)
    for c in classes:
        iri = n.class_iri(c["class"])
        props = [("rdf:type", "owl:Class"), ("rdfs:label", lit(c["class"]))]
        if c["parent"] is not None:
            props.append(("rdfs:subClassOf", n.class_iri(c["parent"])))
        if "membership" in c:
            props.append((":membership", lit(c["membership"])))
        if "identity" in c:
            props.append((":identity", lit(c["identity"])))
            key = re.match(r"\(([^)]*)\)|(\w+)", c["identity"])
            cols = [x.strip() for x in key[1].split(",")] if key[1] else [key[2]]
            props.append(("owl:hasKey", coll(n.column(f"DimGeography.{x}") for x in cols)))
        props += membership_shape(c, by_label, ctx_cols, n)
        g.add(iri, props, ident)
    for r in item.get("relations", []):
        for end in (strip_home(r["from"]), strip_home(r["to"])):
            if end not in n.class_home and end not in n.endpoint_only:
                n.endpoint_only.add(end)
                g.add(n.class_iri(end), [("rdf:type", "owl:Class"), ("rdfs:label", lit(end))], ident)
        props = [("rdf:type", "owl:ObjectProperty"), ("rdfs:label", lit(r["relation"])),
                 ("rdfs:domain", n.class_iri(strip_home(r["from"]))), ("rdfs:range", n.class_iri(strip_home(r["to"]))),
                 (":via", lit(r["via"]))]
        m = re.fullmatch(r"(\w+)\.(\w+)(?:（.*）)?", r["via"])
        if m:
            found = [iri for (f, _), iri in n.rels.items() if f == f"retail.{m[1]}.{m[2]}"]
            if len(found) == 1:
                props.append((":viaRelationship", found[0]))
        g.add(f":{ident}.{local(r['relation'])}", props, ident)
    for x in item.get("nodes", []):
        key = account_key(x["account"])
        g.add("account:" + key, [
            ("rdf:type", "owl:NamedIndividual"), ("rdfs:label", lit(x["account"])),
            (":parentAccount", f"account:{x['parent_account']}" if x.get("parent_account") is not None else None),
            (":kind", lit(x["kind"])), (":leaf", lit(x["leaf"]) if "leaf" in x else None),
            (":note", lit(x["note"]) if "note" in x else None),
        ], ident)


def account_key(text: str) -> str:
    return re.search(r"（(\d+)）$", text)[1]


def strip_home(name: str) -> str:
    return re.sub(r"（H\d+）$", "", name)


def encode_l1plus(g: Graph, data: dict, ctx: dict, n: Names):
    ctx_cols = {ds["name"].split(".", 1)[1]: [c["name"] for c in ds["columns"]] for ds in ctx["datasets"]}
    # Classes are named from their defining hierarchy first, so relation endpoints resolve.
    for h in data["hierarchies"]:
        for c in h.get("classes", []):
            if c["class"] in n.class_home:
                raise ValueError(f"Class defined twice: {c['class']}")
            n.class_home[c["class"]] = h["id"]
            n.class_iri(c["class"])
    meta = {k: v for k, v in data.items() if k not in SECTIONS}
    g.add(":L1plus", [("rdf:type", "owl:Ontology"), (":version", lit(meta["version"])), (":base", lit(meta["base"])),
                      ("rdfs:label", lit(meta["title"])), (":asOfDate", date(meta["as_of_date"]))],
          "l1plus", "L1+：歧义澄清与常用业务概念（109 条，编号即节点名）")
    for section in SECTIONS:
        for k, item in enumerate(data[section]):
            ident = item["id"]
            start = len(g.blocks)
            if section == "general_rules":
                g.add(":" + ident, [("rdf:type", ":GeneralRule"), (":rule", lit(item["rule"]))], ident)
            elif section == "clarifications":
                g.add(":" + ident, [
                    ("rdf:type", ":Clarification"), (":topic", lit(item["topic"])),
                    *[(":ref", ref_object(r, n)) for r in item["refs"]], (":rule", lit(item["rule"])),
                    (":appliesWhen", lit(item["applies_when"]) if "applies_when" in item else None),
                    *[(":exception", lit(x)) for x in item.get("exceptions", [])],
                    (":sql", lit(item["sql"]) if "sql" in item else None),
                ], ident)
            elif section == "concepts":
                g.add(":" + ident, [
                    ("rdf:type", ":Concept"), ("rdfs:label", lit(item["name"])),
                    *[("skos:altLabel", lit(a)) for a in item.get("aliases", [])],
                    (":definition", lit(item["definition"])),
                    (":appliesWhen", lit(item["applies_when"]) if "applies_when" in item else None),
                    *[(":exception", lit(x)) for x in item.get("exceptions", [])],
                    (":sql", lit(item["sql"]) if "sql" in item else None),
                ], ident)
            elif section == "aliases":
                encode_alias(g, item, n)
            else:
                encode_hierarchy(g, item, n, ctx_cols)
            for subject, props in EXTRA.get(ident, []):
                g.add(subject, props, ident)
            if k == 0:
                _, s0, p0, o0 = g.blocks[start]
                g.blocks[start] = (SECTION_COMMENTS[section], s0, p0, o0)


SECTION_COMMENTS = {
    "general_rules": "L1+ 通则（G）",
    "clarifications": "L1+ 歧义澄清（A）。:ref 指向被澄清的 L1 节点",
    "concepts": "L1+ 业务概念（D）",
    "aliases": "L1+ 实例别名（E）：每个说法是一个个体（skos:altLabel 是说法）；:selects 的 SHACL 形状写出非等值的选法",
    "hierarchies": "L1+ 层级（H）：OWL 类与子类、SHACL 成员条件、划分（owl:disjointUnionOf）、科目个体树",
}


# ---------------------------------------------------------------------------
# Hand-written formalizations (T34 step 1: judged entry by entry from the text).
# Each is (subject, [(predicate, object)]). Only what the entry states explicitly;
# the entry's text stays as annotation either way.
# ---------------------------------------------------------------------------
def _accounts(keys):
    return coll(f"account:{k}" for k in keys)


EXPENSE_LEAVES = [5, 7, 8, 9, 10, 11, 12, 15, 16, 17, 18, 20, 21, 22, 23]
PLAN_LEAVES = [4, 5, 7, 8, 9, 10, 11, 12, 15, 16, 17, 18, 19, 20, 21, 22, 23]


def _range(table, first, last):
    return bnode((":table", f"retail:{table}"), (":firstDateKey", date(first)), (":lastDateKey", date(last)))


def _term(terms, start=None, end=None, target=None):
    pairs = [("skos:altLabel", lit(t)) for t in terms]
    if start:
        pairs.append((":start", date(start)))
    if end:
        pairs.append((":end", date(end)))
    if target:
        pairs.append((":target", target))
    return bnode(*pairs)


def _band(label, **bounds):
    return bnode(("rdfs:label", lit(label)), *[(f"sh:{k}", lit(v)) for k, v in bounds.items()])


def _disjoint_union(whole, parts):
    return (whole, [("owl:disjointUnionOf", coll(f"class:{p}" for p in parts))])


EXTRA: dict[str, list[tuple[str, list[tuple[str, str]]]]] = {
    "A01": [(":A01", [(":defaultScope", "class:门店"), (":exceptionScope", "class:实体店")])],
    "A06": [(":A06", [(":dataRange", _range(t, a, b)) for t, a, b in [
        ("FactOnlineSales", "2007-01-01", "2009-12-31"), ("FactSales", "2007-01-01", "2009-12-31"),
        ("FactITSLA", "2007-01-01", "2009-12-31"), ("FactInventory", "2007-01-06", "2009-12-26"),
        ("FactSalesQuota", "2007-01-01", "2009-12-01"), ("FactStrategyPlan", "2007-01-01", "2009-12-01"),
        ("FactITMachine", "2007-01-01", "2009-01-01")]])],
    "A07": [(":A07", [(":timeTerm", x) for x in [
        _term(["本月", "上月", "最近一个月"], "2009-12-01", "2009-12-31"),
        _term(["本季度", "上季度"], "2009-10-01", "2009-12-31"),
        _term(["今年", "本年", "近一年", "过去 12 个月"], "2009-01-01", "2009-12-31"),
        _term(["去年"], "2008-01-01", "2008-12-31"),
        _term(["前年"], "2007-01-01", "2007-12-31"),
        _term(["本周", "上周", "最近一周"], "2009-12-25", "2009-12-31"),
        _term(["截至目前", "累计"], None, "2009-12-31")]])],
    "A10": [(":A10", [(":seasonColumn", bnode((":continent", lit(c)), (":onColumn", f"retail:DimDate.{col}")))
                      for c, col in [("North America", "NorthAmericaSeason"), ("Europe", "EuropeSeason"),
                                     ("Asia", "AsiaSeason")]])],
    "A08": [(":A08", [(":defaultWindow", bnode((":start", date("2009-01-01")), (":end", date("2009-12-31")))),
                      (":comparisonWindow", bnode((":start", date("2008-01-01")), (":end", date("2008-12-31"))))])],
    "A11": [(":A11", [(":rowScope", "class:线上订单行"), (":rowScope", "class:全渠道汇总行")])],
    "A12": [(":A12", [(":rowScope", "class:线上订单行")])],
    "A15": [(":A15", [(":decisionList", coll([
        bnode(*[("skos:altLabel", lit(t)) for t in ("科目名（E12）", "费用", "成本", "税", "损益", "利润", "执行率")],
              (":table", "retail:FactStrategyPlan")),
        bnode(*[("skos:altLabel", lit(t)) for t in ("销售目标", "目标", "配额", "达成率", "完成率", "目标差异", "预算差异",
                                                     "目标销量", "目标销售额", "预算销售额", "销售额预算")],
              (":table", "retail:FactSalesQuota")),
        bnode(("skos:altLabel", lit("收入")), (":table", "retail:FactStrategyPlan"), (":account", "account:4")),
        bnode(("skos:altLabel", lit("预算")), (":table", "retail:FactStrategyPlan"), (":account", "account:4")),
        bnode(*[("skos:altLabel", lit(t)) for t in ("计划", "预测", "计划金额", "预测值", "预测销售额")],
              (":table", "retail:FactStrategyPlan"), (":account", "account:4"))])),
                      (":scenarioTerm", _term(["预算"], target="class:Budget")),
                      (":scenarioTerm", _term(["预测"], target="class:Forecast"))])],
    "A16": [(":A16", [(":termTarget", _term(["标价", "吊牌价", "零售价", "产品单价", "最贵 / 最便宜的产品"],
                                            target="retail:DimProduct.UnitPrice")),
                      (":termTarget", _term(["均价", "单价", "平均价格", "成交价", "平均售价"], target="metric:平均单价"))])],
    "A24": [(":A24", [(":termTarget", bnode(*[("skos:altLabel", lit(t)) for t in ("缺货", "低于安全库存", "补货预警")],
                                            (":selects", bnode(("sh:path", "retail:FactInventory.OnHandQuantity"),
                                                               ("sh:lessThan", "retail:FactInventory.SafetyStockQuantity"))))),
                      (":termTarget", bnode(*[("skos:altLabel", lit(t)) for t in ("断货", "零库存", "无库存")],
                                            (":selects", bnode(("sh:path", "retail:FactInventory.OnHandQuantity"),
                                                               ("sh:hasValue", "0")))))])],
    "A27": [(":最近购买月数", [("rdf:type", "owl:DatatypeProperty"), ("rdfs:domain", "retail:DimCustomer"),
                          ("rdfs:range", "xsd:integer"), ("rdfs:label", lit("月数（末购日到参照日）")),
                          (":sqlExpressionOf", lit("dateDiff('month', 末购日, 参照日)")), (":definedBy", ":A27")])],
    "A17": [(":A17", [(":rowScope", "class:打折交易")])],
    "A18": [(":A18", [(":defaultMetric", f"metric:{m}") for m in ("销售额", "销售数量", "折扣金额", "折扣率")]
             + [(":rowScope", "class:打折交易"), (":defaultGroupBy", "retail:DimPromotion.PromotionKey")])],
    "A19": [(":A19", [(":defaultGroupBy", "retail:DimPromotion.PromotionKey"),
                      (":alsoShow", "retail:DimPromotion.PromotionName")])],
    "A20": [(":A20", [(":requiresLeftJoin", f"rel:{t}.ProductKey-DimProduct")
                      for t in ("FactOnlineSales", "FactSales", "FactInventory", "FactSalesQuota")])],
    "A31": [(":A31", [(":defines", "class:在售产品"), (":defines", "class:停售产品")])],
    "A32": [(":A32", [(":geoPath", coll(["rel:FactStrategyPlan.EntityKey-DimEntity",
                                         bnode(("owl:inverseOf", "rel:DimStore.EntityKey-DimEntity")),
                                         "rel:DimStore.GeographyKey-DimGeography"]))])],
    "A33": [(":A33", [(":planRowAccounts", _accounts(PLAN_LEAVES))])],
    "A34": [(":A34", [(":termTarget", _term(["IT 成本", "设备成本", "运维成本"], target="retail:FactITMachine.CostAmount")),
                      (":termTarget", _term(["设备购置费", "购置成本"], target="class:设备购置费")),
                      (":termTarget", _term(["年度维护费", "维护费"], target="class:年度维护费"))])],
    "A35": [(":A35", [(":useRelationship", "rel:FactITSLA.StoreKey-DimStore"),
                      (":notRelationship", "rel:DimMachine.StoreKey-DimStore")])],
    "A37": [(":A37", [(":groupBy", coll(["retail:DimDate.CalendarYear", "retail:DimDate.CalendarWeekLabel"]))])],
    "A39": [(":A39", [(":termTarget", _term(["区域", "大区"], target="retail:DimGeography.ContinentName")),
                      (":termTarget", _term(["地区"], target="retail:DimGeography.RegionCountryName"))])],
    "A40": [(":A40", [(":asserts", bnode((":subcategoryKey", "19"), (":subcategoryName", lit("Projectors & Screens")),
                                         (":inCategory", lit("Computers"))))])],
    "A41": [(":A41", [(":rootAccount", "account:1"),
                      (":breakCycle", bnode((":root", "account:1"), (":ignoreParentOf", "account:1")))])],
    "D01": [(":D01", [("rdf:type", "owl:DatatypeProperty"), ("rdfs:domain", "retail:DimCustomer"), ("rdfs:range", "xsd:date")])],
    "D02": [(":D02", [("rdf:type", "owl:DatatypeProperty"), ("rdfs:domain", "retail:DimCustomer"), ("rdfs:range", "xsd:date")])],
    "D03": [(":D03", [("rdf:type", "owl:DatatypeProperty"), ("rdfs:domain", "retail:DimCustomer"), ("rdfs:range", "xsd:date")])],
    "D05": [(":D05", [("rdf:type", "owl:Class"), ("rdfs:subClassOf", "retail:DimCustomer"),
                      ("owl:equivalentClass", "class:复购客户"), (":rowScope", "class:线上订单行")])],
    "D05b": [(":D05b", [("rdf:type", "owl:Class"), ("rdfs:subClassOf", "retail:DimCustomer"),
                        (":rowScope", "class:线上销售行")])],
    "D06": [(":D06", [(":rowScope", "class:线上订单行")])],
    "D06c": [(":D06c", [(":rowScope", "class:线上销售行")])],
    "D07": [(":D07", [(":rowScope", "class:线上订单行")])],
    "D07b": [(":D07b", [(":rowScope", "class:线上销售行")])],
    "D16": [(":D16", [(":numeratorMetric", "metric:销售数量"), (":denominatorMetric", "metric:订单数")])],
    "D17": [(":D17", [(":numeratorMetric", "metric:退货金额"), (":denominatorMetric", "metric:销售额")])],
    "D10": [(":D10", [("rdf:type", "owl:DatatypeProperty"), ("rdfs:domain", "retail:DimCustomer"),
                      ("rdfs:range", "xsd:integer"), (":sqlExpressionOf", lit("2009 - toYear(toDate(BirthDate))")),
                      *[(":band", b) for b in (
                          _band("30 岁以下", maxExclusive=30), _band("30–39", minInclusive=30, maxExclusive=40),
                          _band("40–49", minInclusive=40, maxExclusive=50), _band("50–59", minInclusive=50, maxExclusive=60),
                          _band("60 岁及以上", minInclusive=60))]])],
    "D11": [(":D11", [(":bandOf", "retail:DimCustomer.YearlyIncome"), *[(":band", b) for b in (
        _band("[0, 40000)", minInclusive=0, maxExclusive=40000),
        _band("[40000, 80000)", minInclusive=40000, maxExclusive=80000),
        _band("[80000, 130000)", minInclusive=80000, maxExclusive=130000),
        _band("[130000, +∞)", minInclusive=130000))]])],
    "D19": [(":D19", [(":band", b) for b in (
        _band("A", maxInclusive=0.8), _band("B", minExclusive=0.8, maxInclusive=0.95), _band("C", minExclusive=0.95))])],
    "D20": [(":D20", [(":objectClass", bnode(("rdf:type", "owl:Class"), ("rdfs:label", lit("动销产品")),
                                             ("rdfs:subClassOf", "class:在售产品")))])],
    "D21": [(":D21", [("rdf:type", "owl:Class"), ("rdfs:subClassOf", "class:在售产品"),
                      (":defaultWindow", bnode((":start", date("2009-10-03")), (":end", date("2009-12-31"))))])],
    "D22": [(":D22", [("rdf:type", "owl:Class"), ("rdfs:subClassOf", "class:门店")])],
    "D23": [(":D23", [("rdf:type", "owl:Class"), ("owl:equivalentClass", "class:已关店门店"),
                      (":sentinel", bnode((":onColumn", "retail:DimStore.CloseDate"), (":value", lit("2090-12-31"))))])],
    "D27": [(":D27", [("rdf:type", "owl:Class"), ("owl:equivalentClass", "class:零库存组合")])],
    "D29": [(":D29", [(":defaultWindow", bnode((":start", date("2009-10-03")), (":end", date("2009-12-31"))))])],
    "D30": [(":D30", [(":defaultAccount", "account:4"), (":numeratorScenario", "class:Actual"),
                      (":denominatorScenario", "class:Budget")])],
    "D32": [(":D32", [(":defaultScenario", "class:Actual"),
                      (":component", bnode(("rdfs:label", lit("收入")), (":sumOfAccounts", _accounts([4])))),
                      (":component", bnode(("rdfs:label", lit("费用")), (":sumOfAccounts", _accounts(EXPENSE_LEAVES)))),
                      (":component", bnode(("rdfs:label", lit("税")), (":sumOfAccounts", _accounts([19])))),
                      (":derived", bnode((":result", "account:24"), (":plus", "account:2"), (":minus", "account:3"))),
                      (":derived", bnode((":result", "account:1"), (":plus", "account:24"), (":minus", "account:19")))])],
    "D33": [(":D33", [(":denominatorAccount", "account:4")])],
    "H01": [_disjoint_union("class:线上订单行", ["线上销售行", "线上退货行"])],
    "H02": [_disjoint_union("class:门店", ["实体店", "虚拟门店"]), _disjoint_union("class:门店", ["营业中门店", "已关店门店"]),
            (":H02", [(":storeTypeChannel", bnode((":storeType", lit(t)), (":channelKey", str(k))))
                      for t, k in [("Store", 1), ("Online", 2), ("Catalog", 3), ("Reseller", 4)]])],
    "H03": [_disjoint_union("class:产品键", ["已登记产品", "未登记产品"]),
            _disjoint_union("class:已登记产品", ["在售产品", "停售产品"])],
    "H05": [(":H05", [(":axiom", bnode(("rdf:type", "owl:AllDisjointClasses"), ("owl:members", coll(
        f"class:{c}" for c in ("集团级实体", "国家_地区级实体", "州级实体", "门店实体")))))])],
    "H06": [_disjoint_union("class:员工", ["销售总监", "大区经理", "州经理", "门店经理"]),
            (":H06", [(":breakCycle", bnode((":rootKey", "18"), (":onColumn", "retail:DimEmployee.ParentEmployeeKey")))])],
    "H07": [("account:2", [(":leafAccounts", _accounts([4]))]),
            ("account:3", [(":leafAccounts", _accounts(EXPENSE_LEAVES))]),
            ("account:6", [(":leafAccounts", _accounts([7, 8, 9, 10, 11, 12, 15, 16, 17, 18, 20, 21, 22, 23]))]),
            ("account:13", [(":leafAccounts", _accounts([15, 16, 17, 18, 20, 21, 22, 23]))]),
            ("account:14", [(":leafAccounts", _accounts([20, 21, 22, 23]))]),
            (":H07", [(":breakCycle", bnode((":root", "account:1"), (":ignoreParentOf", "account:1")))])],
    "H08": [_disjoint_union("class:分层客户集合", ["活跃客户", "有流失风险客户", "已流失客户"]),
            ("class:分层客户集合", [("owl:disjointWith", "class:未购买客户")]),
            ("class:活跃客户", [("rdf:type", "sh:NodeShape"),
                            ("sh:property", bnode(("sh:path", ":最近购买月数"), ("sh:maxInclusive", "6")))]),
            ("class:有流失风险客户", [("rdf:type", "sh:NodeShape"), ("sh:property", bnode(
                ("sh:path", ":最近购买月数"), ("sh:minInclusive", "7"), ("sh:maxInclusive", "12")))]),
            ("class:已流失客户", [("rdf:type", "sh:NodeShape"),
                             ("sh:property", bnode(("sh:path", ":最近购买月数"), ("sh:minExclusive", "12")))]),
            ("class:新客", [(":definedBy", ":D01"), (":definedBy", ":约定14"), (":definedBy", ":A28")]),
            ("class:复购客户", [(":definedBy", ":D05")])],
    "H09": [_disjoint_union("class:交易", ["无折扣交易", "打折交易"])],
    "H10": [(":H10", [(":axiom", bnode(("rdf:type", "owl:AllDisjointClasses"),
                                       ("owl:members", coll(["class:Actual", "class:Budget", "class:Forecast"])))),
                      (":axiom", bnode(("rdf:type", "sh:NodeShape"),
                                       ("sh:targetClass", "retail:FactSalesQuota"), ("sh:targetClass", "retail:FactStrategyPlan"),
                                       ("sh:property", bnode(("sh:path", bnode(("sh:alternativePath", coll(
                                           ["retail:FactSalesQuota.ScenarioKey", "retail:FactStrategyPlan.ScenarioKey"])))),
                                           ("sh:minCount", "1"), ("sh:maxCount", "1"), ("sh:in", "( 1 2 3 )")))))])],
    "H11": [_disjoint_union("retail:DimDate", ["工作日", "周末"])],
    "H13": [_disjoint_union("class:IT_设备", ["POS", "服务器", "集线器", "路由器"]),
            _disjoint_union("class:IT_成本", ["设备购置费", "年度维护费"])],
}


# ---------------------------------------------------------------------------
# Whole document
# ---------------------------------------------------------------------------
def turtle(ctx: dict, data: dict) -> str:
    n = Names(ctx, data)
    g = Graph()
    for i, (name, (kind, label)) in enumerate(VOCAB.items()):
        rdf_kind = {"class": "owl:Class", "ann": "owl:AnnotationProperty",
                    "obj": "owl:ObjectProperty", "data": "owl:DatatypeProperty"}[kind]
        g.add(":" + name, [("rdf:type", rdf_kind), ("rdfs:label", lit(label))], "vocab",
              "本体词汇。注解属性（owl:AnnotationProperty）保存原文；对象属性、数据属性与 SHACL 形状是形式化部分" if i == 0 else None)
    encode_l1(g, ctx, n)
    encode_l1plus(g, data, ctx, n)
    return g.text()


def owners(ctx: dict, data: dict) -> list[str]:
    g = Graph()
    n = Names(ctx, data)
    encode_l1(g, ctx, n)
    encode_l1plus(g, data, ctx, n)
    return [(s, o) for _, s, _, o in g.blocks]


# ---------------------------------------------------------------------------
# Decoding (inverse of the encoders above)
# ---------------------------------------------------------------------------
def _opt_text(p: Parsed, s, pred, out: dict, key: str):
    v = p.opt(s, pred)
    if v is not None:
        out[key] = text_of(v)


def decode_l1(p: Parsed, n: Names) -> dict:
    ctx = {}
    m = ":model"
    ctx["model"] = {"title": text_of(p.one(m, "rdfs:label")), "description": text_of(p.one(m, "rdfs:comment")),
                    "as_of_date": text_of(p.one(m, ":asOfDate")), "currency": text_of(p.one(m, ":currency")),
                    "grain_note": text_of(p.one(m, ":grainNote"))}
    out = []
    for s in p.typed(":Convention"):
        d = {"id": int(s[len(":约定"):]), "group": text_of(p.one(s, ":group")), "rule": text_of(p.one(s, ":rule"))}
        for key, pred in (("applies_to_datasets", ":appliesToDataset"), ("applies_to_columns", ":appliesToColumn")):
            if p.all(s, pred):
                d[key] = ["retail." + unprefix(x, "retail") for x in p.all(s, pred)]
        if p.all(s, ":metric"):
            d["metrics"] = [_metric_name(x, n) for x in p.all(s, ":metric")]
        _opt_text(p, s, ":note", d, "note")
        out.append(d)
    ctx["conventions"] = out
    out = []
    for s in p.typed(":Synonym"):
        d = {"terms": [text_of(x) for x in p.all(s, "skos:altLabel")]}
        if p.opt(s, ":mapsToMetric"):
            d["maps_to_metric"] = _metric_name(p.one(s, ":mapsToMetric"), n)
        if p.opt(s, ":mapsToColumn"):
            d["maps_to_column"] = "retail." + unprefix(p.one(s, ":mapsToColumn"), "retail")
        if p.opt(s, ":defaultDataset"):
            d["default_dataset"] = "retail." + unprefix(p.one(s, ":defaultDataset"), "retail")
        _opt_text(p, s, ":why", d, "why")
        out.append(d)
    ctx["synonyms"] = out
    columns: dict[str, list] = {}
    for s in p.order:
        if "owl:DatatypeProperty" in p.all(s, "rdf:type") and p.opt(s, ":sqlType") is not None:
            columns.setdefault(p.one(s, "rdfs:domain"), []).append(s)
    out = []
    for s in [x for x in p.order if {":FactTable", ":DimensionTable"} & set(p.all(x, "rdf:type"))]:
        kind = "fact" if ":FactTable" in p.all(s, "rdf:type") else "dimension"
        d = {"name": "retail." + unprefix(s, "retail"), "title": text_of(p.one(s, "rdfs:label")), "kind": kind,
             "rows": value_of(p.one(s, ":rows")), "grain": text_of(p.one(s, ":grain")),
             "description": text_of(p.one(s, "rdfs:comment")), "when_to_use": text_of(p.one(s, ":whenToUse"))}
        if p.all(s, ":differsFrom"):
            d["differs_from"] = [{"dataset": "retail." + unprefix(p.one(b, ":dataset"), "retail"),
                                  "how": text_of(p.one(b, ":how"))} for b in p.all(s, ":differsFrom")]
        if p.opt(s, ":dateColumn"):
            d["date_column"] = unprefix(p.one(s, ":dateColumn"), "retail").split(".", 1)[1]
        if p.all(s, ":caution"):
            d["cautions"] = [text_of(x) for x in p.all(s, ":caution")]
        cols = []
        for c in columns.get(s, []):
            cd = {"name": unprefix(c, "retail").split(".", 1)[1], "type": text_of(p.one(c, ":sqlType")),
                  "description": text_of(p.one(c, "rdfs:comment"))}
            _opt_text(p, c, ":unit", cd, "unit")
            _opt_text(p, c, ":role", cd, "role")
            if p.all(c, ":enumValue"):
                cd["values"] = []
                for b in p.all(c, ":enumValue"):
                    v = {"value": value_of(p.one(b, ":code")), "meaning": text_of(p.one(b, ":meaning"))}
                    if p.opt(b, ":rows") is not None:
                        v["rows"] = value_of(p.one(b, ":rows"))
                    cd["values"].append(v)
            _opt_text(p, c, ":valueSemantics", cd, "value_semantics")
            cols.append(cd)
        d["columns"] = cols
        out.append(d)
    ctx["datasets"] = out
    out = []
    for s in [x for x in p.order if p.opt(x, ":joinFrom") is not None]:
        d = {"from": "retail." + unprefix(p.one(s, ":joinFrom"), "retail"),
             "to": "retail." + unprefix(p.one(s, ":joinTo"), "retail"),
             "cardinality": text_of(p.one(s, ":cardinality")), "orphan_rows": value_of(p.one(s, ":orphanRows")),
             "use": text_of(p.one(s, ":use"))}
        _opt_text(p, s, ":caution", d, "caution")
        out.append(d)
    ctx["relationships"] = out
    ctx["multi_path_defaults"] = [
        {"pair": text_of(p.one(s, ":pair")),
         "paths": [{"path": text_of(p.one(b, ":route")), "meaning": text_of(p.one(b, ":meaning"))} for b in p.all(s, ":path")],
         "default": text_of(p.one(s, ":default")), "why": text_of(p.one(s, ":why"))}
        for s in p.typed(":MultiPathDefault")]
    out = []
    for s in p.typed(":Metric"):
        d = {"name": text_of(p.one(s, "rdfs:label"))}
        if p.all(s, "skos:altLabel"):
            d["aliases"] = [text_of(x) for x in p.all(s, "skos:altLabel")]
        d["definition"] = text_of(p.one(s, ":definition"))
        _opt_text(p, s, ":sqlExpression", d, "expression")
        _opt_text(p, s, ":numerator", d, "numerator")
        _opt_text(p, s, ":denominator", d, "denominator")
        d["additivity"] = text_of(p.one(s, ":additivity"))
        _opt_text(p, s, ":unit", d, "unit")
        for key, pred in (("dataset", ":dataset"), ("alternate_dataset", ":alternateDataset"),
                          ("denominator_dataset", ":denominatorDataset")):
            if p.opt(s, pred):
                d[key] = "retail." + unprefix(p.one(s, pred), "retail")
        if p.opt(s, ":onlyDataset") is not None:
            d["only_dataset"] = value_of(p.one(s, ":onlyDataset"))
        if p.all(s, ":defaultFilter"):
            d["default_filters"] = [text_of(x) for x in p.all(s, ":defaultFilter")]
        if p.all(s, ":convention"):
            d["conventions"] = [int(x[len(":约定"):]) for x in p.all(s, ":convention")]
        _opt_text(p, s, ":note", d, "note")
        out.append(d)
    ctx["metrics"] = out
    ctx["data_quality"] = [
        {"id": {"dq:" + local(x): x for x in n.dq}[s], "severity": text_of(p.one(s, ":severity")),
         "title": text_of(p.one(s, "rdfs:label")), "detail": text_of(p.one(s, ":detail")),
         "impact": text_of(p.one(s, ":impact")), "workaround": text_of(p.one(s, ":workaround"))}
        for s in p.typed(":DataQualityIssue")]
    return ctx


def _metric_name(iri: str, n: Names) -> str:
    return {v: k for k, v in n.metric_iri.items()}[iri]


def _decode_alias_value(o):
    if isinstance(o, Coll):
        return [value_of(x) for x in o.items]
    if isinstance(o, BNode):
        return {unprefix(pred, "retail").split(".", 1)[1]: value_of(v) for pred, v in o.props}
    return value_of(o)


def decode_l1plus(p: Parsed, n: Names) -> dict:
    m = ":L1plus"
    data = {"version": value_of(p.one(m, ":version")), "base": text_of(p.one(m, ":base")),
            "title": text_of(p.one(m, "rdfs:label")), "as_of_date": text_of(p.one(m, ":asOfDate"))}
    data["general_rules"] = [{"id": s[1:], "rule": text_of(p.one(s, ":rule"))} for s in p.typed(":GeneralRule")]
    out = []
    for s in p.typed(":Clarification"):
        d = {"id": s[1:], "topic": text_of(p.one(s, ":topic")), "refs": [ref_text(x, n) for x in p.all(s, ":ref")],
             "rule": text_of(p.one(s, ":rule"))}
        _opt_text(p, s, ":appliesWhen", d, "applies_when")
        if p.all(s, ":exception"):
            d["exceptions"] = [text_of(x) for x in p.all(s, ":exception")]
        _opt_text(p, s, ":sql", d, "sql")
        out.append(d)
    data["clarifications"] = out
    out = []
    for s in p.typed(":Concept"):
        d = {"id": s[1:], "name": text_of(p.one(s, "rdfs:label"))}
        if p.all(s, "skos:altLabel"):
            d["aliases"] = [text_of(x) for x in p.all(s, "skos:altLabel")]
        d["definition"] = text_of(p.one(s, ":definition"))
        _opt_text(p, s, ":appliesWhen", d, "applies_when")
        if p.all(s, ":exception"):
            d["exceptions"] = [text_of(x) for x in p.all(s, ":exception")]
        _opt_text(p, s, ":sql", d, "sql")
        out.append(d)
    data["concepts"] = out
    out = []
    for s in p.typed(":AliasSet"):
        d = {"id": s[1:], "entity": text_of(p.one(s, "rdfs:label")), "column": text_of(p.one(s, ":column"))}
        _opt_text(p, s, ":note", d, "note")
        d["map"] = []
        for b in p.all(s, ":map"):
            cond = p.opt(b, ":condition")
            mp = {"terms": [text_of(x) for x in p.all(b, "skos:altLabel")],
                  "value": text_of(cond) if cond is not None else _decode_alias_value(p.one(b, ":value"))}
            if p.opt(b, ":key") is not None:
                mp["key"] = value_of(p.one(b, ":key"))
            _opt_text(p, b, ":level", mp, "level")
            if p.opt(b, ":onColumn") is not None:
                mp["column"] = unprefix(p.one(b, ":onColumn"), "retail").split(".", 1)[1]
            if p.opt(b, ":op") is not None:
                mp["op"] = text_of(p.one(b, ":op"))
            _opt_text(p, b, ":filter", mp, "filter")
            d["map"].append(mp)
        if p.all(s, ":noExactMapping"):
            d["no_exact_mapping"] = [{"terms": [text_of(x) for x in p.all(b, "skos:altLabel")],
                                      "within": text_of(p.one(b, ":within"))} for b in p.all(s, ":noExactMapping")]
        _opt_text(p, s, ":noExactMappingRule", d, "no_exact_mapping_rule")
        out.append(d)
    data["aliases"] = out
    out = []
    label_of = lambda iri: text_of(p.one(iri, "rdfs:label"))  # noqa: E731
    for s in p.typed(":Hierarchy"):
        ident = s[1:]
        d = {"id": ident, "name": text_of(p.one(s, "rdfs:label"))}
        _opt_text(p, s, ":note", d, "note")
        if p.all(s, ":class"):
            d["classes"] = []
            for c in p.all(s, ":class"):
                parent = p.opt(c, "rdfs:subClassOf")
                cd = {"class": label_of(c), "parent": label_of(parent) if parent else None}
                _opt_text(p, c, ":membership", cd, "membership")
                _opt_text(p, c, ":identity", cd, "identity")
                d["classes"].append(cd)
        if p.all(s, ":relation"):
            def end(iri):
                label = label_of(iri)
                home = n.class_home.get(label)
                return f"{label}（{home}）" if home and home != ident else label
            d["relations"] = [{"relation": label_of(r), "from": end(p.one(r, "rdfs:domain")), "to": end(p.one(r, "rdfs:range")),
                               "via": text_of(p.one(r, ":via"))} for r in p.all(s, ":relation")]
        if p.all(s, ":node"):
            d["nodes"] = []
            for a in p.all(s, ":node"):
                parent = p.opt(a, ":parentAccount")
                nd = {"account": label_of(a), "parent_account": int(unprefix(parent, "account")) if parent else None,
                      "kind": text_of(p.one(a, ":kind"))}
                if p.opt(a, ":leaf") is not None:
                    nd["leaf"] = value_of(p.one(a, ":leaf"))
                _opt_text(p, a, ":note", nd, "note")
                d["nodes"].append(nd)
        d["constraints"] = [text_of(x) for x in p.all(s, ":constraint")]
        out.append(d)
    data["hierarchies"] = out
    return data


# ---------------------------------------------------------------------------
# Check and counts
# ---------------------------------------------------------------------------
def check(ctx: dict, data: dict, text: str) -> Parsed:
    p = Parsed(text)
    n = Names(ctx, data)
    for h in data["hierarchies"]:
        for c in h.get("classes", []):
            n.class_home[c["class"]] = h["id"]
    l1 = decode_l1(p, n)
    if l1 != ctx:
        diff = [k for k in ctx if l1.get(k) != ctx[k]]
        raise ValueError(f"L1 does not round-trip: {diff}")
    plus = decode_l1plus(p, n)
    if plus != data:
        diff = [k for k in data if plus.get(k) != data[k]]
        raise ValueError(f"L1+ does not round-trip: {diff}")
    # Every node in this ontology's own namespaces that is used must be described somewhere.
    defined = set(p.order)
    used = {o for _, _, o in p.triples() if isinstance(o, str)} | {pr for _, pr, _ in p.triples()}
    own = tuple(x + ":" for x in ("", "retail", "rel", "metric", "class", "account", "dq"))
    undefined = sorted(x for x in used if x.startswith(own) and x not in defined)
    if undefined:
        raise ValueError(f"Undefined nodes: {undefined[:20]}")
    if text != turtle(ctx, data):
        raise ValueError("Formal structure differs from the source-derived ontology")
    return p


def l1_context() -> dict:
    from render.common import Namer
    from render.context import render_l1

    return render_l1(Namer("sql"))


def render_context() -> dict:
    return {"ontology_turtle": turtle(l1_context(), overlay())}


def counts(ctx: dict, data: dict, p: Parsed) -> dict:
    """Per-element modes and triple counts."""
    triples = p.triples()
    ann = sum(1 for _, pred, _ in triples if pred in ANNOTATION_PREDICATES)
    owned = owners(ctx, data)
    by_owner: dict[str, list] = {}
    for subject, owner in owned:
        by_owner.setdefault(owner, []).append(subject)

    def formal_preds(owner, entry=None):
        out = []
        for subject in dict.fromkeys(by_owner.get(owner, [])):
            for s, pred, o in _subtree(p, subject):
                if pred in ANNOTATION_PREDICATES or pred == ":ref" or (s == entry and pred == "rdf:type"):
                    continue
                out.append(pred)
        return out

    entries = []
    for section in SECTIONS:
        for item in data[section]:
            mode = FORMAL if formal_preds(item["id"], ":" + item["id"]) else ANNOTATED
            entries.append((section, item["id"], mode, "sql" in item))
    mpd = []
    for i, mp in enumerate(ctx["multi_path_defaults"]):
        s = f":多路径{i + 1}"
        mpd.append(sum(1 for b in p.all(s, ":path") if p.opt(b, ":hops") is not None))
    return {"triples": len(triples), "annotation": ann, "formal": len(triples) - ann, "entries": entries, "mpd": mpd}


def _subtree(p: Parsed, subject):
    out = []

    def walk(s, props):
        for pred, o in props:
            out.append((s, pred, o))
            if isinstance(o, BNode):
                walk(o, o.props)
            elif isinstance(o, Coll):
                for item in o.items:
                    if isinstance(item, BNode):
                        walk(item, item.props)
    walk(subject, [x for x in p.props[subject]] if isinstance(subject, str) else subject.props)
    # Only the blocks owned by this entry: other blocks on the same subject (e.g. a table node
    # that an entry adds an axiom to) are attributed by the caller through `owners`.
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
TOKEN_CELLS = ("SQL-L1", "SQL-L1plus", "SQL-L3a", CELL)


def token_rows() -> list[tuple[str, int, int, int]]:
    """(cell, system-message chars, semantic-context tokens, system-message tokens)."""
    from harness import cells, run_direct

    known = {**cells.CELLS, **cells.L1PLUS_CELLS}
    rows = []
    for name in TOKEN_CELLS:
        system = run_direct.system_for(known[name])
        context = run_direct.context_text(known[name])
        rows.append((name, len(system), run_direct.estimate_tokens_from_text(context),
                     run_direct.estimate_tokens_from_text(system)))
    return rows


def correspondence_lines(ctx: dict, data: dict, p: Parsed, c: dict) -> list[str]:
    cols = [col for ds in ctx["datasets"] for col in ds["columns"]]
    values = sum(len(col.get("values", [])) for col in cols)
    exprs = sum(1 for m in ctx["metrics"] if "expression" in m)
    ratios = sum(1 for s in p.order if p.opt(s, ":numeratorMetric") and p.opt(s, ":denominatorMetric")
                 and ":Metric" in p.all(s, "rdf:type"))
    entries = c["entries"]
    formal = sum(1 for e in entries if e[2] == FORMAL)
    sql_only = sum(1 for e in entries if e[2] == ANNOTATED and e[3])

    def node_count(pred, cls):
        return sum(1 for s in p.order if cls in p.all(s, pred))

    tables = node_count("rdf:type", ":FactTable") + node_count("rdf:type", ":DimensionTable")
    columns = sum(1 for s in p.order if p.opt(s, ":sqlType") is not None)
    enum_nodes = sum(len(p.all(s, ":enumValue")) for s in p.order)
    rels = sum(1 for s in p.order if p.opt(s, ":joinFrom") is not None)
    metrics = node_count("rdf:type", ":Metric")
    pct = lambda a, b: f"{a / b:.0%}"  # noqa: E731
    mpd_formal = sum(1 for i, mp in enumerate(ctx["multi_path_defaults"]) if c["mpd"][i] == len(mp["paths"]))
    rows = [
        ("表", len(ctx["datasets"]), tables, f"{tables}（OWL 类）", "0"),
        ("字段", len(cols), columns, f"{columns}（数据属性，rdfs:domain / rdfs:range）", "0"),
        ("枚举值", values, enum_nodes, f"{enum_nodes}（个体：code + meaning）", "0"),
        ("关系", len(ctx["relationships"]), rels, f"{rels}（对象属性，Functional / InverseFunctional）", "0"),
        ("指标", len(ctx["metrics"]), metrics, f"{ratios}（比率：分子、分母都链接到指标）",
         f"{metrics - ratios}（其中 {exprs} 个有 SQL 表达式）"),
        ("约定", len(ctx["conventions"]), node_count("rdf:type", ":Convention"), "0", "15（适用表、字段、指标是链接）"),
        ("同义词", len(ctx["synonyms"]), node_count("rdf:type", ":Synonym"), "56（说法 → 指标 / 字段的链接）", "0"),
        ("多路径默认", len(ctx["multi_path_defaults"]), node_count("rdf:type", ":MultiPathDefault"),
         f"{mpd_formal}（全部路径解析成有序关系链）", f"{len(ctx['multi_path_defaults']) - mpd_formal}（至少一条路径只有原文）"),
        ("数据质量", len(ctx["data_quality"]), node_count("rdf:type", ":DataQualityIssue"), "0", "15"),
    ]
    lines = [
        "# L3a-full 逐条对应核对（T34）", "",
        "复现：`uv run python -m render.l3a_full`（写 `build/contexts/SQL-L3a-full.yaml` 与本报告）；"
        "测试：`uv run pytest tests/test_l3a_full.py`。", "",
        "## 怎么核对", "",
        "- 输入只有 `semantic/source.yaml`（经 `render.context.render_l1`，即 SQL-L1 的上下文）与 "
        "`semantic/l1plus.yaml`（`render.l1plus.overlay`，与 SQL-L1plus 的 `l1plus` 节相同）。",
        "- 核对器解析生成的 Turtle（本模块自带的、保留文档顺序的解析器，只认生成器用到的 Turtle 子集：前缀名、字面量、"
        "`[ ]` 空白节点、`( )` 列表），再从图里**反解**出 SQL-L1 的整份上下文和 L1+ 的整份 overlay，"
        "要求与源**逐字段相等**（含列表顺序、标量类型）。所以下表的「源」与「本体」两列相等不是数出来凑的："
        "少一个字段、改一个字、挂错节点，反解就不相等，渲染直接失败。",
        "- 另查：本体自己命名空间里用到的每个节点都有定义（不悬空）；生成结果可重现。",
        "- 通用解析器复核：`uv run --with rdflib pytest tests/test_l3a_full.py` 用 rdflib 解析同一份 Turtle，"
        "三元组数与本模块解析器一致（rdflib 不是项目依赖，未安装时该测试跳过）。",
        "- 不运行 OWL 推理机或 SHACL 引擎，不编译查询。", "",
        "## L1", "",
        "| 项 | 源 | 本体 | 形式化 | 注解 |", "|---|---|---|---|---|",
        *[f"| {a} | {b} | {c_} | {d} | {e} |" for a, b, c_, d, e in rows],
        "",
        "形式化与注解的判定：表、字段、关系、枚举值、同义词本身就是结构（类、属性、个体、链接），计形式化；"
        "比率指标的分子、分母恰好是另一个指标名时，链接到该指标（`:numeratorMetric` / `:denominatorMetric`），计形式化；"
        "约定、其余指标、数据质量的核心是文字口径，计注解（指标的 SQL 表达式按卡片允许的「注解里的 SQL 片段」保留）。"
        "所有原文（描述、口径、理由……）都同时以注解保留。", "",
        "枚举值以个体表达（`:enumValue [ :code … ; :meaning … ]`），**没有**写成闭合的 `sh:in`："
        "L1 没有声明哪些取值清单是完整的，本卡不从数据推。", "",
        "## L1+（109 条）", "",
        f"共 {len(entries)} 条：形式化 {formal} 条（{pct(formal, len(entries))}）；"
        f"注解 {len(entries) - formal} 条（{pct(len(entries) - formal, len(entries))}），"
        f"其中 {sql_only} 条带 SQL 片段。", "",
        "判定：该条（含它名下的类、关系、科目节点）除了自身类型、`:ref` 链接和注解之外，还有至少一条 OWL / SHACL "
        "公理、个体或带类型的取值，计形式化；否则计注解。形式化的条目原文仍完整保留，"
        "不代表该条每一句都已形式化。", "",
        "## 三元组", "",
        f"共 {c['triples']:,} 个三元组（列表按 rdf:first / rdf:rest 展开计）："
        f"注解 {c['annotation']:,}（{pct(c['annotation'], c['triples'])}），"
        f"形式化 {c['formal']:,}（{pct(c['formal'], c['triples'])}）。"
        "注解 = 谓词是 rdfs:label、rdfs:comment、skos:altLabel 或本体声明的注解属性。", "",
    ]
    return lines


def report(ctx: dict, data: dict, p: Parsed, c: dict, tokens) -> str:
    lines = correspondence_lines(ctx, data, p, c)
    plus = dict((r[0], r[3]) for r in tokens)["SQL-L1plus"]
    lines += [
        "## 系统消息的 token 数", "",
        "方法：`harness.run_direct.system_for` 拼出完整系统消息（系统提示 + 语义上下文 + 语法说明），"
        "用 harness 的 `estimate_tokens_from_text` 估算（DeepSeek 官方经验比例：中文字符 ≈ 0.6 token，"
        "其他字符 ≈ 0.3 token）。是估算，不是分词器的实数；正式运行以 API 返回的用量为准。", "",
        "「语义上下文」只算 `build/contexts/<单元>.yaml` 的文本；「系统消息」是实际发给模型的整条系统消息。"
        "四个单元的系统提示与语法说明逐字节相同（测试核对），差别只在语义上下文。", "",
        "| 单元 | 系统消息字符数 | 语义上下文（估算 token） | 系统消息（估算 token） | 系统消息对 SQL-L1plus |",
        "|---|---|---|---|---|",
        *[f"| {name} | {chars:,} | {ctx_tok:,} | {tok:,} | {tok / plus:.2f}× |"
          for name, chars, ctx_tok, tok in tokens], "",
        "## 逐条", "",
        "| 节 | 编号 | 表达方式 | SQL 片段 |", "|---|---|---|---|",
        *[f"| {s} | {i} | {m} | {'有' if q else ''} |" for s, i, m, q in c["entries"]],
    ]
    return "\n".join(lines) + "\n"


def main():
    from render.common import dump_yaml

    ctx, data = l1_context(), overlay()
    text = turtle(ctx, data)
    p = check(ctx, data, text)
    c = counts(ctx, data, p)
    BUILD.joinpath("contexts").mkdir(parents=True, exist_ok=True)
    out = BUILD / "contexts" / f"{CELL}.yaml"
    out.write_text(dump_yaml({"ontology_turtle": text}), encoding="utf-8")
    import yaml

    if yaml.safe_load(out.read_text(encoding="utf-8"))["ontology_turtle"] != text:
        raise ValueError("YAML wrapper changed the Turtle text")
    from render.context import main as render_main

    render_main(["SQL-L1", "SQL-L1plus", "SQL-L3a"])
    tokens = token_rows()
    REPORT.write_text(report(ctx, data, p, c, tokens), encoding="utf-8")
    formal = sum(1 for e in c["entries"] if e[2] == FORMAL)
    print(f"{out.relative_to(REPO)}: {len(text):,} chars; L1+ formal {formal}/{len(c['entries'])}; "
          f"triples {c['triples']:,} (annotation {c['annotation']:,}); tokens {tokens}")


if __name__ == "__main__":
    main()
