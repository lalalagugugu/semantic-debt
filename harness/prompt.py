"""Prompt assembly and response parsing for direct answering (直答).

Order (T11 card, spec 1 and carried-forward requirement 2):

    system message = system prompt → semantic context → syntax notes
    user message   = one question

Everything before the question is identical for every question of a cell, so
DeepSeek's prefix cache can hit for the whole context. Nothing that varies by
question may be placed in the system message.

The system prompt is part of the ``harness-v1`` freeze (G3). It must not contain
anything about specific questions, answers or this dataset.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REFUSAL = "CANNOT_ANSWER"

SYSTEM_PROMPT = """你是企业数据分析助手。下面给出一份描述数据模型的语义上下文和一段查询语言说明。用户会提一个业务问题，请写一条查询来回答它。

作答要求：
1. 只使用语义上下文里出现的表、字段和关系。
2. 输出恰好一个代码块，里面是一条可以直接执行的查询；查询的结果就是问题的答案。
3. 代码块之后另起一行，以「假设：」开头，用一句话说明你对问题里含糊之处做了什么假设；没有就写「假设：无」。
4. 如果根据语义上下文无法回答这个问题，只输出 CANNOT_ANSWER，不要输出其他内容。
5. 如果收到查询的执行报错，按同样的格式输出修正后的完整查询。"""

CONTEXT_HEADER = "## 语义上下文"
SYNTAX_HEADER = "## 查询语言说明"

FIX_TEMPLATE = "查询执行报错：\n```\n{error}\n```\n请修正后重新输出，格式同上。"
MAX_ERROR_CHARS = 2000


def system_message(context_text: str, syntax_text: str, context_lang: str = "yaml") -> str:
    """The stable prefix: system prompt → semantic context → syntax notes."""
    return (
        f"{SYSTEM_PROMPT}\n\n{CONTEXT_HEADER}\n\n```{context_lang}\n{context_text.rstrip()}\n```\n\n"
        f"{SYNTAX_HEADER}\n\n{syntax_text.strip()}\n"
    )


def first_messages(system: str, question: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": system}, {"role": "user", "content": question}]


def fix_message(error: str) -> dict[str, str]:
    return {"role": "user", "content": FIX_TEMPLATE.format(error=error[:MAX_ERROR_CHARS])}


@dataclass(frozen=True)
class Parsed:
    query: str | None
    assumption: str | None
    refused: bool
    n_code_blocks: int


_FENCE = re.compile(r"```[^\n`]*\n(.*?)```", re.DOTALL)
_ASSUMPTION = re.compile(r"^\s*(?:[*_>#-]+\s*)*假设[:：]\s*(.*)$", re.MULTILINE)


def parse_response(content: str | None) -> Parsed:
    """Extract the query and the assumption line.

    - No code block and the text contains CANNOT_ANSWER → refusal.
    - Several code blocks → the last one is the answer (``n_code_blocks`` records it).
    - No code block and no refusal → ``query=None`` (format failure; the harness
      records it and does not retry, because it is not an execution error).
    """
    text = content or ""
    blocks = [b.strip() for b in _FENCE.findall(text)]
    blocks = [b for b in blocks if b]
    assumption_match = _ASSUMPTION.findall(text)
    assumption = assumption_match[-1].strip() if assumption_match else None
    if not blocks:
        return Parsed(None, assumption, REFUSAL in text, 0)
    return Parsed(blocks[-1], assumption, False, len(blocks))
