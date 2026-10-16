"""T11 SQL harness: prompt, parsing, execution scope, attempt flow, logs, resume, dry run.

Offline tests use MockClient and a fake executor. Tests marked ``chdb`` open
``$SEMDEBT_DATA_DIR/chdb`` and are skipped when it is not available.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness import prompt as P
from harness import run_direct as R
from harness.cells import CELLS, SYNTAX, Cell
from harness.client import APIError, MockClient
from harness.executors import (
    ENGINE_ERROR, SCOPE_VIOLATION, TIMEOUT, ExecResult, ast_references, mask_sql, scope_violations,
)
from harness.questions import Question  # noqa: E402

CHDB = Path(os.environ.get("SEMDEBT_DATA_DIR", "/nonexistent")).expanduser() / "chdb"
needs_chdb = pytest.mark.skipif(not CHDB.exists(), reason="chDB data directory not available")


# ---------------------------------------------------------------------------
# prompt


def test_prompt_order_and_stable_prefix():
    system = P.system_message("CTX-BODY", "SYNTAX-BODY")
    assert system.index(P.SYSTEM_PROMPT) < system.index("CTX-BODY") < system.index("SYNTAX-BODY")
    m1 = P.first_messages(system, "问题一")
    m2 = P.first_messages(system, "问题二")
    assert m1[0] == m2[0]  # identical prefix for every question of a cell
    assert [m["role"] for m in m1] == ["system", "user"]
    assert m1[1]["content"] == "问题一"  # the user message is the question only


def test_system_prompt_has_no_dataset_specific_content():
    schema = json.loads((REPO / "render" / "physical_schema.json").read_text(encoding="utf-8"))
    names = set()
    for db, tables in schema.items():
        names.add(db)
        for table, columns in tables.items():
            names.add(table)
            names.update(c[0] if isinstance(c, list) else c for c in columns)
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", P.SYSTEM_PROMPT))
    assert not words & {n for n in names if isinstance(n, str)}
    assert "Contoso" not in P.SYSTEM_PROMPT


def test_system_message_for_real_cell_contains_context_and_syntax():
    cell = CELLS["SQL-R"]
    if not (REPO / "build" / "contexts" / "SQL-R.yaml").exists():
        pytest.skip("contexts not rendered")
    system = R.system_for(cell)
    assert (SYNTAX / "clickhouse_sql.md").read_text(encoding="utf-8").strip() in system


@pytest.mark.parametrize("text,query,assumption,refused,blocks", [
    ("```sql\nSELECT 1\n```\n假设：无", "SELECT 1", "无", False, 1),
    ("思路……\n```sql\nSELECT 1\n```\n再想想\n```sql\nSELECT 2;\n```\n**假设：** 按年统计", "SELECT 2;", "** 按年统计", False, 2),
    ("CANNOT_ANSWER", None, None, True, 0),
    ("我觉得可以这样写 SELECT 1", None, None, False, 0),
    ("```\nSELECT 3\n```\n假设:取全部门店", "SELECT 3", "取全部门店", False, 1),
])
def test_parse_response(text, query, assumption, refused, blocks):
    p = P.parse_response(text)
    assert (p.query, p.refused, p.n_code_blocks) == (query, refused, blocks)
    if assumption is not None:
        assert p.assumption is not None and assumption.strip("* ") in p.assumption


# ---------------------------------------------------------------------------
# execution scope (static, offline)

AST_SAMPLE = """SelectWithUnionQuery (children 1)
 ExpressionList (children 1)
  SelectQuery (children 3)
   ExpressionList (children 1)
    Identifier s.amount (alias ads)
   TablesInSelectQuery (children 2)
    TablesInSelectQueryElement (children 1)
     TableExpression (children 1)
      TableIdentifier ads.ads_sales_month_store (alias s)
    TablesInSelectQueryElement (children 2)
     TableExpression (children 1)
      TableIdentifier retail.FactSales (alias f)
     TableJoin (children 1)
      Literal UInt64_1
   Function in (children 1)
    ExpressionList (children 2)
     Literal UInt64_1
     Identifier retail.FactOnlineSales
"""


def test_ast_references():
    tables, functions, aliases, idents = ast_references(AST_SAMPLE)
    assert tables == ["ads.ads_sales_month_store", "retail.FactSales"]
    assert aliases == {"ads", "s", "f"}
    assert "retail.FactOnlineSales" in idents


def test_scope_rejects_other_databases_but_not_aliases():
    known = frozenset({"retail", "ads", "dwd", "l0", "system", "default"})
    bad = scope_violations(AST_SAMPLE, frozenset({"ads"}), known)
    assert bad == ["retail.FactOnlineSales", "retail.FactSales"]
    assert scope_violations(AST_SAMPLE, frozenset({"ads", "retail"}), known) == []


def test_mask_sql_hides_strings_and_comments():
    masked = mask_sql("SELECT 'a;b' -- x;y\n, `c;d` /* ; */")
    assert ";" not in masked
    assert len(masked) == len("SELECT 'a;b' -- x;y\n, `c;d` /* ; */")


# ---------------------------------------------------------------------------
# execution scope on chDB (the carried-forward requirement)


@needs_chdb
@pytest.mark.parametrize("query", [
    "SELECT sum(SalesAmount) FROM retail.FactSales",
    "SELECT sum(SalesAmount) FROM retail.FactOnlineSales",
    "SELECT count() FROM `retail`.`FactSales`",
    "WITH x AS (SELECT * FROM retail.FactSales) SELECT count() FROM x",
    "SELECT 1 WHERE 1 IN (SELECT 1 FROM retail.FactInventory)",
    "SELECT count() FROM dwd.wide_sales",
    "SELECT count() FROM system.tables",
    "SELECT count() FROM file('anything.csv')",
])
def test_l15s_cannot_reach_detail_tables(query):
    ex = R.make_executor(CELLS["SQL-L1.5S"], timeout_s=30)
    result = ex.execute(query)
    assert not result.ok
    assert result.error_class == SCOPE_VIOLATION


@needs_chdb
def test_scope_allows_own_databases():
    assert R.make_executor(CELLS["SQL-L1.5S"], 30).execute("SELECT count() FROM ads.dim_store").ok
    assert R.make_executor(CELLS["SQL-L1.5S"], 30).execute("SELECT count() FROM dim_store").ok  # default db
    w = R.make_executor(CELLS["SQL-L1.5W"], 30)
    assert w.execute("SELECT count() FROM retail.DimStore").ok
    assert w.execute("SELECT count() FROM ads.dim_store").error_class == SCOPE_VIOLATION
    assert R.make_executor(CELLS["SQL-L0"], 30).execute("SELECT count() FROM retail.DimStore").error_class == SCOPE_VIOLATION
    assert R.make_executor(CELLS["SQL-L1"], 30).execute("SELECT count() FROM l0.x").error_class == SCOPE_VIOLATION


@needs_chdb
def test_timeout_and_engine_errors_are_classified():
    ex = R.make_executor(CELLS["SQL-L1"], timeout_s=1)
    slow = ex.execute("SELECT count() FROM numbers(100000000000) WHERE sipHash64(number) % 7 = 3")
    assert slow.error_class == TIMEOUT
    bad = ex.execute("SELECT nope FROM retail.DimStore")
    assert bad.error_class == ENGINE_ERROR
    syntax = ex.execute("SELEC 1")
    assert syntax.error_class == ENGINE_ERROR and "EXPLAIN" not in syntax.error
    assert ex.execute("SELECT 1; SELECT 2").error_class == "forbidden_statement"
    assert ex.execute("SELECT 1 SETTINGS max_execution_time = 999").error_class == "forbidden_statement"


@needs_chdb
def test_numbers_come_back_unquoted():
    r = R.make_executor(CELLS["SQL-L1"], 30).execute("SELECT count() AS c, toDecimal64(1.25, 2) AS d FROM retail.DimStore")
    assert isinstance(r.rows[0][0], int) and isinstance(r.rows[0][1], float)
    assert r.columns[0]["type"] == "UInt64"


# ---------------------------------------------------------------------------
# attempt flow with a fake executor


class FakeExecutor:
    name = "fake"

    def __init__(self, table: dict[str, ExecResult]):
        self.table = table
        self.seen: list[str] = []

    def execute(self, query: str) -> ExecResult:
        self.seen.append(query)
        return self.table.get(query.strip(), ExecResult(error="Code: 47. Unknown identifier", error_class=ENGINE_ERROR))


QTEXT = "这是一个绝不能进入日志的问题原文样本"
Q = Question("Q001", QTEXT, refs=[[[42]]], rules={"ordered": False, "top_n": None, "tie_columns": [],
                                                    "value_kinds": ["count"], "value_types": ["UInt64"]})


def _ctx(tmp_path, client, executor, cell="SQL-L1"):
    return R.RunContext(run_id="test-run", cell=CELLS[cell], client=client, executor=executor,
                        system=P.system_message("ctx", "syntax"), eval_commit="evalabc", harness_commit="h123",
                        timeout_s=120, raw_dir=tmp_path / "raw")


def _scripted(*answers):
    answers = list(answers)
    calls = []

    def respond(messages):
        calls.append(messages)
        return answers.pop(0)
    return respond, calls


def test_correct_first_try(tmp_path):
    respond, calls = _scripted("```sql\nSELECT 42\n```\n假设：无")
    ex = FakeExecutor({"SELECT 42": ExecResult(rows=[[42]], columns=[{"name": "c", "type": "UInt64"}])})
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), ex), Q, 1)
    assert rec["status"] == "done" and rec["final"]["outcome"] == "correct" and rec["first"] == "correct"
    assert rec["n_calls"] == 1 and not rec["fixed"]
    assert rec["model_version"] == "mock-version"
    assert set(rec["usage"]) >= {"cache_hit_tokens", "cache_miss_tokens", "completion_tokens", "reasoning_tokens"}
    raw = tmp_path / "raw" / "Q001_r1_t0.json"
    assert raw.exists() and R.sha256(raw.read_bytes()) == rec["turns"][0]["raw_sha256"]
    assert "reasoning_content" in raw.read_text()


def test_exec_error_is_sent_back_exactly_once(tmp_path):
    respond, calls = _scripted("```sql\nSELECT bad\n```\n假设：无", "```sql\nSELECT 42\n```\n假设：无")
    ex = FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])})
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), ex), Q, 1)
    assert rec["first"] == "exec_error" and rec["final"]["outcome"] == "correct" and rec["fixed"]
    assert len(calls) == 2
    fix = calls[1]
    assert [m["role"] for m in fix] == ["system", "user", "assistant", "user"]
    assert "Unknown identifier" in fix[3]["content"]
    assert all("reasoning_content" not in m for m in fix)
    assert rec["turns"][0]["exec"]["status"] == "error" and rec["turns"][1]["exec"]["status"] == "ok"


def test_no_second_fix_and_no_retry_on_wrong(tmp_path):
    respond, calls = _scripted("```sql\nSELECT bad\n```", "```sql\nSELECT worse\n```")
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({})), Q, 1)
    assert rec["final"]["outcome"] == "exec_error" and rec["final"]["error_class"] == ENGINE_ERROR and len(calls) == 2
    respond, calls = _scripted("```sql\nSELECT 41\n```")
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 41": ExecResult(rows=[[41]])})), Q, 2)
    assert rec["final"]["outcome"] == "wrong" and len(calls) == 1


def test_scope_violation_goes_back_to_model_and_is_classified(tmp_path):
    respond, calls = _scripted("```sql\nSELECT x FROM retail.FactSales\n```", "```sql\nSELECT x FROM retail.FactSales\n```")
    err = ExecResult(error="not accessible", error_class=SCOPE_VIOLATION)
    ex = FakeExecutor({"SELECT x FROM retail.FactSales": err})
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), ex, "SQL-L1.5S"), Q, 1)
    assert len(calls) == 2 and rec["final"]["error_class"] == SCOPE_VIOLATION


def test_refusal_and_missing_query(tmp_path):
    respond, calls = _scripted("CANNOT_ANSWER")
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({})), Q, 1)
    assert rec["final"]["outcome"] == "refused" and len(calls) == 1
    respond, calls = _scripted("不知道怎么写")
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({})), Q, 1)
    assert rec["final"]["outcome"] == "exec_error" and rec["final"]["error_class"] == R.NO_QUERY and len(calls) == 1


def test_rules_are_passed_through_untouched(tmp_path, monkeypatch):
    seen = []
    real = R.score_detailed

    def spy(candidate, refs, rules):
        seen.append(rules)
        return real(candidate, refs, rules)
    monkeypatch.setattr(R, "score_detailed", spy)
    respond, _ = _scripted("```sql\nSELECT 42\n```")
    R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])})), Q, 1)
    assert seen and all(r is Q.rules for r in seen)


def test_api_error_is_recorded(tmp_path):
    class Broken:
        model = "deepseek-flash"

        def chat(self, messages):
            raise APIError("HTTP 503", 5)
    rec = R.run_attempt(_ctx(tmp_path, Broken(), FakeExecutor({})), Q, 1)
    assert rec["status"] == "api_error" and rec["transport_retries"] == 5


# ---------------------------------------------------------------------------
# cell run: log, no question text, resume


def test_run_cell_log_resume_and_no_question_text(tmp_path):
    questions = [Question(f"Q{i:03d}", f"{QTEXT}{i}", [[[i]]], {"ordered": False, "top_n": None}) for i in range(1, 4)]
    by_text = {q.text: q for q in questions}

    def respond(messages):
        q = by_text[messages[1]["content"]]
        return f"```sql\nSELECT {int(q.qid[1:])}\n```\n假设：无"
    ex = FakeExecutor({f"SELECT {i}": ExecResult(rows=[[i]]) for i in range(1, 4)})
    ctx = _ctx(tmp_path, MockClient(respond), ex)
    path = R.run_cell(ctx, questions[:2], reps=3, concurrency=4, runs_root=tmp_path / "runs", progress=lambda *_: None)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    # resume: only the missing pairs run
    path = R.run_cell(ctx, questions, reps=3, concurrency=4, runs_root=tmp_path / "runs", progress=lambda *_: None)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 9
    assert len(ex.seen) == 9
    assert QTEXT not in path.read_text(encoding="utf-8")
    recs = [json.loads(l) for l in lines]
    required = {"qid", "cell", "rep", "model_version", "eval_commit", "turns", "final", "usage", "latency_s", "status"}
    assert all(required <= set(r) for r in recs)
    assert all("raw_sha256" in t and "query" in t and "assumption" in t for r in recs for t in r["turns"])
    assert len({r["system_sha256"] for r in recs}) == 1
    s = R.summarize(path)
    assert s["attempts"] == 9 and s["accuracy"] == 1.0


def test_api_error_lines_are_rerun_on_resume(tmp_path):
    path = R.log_path("test-run", "SQL-L1", tmp_path / "runs")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"qid": "Q001", "rep": 1, "status": "api_error"}) + "\n"
                    + json.dumps({"qid": "Q001", "rep": 2, "status": "done"}) + "\n", encoding="utf-8")
    assert R.done_pairs(path) == {("Q001", 2)}


# ---------------------------------------------------------------------------
# dry run and pricing


def test_dry_run_matches_board_unit_list(tmp_path):
    board = (REPO / "tasks" / "BOARD.md").read_text(encoding="utf-8")
    assert "| SQL 直答 | L0、R、L1、L1c、L1.5W、L1.5S | T13 |" in board
    assert "| SQL 直答 | L1 调优 | T14 |" in board
    assert "| 英文锚点 | R-EN、L1c-EN" in board
    expected = {"SQL-L0", "SQL-R", "SQL-L1", "SQL-L1c", "SQL-L1.5W", "SQL-L1.5S", "SQL-L1-tuned", "SQL-L2",
                "SQL-R-EN", "SQL-L1c-EN"}
    assert set(CELLS) == expected
    rows, total = R.dry_run(list(CELLS.values()), {"zh": 122, "en": 99}, 3, "deepseek-flash", fix_rate=0.1,
                            output_tokens=3000, hit_ratio=0.95, question_tokens=60, runs_root=tmp_path)
    by = {r["cell"]: r for r in rows}
    assert by["SQL-L1"]["attempts"] == 366 and by["SQL-L1"]["calls"] == round(366 * 1.1)
    assert by["SQL-R-EN"]["attempts"] == 297
    assert sum(r["attempts"] for r in rows) == 8 * 366 + 2 * 297
    assert total > 0


def test_cost_and_peak():
    from datetime import datetime
    usage = {"cache_hit_tokens": 1_000_000, "cache_miss_tokens": 1_000_000, "completion_tokens": 1_000_000}
    assert R.cost_cny("deepseek-flash", usage, peak=False) == pytest.approx(0.02 + 1 + 4)
    assert R.cost_cny("deepseek-flash", usage, peak=True) == pytest.approx(2 * 5.02)
    assert R.is_peak(datetime(2026, 10, 16, 10, 0, tzinfo=R.BEIJING))       # Friday 10:00
    assert not R.is_peak(datetime(2026, 10, 16, 13, 0, tzinfo=R.BEIJING))   # lunch
    assert not R.is_peak(datetime(2026, 10, 17, 10, 0, tzinfo=R.BEIJING))   # Saturday


@needs_chdb
def test_failed_query_does_not_leak_into_the_next_result():
    """chDB returns a failed streaming query's output to the next query unless resynced."""
    ex = R.make_executor(CELLS["SQL-L1"], timeout_s=30)
    failed = ex.execute("SELECT throwIf(number = 5) FROM numbers(100000)")
    assert not failed.ok
    after = ex.execute("SELECT 'fresh' AS x")
    assert after.ok and after.rows == [["fresh"]]


# ---------------------------------------------------------------------------
# scope message and resource limits (decisions/2026-10-16-t11-exec-limits-and-scope-message.md)

from harness.executors import RESOURCE_LIMIT, SCOPE_MESSAGE, ChdbExecutor  # noqa: E402


@needs_chdb
def test_scope_message_is_the_harness_message_not_the_engine_hint():
    ex = R.make_executor(CELLS["SQL-L1.5S"], 30)
    static = ex.execute("SELECT count() FROM retail.FactSales")
    assert static.error == SCOPE_MESSAGE and "retail" in static.detail
    # unqualified detail table: ClickHouse answers "Maybe you meant retail.FactOnlineSales?"
    hinted = ex.execute("SELECT count() FROM FactOnlineSales")
    assert hinted.error_class == SCOPE_VIOLATION and hinted.error == SCOPE_MESSAGE
    assert "retail" not in hinted.error and "Maybe you meant" in hinted.detail
    assert "retail" not in json.dumps(hinted.summary(), ensure_ascii=False)


@needs_chdb
def test_other_engine_errors_go_back_verbatim():
    bad = R.make_executor(CELLS["SQL-L1"], 30).execute("SELECT nope FROM retail.DimStore")
    assert bad.error_class == ENGINE_ERROR and "nope" in bad.error and bad.error == bad.detail


@needs_chdb
def test_resource_limits_are_classified_apart_from_timeouts_and_engine_errors():
    rows = ChdbExecutor(("retail",), timeout_s=30, max_result_rows=10).execute("SELECT number FROM numbers(100)")
    assert (rows.error_class, rows.limit) == (RESOURCE_LIMIT, "result_rows")
    mem = ChdbExecutor(("retail",), timeout_s=30, max_memory_bytes=50 * 1024**2).execute(
        "SELECT length(groupArray(number)) FROM numbers(100000000)")
    assert (mem.error_class, mem.limit) == (RESOURCE_LIMIT, "memory")
    assert mem.summary()["limit"] == "memory"
    ok = R.make_executor(CELLS["SQL-L1"], 30).execute("SELECT number FROM numbers(100)")  # default caps restored
    assert ok.ok and len(ok.rows) == 100
    ex = R.make_executor(CELLS["SQL-L1"], 30)
    assert ex.execute("SELECT 1 SETTINGS max_memory_usage = 0").error_class == "forbidden_statement"


def test_limits_are_global_constants():
    from harness import executors as E
    assert E.DEFAULT_MAX_RESULT_ROWS >= 1_000_000
    assert 0 < E.DEFAULT_MAX_MEMORY_BYTES


# ---------------------------------------------------------------------------
# pending scoring (judge / no rules / no refs)


def test_rows_for_unscorable_questions_are_pending_but_errors_are_scored(tmp_path):
    q = Question("Q002", QTEXT, refs=[[[1]]], rules=None)
    respond, _ = _scripted("```sql\nSELECT 41\n```")
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 41": ExecResult(rows=[[41]])})), q, 1)
    assert rec["final"]["outcome"] == "pending" and rec["final"]["pending"] == "no_rules"
    assert (tmp_path / "raw" / "Q002_r1_t0.exec.json").exists()
    judge = Question("Q003", QTEXT, refs=[[[1]]], rules={"ordered": False, "top_n": None}, scoring="judge")
    respond, _ = _scripted("CANNOT_ANSWER")
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({})), judge, 1)
    assert rec["final"]["outcome"] == "refused" and rec["scoring"] == "judge"


# ---------------------------------------------------------------------------
# the real question bank and the external contexts

EVAL = Path(os.environ.get("SEMDEBT_EVAL_DIR", "/nonexistent")).expanduser()
needs_eval = pytest.mark.skipif(not (EVAL / "questions").is_dir(), reason="question bank not available")


def test_parse_value_types():
    from harness.questions import parse_value
    assert parse_value("\\N", "Nullable(Float64)") is None
    assert parse_value("12", "UInt64") == 12 and isinstance(parse_value("12", "UInt64"), int)
    assert parse_value("1.5", "Float64") == 1.5 and parse_value("inf", "Float64") == float("inf")
    assert parse_value("2020-01-01", "Nullable(Date)") == "2020-01-01"
    assert parse_value("7", "String") == "7"


@needs_eval
def test_load_real_bank_and_pass_rules_through():
    import yaml
    from harness.questions import load_questions
    zh, en = load_questions(EVAL), load_questions(EVAL, lang="en")
    assert len(en) == 99 and "EN33" not in {q.qid for q in en}
    records = {r["id"]: r for p in sorted((EVAL / "questions").glob("*.yaml"))
               for r in yaml.safe_load(p.read_text(encoding="utf-8"))["questions"]}
    assert {q.qid for q in zh} == set(records)
    for q in zh:
        rec = records[q.qid]
        assert q.text == rec["text_zh"] and len(q.refs) == len(rec["refs"])
        assert q.rules is rec.get("rules") or q.rules == rec.get("rules")   # untouched
        assert q.scoring == rec["scoring"]


@needs_eval
def test_external_contexts():
    l1c, ren = R.system_for(CELLS["SQL-L1c"]), R.system_for(CELLS["SQL-R-EN"])
    md = (EVAL / R.VENDOR_SEMANTIC_LAYER).read_text(encoding="utf-8").strip()
    ddl = R.VENDOR_DDL.read_text(encoding="utf-8").strip()
    assert md in l1c and ddl in l1c and l1c.index(md) < l1c.index(ddl) < l1c.index(P.SYNTAX_HEADER)
    assert ddl in ren and md not in ren
    assert R.system_for(CELLS["SQL-L1c-EN"]) == l1c


def test_transport_errors_mid_read_are_retried(monkeypatch):
    """An ssl.SSLError while reading the body (seen in the T11 smoke run) is a transport retry."""
    import ssl
    import urllib.request
    from harness import client as C

    payload = json.dumps({"model": "m", "choices": [{"message": {"content": "x"}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 1}}).encode()
    events = [ssl.SSLError("record layer failure"), payload]

    class Resp:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self.body

    def fake_urlopen(request, timeout):
        e = events.pop(0)
        if isinstance(e, Exception):
            raise e
        return Resp(e)

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(C.time, "sleep", lambda s: None)
    reply = C.DeepSeekClient("deepseek-flash").chat([{"role": "user", "content": "hi"}])
    assert reply.content == "x" and reply.transport_retries == 1
