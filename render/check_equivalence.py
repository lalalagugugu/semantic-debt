"""Check that contexts of the same tier carry the same information on every stack.

Task card T10: within one tier, the SQL and DAX contexts (and at L2 the Cube SQL and
JSON contexts) may differ only in physical-name syntax and in how a metric is
called. This script reads the rendered files in build/contexts/, rewrites each
stack's physical names into one neutral form, replaces every metric call by a
placeholder, and requires the results to be identical. Separately it checks each
call is written in its stack's syntax and names the metrics.yaml callable for that
metric and dataset, and that L2 = L1 + callables.

The normalisation is written here independently of common.Namer (it parses the
output, it does not re-run the renderer), so a renderer bug shows up as a diff.

    uv run python render/check_equivalence.py     # exit 1 on any difference
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from render.common import BUILD, CUBE_NAMES, metrics_file, variant_callables  # noqa: E402

CTX = BUILD / "contexts"

# (left cell, right cell, what is compared)
PAIRS = [
    ("SQL-L0", "DAX-L0", "L0：SQL 与 DAX"),
    ("SQL-L1", "DAX-L1", "L1：SQL 与 DAX"),
    ("SQL-L2", "DAX-L2", "L2：SQL（Cube SQL 接口）与 DAX"),
    ("SQL-L2", "JSON-L2", "L2：SQL（Cube SQL 接口）与 JSON"),
]
# L2 must equal L1 once the callables are removed
L1_VS_L2 = [("SQL-L1", "SQL-L2"), ("DAX-L1", "DAX-L2")]

STACK_OF = {"SQL-L0": "sql", "SQL-L1": "sql", "SQL-L2": "cube_sql", "JSON-L2": "cube_json",
            "DAX-L0": "dax", "DAX-L1": "dax", "DAX-L2": "dax"}

_COARSE = {
    # ClickHouse
    "Int": "number", "UInt": "number", "Float": "number", "Decimal": "number",
    "String": "string", "Date": "time", "DateTime": "time", "Bool": "boolean",
}
_DAX_COARSE = {"int64": "number", "double": "number", "decimal": "number", "string": "string",
               "dateTime": "time", "boolean": "boolean"}
_CUBE_COARSE = {"number": "number", "string": "string", "time": "time", "boolean": "boolean"}

# every name that can stand for a table, mapped to one placeholder per table
_TABLE_TOKENS = {t: f"<{t}>" for t in CUBE_NAMES}
_TABLE_TOKENS.update({c: f"<{t}>" for t, c in CUBE_NAMES.items()})
_TABLE_RE = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(sorted(_TABLE_TOKENS, key=len, reverse=True)) + r")(?![A-Za-z0-9_])")


def coarse_type(stack: str, t: str) -> str:
    if stack == "sql":
        base = re.sub(r"^(Nullable|LowCardinality)\((.*)\)$", r"\2", t)
        base = re.sub(r"^(Nullable|LowCardinality)\((.*)\)$", r"\2", base)
        for prefix, kind in sorted(_COARSE.items(), key=lambda kv: -len(kv[0])):
            if base.startswith(prefix):
                return kind
        raise ValueError(f"未知的 ClickHouse 类型 {t}")
    table = _DAX_COARSE if stack == "dax" else _CUBE_COARSE
    if t not in table:
        raise ValueError(f"{stack} 下未知的类型 {t}")
    return table[t]


def neutral_name(stack: str, s: str) -> str:
    """Physical names → `<Table>` / `<Table>.Column` in every stack."""
    s = _TABLE_RE.sub(lambda m: _TABLE_TOKENS[m.group(1)], s)
    if stack == "sql":
        s = re.sub(r"(?<![A-Za-z0-9_])(?:retail|l0)\.(?=[<A-Za-z_])", "", s)
    if stack == "dax":
        s = re.sub(r"(<\w+>|[A-Za-z_]\w*)\[([^\]]+)\]", r"\1.\2", s)
    return s


def normalise(obj, stack: str, calls: list | None = None, key: str | None = None):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "type" and isinstance(v, str):
                out[k] = coarse_type(stack, v)
            elif k == "callables":
                if calls is not None:
                    calls.append(v)
                out[k] = [{"dataset": normalise(c["dataset"], stack), "call": "<CALL>"} for c in v]
            else:
                out[k] = normalise(v, stack, calls, k)
        return out
    if isinstance(obj, list):
        return [normalise(x, stack, calls, key) for x in obj]
    if isinstance(obj, str):
        return neutral_name(stack, obj)
    return obj


def diff(a, b, path: str = "") -> list[str]:
    if type(a) is not type(b):
        return [f"{path}: 类型不同 {type(a).__name__} vs {type(b).__name__}"]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}.{k}: 只在{'右' if k not in a else '左'}边出现")
            else:
                out += diff(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path}: 长度 {len(a)} vs {len(b)}"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [f"{path}: {str(a)[:80]!r} ≠ {str(b)[:80]!r}"]


def strip_callables(obj):
    if isinstance(obj, dict):
        return {k: strip_callables(v) for k, v in obj.items() if k != "callables"}
    if isinstance(obj, list):
        return [strip_callables(x) for x in obj]
    return obj


def expected_calls(stack: str) -> dict[tuple, str]:
    """(metric, `<Table>`) → the call as this stack must write it, built from metrics.yaml."""
    out = {}
    for m in metrics_file()["metrics"]:
        pairs = [(m["dataset"], m["dax_measure"], m["cube_member"])]
        if m.get("alternate_dataset"):
            pairs.append((m["alternate_dataset"], m["alternate_dax_measure"], m["alternate_cube_member"]))
        for ds, dax, cube in pairs:
            call = {"dax": dax, "cube_sql": f"MEASURE({cube})", "cube_json": cube}[stack]
            out[(m["name"], f"<{ds}>")] = call
        for _, ds, dax, cube, scope in variant_callables(m):       # variants: keyed by their scope too
            call = {"dax": dax, "cube_sql": f"MEASURE({cube})", "cube_json": cube}[stack]
            out[(m["name"], f"<{ds}>", scope)] = call
    return out


def check_calls(cell: str, ctx: dict) -> list[str]:
    stack = STACK_OF[cell]
    want = expected_calls(stack)
    problems, seen = [], set()
    for m in ctx.get("metrics", []):
        for c in m.get("callables", []):
            key = (m["name"], neutral_name(stack, c["dataset"]), *([c["scope"]] if c.get("scope") else []))
            seen.add(key)
            if want.get(key) != c["call"]:
                problems.append(f"{cell} 的「{m['name']}」@{c['dataset']} 写成 {c['call']!r}，应为 {want.get(key)!r}")
    missing = set(want) - seen
    problems += [f"{cell} 缺少调用名：{k}" for k in sorted(missing)]
    return problems


def load(cell: str) -> dict:
    path = CTX / f"{cell}.yaml"
    if not path.exists():
        raise SystemExit(f"缺少 {path}；先运行 uv run python render/context.py")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def run(load=load) -> list[str]:
    """All checks; `load(cell)` returns a context (defaults to reading build/contexts/)."""
    problems: list[str] = []
    norm = {cell: normalise(load(cell), STACK_OF[cell]) for cell in STACK_OF}
    for left, right, label in PAIRS:
        d = diff(norm[left], norm[right])
        status = "一致" if not d else f"{len(d)} 处不同"
        print(f"{label}：{status}")
        problems += [f"{label} {x}" for x in d]
    for l1, l2 in L1_VS_L2:
        d = diff(norm[l1], strip_callables(norm[l2]))
        print(f"{l2} 去掉调用名 = {l1}：{'一致' if not d else f'{len(d)} 处不同'}")
        problems += [f"{l2} vs {l1} {x}" for x in d]
    for cell in ("SQL-L2", "JSON-L2", "DAX-L2"):
        p = check_calls(cell, load(cell))
        print(f"{cell} 的调用名：{'全部正确' if not p else f'{len(p)} 处错误'}")
        problems += p
    # Cube renames every table; a leftover original name would normalise to the same
    # placeholder and slip through the comparison above, so look for it directly.
    leftover = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(CUBE_NAMES) + r")(?![A-Za-z0-9_])")
    for cell in ("SQL-L2", "JSON-L2"):
        found = sorted(set(leftover.findall(yaml.safe_dump(load(cell), allow_unicode=True))))
        print(f"{cell} 里残留的原表名：{'无' if not found else found}")
        if found:
            problems.append(f"{cell} 仍出现原表名 {found}（Cube 单元应全部换成 cube 名）")
    for cell in ("SQL-L0", "SQL-L1", "DAX-L0", "DAX-L1"):
        if "callables" in yaml.safe_dump(load(cell)):
            problems.append(f"{cell} 出现了调用名（只有 L2 才有）")
    return problems


def main() -> None:
    problems = run()
    if problems:
        print("\n等价校验未通过：")
        for p in problems[:80]:
            print(f"  - {p}")
        sys.exit(1)
    print("等价校验通过。")


if __name__ == "__main__":
    main()
