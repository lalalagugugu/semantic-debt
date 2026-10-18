"""The explorer agent's tool (T15): the one paragraph appended to the system message,
the ``run_sql`` function schema, and how a tool result is shown to the model.

Everything in this module is the ``harness-agent-v1`` freeze. It says how the tool
works and nothing about the data (T15 card, spec 4).

    system message (-E) = direct system message of the same cell (harness-v1, byte for byte)
                          + TOOL_SECTION

The direct message is a strict prefix, so the -E cell sees exactly the direct cell's
system prompt, semantic context and syntax notes. The limits below are one value for
every -E cell (T15 card, T11 hand-over 1): never set per cell or per question.
"""

from __future__ import annotations

import json

from harness import prompt as P
from harness.executors import ExecResult

TOOL_NAME = "run_sql"
MAX_TOOL_CALLS = 8          # run_sql calls per attempt; after that only the final answer
ECHO_ROWS = 50              # rows shown to the model per run_sql call
ECHO_MAX_CHARS = 20_000     # characters of one tool result; guards against one huge cell value

TOOL_SECTION = f"""## 工具

你可以调用只读工具 {TOOL_NAME} 执行查询、查看数据，例如查看字段的实际取值、看样例行、试跑查询并检查结果。
- {TOOL_NAME} 每次执行一条只读 SELECT 查询，查询语言和可用范围与上面的说明相同。
- 每次最多返回 {ECHO_ROWS} 行；结果超过 {ECHO_ROWS} 行时只返回前 {ECHO_ROWS} 行，并注明结果已截断和总行数。
- 每道题最多调用 {MAX_TOOL_CALLS} 次 {TOOL_NAME}；用完后不能再调用，必须直接作答。
- 调不调用、调用几次、查什么，由你决定。
- 准备作答时不再调用工具，按上面的作答要求输出最终答案。最终答案里的查询会由系统另行完整执行，它的结果才是你的答案；{TOOL_NAME} 的返回不算作答。
- 最终查询执行报错时，你会收到报错，这时不能再调用工具，直接按同样的格式输出修正后的完整查询。"""

TOOLS = [{
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": f"执行一条只读 SELECT 查询，返回结果的前 {ECHO_ROWS} 行和总行数。",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "一条只读 SELECT 查询"}},
            "required": ["query"],
        },
    },
}]

LIMIT_REACHED = f"已达到 {TOOL_NAME} 的调用上限（{MAX_TOOL_CALLS} 次），本次未执行。请直接按作答要求输出最终答案。"
# Sent once, as a user message, right before the forced answer (tool_choice "none") whenever the
# calls are used up, whether the last one ran normally or a reply asked for more than remained
# (decisions/2026-10-19-t15-1-midreport-dsh.md section 1, harness-agent-v1.1).
TOOLS_EXHAUSTED = f"{TOOL_NAME} 次数已用完，请直接按作答要求输出最终答案。"
BAD_ARGUMENTS = f"调用参数无法解析：参数应为 JSON 对象 {{\"query\": \"<一条 SELECT 查询>\"}}。本次未执行。"
UNKNOWN_TOOL = f"没有这个工具；可用的工具只有 {TOOL_NAME}。本次未执行。"
ERROR_TEMPLATE = "查询执行报错：\n{error}"


def agent_system_message(direct_system: str) -> str:
    return f"{direct_system.rstrip()}\n\n{TOOL_SECTION}\n"


def _cell(value) -> str:
    if value is None:
        return "NULL"
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")


def render_result(result: ExecResult) -> tuple[str, int, bool]:
    """The tool message for one execution, how many rows it shows, and whether the
    character cap cut it.

    Rows are tab-separated under a header of column names. More than ``ECHO_ROWS`` rows
    are cut and the model is told so with the total count; never presented as complete.
    """
    if not result.ok:
        return ERROR_TEMPLATE.format(error=(result.error or "execution error")[:P.MAX_ERROR_CHARS]), 0, False
    rows = result.rows or []
    shown = rows[:ECHO_ROWS]
    if len(rows) > ECHO_ROWS:
        head = f"结果已截断，共 {len(rows)} 行，以下只显示前 {ECHO_ROWS} 行。"
    else:
        head = f"共 {len(rows)} 行。"
    names = [c.get("name", f"c{i}") for i, c in enumerate(result.columns)] or \
        [f"c{i}" for i in range(len(shown[0]) if shown else 0)]
    lines = [head, "\t".join(_cell(n) for n in names), *("\t".join(_cell(v) for v in row) for row in shown)]
    text = "\n".join(lines)
    if len(text) <= ECHO_MAX_CHARS:
        return text, len(shown), False
    return text[:ECHO_MAX_CHARS] + f"\n（输出超过 {ECHO_MAX_CHARS} 字符，以下已截断。）", len(shown), True
