"""Shared pieces for the renderers: loading the sources and per-stack physical names.

Every self-built cell reads the same context structure; stacks differ only in
(a) how a table / column / type is written and (b) how a metric is called.
Both live here so ``context.py``, ``cube.py``, ``tmdl.py`` and
``check_equivalence.py`` agree on them.

Stacks:
    sql        ClickHouse SQL on chDB (databases retail / dwd / ads / l0)
    dax        DAX on the Power BI model (table names = ClickHouse table names)
    cube_sql   Cube SQL API (Postgres dialect, MEASURE())
    cube_json  Cube REST /load (JSON query)
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SEMANTIC = REPO / "semantic"
BUILD = REPO / "build"
SCHEMA_SNAPSHOT = REPO / "render" / "physical_schema.json"

STACKS = ("sql", "dax", "cube_sql", "cube_json")

# Cube names. The eight that carry metrics are fixed by semantic/metrics.yaml
# (naming.cubes); the rest follow the same rule: snake_case, no Fact/Dim prefix.
# DimDate is `calendar`, not `date`, because DATE is a keyword in Postgres.
CUBE_NAMES: dict[str, str] = {
    "FactOnlineSales": "online_sales",
    "FactSales": "sales",
    "FactInventory": "inventory",
    "FactSalesQuota": "sales_quota",
    "FactStrategyPlan": "strategy_plan",
    "FactExchangeRate": "exchange_rate",
    "FactITMachine": "it_machine",
    "FactITSLA": "it_sla",
    "DimProduct": "product",
    "DimStore": "store",
    "DimCustomer": "customer",
    "DimDate": "calendar",
    "DimGeography": "geography",
    "DimChannel": "channel",
    "DimPromotion": "promotion",
    "DimScenario": "scenario",
    "DimAccount": "account",
    "DimCurrency": "currency",
    "DimProductCategory": "product_category",
    "DimProductSubcategory": "product_subcategory",
    "DimEmployee": "employee",
    "DimEntity": "entity",
    "DimSalesTerritory": "sales_territory",
    "DimMachine": "machine",
    "DimOutage": "outage",
}


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@cache
def source() -> dict:
    return _yaml(SEMANTIC / "source.yaml")


@cache
def metrics_file() -> dict:
    return _yaml(SEMANTIC / "metrics.yaml")


@cache
def l0_map() -> dict:
    return _yaml(SEMANTIC / "l0_map.yaml")


@cache
def summary() -> dict:
    return _yaml(SEMANTIC / "summary" / "summary.yaml")


@cache
def physical_schema() -> dict[str, dict[str, list[tuple[str, str]]]]:
    raw = json.loads(SCHEMA_SNAPSHOT.read_text(encoding="utf-8"))
    return {db: {t: [tuple(c) for c in cols] for t, cols in tabs.items()} for db, tabs in raw.items()}


def column_types(db: str, table: str) -> dict[str, str]:
    return dict(physical_schema()[db][table])


def tuning_file(cell: str) -> Path:
    return SEMANTIC / "tuning" / f"{cell}.yaml"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------
def logical_type(ch_type: str) -> str:
    """ClickHouse type → stack-neutral category (used by the equivalence check)."""
    t = ch_type
    for wrapper in ("Nullable(", "LowCardinality("):
        while t.startswith(wrapper):
            t = t[len(wrapper):-1]
    if t.startswith(("Int", "UInt")):
        return "integer"
    if t.startswith(("Float", "Decimal")):
        return "decimal"
    if t.startswith("DateTime"):
        return "datetime"
    if t == "Date" or t.startswith("Date32"):
        return "date"
    if t == "String" or t.startswith("FixedString"):
        return "string"
    if t == "Bool":
        return "boolean"
    raise ValueError(f"unmapped ClickHouse type {ch_type}")


DAX_TYPES = {"integer": "int64", "decimal": "double", "datetime": "dateTime", "date": "dateTime",
             "string": "string", "boolean": "boolean"}
CUBE_TYPES = {"integer": "number", "decimal": "number", "datetime": "time", "date": "time",
              "string": "string", "boolean": "boolean"}


# ---------------------------------------------------------------------------
# Physical names per stack
# ---------------------------------------------------------------------------
_TABLE_WORD = re.compile(r"\b(" + "|".join(sorted(CUBE_NAMES, key=len, reverse=True)) + r")\b")


class Namer:
    """How one stack writes physical names, types and metric calls."""

    def __init__(self, stack: str):
        if stack not in STACKS:
            raise ValueError(stack)
        self.stack = stack

    @property
    def is_cube(self) -> bool:
        return self.stack in ("cube_sql", "cube_json")

    def table(self, name: str, db: str = "retail") -> str:
        if self.stack == "sql":
            return f"{db}.{name}"
        if self.is_cube:
            if db != "retail":
                raise ValueError(f"Cube 只承载 retail 的表，没有 {db}.{name}")
            return CUBE_NAMES[name]
        return name  # dax: Power BI table name = ClickHouse table name

    def column(self, table: str, col: str, db: str = "retail") -> str:
        t = self.table(table, db)
        return f"{t}[{col}]" if self.stack == "dax" else f"{t}.{col}"

    def ref(self, dotted: str, db: str = "retail") -> str:
        """`Table.Column` or `Table` as written in source.yaml → this stack."""
        if "." in dotted:
            table, col = dotted.split(".", 1)
            return self.column(table, col, db)
        return self.table(dotted, db)

    def type(self, ch_type: str) -> str:
        if self.stack == "sql":
            return ch_type
        lt = logical_type(ch_type)
        return DAX_TYPES[lt] if self.stack == "dax" else CUBE_TYPES[lt]

    def text(self, s: str) -> str:
        """Free text that mentions tables: only Cube renames tables, so only Cube rewrites."""
        if not self.is_cube:
            return s
        return _TABLE_WORD.sub(lambda m: CUBE_NAMES[m.group(1)], s)

    def call(self, dax_measure: str, cube_member: str) -> str:
        if self.stack == "dax":
            return dax_measure
        if self.stack == "cube_sql":
            return f"MEASURE({cube_member})"
        if self.stack == "cube_json":
            return cube_member
        raise ValueError("ClickHouse SQL 没有可调用的指标（L2 的 SQL 走 Cube 的 SQL 接口）")


def metric_callables(m: dict) -> list[tuple[str, str, str]]:
    """(dataset, dax_measure, cube_member) for every callable of one metrics.yaml entry."""
    out = [(m["dataset"], m["dax_measure"], m["cube_member"])]
    if m.get("alternate_dataset"):
        out.append((m["alternate_dataset"], m["alternate_dax_measure"], m["alternate_cube_member"]))
    return out


def variant_key(metric: str, variant_id: str) -> str:
    """Key of a variant callable in the (metric, dataset) maps: ``<指标>｜<变体>``."""
    return f"{metric}｜{variant_id}"


def variant_callables(m: dict) -> list[tuple[str, str, str, str, str]]:
    """(variant id, dataset, dax_measure, cube_member, scope) for each variant the L1 text states
    (metrics.yaml ``variants``: share scopes, period lengths, scenario; semantic-v1.4)."""
    return [(v["id"], v["dataset"], v["dax_measure"], v["cube_member"], v["scope"]) for v in m.get("variants") or []]


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper: yaml.SafeDumper, value: str):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str)


def dump_yaml(obj) -> str:
    return yaml.dump(obj, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=100, default_flow_style=False)
