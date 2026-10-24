"""Delivery check on the DAX cells: the context a DAX cell reads must describe the model its
queries run on (T17-mac; decisions/2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md §三 3).

The YAML checks (check_references, check_conventions, check_equivalence) only read
``build/contexts/``. A DAX query runs against the Power BI model in ``build/pbip/``, so this
script parses the TMDL the renderer wrote (not ``Namer``, not ``Project``) and compares it with
``DAX-L0/L1/L2.yaml``:

1. tables: the same set;
2. columns: every context column is in the model with the same data type; every visible model
   column is in the context (hidden columns may stay out: technical columns at L1 / L2, the
   helper column of the current-inventory measures);
3. measures: at L2 every callable of the context (variants included) is a model measure and
   every model measure is a callable; L0 / L1 have none;
4. relationships: every context relationship is in the model as the context says
   (``model_relationship``: absent = active, ``inactive``, ``none`` = not a model relationship),
   and the model has no other;
5. ambiguity: along active relationships (many → one), no table reaches another by two paths,
   which Power BI rejects when it loads the model.

    uv run python render/check_pbip.py        # exit 1 on any problem; writes reports/validation/pbip_check.md
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CONTEXTS = REPO / "build" / "contexts"
PBIP = REPO / "build" / "pbip"
REPORT = REPO / "reports" / "validation" / "pbip_check.md"
TIERS = ("L0", "L1", "L2")

_NAME = r"(?:'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_]*)"
_QUALIFIED = re.compile(rf"^({_NAME})\.({_NAME})$")


def unquote(name: str) -> str:
    return name[1:-1].replace("''", "'") if name.startswith("'") else name


def parse_table(text: str) -> dict:
    """One ``tables/<name>.tmdl``: name, columns {name: (dataType, hidden)}, measure names and
    their expressions (the lines indented under ``measure X =``)."""
    table, columns, measures, expressions = None, {}, [], {}
    current, in_measure = None, None
    for line in text.splitlines():
        if in_measure and line.startswith("\t\t\t"):
            expressions[in_measure].append(line.strip())
            continue
        in_measure = None
        if m := re.match(rf"^table ({_NAME})\s*$", line):
            table = unquote(m.group(1))
        elif m := re.match(rf"^\tcolumn ({_NAME})(?:\s*=.*)?$", line):
            current = unquote(m.group(1))
            columns[current] = [None, False]
        elif m := re.match(rf"^\tmeasure ({_NAME})\s*=", line):
            in_measure = unquote(m.group(1))
            measures.append(in_measure)
            expressions[in_measure] = []
            current = None
        elif re.match(r"^\t\S", line):
            current = None
        elif current and (m := re.match(r"^\t\tdataType: (\w+)", line)):
            columns[current][0] = m.group(1)
        elif current and re.match(r"^\t\tisHidden\s*$", line):
            columns[current][1] = True
    return {"name": table, "columns": {k: tuple(v) for k, v in columns.items()}, "measures": measures,
            "expressions": {k: "\n".join(v) for k, v in expressions.items()}}


def parse_relationships(text: str) -> list[dict]:
    out, cur = [], None
    for line in text.splitlines():
        if line.startswith("relationship "):
            cur = {"active": True}
            out.append(cur)
        elif cur is not None and (m := re.match(r"^\t(fromColumn|toColumn): (.+)$", line)):
            q = _QUALIFIED.match(m.group(2).strip())
            cur[m.group(1)] = (unquote(q.group(1)), unquote(q.group(2)))
        elif cur is not None and re.match(r"^\tisActive: false\s*$", line):
            cur["active"] = False
    return out


def load_model(tier: str, root: Path = PBIP) -> dict:
    defn = root / f"retail-{tier}" / f"retail-{tier}.SemanticModel" / "definition"
    tables = [parse_table(p.read_text(encoding="utf-8")) for p in sorted((defn / "tables").glob("*.tmdl"))]
    return {"tables": {t["name"]: t for t in tables},
            "relationships": parse_relationships((defn / "relationships.tmdl").read_text(encoding="utf-8"))}


def _ref(s: str) -> tuple[str, str]:
    m = re.fullmatch(r"([A-Za-z_]\w*)\[([^\]]+)\]", s)
    if not m:
        raise ValueError(f"not a DAX column reference: {s}")
    return m.group(1), m.group(2)


def ambiguous_paths(edges: list[tuple[str, str]]) -> list[str]:
    """Pairs of tables joined by more than one path along active many → one edges."""
    graph = defaultdict(list)
    for a, b in edges:
        graph[a].append(b)
    out = []
    for start in sorted(graph):
        count: dict[str, int] = defaultdict(int)

        def walk(node: str, seen: tuple[str, ...]) -> None:
            for nxt in graph.get(node, []):
                if nxt in seen:
                    continue
                count[nxt] += 1
                walk(nxt, seen + (nxt,))

        walk(start, (start,))
        out += [f"{start} → {t}：{n} 条路径" for t, n in sorted(count.items()) if n > 1]
    return out


def check(tier: str, ctx: dict, model: dict) -> list[str]:
    problems: list[str] = []
    mt = model["tables"]
    ctx_tables = {ds["name"]: ds for ds in ctx["datasets"]}
    if set(ctx_tables) != set(mt):
        problems.append(f"表不一致：只在上下文 {sorted(set(ctx_tables) - set(mt))}，只在模型 {sorted(set(mt) - set(ctx_tables))}")
    for name in sorted(set(ctx_tables) & set(mt)):
        cols = {c["name"]: c["type"] for c in ctx_tables[name]["columns"]}
        model_cols = mt[name]["columns"]
        for c, t in cols.items():
            if c not in model_cols:
                problems.append(f"{name}[{c}]：上下文有、模型里没有")
            elif model_cols[c][0] != t:
                problems.append(f"{name}[{c}]：类型 上下文 {t} ≠ 模型 {model_cols[c][0]}")
        for c, (_, hidden) in model_cols.items():
            if not hidden and c not in cols:
                problems.append(f"{name}[{c}]：模型里可见、上下文没有")

    calls = {c["call"][1:-1] for m in ctx.get("metrics", []) for c in m.get("callables") or []}
    measures = [m for t in mt.values() for m in t["measures"]]
    if len(measures) != len(set(measures)):
        problems.append("模型里有重名的度量值")
    if calls != set(measures):
        problems.append(f"度量值不一致：只在上下文 {sorted(calls - set(measures))}，只在模型 {sorted(set(measures) - calls)}")

    model_rels = {(r["fromColumn"], r["toColumn"]): r["active"] for r in model["relationships"]}
    seen = set()
    for r in ctx.get("relationships", []):
        key = (_ref(r["from"]), _ref(r["to"]))
        mark = r.get("model_relationship")
        label = f"{r['from']} → {r['to']}"
        if mark == "none":
            if key in model_rels:
                problems.append(f"{label}：上下文标为不是模型关系，模型里却有")
            continue
        seen.add(key)
        if key not in model_rels:
            problems.append(f"{label}：上下文有、模型里没有")
        elif model_rels[key] != (mark != "inactive"):
            problems.append(f"{label}：上下文 {'非激活' if mark == 'inactive' else '激活'}，"
                            f"模型 {'激活' if model_rels[key] else '非激活'}")
    for key in sorted(set(model_rels) - seen):
        problems.append(f"{key[0][0]}[{key[0][1]}] → {key[1][0]}[{key[1][1]}]：模型里有、上下文没有")

    active = [(f[0], t[0]) for (f, t), a in model_rels.items() if a]
    problems += [f"歧义路径 {x}" for x in ambiguous_paths(active)]
    return problems


def summary(tier: str, ctx: dict, model: dict) -> dict:
    rels = model["relationships"]
    marks = defaultdict(int)
    for r in ctx.get("relationships", []):
        marks[r.get("model_relationship", "active")] += 1
    return {
        "tables": len(model["tables"]),
        "columns": sum(len(t["columns"]) for t in model["tables"].values()),
        "hidden": sum(h for t in model["tables"].values() for _, h in t["columns"].values()),
        "measures": sum(len(t["measures"]) for t in model["tables"].values()),
        "relationships": len(rels),
        "inactive": sum(not r["active"] for r in rels),
        "ctx_relationships": dict(marks),
    }


def run(contexts: Path = CONTEXTS, pbip: Path = PBIP) -> tuple[dict[str, list[str]], dict[str, dict]]:
    problems, stats = {}, {}
    for tier in TIERS:
        ctx = yaml.safe_load((contexts / f"DAX-{tier}.yaml").read_text(encoding="utf-8"))
        model = load_model(tier, pbip)
        problems[tier] = check(tier, ctx, model)
        stats[tier] = summary(tier, ctx, model)
    return problems, stats


def write_report(problems: dict[str, list[str]], stats: dict[str, dict]) -> None:
    L = ["# DAX 单元的交付检查：上下文与 Power BI 模型", "",
         "- 生成：`uv run python render/check_pbip.py`（`render/render_all.py` 也会跑）。只读 `build/contexts/DAX-*.yaml` "
         "与 `build/pbip/` 的 TMDL，不读题库，不连 Power BI，不调模型。",
         "- 依据：`decisions/2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md` 第三节第 3 条（T17-mac）。"
         "YAML 上的三项通用检查（引用、约定覆盖、等价）已含 DAX 单元；本检查补上「上下文说的就是查询跑的那个模型」。",
         "- 关系标记 `model_relationship`（只在 DAX 上下文）：`inactive` = 模型里是非激活关系，要用 `USERELATIONSHIP`；"
         "`none` = 自连接，模型里不是关系。",
         "", "| 单元 | 表 | 列（隐藏） | 度量值 | 模型关系（非激活） | 上下文关系：激活 / 非激活 / 不是模型关系 | 问题 |",
         "|---|---|---|---|---|---|---|"]
    for tier in TIERS:
        s = stats[tier]
        c = s["ctx_relationships"]
        L.append(f"| DAX-{tier} | {s['tables']} | {s['columns']}（{s['hidden']}） | {s['measures']} | "
                 f"{s['relationships']}（{s['inactive']}） | {c.get('active', 0)} / {c.get('inactive', 0)} / {c.get('none', 0)} | "
                 f"{len(problems[tier]) or '无'} |")
    for tier in TIERS:
        for p in problems[tier]:
            L.append(f"- DAX-{tier}：{p}")
    L += ["", "PBIP 能否被 Power BI Desktop 打开、描述与同义词是否被读到，静态检查管不到，留给 Windows 上的探测"
          "（`windows/README.md`）。", ""]
    REPORT.write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    problems, stats = run()
    for tier in TIERS:
        print(f"DAX-{tier}：{len(problems[tier])} 处问题")
        for p in problems[tier]:
            print(f"  - {p}")
    write_report(problems, stats)
    print(f"写入 {REPORT.relative_to(REPO)}")
    return 1 if any(problems.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
