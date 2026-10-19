"""T21 planning agent: plan first, lookup, python sandbox, the shared tool cap, both answer
forms, fix once, log and rescore; the sandbox's one allowed docker command; isolation.

Offline: MockClient, a fake executor and a fake sandbox (no API call, no docker). Tests
marked ``docker`` run the real sandbox image and are skipped when docker is not reachable
(set DOCKER_HOST to Docker Desktop's socket inside the Claude Code sandbox).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness import plan_prompt as PP  # noqa: E402
from harness import prompt as P  # noqa: E402
from harness import pysandbox as SB  # noqa: E402
from harness import rescore as RS  # noqa: E402
from harness import run_direct as R  # noqa: E402
from harness import run_plan as RP  # noqa: E402
from harness.cells import CELLS, CONTEXTS, PLAN_CELLS, SYNTAX  # noqa: E402
from harness.client import MockClient  # noqa: E402
from harness.executors import ENGINE_ERROR, ExecResult  # noqa: E402
from harness.pysandbox import PyResult  # noqa: E402
from harness.questions import Question  # noqa: E402

QTEXT = "这是一个绝不能进入日志的规划问题原文"
RULES = {"ordered": False, "top_n": None, "tie_columns": [], "value_kinds": ["count"], "value_types": ["UInt64"],
         "required_columns": [0]}
Q = Question("Q001", QTEXT, refs=[[[42]]], rules=RULES)
ANSWER = "```sql\nSELECT 42\n```\n假设：无"
PY_ANSWER = "```sql\nSELECT 40\n```\n```sql\nSELECT 2\n```\n```python\nanswer = results[1] + results[2]\n```\n假设：无"
OK42 = ExecResult(rows=[[42]], columns=[{"name": "n", "type": "UInt64"}])
CONTEXT = """model:
  title: 测试模型
datasets:
- name: db.T
  title: 测试表
  columns:
  - name: a
    type: Int32
- name: db.U
  title: 另一张表。第二句不进目录。
metrics:
- name: 数量
  definition: 行数合计。按日统计。
relationships:
- from: db.T.a
  to: db.U.a
"""


class FakeExecutor:
    name = "fake"

    def __init__(self, table: dict[str, ExecResult]):
        self.table, self.seen = table, []

    def execute(self, query: str) -> ExecResult:
        self.seen.append(query.strip())
        return self.table.get(query.strip(), ExecResult(error="Code: 47. Unknown identifier", error_class=ENGINE_ERROR))


class FakeSandbox:
    """Records calls; ``answer`` adds the first column of every table (enough for the tests)."""

    name = "fake-sandbox"

    def __init__(self, result: PyResult | None = None):
        self.calls, self.result = [], result

    def run(self, code, tables, want_answer=False):
        self.calls.append({"code": code, "tables": tables, "want_answer": want_answer})
        if self.result is not None:
            return self.result
        if want_answer:
            total = sum(t["rows"][0][0] for t in tables.values())
            return PyResult(True, answer={"columns": [{"name": "n", "type": "Int64"}], "rows": [[total]]})
        return PyResult(True, stdout=f"tables={sorted(tables)}")


def _ctx(tmp_path, client, executor, sandbox=None, cell="SQL-L1-P", tool_executor=None):
    return RP.PlanContext(run_id="test-run", cell=RP._named(PLAN_CELLS[cell], cell), client=client, executor=executor,
                          system=PP.plan_system_message(CONTEXT, "syntax"), eval_commit="evalabc",
                          harness_commit="h123", timeout_s=120, raw_dir=tmp_path / "raw",
                          tool_executor=tool_executor, sandbox=sandbox or FakeSandbox(), lookup=PP.Lookup(CONTEXT))


def call(name, **args):
    return {"id": f"call_{name}_{abs(hash(json.dumps(args, ensure_ascii=False))) % 10**6}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}


def tools(*calls, content=""):
    return {"content": content, "tool_calls": list(calls)}


def plan(*steps):
    return call("plan", steps=list(steps) or ["拆题", "查数", "作答"])


def scripted(*answers):
    answers = list(answers)
    seen: list[list[dict]] = []

    def respond(messages):
        seen.append([dict(m) for m in messages])
        return answers.pop(0)
    return respond, seen


def tool_messages(messages):
    return [m["content"] for m in messages if m["role"] == "tool"]


# ---------------------------------------------------------------------------
# system message, tool section, catalog and lookup


def test_system_message_is_system_prompt_catalog_syntax_and_tool_section():
    msg = PP.plan_system_message(CONTEXT, "SYNTAX NOTES")
    assert msg.startswith(P.SYSTEM_PROMPT + "\n\n" + PP.CATALOG_HEADER)
    assert "\n\n## 查询语言说明\n\nSYNTAX NOTES\n\n" in msg
    assert msg.endswith(PP.TOOL_SECTION + "\n")
    assert "- db.T — 测试表" in msg and "- db.U — 另一张表。" in msg and "第二句" not in msg
    assert "- metrics:数量 — 行数合计。" in msg and "- relationships — 表之间的关系，1 条" in msg
    assert "type: Int32" not in msg                    # the context itself is not in the system message


def test_tool_section_states_the_limits_and_no_data_hints():
    s = PP.TOOL_SECTION
    for needle in ("plan", "lookup", "run_sql", "python", f"最多调用 {PP.MAX_TOOL_CALLS} 次", f"{PP.MAX_PY_ROWS} 行",
                   f"{PP.PY_TIMEOUT_S} 秒", "answer", "results[1]", "必须先调用 plan"):
        assert needle in s
    for word in ("Contoso", "Fact", "Dim", "线上", "门店", "retail", "l0."):
        assert word not in s
    assert PP.MAX_TOOL_CALLS == 12 and PP.ECHO_ROWS == 50


def test_prompt_py_is_still_harness_v1():
    from harness import run_agent as AG
    AG.verify_file_at_tag("harness/prompt.py", "harness-v1")


def test_lookup_returns_verbatim_slices_and_resolves_short_names():
    lk = PP.Lookup(CONTEXT)
    text, found, missing = lk.render(["db.T", "数量", "relationships", "nope"])
    assert found == ["db.T", "metrics:数量", "relationships"] and missing == ["nope"]
    assert "- name: db.T\n  title: 测试表\n  columns:\n  - name: a\n    type: Int32" in text
    assert "目录里没有名为「nope」的条目。" in text
    many, found, _ = lk.render(["db.T"] * (PP.MAX_LOOKUP_NAMES + 2))
    assert many.startswith(PP.TOO_MANY_NAMES) and len(found) == PP.MAX_LOOKUP_NAMES


@pytest.mark.parametrize("name", ["SQL-L0", "SQL-L1"])
def test_lookup_on_the_rendered_contexts_is_byte_identical(name):
    path = CONTEXTS / f"{name}.yaml"
    if not path.exists():
        pytest.skip("build/contexts not rendered (uv run python render/render_all.py)")
    text = path.read_text(encoding="utf-8")
    sections = PP.split_sections(text)
    assert "".join(sections.values()) == text
    full = yaml.safe_load(text)
    lk = PP.Lookup(text)
    for sec, body in sections.items():
        assert lk.resolve(sec) == (sec, body)
        if isinstance(full[sec], list):
            items = PP.split_items(body)
            assert [yaml.safe_load(i)[0] for i in items] == full[sec]
            assert all(i in text for i in items)
    for key, entry in lk.entries.items():
        assert lk.resolve(key)[1] == entry.text and entry.text in text
    # every entry is in the catalog by its lookup name
    catalog = PP.catalog_text(text)
    assert all(f"- {k}" in catalog for k in lk.entries)
    assert len(catalog) < len(text)


def test_plan_cells_are_l0_and_l1_with_the_direct_scope():
    assert set(PLAN_CELLS) == {"SQL-L0-P", "SQL-L1-P"}
    assert PLAN_CELLS["SQL-L1-P"] == CELLS["SQL-L1"] and PLAN_CELLS["SQL-L0-P"] == CELLS["SQL-L0"]


def test_plan_system_for_uses_the_cell_syntax():
    if not (CONTEXTS / "SQL-L1.yaml").exists():
        pytest.skip("build/contexts not rendered")
    msg = RP.plan_system_for(PLAN_CELLS["SQL-L1-P"])
    assert (SYNTAX / "clickhouse_sql.md").read_text(encoding="utf-8").strip() in msg


# ---------------------------------------------------------------------------
# final answer parsing


def test_parse_final_forms():
    f = PP.parse_final(ANSWER)
    assert f.kind == "sql" and f.queries == ("SELECT 42",) and f.python is None
    f = PP.parse_final(PY_ANSWER)
    assert f.kind == "sql+python" and f.queries == ("SELECT 40", "SELECT 2") and "results[1]" in f.python
    assert f.assumption == "无"
    assert PP.parse_final("CANNOT_ANSWER").kind == "refused"
    assert PP.parse_final("没有代码块").kind == "none"
    only_py = PP.parse_final("```python\nanswer = pd.DataFrame({'n': [1]})\n```")
    assert only_py.kind == "sql+python" and only_py.queries == ()
    # a python block that is not last: direct rules, last block is the query
    assert PP.parse_final("```python\nx\n```\n```sql\nSELECT 1\n```").kind == "sql"


# ---------------------------------------------------------------------------
# the loop


def test_plan_must_come_first_and_rejections_are_not_counted(tmp_path):
    respond, seen = scripted(tools(call("run_sql", query="SELECT 1")), tools(plan()),
                             tools(call("run_sql", query="SELECT 1")), ANSWER)
    ex = FakeExecutor({"SELECT 1": OK42, "SELECT 42": OK42})
    line = RP.run_attempt(_ctx(tmp_path, MockClient(respond), ex), Q, 1)
    assert tool_messages(seen[1]) == [PP.PLAN_FIRST]
    assert tool_messages(seen[2])[-1] == PP.PLAN_RECORDED
    assert line["plan_first_rejections"] == 1 and line["n_plans"] == 1 and line["n_tool_calls"] == 1
    assert ex.seen == ["SELECT 1", "SELECT 42"] and line["final"]["outcome"] == "correct"


def test_plan_in_the_same_reply_as_other_tools_is_enough(tmp_path):
    respond, seen = scripted(tools(plan(), call("lookup", names=["db.T"])), ANSWER)
    line = RP.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": OK42})), Q, 1)
    msgs = tool_messages(seen[1])
    assert msgs[0] == PP.PLAN_RECORDED and msgs[1].startswith("### db.T\n```yaml\n- name: db.T")
    assert line["tool_executed"] == {"lookup": 1, "run_sql": 0, "python": 0}
    assert line["steps"][0]["tool_calls"][1]["found"] == ["db.T"]


def test_plan_text_goes_to_runs_raw_not_to_the_log(tmp_path):
    respond, _ = scripted(tools(plan("先找出" + QTEXT)), ANSWER)
    line = RP.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": OK42})), Q, 1)
    assert QTEXT not in json.dumps(line, ensure_ascii=False)
    rec = line["steps"][0]["tool_calls"][0]
    raw = tmp_path / "raw" / "Q001_r1_t0_c0.plan.json"
    assert R.sha256(raw.read_bytes()) == rec["plan_raw_sha256"] and QTEXT in raw.read_text(encoding="utf-8")


def test_twelve_counted_calls_then_the_model_must_answer(tmp_path):
    replies = [tools(plan())] + [tools(call("lookup", names=["db.T"])) for _ in range(PP.MAX_TOOL_CALLS)] + [ANSWER]
    client = MockClient(scripted(*replies)[0])
    line = RP.run_attempt(_ctx(tmp_path, client, FakeExecutor({"SELECT 42": OK42})), Q, 1)
    assert line["n_tool_calls"] == PP.MAX_TOOL_CALLS and line["hit_tool_limit"] and line["limit_message_sent"]
    assert [r["tool_choice"] for r in client.requests] == [None] * (PP.MAX_TOOL_CALLS + 1) + ["none"]
    assert line["final"]["outcome"] == "correct"


def test_exhausted_message_is_sent_once_before_the_forced_answer(tmp_path):
    replies = [tools(plan(), *[call("lookup", names=["db.T"]) for _ in range(PP.MAX_TOOL_CALLS + 2)]), ANSWER]
    respond, seen = scripted(*replies)
    client = MockClient(respond)
    line = RP.run_attempt(_ctx(tmp_path, client, FakeExecutor({"SELECT 42": OK42})), Q, 1)
    statuses = [c["status"] for c in line["steps"][0]["tool_calls"]]
    assert statuses.count("executed") == PP.MAX_TOOL_CALLS and statuses.count("limit_reached") == 2
    assert seen[1][-1] == {"role": "user", "content": PP.TOOLS_EXHAUSTED}
    assert client.requests[-1]["tool_choice"] == "none"


def test_plans_beyond_the_free_ones_count(tmp_path):
    replies = [tools(plan()) for _ in range(PP.MAX_PLANS + 2)] + [ANSWER]
    respond, seen = scripted(*replies)
    line = RP.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": OK42})), Q, 1)
    assert line["n_plans"] == PP.MAX_PLANS + 2 and line["n_tool_calls"] == 2
    assert tool_messages(seen[-1])[-1] == PP.PLAN_LIMIT


def test_model_call_backstop_forces_an_answer(tmp_path):
    # a model that keeps calling tools before any plan never reaches the tool cap
    replies = [tools(call("run_sql", query="SELECT 1")) for _ in range(RP.MAX_MODEL_CALLS)] + [ANSWER]
    client = MockClient(scripted(*replies)[0])
    line = RP.run_attempt(_ctx(tmp_path, client, FakeExecutor({"SELECT 42": OK42})), Q, 1)
    assert line["hit_model_call_limit"] and line["n_tool_calls"] == 0 and line["limit_message_sent"]
    assert line["n_calls"] == RP.MAX_MODEL_CALLS + 1 and client.requests[-1]["tool_choice"] == "none"


def test_run_sql_results_are_numbered_and_reach_python(tmp_path):
    big = ExecResult(rows=[[i] for i in range(PP.MAX_PY_ROWS + 5)], columns=[{"name": "i", "type": "UInt32"}])
    ex = FakeExecutor({"SELECT 1": OK42, "SELECT big": big, "SELECT 42": OK42})
    sb = FakeSandbox()
    respond, seen = scripted(tools(plan(), call("run_sql", query="SELECT 1"), call("run_sql", query="SELECT bad"),
                                   call("run_sql", query="SELECT big"), call("python", code="print(1)")), ANSWER)
    line = RP.run_attempt(_ctx(tmp_path, MockClient(respond), ex, sb), Q, 1)
    msgs = tool_messages(seen[1])
    assert msgs[1].startswith("结果编号 1。\n共 1 行。")
    assert msgs[2].startswith("查询执行报错")                          # an error gets no number
    assert msgs[3].startswith("结果编号 2。完整结果共 200005 行，超过 200000 行，results[2] 只保存前 200000 行。")
    assert msgs[4] == "tables=[1, 2]"
    assert len(sb.calls[0]["tables"][2]["rows"]) == PP.MAX_PY_ROWS and not sb.calls[0]["want_answer"]
    calls = line["steps"][0]["tool_calls"]
    assert [c.get("result_no") for c in calls[1:4]] == [1, None, 2] and calls[3]["py_rows_cut"]
    assert calls[4]["py"]["status"] == "ok" and "code" not in calls[4]


def test_python_error_is_shown_with_its_output(tmp_path):
    sb = FakeSandbox(PyResult(False, stdout="partial", error="NameError: x", error_class="python_error"))
    respond, seen = scripted(tools(plan(), call("python", code="print(x)")), ANSWER)
    RP.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": OK42}), sb), Q, 1)
    assert tool_messages(seen[1])[1] == "partial\nPython 执行报错：\nNameError: x"


def test_bad_arguments_and_unknown_tools_count(tmp_path):
    bad = {"id": "c9", "type": "function", "function": {"name": "run_sql", "arguments": "{oops"}}
    respond, seen = scripted(tools(plan(), bad, call("shell", cmd="ls"), call("lookup", names="db.T")), ANSWER)
    line = RP.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": OK42})), Q, 1)
    assert tool_messages(seen[1])[1:] == [PP.BAD_ARGUMENTS, PP.UNKNOWN_TOOL, PP.BAD_ARGUMENTS]
    assert line["n_tool_calls"] == 3 and line["n_tool_executed"] == 0


def test_sql_python_answer_reruns_the_queries_and_scores_the_answer_table(tmp_path):
    ex = FakeExecutor({"SELECT 40": ExecResult(rows=[[40]], columns=[{"name": "a", "type": "UInt8"}]),
                       "SELECT 2": ExecResult(rows=[[2]], columns=[{"name": "b", "type": "UInt8"}])})
    sb = FakeSandbox()
    respond, _ = scripted(tools(plan()), PY_ANSWER)
    line = RP.run_attempt(_ctx(tmp_path, MockClient(respond), ex, sb), Q, 1)
    assert ex.seen == ["SELECT 40", "SELECT 2"]
    assert sb.calls[-1]["want_answer"] and sorted(sb.calls[-1]["tables"]) == [1, 2]
    assert line["answer_kind"] == "sql+python" and line["final"]["outcome"] == "correct"
    turn = line["turns"][0]
    assert turn["queries"] == ["SELECT 40", "SELECT 2"] and turn["query"] is None
    assert turn["exec"]["status"] == "ok" and turn["exec"]["row_count"] == 1
    # rescore reads the answer table from the turn's exec file, unchanged
    assert RS.candidate_of(turn, tmp_path / "raw", "Q001", 1) == [[42]]


def test_python_answer_error_is_fixed_once_without_tools(tmp_path):
    ex = FakeExecutor({"SELECT 40": OK42, "SELECT 2": OK42, "SELECT 42": OK42})
    sb = FakeSandbox(PyResult(False, error="KeyError: 3", error_class="python_error"))
    respond, seen = scripted(tools(plan()), PY_ANSWER, ANSWER)
    client = MockClient(respond)
    line = RP.run_attempt(_ctx(tmp_path, client, ex, sb), Q, 1)
    assert "Python 执行报错：\nKeyError: 3" in seen[-1][-1]["content"]
    assert client.requests[-1]["tool_choice"] == "none"
    assert line["fixed"] and line["first"] == "exec_error" and line["final"]["outcome"] == "correct"
    assert line["answer_kinds"] == ["sql+python", "sql"]


def test_python_answer_query_error_names_the_query(tmp_path):
    respond, seen = scripted(tools(plan()), PY_ANSWER, ANSWER)
    line = RP.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT 42": OK42})), Q, 1)
    assert "查询 1 执行报错：" in seen[-1][-1]["content"]
    assert line["turns"][0]["exec"]["error_class"] == ENGINE_ERROR


def test_python_answer_with_too_many_rows_is_an_error(tmp_path):
    big = ExecResult(rows=[[1]] * (PP.MAX_PY_ROWS + 1), columns=[{"name": "a", "type": "UInt8"}])
    respond, _ = scripted(tools(plan()), "```sql\nSELECT big\n```\n```python\nanswer = results[1]\n```",
                          "CANNOT_ANSWER")
    line = RP.run_attempt(_ctx(tmp_path, MockClient(respond), FakeExecutor({"SELECT big": big})), Q, 1)
    assert line["turns"][0]["exec"]["limit"] == "py_rows" and line["final"]["outcome"] == "refused"


def test_answer_without_plan_is_still_scored_and_flagged(tmp_path):
    line = RP.run_attempt(_ctx(tmp_path, MockClient(lambda m: ANSWER), FakeExecutor({"SELECT 42": OK42})), Q, 1)
    assert line["n_plans"] == 0 and line["final"]["outcome"] == "correct" and line["answer_kind"] == "sql"


def test_run_cell_log_has_no_question_text_and_rescores(tmp_path):
    questions = [Question(f"Q{i:03d}", f"{QTEXT}{i}", [[[42]]], RULES) for i in range(1, 4)]

    def respond(messages):
        n = len(messages)
        if n == 2:
            return tools(plan(QTEXT), call("run_sql", query="SELECT 1"), call("python", code=f"# {QTEXT}"))
        return PY_ANSWER if n == 6 else ANSWER
    ex = FakeExecutor({"SELECT 1": OK42, "SELECT 40": ExecResult(rows=[[40]], columns=[]),
                       "SELECT 2": ExecResult(rows=[[2]], columns=[])})
    ctx = _ctx(tmp_path, MockClient(respond), ex)
    path = R.run_cell(ctx, questions, reps=2, concurrency=3, runs_root=tmp_path / "runs",
                      progress=lambda *_: None, attempt=RP.run_attempt)
    text = path.read_text(encoding="utf-8")
    assert path.name == "SQL-L1-P.jsonl" and QTEXT not in text
    recs = [json.loads(l) for l in text.splitlines()]
    assert len(recs) == 6 and all(r["final"]["outcome"] == "correct" for r in recs)
    s = RP.summarize(path)
    assert s["accuracy"] == 1.0 and s["plan"]["answer_kind"] == {"sql+python": 6} and s["agent"]["run_sql_forbidden_statements"] == 0
    assert s["plan"]["tool_executed"] == {"lookup": 0, "run_sql": 6, "python": 6}
    for rec in recs:
        out = RS.rescore_line(rec, questions[int(rec["qid"][1:]) - 1], tmp_path / "raw", "rs", "evalabc")
        assert out["final"]["outcome"] == "correct"


def test_dry_run_estimates_from_the_catalog_prompt(tmp_path):
    if not (CONTEXTS / "SQL-L1.yaml").exists():
        pytest.skip("build/contexts not rendered")
    rows, total = RP.dry_run(["SQL-L0-P", "SQL-L1-P"], 24, 1, "deepseek-flash", calls=7, growth=3000, output=2000,
                             question_tokens=60, runs_root=tmp_path)
    assert all(r["source"] == "estimated" for r in rows) and total > 0


def test_cli_requires_a_run_id_and_only_plan_cells():
    with pytest.raises(SystemExit):
        RP.parse_args(["--cell", "SQL-L1-P"])
    with pytest.raises(SystemExit):
        RP.parse_args(["--cell", "SQL-L1-E", "--dry-run"])
    assert RP.parse_args(["--cell", "SQL-L1-P", "--dry-run"]).eval_tag == "eval-v1.2"


def test_main_refuses_when_the_sandbox_does_not_run(monkeypatch, capsys):
    monkeypatch.setattr(R, "is_peak", lambda *a: False)
    monkeypatch.setattr(RP, "check_versions", lambda args: [])
    sb = FakeSandbox(PyResult(False, error="no docker", error_class="sandbox_error"))
    rc = RP.main(["--cell", "SQL-L1-P", "--run-id", "x", "--est-from-args"], load=lambda lang: [Q], sandbox=sb)
    assert rc == 2 and "Python sandbox does not run" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# the one docker command


def test_docker_command_is_the_fixed_isolated_run():
    cmd = SB.docker_command("semdebt-py-0123456789ab")
    SB.check_command(cmd)
    assert cmd[:4] == ["docker", "run", "--rm", "-i"] and cmd[-1] == SB.IMAGE_ID
    joined = " ".join(cmd)
    assert "--network none" in joined and "--read-only" in joined and "--cap-drop ALL" in joined
    assert not any(a in cmd for a in ("-v", "--volume", "--mount", "--privileged", "-p"))
    assert SB.IMAGE_ID.startswith("sha256:") and len(SB.IMAGE_ID) == 71 and set(SB.IMAGE_ID[7:]) != {"0"}


@pytest.mark.parametrize("mutate", [
    lambda c: c[:-1] + ["-v", "/:/host"] + c[-1:],
    lambda c: c[:-1] + ["--mount", "type=bind,src=/,dst=/h"] + c[-1:],
    lambda c: c[:-1] + ["--privileged"] + c[-1:],
    lambda c: [x if x != "none" else "host" for x in c],
    lambda c: [x for x in c if x != "--read-only"],
    lambda c: c[:-1] + ["semdebt-pysandbox:1"],
    lambda c: c[:-1] + ["sha256:" + "f" * 64],
    lambda c: ["docker", "exec", "x", "sh"],
    lambda c: ["docker", "kill", c[5]],
    lambda c: c[:5] + ["other-name"] + c[6:],
])
def test_any_other_docker_invocation_is_refused(mutate):
    with pytest.raises(ValueError):
        SB.check_command(mutate(SB.docker_command("semdebt-py-0123456789ab")))


def test_parse_output_classifies_failures():
    assert SB.parse_output(137, b"", b"", 31.0).error_class == "timeout"
    assert SB.parse_output(137, b"", b"", 2.0).error_class == "resource_limit"
    assert SB.parse_output(125, b"", b"docker: error", 0.1).error_class == "sandbox_error"
    ok = SB.parse_output(0, json.dumps({"ok": True, "stdout": "x", "answer": None}).encode(), b"", 0.2)
    assert ok.ok and ok.stdout == "x"


def test_plan_freeze_files_exist():
    for path in RP.PLAN_FILES:
        assert (REPO / path).exists()


# ---------------------------------------------------------------------------
# the real sandbox (docker)


def _docker_ok() -> bool:
    try:
        return subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                              capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


needs_docker = pytest.mark.skipif(not _docker_ok(), reason="docker not reachable (set DOCKER_HOST)")


@needs_docker
def test_real_sandbox_types_columns_and_returns_the_answer_table():
    tables = {1: {"columns": [{"name": "k", "type": "UInt64"}, {"name": "d", "type": "Date"},
                              {"name": "x", "type": "Nullable(Decimal(18, 2))"}, {"name": "s", "type": "String"}],
                  "rows": [["18446744073709551615", "2009-01-02", "1.50", "a"], ["2", "2009-12-31", None, "b"]]}}
    code = ("print(results[1].dtypes.astype(str).tolist())\n"
            "answer = results[1].assign(y=results[1].x * 2).sort_values('d')[['s', 'd', 'y']]")
    r = SB.DockerSandbox().run(code, tables, want_answer=True)
    assert r.ok, r.error
    assert r.stdout.strip() == "['uint64', 'datetime64[ns]', 'float64', 'object']"
    assert r.answer["rows"] == [["a", "2009-01-02", 3.0], ["b", "2009-12-31", None]]
    assert [c["type"] for c in r.answer["columns"]] == ["String", "Date", "Float64"]


@needs_docker
def test_real_sandbox_reports_errors_and_a_missing_answer():
    r = SB.DockerSandbox().run("print('before')\n1/0", {})
    assert not r.ok and r.error_class == "python_error" and "ZeroDivisionError" in r.error and r.stdout == "before\n"
    r = SB.DockerSandbox().run("x = 1", {}, want_answer=True)
    assert not r.ok and "answer" in r.error


@needs_docker
def test_real_sandbox_isolation_every_probe_is_blocked():
    sys.path.insert(0, str(REPO / "harness" / "pysandbox_image"))
    import isolation_probe

    r = SB.DockerSandbox().run(isolation_probe.request()["code"], {})
    lines = r.stdout.strip().splitlines()
    assert r.ok and len(lines) == 11, r.stdout
    assert all(l.startswith("blocked") for l in lines), r.stdout


@needs_docker
def test_real_sandbox_kills_code_after_the_time_limit():
    r = SB.DockerSandbox().run("while True:\n    pass", {})
    assert not r.ok and r.error_class == "timeout" and SB.TIMEOUT_S <= r.elapsed_s < SB.TIMEOUT_S + SB.HOST_GRACE_S
