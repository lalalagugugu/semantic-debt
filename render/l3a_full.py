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
        self.vocab_lines: set[str] = set()   # subjects written on one line without a blank line before

    def add(self, subject: str, props: list[tuple[str, str]], owner: str, comment: str | None = None):
        props = [(p, o) for p, o in props if o is not None]
        if props:
            self.blocks.append((comment, subject, props, owner))

    def text(self) -> str:
        lines = [f"@prefix {p}: <{u}> ." for p, u in PREFIXES.items()]
        for comment, subject, props, owner in self.blocks:
            compact = subject in self.vocab_lines and props[0][1] in (
                "owl:Class", "owl:AnnotationProperty", "owl:ObjectProperty", "owl:DatatypeProperty")
            if not compact or comment:
                lines.append("")
            if comment:
                lines.append(f"# {comment}")
            grouped: dict[str, list[str]] = {}
            for p, o in props:
                grouped.setdefault("a" if p == "rdf:type" else p, []).append(o)
            items = [f"{p} {' , '.join(objs)}" for p, objs in grouped.items()]
            sep = " ; " if compact else " ;\n    "   # vocabulary: one line per term
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
          L1PLUS_HEADER, "L1+：歧义澄清与常用业务概念（109 条，编号即节点名）")
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
_LITERAL = re.compile(r'"""(?:[^"\\]|"(?!""))*"""|"(?:[^"\\\n]|\\.)*"')
_VOCAB_USE = re.compile(r"(?<![\w:])(:[A-Za-z]\w*)")


def _vocab_used(props) -> list[str]:
    """Vocabulary terms a block uses, in order (literals stripped first)."""
    seen = []
    for pred, obj in props:
        for term in _VOCAB_USE.findall(pred + " " + _LITERAL.sub("", obj)):
            if term[1:] in VOCAB and term not in seen:
                seen.append(term)
    return seen


def _declare(term: str) -> list[tuple[str, str]]:
    kind, label = VOCAB[term[1:]]
    return [("rdf:type", {"class": "owl:Class", "ann": "owl:AnnotationProperty",
                          "obj": "owl:ObjectProperty", "data": "owl:DatatypeProperty"}[kind]), ("rdfs:label", lit(label))]


def build(ctx: dict, data: dict | None) -> Graph:
    """The ontology as blocks. data=None → SQL-L1-onto (L1 only); otherwise SQL-L3a-full.

    The L1 part is generated by the same code either way. Vocabulary used by L1 is declared
    first; vocabulary used only by L1+ is declared where the L1+ part starts and is owned by
    the first entry that uses it, so every L1+ triple traces to an entry (or the L1+ header)."""
    n = Names(ctx, data or {})
    l1 = Graph()
    encode_l1(l1, ctx, n)
    plus = Graph()
    if data is not None:
        encode_l1plus(plus, data, ctx, n)
    l1_terms = list(dict.fromkeys(t for _, _, props, _ in l1.blocks for t in _vocab_used(props)))
    l1_terms = [":" + k for k in VOCAB if ":" + k in l1_terms]          # VOCAB order
    g = Graph()
    for i, term in enumerate(l1_terms):
        g.add(term, _declare(term), "vocab",
              "本体词汇。注解属性（owl:AnnotationProperty）保存原文；对象属性、数据属性与 SHACL 形状是形式化部分" if i == 0 else None)
    g.blocks += l1.blocks
    declared, extra = set(l1_terms), []
    for _, _, props, owner in plus.blocks:
        for term in _vocab_used(props):
            if term not in declared:
                declared.add(term)
                extra.append((term, owner))
    for i, (term, owner) in enumerate(extra):
        g.add(term, _declare(term), owner, "L1+ 用到的其余词汇" if i == 0 else None)
    # Vocabulary declarations are one line each; keep them compact like the L1 vocabulary.
    g.vocab_lines = {term for term, _ in extra} | set(l1_terms)
    g.blocks += plus.blocks
    return g


def turtle(ctx: dict, data: dict | None) -> str:
    return build(ctx, data).text()


def owners(ctx: dict, data: dict | None) -> list[tuple[str, str]]:
    return [(s, o) for _, s, _, o in build(ctx, data).blocks]


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
ENTRY_ID = re.compile(r"(?<![A-Za-z0-9])[ADEGH]\d{2}[a-z]?(?![A-Za-z0-9])")
L1PLUS_HEADER = "l1plus"   # owner of the `:L1plus` node (l1plus.yaml's top-level fields, not an entry)


def check(ctx: dict, data: dict | None, text: str) -> Parsed:
    """Rebuild the source from the Turtle and require field-for-field equality.

    data=None checks SQL-L1-onto: the rebuild equals the SQL-L1 context and no L1+ entry ID
    appears anywhere in the text."""
    p = Parsed(text)
    n = Names(ctx, data or {})
    for h in (data or {}).get("hierarchies", []):
        for c in h.get("classes", []):
            n.class_home[c["class"]] = h["id"]
    l1 = decode_l1(p, n)
    if l1 != ctx:
        diff = [k for k in ctx if l1.get(k) != ctx[k]]
        raise ValueError(f"L1 does not round-trip: {diff}")
    if data is None:
        if p.typed(":Hierarchy") or p.typed(":Clarification") or ":L1plus" in p.props:
            raise ValueError("L1+ content in the L1-only ontology")
        ids = sorted(set(ENTRY_ID.findall(text)))
        if ids:
            raise ValueError(f"L1+ entry IDs in the L1-only ontology: {ids[:10]}")
    else:
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


def canonical(o) -> str:
    """A blank-node-free key for an RDF term, so graphs compare as triple multisets."""
    if isinstance(o, BNode):
        return "[" + " ; ".join(sorted(f"{p} {canonical(x)}" for p, x in o.props)) + "]"
    if isinstance(o, Coll):
        return "(" + " ".join(canonical(x) for x in o.items) + ")"
    if isinstance(o, Lit):
        return repr((o.value, o.datatype))
    return "nil" if o is None else o


def triple_counter(p: Parsed) -> Counter:
    return Counter((canonical(s), pred, canonical(o)) for s, pred, o in p.triples())


def check_subgraph(ctx: dict, data: dict, l1_text: str, full_text: str) -> dict:
    """SQL-L1-onto ⊆ SQL-L3a-full as graphs, and the difference is exactly the triples
    generated from the 109 entries (plus the L1+ header), each traced to its owner."""
    small, big = triple_counter(Parsed(l1_text)), triple_counter(Parsed(full_text))
    if small - big:
        raise ValueError(f"SQL-L1-onto is not a subgraph: {list((small - big).items())[:5]}")
    g = build(ctx, data)
    l1_owners = {o for _, o in owners(ctx, None)}
    by_owner: dict[str, Counter] = {}
    for owner in dict.fromkeys(o for _, _, _, o in g.blocks):
        if owner in l1_owners:
            continue
        part = Graph()
        part.blocks = [b for b in g.blocks if b[3] == owner]
        by_owner[owner] = triple_counter(Parsed(part.text()))
    ids = [item["id"] for s in SECTIONS for item in data[s]]
    if set(by_owner) != set(ids) | {L1PLUS_HEADER}:
        raise ValueError(f"Unexpected owners: {sorted(set(by_owner) ^ (set(ids) | {L1PLUS_HEADER}))[:10]}")
    traced = sum(by_owner.values(), Counter())
    if big - small != traced or small + traced != big:
        raise ValueError("Difference between the two ontologies is not exactly the L1+ triples")
    return {"l1": sum(small.values()), "full": sum(big.values()),
            "per_entry": {k: sum(v.values()) for k, v in by_owner.items()}}


def l1_context() -> dict:
    from render.common import Namer
    from render.context import render_l1

    return render_l1(Namer("sql"))


def render_context(with_l1plus: bool = True) -> dict:
    return {"ontology_turtle": turtle(l1_context(), overlay() if with_l1plus else None)}


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
            if subject in VOCAB_SUBJECTS:
                continue
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
# ---------------------------------------------------------------------------
# Three tiers (aligned with T26), judged entry by entry for the old SQL-L3a and this one:
#   1 core 口径 formalized: the part that decides how the SQL is written is an axiom / shape /
#     individual, not only annotation (explanations and edge cases may stay as text);
#   2 declarations only: types, domain / range, links; the core 口径 is in annotation;
#   3 annotation only.
# (old tier, new tier, why it changed or what stays text)
# ---------------------------------------------------------------------------
_OLD_A = "旧 L3a 的 A / D / G 条只有原文注解树（含 SQL 片段注解），没有类型和链接"
TIERS: dict[str, tuple[int, int, str]] = {
    "G01": (3, 3, "比率分母为 0 / NULL 的通则是文字规则，无对应公理"),
    "A01": (3, 1, "默认范围链接到类:门店（≡ DimStore），例外链接到类:实体店（StoreType 的 hasValue）"),
    "A02": (3, 2, "引用解析成节点链接；按序选表的规则仍在注解"),
    "A03": (3, 2, "同上：引用成链接，选表两步规则在注解"),
    "A04": (3, 2, "引用成链接，地理路径跟随事实表的规则在注解"),
    "A05": (3, 2, "引用成链接，规则在注解"),
    "A06": (3, 1, "各事实表的最早 / 最晚 DateKey 写成 xsd:date 个体；主数据不截断的说明在注解"),
    "A07": (3, 1, "列出的相对时间词写成带起止日的个体；「近 N 天」「近 N 个月」是参数式，留在注解与 SQL 片段"),
    "A08": (3, 2, "只形式化了默认本期 / 对比期；同比、环比怎么取对比期的规则在注解"),
    "A09": (3, 2, "引用成链接；交易日日均的定义在注解与 SQL 片段"),
    "A10": (3, 1, "大洲 → 季节字段的对应写成个体；按「大洲 × 季节」分组的要求在注解"),
    "A11": (3, 1, "行范围链接到类:线上订单行 与 类:全渠道汇总行（全部行，含退货行）"),
    "A12": (3, 1, "行范围链接到类:线上订单行（全部交易行，含只有退货的订单）"),
    "A13": (3, 2, "引用成链接；利润率的选择与上卷公式在注解与 SQL 片段"),
    "A14": (3, 2, "引用成链接；选表顺序交给 A15，本条规则在注解"),
    "A15": (3, 1, "五条按序规则写成有序列表（说法 → 表 / 科目），说法 → 场景写成个体"),
    "A16": (3, 1, "说法 → 落点（DimProduct.UnitPrice 或 指标:平均单价）"),
    "A17": (3, 1, "分子分母的行范围链接到类:打折交易（PromotionKey 的 sh:not hasValue 1）"),
    "A18": (3, 1, "默认指标、行范围、默认分组字段都是链接"),
    "A19": (3, 1, "默认分组字段与同时列出的字段是链接；按交易日期分年的说明在注解"),
    "A20": (3, 1, "四条「事实表 → DimProduct」关系标为必须左连接；未知组为 NULL 的写法在注解"),
    "A21": (3, 2, "引用成链接；占比分母规则在注解与 SQL 片段"),
    "A22": (3, 2, "引用成链接；期末 / 平均库存的算法在注解与 SQL 片段"),
    "A23": (3, 2, "引用成链接；周转率窗口规则在注解"),
    "A24": (3, 2, "两组说法写成比较形状（lessThan / hasValue 0）；本条的核心「按产品先跨店汇总再比较」在注解"),
    "A25": (3, 2, "引用成链接；不用宽表的规则在注解"),
    "A26": (3, 2, "引用成链接；对齐与全外连接的规则在注解"),
    "A27": (3, 2, "月数定义成数据属性（定义域 DimCustomer）；客户集合与筛选规则在注解"),
    "A28": (3, 2, "引用成链接；新客窗口的读法在注解"),
    "A29": (3, 2, "引用成链接；同店判定规则在注解"),
    "A30": (3, 2, "引用成链接；坪效分子分母范围在注解与 SQL 片段"),
    "A31": (3, 2, "在售 / 停售链接到带 hasValue 的类；门店数、产品数的计数规则（本条主体）在注解"),
    "A32": (3, 1, "地理上卷写成有序关系链（含 owl:inverseOf）；组织树例外在注解"),
    "A33": (3, 1, "计划表有行的叶子科目写成有序列表，父科目的叶子集合见 H07 的 :leafAccounts"),
    "A34": (3, 1, "三组说法 → 落点（CostAmount、类:设备购置费、类:年度维护费）"),
    "A35": (3, 1, "使用 / 不使用的关系是链接"),
    "A36": (3, 2, "引用成链接；颜色大小写不敏感已在 E07 形式化，本条的平均值规则在注解"),
    "A37": (3, 1, "按周分组的两个字段写成有序列表"),
    "A38": (3, 2, "引用成链接；业绩汇总沿员工树的规则在注解（断环在 H06）"),
    "A39": (3, 1, "说法 → 落点（ContinentName、RegionCountryName）"),
    "A40": (3, 1, "子类 19 属于 Computers 写成断言个体"),
    "A41": (3, 1, "根科目与断环写成链接（根 = 科目 1，忽略 1 的上级）"),
    "D01": (3, 2, "首购日声明为数据属性（定义域 DimCustomer，值域 xsd:date）；口径在注解与 SQL 片段"),
    "D02": (3, 2, "同 D01"),
    "D03": (3, 2, "同 D01"),
    "D04": (3, 3, "三个留存口径是文字与 SQL 片段"),
    "D05": (3, 2, "声明为类（⊑ DimCustomer，≡ 类:复购客户），行范围链接；「≥ 2 个订单」在注解与 SQL 片段"),
    "D05b": (3, 2, "同 D05，行范围是类:线上销售行"),
    "D06": (3, 2, "行范围链接；比率口径在注解与 SQL 片段"),
    "D06b": (3, 3, "文字与 SQL 片段"),
    "D06c": (3, 2, "行范围链接到类:线上销售行；比率口径在注解"),
    "D07": (3, 2, "行范围链接；订单数口径在注解"),
    "D07b": (3, 2, "行范围链接到类:线上销售行；口径在注解"),
    "D08": (3, 3, "文字"),
    "D09": (3, 3, "文字"),
    "D10": (3, 1, "年龄声明为数据属性并给出派生式；五个年龄段写成区间个体（sh:minInclusive / maxExclusive）"),
    "D11": (3, 1, "四个收入档写成 YearlyIncome 上的区间个体"),
    "D12": (3, 3, "文字与 SQL 片段"),
    "D13": (3, 3, "文字"),
    "D14": (3, 3, "文字"),
    "D15": (3, 3, "文字与 SQL 片段"),
    "D16": (3, 1, "分子 = 指标:销售数量，分母 = 指标:订单数"),
    "D17": (3, 1, "分子 = 指标:退货金额，分母 = 指标:销售额"),
    "D18": (3, 3, "文字与 SQL 片段"),
    "D19": (3, 2, "A / B / C 的阈值写成区间个体；累计占比（含同额）的算法在注解与 SQL 片段"),
    "D20": (3, 2, "动销产品声明为类:在售产品的子类；窗口与分母规则在注解"),
    "D21": (3, 2, "声明为类:在售产品的子类，默认窗口是个体；判定规则在注解"),
    "D22": (3, 2, "声明为类:门店的子类；开店日期判定在注解"),
    "D23": (3, 1, "≡ 类:已关店门店（Status 的 hasValue 'Off'），CloseDate 哨兵值写成个体"),
    "D24": (3, 3, "文字"),
    "D25": (3, 3, "文字"),
    "D26": (3, 3, "文字与 SQL 片段"),
    "D27": (3, 1, "≡ 类:零库存组合（OnHandQuantity 的 hasValue 0）"),
    "D28": (3, 3, "文字"),
    "D29": (3, 2, "默认窗口是个体；渠道范围与日分母规则在注解与 SQL 片段"),
    "D30": (3, 1, "默认科目 = 科目 4，分子场景 Actual、分母场景 Budget 是链接"),
    "D31": (3, 3, "默认科目只在落到战略计划表时成立，不写成无条件公理"),
    "D32": (3, 1, "收入、费用、税写成叶子科目列表，税前 / 税后利润写成显式减法个体，默认场景链接"),
    "D33": (3, 2, "只形式化了分母科目；分子随问题，在注解"),
}
for _i, _e in enumerate(("E01", "E02", "E03", "E06", "E08", "E11", "E12", "E13", "E14", "E15", "E17")):
    TIERS[_e] = (1, 1, "同档：说法 → 取值的个体旧版已有；新增作用字段的链接（旧版只是字段原文）"
                 + ("，E12 另链接科目个体" if _e == "E12" else ""))
TIERS.update({
    "E04": (2, 1, "旧版「大中华区」的取值是列表，被丢掉；新版写成 sh:in"),
    "E05": (2, 1, "旧版「游戏」的列表取值被丢掉；新版写成 sh:in；分不出的说法写成个体，处理规则在注解"),
    "E07": (2, 1, "旧版只有 :value，大小写不敏感只在注解；新版每个颜色写 sh:pattern + sh:flags \"i\"（E07 已知问题）"),
    "E09": (2, 1, "旧版把「PromotionKey = 1 / != 1」当取值、名单列表被丢掉；新版写成条件形状（hasValue / sh:not）与 sh:in"),
    "E10": (2, 1, "旧版字典取值全部丢掉、只剩说法；新版每个说法给出三个季节字段的取值"),
    "E16": (2, 1, "旧版列表取值全部丢掉；新版写成 sh:in"),
    "H01": (2, 1, "旧版缺「SalesQuantity > 0」与划分；新版补 sh:minExclusive 与 owl:disjointUnionOf"),
    "H02": (2, 1, "旧版缺虚拟门店（!=）与两个划分；新版补 sh:not 与两个 owl:disjointUnionOf"),
    "H03": (2, 1, "旧版有在售 / 停售的 hasValue、缺划分；新版补两个 owl:disjointUnionOf（能否连上 DimProduct 的判定在注解，左连接见 A20）"),
    "H04": (2, 1, "旧版无形状；新版城市的「GeographyType = 'City' 的行」转 hasValue（旧版的字面等式规则在此不生效），身份写成 owl:hasKey"),
    "H05": (2, 1, "旧版「EntityType = 'Group'，3 个」带逗号，字面等式规则不生效；新版四类都转 hasValue，并加 owl:AllDisjointClasses"),
    "H06": (2, 1, "旧版有职级 hasValue、缺划分与断环；新版补 owl:disjointUnionOf 与断环个体"),
    "H07": (2, 1, "旧版只有科目树；新版加各父科目的叶子集合与断环（利润的显式减法在 D32）"),
    "H08": (2, 1, "旧版只有类与子类；新版把三层客户写成月数区间形状，加划分与 owl:disjointWith（客户集合规则在 A27 的注解）"),
    "H09": (2, 1, "旧版缺打折交易（!=）与划分；新版补 sh:not 与 owl:disjointUnionOf，路径用 sh:alternativePath"),
    "H10": (1, 1, "同档：旧版已有三个场景的 hasValue 与「每行恰好一个场景」的形状；新版加 owl:AllDisjointClasses"),
    "H11": (2, 1, "旧版缺划分；新版写 DimDate 的 owl:disjointUnionOf"),
    "H12": (2, 1, "旧版缺「OnHand < SafetyStock」；新版补 sh:lessThan。零库存 ⊂ 低于安全库存按原文不是规则，不写"),
    "H13": (2, 1, "旧版缺两个 IN 条件与划分；新版补 sh:in 与两个 owl:disjointUnionOf"),
})

# Constructs that count as OWL / SHACL (reported per entry); custom properties are listed as such.
_CONSTRUCTS = [
    "owl:Class", "rdfs:subClassOf", "owl:equivalentClass", "owl:disjointUnionOf", "owl:AllDisjointClasses",
    "owl:disjointWith", "owl:hasKey", "owl:inverseOf", "owl:ObjectProperty", "owl:DatatypeProperty", "rdfs:domain",
    "owl:NamedIndividual", "sh:NodeShape", "sh:hasValue", "sh:in", "sh:not", "sh:pattern", "sh:flags", "sh:lessThan",
    "sh:minInclusive", "sh:maxInclusive", "sh:minExclusive", "sh:maxExclusive", "sh:alternativePath",
    "sh:targetClass", "sh:minCount", "sh:maxCount",
]
SPARQL_PREDICATES = {"sh:sparql", "sh:select", "sh:ask", "sh:rule", "sh:SPARQLRule", "sh:SPARQLConstraint"}


def constructs(ctx: dict, data: dict) -> dict[str, list[str]]:
    """OWL / SHACL constructs (and custom links) used by each entry's own blocks."""
    g = build(ctx, data)
    out: dict[str, list[str]] = {}
    for owner in dict.fromkeys(o for _, _, _, o in g.blocks):
        part = Graph()
        part.blocks = [b for b in g.blocks if b[3] == owner]
        p = Parsed(part.text())
        used = set()
        custom = set()
        for s, pred, o in p.triples():
            if isinstance(s, str) and s in VOCAB_SUBJECTS:
                continue
            if s == ":" + owner and pred == "rdf:type":
                if o not in (":Clarification", ":Concept", ":AliasSet", ":Hierarchy", ":GeneralRule"):
                    used.add(o)
                continue
            used.add(pred)
            if pred == "rdf:type" and isinstance(o, str):
                used.add(o)
            if pred.startswith(":") and pred not in ANNOTATION_PREDICATES:
                custom.add(pred)
        out[owner] = [c for c in _CONSTRUCTS if c in used] + sorted(custom) + sorted(used & SPARQL_PREDICATES)
    return out


VOCAB_SUBJECTS = {":" + k for k in VOCAB}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
L1_CELL = "SQL-L1-onto"
TOKEN_CELLS = ("SQL-L1", L1_CELL, "SQL-L1plus", CELL)
TOKEN_REFERENCE = ("SQL-L3a",)
CONTEXT_LIMIT = {
    "url": "https://api-docs.deepseek.com/quick_start/pricing", "checked": "2026-11-04",
    "by": "协调会话", "model": "deepseek-flash（DeepSeek-V4.1-Flash-1017）", "context": 1_000_000, "max_output": 384_000,
}


def token_rows() -> list[tuple[str, int, int, int]]:
    """(cell, system-message chars, semantic-context tokens, system-message tokens)."""
    from harness import cells, run_direct

    known = {**cells.CELLS, **cells.L1PLUS_CELLS}
    rows = []
    for name in TOKEN_CELLS + TOKEN_REFERENCE:
        system = run_direct.system_for(known[name])
        rows.append((name, len(system), run_direct.estimate_tokens_from_text(run_direct.context_text(known[name])),
                     run_direct.estimate_tokens_from_text(system)))
    return rows


def l1_tiers(ctx: dict) -> dict:
    """Conventions and metrics by the same three tiers."""
    names = {m["name"] for m in ctx["metrics"]}
    pure_ratio = [m["name"] for m in ctx["metrics"] if m.get("numerator") in names
                  and m.get("denominator") in names and not m.get("default_filters")]
    return {"conventions": (0, len(ctx["conventions"]), 0), "metrics": (len(pure_ratio), len(ctx["metrics"]) - len(pure_ratio), 0),
            "pure_ratio": pure_ratio}


def report(ctx: dict, data: dict, p_l1: Parsed, p_full: Parsed, sub: dict, tokens) -> str:
    pct = lambda a, b: f"{a / b:.0%}"  # noqa: E731
    cols = [col for ds in ctx["datasets"] for col in ds["columns"]]

    def l1_counts(p):
        return [
            len([s for s in p.order if {":FactTable", ":DimensionTable"} & set(p.all(s, "rdf:type"))]),
            len([s for s in p.order if p.opt(s, ":sqlType") is not None]),
            sum(len(p.all(s, ":enumValue")) for s in p.order),
            len([s for s in p.order if p.opt(s, ":joinFrom") is not None]),
            len(p.typed(":Metric")), len(p.typed(":Convention")), len(p.typed(":Synonym")),
            len(p.typed(":MultiPathDefault")), len(p.typed(":DataQualityIssue")),
        ]
    src = [len(ctx["datasets"]), len(cols), sum(len(c.get("values", [])) for c in cols), len(ctx["relationships"]),
           len(ctx["metrics"]), len(ctx["conventions"]), len(ctx["synonyms"]), len(ctx["multi_path_defaults"]),
           len(ctx["data_quality"])]
    labels = ["表", "字段", "枚举值", "关系", "指标", "约定", "同义词", "多路径默认", "数据质量"]
    a, b = l1_counts(p_l1), l1_counts(p_full)
    ids = [item["id"] for s in SECTIONS for item in data[s]]
    l1t = l1_tiers(ctx)
    c_full = counts(ctx, data, p_full)
    wide = sum(1 for e in c_full["entries"] if e[2] == FORMAL)
    cons = constructs(ctx, data)
    tiers_new = Counter(TIERS[i][1] for i in ids)
    tiers_old = Counter(TIERS[i][0] for i in ids)
    same = [i for i in ids if TIERS[i][0] == TIERS[i][1]]

    def ann_split(p):
        t = p.triples()
        ann = sum(1 for _, pred, _ in t if pred in ANNOTATION_PREDICATES)
        return len(t), ann

    t1, a1 = ann_split(p_l1)
    t2, a2 = ann_split(p_full)
    sparql = sorted({x for v in cons.values() for x in v if x in SPARQL_PREDICATES})
    plus_tok = dict((r[0], r[3]) for r in tokens)["SQL-L1plus"]
    limit = CONTEXT_LIMIT
    lines = [
        "# L1-onto / L3a-full 逐条对应核对（T34）", "",
        "复现：`uv run python -m render.l3a_full`（写 `build/contexts/SQL-L1-onto.yaml`、`build/contexts/SQL-L3a-full.yaml` 与本报告）；"
        "测试：`uv run pytest tests/test_l3a_full.py`（加 `--with rdflib` 另做通用解析器复核）。", "",
        "## 两份本体", "",
        "- **SQL-L1-onto**：只含 L1（`semantic/source.yaml` 经 `render.context.render_l1`，即 SQL-L1 的上下文）。",
        "- **SQL-L3a-full**：L1 加 `semantic/l1plus.yaml` 的 109 条（`render.l1plus.overlay`，与 SQL-L1plus 的 `l1plus` 节相同）。",
        "- 同一个生成器（`render.l3a_full.build`）：只喂 L1 得到前者，喂 L1 和 109 条得到后者；不是从后者的文本里删。"
        "序列化确定、可复现（测试在不同 `PYTHONHASHSEED` 下各生成一次，逐字节相同）。", "",
        "## 怎么核对", "",
        "1. **反向重建**：核对器解析生成的 Turtle（本模块自带的、保留文档顺序的解析器，只认生成器用到的子集），"
        "从图里反解出 SQL-L1 的上下文（两份都做）和 L1+ 的 overlay（SQL-L3a-full），要求与源**逐字段相等**（含列表顺序、标量类型）。"
        "SQL-L1-onto 另查：109 条的编号（`A01`…`H13`、`G01`、`D05b` 这类）在整份文本里一个都不出现。",
        f"2. **子图**（按图比，不比文本）：把三元组规范化（空白节点按内容展开）后按多重集比较。SQL-L1-onto 的 {sub['l1']:,} 个三元组"
        f"全部在 SQL-L3a-full 的 {sub['full']:,} 个里；差 {sub['full'] - sub['l1']:,} 个，恰好等于按条目分别生成的三元组之和，"
        f"每个都追到条目编号：109 条共 {sum(v for k, v in sub['per_entry'].items() if k != L1PLUS_HEADER):,} 个，"
        f"另 {sub['per_entry'][L1PLUS_HEADER]} 个属于 L1+ 的文件头 `:L1plus`（`l1plus.yaml` 顶层的 version、base、title、as_of_date 与两个词汇声明，"
        "不属于任何一条；保留它是为了 SQL-L1plus 的 `l1plus` 节能逐字段重建）。"
        "109 条里只用到的词汇，声明归第一个用到它的条目。不多不少，否则渲染失败。",
        "3. 本体自己命名空间里用到的每个节点都有定义；生成结果可重现。",
        "4. 通用解析器复核：rdflib 解析两份文本，三元组数与本模块解析器一致（rdflib 不是项目依赖，未安装时该测试跳过）。",
        "5. 不运行 OWL 推理机或 SHACL 引擎，不编译查询。", "",
        "## L1：两份本体里都出现且数量相同", "",
        "| 项 | 源 | SQL-L1-onto | SQL-L3a-full |", "|---|---|---|---|",
        *[f"| {lab} | {x} | {y} | {z} |" for lab, x, y, z in zip(labels, src, a, b)], "",
        "表是 OWL 类（行是实例），字段是数据属性（rdfs:domain 表、rdfs:range xsd 类型，另保留 ClickHouse 类型原文），"
        "外键是对象属性（多对一 = owl:FunctionalProperty，一对一再加 owl:InverseFunctionalProperty），"
        "枚举值是个体（`:enumValue [ :code … ; :meaning … ]`，没有写成闭合 `sh:in`：L1 没说哪些清单是完整的），"
        "同义词是「说法 → 指标 / 字段」的链接，多路径默认能解析的写成有序关系链。", "",
        "### L1 的约定与指标，按三档", "",
        "三档（与 T26 对齐）：(1) 核心口径已形式化：决定 SQL 怎么写的那部分是公理、形状或个体，不只在注解里；"
        "(2) 只有声明：类型、定义域值域、链接，核心口径在注解里；(3) 纯注解。两份本体的 L1 部分相同，下表对两份都成立。", "",
        "| 项 | (1) 核心已形式化 | (2) 只有声明 | (3) 纯注解 | 说明 |", "|---|---|---|---|---|",
        f"| 约定 | 0 | {l1t['conventions'][1]} | 0 | 适用的表、字段、指标是链接；规则是文字 |",
        f"| 指标 | {l1t['metrics'][0]} | {l1t['metrics'][1]} | 0 | (1) 是纯比率、分子分母都链接到指标：{'、'.join(l1t['pure_ratio'])}；"
        "(2) 有表与约定的链接，口径是文字或注解里的 SQL 表达式（折扣率的分子分母虽是链接，但「PromotionKey != 1」的默认筛选在注解，归 (2)） |", "",
        "## L1+ 109 条，按三档（新旧对照）", "",
        "| 档 | 旧 SQL-L3a | SQL-L3a-full |", "|---|---|---|",
        *[f"| ({k}) | {tiers_old[k]}（{pct(tiers_old[k], len(ids))}） | {tiers_new[k]}（{pct(tiers_new[k], len(ids))}） |" for k in (1, 2, 3)], "",
        f"和旧 L3a 同档的 {len(same)} 条：{'、'.join(same)}；其余 {len(ids) - len(same)} 条档位提高，理由逐条见下表。",
        f"SHACL-SPARQL 或其他查询式规则：{'、'.join(sparql) if sparql else '没有用'}（指标口径都用注解里的 SQL 片段，按卡片允许的写法）。", "",
        f"**宽口径**（上一版报的）：只要条目名下有任何一条非注解、非 `:ref`、非自身类型的三元组就算形式化，"
        f"这样是 {wide} 条（{pct(wide, len(ids))}）。它把「只有声明」也算进形式化，比上面的三档宽，保留作参考。", "",
        "旧 L3a 的档位按旧生成器（`render/l1plus.py`）的实际输出判：A / D / G 条只有原文注解树；E 条有「说法 → 取值」个体，"
        "但列表、字典取值和 E07 的筛选写法被丢掉；H 条有类与子类，成员定义只有「开头是字面等式且后面紧跟（、；或结尾」才转 hasValue，"
        "没有划分公理和键。", "",
        "## 三元组", "",
        f"SQL-L1-onto {t1:,} 个，注解 {a1:,}（{pct(a1, t1)}），其余 {t1 - a1:,}（{pct(t1 - a1, t1)}）；"
        f"SQL-L3a-full {t2:,} 个，注解 {a2:,}（{pct(a2, t2)}），其余 {t2 - a2:,}（{pct(t2 - a2, t2)}）。"
        "列表按 rdf:first / rdf:rest 展开计；注解 = 谓词是 rdfs:label、rdfs:comment、skos:altLabel 或本体声明的注解属性。", "",
        "## 系统消息的 token 数", "",
        "方法：`harness.run_direct.system_for` 拼出完整系统消息（系统提示 + 语义上下文 + 语法说明），"
        "用 harness 的 `estimate_tokens_from_text` 估算（DeepSeek 官方经验比例：中文字符 ≈ 0.6 token，其他字符 ≈ 0.3 token）。"
        "是估算，不是分词器的实数；正式运行以 API 返回的用量为准。各单元的系统提示与语法说明逐字节相同（测试核对），差别只在语义上下文。", "",
        "| 单元 | 组 | 系统消息字符数 | 语义上下文（估算 token） | 系统消息（估算 token） | 对 SQL-L1plus | 占上下文上限 |",
        "|---|---|---|---|---|---|---|",
        *[f"| {name} | {({'SQL-L1': '1 文字', L1_CELL: '1 本体', 'SQL-L1plus': '2 文字', CELL: '2 本体'}).get(name, '参考（旧，混合写法）')} "
          f"| {chars:,} | {ctx_tok:,} | {tok:,} | {tok / plus_tok:.2f}× | {tok / limit['context']:.1%} |"
          for name, chars, ctx_tok, tok in tokens], "",
        f"上下文上限：{limit['model']} 上下文 {limit['context']:,} token、最大输出 {limit['max_output']:,} token；"
        f"来源 DeepSeek 官方文档 {limit['url']}，{limit['checked']} 由{limit['by']}查（盲写会话访问该网址被拒）。"
        "四份都远低于上限的 80%。", "",
        "## 逐条", "",
        "构造：条目自己生成的三元组里用到的 OWL / SHACL 词汇与本体的自定义属性（`:ref` 是指向 L1 节点的链接）；不含词汇声明。", "",
        "| 节 | 编号 | 旧档 | 新档 | 同 / 改 | 用到的构造 | 说明 |", "|---|---|---|---|---|---|---|",
    ]
    for section in SECTIONS:
        for item in data[section]:
            i = item["id"]
            old, new, why = TIERS[i]
            lines.append(f"| {section} | {i} | ({old}) | ({new}) | {'同' if old == new else '改'} | "
                         f"{' '.join(f'`{x}`' for x in cons.get(i, [])) or '—'} | {why} |")
    return "\n".join(lines) + "\n"


def main():
    from render.common import dump_yaml
    import yaml

    ctx, data = l1_context(), overlay()
    texts = {L1_CELL: turtle(ctx, None), CELL: turtle(ctx, data)}
    p_l1 = check(ctx, None, texts[L1_CELL])
    p_full = check(ctx, data, texts[CELL])
    sub = check_subgraph(ctx, data, texts[L1_CELL], texts[CELL])
    BUILD.joinpath("contexts").mkdir(parents=True, exist_ok=True)
    for name, text in texts.items():
        out = BUILD / "contexts" / f"{name}.yaml"
        out.write_text(dump_yaml({"ontology_turtle": text}), encoding="utf-8")
        if yaml.safe_load(out.read_text(encoding="utf-8"))["ontology_turtle"] != text:
            raise ValueError("YAML wrapper changed the Turtle text")
    from render.context import main as render_main

    render_main(["SQL-L1", "SQL-L1plus", "SQL-L3a"])
    tokens = token_rows()
    if any(tok > 0.8 * CONTEXT_LIMIT["context"] for _, _, _, tok in tokens):
        raise SystemExit("A context exceeds 80% of the model's context window: stop and report (T34 card)")
    REPORT.write_text(report(ctx, data, p_l1, p_full, sub, tokens), encoding="utf-8")
    print(f"triples L1-onto {sub['l1']:,}, L3a-full {sub['full']:,}; tokens {[(r[0], r[3]) for r in tokens]}")


if __name__ == "__main__":
    main()
