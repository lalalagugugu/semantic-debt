"""T17 DAX executor, probe and DAX delivery check: offline, with fake ADOMD sessions and fake .NET
values. No Power BI, no Windows, no question bank, no model API."""

from __future__ import annotations

import json
import math
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness import dax_probe as DP  # noqa: E402
from harness import executors as E  # noqa: E402
from harness.cells import CELLS, DAX_CELLS, dax_tier  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


class FakeSession:
    """Stands in for AdomdSession: records queries, answers from a function."""

    def __init__(self, answer=None):
        self.queries: list[str] = []
        self.answer = answer or (lambda q: ([{"name": "[v]", "type": "dax:Int64"}], [[1]]))

    def run(self, query, timeout_s, max_rows, on_command=None):
        self.queries.append(query)
        out = self.answer(query)
        if isinstance(out, BaseException):
            raise out
        if len(out[1]) > max_rows:
            raise E._ResultTooLarge
        return out


# ---------------------------------------------------------------------------
# static checks: INFO.* (T10 handoff) and statement shape


@pytest.mark.parametrize("query", [
    "EVALUATE INFO.PARTITIONS()",
    "EVALUATE info.tables()",
    "EVALUATE INFO . VIEW.TABLES ( )",
    "DEFINE VAR t = INFO.COLUMNS() EVALUATE t",
    "EVALUATE SELECTCOLUMNS ( INFO.PARTITIONS (), \"q\", [QueryDefinition] )",
    "EVALUATE ROW(\"v\", 1) // fine\n+ COUNTROWS(INFO.MEASURES())",
    "SELECT * FROM $SYSTEM.TMSCHEMA_PARTITIONS",
    "EVALUATE ROW(\"v\", 1) $system",
])
def test_metadata_functions_are_rejected_before_execution(query):
    session = FakeSession()
    res = E.DaxExecutor("L0", session=session).execute(query)
    assert res.error_class == E.METADATA_FUNCTION and res.error == E.METADATA_MESSAGE
    assert session.queries == []                      # rejected, not executed and filtered


@pytest.mark.parametrize("query", [
    'EVALUATE ROW ( "INFO.PARTITIONS()", 1 )',         # inside a string
    "// INFO.PARTITIONS()\nEVALUATE ROW ( \"v\", 1 )",  # inside a comment
    "/* $SYSTEM */ EVALUATE ROW ( \"v\", 1 )",
    "EVALUATE VALUES ( 'INFO.x'[y] )",                  # a quoted table name
    "EVALUATE ROW ( \"v\", [INFO.Something] )",         # a bracketed name
    "DEFINE MEASURE 'T'[m] = 1 EVALUATE ROW ( \"v\", [m] ) ORDER BY [v]",
    "  evaluate { 1 }",
])
def test_ordinary_queries_pass_the_static_check(query):
    assert E.dax_static_check(query) is None


@pytest.mark.parametrize("query", [
    "SELECT [Name] FROM T", "WITH MEMBER x AS 1 SELECT x ON 0 FROM [Model]", "", "   ",
    "EVALUATE { 1 } EVALUATE { 2 }", "<Batch/>",
])
def test_non_query_statements_are_forbidden(query):
    session = FakeSession()
    res = E.DaxExecutor("L1", session=session).execute(query)
    assert res.error_class == E.FORBIDDEN_STATEMENT and session.queries == []


def test_metadata_wins_over_statement_shape():
    assert E.dax_static_check("INFO.TABLES()")[0] == E.METADATA_FUNCTION


# ---------------------------------------------------------------------------
# execution and error classes


def test_rows_and_columns_pass_through():
    cols = [{"name": "DimStore[StoreName]", "type": "dax:String"}, {"name": "[v]", "type": "dax:Decimal"}]
    ex = E.DaxExecutor("L1", session=FakeSession(lambda q: (cols, [["a", Decimal("1.5")], ["b", None]])))
    res = ex.execute('EVALUATE SUMMARIZECOLUMNS ( \'DimStore\'[StoreName], "v", 1 )')
    assert res.ok and res.rows == [["a", Decimal("1.5")], ["b", None]] and res.columns == cols
    assert res.summary()["row_count"] == 2


class AdomdErrorResponseException(Exception):
    pass


class AdomdConnectionException(Exception):
    pass


@pytest.mark.parametrize("exc, kind", [
    (AdomdErrorResponseException("Query (1, 10) The syntax for 'x' is incorrect."), E.ENGINE_ERROR),
    (AdomdErrorResponseException("The operation has been cancelled because of a timeout."), E.TIMEOUT),
    (AdomdErrorResponseException("Memory error: allocation failure"), E.RESOURCE_LIMIT),
    (AdomdConnectionException("No connection could be made"), E.TRANSPORT_ERROR),
    (E.DaxConnectionError("no engine"), E.TRANSPORT_ERROR),
])
def test_error_classes(exc, kind):
    res = E.DaxExecutor("L1", session=FakeSession(lambda q: exc)).execute('EVALUATE ROW ( "v", 1 )')
    assert res.error_class == kind
    if kind == E.ENGINE_ERROR:
        assert res.error == str(exc)                  # the engine's message goes back to the model


def test_stack_trace_is_not_sent_to_the_model():
    exc = AdomdErrorResponseException("Bad column.\n   at Microsoft.AnalysisServices.AdomdClient.X()\n   at Y")
    res = E.DaxExecutor("L1", session=FakeSession(lambda q: exc)).execute('EVALUATE ROW ( "v", 1 )')
    assert res.error == "Bad column."


def test_result_row_cap():
    ex = E.DaxExecutor("L1", max_result_rows=2, session=FakeSession(lambda q: ([{"name": "v"}], [[1], [2], [3]])))
    res = ex.execute("EVALUATE { 1, 2, 3 }")
    assert res.error_class == E.RESOURCE_LIMIT and res.limit == "result_rows"


def test_backstop_timeout_cancels_the_command():
    cancelled = []

    class Cmd:
        def Cancel(self):
            cancelled.append(True)

    class Slow(FakeSession):
        def run(self, query, timeout_s, max_rows, on_command=None):
            on_command(Cmd())
            time.sleep(3.0)
            return [], []

    ex = E.DaxExecutor("L1", timeout_s=1, session=Slow())
    ex.backstop_s = 0.05
    res = ex.execute('EVALUATE ROW ( "v", 1 )')
    assert res.error_class == E.TIMEOUT and cancelled == [True]


# ---------------------------------------------------------------------------
# .NET values


class DBNull:
    pass


class DateTime:
    def __init__(self, *a):
        self.Year, self.Month, self.Day, self.Hour, self.Minute, self.Second, self.Millisecond = a


def test_dotnet_values():
    Dec = type("Decimal", (), {"ToString": lambda self, *a: "12.50", "__str__": lambda self: "12.50"})
    assert E.dax_value(DBNull()) is None
    assert E.dax_value(Dec()) == Decimal("12.50")
    assert E.dax_value(DateTime(2009, 3, 1, 0, 0, 0, 0)) == datetime(2009, 3, 1)
    assert E.dax_value(DateTime(2009, 3, 1, 2, 3, 4, 5)) == datetime(2009, 3, 1, 2, 3, 4, 5000)
    for v in (None, True, 3, 2.5, "x"):
        assert E.dax_value(v) == v


# ---------------------------------------------------------------------------
# port discovery: one model at a time


def _workspace(root: Path, name: str, port: int, utf16: bool = True) -> None:
    d = root / name / "Data"
    d.mkdir(parents=True)
    (d / "msmdsrv.port.txt").write_bytes(str(port).encode("utf-16-le" if utf16 else "ascii"))


def test_port_file_encodings(tmp_path):
    _workspace(tmp_path, "a", 51234)
    _workspace(tmp_path, "b", 61234, utf16=False)
    assert E.read_port_file(tmp_path / "a" / "Data" / "msmdsrv.port.txt") == 51234
    assert E.read_port_file(tmp_path / "b" / "Data" / "msmdsrv.port.txt") == 61234


def test_discover_port(tmp_path, monkeypatch):
    monkeypatch.delenv("SEMDEBT_PBI_PORT", raising=False)
    _workspace(tmp_path, "AnalysisServicesWorkspace_1", 51000)        # left behind by a crash
    _workspace(tmp_path, "AnalysisServicesWorkspace_2", 52000)
    port, path = E.discover_port([tmp_path], alive=lambda p: p == 52000)
    assert port == 52000 and "AnalysisServicesWorkspace_2" in str(path)
    with pytest.raises(E.DaxConnectionError, match="一次只开一个模型"):
        E.discover_port([tmp_path], alive=lambda p: True)
    with pytest.raises(E.DaxConnectionError, match="没有找到"):
        E.discover_port([tmp_path], alive=lambda p: False)
    monkeypatch.setenv("SEMDEBT_PBI_PORT", "60000")
    assert E.discover_port([tmp_path], alive=lambda p: False) == (60000, None)


# ---------------------------------------------------------------------------
# the model open in Desktop must be the cell's tier


def _dmv_answer(sig: dict, extra_table: str | None = None):
    tables = list(sig["tables"]) + ([extra_table] if extra_table else [])
    ids = {t: i for i, t in enumerate(tables)}

    def answer(q):
        if "TMSCHEMA_TABLES" in q:
            return [], [[ids[t], t] for t in tables]
        if "TMSCHEMA_COLUMNS" in q:
            rows = [[ids[t], c, 1] for t in sig["tables"] for c in sig["tables"][t]]
            rows += [[ids[t], f"RowNumber-{i}", 3] for t, i in ids.items()]
            return [], rows
        if "TMSCHEMA_MEASURES" in q:
            return [], [[0, m] for m in sig["measures"]]
        raise AssertionError(q)
    return answer


@pytest.fixture(scope="module")
def rendered():
    from render import context, tmdl

    context.main([])
    tmdl.main()
    return {tier: E.expected_signature(tier) for tier in ("L0", "L1", "L2")}


def test_verify_model_accepts_the_right_tier(rendered):
    sig = rendered["L2"]
    ex = E.DaxExecutor("L2", session=FakeSession(_dmv_answer(sig, extra_table="LocalDateTable_abc")))
    ex.verify_model(sig)                               # Desktop's auto date tables are ignored here


@pytest.mark.parametrize("cell_tier, open_tier", [("L1", "L2"), ("L2", "L1"), ("L1", "L0"), ("L0", "L1")])
def test_verify_model_rejects_another_tier(rendered, cell_tier, open_tier):
    ex = E.DaxExecutor(cell_tier, session=FakeSession(_dmv_answer(rendered[open_tier])))
    with pytest.raises(E.DaxModelMismatch, match=f"retail-{cell_tier}"):
        ex.verify_model(rendered[cell_tier])


# ---------------------------------------------------------------------------
# cells and runner


def test_dax_cells_registered_but_not_in_all():
    assert set(DAX_CELLS) == {"DAX-L0", "DAX-L1", "DAX-L2"}
    assert not set(DAX_CELLS) & set(CELLS)
    for name, cell in DAX_CELLS.items():
        assert cell.stack == "dax" and cell.syntax == "dax.md" and cell.context == f"build:{name}.yaml"
        assert dax_tier(cell) == name[4:]


def test_make_executor_for_dax():
    from harness import run_direct as R

    ex = R.make_executor(DAX_CELLS["DAX-L2"], 30)
    assert isinstance(ex, E.DaxExecutor) and ex.tier == "L2" and ex.timeout_s == 30


def test_run_refuses_two_dax_cells(capsys):
    from harness import run_direct as R

    assert R.main(["--cell", "DAX-L0", "--cell", "DAX-L1", "--run-id", "x"]) == 2
    assert "one model at a time" in capsys.readouterr().out


def test_dax_system_message_uses_the_dax_note():
    from harness import run_direct as R

    system = R.system_for(DAX_CELLS["DAX-L1"])
    assert "## 查询语言：DAX" in system and "model_relationship: inactive" in system


# ---------------------------------------------------------------------------
# probe


def test_probe_expected_file_covers_every_tier_and_group():
    spec = json.loads(DP.EXPECTED_JSON.read_text(encoding="utf-8"))
    assert spec["tolerance"] == 0.005
    groups = {}
    for c in spec["checks"]:
        groups.setdefault(c["group"], []).append(c)
        assert isinstance(c["expected"], (int, float)) and not math.isnan(c["expected"]), c["id"]
    assert len(groups["rows"]) == 25 and all(set(c["dax"]) == {"L0", "L1", "L2"} for c in groups["rows"])
    assert len([c for c in groups["orphans"] if c["id"].endswith("by_value")]) == 5
    assert len(groups["variants"]) == 10 and all(set(c["dax"]) == {"L2"} for c in groups["variants"])
    for c in groups["rows"]:                            # L0 checks use L0 names only
        assert "'Fact" not in c["dax"]["L0"] and "'Dim" not in c["dax"]["L0"]
    for c in spec["checks"]:
        for q in c["dax"].values():
            assert E.dax_static_check(q) is None, q


def test_syntax_probe_queries_pass_the_static_check():
    for sid, _, query, _ in DP.SYNTAX:
        assert E.dax_static_check(query) is None or sid in {"S01"}, sid


def test_judge_syntax():
    ok = E.ExecResult(rows=[[1], [1]], columns=[])
    bad = E.ExecResult(error="x", error_class=E.ENGINE_ERROR)
    assert DP.judge_syntax("error", bad)[0] and not DP.judge_syntax("error", ok)[0]
    assert DP.judge_syntax(("rows>", 1), ok)[0] and DP.judge_syntax(("all_equal", 0), ok)[0]
    assert DP.judge_syntax(("inf", None), E.ExecResult(rows=[[float("inf")]]))[0]
    assert DP.judge_syntax(("blank_group", 0), E.ExecResult(rows=[["a"], [None]]))[0]
    assert DP.judge_syntax(("a=b+1", None), E.ExecResult(rows=[[5, 4]]))[0]


def test_probe_against_a_fake_engine(rendered, tmp_path):
    """L0: identity, no descriptions, every data check answered with the reference number → 0 failures;
    one wrong number → reported as a failure."""
    spec = json.loads(DP.EXPECTED_JSON.read_text(encoding="utf-8"))
    by_query = {c["dax"]["L0"]: c["expected"] for c in spec["checks"] if "L0" in c["dax"]}
    sig = rendered["L0"]
    meta = _dmv_answer(sig)
    from render.check_pbip import load_model

    rels = load_model("L0")["relationships"]

    def answer(q):
        if "TMSCHEMA_TABLES" in q and "Description" in q:
            return [], [[t, None] for t in sig["tables"]]
        if "TMSCHEMA_COLUMNS" in q and "Description" in q:
            return [], [[c, None, 1] for t in sig["tables"] for c in sig["tables"][t]]
        if "LINGUISTIC" in q:
            return [], []
        if "RELATIONSHIPS" in q:
            return [], [[r["active"]] for r in rels]
        if q in by_query:
            return [{"name": "[v]"}], [[by_query[q]]]
        return meta(q)

    ex = E.DaxExecutor("L0", session=FakeSession(answer))
    code, text = DP.probe("L0", tmp_path, executor=ex)
    assert code == 0, text
    assert "孤儿行" in text and "fct_ol_sls" not in text.split("孤儿行")[0][-10:]
    wrong = next(iter(by_query))
    by_query[wrong] = by_query[wrong] * 1.01 + 1
    code, text = DP.probe("L0", tmp_path, executor=ex)
    assert code == 1 and "不符" in text


def test_bundle_manifest_and_prepare(tmp_path, monkeypatch, rendered):
    import shutil

    bundle = tmp_path / "bundle"
    shutil.copytree(REPO / "build" / "pbip", bundle / "pbip")
    (bundle / "parquet").mkdir()
    (bundle / "parquet" / "X.parquet").write_bytes(b"PAR1")
    files = sorted(p for p in bundle.rglob("*") if p.is_file())
    (bundle / "MANIFEST.sha256").write_text(
        "".join(f"{DP.sha256_file(p)}  {p.relative_to(bundle).as_posix()}\n" for p in files), encoding="utf-8")
    assert DP.verify_manifest(bundle) == []
    monkeypatch.setenv("SEMDEBT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SEMDEBT_T17_BUNDLE", str(bundle))
    assert DP.prepare() == 0
    expr = (tmp_path / "data" / "t17-pbip-work" / "retail-L1" / "retail-L1.SemanticModel" / "definition"
            / "expressions.tmdl").read_text(encoding="utf-8")
    assert str((bundle / "parquet").resolve()) in expr
    (bundle / "parquet" / "X.parquet").write_bytes(b"PAR2")
    assert DP.verify_manifest(bundle) == ["哈希不符 parquet/X.parquet"]


def test_normalise_pbip_text():
    a = 'expression DataDir = "C:\\data\\parquet" meta [x]\n Source = File.Contents(DataDir & "\\T.parquet")'
    b = 'expression DataDir = "/srv/data/parquet" meta [x]\n Source = File.Contents(DataDir & "/T.parquet")'
    assert DP.normalise_pbip_text(a) == DP.normalise_pbip_text(b)


# ---------------------------------------------------------------------------
# DAX delivery check (render/check_pbip.py)


def test_pbip_check_passes_on_the_rendered_model(rendered):
    from render import check_pbip

    problems, stats = check_pbip.run()
    assert problems == {"L0": [], "L1": [], "L2": []}
    assert stats["L1"]["inactive"] == 2 and stats["L1"]["ctx_relationships"] == {"active": 43, "inactive": 2, "none": 3}
    assert stats["L2"]["measures"] == 102


def test_pbip_check_catches_a_missing_mark_and_a_type(rendered):
    import yaml
    from render import check_pbip

    ctx = yaml.safe_load((REPO / "build" / "contexts" / "DAX-L1.yaml").read_text(encoding="utf-8"))
    rel = next(r for r in ctx["relationships"] if r.get("model_relationship") == "inactive")
    del rel["model_relationship"]
    ds = next(d for d in ctx["datasets"] if d["name"] == "DimStore")
    next(c for c in ds["columns"] if c["name"] == "EntityKey")["type"] = "double"
    problems = check_pbip.check("L1", ctx, check_pbip.load_model("L1"))
    assert any("上下文 激活，模型 非激活" in p for p in problems)
    assert any("DimStore[EntityKey]：类型" in p for p in problems)


def test_ambiguous_paths():
    from render.check_pbip import ambiguous_paths

    assert ambiguous_paths([("F", "A"), ("A", "G"), ("F", "B"), ("B", "G")]) == ["F → G：2 条路径"]
    assert ambiguous_paths([("F", "A"), ("A", "G"), ("F", "B")]) == []
