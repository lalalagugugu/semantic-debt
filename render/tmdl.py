"""Generate the three Power BI projects (PBIP, TMDL) for DAX-L0, DAX-L1 and DAX-L2.

    uv run python render/tmdl.py          # → build/pbip/{retail-L0,retail-L1,retail-L2}/

Tables and columns come from the Parquet files (types from render/physical_schema.json,
which is what export_parquet.py wrote); the data directory is the `DataDir`
parameter, filled from $SEMDEBT_DATA_DIR/parquet at render time — on Windows, run
this script there (T17), or change the parameter in Desktop.

    L0  L0 names (renamed in Power Query), technical columns as calculated columns,
        only the kept relationships, no description, no synonym, no instruction.
    L1  original names, table and column descriptions, column synonyms (linguistic
        metadata), everything without a native place (conventions, relationship use,
        metric text, data quality, metric synonyms) in the AI instructions.
    L2  L1 plus every metrics.yaml measure (render/measures.py), measure synonyms.

The location of descriptions, synonyms and AI instructions follows the PBIP format
as documented; T17 checks it against a project saved by Desktop (task card T10/T17).

Model constraints the YAML contexts do not have (recorded, not hidden):
  - Power BI allows one active relationship between two tables along any path.
    DimStore.GeographyKey → DimGeography and DimMachine.StoreKey → DimStore are
    inactive (multi_path_defaults: customer geography is the default); DAX reaches
    them with USERELATIONSHIP.
  - Self-referencing parent keys (DimAccount, DimEmployee, DimEntity) cannot be
    relationships; they stay plain columns.
  - Four Float64 foreign keys are typed Int64 in Power Query so their relationships
    are valid (KEY_CASTS).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from render.common import BUILD, DAX_TYPES, l0_map, logical_type, metric_callables, metrics_file, physical_schema, source  # noqa: E402
from render.measures import DAX_CALCULATED_COLUMNS, dax_measures  # noqa: E402

OUT_DIR = BUILD / "pbip"
NS = uuid.UUID("6f1c4a52-31b7-4d5e-9a0e-5d7f0d3c2b10")

INACTIVE = {("DimStore.GeographyKey", "DimGeography.GeographyKey"), ("DimMachine.StoreKey", "DimStore.StoreKey")}
KEY_CASTS = {("DimStore", "EntityKey"), ("DimStore", "EmployeeKey"),
             ("DimProduct", "ProductSubcategoryKey"), ("DimSalesTerritory", "EmployeeKey")}
DATE_TABLE = ("DimDate", "DateKey")


def tag(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


def q(name: str) -> str:
    """TMDL / DAX object name, quoted when needed."""
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "'" + name.replace("'", "''") + "'"


def doc(text: str | None, indent: str) -> list[str]:
    if not text:
        return []
    return [f"{indent}/// {line}" if line else f"{indent}///" for line in " ".join(text.split()).split("\n")]


def expr_block(expr: str, indent: str) -> list[str]:
    return [f"{indent}{line}" if line else "" for line in expr.splitlines()]


def data_dir() -> str:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    return str(Path(root).expanduser() / "parquet") if root else "SET_DataDir_TO_THE_PARQUET_DIRECTORY"


# ---------------------------------------------------------------------------
# L0 technical columns: the three expression shapes used in l0_map.yaml
# ---------------------------------------------------------------------------
def l0_technical_dax(expr: str, table: str, date_col: str) -> tuple[str, str]:
    d = f"{q(table)}[{date_col}]"
    if expr == "toUInt32(toYYYYMMDD(DateKey))":
        return f"YEAR ( {d} ) * 10000 + MONTH ( {d} ) * 100 + DAY ( {d} )", "int64"
    if m := re.fullmatch(r"'([A-Z0-9]+)'", expr):
        return f'"{m.group(1)}"', "string"
    if expr == "toDateTime(DateKey, 'UTC') + toIntervalHour(26)":
        return f"{d} + 1 + TIME ( 2, 0, 0 )", "dateTime"
    raise ValueError(f"l0_map.yaml 里有渲染器不认识的技术字段表达式：{expr}")


# ---------------------------------------------------------------------------
# Model assembly
# ---------------------------------------------------------------------------
class Project:
    def __init__(self, tier: str):
        self.tier = tier
        self.name = f"retail-{tier}"
        self.l0 = tier == "L0"
        m = l0_map()
        self.l0_tables = {t["source"]: t for t in m["tables"]}

    # names
    def tname(self, t: str) -> str:
        return self.l0_tables[t]["l0"] if self.l0 else t

    def cname(self, t: str, c: str) -> str:
        return self.l0_tables[t]["columns"][c] if self.l0 else c

    def relationships(self) -> list[tuple[str, str, bool]]:
        if self.l0:
            kept = l0_map()["relationships"]["kept"]
            return [(r["from"], r["to"], True) for r in kept]
        out = []
        for r in source()["relationships"]:
            if r["from"].split(".")[0] == r["to"].split(".")[0]:
                continue
            out.append((r["from"], r["to"], (r["from"], r["to"]) not in INACTIVE))
        return out

    def table_file(self, ds: dict, measures: list[tuple[str, str, str]]) -> str:
        t = ds["name"]
        tn = self.tname(t)
        types = dict(physical_schema()["retail"][t])
        lines = []
        if not self.l0:
            lines += doc(f"{ds['title']}。{ds['grain']} {ds['description']} 何时使用：{ds['when_to_use']}", "")
        lines += [f"table {q(tn)}", f"\tlineageTag: {tag(self.name, t)}"]
        if t == DATE_TABLE[0]:
            lines.append("\tdataCategory: Time")
        lines.append("")

        for c in ds["columns"]:
            cn = self.cname(t, c["name"])
            ch = types[c["name"]]
            dtype = "int64" if (t, c["name"]) in KEY_CASTS else DAX_TYPES[logical_type(ch)]
            if not self.l0:
                desc = c["description"]
                if c.get("values"):
                    desc += " 取值：" + "；".join(f"{v['value']} = {v['meaning']}" for v in c["values"])
                lines += doc(desc, "\t")
            lines += [f"\tcolumn {q(cn)}", f"\t\tdataType: {dtype}"]
            if (t, c["name"]) == DATE_TABLE:
                lines.append("\t\tisKey")
            if c.get("technical") and not self.l0:
                lines.append("\t\tisHidden")
            lines += [f"\t\tlineageTag: {tag(self.name, t, c['name'])}", "\t\tsummarizeBy: none",
                      f"\t\tsourceColumn: {cn}", ""]

        if self.l0:
            date_col = self.cname(t, "DateKey") if "DateKey" in types else None
            for tc in self.l0_tables[t].get("technical_columns", []):
                expr, dtype = l0_technical_dax(tc["expr"], tn, date_col)
                lines += [f"\tcolumn {q(tc['name'])} = {expr}", f"\t\tdataType: {dtype}",
                          f"\t\tlineageTag: {tag(self.name, t, tc['name'])}", "\t\tsummarizeBy: none", ""]

        if self.tier == "L2":
            for name, expr, dtype in DAX_CALCULATED_COLUMNS.get(t, []):
                lines += [f"\tcolumn {q(name)} = {expr}", f"\t\tdataType: {dtype}", "\t\tisHidden",
                          f"\t\tlineageTag: {tag(self.name, t, name)}", "\t\tsummarizeBy: none", ""]
            for mname, expr, description in measures:
                lines += doc(description, "\t")
                lines += [f"\tmeasure {q(mname)} ="] + expr_block(expr, "\t\t\t")
                lines += [f"\t\tlineageTag: {tag(self.name, t, 'measure', mname)}", ""]

        lines += self.partition(t, tn)
        return "\n".join(lines) + "\n"

    def partition(self, t: str, tn: str) -> list[str]:
        steps = [f'Source = Parquet.Document(File.Contents(DataDir & "{os.sep}{t}.parquet"))']
        last = "Source"
        casts = [c for (tt, c) in sorted(KEY_CASTS) if tt == t]
        if casts:
            pairs = ", ".join(f'{{"{c}", Int64.Type}}' for c in casts)
            steps.append(f"Typed = Table.TransformColumnTypes({last}, {{{pairs}}})")
            last = "Typed"
        if self.l0:
            pairs = ", ".join(f'{{"{src}", "{dst}"}}' for src, dst in self.l0_tables[t]["columns"].items())
            steps.append(f"Renamed = Table.RenameColumns({last}, {{{pairs}}})")
            last = "Renamed"
        body = ["let"] + [f"    {s}," for s in steps[:-1]] + [f"    {steps[-1]}", "in", f"    {last}"]
        return [f"\tpartition {q(tn)} = m", "\t\tmode: import", "\t\tsource ="] + [f"\t\t\t\t{x}" for x in body] + [""]

    def relationships_file(self) -> str:
        lines = []
        for f, t, active in self.relationships():
            ft, fc = f.split(".")
            tt, tc = t.split(".")
            lines += [f"relationship {tag(self.name, 'rel', f, t)}",
                      f"\tfromColumn: {q(self.tname(ft))}.{q(self.cname(ft, fc))}",
                      f"\ttoColumn: {q(self.tname(tt))}.{q(self.cname(tt, tc))}"]
            if not active:
                lines.append("\tisActive: false")
            lines.append("")
        return "\n".join(lines)

    # synonyms: Power BI linguistic metadata
    def linguistic(self) -> dict:
        entities: dict[str, dict] = {}

        def add(entity: str, prop: str, terms: list[str]) -> None:
            key = f"{entity}.{prop}".lower().replace(" ", "_")
            e = entities.setdefault(key, {"Definition": {"Binding": {"ConceptualEntity": entity, "ConceptualProperty": prop}},
                                          "State": "Authored", "Terms": []})
            seen = {next(iter(x)) for x in e["Terms"]}
            e["Terms"] += [{term: {"State": "Authored"}} for term in terms if term not in seen]

        measure_home = {}
        if self.tier == "L2":
            impl = dax_measures()
            for m in metrics_file()["metrics"]:
                for ds, dax, _ in metric_callables(m):
                    measure_home[(m["name"], ds)] = (impl[(m["name"], ds)][0], dax[1:-1])
        for s in source()["synonyms"]:
            if s.get("maps_to_column"):
                t, c = s["maps_to_column"].split(".")
                add(t, c, s["terms"])
            elif s.get("maps_to_metric") and self.tier == "L2":
                m = next(x for x in metrics_file()["metrics"] if x["name"] == s["maps_to_metric"])
                home, name = measure_home[(m["name"], m["dataset"])]
                add(home, name, s["terms"])
        if self.tier == "L2":
            for m in source()["metrics"]:
                if m.get("aliases"):
                    l2 = next(x for x in metrics_file()["metrics"] if x["name"] == m["name"])
                    home, name = measure_home[(m["name"], l2["dataset"])]
                    add(home, name, [m["name"], *m["aliases"]])
        return {"Version": "1.0.0", "Language": "zh-CN", "DynamicImprovement": "HighConfidence", "Entities": entities}

    def instructions(self) -> str:
        s = source()
        out = [f"# {s['title']}", "", " ".join(s["description"].split()), "", " ".join(s["grain_note"].split()), "",
               f"数据截至 {s['as_of_date']}，币种 {s['currency']}。", "", "## 企业约定", ""]
        for c in s["conventions"]:
            out.append(f"{c['id']}. {' '.join(c['rule'].split())}")
            if c.get("note"):
                out.append(f"   - 说明：{' '.join(c['note'].split())}")
        out += ["", "## 关系的用途", ""]
        for r in s["relationships"]:
            line = f"- {r['from']} → {r['to']}（{r['cardinality']}）：{' '.join(r['use'].split())}"
            if r.get("caution"):
                line += f" 注意：{' '.join(r['caution'].split())}"
            out.append(line)
        out += ["", "## 多条路径时的默认", ""]
        for p in s["multi_path_defaults"]:
            out.append(f"- {p['pair']}：默认 {p['default']}。{' '.join(p['why'].split())}")
        out += ["", "## 指标口径", ""]
        l2 = {m["name"]: m for m in metrics_file()["metrics"]}
        for m in s["metrics"]:
            line = f"- **{m['name']}**：{' '.join(m['definition'].split())}"
            if m.get("default_filters"):
                line += " 默认筛选：" + "；".join(m["default_filters"]) + "。"
            if m.get("note"):
                line += " " + " ".join(m["note"].split())
            if self.tier == "L2":
                line += " 度量值：" + "、".join(f"{dax}（{ds}）" for ds, dax, _ in metric_callables(l2[m["name"]]))
            out.append(line)
        if self.tier != "L2":
            out += ["", "## 指标的业务说法", ""]
            for syn in s["synonyms"]:
                if syn.get("maps_to_metric"):
                    out.append(f"- {'、'.join(syn['terms'])} → {syn['maps_to_metric']}")
        out += ["", "## 数据质量", ""]
        for dq in s["data_quality"]:
            out.append(f"- **{dq['title']}**：{' '.join(dq['detail'].split())} 影响：{' '.join(dq['impact'].split())} "
                       f"做法：{' '.join(dq['workaround'].split())}")
        return "\n".join(out) + "\n"

    # files
    def write(self, root: Path) -> None:
        proj = root / self.name
        if proj.exists():
            shutil.rmtree(proj)
        sm = proj / f"{self.name}.SemanticModel"
        rp = proj / f"{self.name}.Report"
        defn = sm / "definition"
        (defn / "tables").mkdir(parents=True)
        (defn / "cultures").mkdir()
        rp.mkdir(parents=True)

        measures: dict[str, list[tuple[str, str, str]]] = {}
        if self.tier == "L2":
            impl = dax_measures()
            for m in metrics_file()["metrics"]:
                for ds, dax, _ in metric_callables(m):
                    home, expr = impl[(m["name"], ds)]
                    measures.setdefault(home, []).append((dax[1:-1], expr, m["definition"]))

        tables = []
        for ds in source()["datasets"]:
            tn = self.tname(ds["name"])
            tables.append(tn)
            (defn / "tables" / f"{tn}.tmdl").write_text(self.table_file(ds, measures.get(ds["name"], [])), encoding="utf-8")

        (defn / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1600\n", encoding="utf-8")
        model = ["model Model", "\tculture: zh-CN", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
                 "\tsourceQueryCulture: zh-CN", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull",
                 "", *[f"ref table {q(t)}" for t in tables], "", "ref cultureInfo zh-CN", ""]
        (defn / "model.tmdl").write_text("\n".join(model), encoding="utf-8")
        (defn / "relationships.tmdl").write_text(self.relationships_file(), encoding="utf-8")
        dd = data_dir().replace('"', '""')
        (defn / "expressions.tmdl").write_text(
            f'expression DataDir = "{dd}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
            f"\tlineageTag: {tag(self.name, 'DataDir')}\n\n\tannotation PBI_ResultType = Text\n", encoding="utf-8")
        culture = ["cultureInfo zh-CN", ""]
        if not self.l0:
            ling = json.dumps(self.linguistic(), ensure_ascii=False, indent=2)
            culture += ["\tlinguisticMetadata ="] + [f"\t\t\t{x}" for x in ling.splitlines()] + ["\t\tcontentType: json", ""]
        (defn / "cultures" / "zh-CN.tmdl").write_text("\n".join(culture), encoding="utf-8")
        (sm / "definition.pbism").write_text(json.dumps({"version": "4.2", "settings": {}}, indent=2) + "\n", encoding="utf-8")
        if not self.l0:
            ins = sm / "Copilot" / "Instructions"
            ins.mkdir(parents=True)
            (ins / "instructions.md").write_text(self.instructions(), encoding="utf-8")

        (rp / "definition.pbir").write_text(json.dumps(
            {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{self.name}.SemanticModel"}}}, indent=2) + "\n",
            encoding="utf-8")
        report = {"config": "{}", "layoutOptimization": 0, "resourcePackages": [], "filters": "[]",
                  "sections": [{"name": "ReportSection", "displayName": "Page 1", "displayOption": 1, "width": 1280,
                                "height": 720, "config": "{}", "filters": "[]", "visualContainers": []}]}
        (rp / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (proj / f"{self.name}.pbip").write_text(json.dumps(
            {"version": "1.0", "artifacts": [{"report": {"path": f"{self.name}.Report"}}],
             "settings": {"enableAutoRecovery": True}}, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for tier in ("L0", "L1", "L2"):
        p = Project(tier)
        p.write(OUT_DIR)
        n_rel = len(p.relationships())
        print(f"写入 {(OUT_DIR / p.name).relative_to(BUILD.parent)}：25 张表，{n_rel} 条关系")


if __name__ == "__main__":
    main()
