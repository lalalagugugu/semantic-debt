"""DeepSeek official API (OpenAI-compatible chat completions), plus a mock.

- The key is read only from ``DEEPSEEK_API_KEY`` (hard rule 5); it never reaches
  a log or a file.
- Thinking mode on, effort ``high``; ``temperature`` is never sent (it has no
  effect in thinking mode).
- Rate limits (429), server errors (5xx) and network failures are retried with
  exponential backoff. These are transport retries, not answer retries; their
  count is returned and logged.
"""

from __future__ import annotations

import http.client
import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_EFFORT = "high"


@dataclass(frozen=True)
class Reply:
    content: str
    reasoning: str | None
    model_version: str
    finish_reason: str | None
    usage: dict[str, int]
    latency_s: float
    raw: bytes
    transport_retries: int = 0
    # ``model`` only echoes the requested name; the fingerprint is the version evidence
    # (decisions/2026-10-17-model-version-fingerprint.md)
    system_fingerprint: str | None = None
    # function calls of the explorer agent (T15), as the API returned them; None for direct answering
    tool_calls: list[dict] | None = None


class APIError(RuntimeError):
    def __init__(self, message: str, transport_retries: int = 0) -> None:
        super().__init__(message)
        self.transport_retries = transport_retries


class ModelClient(Protocol):
    model: str

    def chat(self, messages: list[dict[str, Any]], *, tools: list[dict] | None = None,
             tool_choice: str | None = None) -> Reply: ...


def usage_summary(usage: dict) -> dict[str, int]:
    """Token counts as logged: cache hit / miss input, output, of which reasoning."""
    details = usage.get("completion_tokens_details") or {}
    hit = int(usage.get("prompt_cache_hit_tokens") or 0)
    miss = int(usage.get("prompt_cache_miss_tokens") or 0)
    prompt = int(usage.get("prompt_tokens") or hit + miss)
    return {
        "prompt_tokens": prompt,
        "cache_hit_tokens": hit,
        "cache_miss_tokens": miss,
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "reasoning_tokens": int(details.get("reasoning_tokens") or 0),
    }


class DeepSeekClient:
    def __init__(self, model: str, *, effort: str = DEFAULT_EFFORT, max_attempts: int = 6,
                 request_timeout_s: float = 900.0, url: str = API_URL,
                 before_request: Callable[[], None] | None = None) -> None:
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")
        self._key = key
        self.model = model
        self.effort = effort
        self.max_attempts = max_attempts
        self.request_timeout_s = request_timeout_s
        self.url = url
        self.before_request = before_request

    def chat(self, messages: list[dict[str, Any]], *, tools: list[dict] | None = None,
             tool_choice: str | None = None) -> Reply:
        """``tools`` / ``tool_choice`` are sent only when given, so a direct-answer request is
        byte-for-byte what it was before the explorer agent (T15) existed."""
        request_body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "thinking": {"type": "enabled"},
            "reasoning_effort": self.effort,
            "stream": False,
        }
        if tools is not None:
            request_body["tools"] = tools
        if tool_choice is not None:
            request_body["tool_choice"] = tool_choice
        body = json.dumps(request_body, ensure_ascii=False).encode()
        retries = 0
        last_error = ""
        for attempt in range(self.max_attempts):
            if self.before_request is not None:
                self.before_request()
            request = urllib.request.Request(self.url, data=body, method="POST", headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._key}",
            })
            start = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=self.request_timeout_s) as response:
                    raw = response.read()
                latency = time.monotonic() - start
                return _reply(raw, latency, retries)
            except urllib.error.HTTPError as exc:
                detail = exc.read()[:500].decode("utf-8", "replace")
                last_error = f"HTTP {exc.code}: {detail}"
                if exc.code != 429 and exc.code < 500:
                    raise APIError(last_error, retries) from None
            except (OSError, http.client.HTTPException, json.JSONDecodeError) as exc:
                # URLError, timeouts, connection resets and ssl.SSLError mid-read are all OSError
                last_error = f"{type(exc).__name__}: {exc}"
            retries += 1
            if attempt + 1 < self.max_attempts:
                time.sleep(min(120.0, 2.0 * 2 ** attempt) * (0.5 + random.random()))
        raise APIError(f"gave up after {retries} transport retries: {last_error}", retries)


def _reply(raw: bytes, latency: float, retries: int) -> Reply:
    payload = json.loads(raw)
    choice = payload["choices"][0]
    message = choice.get("message") or {}
    return Reply(
        content=message.get("content") or "",
        reasoning=message.get("reasoning_content"),
        model_version=payload.get("model", ""),
        finish_reason=choice.get("finish_reason"),
        usage=usage_summary(payload.get("usage") or {}),
        latency_s=latency,
        raw=raw,
        transport_retries=retries,
        system_fingerprint=payload.get("system_fingerprint"),
        tool_calls=message.get("tool_calls") or None,
    )


@dataclass
class MockClient:
    """Offline stand-in. ``respond(messages) -> content`` decides the answer.

    ``respond`` may also return a dict ``{"content": ..., "tool_calls": [...]}`` (explorer
    agent tests); ``tools`` / ``tool_choice`` of each call are kept in ``requests``.
    Usage figures imitate prefix caching: the system message counts as a cache
    hit after the first call with the same system text.
    """

    respond: Callable[[list[dict[str, str]]], str]
    model: str = "mock"
    fingerprint: str | None = "fp_mock"
    _seen: set[str] = field(default_factory=set)
    requests: list[dict] = field(default_factory=list)

    def chat(self, messages: list[dict[str, Any]], *, tools: list[dict] | None = None,
             tool_choice: str | None = None) -> Reply:
        self.requests.append({"tools": tools, "tool_choice": tool_choice})
        answer = self.respond(messages)
        content, tool_calls = (answer.get("content") or "", answer.get("tool_calls")) if isinstance(answer, dict) \
            else (answer, None)
        system = messages[0]["content"]
        prefix = len(system) // 2
        rest = sum(len(m.get("content") or "") for m in messages[1:]) // 2
        hit = prefix if system in self._seen else 0
        self._seen.add(system)
        payload = {
            "model": "mock-version",
            **({"system_fingerprint": self.fingerprint} if self.fingerprint is not None else {}),
            "choices": [{"message": {"content": content, "reasoning_content": "(mock)",
                                     **({"tool_calls": tool_calls} if tool_calls else {})},
                         "finish_reason": "tool_calls" if tool_calls else "stop"}],
            "usage": {"prompt_tokens": prefix + rest, "prompt_cache_hit_tokens": hit,
                      "prompt_cache_miss_tokens": prefix + rest - hit, "completion_tokens": len(content) // 2,
                      "completion_tokens_details": {"reasoning_tokens": 3}},
        }
        return _reply(json.dumps(payload, ensure_ascii=False).encode(), 0.0, 0)
