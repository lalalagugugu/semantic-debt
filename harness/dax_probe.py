"""DAX probe (T17): check the Power BI model open in Desktop without calling any model.

Three subcommands:

    uv run python harness/dax_probe.py expected        # Mac: the reference numbers, from chDB
    uv run python harness/dax_probe.py prepare         # Windows: verify the bundle, make the working PBIPs
    uv run python harness/dax_probe.py probe --tier L1 # Windows: connect, run every check, plain-text report

``expected`` computes, with chDB reading ``$SEMDEBT_DATA_DIR/parquet/*.parquet`` directly (the very
files Power BI imports; no chDB data directory is opened, so it cannot collide with another run,
hard rule 9), the numbers each check must reproduce, and writes
``reports/validation/dax_probe_expected.json`` (committed). The DAX of each check is written per
tier with that model's names (L0 names at L0).

Checks (relative difference at most 0.5 %, task card T17 §做法 2):

- ``rows``      every table's row count (all tiers);
- ``sums``      sums and distinct counts of the main fact columns (all tiers);
- ``orphans``   the five relationships with orphan rows (source.yaml ``orphan_rows``): rows whose key
                is not in the one-side table, by value, and, where the model has the relationship,
                the rows that fall into the relationship's blank member. Listed apart in the report.
                The model keeps them as they are (no unknown member, no data fix) so that the DAX
                and SQL lines stay comparable;
- ``measures``  L2: measures against the totals source.yaml records and the Cube cross-checks
                (render/verify_cube.py), mapped to the DAX measure names;
- ``variants``  L2: the ten semantic-v1.4 variant measures, each on one slice (deferred from v1.4:
                "DAX 变体须经 T17 实测");
- ``syntax``    L1: the depth-2 claims of render/syntax/dax.md that were written without a real
                engine (reports/validation/dax-syntax-t2.md), each as a query whose outcome the
                claim predicts.

The probe also reports what Desktop actually loaded: model identity (tables, columns, measures),
Desktop's own auto date tables, descriptions and synonyms (T10 handoff 二), relationship
activity, and at L2 whether each measure expression is the one the renderer wrote.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO = Path(__file__).resolve().parent.parent
EXPECTED_JSON = REPO / "reports" / "validation" / "dax_probe_expected.json"
TOLERANCE = 0.005
TIERS = ("L0", "L1", "L2")

SUMS = [  # (table, column, aggregate)
    ("FactSales", "SalesAmount", "sum"), ("FactSales", "SalesQuantity", "sum"), ("FactSales", "TotalCost", "sum"),
    ("FactSales", "ReturnAmount", "sum"), ("FactSales", "DiscountAmount", "sum"), ("FactSales", "StoreKey", "distinct"),
    ("FactOnlineSales", "SalesAmount", "sum"), ("FactOnlineSales", "SalesQuantity", "sum"),
    ("FactOnlineSales", "TotalCost", "sum"), ("FactOnlineSales", "ReturnAmount", "sum"),
    ("FactOnlineSales", "SalesOrderNumber", "distinct"), ("FactOnlineSales", "CustomerKey", "distinct"),
    ("FactInventory", "OnHandQuantity", "sum"), ("FactInventory", "OnOrderQuantity", "sum"),
    ("FactSalesQuota", "SalesAmountQuota", "sum"), ("FactSalesQuota", "SalesQuantityQuota", "sum"),
    ("FactStrategyPlan", "Amount", "sum"), ("FactITMachine", "CostAmount", "sum"), ("FactITSLA", "DownTime", "sum"),
    ("FactExchangeRate", "AverageRate", "sum"),
]


# ---------------------------------------------------------------------------
# Names per tier


class Names:
    """How one tier's model names a table / column, quoted for DAX."""

    def __init__(self, tier: str):
        from render.tmdl import Project, q

        self.tier, self._p, self._q = tier, Project(tier), q

    def t(self, table: str) -> str:
        return "'" + self._p.tname(table).replace("'", "''") + "'"

    def c(self, table: str, column: str) -> str:
        return f"{self.t(table)}[{self._p.cname(table, column)}]"

    def relationships(self) -> dict[tuple[str, str], bool]:
        return {(f, t): active for f, t, active in self._p.relationships()}


# ---------------------------------------------------------------------------
# chDB over the Parquet files (Mac)


def parquet_dir() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        raise SystemExit("SEMDEBT_DATA_DIR is not set")
    return Path(root).expanduser() / "parquet"


def on_parquet(sql: str, pq: Path) -> str:
    """``retail.T`` → the Parquet file Power BI imports for T."""
    return re.sub(r"\bretail\.(\w+)", lambda m: f"file('{pq}/{m.group(1)}.parquet', Parquet)", sql)


def make_scalar(pq: Path):
    import chdb

    def scalar(sql: str) -> float:
        out = chdb.query(on_parquet(sql, pq), "TSV").bytes().decode().strip()
        if out in ("", "\\N", "nan"):
            return float("nan")
        return float(out)

    return scalar


def _row(expr: str) -> str:
    return f'EVALUATE ROW ( "v", {expr} )'


# ---------------------------------------------------------------------------
# The checks


def data_checks(scalar) -> list[dict]:
    from render.common import source

    names = {tier: Names(tier) for tier in TIERS}
    out: list[dict] = []

    def add(cid: str, group: str, title: str, dax: dict[str, str], sql: str | None, expected: float | None = None,
            origin: str = "chDB / Parquet") -> None:
        value = scalar(sql) if sql is not None else expected
        out.append({"id": cid, "group": group, "title": title, "dax": dax, "sql": sql, "expected": value,
                    "origin": origin})

    for ds in source()["datasets"]:
        t = ds["name"]
        add(f"rows.{t}", "rows", f"{t} 行数", {tier: _row(f"COUNTROWS ( {n.t(t)} )") for tier, n in names.items()},
            f"SELECT count() FROM retail.{t}")

    for t, c, agg in SUMS:
        dax_fn = "SUM" if agg == "sum" else "DISTINCTCOUNT"
        sql_fn = f"sum({c})" if agg == "sum" else f"uniqExact({c})"
        add(f"sums.{t}.{c}.{agg}", "sums", f"{t}.{c} {'合计' if agg == 'sum' else '去重计数'}",
            {tier: _row(f"{dax_fn} ( {n.c(t, c)} )") for tier, n in names.items()}, f"SELECT {sql_fn} FROM retail.{t}")

    for r in source()["relationships"]:
        if not r.get("orphan_rows"):
            continue
        (ft, fc), (tt, tc) = r["from"].split("."), r["to"].split(".")
        label = f"{r['from']} → {r['to']}"
        by_value = {}
        for tier, n in names.items():
            fk, pk = n.c(ft, fc), n.c(tt, tc)
            by_value[tier] = _row(f"SUMX ( FILTER ( ALL ( {fk} ), NOT ISBLANK ( {fk} ) && NOT ( {fk} IN ALLNOBLANKROW ( {pk} ) ) ), "
                                  f"CALCULATE ( COUNTROWS ( {n.t(ft)} ) ) ) + 0")
        sql_orphan = (f"SELECT countIf({fc} IS NOT NULL AND {fc} NOT IN (SELECT {tc} FROM retail.{tt} WHERE {tc} IS NOT NULL)) "
                      f"FROM retail.{ft}")
        got = scalar(sql_orphan)
        if got != r["orphan_rows"]:
            raise SystemExit(f"{label}: Parquet gives {got} orphan rows, source.yaml says {r['orphan_rows']}")
        add(f"orphans.{r['from']}.by_value", "orphans", f"{label} 孤儿行（按值）", by_value, sql_orphan)
        blank = {}
        for tier, n in names.items():
            active = n.relationships().get((r["from"], r["to"]))
            if active:                       # inactive ones would need USERELATIONSHIP; none of the five is
                blank[tier] = _row(f"CALCULATE ( COUNTROWS ( {n.t(ft)} ), ISBLANK ( {n.c(tt, tc)} ) ) + 0")
        if blank:
            add(f"orphans.{r['from']}.blank_member", "orphans", f"{label} 落进空白成员的行（键为空或找不到）", blank,
                f"SELECT countIf({fc} IS NULL OR {fc} NOT IN (SELECT {tc} FROM retail.{tt} WHERE {tc} IS NOT NULL)) "
                f"FROM retail.{ft}")
    return out


def _dax_by_cube_member() -> dict[str, str]:
    from render.common import metric_callables, metrics_file, variant_callables

    out = {}
    for m in metrics_file()["metrics"]:
        for _, dax, cube in metric_callables(m):
            out[cube] = dax
        for _, _, dax, cube, _ in variant_callables(m):
            out[cube] = dax
    return out


def measure_checks(scalar) -> list[dict]:
    from render import verify_cube as V

    dax = _dax_by_cube_member()
    filters = {"": None, V._Y2009: "'DimDate'[CalendarYear] = 2009",
               V._WORKDAY_2009: "'DimDate'[CalendarYear] = 2009, 'DimDate'[IsWorkDay] = \"WorkDay\""}
    out = []
    for member, where, expected, _tol, origin in V.EXPECTED:
        f = filters[where]
        expr = f"CALCULATE ( {dax[member]}, {f} )" if f else dax[member]
        out.append({"id": f"measures.{member}", "group": "measures",
                    "title": f"{dax[member]}{'（' + ('2009' if where == V._Y2009 else '2009 平日') + '）' if f else ''}",
                    "dax": {"L2": _row(expr)}, "sql": None, "expected": expected, "origin": f"source.yaml {origin}"})
    for member, direct in V.CROSS_CHECKS:
        out.append({"id": f"measures.{member}", "group": "measures", "title": dax[member],
                    "dax": {"L2": _row(dax[member])}, "sql": direct, "expected": scalar(direct),
                    "origin": "chDB / Parquet（render/verify_cube.py 的直接查询）"})
    return out


def variant_checks(scalar) -> list[dict]:
    """One slice per variant measure, with the reading metrics.yaml's ``scope`` states."""
    from render.common import metrics_file, variant_callables

    store = int(scalar("SELECT min(StoreKey) FROM retail.FactSales"))
    subcat = int(scalar("SELECT min(toInt64(ProductSubcategoryKey)) FROM retail.DimProduct "
                        "WHERE ProductKey IN (SELECT DISTINCT ProductKey FROM retail.FactSales)"))
    in_subcat = (f"ProductKey IN (SELECT ProductKey FROM retail.DimProduct WHERE toInt64(ProductSubcategoryKey) = {subcat})")
    in_cat = ("ProductKey IN (SELECT ProductKey FROM retail.DimProduct WHERE toInt64(ProductSubcategoryKey) IN "
              "(SELECT ProductSubcategoryKey FROM retail.DimProductSubcategory WHERE ProductCategoryKey = "
              f"(SELECT ProductCategoryKey FROM retail.DimProductSubcategory WHERE ProductSubcategoryKey = {subcat})))")
    out = []
    for m in metrics_file()["metrics"]:
        for vid, ds, dax, _cube, scope in variant_callables(m):
            key = (m["name"], vid)
            if key == ("销售额占比", "渠道内"):
                expr = f"CALCULATE ( {dax}, 'DimStore'[StoreKey] = {store} )"
                sql = (f"SELECT (SELECT sum(SalesAmount) FROM retail.{ds} WHERE StoreKey = {store}) / "
                       f"(SELECT sum(SalesAmount) FROM retail.{ds} WHERE channelKey = "
                       f"(SELECT any(channelKey) FROM retail.{ds} WHERE StoreKey = {store}))")
                where = f"门店 {store}"
            elif key == ("销售额占比", "品类内"):
                expr = f"CALCULATE ( {dax}, 'DimProductSubcategory'[ProductSubcategoryKey] = {subcat} )"
                sql = (f"SELECT (SELECT sum(SalesAmount) FROM retail.{ds} WHERE {in_subcat}) / "
                       f"(SELECT sum(SalesAmount) FROM retail.{ds} WHERE {in_cat})")
                where = f"子类 {subcat}"
            elif key == ("销售额环比增长率", "按季"):
                expr = f"CALCULATE ( {dax}, DATESBETWEEN ( 'DimDate'[DateKey], DATE ( 2009, 4, 1 ), DATE ( 2009, 6, 30 ) ) )"
                sql = (f"SELECT sumIf(SalesAmount, toStartOfQuarter(DateKey) = '2009-04-01') / "
                       f"sumIf(SalesAmount, toStartOfQuarter(DateKey) = '2009-01-01') - 1 FROM retail.{ds}")
                where = "2009 年第 2 季"
            elif key == ("同店销售额", "作基年"):
                expr = f"CALCULATE ( {dax}, 'DimDate'[CalendarYear] = 2008 )"
                sql = (f"SELECT sum(SalesAmount) FROM retail.{ds} WHERE toYear(DateKey) = 2008 AND StoreKey IN "
                       f"(SELECT DISTINCT StoreKey FROM retail.{ds} WHERE toYear(DateKey) = 2009)")
                where = "2008 年"
            elif vid == "按查询场景" and ds == "FactSalesQuota":
                col = {"目标销售额": "SalesAmountQuota", "目标销量": "SalesQuantityQuota", "目标毛利": "GrossMarginQuota"}[m["name"]]
                expr = f"CALCULATE ( {dax}, 'DimScenario'[ScenarioName] = \"Actual\" )"
                sql = (f"SELECT sum({col}) FROM retail.{ds} WHERE ScenarioKey = "
                       "(SELECT ScenarioKey FROM retail.DimScenario WHERE ScenarioName = 'Actual')")
                where = "场景 Actual"
            elif key == ("计划收入", "按查询场景"):
                expr = f"CALCULATE ( {dax}, 'DimScenario'[ScenarioName] = \"Actual\" )"
                sql = ("SELECT sum(Amount) FROM retail.FactStrategyPlan WHERE ScenarioKey = "
                       "(SELECT ScenarioKey FROM retail.DimScenario WHERE ScenarioName = 'Actual') AND AccountKey IN "
                       "(SELECT AccountKey FROM retail.DimAccount WHERE AccountName = 'Sale Revenue')")
                where = "场景 Actual"
            else:
                raise SystemExit(f"no probe slice for the variant {key} — add one before the DAX runs")
            out.append({"id": f"variants.{m['name']}.{vid}.{ds}", "group": "variants",
                        "title": f"{dax}（{m['name']}·{vid}，{where}）", "scope": scope,
                        "dax": {"L2": _row(expr)}, "sql": sql, "expected": scalar(sql), "origin": "chDB / Parquet"})
    return out


def build_expected() -> dict:
    pq = parquet_dir()
    scalar = make_scalar(pq)
    checks = data_checks(scalar) + measure_checks(scalar) + variant_checks(scalar)
    return {"tolerance": TOLERANCE, "parquet": {p.name: sha256_file(p) for p in sorted(pq.glob("*.parquet"))},
            "checks": checks}


# Depth-2 claims of render/syntax/dax.md, checked on the L1 model (the engine behaviour does not
# depend on the tier). ``expect``: "error", "ok", or ("rows", n) / ("rows>", n) / ("all_equal", col) /
# ("not_all_equal", col) / ("value", x) / ("inf", None) / ("blank_group", col) / ("a=b+1", None).
SYNTAX = [
    ("S01", "EVALUATE 后单个数值要包成 ROW", "EVALUATE 1", "error"),
    ("S01b", "同上（正例）", 'EVALUATE ROW ( "v", 1 )', "ok"),
    ("S02", "DEFINE MEASURE 要写明表", 'DEFINE MEASURE [x] = 1 EVALUATE ROW ( "v", [x] )', "error"),
    ("S02b", "同上（正例）", "DEFINE MEASURE 'FactSales'[x] = 1 EVALUATE ROW ( \"v\", [x] )", "ok"),
    ("S02c", "DEFINE VAR 可在 EVALUATE 里用", 'DEFINE VAR _t = { 1, 2 } EVALUATE _t', ("rows", 2)),
    ("S03", "ADDCOLUMNS 新列与已有列同名报错",
     "EVALUATE ADDCOLUMNS ( VALUES ( 'DimChannel'[ChannelName] ), \"ChannelName\", 1 )", "error"),
    ("S03b", "结果列名可以用中文", "EVALUATE ADDCOLUMNS ( VALUES ( 'DimChannel'[ChannelName] ), \"合计\", 1 )", "ok"),
    ("S04", "ORDER BY 只能排结果里有的列",
     "EVALUATE VALUES ( 'DimChannel'[ChannelName] ) ORDER BY 'DimChannel'[ChannelKey]", "error"),
    ("S04b", "ORDER BY 新算的列写 [结果列名]",
     "EVALUATE ADDCOLUMNS ( VALUES ( 'DimChannel'[ChannelName] ), \"n\", 1 ) ORDER BY [n] DESC", "ok"),
    ("S05", "TOPN 遇并列返回多于 N 行", "EVALUATE TOPN ( 1, VALUES ( 'DimChannel'[ChannelName] ), 1, DESC )", ("rows>", 1)),
    ("S06", "SUMMARIZECOLUMNS 去掉结果全为空的组合",
     "EVALUATE SUMMARIZECOLUMNS ( 'DimChannel'[ChannelName], \"v\", BLANK () )", ("rows", 0)),
    ("S07", "没有激活关系时每组同一个合计、不报错",
     "EVALUATE SUMMARIZECOLUMNS ( 'DimGeography'[ContinentName], \"v\", SUM ( 'FactSales'[SalesAmount] ) )",
     ("all_equal", 1)),
    ("S07b", "加 USERELATIONSHIP 后按组分开",
     "EVALUATE SUMMARIZECOLUMNS ( 'DimGeography'[ContinentName], \"v\", CALCULATE ( SUM ( 'FactSales'[SalesAmount] ), "
     "USERELATIONSHIP ( 'DimStore'[GeographyKey], 'DimGeography'[GeographyKey] ) ) )", ("not_all_equal", 1)),
    ("S08", "SUMMARIZECOLUMNS 放进逐行函数内部（说明里写「不要」；这里记录引擎实际行为）",
     "EVALUATE ADDCOLUMNS ( VALUES ( 'DimChannel'[ChannelName] ), \"n\", COUNTROWS ( SUMMARIZECOLUMNS ( "
     "'DimDate'[CalendarYear], \"v\", SUM ( 'FactSales'[SalesAmount] ) ) ) )", "error"),
    ("S09", "孤儿行归入空白组",
     "EVALUATE SUMMARIZECOLUMNS ( 'DimProduct'[BrandName], \"v\", SUM ( 'FactSales'[SalesAmount] ) )", ("blank_group", 0)),
    ("S10", "RELATED 只能在逐行计算的地方用", "EVALUATE ROW ( \"v\", RELATED ( 'DimChannel'[ChannelName] ) )", "error"),
    ("S11", "自连接用 LOOKUPVALUE 按键取值",
     "EVALUATE ROW ( \"v\", LOOKUPVALUE ( 'DimEmployee'[FirstName], 'DimEmployee'[EmployeeKey], 1 ) )", "ok"),
    ("S12", "CALCULATE 简写条件不能比较两张表的列",
     "EVALUATE ROW ( \"v\", CALCULATE ( SUM ( 'FactSales'[SalesAmount] ), 'FactSales'[StoreKey] = 'DimStore'[StoreKey] ) )",
     "error"),
    ("S12b", "CALCULATE 简写条件里用度量值（说明里写「改用 FILTER」；这里记录引擎实际行为）",
     "DEFINE MEASURE 'FactSales'[m] = 1 EVALUATE ROW ( \"v\", CALCULATE ( SUM ( 'FactSales'[SalesAmount] ), "
     "'FactSales'[SalesQuantity] > [m] ) )", "error"),
    ("S13", "字符串 = 不区分大小写", 'EVALUATE ROW ( "v", "abc" = "ABC" )', ("value", True)),
    ("S13b", "BLANK() = 0 为真", 'EVALUATE ROW ( "v", BLANK () = 0 )', ("value", True)),
    ("S13c", "BLANK() == 0 为假", 'EVALUATE ROW ( "v", BLANK () == 0 )', ("value", False)),
    ("S14", "/ 分母为零不报错、返回无穷大", 'EVALUATE ROW ( "v", 1 / 0 )', ("inf", None)),
    ("S15", "日期列不能和字符串比较",
     "EVALUATE FILTER ( VALUES ( 'DimDate'[DateKey] ), 'DimDate'[DateKey] >= \"2008-01-01\" )", "error"),
    ("S15b", "同上（正例：DATE）",
     "EVALUATE FILTER ( VALUES ( 'DimDate'[DateKey] ), 'DimDate'[DateKey] >= DATE ( 2008, 1, 1 ) )", ("rows>", 0)),
    ("S16", "RANKX 第一个参数写 VALUES 时每组都排第 1",
     "EVALUATE SUMMARIZECOLUMNS ( 'DimChannel'[ChannelName], \"r\", RANKX ( VALUES ( 'DimChannel'[ChannelName] ), "
     "CALCULATE ( SUM ( 'FactSales'[SalesAmount] ) ) ) )", ("all_equal", 1)),
    ("S16b", "RANKX 写 ALL 时正常排名",
     "EVALUATE SUMMARIZECOLUMNS ( 'DimChannel'[ChannelName], \"r\", RANKX ( ALL ( 'DimChannel'[ChannelName] ), "
     "CALCULATE ( SUM ( 'FactSales'[SalesAmount] ) ) ) )", ("not_all_equal", 1)),
    ("S17", "DISTINCTCOUNT 把空值算作一个值",
     "EVALUATE ROW ( \"a\", DISTINCTCOUNT ( 'FactInventory'[Aging] ), \"b\", DISTINCTCOUNTNOBLANK ( 'FactInventory'[Aging] ) )",
     ("a=b+1", None)),
    ("S18", "QUOTIENT 整数除法", 'EVALUATE ROW ( "v", QUOTIENT ( 7, 2 ) )', ("value", 3)),
]


def judge_syntax(expect, result) -> tuple[bool, str]:
    if expect == "error":
        return (not result.ok), ("报错" if not result.ok else "没有报错")
    if not result.ok:
        return False, f"报错：{(result.error or '')[:160]}"
    rows = result.rows or []
    if expect == "ok":
        return True, f"{len(rows)} 行"
    kind, arg = expect
    if kind == "rows":
        return len(rows) == arg, f"{len(rows)} 行"
    if kind == "rows>":
        return len(rows) > arg, f"{len(rows)} 行"
    if kind in ("all_equal", "not_all_equal"):
        values = {repr(r[arg]) for r in rows}
        same = len(values) == 1 and len(rows) > 1
        return (same if kind == "all_equal" else len(values) > 1), f"{len(rows)} 行，第 {arg + 1} 列 {len(values)} 种值"
    if kind == "value":
        got = rows[0][0] if rows else None
        return got == arg, f"值 {got!r}"
    if kind == "inf":
        got = rows[0][0] if rows else None
        return isinstance(got, float) and math.isinf(got), f"值 {got!r}"
    if kind == "blank_group":
        return any(r[arg] in (None, "") for r in rows), f"{len(rows)} 行，含空白组：{any(r[arg] in (None, '') for r in rows)}"
    if kind == "a=b+1":
        a, b = rows[0][0], rows[0][1]
        return a == b + 1, f"a={a} b={b}"
    raise ValueError(expect)


# ---------------------------------------------------------------------------
# Bundle (Windows side)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def data_root() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        raise SystemExit("SEMDEBT_DATA_DIR is not set")
    return Path(root).expanduser()


def bundle_dir() -> Path:
    return Path(os.environ.get("SEMDEBT_T17_BUNDLE") or data_root() / "t17-bundle")


def work_dir() -> Path:
    return data_root() / "t17-pbip-work"


_DATADIR_LINE = re.compile(r'^(expression DataDir = )"(?:[^"]|"")*"', re.MULTILINE)
_PART_SEP = re.compile(r'DataDir & "[\\/]')


def normalise_pbip_text(text: str) -> str:
    """The two things that depend on where the model is rendered: the DataDir value and the separator."""
    return _PART_SEP.sub('DataDir & "/', _DATADIR_LINE.sub(r'\1"<DataDir>"', text))


def verify_manifest(root: Path) -> list[str]:
    problems = []
    manifest = root / "MANIFEST.sha256"
    if not manifest.exists():
        return [f"{manifest} 不存在"]
    listed = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        listed.add(rel)
        path = root / Path(rel)
        if not path.exists():
            problems.append(f"缺少 {rel}")
        elif sha256_file(path) != digest:
            problems.append(f"哈希不符 {rel}")
    extra = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} - listed - {"MANIFEST.sha256", "BUNDLE.txt"}
    problems += [f"清单外的文件 {x}" for x in sorted(extra)]
    return problems


def compare_with_render(bundle_pbip: Path, rendered: Path) -> list[str]:
    """The bundle's PBIP must be what this checkout renders (up to DataDir and the path separator)."""
    a = {p.relative_to(bundle_pbip).as_posix(): p for p in bundle_pbip.rglob("*") if p.is_file()}
    b = {p.relative_to(rendered).as_posix(): p for p in rendered.rglob("*") if p.is_file()}
    problems = [f"只在压缩包里：{x}" for x in sorted(set(a) - set(b))] + [f"只在本机渲染里：{x}" for x in sorted(set(b) - set(a))]
    for rel in sorted(set(a) & set(b)):
        if normalise_pbip_text(a[rel].read_text(encoding="utf-8")) != normalise_pbip_text(b[rel].read_text(encoding="utf-8")):
            problems.append(f"内容不同：{rel}")
    return problems


def prepare(rendered: Path | None = None) -> int:
    root = bundle_dir()
    print(f"压缩包目录：{root}")
    problems = verify_manifest(root)
    if problems:
        print("清单校验不通过：\n  " + "\n  ".join(problems))
        return 1
    print("清单校验通过（parquet/、pbip/ 的哈希全部一致）")
    rendered = rendered or REPO / "build" / "pbip"
    problems = compare_with_render(root / "pbip", rendered)
    if problems:
        print("压缩包里的 PBIP 与本机仓库渲染出的不一致（仓库版本不对？先 render_all）：\n  " + "\n  ".join(problems[:20]))
        return 1
    print("压缩包里的 PBIP 与本机仓库渲染出的一致")
    parquet = (root / "parquet").resolve()
    for tier in TIERS:
        dst = work_dir() / f"retail-{tier}"
        if dst.exists():
            print(f"已存在，不覆盖：{dst}（要重建就先删掉它）")
            continue
        shutil.copytree(root / "pbip" / f"retail-{tier}", dst)
        expr = dst / f"retail-{tier}.SemanticModel" / "definition" / "expressions.tmdl"
        value = str(parquet).replace('"', '""')
        expr.write_text(_DATADIR_LINE.sub(lambda m: f'{m.group(1)}"{value}"', expr.read_text(encoding="utf-8")),
                        encoding="utf-8")
        for t in (dst / f"retail-{tier}.SemanticModel" / "definition" / "tables").glob("*.tmdl"):
            t.write_text(_PART_SEP.sub(lambda m: 'DataDir & "' + os.sep, t.read_text(encoding="utf-8")),
                         encoding="utf-8")
        print(f"写入 {dst}（DataDir = {parquet}）")
    return 0


# ---------------------------------------------------------------------------
# Probe (Windows)


def _num(result) -> float | None:
    if not result.ok or not result.rows:
        return None
    v = result.rows[0][0]
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rel(got: float, expected: float) -> float:
    if expected == 0:
        return abs(got)
    return abs(got - expected) / abs(expected)


def _ws(s: str) -> str:
    return " ".join(s.split())


def probe(tier: str, out_dir: Path, executor=None, expected_path: Path = EXPECTED_JSON) -> tuple[int, str]:
    from harness.executors import (AUTO_TABLE_PREFIXES, DaxConnectionError, DaxExecutor, DaxModelMismatch,
                                   discover_port, expected_signature)
    from render.check_pbip import load_model

    lines = [f"T17 DAX 探测 · 档位 {tier} · {datetime.now().isoformat(timespec='seconds')}", ""]
    fails = 0

    def say(s: str = "") -> None:
        lines.append(s)
        print(s)

    say("== 连接")
    if executor is None:
        try:
            port, path = discover_port()
        except DaxConnectionError as exc:
            say(f"失败：{exc}")
            return 1, "\n".join(lines)
        say(f"端口 {port}（{path or 'SEMDEBT_PBI_PORT'}）")
        executor = DaxExecutor(tier, timeout_s=600, port=port)
    try:
        sig = executor.verify_model(expected_signature(tier))
        say(f"模型核对通过：retail-{tier}，{len(sig['tables'])} 张表（含 Desktop 自加的），{len(sig['measures'])} 个度量值")
    except (DaxConnectionError, DaxModelMismatch) as exc:
        say(f"失败：{exc}")
        return 1, "\n".join(lines)
    except Exception as exc:  # noqa: BLE001 - report whatever ADOMD raised
        say(f"失败：{type(exc).__name__}: {exc}")
        return 1, "\n".join(lines)

    say("")
    say("== Desktop 实际载入的模型")
    auto = [t for t in sig["tables"] if t.startswith(AUTO_TABLE_PREFIXES)]
    say(f"自动日期表：{len(auto)} 张（应为 0；模型里关掉了自动日期/时间）")
    fails += bool(auto)
    tables = executor.dmv("SELECT [Name], [Description] FROM $SYSTEM.TMSCHEMA_TABLES")
    columns = executor.dmv("SELECT [ExplicitName], [Description], [Type] FROM $SYSTEM.TMSCHEMA_COLUMNS")
    t_desc = sum(1 for _, d in tables if d)
    c_desc = sum(1 for _, d, ty in columns if d and int(ty) != 3)
    want_desc = tier != "L0"
    ok = (t_desc > 0 and c_desc > 0) if want_desc else (t_desc == 0 and c_desc == 0)
    fails += not ok
    say(f"描述：表 {t_desc} 个、列 {c_desc} 个带描述（{'应大于 0' if want_desc else '应为 0'}）{'' if ok else '  ← 不符'}")
    try:
        ling = executor.dmv("SELECT [Content] FROM $SYSTEM.TMSCHEMA_LINGUISTIC_METADATA")
        terms = sum(len(re.findall(r'"State"\s*:\s*"Authored"', str(c[0] or ""))) for c in ling)
        say(f"同义词（linguistic metadata）：{len(ling)} 份，约 {terms} 个条目（L0 应为 0）")
    except Exception as exc:  # noqa: BLE001
        say(f"同义词：DMV 读取失败（{type(exc).__name__}），记下来即可")
    rels = executor.dmv("SELECT [IsActive] FROM $SYSTEM.TMSCHEMA_RELATIONSHIPS")
    model = load_model(tier)
    want_rels, want_inactive = len(model["relationships"]), sum(not r["active"] for r in model["relationships"])
    got_inactive = sum(1 for (a,) in rels if not a)
    ok = len(rels) == want_rels and got_inactive == want_inactive
    fails += not ok
    say(f"关系：{len(rels)} 条，非激活 {got_inactive} 条（应为 {want_rels} / {want_inactive}）{'' if ok else '  ← 不符'}")
    say("AI 指令（Copilot/Instructions/instructions.md）：DMV 读不到，请在 Desktop 里打开 Copilot 面板目测，结果手写在下面。")

    spec = json.loads(expected_path.read_text(encoding="utf-8"))
    tol = spec["tolerance"]
    groups = [("rows", "逐表行数"), ("sums", "合计与去重计数"), ("orphans", "孤儿行（5 条关系，照现状建模）"),
              ("measures", "度量值（L2）"), ("variants", "v1.4 变体度量值（L2）")]
    for group, title in groups:
        checks = [c for c in spec["checks"] if c["group"] == group and tier in c["dax"]]
        if not checks:
            continue
        say("")
        say(f"== {title}：{len(checks)} 项，容差 {tol:.1%}")
        for c in checks:
            res = executor.execute(c["dax"][tier])
            got = _num(res)
            exp = c["expected"]
            if got is None:
                fails += 1
                say(f"  失败  {c['title']}：{res.error_class or '非数值'} {(res.error or '')[:200]}")
                continue
            rel = _rel(got, exp)
            ok = rel <= tol
            fails += not ok
            say(f"  {'通过' if ok else '不符'}  {c['title']}：DAX {got:,.6f}  对照 {exp:,.6f}  相差 {rel:.4%}"
                f"  [{res.elapsed_s:.1f}s]")

    if tier == "L1":
        say("")
        say(f"== 写法说明 2 级条目（render/syntax/dax.md）：{len(SYNTAX)} 项")
        for sid, claim, query, expect in SYNTAX:
            res = executor.execute(query)
            ok, what = judge_syntax(expect, res)
            fails += not ok
            say(f"  {'符合' if ok else '不符'}  {sid} {claim}：{what}")
        res = executor.execute("EVALUATE INFO.PARTITIONS ()")
        ok = res.error_class == "metadata_function"
        fails += not ok
        say(f"  {'符合' if ok else '不符'}  执行器拒绝 INFO.：{res.error_class}")

    if tier == "L2":
        say("")
        say("== 度量值表达式：Desktop 载入的 vs 渲染器写的")
        loaded = {name: expr for _, name, expr in executor.dmv("SELECT [TableID], [Name], [Expression] FROM $SYSTEM.TMSCHEMA_MEASURES")}
        written = {k: v for t in model["tables"].values() for k, v in t["expressions"].items()}
        diff = [k for k in written if _ws(str(loaded.get(k, ""))) != _ws(written[k])]
        fails += bool(diff)
        say(f"  {len(written) - len(diff)} / {len(written)} 一致" + (f"；不同：{', '.join(diff[:20])}" if diff else ""))

    say("")
    say(f"结论：{'全部通过' if not fails else f'{fails} 项不通过或不符，贴回给 Mac 上的 agent'}")
    text = "\n".join(lines) + "\n"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"probe-{tier}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    path.write_text(text, encoding="utf-8")
    print(f"\n报告写入 {path}")
    return (1 if fails else 0), text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("expected", help="Mac: compute reference numbers from the Parquet files with chDB")
    sub.add_parser("prepare", help="Windows: verify the bundle and make the working PBIPs")
    p = sub.add_parser("probe", help="Windows: run the checks against the model open in Desktop")
    p.add_argument("--tier", required=True, choices=TIERS)
    args = ap.parse_args(argv)
    if args.cmd == "expected":
        spec = build_expected()
        EXPECTED_JSON.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        n = {g: sum(c["group"] == g for c in spec["checks"]) for g in ("rows", "sums", "orphans", "measures", "variants")}
        print(f"写入 {EXPECTED_JSON.relative_to(REPO)}：{n}")
        return 0
    if args.cmd == "prepare":
        return prepare()
    return probe(args.tier, data_root() / "t17-probe")[0]


if __name__ == "__main__":
    raise SystemExit(main())
