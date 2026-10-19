"""Generate the Cube Core data model (build/cube/model/cubes/<cube>.yml).

One cube per source table (names in common.CUBE_NAMES), every non-technical column
as a dimension with the same name as in ClickHouse, the relationships of
source.yaml as joins, and the metrics of metrics.yaml as measures (implementations
in render/measures.py). This is the model SQL-L2, JSON-L2 and SQL-L2-E query.

    uv run python render/cube.py

What the model cannot carry:
  - self-joins (DimAccount / DimEmployee / DimEntity parent keys): Cube has no
    self-join; the parent key stays a plain dimension.
  - a few metrics behave differently from DAX; see render/measures.py.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from render.common import (  # noqa: E402
    BUILD, CUBE_NAMES, CUBE_TYPES, dump_yaml, logical_type, metrics_file, physical_schema, source, variant_callables,
    variant_key,
)
from render.measures import CUBE_SQL, cube_measures  # noqa: E402

OUT_DIR = BUILD / "cube" / "model" / "cubes"


def primary_key(ds: dict) -> str:
    keys = [c["name"] for c in ds["columns"] if c.get("role") == "key"]
    return keys[0] if keys else ds["columns"][0]["name"]


def build_model() -> dict[str, dict]:
    """cube name → cube definition."""
    src = source()
    types = physical_schema()["retail"]
    measures = cube_measures()
    by_cube: dict[str, list[dict]] = {}
    for m in metrics_file()["metrics"]:
        pairs = [(m["dataset"], m["cube_member"])]
        if m.get("alternate_dataset"):
            pairs.append((m["alternate_dataset"], m["alternate_cube_member"]))
        items = [(m["name"], dataset, member, m["name"], m["definition"]) for dataset, member in pairs]
        items += [(variant_key(m["name"], vid), dataset, member, f"{m['name']}（{vid}）", f"{m['definition']} 本成员：{scope}。")
                  for vid, dataset, _, member, scope in variant_callables(m)]
        for key, dataset, member, title, description in items:
            cube, name = member.split(".", 1)
            specs = measures[(key, dataset)]
            public = dict(specs[0])
            if public.pop("name") != name:
                raise ValueError(f"{member} 的实现名字对不上")
            public = {"name": name, "title": title, "description": description, **public}
            for spec in [public, *specs[1:]]:
                existing = {x["name"]: x for x in by_cube.setdefault(cube, [])}
                if spec["name"] in existing:
                    if existing[spec["name"]] != spec:
                        raise ValueError(f"{cube}.{spec['name']} 有两份不同的定义")
                    continue
                by_cube[cube].append(spec)

    joins: dict[str, list[dict]] = {}
    for r in src["relationships"]:
        ft, fc = r["from"].split(".")
        tt, tc = r["to"].split(".")
        if ft == tt:
            continue  # self-join: not expressible in Cube
        rel = {"多对一": "many_to_one", "一对一": "one_to_one", "一对多": "one_to_many"}[r["cardinality"]]
        joins.setdefault(CUBE_NAMES[ft], []).append({
            "name": CUBE_NAMES[tt],
            "relationship": rel,
            "sql": f"{{CUBE}}.{fc} = {{{CUBE_NAMES[tt]}}}.{tc}",
        })

    model: dict[str, dict] = {}
    for ds in src["datasets"]:
        cube = CUBE_NAMES[ds["name"]]
        coltypes = dict(types[ds["name"]])
        pk = primary_key(ds)
        dims = []
        for c in ds["columns"]:
            if c.get("technical") and c["name"] != pk:
                continue
            d = {"name": c["name"], "sql": f"{{CUBE}}.{c['name']}",
                 "type": CUBE_TYPES[logical_type(coltypes[c["name"]])]}
            if c["name"] == pk:
                d["primary_key"] = True
                if c.get("technical"):
                    d["public"] = False
            d["description"] = c["description"]
            dims.append(d)
        body = {"name": cube, "title": ds["title"], "description": ds["description"]}
        if ds["name"] in CUBE_SQL:
            body["sql"] = CUBE_SQL[ds["name"]]
        else:
            body["sql_table"] = f"retail.{ds['name']}"
        if cube in joins:
            body["joins"] = joins[cube]
        body["dimensions"] = dims
        if cube in by_cube:
            body["measures"] = by_cube.pop(cube)
        model[cube] = body
    if by_cube:
        raise ValueError(f"metrics.yaml 引用了不存在的 cube：{sorted(by_cube)}")
    check_model(model)
    return model


_REF = re.compile(r"\{(\w+)\}")


def check_model(model: dict[str, dict]) -> None:
    """Every {member} in a measure resolves inside its cube; every {cube} in a join exists."""
    problems = []
    for cube, body in model.items():
        members = {d["name"] for d in body["dimensions"]} | {m["name"] for m in body.get("measures", [])}
        for m in body.get("measures", []):
            for ref in _REF.findall(m.get("sql", "")):
                if ref != "CUBE" and ref not in members:
                    problems.append(f"{cube}.{m['name']} 引用了不存在的成员 {ref}")
            for f in m.get("filters", []):
                for ref in _REF.findall(f["sql"]):
                    if ref != "CUBE":
                        problems.append(f"{cube}.{m['name']} 的筛选引用了 {ref}")
            if m.get("time_shift") and not any(d["name"] == m["time_shift"][0]["time_dimension"] and d["type"] == "time"
                                              for d in body["dimensions"]):
                problems.append(f"{cube}.{m['name']} 的 time_shift 指向的不是本 cube 的时间维度")
        for j in body.get("joins", []):
            if j["name"] not in model:
                problems.append(f"{cube} 连接到不存在的 cube {j['name']}")
        names = [d["name"] for d in body["dimensions"]] + [m["name"] for m in body.get("measures", [])]
        lowered = [n.lower() for n in names]
        dup = sorted({n for n in lowered if lowered.count(n) > 1})
        if dup:
            problems.append(f"{cube} 的成员名不区分大小写时重名：{dup}")
    if problems:
        raise ValueError("Cube 模型校验未通过：\n  " + "\n  ".join(problems))


def main() -> None:
    model = build_model()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    for cube, body in model.items():
        (OUT_DIR / f"{cube}.yml").write_text(dump_yaml({"cubes": [body]}), encoding="utf-8")
    n_measures = sum(len([m for m in b.get("measures", []) if m.get("public", True)]) for b in model.values())
    print(f"写入 {OUT_DIR.relative_to(BUILD.parent)}：{len(model)} 个 cube，{n_measures} 个公开指标")


if __name__ == "__main__":
    main()
