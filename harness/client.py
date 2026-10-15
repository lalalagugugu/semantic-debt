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

import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Protocol

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


class APIError(RuntimeError):
    def __init__(self, message: str, transport_retries: int = 0) -> None:
        super().__init__(message)
        self.transport_retries = transport_retries


class ModelClient(Protocol):
    model: str

    def chat(self, messages: list[dict[str, str]]) -> Reply: ...


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
                 request_timeout_s: float = 900.0, url: str = API_URL) -> None:
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")
        self._key = key
        self.model = model
        self.effort = effort
        self.max_attempts = max_attempts
        self.request_timeout_s = request_timeout_s
        self.url = url

    def chat(self, messages: list[dict[str, str]]) -> Reply:
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "thinking": {"type": "enabled"},
            "reasoning_effort": self.effort,
            "stream": False,
        }, ensure_ascii=False).encode()
        retries = 0
        last_error = ""
        for attempt in range(self.max_attempts):
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
            except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as exc:
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
    )


@dataclass
class MockClient:
    """Offline stand-in. ``respond(messages) -> content`` decides the answer.

    Usage figures imitate prefix caching: the system message counts as a cache
    hit after the first call with the same system text.
    """

    respond: Callable[[list[dict[str, str]]], str]
    model: str = "mock"
    _seen: set[str] = field(default_factory=set)

    def chat(self, messages: list[dict[str, str]]) -> Reply:
        content = self.respond(messages)
        system = messages[0]["content"]
        prefix = len(system) // 2
        rest = sum(len(m["content"]) for m in messages[1:]) // 2
        hit = prefix if system in self._seen else 0
        self._seen.add(system)
        payload = {
            "model": "mock-version",
            "choices": [{"message": {"content": content, "reasoning_content": "(mock)"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prefix + rest, "prompt_cache_hit_tokens": hit,
                      "prompt_cache_miss_tokens": prefix + rest - hit, "completion_tokens": len(content) // 2,
                      "completion_tokens_details": {"reasoning_tokens": 3}},
        }
        return _reply(json.dumps(payload, ensure_ascii=False).encode(), 0.0, 0)
