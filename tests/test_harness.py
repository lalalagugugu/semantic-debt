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
from harness.scorer_v2 import ExecError  # noqa: E402

CHDB = Path(os.environ.get("SEMDEBT_DATA_DIR", "/nonexistent")).expanduser() / "chdb"
needs_chdb = pytest.mark.skipif(not CHDB.exists(), reason="chDB data directory not available")


# ---------------------------------------------------------------------------
# prompt


@pytest.mark.parametrize("path", ["harness/prompt.py", "harness/scorer.py"])
@pytest.mark.parametrize("baseline", [
    "84f5e045dc9d3456c11c4453515c746047a69c74",  # experiment baseline, including PR #100
    "88fd81c9d743ef93d1e00f65c7f5f8faa95d72ec",  # main at PR preparation, including T15
    "89ce1b31b22e009b726448ff23fe0f55d5a26a80",  # main at interface-audit delivery
])
def test_t16_frozen_files_match_main_byte_for_byte(path, baseline):
    import subprocess

    expected = subprocess.check_output(["git", "show", f"{baseline}:{path}"], cwd=REPO)
    actual = (REPO / path).read_bytes()
    assert actual == expected, f"{path} differs from experiment main {baseline}"


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


def test_tuned_instruction_patch_extends_the_frozen_prompt(tmp_path):
    """T14 second unit: requirements numbered on after item 15, notes after the syntax notes, why not sent."""
    from harness import tuned_instructions as TI

    path = tmp_path / "X.instructions.yaml"
    path.write_text("answer_requirements:\n  - {id: O1, text: \"要求甲\", why: \"理由甲\"}\n"
                    "  - {id: S5-out, text: \"要求\\n乙\"}\nsyntax_notes:\n  - {id: P1, text: \"写法丙（见 O1）\"}\n",
                    encoding="utf-8")
    system = TI.system_message("CTX-BODY", "SYNTAX-BODY\n", "yaml", TI.load(path))
    plain = P.system_message("CTX-BODY", "SYNTAX-BODY\n", "yaml")
    assert system.startswith(P.SYSTEM_PROMPT + "\n16. （O1）要求甲\n17. （S5-out）要求 乙\n\n")
    assert system.endswith("SYNTAX-BODY\n- （P1）写法丙（见 O1）\n")
    assert "理由甲" not in system
    # removing the inserted lines gives the frozen message back
    assert system.replace("\n16. （O1）要求甲\n17. （S5-out）要求 乙", "").replace("\n- （P1）写法丙（见 O1）", "") == plain


@pytest.mark.parametrize("text", ["answer_requirements: [{id: O1}]\n", "rules: []\n",
                                  "syntax_notes: [{id: P1, text: a, from: Q1}]\n"])
def test_tuned_instruction_patch_rejects_other_shapes(tmp_path, text):
    from harness import tuned_instructions as TI

    path = tmp_path / "X.instructions.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        TI.load(path)


def test_tuned_instr_cell_shares_the_tuned_context():
    a, b = CELLS["SQL-L1-tuned"], CELLS["SQL-L1-tuned-instr"]
    assert (a.context, a.syntax, a.allowed, a.instructions) == (b.context, b.syntax, b.allowed, None)
    assert b.instructions == "SQL-L1"
    if not (REPO / "build" / "contexts" / "SQL-L1-tuned.yaml").exists():
        pytest.skip("contexts not rendered")
    if (REPO / "semantic" / "tuning" / "SQL-L1.instructions.yaml").exists():
        tuned, instr = R.system_for(a), R.system_for(b)
        assert len(instr) > len(tuned) and instr.startswith(P.SYSTEM_PROMPT + "\n16. ")


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
                                                    "value_kinds": ["count"], "value_types": ["UInt64"],
                                                    "required_columns": [0]})


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


@pytest.mark.parametrize("fingerprints", [("unexpected",), (None,), ("expected", "unexpected")])
def test_t16_stops_on_each_call_fingerprint(tmp_path, monkeypatch, fingerprints):
    monkeypatch.setattr(R, "is_peak", lambda *a: False)
    client = MockClient(lambda m: "```sql\nSELECT bad\n```", fingerprint=fingerprints[0])
    calls = []

    def respond(messages):
        client.fingerprint = fingerprints[len(calls)]
        calls.append(messages)
        return "```sql\nSELECT bad\n```"

    client.respond = respond
    ex = FakeExecutor({})
    ctx = _ctx(tmp_path, client, ex)
    ctx.boundary = R.CallBoundary("expected")
    rec = R.run_attempt(ctx, Q, 1)
    assert rec["status"] == "stopped" and ctx.boundary.stopped.is_set()
    assert len(calls) == len(fingerprints) and len(ex.seen) == len(fingerprints) - 1
    assert rec["turns"][-1]["exec"]["status"] == "not_executed"
    raw = ctx.raw_dir / f"{Q.qid}_r1_t{len(calls) - 1}.json"
    assert R.sha256(raw.read_bytes()) == rec["turns"][-1]["raw_sha256"]
    R.run_attempt(ctx, Q, 2)
    assert len(calls) == len(fingerprints)


def test_t16_peak_boundary_blocks_fix_call(tmp_path, monkeypatch):
    peak = [False]
    monkeypatch.setattr(R, "is_peak", lambda *a: peak[0])
    calls = []

    def respond(messages):
        calls.append(messages)
        peak[0] = True
        return "```sql\nSELECT bad\n```"

    ctx = _ctx(tmp_path, MockClient(respond), FakeExecutor({}))
    ctx.boundary = R.CallBoundary("fp_mock")
    rec = R.run_attempt(ctx, Q, 1)
    assert rec["status"] == "stopped" and len(calls) == 1
    assert ctx.boundary.stopped.is_set() and len(rec["turns"]) == 1


def test_t16_both_cube_factories_and_json_flow(tmp_path):
    from harness.executors import CubeSqlExecutor, CubeJsonExecutor
    assert isinstance(R.make_executor(CELLS["SQL-L2"], 7), CubeSqlExecutor)
    assert isinstance(R.make_executor(CELLS["JSON-L2"], 7), CubeJsonExecutor)
    query = '{"measures": ["sales.sales_amount"]}'
    ex = FakeExecutor({query: ExecResult(rows=[[42]], columns=["sales.sales_amount"])})
    ctx = _ctx(tmp_path, MockClient(lambda m: f"```json\n{query}\n```"), ex, "JSON-L2")
    rec = R.run_attempt(ctx, Q, 1)
    assert ex.seen == [query] and rec["final"]["outcome"] == "correct"
    assert json.loads((ctx.raw_dir / f"{Q.qid}_r1_t0.exec.json").read_text())["rows"] == [[42]]


def test_t16_request_boundary_also_checks_transport_retries(monkeypatch):
    from harness import client as C
    monkeypatch.setenv("DEEPSEEK_API_KEY", "offline-test-placeholder")
    monkeypatch.setattr(C.time, "sleep", lambda _: None)
    requests = []

    def fail(*a, **kw):
        requests.append(1)
        raise OSError("offline")

    monkeypatch.setattr(C.urllib.request, "urlopen", fail)
    checks = []

    def boundary():
        checks.append(1)
        if len(checks) == 2:
            raise R.RunStopped("peak hours")

    client = C.DeepSeekClient("deepseek-flash", before_request=boundary)
    with pytest.raises(R.RunStopped, match="peak hours"):
        client.chat([])
    assert len(checks) == 2 and len(requests) == 1


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
    real_guarded = R.score_with_timeout

    def spy_guarded(candidate, refs, rules, **kw):   # the time-limited path pickles them into a child process
        seen.append((rules, kw.get("reference_rules")))
        return real_guarded(candidate, refs, rules, **kw)
    monkeypatch.setattr(R, "score_detailed", spy)
    monkeypatch.setattr(R, "score_with_timeout", spy_guarded)
    respond, _ = _scripted("```sql\nSELECT 42\n```")
    R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])})), Q, 1)
    assert seen and all(r is Q.rules and rr is None for r, rr in seen)


def test_per_reference_rules_are_passed_through_untouched(tmp_path, monkeypatch):
    """decisions/2026-10-16-per-reference-rules.md: a ref's own rules replace the
    question's wholesale; the harness hands both to the scorer as they are."""
    one = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["count"], "value_types": ["UInt64"],
           "required_columns": [0]}
    two = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["other", "count"],
           "value_types": ["String", "UInt64"], "required_columns": [0, 1]}
    q = Question("Q005", QTEXT, refs=[[[8]], [["a", 7]]], rules=one, ref_rules=[None, two])
    seen = []
    real = R.score_detailed

    def spy(candidate, refs, rules, **kw):
        seen.append((rules, kw.get("reference_rules")))
        return real(candidate, refs, rules, **kw)
    real_guarded = R.score_with_timeout

    def spy_guarded(candidate, refs, rules, **kw):
        seen.append((rules, kw.get("reference_rules")))
        return real_guarded(candidate, refs, rules, **kw)
    monkeypatch.setattr(R, "score_detailed", spy)
    monkeypatch.setattr(R, "score_with_timeout", spy_guarded)
    respond, _ = _scripted("```sql\nSELECT 'a', 7\n```")
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 'a', 7": ExecResult(rows=[["a", 7]])})), q, 1)
    assert rec["final"]["outcome"] == "correct" and rec["final"]["matched_ref"] == 1
    assert seen and all(r is one and rr is q.ref_rules for r, rr in seen)


def test_anchor_carries_the_revised_column(tmp_path):
    rules = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["count"], "value_types": ["UInt64"],
             "required_columns": [0]}
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
    questions = [Question(f"Q{i:03d}", f"{QTEXT}{i}", [[[i]]], Q.rules) for i in range(1, 4)]
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
    assert "| SQL 直答 | L1 调优、L1 调优 + 指令（2026-10-23 裁决拆成两个单元） | T14 |" in board
    assert "| 英文锚点 | R-EN、L1c-EN" in board
    expected = {"SQL-L0", "SQL-R", "SQL-L1", "SQL-L1c", "SQL-L1.5W", "SQL-L1.5S", "SQL-L1-tuned", "SQL-L1-tuned-instr",
                "SQL-L2", "SQL-R-EN", "SQL-L1c-EN", "JSON-L2"}
    assert set(CELLS) == expected
    try:
        rows, total = R.dry_run(list(CELLS.values()), {"zh": 122, "en": 99}, 3, "deepseek-flash", fix_rate=0.1,
                                output_tokens=3000, hit_ratio=0.95, question_tokens=60, runs_root=tmp_path)
    except (PermissionError, FileNotFoundError):
        pytest.skip("required question bank or syntax note is unavailable")
    by = {r["cell"]: r for r in rows}
    assert by["SQL-L1"]["attempts"] == 366 and by["SQL-L1"]["calls"] == round(366 * 1.1)
    assert by["SQL-R-EN"]["attempts"] == 297
    assert sum(r["attempts"] for r in rows) == 10 * 366 + 2 * 297
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
    judge = Question("Q003", QTEXT, refs=[[[1]]], rules=Q.rules, scoring="judge")
    respond, _ = _scripted("CANNOT_ANSWER")
    rec = R.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({})), judge, 1)
    assert rec["final"]["outcome"] == "refused" and rec["scoring"] == "judge"


# ---------------------------------------------------------------------------
# the real question bank and the external contexts

EVAL = Path(os.environ.get("SEMDEBT_EVAL_DIR", "/nonexistent")).expanduser()
def _eval_readable() -> bool:
    # 盲模式下题库目录能 stat 但读不了：要真去列一次，读不了就跳过，免得测试报错把题面带进输出
    try:
        next((EVAL / "questions").iterdir(), None)
        return True
    except OSError:
        return False


needs_eval = pytest.mark.skipif(not _eval_readable(), reason="question bank not available")


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
    # rules from before required_columns meant every column required; v2 needs it written out
    r1x, r2x = {**r1, "required_columns": [0]}, {**r2, "required_columns": [0, 1]}
    assert anchor_rules([{"name": "c", "type": "UInt64"}], [[5]], current) == (r1x, None)
    assert anchor_rules([{"name": "a", "type": "String"}, {"name": "b", "type": "Float64"}], [["x", 2.0]], current)[0] == r2x
    assert anchor_rules([{"name": "c", "type": "Int64"}], [[5]], current) == (None, "structure_differs")
    # §3.1: Nullable(...) is stripped before comparing
    assert anchor_rules([{"name": "c", "type": "Nullable(UInt64)"}], [[5]], current) == (r1x, None)
    assert anchor_rules([{"name": "a", "type": "String"}, {"name": "b", "type": "Nullable(Float64)"}],
                        [["x", None]], current)[0] == r2x
    # §3.2: an empty original reference is scored as empty only if the published artifact is empty too
    wide = [{"name": "a", "type": "String"}, {"name": "b", "type": "Float64"}, {"name": "c", "type": "Float64"}]
    assert anchor_rules(wide, [], current, published_rows=0) == (r1x, None)
    assert anchor_rules(wide, [], current, published_rows=3)[0] is None
    assert anchor_rules(wide, [], current, published_rows=None)[0] is None
    # rules the question bank wrote for this original reference take precedence, still self-matched
    own = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["other"] * 3,
           "value_types": ["String", "Float64", "Float64"]}
    assert anchor_rules(wide, [["x", 1.0, 2.0]], current, original_rules=own) == ({**own, "required_columns": [0, 1, 2]}, None)
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
    assert anchor_rules(meta, tied, current, pick=tied[:2]) == ({**top, "required_columns": [0, 1]}, None)
    from harness.scorer_v2 import score_detailed
    top = {**top, "required_columns": [0, 1]}
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
def test_rewritten_bank_questions_drop_the_revised_column():
    """The 12 rewritten bank questions: semantic-gaps-and-realistic-questions §3, §5–7 (6) and
    ux-conventions-and-annotation-disputes §4 item 4 (Q45, Q67, Q69, Q92, Q97, Q98). Their
    anchors are still scored on the original reference; only the revised column is dropped."""
    from harness.anchor_refs import anchor_dir
    from harness.questions import REVISED_EXCLUDED, load_questions
    want = {"Q13", "Q14", "Q21", "Q28", "Q36", "Q89", "Q45", "Q67", "Q69", "Q92", "Q97", "Q98"}
    assert REVISED_EXCLUDED == want
    if not (anchor_dir() / "MANIFEST.json").exists():
        pytest.skip("anchor references not built")
    en = load_questions(EVAL, lang="en")
    dropped = {q.meta["bank_qid"]: q for q in en if q.revised is None}
    assert set(dropped) == want
    assert all(q.meta["revised_excluded"] == "bank question rewritten" for q in dropped.values())


def _all_required(rules):
    """Pre-required_columns rules as the loader hands them to scorer v2: every column required."""
    return rules if "required_columns" in rules else {**rules, "required_columns": list(range(len(rules["value_types"])))}


# Anchors whose original reference scorer v2 cannot match to itself, so they lose their rules
# (pending either way): EN44 is a judge question and its original reference holds inf (growth
# from a zero base); v2 never treats a non-finite value as equal, even to itself.
V2_SELF_MATCH_EXCEPTIONS = {"EN44"}


@needs_eval
def test_anchors_score_exactly_as_at_eval_v1_whatever_the_current_bank():
    """Anchors inherit the Chinese rules from the fixed tag (default eval-v1), never from the
    current checkout: the 87 scorable anchors, their effective rules, boundary completion and
    pending set are the same as with the eval-v1 bank (snapshot from the loader before the
    change), on eval-v1 or eval-v1.1. Those rules have no required_columns, i.e. every column
    is required; since harness-v1.1 (scorer v2 needs the field) the loader writes that out as
    every column, and nothing else changes."""
    import hashlib
    from harness.anchor_refs import anchor_dir
    from harness.questions import bank_anchor_rules, load_questions
    if not (anchor_dir() / "MANIFEST.json").exists():
        pytest.skip("anchor references not built")
    snap = json.loads((Path(__file__).parent / "anchor_rules_eval_v1.json").read_text(encoding="utf-8"))
    en = {q.qid: q for q in load_questions(EVAL, lang="en")}
    assert set(en) == set(snap["anchors"])
    assert sum(q.pending is None for q in en.values()) == snap["scorable"] == 87
    tag = _git_rev(EVAL, "eval-v1")
    written = bank_anchor_rules(EVAL)
    for qid, q in en.items():
        want = snap["anchors"][qid]
        before = None
        if qid in V2_SELF_MATCH_EXCEPTIONS:
            assert q.pending == want["pending"] == "judge" and q.rules is None, qid
            continue
        if q.rules:
            assert q.rules["required_columns"] == list(range(len(q.rules["value_types"]))), qid
            before = {k: v for k, v in q.rules.items() if k != "required_columns"}
        digest = hashlib.sha256(json.dumps(before, sort_keys=True, ensure_ascii=False).encode()).hexdigest() if before else None
        assert (q.pending, digest, bool(q.meta.get("boundary_completed"))) == \
            (want["pending"], want["rules_sha256"], want["boundary_completed"]), qid
        assert q.meta["rules_tag"] == {"tag": "eval-v1", "commit": tag}
        if q.meta.get("rules_source"):         # the bank's own rules for original references: current checkout
            assert before == written[q.meta["vendor_id"]]["rules"]


def _git_rev(root, tag):
    import subprocess
    return subprocess.run(["git", "-C", str(root), "rev-parse", f"{tag}^{{commit}}"],
                          capture_output=True, text=True, check=True).stdout.strip()


@needs_eval
def test_anchor_rules_tag_is_explicit_and_never_falls_back():
    from harness.anchor_refs import anchor_dir
    from harness.questions import EvalVersionError, load_questions, zh_rules_at
    with pytest.raises(EvalVersionError, match="never inherit rules from the current checkout"):
        zh_rules_at(EVAL, "no-such-tag")
    if not (anchor_dir() / "MANIFEST.json").exists():
        pytest.skip("anchor references not built")
    with pytest.raises(EvalVersionError):
        load_questions(EVAL, lang="en", anchor_rules_tag="no-such-tag")
    rules, commit = zh_rules_at(EVAL, "eval-v1")
    assert commit == _git_rev(EVAL, "eval-v1") and "Q01" in rules and all(q.text == "" for q in rules.values())


def test_anchor_log_lines_carry_the_rules_tag(tmp_path):
    respond, _ = _scripted("```sql\nSELECT 42\n```")
    ctx = _ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])}))
    tag = {"tag": "eval-v1", "commit": "07dca9a" + "0" * 33}
    anchor = Question("EN08", QTEXT, refs=[[[42]]], rules=Q.rules, lang="en", meta={"rules_tag": tag})
    assert R.run_attempt(ctx, anchor, 1)["anchor_rules"] == tag
    respond, _ = _scripted("```sql\nSELECT 42\n```")
    ctx = _ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])}))
    assert "anchor_rules" not in R.run_attempt(ctx, Question("Q008", QTEXT, refs=[[[42]]], rules=Q.rules), 1)


@needs_eval
def test_anchor_details_on_the_real_bank():
    """decisions/2026-10-16-q79-release-and-anchor-refs.md §3 on the real anchors; the Chinese
    rules they inherit are those of the anchor rules tag (eval-v1), not of the current checkout."""
    from harness.anchor_refs import anchor_dir
    from harness.questions import load_questions, published_row_count, zh_rules_at
    if not (anchor_dir() / "MANIFEST.json").exists():
        pytest.skip("anchor references not built")
    zh, _ = zh_rules_at(EVAL, "eval-v1")
    en = {q.qid: q for q in load_questions(EVAL, lang="en")}
    for qid in ("EN84", "EN100"):           # differ from the eval-v1 refs only by Nullable(...)
        assert en[qid].pending is None and en[qid].rules == _all_required(zh[en[qid].meta["bank_qid"]].rules)
    for qid in ("EN39", "EN49"):            # empty locally and in the published artifact
        assert en[qid].refs == [[]] and en[qid].meta["empty_original_ref"]
        assert published_row_count(EVAL, en[qid].meta["vendor_id"]) == 0
        assert en[qid].rules == _all_required(zh[en[qid].meta["bank_qid"]].rules)
    assert en["EN49"].pending is None and en["EN39"].pending == "judge"


@needs_eval
def test_anchor_rules_from_the_bank_and_boundary_on_the_real_bank():
    """Eval PR #12 rules for the 8 structure-differing anchors; §4.3 boundary for EN79."""
    import random
    from harness.anchor_refs import anchor_dir, anchor_manifest
    from harness.questions import bank_anchor_rules, load_questions
    from harness.scorer_v2 import score_detailed
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
        assert q.pending is None and q.rules == _all_required(entry["rules"])
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


def test_rescore_records_the_eval_tag_it_was_scored_on(tmp_path):
    """The rescored line says which bank tag scored it; the source run's tag stays under rescored_from."""
    from harness import rescore as RS
    respond, _ = _scripted("```sql\nSELECT 42\n```")
    ctx = _ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])}))
    ctx.raw_dir = tmp_path / "raw" / "src" / "SQL-L1"
    ctx.run_id, ctx.eval_tag = "src", "eval-old"
    R.run_cell(ctx, [Q], reps=1, concurrency=1, runs_root=tmp_path / "runs", progress=lambda *_: None)
    kw = dict(runs_root=tmp_path / "runs", raw_root=tmp_path / "raw", questions={Q.qid: Q}, commit="evalnew")
    rec = json.loads(RS.rescore("src", "SQL-L1", "rs-tag", eval_tag="eval-new", **kw).read_text(encoding="utf-8"))
    assert (rec["eval_tag"], rec["eval_commit"]) == ("eval-new", "evalnew")
    assert (rec["rescored_from"]["eval_tag"], rec["rescored_from"]["eval_commit"]) == ("eval-old", "evalabc")
    rec = json.loads(RS.rescore("src", "SQL-L1", "rs-untagged", **kw).read_text(encoding="utf-8"))
    assert rec["eval_tag"] is None                    # not verified against a tag: never the source's tag


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


# ---------------------------------------------------------------------------
# harness-v1.1: scorer v2 on every scoring path (decisions/2026-10-18-scorer-spec-v2.md)

# A year in an integer column: the old scorer let 2009 pass for 2008 (0.05 % tolerance);
# v2 compares every integer-typed reference column exactly (spec §12 item 2).
YEAR = Question("Q009", QTEXT, refs=[[[2008, 5]]],
                rules={"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["other", "count"],
                       "value_types": ["UInt16", "UInt64"], "required_columns": [0, 1]})


def test_run_scoring_uses_scorer_v2_in_process_and_in_the_child():
    from harness import scorer as old
    assert old.score_detailed([[2009, 5]], YEAR.refs, YEAR.rules).outcome == "correct"
    for timeout in (None, 60):
        assert R.score_question([[2009, 5]], YEAR, score_timeout_s=timeout)["outcome"] == "wrong"
        assert R.score_question([[2008, 5]], YEAR, score_timeout_s=timeout)["outcome"] == "correct"


def test_rescore_restores_cube_numbers_without_coercing_string_dimensions(tmp_path):
    from decimal import Decimal
    from harness import rescore as RS

    payload = {"columns": [{"name": "cube.code", "type": "string"},
                           {"name": "cube.value", "type": "number"}],
               "rows": [["001", "12345678901234567890.125"], ["002", None], ["003", 7]],
               "error": None}
    data = json.dumps(payload).encode()
    path = tmp_path / "Q001_r1_t0.exec.json"
    path.write_bytes(data)
    turn = {"turn": 0, "exec": {"status": "ok", "exec_raw_sha256": R.sha256(data)}}
    candidate = RS.candidate_of(turn, tmp_path, "Q001", 1)
    assert candidate == [["001", Decimal("12345678901234567890.125")], ["002", None], ["003", 7]]
    assert path.read_bytes() == data
    payload["columns"][1]["type"] = "string"
    data = json.dumps(payload).encode()
    path.write_bytes(data)
    turn["exec"]["exec_raw_sha256"] = R.sha256(data)
    assert RS.candidate_of(turn, tmp_path, "Q001", 1)[0][1] == "12345678901234567890.125"


def test_rescore_uses_scorer_v2(tmp_path):
    from harness import rescore as RS
    respond, _ = _scripted("```sql\nSELECT 2009, 5\n```")
    ctx = _ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 2009, 5": ExecResult(rows=[[2009, 5]])}))
    ctx.raw_dir = tmp_path / "raw" / "src" / "SQL-L1"
    ctx.run_id = "src"
    R.run_cell(ctx, [YEAR], reps=1, concurrency=1, runs_root=tmp_path / "runs", progress=lambda *_: None)
    path = RS.rescore("src", "SQL-L1", "src-v2", runs_root=tmp_path / "runs", raw_root=tmp_path / "raw",
                      questions={"Q009": YEAR}, commit="evalnew")
    assert json.loads(path.read_text(encoding="utf-8"))["final"]["outcome"] == "wrong"


def test_errors_and_refusals_need_no_reference():
    bare = Question("Q010", QTEXT, refs=None, rules=None)
    assert R.score_question(ExecError("boom"), bare)["outcome"] == "exec_error"
    assert R.score_question(ExecError("boom"), bare)["reason"] is None       # never in the log
    assert R.score_question("CANNOT_ANSWER", bare)["outcome"] == "refused"
    assert R.score_question([[1]], bare)["outcome"] == "pending"


def test_unscored_is_not_a_verdict_in_the_summary(tmp_path):
    respond, _ = _scripted("```sql\nSELECT 42\n```")
    ctx = _ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": ExecResult(rows=[[42]])}))
    path = R.run_cell(ctx, [Q], reps=1, concurrency=1, runs_root=tmp_path / "runs", progress=lambda *_: None)
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert R.summarize(path)["accuracy"] == 1.0
    rec["final"] = {**rec["final"], "outcome": R.UNSCORED, "reason": "mapping_cap"}
    path.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    s = R.summarize(path)
    assert s["accuracy"] is None and s["accuracy_scored"] is None and s["outcomes"] == {"unscored": 1}


def test_exec_error_reasons_are_redacted_for_reports():
    from harness.redact import RAW_ENGINE_MESSAGE, exec_error_ref, report_reason
    msg = "Code: 47. DB::Exception: Unknown expression identifier `SecretCol` in SELECT secret FROM t"
    ref = exec_error_ref(msg, "engine_error")
    assert ref.startswith("engine_error · sha256:") and len(ref.split(":")[-1]) == 16
    assert "SecretCol" not in ref and not RAW_ENGINE_MESSAGE.search(ref)
    assert exec_error_ref(msg) == exec_error_ref(msg, None) and exec_error_ref(msg).startswith("execution_failed")
    assert report_reason("exec_error", msg, "timeout").startswith("timeout · sha256:")
    assert report_reason("wrong", "values") == "values" and report_reason("exec_error", None) is None


def test_reports_hold_no_raw_engine_message():
    from harness.redact import RAW_ENGINE_MESSAGE
    hits = [f"{p.relative_to(REPO)}:{n}" for p in sorted((REPO / "reports").rglob("*"))
            if p.is_file() and p.suffix in (".md", ".json", ".jsonl", ".csv", ".txt")
            for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
            if RAW_ENGINE_MESSAGE.search(line)]
    assert not hits, hits


def test_a_bank_scorer_v2_rejects_stops_the_run_before_any_call(capsys):
    old_style = Question("Q011", QTEXT, refs=[[[1]]], rules={"ordered": False, "top_n": None})   # pre-v2 rules
    assert R.invalid_rules([Q, YEAR, Question("Q012", QTEXT, refs=None, rules=None)]) == []
    (bad,) = R.invalid_rules([Q, old_style])
    assert bad.startswith("Q011: ")
    called = []
    rc = R.main(["--cell", "SQL-L1", "--dry-run"], load=lambda lang, **_: called.append(lang) or [old_style])
    assert rc == 2 and "scorer v2 rejects the rules of 1 question" in capsys.readouterr().out


@needs_eval
def test_the_bank_of_the_run_passes_scorer_v2_validation():
    """eval-v1.2 is the first bank written for scorer v2 (spec §9: identity columns required)."""
    import subprocess
    from harness.questions import load_questions
    tag = subprocess.run(["git", "-C", str(EVAL), "describe", "--tags", "--exact-match"],
                         capture_output=True, text=True).stdout.strip()
    if tag != "eval-v1.2":
        pytest.skip(f"bank checkout is {tag or 'untagged'}, not eval-v1.2")
    assert R.invalid_rules(load_questions(EVAL)) == []


# ---------------------------------------------------------------------------
# C13: syntax-note teaching ladder (decisions/2026-10-19-phase1-replan.md §三)


def test_ladder_cells_change_only_the_syntax_note_and_nest():
    try:
        from harness.cells import CELLS, LADDER_CELLS, syntax_path
        l1 = CELLS["SQL-L1"]
        notes = [syntax_path(l1.syntax).read_text(encoding="utf-8")]
        for name in ("SQL-L1-T2", "SQL-L1-T3", "SQL-L1-T4"):
            c = LADDER_CELLS[name]
            assert (c.stack, c.allowed, c.context, c.lang) == (l1.stack, l1.allowed, l1.context, l1.lang)
            assert c.skip_judge and c.card == "C13" and name not in CELLS        # never in --cell all
            text = syntax_path(c.syntax).read_text(encoding="utf-8")
            extends_previous = text.startswith(notes[-1].rstrip("\n")) and len(text) > len(notes[-1])
            assert extends_previous, "each syntax level must extend the previous level"
            notes.append(text)
        assert [LADDER_CELLS[n].split for n in ("SQL-L1-T2", "SQL-L1-T3", "SQL-L1-T4")] == ["all", "all", "heldout"]
        if (REPO / "build" / "contexts" / "SQL-L1.yaml").exists():
            base, t2 = R.system_for(l1), R.system_for(LADDER_CELLS["SQL-L1-T2"])
            same_context = base.replace(notes[0].strip(), notes[1].strip()) == t2
            assert same_context, "ladder cells must change only the syntax note"
    except (PermissionError, FileNotFoundError):
        pytest.skip("required question bank or syntax note is unavailable")


def test_questions_for_skips_judge_and_keeps_the_cells_split():
    from harness.cells import CELLS, LADDER_CELLS
    qs = [Question(f"Q{i:03d}", QTEXT, refs=[[[1]]], rules=Q.rules, scoring=s, meta={"split": sp})
          for i, (s, sp) in enumerate([("deterministic", "tuning"), ("deterministic", "heldout"),
                                       ("judge", "tuning"), ("judge", "heldout")])]
    ids = lambda cell, **kw: [q.qid for q in R.questions_for(cell, qs, **kw)]   # noqa: E731
    assert ids(CELLS["SQL-L1"]) == ["Q000", "Q001", "Q002", "Q003"]
    assert ids(CELLS["SQL-L1"], skip_judge=True) == ["Q000", "Q001"]
    assert ids(LADDER_CELLS["SQL-L1-T2"]) == ids(LADDER_CELLS["SQL-L1-T3"]) == ["Q000", "Q001"]
    assert ids(LADDER_CELLS["SQL-L1-T4"]) == ["Q001"]                           # held-out only, no judge


def test_dry_run_counts_each_cells_own_questions():
    from harness.cells import LADDER_CELLS
    cells = [LADDER_CELLS["SQL-L1-T2"], LADDER_CELLS["SQL-L1-T4"]]
    try:
        rows, _ = R.dry_run(cells, {"SQL-L1-T2": 109, "SQL-L1-T4": 55, "zh": 122}, 3, "deepseek-flash", fix_rate=0.0,
                            output_tokens=1000, hit_ratio=0.9, question_tokens=60, use_measured=False)
    except (PermissionError, FileNotFoundError):
        pytest.skip("required question bank or syntax note is unavailable")
    assert [(r["cell"], r["questions"], r["attempts"]) for r in rows] == [("SQL-L1-T2", 109, 327), ("SQL-L1-T4", 55, 165)]


@needs_eval
def test_ladder_level4_examples_are_tuning_questions_only():
    """Frozen examples follow the eval-v1.2 selection rule and remain tuning-only in the
    current bank, which may add references without changing the frozen examples."""
    import subprocess
    import yaml
    from harness.cells import LADDER_CELLS, syntax_path
    from harness.questions import NON_QUESTION_FILES, question_files
    recs = []
    for f in question_files(EVAL):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        recs += d["questions"] if isinstance(d, dict) else d
    by_text = {r["text_zh"].strip(): r for r in recs}
    text = syntax_path(LADDER_CELLS["SQL-L1-T4"].syntax).read_text(encoding="utf-8")
    asked = [line[2:].strip() for line in text.splitlines() if line.startswith("问：")]
    assert len(asked) == 6
    picked = [by_text[a] for a in asked]
    assert all(r["split"] == "tuning" and r["scoring"] == "deterministic" and r["refs"] for r in picked)
    # C13 selected and froze these examples against eval-v1.2, not today's reference count.
    commit = _git_rev(EVAL, "eval-v1.2")
    files = subprocess.check_output(
        ["git", "-C", str(EVAL), "ls-tree", "--name-only", commit, "questions/"], text=True)
    frozen = []
    for name in sorted(files.splitlines()):
        if not name.endswith(".yaml") or Path(name).name in NON_QUESTION_FILES:
            continue
        d = yaml.safe_load(subprocess.check_output(
            ["git", "-C", str(EVAL), "show", f"{commit}:{name}"], text=True))
        frozen += d["questions"] if isinstance(d, dict) else d
    frozen_by_id = {r["id"]: r for r in frozen}
    frozen_picked = [frozen_by_id[r["id"]] for r in picked]
    assert all(r["text_zh"].strip() == a for r, a in zip(frozen_picked, asked))
    assert all(len(r["refs"]) == 1 for r in frozen_picked)
    pool = [r for r in frozen if r.get("split") == "tuning" and r["scoring"] == "deterministic"
            and len(r["refs"]) == 1 and not r["refs"][0].get("postprocess")]
    rule = []
    for lv in ("Q1", "Q2", "Q3"):
        level = sorted((r for r in pool if (r.get("labels") or {}).get("q_level") == lv),
                       key=lambda r: (len(r["refs"][0]["sql"]), r["id"]))
        n = len(level)
        assert n % 2 == 0                      # the two middle positions; every level has an even count
        rule += [level[n // 2 - 1]["id"], level[n // 2]["id"]]
    assert [r["id"] for r in picked] == rule
    for r in frozen_picked:
        assert r["refs"][0]["sql"].strip() in text


@pytest.mark.parametrize("entry,cell", [
    ("run_direct", "SQL-L1"), ("run_direct", "SQL-L1-T4"),
    ("run_direct", "SQL-L1plus-sel-k1"), ("run_direct", "SQL-L1plus-sel-k3"),
    ("run_agent", "SQL-L1-E"), ("run_plan", "SQL-L1-P"),
])
@pytest.mark.parametrize("budget,expected", [(None, 0), ("0.99", 2), ("1", 0), ("1.01", 0)])
def test_dry_run_checks_budget_before_returning(entry, cell, budget, expected, monkeypatch, capsys):
    from importlib import import_module

    runner = import_module("harness." + entry)
    # Isolate the cost boundary from private contexts, measured logs and model calls.
    monkeypatch.setattr(runner, "dry_run", lambda *a, **kw: ([], 1.0))
    monkeypatch.setattr(runner, "print_dry_run", lambda *a: None)
    argv = ["--cell", cell, "--dry-run"]
    if budget is not None:
        argv += ["--budget", budget]
    assert runner.main(argv, load=lambda **kw: [Q]) == expected
    output = capsys.readouterr().out
    assert ("exceeds budget" in output) == (expected == 2)
    assert QTEXT not in output


def test_selective_cells_preserve_base_prompt_and_scope(tmp_path, monkeypatch):
    from dataclasses import replace
    from harness.cells import L1PLUS_CELLS, SELECTIVE_CELLS
    from render.context import dump_yaml, render_cell

    monkeypatch.setattr(R, "CONTEXTS", tmp_path)
    tmp_path.joinpath("SQL-L1plus.yaml").write_text(dump_yaml(render_cell("SQL-L1plus")), encoding="utf-8")
    base = L1PLUS_CELLS["SQL-L1plus"]
    before = R.system_for(base)
    assert R.sha256(before) == "b80107d469e5600f1c7f3150afef18d11734452a25cc9340f1df46bc470073a3"
    for name, cell in SELECTIVE_CELLS.items():
        k = cell.selective_k
        assert replace(cell, name=base.name, card=base.card, selective_k=None) == base
        rule = (f"计分规则：每道题独立计分。答对得 1 分，答错扣 {k} 分，只输出 CANNOT_ANSWER 得 0 分。"
                f"请让本题的期望得分最高：只有当你判断自己答对的可能性高于 {50 if k == 1 else 75}% 时才作答，"
                "否则只输出 CANNOT_ANSWER。题面有歧义时，可以在「假设：」里写明你采用的理解再作答。")
        assert R.system_for(cell) == before + "\n" + rule + "\n"
        assert name not in CELLS and cell.skip_judge
    assert R.system_for(base) == before


@pytest.mark.parametrize("name", ["SQL-L1plus-sel-k1", "SQL-L1plus-sel-k3"])
@pytest.mark.parametrize("answers,expected,calls", [
    (["CANNOT_ANSWER"], "refused", 1),
    (["invalid format"], "exec_error", 1),
    (["```sql\nSELECT bad\n```", "```sql\nSELECT 42\n```\n假设：无"], "correct", 2),
])
def test_selective_attempt_retains_existing_refusal_format_and_fix(name, answers, expected, calls, tmp_path):
    from harness.cells import SELECTIVE_CELLS

    respond, messages = _scripted(*answers)
    executor = FakeExecutor({"SELECT bad": ExecResult(error="bad query", error_class=ENGINE_ERROR),
                             "SELECT 42": ExecResult(rows=[[42]])})
    ctx = _ctx(tmp_path, MockClient(respond), executor)
    ctx.cell = SELECTIVE_CELLS[name]
    rec = R.run_attempt(ctx, Q, 1)
    assert rec["final"]["outcome"] == expected
    assert len(messages) == calls
    if calls == 2:
        assert "bad query" in messages[-1][-1]["content"]


@pytest.mark.parametrize("amount", [0.5, 0.6])
def test_selective_runtime_budget_shared_across_cells_and_resume(tmp_path, monkeypatch, amount):
    from harness.cells import SELECTIVE_CELLS
    from harness.spend import SpendGuard

    monkeypatch.setattr(R, "cost_cny", lambda *a: amount)
    ledger = tmp_path / "raw" / "spend-ledger.jsonl"
    spend = SpendGuard(ledger, 1, "deepseek-flash")
    boundary = R.CallBoundary(None, allow_peak=True, spend=spend)
    client = MockClient(lambda m: "CANNOT_ANSWER", model="deepseek-flash")
    for i, cell in enumerate(SELECTIVE_CELLS.values(), 1):
        ctx = _ctx(tmp_path, client, FakeExecutor({}))
        ctx.cell, ctx.boundary = cell, boundary
        assert R.run_attempt(ctx, Q, i)["final"]["outcome"] == "refused"
    assert spend.reached and boundary.stopped.is_set()
    assert len(client.requests) == 2
    assert R.run_attempt(ctx, Q, 3)["status"] == "stopped"
    assert len(client.requests) == 2
    restored = SpendGuard(ledger, 1, "deepseek-flash")
    assert restored.total == spend.total and restored.reached
    events = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [r["event"] for r in events] == ["request", "charge"] * 2


def test_selective_runtime_budget_blocks_execution_fix(tmp_path, monkeypatch):
    from harness.spend import SpendGuard

    monkeypatch.setattr(R, "cost_cny", lambda *a: 1.0)
    respond, messages = _scripted("```sql\nSELECT bad\n```", "CANNOT_ANSWER")
    ctx = _ctx(tmp_path, MockClient(respond, model="deepseek-flash"),
               FakeExecutor({"SELECT bad": ExecResult(error="bad", error_class=ENGINE_ERROR)}))
    ctx.boundary = R.CallBoundary(None, allow_peak=True,
                                  spend=SpendGuard(tmp_path / "ledger.jsonl", 1, "deepseek-flash"))
    record = R.run_attempt(ctx, Q, 1)
    assert record["status"] == "stopped" and len(messages) == 1
    assert len(record["turns"]) == 1 and record["turns"][0]["usage"]
    assert (ctx.raw_dir / f"{Q.qid}_r1_t0.json").exists()


def test_selective_runtime_budget_serializes_concurrent_requests(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from decimal import Decimal
    from harness.spend import SpendGuard

    monkeypatch.setattr(R, "cost_cny", lambda *a: 0.1)
    ctx = _ctx(tmp_path, MockClient(lambda m: "CANNOT_ANSWER", model="deepseek-flash"), FakeExecutor({}))
    spend = SpendGuard(tmp_path / "ledger.jsonl", 1, "deepseek-flash")
    ctx.boundary = R.CallBoundary(None, allow_peak=True, spend=spend)
    with ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(lambda q: R.run_attempt(ctx, q, 1), _questions(30)))
    assert len(ctx.client.requests) == 10
    assert spend.total == Decimal("1.0")
    assert sum(r["status"] == "done" for r in records) == 10
    assert sum(r["status"] == "stopped" for r in records) == 20


@pytest.mark.parametrize("failure", ["api_error", "missing_usage", "fingerprint"])
def test_selective_runtime_budget_preserves_failed_or_unconfirmed_calls(tmp_path, monkeypatch, failure):
    from dataclasses import replace
    from harness.spend import SpendGuard

    client = MockClient(lambda m: "CANNOT_ANSWER", model="deepseek-flash")
    original_chat = client.chat
    def respond(*a, **kw):
        if failure == "api_error":
            raise APIError("unknown transport result")
        reply = original_chat(*a, **kw)
        return replace(reply, usage={}) if failure == "missing_usage" else reply
    client.chat = respond
    ctx = _ctx(tmp_path, client, FakeExecutor({}))
    ledger = tmp_path / "ledger.jsonl"
    spend = SpendGuard(ledger, 1, "deepseek-flash")
    ctx.boundary = R.CallBoundary("different" if failure == "fingerprint" else None, allow_peak=True, spend=spend)
    rec = R.run_attempt(ctx, Q, 1)
    assert ctx.boundary.stopped.is_set()
    if failure == "fingerprint":
        assert len(rec["turns"]) == 1 and spend.total > 0
        assert SpendGuard(ledger, 1, "deepseek-flash").total == spend.total
    else:
        with pytest.raises(ValueError, match="unresolved request"):
            SpendGuard(ledger, 1, "deepseek-flash")


def test_selective_runtime_budget_rejects_reset_or_untracked_calls(tmp_path):
    from harness.spend import SpendGuard

    ledger = tmp_path / "ledger.jsonl"
    spend = SpendGuard(ledger, 1, "deepseek-flash")
    spend.begin("SQL-L1plus-sel-k1", "Q_SYNTH", 1, 0)
    spend.charge(0.5, {"prompt_tokens": 1, "cache_hit_tokens": 0,
                       "cache_miss_tokens": 1, "completion_tokens": 1})
    with pytest.raises(ValueError, match="differs"):
        SpendGuard(ledger, 2, "deepseek-flash")
    other = tmp_path / "existing"
    (other / "SQL-L1plus-sel-k1").mkdir(parents=True)
    (other / "SQL-L1plus-sel-k1" / "Q01_r1_t0.json").write_text("{}")
    with pytest.raises(ValueError, match="no spend ledger"):
        SpendGuard(other / "spend-ledger.jsonl", 1, "deepseek-flash")


def test_selective_runtime_budget_cli_shares_threshold_and_resumes_without_calls(tmp_path, monkeypatch):
    from harness import client as C, questions as QL

    clients = []
    def make_client(model, **kwargs):
        assert kwargs["max_attempts"] == 1
        client = MockClient(lambda m: "CANNOT_ANSWER", model=model)
        clients.append(client)
        return client
    monkeypatch.setattr(C, "DeepSeekClient", make_client)
    monkeypatch.setattr(R, "REPO", tmp_path)
    monkeypatch.setattr(R, "raw_root", lambda: tmp_path / "raw")
    monkeypatch.setattr(R, "harness_commit", lambda: "synthetic")
    monkeypatch.setattr(QL, "eval_commit", lambda: "synthetic")
    monkeypatch.setattr(R, "system_for", lambda cell: "synthetic system")
    monkeypatch.setattr(R, "make_executor", lambda *a: FakeExecutor({}))
    monkeypatch.setattr(R, "dry_run", lambda *a, **kw: ([], 0.1))
    monkeypatch.setattr(R, "cost_cny", lambda *a: 0.5)
    argv = ["--cell", "SQL-L1plus-sel-k1", "--cell", "SQL-L1plus-sel-k3",
            "--run-id", "synthetic-budget", "--reps", "1", "--budget", "1", "--allow-peak"]
    assert R.main(argv, load=lambda **kw: [Q]) == 3
    assert len(clients) == 1 and len(clients[0].requests) == 2
    assert R.main(argv, load=lambda **kw: [Q]) == 3
    assert len(clients) == 1  # no API client is created once the persisted budget is reached
    assert R.main(["--cell", "SQL-L1plus-sel-k1", "--run-id", "synthetic-missing-budget"],
                  load=lambda **kw: [Q]) == 2


@pytest.mark.parametrize("name", [
    "test_dry_run_matches_board_unit_list", "test_ladder_cells_change_only_the_syntax_note_and_nest",
    "test_dry_run_counts_each_cells_own_questions",
])
@pytest.mark.parametrize("error", [PermissionError, FileNotFoundError])
def test_unavailable_syntax_skips_without_exception_contents(name, error, monkeypatch, tmp_path):
    def denied(*args, **kwargs):
        raise error("private question content")

    if name == "test_ladder_cells_change_only_the_syntax_note_and_nest":
        monkeypatch.setattr(Path, "read_text", denied)
    else:
        monkeypatch.setattr(R, "dry_run", denied)
    with pytest.raises(pytest.skip.Exception) as caught:
        if name == "test_dry_run_matches_board_unit_list":
            globals()[name](tmp_path)
        else:
            globals()[name]()
    assert "private question content" not in str(caught.value)
