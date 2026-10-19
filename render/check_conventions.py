"""Generic delivery check (b): coverage tables. Reads the rendered contexts and the semantic
sources only, never questions or answers; no database, no model calls.

decisions/2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md §一 3 and §三 3. Three tables:

1. **convention × cell**: for each of the 15 conventions, in each L1-and-above cell, whether
   the cell ties it to objects the model can see:
   - *anchors*: the convention's ``applies_to_datasets`` that have a home in the cell (L1.5S:
     the ads dimension view built on that table, or the ads summary tables built from that
     fact table, per ``semantic/summary/summary.sql``);
   - *named by*: visible tables (own text or a column description), wide-table views and
     metrics whose text cites the convention (``约定 N``; metrics also by their ``conventions``
     field);
   - *notes*: L1's data_quality, multi_path_defaults and relationship notes that cite it.
   A cell is ``对象`` when some visible table or view cites it or all its anchors are visible,
   ``仅指标`` when only metric text cites it, ``仅条文`` otherwise.
   L1.5S also gets the table-choice check for conventions 1 and 2: each summary table built
   from FactOnlineSales / FactSales must say which of the two sales it comes from.
2. **summary layer × metric layer**: each L2 callable (metric × dataset) against the ads
   tables built from that dataset: stored directly (a column's ``metric``), computable
   (a ratio whose numerator and denominator are both columns of one table), or absent.
3. **DAX × Cube**: each callable's two implementations exist, the three L2 contexts carry the
   same callables, and the A / B rows of ``reports/validation/metric-text-vs-impl.md``.

    uv run python render/check_conventions.py          # writes reports/validation/delivery_coverage.md
    uv run python render/check_conventions.py --json out.json
Exit 1 when a convention is ``仅条文`` in some cell or a table-choice note is missing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from render.common import CUBE_NAMES, SEMANTIC, metrics_file, source, summary
from render.measures import cube_measures, dax_measures

REPO = Path(__file__).resolve().parent.parent
CONTEXTS = REPO / "build" / "contexts"
OUT = REPO / "reports" / "validation" / "delivery_coverage.md"
IMPL_REPORT = REPO / "reports" / "validation" / "metric-text-vs-impl.md"

TIERS = ["SQL-L1", "SQL-L1.5W", "SQL-L1.5S", "SQL-L2"]
OTHER = ["DAX-L1", "DAX-L2", "JSON-L2"]
TWIN = {"DAX-L1": "SQL-L1", "DAX-L2": "SQL-L2", "JSON-L2": "SQL-L2"}
L2_CELLS = ["SQL-L2", "JSON-L2", "DAX-L2"]

CITE = re.compile(r"约定\s*(\d+(?:\s*(?:、|和|与|及|/|,|，|\+)\s*(?:约定\s*)?\d+)*)")
DATASET_TEXT = ("title", "description", "grain", "cautions", "when_to_use", "differs_from")
METRIC_TEXT = ("definition", "numerator", "denominator", "default_filters", "note")
SALES_SIDE = {"FactOnlineSales": 1, "FactSales": 2}  # table-choice conventions 1 and 2
_CUBE_BACK = {v: k for k, v in CUBE_NAMES.items()}


def cites(obj) -> set[int]:
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return {int(n) for m in CITE.findall(text) for n in re.findall(r"\d+", m)}


def logical(name: str) -> str:
    """Physical name as one stack writes it → source.yaml / ads name."""
    name = name.split(".")[-1] if name.startswith(("retail.", "ads.", "dwd.")) else name
    return _CUBE_BACK.get(name, name)


def lineage() -> dict[str, set[str]]:
    """ads summary table → the retail fact tables its SELECT reads (summary.sql)."""
    sql = re.sub(r"--[^\n]*", "", (SEMANTIC / "summary" / "summary.sql").read_text(encoding="utf-8"))
    parts = re.split(r"(?=CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW))", sql)
    out: dict[str, set[str]] = {}
    for p in parts:
        m = re.match(r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?ads\.(\w+)", p)
        if m and not m.group(1).startswith("dim_"):
            out[m.group(1)] = set(re.findall(r"retail\.(Fact\w+)", p))
    return out


def dim_bases() -> dict[str, str]:
    from render.context import ads_dimension_views
    return {v["base"]: v["view"] for v in ads_dimension_views()}


def load(cell: str) -> dict:
    return yaml.safe_load((CONTEXTS / f"{cell}.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. convention × cell
# ---------------------------------------------------------------------------
def table_cites(ds: dict) -> set[int]:
    own = cites([ds.get(k) for k in DATASET_TEXT if ds.get(k)])
    for c in ds.get("columns", []):
        own |= cites(c.get("description", ""))
    return own


def metric_cites(m: dict) -> set[int]:
    return set(m.get("conventions") or []) | cites([m.get(k) for k in METRIC_TEXT if m.get(k)])


def note_cites(ctx: dict) -> list[tuple[str, str, set[int]]]:
    out = [("data_quality", d["id"], cites(d)) for d in ctx.get("data_quality", []) or []]
    out += [("multi_path_defaults", d["pair"], cites(d)) for d in ctx.get("multi_path_defaults", []) or []]
    out += [("relationships", f"{d['from']}→{d['to']}", cites(d.get("use", "")))
            for d in ctx.get("relationships", []) or []]
    return out


def convention_row(conv: dict, cell: str, ctx: dict, lin: dict[str, set[str]], dims: dict[str, str]) -> dict:
    n = conv["id"]
    shown = {c["id"] for c in ctx["conventions"]}
    names = {logical(ds["name"]) for ds in ctx["datasets"]}
    want = conv.get("applies_to_datasets") or []
    if cell.endswith("L1.5S"):
        homes = {t: ([dims[t]] if t in dims else sorted(a for a, f in lin.items() if t in f)) for t in want}
    else:
        homes = {t: [t] if t in names else [] for t in want}
    homed = [t for t, h in homes.items() if h and all(x in names for x in h)]
    tables = sorted(logical(ds["name"]) for ds in ctx["datasets"] if n in table_cites(ds))
    views = []
    if ctx.get("widetables"):
        views = sorted(logical(v["name"]) for v in ctx["widetables"]["views"] if n in cites(v))
    metrics = [m for m in ctx["metrics"] if n in metric_cites(m)]
    notes = [f"{s}:{i}" for s, i, c in note_cites(ctx) if n in c]
    if tables or views or (want and len(homed) == len(want) and not cell.endswith("L1.5S")):
        verdict = "对象"
    elif metrics:
        verdict = "仅指标"
    else:
        verdict = "仅条文"
    return {"convention": n, "cell": cell, "rule_shown": n in shown, "anchors": f"{len(homed)}/{len(want)}",
            "anchor_homes": homes, "tables": tables, "views": views, "metrics": [m["name"] for m in metrics],
            "callables": sum(bool(m.get("callables")) for m in metrics), "notes": notes, "verdict": verdict}


def table_choice(ctx: dict, lin: dict[str, set[str]]) -> list[dict]:
    """L1.5S: each ads table built from FactOnlineSales / FactSales cites the convention for its side."""
    out = []
    for ds in ctx["datasets"]:
        t = logical(ds["name"])
        sides = sorted(SALES_SIDE[f] for f in lin.get(t, ()) if f in SALES_SIDE)
        if sides:
            own = table_cites(ds)
            out.append({"table": t, "conventions": sides, "ok": all(s in own for s in sides)})
    return out


# ---------------------------------------------------------------------------
# 2. summary layer × metric layer
# ---------------------------------------------------------------------------
def _component(text: str | None) -> str | None:
    return re.sub(r"[（(].*?[)）]", "", text).strip() if text else None


def summary_vs_metrics(lin: dict[str, set[str]], dims: dict[str, str]) -> list[dict]:
    src = {m["name"]: m for m in source()["metrics"]}
    tables = summary()["tables"]
    rows = []
    for m in metrics_file()["metrics"]:
        s = src[m["name"]]
        for ds, dax, cube in [(m["dataset"], m["dax_measure"], m["cube_member"])] + (
                [(m["alternate_dataset"], m["alternate_dax_measure"], m["alternate_cube_member"])]
                if m.get("alternate_dataset") else []):
            direct, derived = [], []
            num, den = _component(s.get("numerator")), _component(s.get("denominator"))
            for t in tables:
                if ds not in lin.get(t["name"], ()):
                    continue
                stored = {c.get("metric") for c in t["columns"]} | {c["name"] for c in t["columns"]}
                if m["name"] in {c.get("metric") for c in t["columns"]}:
                    direct.append(t["name"])
                elif num and den and all(x in stored or x.removesuffix("合计") in stored for x in (num, den)):
                    derived.append(t["name"])
            rows.append({"metric": m["name"], "dataset": ds, "additivity": s["additivity"], "dax": dax,
                         "cube": cube, "direct": direct, "derived": derived, "dim_view": dims.get(ds)})
    return rows


# ---------------------------------------------------------------------------
# 3. DAX × Cube
# ---------------------------------------------------------------------------
def impl_classes() -> dict[str, str]:
    """metric name → A/B row id from metric-text-vs-impl.md."""
    out = {}
    if IMPL_REPORT.exists():
        for line in IMPL_REPORT.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\|\s*([AB]\d+)\s*\|\s*([^|]+?)\s*\|", line)
            if m:
                for name in re.split(r"[、，,]", m.group(2)):
                    out.setdefault(name.strip(), m.group(1))
    return out


def dax_vs_cube(ctxs: dict[str, dict]) -> list[dict]:
    dax, cube, cls = dax_measures(), cube_measures(), impl_classes()
    per_cell = {c: {m["name"]: len(m.get("callables") or []) for m in ctxs[c]["metrics"]} for c in L2_CELLS}
    rows = []
    for (name, ds) in dax:
        rows.append({"metric": name, "dataset": ds, "dax": bool(dax[(name, ds)][1]),
                     "cube": len(cube.get((name, ds), [])),
                     "contexts_agree": len({per_cell[c].get(name) for c in L2_CELLS}) == 1,
                     "class": cls.get(name, "")})
    return rows


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def run() -> dict:
    lin, dims = lineage(), dim_bases()
    ctxs = {c: load(c) for c in TIERS + OTHER}
    conv = source()["conventions"]
    t1 = [convention_row(c, cell, ctxs[cell], lin, dims) for c in conv for cell in TIERS + OTHER]
    return {"conventions": t1, "table_choice": table_choice(ctxs["SQL-L1.5S"], lin),
            "summary_vs_metrics": summary_vs_metrics(lin, dims), "dax_vs_cube": dax_vs_cube(ctxs),
            "rules": {c["id"]: c["rule"] for c in conv}, "groups": {c["id"]: c["group"] for c in conv}}


def _j(xs, k=3) -> str:
    xs = list(xs)
    return "—" if not xs else "、".join(f"`{x}`" for x in xs[:k]) + (f" 等 {len(xs)} 个" if len(xs) > k else "")


def render_md(r: dict) -> str:
    by = {(x["convention"], x["cell"]): x for x in r["conventions"]}
    ids = sorted(r["rules"])
    L = ["# 通用交付检查（b）：覆盖表", "",
         "- 生成：`uv run python render/check_conventions.py`（只读 `build/contexts/` 与 `semantic/`，"
         "不读题库，不开 chDB，不调模型）。引用检查（a）见 `render/check_references.py`。",
         "- 依据：`decisions/2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md` 第一节第 3 条、第三节第 3 条。", ""]

    L += ["## 1. 约定 × 档位", "",
          "每格：判定 · 锚点（约定的 `applies_to_datasets` 在本单元有落点的个数）· 点名它的表 / 视图 / 指标个数。",
          "判定：**对象** = 有可见的表或视图在自己的说明里点名这条约定，或（L1.5S 以外）它的锚点全部可见；"
          "**仅指标** = 只有指标文字点名；**仅条文** = 只有条文本身。L1.5S 的锚点按血缘算："
          "维度表 → 建在它上面的 `ads.dim_*`，事实表 → 由它汇总出的 `ads` 表。", "",
          "| 约定 | 组 | " + " | ".join(TIERS) + " |", "|---|---|" + "---|" * len(TIERS)]
    for n in ids:
        cells = []
        for cell in TIERS:
            x = by[(n, cell)]
            mark = {"对象": "✅", "仅指标": "⚠️", "仅条文": "❌"}[x["verdict"]]
            extra = f"表 {len(x['tables'])}" + (f"·视图 {len(x['views'])}" if cell.endswith("1.5W") else "")
            cells.append(f"{mark} {x['verdict']} · 锚 {x['anchors']} · {extra}·指标 {len(x['metrics'])}"
                         + (f"（可调用 {x['callables']}）" if cell.endswith("L2") else ""))
        L.append(f"| {n} | {r['groups'][n]} | " + " | ".join(cells) + " |")
    same = [c for c in OTHER if all(by[(n, c)]["verdict"] == by[(n, TWIN[c])]["verdict"]
                                    and by[(n, c)]["anchors"] == by[(n, TWIN[c])]["anchors"]
                                    and len(by[(n, c)]["tables"]) == len(by[(n, TWIN[c])]["tables"])
                                    and len(by[(n, c)]["metrics"]) == len(by[(n, TWIN[c])]["metrics"]) for n in ids)]
    L += ["", f"DAX 与 JSON 单元：逐格与对应的 SQL 单元相同的有 {len(same)}/{len(OTHER)} 个"
          f"（{'、'.join(f'{c} = {TWIN[c]}' for c in same) or '无'}）。", ""]

    L += ["### L1 的配套说明在各档位是否还在", "",
          "L1 的 data_quality、多路径默认、关系用途里点名某条约定的条目，在本单元出现的条数。", "",
          "| 约定 | " + " | ".join(TIERS) + " |", "|---|" + "---|" * len(TIERS)]
    for n in ids:
        if by[(n, "SQL-L1")]["notes"]:
            L.append(f"| {n} | " + " | ".join(str(len(by[(n, c)]["notes"])) for c in TIERS) + " |")
    L += ["", "### L1.5S：点名约定的汇总表", "",
          "| 约定 | 锚点的落点 | 点名它的汇总表 / 维度视图 | 点名它的指标 |", "|---|---|---|---|"]
    for n in ids:
        x = by[(n, "SQL-L1.5S")]
        homes = "；".join(f"{t} → {_j(h, 2)}" for t, h in x["anchor_homes"].items()) or "—（无 applies_to）"
        L.append(f"| {n} | {homes} | {_j(x['tables'])} | {_j(x['metrics'])} |")

    L += ["", "### L1.5S：选表约定（1、2）在每张销售汇总表上", "",
          "由线上销售（FactOnlineSales）汇总的表要点名约定 1，由全渠道销售（FactSales）汇总的表要点名约定 2，"
          "模型才能从表本身看出这是哪一种「销售」。", "", "| 汇总表 | 应点名 | 已点名 |", "|---|---|---|"]
    for t in r["table_choice"]:
        L.append(f"| `{t['table']}` | 约定 {'、'.join(map(str, t['conventions']))} | {'✅' if t['ok'] else '❌'} |")

    rows = r["summary_vs_metrics"]
    cnt = lambda f: sum(1 for x in rows if f(x))  # noqa: E731
    L += ["", "## 2. 汇总表 × 指标层", "",
          f"L2 的 {len(rows)} 个可调用对象（指标 × 数据集），对照由同一数据集汇总出的 `ads` 表："
          f"直接存有 {cnt(lambda x: x['direct'])} 个，可由一张表里的分子分母现算 "
          f"{cnt(lambda x: not x['direct'] and x['derived'])} 个，维度指标落在维度视图上 "
          f"{cnt(lambda x: not x['direct'] and not x['derived'] and x['dim_view'])} 个，未自动匹配 "
          f"{cnt(lambda x: not x['direct'] and not x['derived'] and not x['dim_view'])} 个。",
          "「现算」按名字匹配分子分母（指标名或列名），是启发式。**「未自动匹配」不等于汇总层答不了**："
          "其中有靠筛选列得到的（如客户分层、是否新客，表说明里写了「不另设列」），也有跨期、跨行才能算的"
          "（同比、环比、占比、同店），还有汇总层确实没有的数据（IT 成本、停机）。逐个能否回答要人工看，"
          "覆盖内外以 T06 的覆盖标注为准。", "",
          "| 指标 | 数据集 | 可加性 | Cube | DAX | 汇总层 |", "|---|---|---|---|---|---|"]
    for x in rows:
        ads = (f"直接：{_j(x['direct'], 2)}" if x["direct"] else
               f"现算：{_j(x['derived'], 2)}" if x["derived"] else
               f"维度视图：`{x['dim_view']}`" if x["dim_view"] else "未自动匹配")
        L.append(f"| {x['metric']} | {x['dataset']} | {x['additivity']} | `{x['cube']}` | `{x['dax']}` | {ads} |")

    d = r["dax_vs_cube"]
    L += ["", "## 3. DAX × Cube", "",
          f"- {len(d)} 个可调用对象，DAX 有表达式的 {sum(x['dax'] for x in d)} 个，Cube 有成员的 "
          f"{sum(x['cube'] > 0 for x in d)} 个；三个 L2 上下文给出的调用写法个数一致的 "
          f"{sum(x['contexts_agree'] for x in d)} 个。",
          "- 实现层面的读法差异来自 `reports/validation/metric-text-vs-impl.md`（人工逐条比对，本脚本只按指标名引用）："
          "A = 两边选了同一种文字没写明的读法；B = 两边不一致或引擎做不到。", "",
          "| 类 | 可调用对象 |", "|---|---|"]
    for k in ("A", "B"):
        hit = [f"{x['metric']}·{x['dataset']}（{x['class']}）" for x in d if x["class"].startswith(k)]
        L.append(f"| {k} | {len(hit)}：{'、'.join(hit) or '—'} |")
    L.append(f"| 其余 | {sum(not x['class'] for x in d)} |")
    return "\n".join(L) + "\n"


def failures(r: dict) -> list[str]:
    bad = [f"约定 {x['convention']} 在 {x['cell']}：仅条文" for x in r["conventions"] if x["verdict"] == "仅条文"]
    bad += [f"{t['table']} 没有点名约定 {t['conventions']}" for t in r["table_choice"] if not t["ok"]]
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", help="write the full result here")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)
    r = run()
    Path(args.out).write_text(render_md(r), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(r, ensure_ascii=False, indent=1, default=sorted), encoding="utf-8")
    bad = failures(r)
    for b in bad:
        print("GAP ", b)
    print(f"写入 {Path(args.out).relative_to(REPO) if Path(args.out).is_relative_to(REPO) else args.out}；{len(bad)} 处缺口")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
