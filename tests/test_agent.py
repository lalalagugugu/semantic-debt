"""T15 explorer agent: tool loop, echo cap, step limit, scope, fix once, scoring timeout, log.

Offline: MockClient and a fake executor (no API call). Tests marked ``chdb`` run the
real executor on ``$SEMDEBT_DATA_DIR/chdb`` and are skipped when it is not available.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness import agent_prompt as A  # noqa: E402
from harness import prompt as P  # noqa: E402
from harness import rescore as RS  # noqa: E402
from harness import run_agent as AG  # noqa: E402
from harness import run_direct as R  # noqa: E402
from harness.cells import AGENT_CELLS, CELLS  # noqa: E402
from harness.client import APIError, MockClient  # noqa: E402
from harness.executors import ENGINE_ERROR, SCOPE_MESSAGE, SCOPE_VIOLATION, ExecResult  # noqa: E402
from harness.questions import Question  # noqa: E402

CHDB = Path(os.environ.get("SEMDEBT_DATA_DIR", "/nonexistent")).expanduser() / "chdb"
needs_chdb = pytest.mark.skipif(not CHDB.exists(), reason="chDB data directory not available")

QTEXT = "这是一个绝不能进入日志的探查问题原文"
Q = Question("Q001", QTEXT, refs=[[[42]]], rules={"ordered": False, "top_n": None, "tie_columns": [],
                                                    "value_kinds": ["count"], "value_types": ["UInt64"]})
ANSWER = "```sql\nSELECT 42\n```\n假设：无"


class FakeExecutor:
    name = "fake"

    def __init__(self, table: dict[str, ExecResult]):
        self.table = table
        self.seen: list[str] = []

    def execute(self, query: str) -> ExecResult:
        self.seen.append(query.strip())
        return self.table.get(query.strip(), ExecResult(error="Code: 47. Unknown identifier", error_class=ENGINE_ERROR))


OK42 = ExecResult(rows=[[42]], columns=[{"name": "n", "type": "UInt64"}])


def _ctx(tmp_path, client, executor, cell="SQL-L1-E", tool_executor=None):
    direct = P.system_message("ctx", "syntax")
    return R.RunContext(run_id="test-run", cell=AG._named(AGENT_CELLS[cell], cell), client=client, executor=executor,
                        system=A.agent_system_message(direct), eval_commit="evalabc", harness_commit="h123",
                        timeout_s=120, raw_dir=tmp_path / "raw", tool_executor=tool_executor)


def tool(*queries, content=""):
    return {"content": content, "tool_calls": [
        {"id": f"call_{i}_{abs(hash(q)) % 10**6}", "type": "function",
         "function": {"name": "run_sql", "arguments": json.dumps({"query": q}, ensure_ascii=False)}}
        for i, q in enumerate(queries)]}


def scripted(*answers):
    answers = list(answers)
    calls: list[list[dict]] = []

    def respond(messages):
        calls.append([dict(m) for m in messages])
        return answers.pop(0)
    return respond, calls


# ---------------------------------------------------------------------------
# prompt


def test_agent_system_is_the_direct_system_plus_only_the_tool_section():
    direct = R.system_for(CELLS["SQL-L1"]) if (REPO / "build/contexts/SQL-L1.yaml").exists() else P.system_message("c", "s")
    agent = A.agent_system_message(direct)
    assert agent.startswith(direct.rstrip())
    assert agent[len(direct.rstrip()):] == f"\n\n{A.TOOL_SECTION}\n"


def test_tool_section_has_the_limits_and_no_data_hints():
    text = A.TOOL_SECTION + json.dumps(A.TOOLS, ensure_ascii=False)
    assert str(A.ECHO_ROWS) in A.TOOL_SECTION and str(A.MAX_TOOL_CALLS) in A.TOOL_SECTION
    # nothing about this dataset: no table, database or business term
    for word in ("retail", "Fact", "Dim", "ads", "dwd", "l0", "销售", "门店", "客户", "产品", "Contoso", "库存"):
        assert word not in text, word


def test_limits_are_one_value_for_every_agent_cell():
    assert (A.MAX_TOOL_CALLS, A.ECHO_ROWS) == (8, 50)
    assert set(AGENT_CELLS) == {"SQL-L0-E", "SQL-L1-E", "SQL-L2-E"}
    assert AGENT_CELLS["SQL-L1-E"] is CELLS["SQL-L1"] and AGENT_CELLS["SQL-L2-E"] is CELLS["SQL-L2"]
    assert not any(name.endswith("-E") for name in CELLS)       # run_direct --cell all never runs them


def test_prompt_py_is_byte_identical_to_harness_v1():
    assert AG.verify_file_at_tag("harness/prompt.py", "harness-v1")


def test_render_result_cuts_at_the_echo_cap_and_says_so():
    rows = [[i, f"名{i}", None] for i in range(120)]
    text, shown, cut = A.render_result(ExecResult(rows=rows, columns=[{"name": "k"}, {"name": "名称"}, {"name": "v"}]))
    lines = text.splitlines()
    assert lines[0] == "结果已截断，共 120 行，以下只显示前 50 行。"
    assert lines[1] == "k\t名称\tv" and lines[2] == "0\t名0\tNULL"
    assert len(lines) == 2 + 50 and shown == 50 and not cut
    text, shown, _ = A.render_result(ExecResult(rows=[[1]], columns=[{"name": "x"}]))
    assert text.splitlines()[0] == "共 1 行。" and shown == 1
    text, shown, _ = A.render_result(ExecResult(rows=[], columns=[{"name": "x"}]))
    assert text == "共 0 行。\nx" and shown == 0


def test_render_result_character_cap_and_errors():
    text, shown, cut = A.render_result(ExecResult(rows=[["x" * 30_000]], columns=[{"name": "s"}]))
    assert cut and len(text) < A.ECHO_MAX_CHARS + 100 and text.endswith("已截断。）")
    text, shown, cut = A.render_result(ExecResult(error="Code: 47. " + "e" * 5000, error_class=ENGINE_ERROR))
    assert text.startswith("查询执行报错：\nCode: 47.") and len(text) <= len("查询执行报错：\n") + P.MAX_ERROR_CHARS
    text, *_ = A.render_result(ExecResult(rows=[["a\tb\nc"]], columns=[{"name": "s"}]))
    assert text.splitlines()[2] == "a\\tb\\nc"


# ---------------------------------------------------------------------------
# attempt flow


def test_no_tool_call_is_direct_answering_with_tools_offered(tmp_path):
    respond, calls = scripted(ANSWER)
    client = MockClient(respond)
    rec = AG.run_attempt(_ctx(tmp_path, client, FakeExecutor({"SELECT 42": OK42})), Q, 1)
    assert rec["status"] == "done" and rec["final"]["outcome"] == "correct"
    assert rec["n_tool_calls"] == 0 and rec["steps"] == [] and rec["n_calls"] == 1
    assert client.requests == [{"tools": A.TOOLS, "tool_choice": None}]
    assert rec["turns"][0]["turn"] == 0 and rec["agent"]["max_tool_calls"] == 8


def test_tool_results_go_back_with_reasoning_and_the_final_query_is_scored(tmp_path):
    respond, calls = scripted(tool("SELECT n FROM t LIMIT 5"), ANSWER)
    ex = FakeExecutor({"SELECT n FROM t LIMIT 5": ExecResult(rows=[[i] for i in range(80)], columns=[{"name": "n"}]),
                       "SELECT 42": OK42})
    rec = AG.run_attempt(_ctx(tmp_path, MockClient(respond), ex), Q, 1)
    second = calls[1]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "tool"]
    assert second[2]["reasoning_content"] == "(mock)" and second[2]["tool_calls"][0]["function"]["name"] == "run_sql"
    assert second[3]["tool_call_id"] == second[2]["tool_calls"][0]["id"]
    assert second[3]["content"].startswith("结果已截断，共 80 行，以下只显示前 50 行。")
    step = rec["steps"][0]
    c = step["tool_calls"][0]
    assert c["status"] == "executed" and c["truncated"] and c["echoed_rows"] == 50 and c["exec"]["row_count"] == 80
    assert (tmp_path / "raw" / "Q001_r1_t0_c0.exec.json").exists()
    assert (tmp_path / "raw" / "Q001_r1_t0.json").exists() and (tmp_path / "raw" / "Q001_r1_t1.exec.json").exists()
    assert rec["turns"][0]["turn"] == 1 and rec["final"]["outcome"] == "correct"
    assert rec["n_tool_calls"] == 1 and rec["n_calls"] == 2 and rec["n_steps"] == 1
    assert rec["usage"]["prompt_tokens"] == sum(s["usage"]["prompt_tokens"] for s in rec["steps"] + rec["turns"])


def test_eight_tool_calls_then_the_model_must_answer(tmp_path):
    answers = [tool(f"SELECT {i}") for i in range(8)] + [ANSWER]
    respond, calls = scripted(*answers)
    client = MockClient(respond)
    ex = FakeExecutor({**{f"SELECT {i}": ExecResult(rows=[[i]]) for i in range(8)}, "SELECT 42": OK42})
    rec = AG.run_attempt(_ctx(tmp_path, client, ex), Q, 1)
    assert [r["tool_choice"] for r in client.requests] == [None] * 8 + ["none"]
    assert rec["n_tool_calls"] == 8 and rec["hit_tool_limit"] and rec["n_calls"] == 9
    assert rec["final"]["outcome"] == "correct" and rec["turns"][0]["tool_choice"] == "none"


def test_calls_beyond_the_limit_in_one_reply_are_not_executed(tmp_path):
    respond, calls = scripted(tool(*[f"SELECT {i}" for i in range(6)]), tool("SELECT 6", "SELECT 7", "SELECT 8", "SELECT 9"),
                              ANSWER)
    client = MockClient(respond)
    ex = FakeExecutor({**{f"SELECT {i}": ExecResult(rows=[[i]]) for i in range(10)}, "SELECT 42": OK42})
    rec = AG.run_attempt(_ctx(tmp_path, client, ex), Q, 1)
    assert ex.seen == [f"SELECT {i}" for i in range(8)] + ["SELECT 42"]
    statuses = [c["status"] for s in rec["steps"] for c in s["tool_calls"]]
    assert statuses == ["executed"] * 8 + ["limit_reached"] * 2
    assert calls[2][-1]["content"] == A.LIMIT_REACHED
    assert client.requests[-1]["tool_choice"] == "none" and rec["n_tool_calls"] == 8


def test_run_sql_uses_its_own_executor_and_the_final_query_the_direct_one(tmp_path):
    respond, _ = scripted(tool("SELECT 1"), ANSWER)
    final_ex, tool_ex = FakeExecutor({"SELECT 42": OK42}), FakeExecutor({"SELECT 1": OK42})
    tool_ex.timeout_s = 30
    rec = AG.run_attempt(_ctx(tmp_path, MockClient(respond), final_ex, tool_executor=tool_ex), Q, 1)
    assert tool_ex.seen == ["SELECT 1"] and final_ex.seen == ["SELECT 42"]
    assert rec["agent"]["tool_timeout_s"] == 30 and rec["exec_timeout_s"] == 120
    assert AG.parse_args(["--cell", "SQL-L1-E", "--dry-run"]).tool_timeout == 30
    assert AG.parse_args(["--cell", "SQL-L1-E", "--dry-run"]).exec_timeout == 120


def test_bad_arguments_and_unknown_tool_count_but_do_not_execute(tmp_path):
    bad = {"content": "", "tool_calls": [
        {"id": "a", "type": "function", "function": {"name": "run_sql", "arguments": "{not json"}},
        {"id": "b", "type": "function", "function": {"name": "drop_table", "arguments": "{}"}}]}
    respond, calls = scripted(bad, ANSWER)
    ex = FakeExecutor({"SELECT 42": OK42})
    rec = AG.run_attempt(_ctx(tmp_path, MockClient(respond), ex), Q, 1)
    assert ex.seen == ["SELECT 42"]
    assert [c["status"] for c in rec["steps"][0]["tool_calls"]] == ["bad_arguments", "unknown_tool"]
    assert [m["content"] for m in calls[1][-2:]] == [A.BAD_ARGUMENTS, A.UNKNOWN_TOOL]
    assert rec["n_tool_calls"] == 2


def test_scope_violation_in_a_tool_call_is_reported_with_the_harness_message(tmp_path):
    scope = ExecResult(error=SCOPE_MESSAGE, error_class=SCOPE_VIOLATION, detail="static: retail.FactSales")
    respond, calls = scripted(tool("SELECT * FROM retail.FactSales"), ANSWER)
    ex = FakeExecutor({"SELECT * FROM retail.FactSales": scope, "SELECT 42": OK42})
    rec = AG.run_attempt(_ctx(tmp_path, MockClient(respond), ex, cell="SQL-L0-E"), Q, 1)
    assert calls[1][-1]["content"] == f"查询执行报错：\n{SCOPE_MESSAGE}"
    assert rec["steps"][0]["tool_calls"][0]["exec"]["error_class"] == SCOPE_VIOLATION
    assert "retail.FactSales" not in calls[1][-1]["content"]


def test_final_query_error_is_fixed_exactly_once_without_tools(tmp_path):
    respond, calls = scripted(tool("SELECT 1"), "```sql\nSELECT bad\n```\n假设：无", tool("SELECT 2"))
    client = MockClient(respond)
    ex = FakeExecutor({"SELECT 1": ExecResult(rows=[[1]])})
    rec = AG.run_attempt(_ctx(tmp_path, client, ex), Q, 1)
    # the fix request forbids tools; a mock that still returns tool calls gets them ignored, not executed
    assert client.requests[-1]["tool_choice"] == "none" and len(calls) == 3
    fix = calls[2]
    assert [m["role"] for m in fix] == ["system", "user", "assistant", "tool", "assistant", "user"]
    assert all("reasoning_content" in m for m in fix if m["role"] == "assistant")
    assert "Unknown identifier" in fix[-1]["content"]
    assert rec["fixed"] and rec["first"] == "exec_error" and rec["final"]["outcome"] == "exec_error"
    assert [t["turn"] for t in rec["turns"]] == [1, 2] and ex.seen == ["SELECT 1", "SELECT bad"]


def test_refusal_and_missing_query(tmp_path):
    for answer, outcome in (("CANNOT_ANSWER", "refused"), ("我不确定", "exec_error")):
        respond, _ = scripted(answer)
        rec = AG.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({})), Q, 1)
        assert rec["final"]["outcome"] == outcome and not rec["fixed"]


def test_score_timeout_is_pending_not_a_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "score_with_timeout", lambda *a, **k: None)
    respond, _ = scripted(tool("SELECT 1"), ANSWER)
    rec = AG.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 1": OK42, "SELECT 42": OK42})), Q, 1)
    assert rec["final"]["outcome"] == "pending" and rec["final"]["pending"] == "score_timeout"
    assert (tmp_path / "raw" / "Q001_r1_t1.exec.json").exists()     # rows kept for the offline rescore


def test_api_error_keeps_the_steps_so_far(tmp_path):
    class Flaky(MockClient):
        def chat(self, messages, **kw):
            if len(messages) > 2:
                raise APIError("HTTP 503", 4)
            return super().chat(messages, **kw)
    respond, _ = scripted(tool("SELECT 1"))
    rec = AG.run_attempt(_ctx(tmp_path, Flaky(respond), FakeExecutor({"SELECT 1": OK42})), Q, 1)
    assert rec["status"] == "api_error" and len(rec["steps"]) == 1 and rec["n_tool_calls"] == 1


# ---------------------------------------------------------------------------
# cell run, log, rescore, fingerprint, summary


def test_run_cell_log_has_steps_and_no_question_text_and_rescores(tmp_path):
    questions = [Question(f"Q{i:03d}", f"{QTEXT}{i}", [[[42]]], Q.rules) for i in range(1, 4)]

    def respond(messages):
        return tool("SELECT 1") if len(messages) == 2 else ANSWER
    ex = FakeExecutor({"SELECT 1": OK42, "SELECT 42": OK42})
    ctx = _ctx(tmp_path, MockClient(respond), ex)
    path = R.run_cell(ctx, questions, reps=2, concurrency=3, runs_root=tmp_path / "runs",
                      progress=lambda *_: None, attempt=AG.run_attempt)
    assert path.name == "SQL-L1-E.jsonl"
    text = path.read_text(encoding="utf-8")
    assert QTEXT not in text
    recs = [json.loads(l) for l in text.splitlines()]
    assert len(recs) == 6 and all(r["cell"] == "SQL-L1-E" for r in recs)
    assert all({"steps", "n_tool_calls", "wall_s", "tool_time_s", "usage", "agent"} <= set(r) for r in recs)
    s = AG.summarize(path)
    assert s["attempts"] == 6 and s["accuracy"] == 1.0
    assert s["agent"]["tool_calls_per_attempt"] == {1: 6} and s["agent"]["tool_forbidden_statements"] == 0
    assert sum(s["system_fingerprints"].values()) == 12             # tool steps counted too
    # offline rescore reads the final answer's exec file unchanged
    for rec in recs:
        out = RS.rescore_line(rec, questions[int(rec["qid"][1:]) - 1], tmp_path / "raw", "rs", "evalabc")
        assert out["final"]["outcome"] == "correct"


def test_unexpected_fingerprint_stops_the_run(tmp_path):
    questions = [Question(f"Q{i:03d}", f"q{i}", [[[42]]], Q.rules) for i in range(1, 6)]
    client = MockClient(lambda m: ANSWER, fingerprint="fp_other")
    guard = AG.PinnedFingerprintGuard("e72d3c7f663d3e1383b00b3884cb4501")
    path = R.run_cell(_ctx(tmp_path, client, FakeExecutor({"SELECT 42": OK42})), questions, reps=1, concurrency=2,
                      runs_root=tmp_path / "runs", progress=lambda *_: None, guard=guard, attempt=AG.run_attempt)
    assert guard.conflict
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1     # the warm-up attempt only
    ok = AG.PinnedFingerprintGuard("fp_mock")
    ok.observe({"steps": [{"system_fingerprint": "fp_mock"}], "turns": [{"system_fingerprint": "fp_mock"}]})
    assert not ok.conflict and ok.seen == {"fp_mock": 2}


def test_dry_run_estimates_and_prefers_measured_steps(tmp_path):
    rows, total = AG.dry_run(["SQL-L1-E"], 122, 3, "deepseek-flash", calls=1, growth=0, output=0, question_tokens=0,
                             runs_root=tmp_path, use_measured=True)
    if rows[0]["per_attempt"] is None:
        pytest.skip("contexts not rendered")
    assert rows[0]["source"] == "estimated" and rows[0]["attempts"] == 366
    run = tmp_path / "r1"
    run.mkdir()
    line = {"status": "done", "steps": [], "usage": {"cache_hit_tokens": 1_000_000, "cache_miss_tokens": 0,
                                                     "completion_tokens": 0}}
    (run / "SQL-L1-E.jsonl").write_text(json.dumps(line) + "\n", encoding="utf-8")
    rows, total = AG.dry_run(["SQL-L1-E"], 10, 1, "deepseek-flash", calls=1, growth=0, output=0, question_tokens=0,
                             runs_root=tmp_path)
    assert rows[0]["source"].startswith("measured") and total == pytest.approx(10 * 0.02)


def test_estimate_grows_with_calls():
    cell = AGENT_CELLS["SQL-L0-E"]
    if not (REPO / "build/contexts/SQL-L0.yaml").exists():
        pytest.skip("contexts not rendered")
    one = AG.estimated(cell, 1, 2000, 1000, 60)
    five = AG.estimated(cell, 5, 2000, 1000, 60)
    assert one["cache_miss_tokens"] == 60 and five["cache_miss_tokens"] == 60 + 4 * 2000
    assert five["cache_hit_tokens"] > 5 * one["cache_hit_tokens"] and five["completion_tokens"] == 5000


def test_cli_gates_l2_e_and_requires_a_run_id():
    with pytest.raises(SystemExit):
        AG.parse_args(["--cell", "SQL-L2-E", "--run-id", "x"])
    assert AG.parse_args(["--cell", "SQL-L2-E", "--run-id", "x", "--allow-cube"]).allow_cube
    assert AG.parse_args(["--cell", "SQL-L2-E", "--dry-run"]).dry_run
    with pytest.raises(SystemExit):
        AG.parse_args(["--cell", "SQL-L1-E"])
    with pytest.raises(SystemExit):
        AG.parse_args(["--cell", "SQL-L1", "--dry-run"])


def test_verify_file_at_tag(tmp_path):
    root = tmp_path / "repo"
    (root / "harness").mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True)  # noqa: E731
    git("init", "-q")
    (root / "harness/agent_prompt.py").write_text("a\n")
    git("add", ".")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x")
    with pytest.raises(AG.HarnessVersionError, match="not found"):
        AG.verify_file_at_tag("harness/agent_prompt.py", "harness-agent-v1", root)
    git("tag", "harness-agent-v1")
    assert AG.verify_file_at_tag("harness/agent_prompt.py", "harness-agent-v1", root)
    (root / "harness/agent_prompt.py").write_text("b\n")
    with pytest.raises(AG.HarnessVersionError, match="differs"):
        AG.verify_file_at_tag("harness/agent_prompt.py", "harness-agent-v1", root)


# ---------------------------------------------------------------------------
# real chDB: run_sql goes through the same checks as the final query


@needs_chdb
@pytest.mark.parametrize("query, error_class", [
    ("INSERT INTO retail.DimDate SELECT * FROM retail.DimDate LIMIT 0", "forbidden_statement"),
    ("CREATE TABLE x (a Int8) ENGINE = Memory", "forbidden_statement"),
    ("SELECT 1; DROP TABLE retail.DimDate", "forbidden_statement"),
    ("SELECT 1 SETTINGS max_result_rows = 0", "forbidden_statement"),
    ("SELECT * FROM retail.DimDate", "scope_violation"),
    ("SELECT * FROM file('/etc/passwd')", "scope_violation"),
])
def test_tool_on_real_chdb_is_read_only_and_scoped(tmp_path, query, error_class):
    executor = R.make_executor(CELLS["SQL-L0"], timeout_s=30)
    respond, calls = scripted(tool(query), "CANNOT_ANSWER")
    rec = AG.run_attempt(_ctx(tmp_path, MockClient(respond), executor, cell="SQL-L0-E"), Q, 1)
    c = rec["steps"][0]["tool_calls"][0]
    assert c["exec"]["status"] == "error" and c["exec"]["error_class"] == error_class
    assert calls[1][-1]["content"].startswith("查询执行报错：")


@needs_chdb
def test_tool_on_real_chdb_cuts_a_large_result(tmp_path):
    executor = R.make_executor(CELLS["SQL-L1"], timeout_s=30)
    respond, calls = scripted(tool("SELECT number FROM numbers(1000)"), "CANNOT_ANSWER")
    rec = AG.run_attempt(_ctx(tmp_path, MockClient(respond), executor), Q, 1)
    c = rec["steps"][0]["tool_calls"][0]
    assert c["exec"]["row_count"] == 1000 and c["echoed_rows"] == 50 and c["truncated"]
    assert calls[1][-1]["content"].splitlines()[0] == "结果已截断，共 1000 行，以下只显示前 50 行。"
