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
from harness.client import APIError, MockClient, _reply
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


def test_system_prompt_carries_the_presentation_conventions():
    """names-required-by-system-prompt §2.1 / §3.2 and ux-conventions-and-annotation-disputes §1.1 / §5.4 / §8."""
    for phrase in ("用名称标识", "不要只给编码", "不要截断", "照原值输出", "组名用语义上下文里的叫法",
                   "每组一行", "合计、小计行", "YYYY-MM-DD", "原始单位", "不要格式化成字符串",
                   "（本期 − 基期）÷ 基期", "用正数表示", "名称缺失或是占位值时给编码",
                   "同时给出绝对值和百分比", "百分点时不必再给百分比", "列出多行排名时，输出名次列",
                   "同时给出基数（分母）", "平均值不算比率"):
        assert phrase in P.SYSTEM_PROMPT, phrase
    assert not re.search(r"Q\d{1,3}\b", P.SYSTEM_PROMPT)      # no question ids (hard rule 3)


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


def test_system_fingerprint_is_read_from_the_response():
    payload = {"model": "deepseek-flash", "system_fingerprint": "fp_e72d",
               "choices": [{"message": {"content": "x"}, "finish_reason": "stop"}], "usage": {}}
    assert _reply(json.dumps(payload).encode(), 0.0, 0).system_fingerprint == "fp_e72d"
    del payload["system_fingerprint"]
    assert _reply(json.dumps(payload).encode(), 0.0, 0).system_fingerprint is None


def test_fingerprint_is_logged_per_call_and_counted_in_summary(tmp_path):
    """The requested name stays the same; only the fingerprint shows the model behind it changed."""
    scripted, _ = _scripted("```sql\nSELECT bad\n```", "```sql\nSELECT 42\n```")
    client = MockClient(scripted, fingerprint="fp_old")

    def respond(messages):
        if len(messages) > 2:          # the fix call is served by a different deployment
            client.fingerprint = "fp_new"
        return scripted(messages)

    client.respond = respond
    ex = FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])})
    ctx = _ctx(tmp_path, client, ex)
    rec = R.run_attempt(ctx, Q, 1)
    assert rec["model_version"] == "mock-version"
    assert [t["system_fingerprint"] for t in rec["turns"]] == ["fp_old", "fp_new"]

    path = R.log_path("test-run", "SQL-L1", tmp_path / "runs")
    path.parent.mkdir(parents=True)
    legacy = {**rec, "rep": 2, "turns": [{k: v for k, v in t.items() if k != "system_fingerprint"} for t in rec["turns"][:1]]}
    path.write_text(json.dumps(rec) + "\n" + json.dumps(legacy) + "\n", encoding="utf-8")
    s = R.summarize(path)
    assert s["system_fingerprints"] == {"fp_old": 1, "fp_new": 1}
    assert s["calls_without_fingerprint"] == 1


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

    def spy(candidate, refs, rules, **kw):
        seen.append((rules, kw.get("reference_rules")))
        return real(candidate, refs, rules, **kw)
    monkeypatch.setattr(R, "score_detailed", spy)
    respond, _ = _scripted("```sql\nSELECT 42\n```")
    R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])})), Q, 1)
    assert seen and all(r is Q.rules and rr is None for r, rr in seen)


def test_per_reference_rules_are_passed_through_untouched(tmp_path, monkeypatch):
    """decisions/2026-10-16-per-reference-rules.md: a ref's own rules replace the
    question's wholesale; the harness hands both to the scorer as they are."""
    one = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["count"], "value_types": ["UInt64"]}
    two = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["other", "count"],
           "value_types": ["String", "UInt64"]}
    q = Question("Q005", QTEXT, refs=[[[8]], [["a", 7]]], rules=one, ref_rules=[None, two])
    seen = []
    real = R.score_detailed

    def spy(candidate, refs, rules, **kw):
        seen.append((rules, kw.get("reference_rules")))
        return real(candidate, refs, rules, **kw)
    monkeypatch.setattr(R, "score_detailed", spy)
    respond, _ = _scripted("```sql\nSELECT 'a', 7\n```")
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 'a', 7": ExecResult(rows=[["a", 7]])})), q, 1)
    assert rec["final"]["outcome"] == "correct" and rec["final"]["matched_ref"] == 1
    assert seen and all(r is one and rr is q.ref_rules for r, rr in seen)


def test_anchor_carries_the_revised_column(tmp_path):
    rules = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["count"], "value_types": ["UInt64"]}
    revised = Question("Q006", "", refs=[[[8]]], rules=rules, lang="en")
    q = Question("EN06", QTEXT, refs=[[[7]]], rules=rules, lang="en", revised=revised)
    respond, _ = _scripted("```sql\nSELECT 7\n```")
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 7": ExecResult(rows=[[7]])})), q, 1)
    assert rec["final"]["outcome"] == "correct" and rec["final"]["revised"]["outcome"] == "wrong"


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
    from harness.questions import load_questions, question_files
    zh, en = load_questions(EVAL), load_questions(EVAL, lang="en")
    assert len(en) == 99 and "EN33" not in {q.qid for q in en}
    records = {r["id"]: r for p in question_files(EVAL)
               for r in yaml.safe_load(p.read_text(encoding="utf-8"))["questions"]}
    assert {q.qid for q in zh} == set(records)
    for q in zh:
        rec = records[q.qid]
        assert q.text == rec["text_zh"] and len(q.refs) == len(rec["refs"])
        assert q.rules == rec["rules"]                                         # untouched
        own = [ref.get("rules") for ref in rec["refs"]]
        assert q.ref_rules == (own if any(r is not None for r in own) else None)
        assert q.scoring == rec["scoring"]
    # after the rules backfill only judge questions are pending among the 122
    assert {q.qid for q in zh if q.pending} == {qid for qid, r in records.items() if r["scoring"] == "judge"}


@needs_eval
def test_anchor_mapping_follows_the_english_text_not_the_numbering():
    import json as _json
    from harness.questions import anchor_mapping, load_zh, vendor_questions
    zh = {q.qid: q for q in load_zh(EVAL)}
    vendor = {int(v["id"]): v for v in vendor_questions(EVAL)}
    mapping = anchor_mapping(EVAL, list(zh.values()))
    assert set(mapping) == set(vendor) and len(set(mapping.values())) == len(mapping)
    for vid, qid in mapping.items():
        assert zh[qid].meta["text_en"].strip() == vendor[vid]["question"].strip()
    # robust to the bank's order: shuffling our questions changes nothing
    assert anchor_mapping(EVAL, list(reversed(list(zh.values())))) == mapping
    from harness.questions import REVISED_EXCLUDED, load_questions
    en = load_questions(EVAL, lang="en")
    assert sorted(q.meta["vendor_id"] for q in en) == sorted(set(vendor) - {33})
    # every excluded id is a real bank question with an anchor (a typo would silently exclude nothing)
    assert REVISED_EXCLUDED <= set(mapping.values())
    assert {q.meta["bank_qid"] for q in en if q.revised is None} == REVISED_EXCLUDED
    for q in en:   # EN id = benchmark id, and the revised column is the mapped bank question
        assert q.qid == f"EN{q.meta['vendor_id']:02d}" and q.meta["bank_qid"] == mapping[q.meta["vendor_id"]]
        if q.meta["bank_qid"] in REVISED_EXCLUDED:   # rewritten bank question: no revised column
            assert q.revised is None and q.meta["revised_excluded"]
            continue
        assert q.revised.refs == zh[q.meta["bank_qid"]].refs and q.revised.rules == zh[q.meta["bank_qid"]].rules


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


def test_anchor_rules_follow_column_structure():
    from harness.questions import anchor_rules
    r1 = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["count"], "value_types": ["UInt64"]}
    r2 = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["other", "amount"],
          "value_types": ["String", "Float64"]}
    current = Question("Q007", "", refs=[[[1]], [["a", 1.0]]], rules=r1, ref_rules=[None, r2])
    assert anchor_rules([{"name": "c", "type": "UInt64"}], [[5]], current) == (r1, None)
    assert anchor_rules([{"name": "a", "type": "String"}, {"name": "b", "type": "Float64"}], [["x", 2.0]], current)[0] is r2
    assert anchor_rules([{"name": "c", "type": "Int64"}], [[5]], current) == (None, "structure_differs")
    # §3.1: Nullable(...) is stripped before comparing
    assert anchor_rules([{"name": "c", "type": "Nullable(UInt64)"}], [[5]], current) == (r1, None)
    assert anchor_rules([{"name": "a", "type": "String"}, {"name": "b", "type": "Nullable(Float64)"}],
                        [["x", None]], current)[0] is r2
    # §3.2: an empty original reference is scored as empty only if the published artifact is empty too
    wide = [{"name": "a", "type": "String"}, {"name": "b", "type": "Float64"}, {"name": "c", "type": "Float64"}]
    assert anchor_rules(wide, [], current, published_rows=0) == (r1, None)
    assert anchor_rules(wide, [], current, published_rows=3)[0] is None
    assert anchor_rules(wide, [], current, published_rows=None)[0] is None
    # rules the question bank wrote for this original reference take precedence, still self-matched
    own = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["other"] * 3,
           "value_types": ["String", "Float64", "Float64"]}
    assert anchor_rules(wide, [["x", 1.0, 2.0]], current, original_rules=own) == (own, None)
    assert anchor_rules(wide, [["x", 1.0]], current, original_rules=own)[0] is None


def test_anchor_top_n_reference_is_boundary_complete():
    """§4.3: a truncated original reference is completed to the whole tie group; any N tied rows score."""
    from harness.anchor_refs import boundary_sql
    from harness.questions import anchor_rules
    assert boundary_sql("SELECT a FROM t ORDER BY a DESC LIMIT 10") == "SELECT a FROM t ORDER BY a DESC LIMIT 10 WITH TIES"
    assert boundary_sql("SELECT x LIMIT 3 WITH TIES") == "SELECT x LIMIT 3 WITH TIES"
    assert boundary_sql("SELECT ROW_NUMBER() OVER (ORDER BY s) AS rn") == "SELECT rank() OVER (ORDER BY s) AS rn"
    top = {"ordered": True, "top_n": 2, "tie_columns": [1], "value_kinds": ["other", "other"],
           "value_types": ["String", "Float64"], "order_by": [{"column": 1, "descending": True}]}
    tied = [["a", 9.0], ["b", 5.0], ["c", 5.0], ["d", 5.0]]
    current = Question("Q007", "", refs=[tied[:2]], rules=top)
    meta = [{"name": "n", "type": "String"}, {"name": "v", "type": "Float64"}]
    # the whole tie group is not a valid answer (scorer contract), so self-match uses N rows of it
    assert anchor_rules(meta, tied, current)[0] is None
    assert anchor_rules(meta, tied, current, pick=tied[:2]) == (top, None)
    from harness.scorer import score_detailed
    assert score_detailed([["a", 9.0], ["d", 5.0]], [tied], top).outcome == "correct"


def test_bank_anchor_rules_are_read_by_id_and_hash(tmp_path):
    from harness.questions import ANCHOR_RULES, bank_anchor_rules
    rules = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["other"], "value_types": ["Int32"]}
    sql, payload = "a" * 64, "b" * 64
    (tmp_path / ANCHOR_RULES).parent.mkdir(parents=True)
    (tmp_path / ANCHOR_RULES).write_text(
        "# x\n\n| t |\n\n## EN07\n\n"
        f"原始SQL SHA256：`{sql}`；payload SHA256：`{payload}`。\n\n```json\n{json.dumps(rules, indent=2)}\n```\n",
        encoding="utf-8")
    assert bank_anchor_rules(tmp_path) == {7: {"sql_sha256": sql, "sha256": payload, "rules": rules}}
    assert bank_anchor_rules(tmp_path / "missing") == {}


@needs_eval
def test_anchor_details_on_the_real_bank():
    """decisions/2026-10-16-q79-release-and-anchor-refs.md §3 on the real anchors."""
    from harness.anchor_refs import anchor_dir
    from harness.questions import load_questions, load_zh, published_row_count
    if not (anchor_dir() / "MANIFEST.json").exists():
        pytest.skip("anchor references not built")
    zh = {q.qid: q for q in load_zh(EVAL)}
    en = {q.qid: q for q in load_questions(EVAL, lang="en")}
    for qid in ("EN84", "EN100"):           # differ from the current refs only by Nullable(...)
        assert en[qid].pending is None and en[qid].rules == zh[en[qid].meta["bank_qid"]].rules
    for qid in ("EN39", "EN49"):            # empty locally and in the published artifact
        assert en[qid].refs == [[]] and en[qid].meta["empty_original_ref"]
        assert published_row_count(EVAL, en[qid].meta["vendor_id"]) == 0
        assert en[qid].rules == zh[en[qid].meta["bank_qid"]].rules
    assert en["EN49"].pending is None and en["EN39"].pending == "judge"


@needs_eval
def test_anchor_rules_from_the_bank_and_boundary_on_the_real_bank():
    """Eval PR #12 rules for the 8 structure-differing anchors; §4.3 boundary for EN79."""
    import random
    from harness.anchor_refs import anchor_dir, anchor_manifest
    from harness.questions import bank_anchor_rules, load_questions
    from harness.scorer import score_detailed
    if not (anchor_dir() / "MANIFEST.json").exists():
        pytest.skip("anchor references not built")
    written = bank_anchor_rules(EVAL)
    if not written:
        pytest.skip("question bank predates the original-anchor rules (eval PR #12)")
    en = {q.qid: q for q in load_questions(EVAL, lang="en")}
    built = anchor_manifest()
    for vid, entry in written.items():          # picked by id, checked against both hashes, used whole
        q = en[f"EN{vid:02d}"]
        assert (entry["sql_sha256"], entry["sha256"]) == (built[vid]["sql_sha256"], built[vid]["sha256"])
        assert q.pending is None and q.rules == entry["rules"]
    assert all(q.pending in (None, "judge") for q in en.values())
    q79 = en["EN79"]                            # 306 stores tie at the boundary; any 10 of them score
    assert q79.meta["boundary_completed"]["original_rows"] == 10 and len(q79.refs[0]) > 10
    pick = random.Random(0).sample(q79.refs[0], 10)
    assert score_detailed(pick, q79.refs, q79.rules).outcome == "correct"
    assert score_detailed(q79.refs[0][:11], q79.refs, q79.rules).outcome == "wrong"


@needs_eval
def test_ordered_anchors_declare_their_sort_key():
    """Scorer since main #52: ordered rules without order_by warn and fall back to positional
    comparison. Every ordered anchor must carry a key, so loading and self-matching never raise
    that warning. Only that warning is an error: other scorer warnings (e.g. missing
    required_columns before eval-v1.1) are not this test's concern."""
    import warnings
    from harness.anchor_refs import anchor_dir, load_anchor_ref
    from harness.questions import load_questions
    from harness.scorer import score_detailed
    if not (anchor_dir() / "MANIFEST.json").exists():
        pytest.skip("anchor references not built")
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message="ordered rules missing order_by", category=RuntimeWarning)
        en = load_questions(EVAL, lang="en")
        for q in en:
            if q.rules is None or not q.rules.get("ordered"):
                continue
            assert q.rules.get("order_by") or (q.rules.get("selection") or {}).get("output_order"), q.qid
            pick = load_anchor_ref(q.meta["vendor_id"])[1] if q.meta.get("boundary_completed") else q.refs[0]
            assert score_detailed(pick, q.refs, q.rules).outcome == "correct", q.qid


def test_rescore_rebuilds_candidates_from_runs_raw(tmp_path):
    """Offline re-scoring: no model call, candidates from runs-raw, new run dir, sha checked."""
    from harness import rescore as RS
    q_old = Question("Q008", QTEXT, refs=[[[42]]], rules=None)                 # pending: no rules yet
    respond, _ = _scripted("```sql\nSELECT 42\n```")
    ctx = _ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])}))
    ctx.raw_dir = tmp_path / "raw" / "src" / "SQL-L1"
    ctx.run_id = "src"
    R.run_cell(ctx, [q_old], reps=1, concurrency=1, runs_root=tmp_path / "runs", progress=lambda *_: None)
    q_new = Question("Q008", QTEXT, refs=[[[42]]], rules=Q.rules)
    path = RS.rescore("src", "SQL-L1", "src-rescore", runs_root=tmp_path / "runs", raw_root=tmp_path / "raw",
                      questions={"Q008": q_new}, commit="evalnew")
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["final"]["outcome"] == "correct" and rec["rescored_from"]["final"]["outcome"] == "pending"
    assert rec["run_id"] == "src-rescore" and rec["eval_commit"] == "evalnew" and rec["cost_cny"] == 0.0
    with pytest.raises(SystemExit):              # append-only: never overwrite a run directory
        RS.rescore("src", "SQL-L1", "src-rescore", runs_root=tmp_path / "runs", raw_root=tmp_path / "raw",
                   questions={"Q008": q_new}, commit="evalnew")
    changed = Question("Q008", QTEXT + "改", refs=[[[42]]], rules=Q.rules)
    with pytest.raises(ValueError):              # the answer belongs to a different question now
        RS.rescore("src", "SQL-L1", "src-rescore-2", runs_root=tmp_path / "runs", raw_root=tmp_path / "raw",
                   questions={"Q008": changed}, commit="evalnew")
    raw = tmp_path / "raw" / "src" / "SQL-L1" / "Q008_r1_t0.exec.json"
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(ValueError):              # tampered raw result
        RS.rescore("src", "SQL-L1", "src-rescore-3", runs_root=tmp_path / "runs", raw_root=tmp_path / "raw",
                   questions={"Q008": q_new}, commit="evalnew")


def _rescore_source(tmp_path):
    """One finished source run "src" (Q008 answered SELECT 42) and its runs-raw."""
    respond, _ = _scripted("```sql\nSELECT 42\n```")
    ctx = _ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])}))
    ctx.raw_dir = tmp_path / "raw" / "src" / "SQL-L1"
    ctx.run_id = "src"
    R.run_cell(ctx, [Question("Q008", QTEXT, refs=[[[42]]], rules=Q.rules)], reps=1, concurrency=1,
               runs_root=tmp_path / "runs", progress=lambda *_: None)
    return Question("Q008", QTEXT + "改", refs=[[[42]]], rules=Q.rules)      # the wording changed since


def test_rescore_refuses_a_changed_question_by_default(tmp_path):
    from harness import rescore as RS
    changed = _rescore_source(tmp_path)
    with pytest.raises(ValueError, match="question text changed"):
        RS.rescore("src", "SQL-L1", "src-rescore", runs_root=tmp_path / "runs", raw_root=tmp_path / "raw",
                   questions={"Q008": changed}, commit="evalnew")
    assert not (tmp_path / "runs" / "src-rescore").exists()
    import inspect                               # off unless the caller opts in (CLI: --allow-changed-question)
    assert inspect.signature(RS.rescore).parameters["allow_changed"].default is False


def test_rescore_scores_a_changed_question_only_when_allowed_and_marks_it(tmp_path):
    from harness import rescore as RS
    changed = _rescore_source(tmp_path)
    path = RS.rescore("src", "SQL-L1", "src-rescore", runs_root=tmp_path / "runs", raw_root=tmp_path / "raw",
                      questions={"Q008": changed}, commit="evalnew", allow_changed=True)
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["question_changed"] is True
    assert rec["final"]["outcome"] == "correct" and rec["first"] == "correct"
    assert rec["question_sha256"] == R.sha256(QTEXT)  # the line keeps the wording it answered
    unchanged = RS.rescore("src", "SQL-L1", "src-rescore-2", runs_root=tmp_path / "runs",
                           raw_root=tmp_path / "raw", questions={"Q008": Question("Q008", QTEXT, refs=[[[42]]],
                                                                                  rules=Q.rules)},
                           commit="evalnew", allow_changed=True)
    assert "question_changed" not in json.loads(unchanged.read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# T12: fingerprint guard, fixed bank tag, pilot sample


def _questions(n):
    return [Question(f"Q{i:03d}", QTEXT, refs=[[[42]]], rules=Q.rules) for i in range(1, n + 1)]


def test_second_fingerprint_stops_the_run(tmp_path):
    """After the fingerprint changes, attempts not yet started are not launched."""
    client = MockClient(lambda m: "```sql\nSELECT 42\n```", fingerprint="fp_a")
    seen = []

    def respond(messages):
        seen.append(1)
        if len(seen) == 3:
            client.fingerprint = "fp_b"
        return "```sql\nSELECT 42\n```"

    client.respond = respond
    ex = FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])})
    guard = R.FingerprintGuard()
    path = R.run_cell(_ctx(tmp_path, client, ex), _questions(10), reps=1, concurrency=1,
                      runs_root=tmp_path / "runs", progress=lambda *_: None, guard=guard)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert guard.conflict and set(guard.seen) == {"fp_a", "fp_b"}
    assert len(lines) < 10                      # stopped early; what ran is logged
    assert len(lines) == len(seen)


def test_fingerprint_guard_is_seeded_from_the_run_on_resume(tmp_path):
    client = MockClient(lambda m: "```sql\nSELECT 42\n```", fingerprint="fp_a")
    ex = FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])})
    R.run_cell(_ctx(tmp_path, client, ex), _questions(2), reps=1, concurrency=1,
               runs_root=tmp_path / "runs", progress=lambda *_: None)
    guard = R.FingerprintGuard.from_logs(tmp_path / "runs" / "test-run", "mock")
    assert guard.seen == {"fp_a": 2} and not guard.conflict
    assert R.FingerprintGuard.from_logs(tmp_path / "runs" / "test-run", "other").seen == {}


def test_first_attempt_runs_alone_before_the_pool(tmp_path):
    """The first call writes the prefix cache before concurrent calls start."""
    import threading

    order = []
    gate = threading.Event()

    def respond(messages):
        order.append(gate.is_set())
        gate.set()
        return "```sql\nSELECT 42\n```"

    ex = FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])})
    R.run_cell(_ctx(tmp_path, MockClient(respond), ex), _questions(5), reps=1, concurrency=4,
               runs_root=tmp_path / "runs", progress=lambda *_: None)
    assert order[0] is False and all(order[1:])


def _git_repo(root: Path) -> None:
    import subprocess

    def git(*a):
        subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True)
    (root / "questions").mkdir(parents=True)
    (root / "questions" / "a.yaml").write_text("questions: []\n", encoding="utf-8")
    (root / "questions" / "pilot.yaml").write_text("seed: 1\nquestions: [Q2, Q1]\n", encoding="utf-8")
    git("init", "-q")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "x", "--allow-empty")
    git("add", ".")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "bank")
    git("tag", "eval-v1")


def test_bank_must_be_the_clean_tag(tmp_path):
    import subprocess

    from harness.questions import EvalVersionError, pilot_ids, question_files, verify_eval_tag

    root = tmp_path / "bank"
    _git_repo(root)
    full = verify_eval_tag("eval-v1", root)
    assert len(full) == 40
    assert pilot_ids(root) == ["Q2", "Q1"]
    assert [p.name for p in question_files(root)] == ["a.yaml"]    # the pilot list is not a question file
    with pytest.raises(EvalVersionError, match="not found"):
        verify_eval_tag("eval-v9", root)
    (root / "questions" / "a.yaml").write_text("questions: [x]\n", encoding="utf-8")
    with pytest.raises(EvalVersionError, match="local changes"):
        verify_eval_tag("eval-v1", root)
    subprocess.run(["git", "-C", str(root), "checkout", "-q", "--", "."], check=True)
    (root / "questions" / "new.yaml").write_text("questions: []\n", encoding="utf-8")
    with pytest.raises(EvalVersionError, match="local changes"):
        verify_eval_tag("eval-v1", root)
    (root / "questions" / "new.yaml").unlink()
    subprocess.run(["git", "-C", str(root), "checkout", "-q", "HEAD~1"], check=True)
    with pytest.raises(EvalVersionError, match="is not eval-v1"):
        verify_eval_tag("eval-v1", root)


def test_semantic_layer_must_be_the_tag_content(tmp_path):
    """--semantic-tag: semantic/ and render/ equal the tag's tree (HEAD may move on), contexts fresh."""
    import subprocess

    from harness.semantic_version import SemanticVersionError, verify_semantic_tag

    root = tmp_path / "repo"

    def git(*a):
        subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *a],
                       check=True, capture_output=True)
    for rel, text in {"semantic/source.yaml": "a: 1\n", "render/context.py": "x = 1\n", "harness/h.py": "h = 1\n"}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    git("init", "-q")
    git("add", ".")
    git("commit", "-qm", "v")
    git("tag", "semantic-v9")
    contexts = root / "build" / "contexts"
    contexts.mkdir(parents=True)
    (contexts / "SQL-L1.yaml").write_text("ctx a=1\n", encoding="utf-8")
    render = lambda name: "ctx a=1\n" if name == "SQL-L1" else ""   # noqa: E731
    check = lambda: verify_semantic_tag("semantic-v9", ["SQL-L1.yaml"], root=root, contexts_dir=contexts,  # noqa: E731
                                        render=render)

    full = check()
    assert len(full) == 40
    (root / "harness" / "h.py").write_text("h = 2\n", encoding="utf-8")      # harness work after the tag is fine
    git("commit", "-qam", "harness")
    assert check() == full
    with pytest.raises(SemanticVersionError, match="not found"):
        verify_semantic_tag("semantic-v8", [], root=root, contexts_dir=contexts, render=render)
    (root / "semantic" / "source.yaml").write_text("a: 2\n", encoding="utf-8")   # unstaged edit
    with pytest.raises(SemanticVersionError, match="differ from semantic-v9"):
        check()
    git("commit", "-qam", "edit semantic after the tag")                      # committed edit
    with pytest.raises(SemanticVersionError, match="semantic/source.yaml"):
        check()
    git("revert", "--no-edit", "HEAD")
    assert check() == full
    (root / "render" / "new.py").write_text("", encoding="utf-8")             # untracked renderer file
    with pytest.raises(SemanticVersionError, match="render/new.py"):
        check()
    (root / "render" / "new.py").unlink()
    (contexts / "SQL-L1.yaml").write_text("ctx a=0\n", encoding="utf-8")        # stale build
    with pytest.raises(SemanticVersionError, match="stale"):
        check()
    (contexts / "SQL-L1.yaml").unlink()
    assert check() == full      # not built: left to system_for (the dry run shows "no context")


def test_semantic_tag_is_checked_against_this_repo():
    """The real repo: rendering is deterministic, and semantic-v1.1 is not the current content (v1.2 changed it)."""
    import subprocess

    from harness.cells import CONTEXTS, REPO
    from harness.semantic_version import SemanticVersionError, render_context, verify_semantic_tag

    assert render_context("SQL-R") == render_context("SQL-R")
    has = subprocess.run(["git", "-C", str(REPO), "rev-parse", "-q", "--verify", "refs/tags/semantic-v1.1"],
                         capture_output=True).returncode == 0
    if not has:
        pytest.skip("tag semantic-v1.1 not fetched")
    with pytest.raises(SemanticVersionError, match="differ from semantic-v1.1"):
        verify_semantic_tag("semantic-v1.1", [], root=REPO, contexts_dir=CONTEXTS)


def test_final_rescore_swaps_a_key_only_for_its_own_entity_name():
    """T12 final rescore: a key stands in for the name of the same entity, never for
    another entity's name (swapping a selection group column made the scorer search
    without end); dropping convention columns also drops their rank rules."""
    from scripts.t12_final_rescore import key_variants, without
    header = ["StoreName", "ProductName", "product_sales", "pct_of_store", "ProductKey", "store_total_sales", "rank"]
    rules = {"ordered": False, "top_n": None, "required_columns": [0, 1, 3, 5, 6], "identifier_columns": [4],
             "value_kinds": ["other", "other", "amount", "percentage", "other", "amount", "other"],
             "value_types": ["String", "Nullable(String)", "Float64", "Nullable(Float64)", "Int32", "Float64", "UInt64"],
             "rank_columns": [6], "rankings": [{"column": 6}]}
    assert [v["required_columns"] for v in key_variants(rules, header)] == [[0, 4, 3, 5, 6]]
    relaxed = without(rules, [5, 6])
    assert relaxed["required_columns"] == [0, 1, 3] and "rank_columns" not in relaxed and "rankings" not in relaxed
    assert without(rules, []) is rules
    assert key_variants({**rules, "identifier_columns": [0]}, ["t.StoreKey", "StoreName", "x", "y", "z", "w", "v"]) == []
