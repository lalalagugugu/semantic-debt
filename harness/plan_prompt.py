"""The planning agent's tools (T21, -P cells): what the model is told, the tool schemas,
the semantic-context catalog and ``lookup``, and how the final answer is read.

Everything in this module is the ``harness-plan-v1`` freeze. Like ``harness/agent_prompt.py``
it says how the tools work and nothing about the data (T21 card, spec).

    system message (-P) = SYSTEM_PROMPT (harness-v1, byte for byte)
                          + catalog of the cell's semantic context (in place of the full context)
                          + syntax notes of the cell (byte for byte)
                          + TOOL_SECTION

The catalog lists every entry of the rendered context YAML by its lookup name with a
one-line summary taken from the entry itself (dataset title, metric definition, convention
rule, data-quality title: first sentence). ``lookup`` returns entries as slices of the
rendered file, so the text is byte for byte the direct cell's context.

The limits below are one value for every -P cell: never set per cell or per question.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from harness import agent_prompt as A
from harness import prompt as P

PLAN, LOOKUP, RUN_SQL, PYTHON = "plan", "lookup", A.TOOL_NAME, "python"
COUNTED_TOOLS = (LOOKUP, RUN_SQL, PYTHON)
MAX_TOOL_CALLS = 12         # lookup + run_sql + python per attempt; plan is not counted
MAX_PLANS = 3               # the first plan and two revisions; more plan calls count against MAX_TOOL_CALLS
MAX_LOOKUP_NAMES = 10       # names per lookup call
ECHO_ROWS = A.ECHO_ROWS     # 50, as -E
ECHO_MAX_CHARS = A.ECHO_MAX_CHARS
MAX_PY_ROWS = 200_000       # rows of one run_sql result kept for python (and of one final query)
PY_TIMEOUT_S = 30

TOOL_SECTION = f"""## 工具与作答方式

上面的「语义上下文」只是目录：列出每个条目的名称和一句话摘要。条目的完整内容要用 {LOOKUP} 按名称取回。可用的工具：

- {PLAN}：提交解题的步骤计划（steps 是字符串列表）。**第一次调用工具时必须先调用 {PLAN}**；之后思路变了，可以再次调用 {PLAN} 提交修改后的完整计划。{PLAN} 不执行任何操作，前 {MAX_PLANS} 次不计入调用次数。
- {LOOKUP}：按目录里的名称取回语义上下文条目的原文（names 是名称列表，每次最多 {MAX_LOOKUP_NAMES} 个）；用节名（如 relationships）取回整节。
- {RUN_SQL}：执行一条只读 SELECT 查询，查询语言和可用范围与上面的说明相同。返回结果编号、总行数和前 {ECHO_ROWS} 行；完整结果（每份最多 {MAX_PY_ROWS} 行）按结果编号保存，供 {PYTHON} 使用。
- {PYTHON}：在隔离环境里运行一段 Python 代码，可用 pandas（pd）和 numpy（np），没有网络，不能读写文件。变量 results 是字典，results[编号] 是该编号的 {RUN_SQL} 结果（pandas DataFrame）。返回 print 的输出。每次最多运行 {PY_TIMEOUT_S} 秒；每次都是全新的进程，变量不保留。
- {LOOKUP}、{RUN_SQL}、{PYTHON} 每道题合计最多调用 {MAX_TOOL_CALLS} 次；用完后不能再调用，必须直接作答。
- 调不调用、调用几次、查什么，由你决定。

准备作答时不再调用工具，用下面两种格式之一输出最终答案，之后照作答要求另起一行写「假设：」。最终答案会由系统另行完整执行，执行结果才是你的答案；工具的返回不算作答。
1. 一个代码块，里面是一条查询（同作答要求）。
2. 查询加 Python：先给出一个或多个 ```sql 代码块（每块一条查询），最后给出一个 ```python 代码块。系统依次完整执行这些查询，results[1]、results[2]……依次是它们的结果（pandas DataFrame，每份最多 {MAX_PY_ROWS} 行）；代码必须把最终结果表（pandas DataFrame）赋给变量 answer，这张表就是你的答案。
- 最终答案执行报错时，你会收到报错，这时不能再调用工具，直接按同样的格式输出修正后的完整答案。"""

TOOLS = [
    {"type": "function", "function": {
        "name": PLAN,
        "description": "提交或修改解题的步骤计划。不执行任何操作。",
        "parameters": {"type": "object", "properties": {
            "steps": {"type": "array", "items": {"type": "string"}, "description": "按顺序的步骤"}},
            "required": ["steps"]}}},
    {"type": "function", "function": {
        "name": LOOKUP,
        "description": f"按名称取回语义上下文条目的原文，每次最多 {MAX_LOOKUP_NAMES} 个名称。",
        "parameters": {"type": "object", "properties": {
            "names": {"type": "array", "items": {"type": "string"}, "description": "目录里的名称或节名"}},
            "required": ["names"]}}},
    {"type": "function", "function": {
        "name": RUN_SQL,
        "description": f"执行一条只读 SELECT 查询，返回结果编号、总行数和前 {ECHO_ROWS} 行。",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "一条只读 SELECT 查询"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": PYTHON,
        "description": "在无网络、无文件的隔离环境里运行 Python 代码；results[编号] 是对应 run_sql 结果的 DataFrame。返回 print 的输出。",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "Python 代码"}},
            "required": ["code"]}}},
]

PLAN_FIRST = f"请先调用 {PLAN} 提交步骤计划，再调用其他工具。本次未执行，不计入次数。"
PLAN_RECORDED = "计划已记录。"
PLAN_LIMIT = f"计划已修改 {MAX_PLANS} 次，本次计入工具调用次数。计划已记录。"
LIMIT_REACHED = f"已达到工具调用上限（{MAX_TOOL_CALLS} 次），本次未执行。请直接按作答要求输出最终答案。"
TOOLS_EXHAUSTED = f"工具调用次数已用完，请直接按作答要求输出最终答案。"     # same pattern as T15-1
BAD_ARGUMENTS = "调用参数无法解析：参数应为 JSON 对象，字段见工具说明。本次未执行。"
UNKNOWN_TOOL = f"没有这个工具；可用的工具只有 {PLAN}、{LOOKUP}、{RUN_SQL}、{PYTHON}。本次未执行。"
TOO_MANY_NAMES = f"每次最多取回 {MAX_LOOKUP_NAMES} 个名称，本次只取回前 {MAX_LOOKUP_NAMES} 个。"
UNKNOWN_NAME = "目录里没有名为「{name}」的条目。"
RESULT_HEAD = "结果编号 {n}。"
PY_ROWS_CUT = f"完整结果共 {{total}} 行，超过 {MAX_PY_ROWS} 行，results[{{n}}] 只保存前 {MAX_PY_ROWS} 行。"
PY_ERROR = "Python 执行报错：\n{error}"
PY_NO_OUTPUT = "（没有输出）"
PY_OUTPUT_CUT = f"\n（输出超过 {ECHO_MAX_CHARS} 字符，以下已截断。）"
ANSWER_ROWS_CUT = f"查询 {{i}} 的结果共 {{total}} 行，超过 Python 作答的上限 {MAX_PY_ROWS} 行。"

CATALOG_HEADER = "## 语义上下文（目录）"


# ---------------------------------------------------------------------------
# Catalog and lookup: slices of the rendered context YAML


@dataclass(frozen=True)
class Entry:
    key: str            # lookup name
    section: str
    text: str           # verbatim slice of the rendered file
    summary: str


_TOP = re.compile(r"^([A-Za-z_][\w]*):\s*$")
_SENTENCE = re.compile(r"^(.*?[。！？])")
# the field that names an entry, and the field its one-line summary comes from
_KEY_FIELD = {"datasets": "name", "metrics": "name", "conventions": "id", "data_quality": "id"}
_SUMMARY_FIELD = {"datasets": "title", "metrics": "definition", "conventions": "rule", "data_quality": "title"}
SECTION_TITLES = {"model": "模型概况", "conventions": "约定", "synonyms": "同义词", "datasets": "数据集",
                  "relationships": "表之间的关系", "multi_path_defaults": "多路径时的默认走法",
                  "metrics": "指标", "data_quality": "数据质量"}


def split_sections(text: str) -> dict[str, str]:
    """Top-level ``key:`` blocks of the rendered YAML, verbatim (each ends with a newline)."""
    lines = text.splitlines(keepends=True)
    starts = [(i, m.group(1)) for i, l in enumerate(lines) if (m := _TOP.match(l))]
    out = {}
    for j, (i, name) in enumerate(starts):
        end = starts[j + 1][0] if j + 1 < len(starts) else len(lines)
        out[name] = "".join(lines[i:end])
    return out


def split_items(section_text: str) -> list[str]:
    """The ``- `` items of a top-level list section, verbatim (column 0, as rendered)."""
    lines = section_text.splitlines(keepends=True)[1:]
    items, cur = [], []
    for line in lines:
        if line.startswith("- ") and cur:
            items.append("".join(cur))
            cur = []
        cur.append(line)
    if cur:
        items.append("".join(cur))
    return items


def _one_line(value) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    m = _SENTENCE.match(text)
    return m.group(1) if m else text


def catalog_entries(context_text: str) -> tuple[list[Entry], dict[str, str]]:
    """(entry-level lookups, whole-section lookups) of one rendered context."""
    import yaml

    sections = split_sections(context_text)
    entries = []
    for name, field in _KEY_FIELD.items():
        if name not in sections:
            continue
        for item in split_items(sections[name]):
            data = yaml.safe_load(item)[0]
            key = str(data[field]) if name == "datasets" else f"{name}:{data[field]}"
            entries.append(Entry(key, name, item, _one_line(data.get(_SUMMARY_FIELD[name]))))
    return entries, sections


def catalog_text(context_text: str) -> str:
    import yaml

    entries, sections = catalog_entries(context_text)
    out = []
    for name in _KEY_FIELD:
        rows = [e for e in entries if e.section == name]
        if not rows:
            continue
        out.append(f"### {SECTION_TITLES.get(name, name)}（{len(rows)} 条；lookup 名称 — 摘要）")
        out.extend(f"- {e.key}" + (f" — {e.summary}" if e.summary else "") for e in rows)
        out.append("")
    out.append("### 整节（lookup 节名 — 内容）")
    for name, text in sections.items():
        data = yaml.safe_load(text)[name]
        size = f"，{len(data)} 条" if isinstance(data, list) else ""
        out.append(f"- {name} — {SECTION_TITLES.get(name, name)}{size}")
    return "\n".join(out)


def plan_system_message(context_text: str, syntax_text: str) -> str:
    return (f"{P.SYSTEM_PROMPT}\n\n{CATALOG_HEADER}\n\n{catalog_text(context_text)}\n\n"
            f"{P.SYNTAX_HEADER}\n\n{syntax_text.strip()}\n\n{TOOL_SECTION}\n")


class Lookup:
    """``lookup`` over one rendered context: exact name, section name, or a unique match on
    the part after ``section:``."""

    def __init__(self, context_text: str) -> None:
        entries, self.sections = catalog_entries(context_text)
        self.entries = {e.key: e for e in entries}
        self.short: dict[str, list[str]] = {}
        for e in entries:
            self.short.setdefault(e.key.partition(":")[2] or e.key, []).append(e.key)

    def resolve(self, name: str) -> tuple[str, str] | None:
        name = name.strip()
        if name in self.entries:
            return name, self.entries[name].text
        if name in self.sections:
            return name, self.sections[name]
        keys = self.short.get(name, [])
        if len(keys) == 1:
            return keys[0], self.entries[keys[0]].text
        return None

    def render(self, names: list[str]) -> tuple[str, list[str], list[str]]:
        """(tool message, names found, names not found)."""
        parts, found, missing = [], [], []
        if len(names) > MAX_LOOKUP_NAMES:
            parts.append(TOO_MANY_NAMES)
            names = names[:MAX_LOOKUP_NAMES]
        for name in names:
            hit = self.resolve(str(name))
            if hit is None:
                missing.append(str(name))
                parts.append(UNKNOWN_NAME.format(name=name))
            else:
                found.append(hit[0])
                parts.append(f"### {hit[0]}\n```yaml\n{hit[1].rstrip()}\n```")
        return "\n\n".join(parts), found, missing


# ---------------------------------------------------------------------------
# Tool messages


def render_sql_result(n: int | None, result, kept_rows: int | None) -> tuple[str, int, bool]:
    """``run_sql``'s message: the -E rendering, with the result number and the python cap."""
    text, shown, cut = A.render_result(result)
    if not result.ok or n is None:
        return text, shown, cut
    head = RESULT_HEAD.format(n=n)
    total = len(result.rows or [])
    if kept_rows is not None and total > kept_rows:
        head += PY_ROWS_CUT.format(total=total, n=n)
    return f"{head}\n{text}", shown, cut


def render_python(result) -> str:
    if not result.ok:
        body = PY_ERROR.format(error=(result.error or "")[:P.MAX_ERROR_CHARS])
        if result.stdout:
            body = f"{result.stdout.rstrip()}\n{body}"
    else:
        body = result.stdout.rstrip() or PY_NO_OUTPUT
    if len(body) > ECHO_MAX_CHARS:
        body = body[:ECHO_MAX_CHARS] + PY_OUTPUT_CUT
    return body


def tool_args(tc: dict) -> tuple[str | None, dict | None]:
    """(tool name, parsed arguments or None when they cannot be parsed)."""
    fn = tc.get("function") or {}
    try:
        args = json.loads(fn.get("arguments") or "")
    except (TypeError, ValueError):
        return fn.get("name"), None
    return fn.get("name"), args if isinstance(args, dict) else None


# ---------------------------------------------------------------------------
# The final answer: one query, or queries + Python


@dataclass(frozen=True)
class FinalAnswer:
    kind: str                       # "sql", "sql+python", "refused" or "none"
    queries: tuple[str, ...]
    python: str | None
    assumption: str | None
    n_code_blocks: int

    def as_parsed(self) -> P.Parsed:
        """The direct-answer view (for kind "sql", "refused", "none")."""
        return P.Parsed(self.queries[-1] if self.kind == "sql" else None, self.assumption,
                        self.kind == "refused", self.n_code_blocks)


_FENCE = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)


def parse_final(content: str | None) -> FinalAnswer:
    """Format 2 when the last code block is Python: every earlier non-empty block is one
    query. Otherwise exactly the direct-answer rules (``prompt.parse_response``)."""
    blocks = [(lang.strip().lower(), body.strip()) for lang, body in _FENCE.findall(content or "")]
    blocks = [(lang, body) for lang, body in blocks if body]
    if blocks and blocks[-1][0] in {"python", "py", "python3"}:
        parsed = P.parse_response(content)
        queries = tuple(body for lang, body in blocks[:-1] if lang not in {"python", "py", "python3"})
        return FinalAnswer("sql+python", queries, blocks[-1][1], parsed.assumption, len(blocks))
    parsed = P.parse_response(content)
    kind = "refused" if parsed.refused else ("sql" if parsed.query else "none")
    return FinalAnswer(kind, (parsed.query,) if parsed.query else (), None, parsed.assumption, parsed.n_code_blocks)
