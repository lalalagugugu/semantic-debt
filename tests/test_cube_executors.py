"""T16 executors: offline protocol mocks; no Docker, question bank or model API."""

from __future__ import annotations

import asyncio
import io
import json
import sys
import urllib.error
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness import executors as E


@pytest.mark.parametrize("query", [
    "SELECT 1", "-- comment\nSELECT 1;", "WITH a AS (SELECT 1) SELECT * FROM a",
    "SELECT 'DELETE; DROP TABLE sales'", 'SELECT "UPDATE" FROM sales',
    "SELECT $$a; DELETE$$", "SELECT $x$SET readonly=0$x$",
    "SELECT /* outer /* nested */ comment */ 1",
    r"SELECT E'a\'; DELETE; b'",
])
def test_sql_accepts_readonly(query):
    assert E._pg_readonly(query)


@pytest.mark.parametrize("query", [
    "", "SELECT 1; DELETE FROM sales", "DROP TABLE sales", "SET readonly=0",
    "WITH x AS (DELETE FROM sales RETURNING *) SELECT * FROM x",
    "SELECT 1 INTO new_table", "COPY sales TO '/tmp/x'", "EXPLAIN SELECT 1",
    "SELECT 1 /* unclosed", "SELECT $x$unclosed", "SELECT 1;;",
    "SELECT 1 /* outer /* inner */ ; DELETE FROM sales */; DELETE FROM sales",
    r"SELECT '\'; DELETE FROM sales; --'",
])
def test_sql_rejects_before_connecting(monkeypatch, query):
    async def unexpected(**kwargs):
        pytest.fail("Rejected SQL must not open a connection")
    monkeypatch.setattr(psycopg.AsyncConnection, "connect", unexpected)
    assert E.CubeSqlExecutor().execute(query).error_class == E.FORBIDDEN_STATEMENT


def test_sql_protocol_types_and_closed_connection(monkeypatch):
    events = []

    class Cursor:
        description = [SimpleNamespace(name="n", type_code=1700), SimpleNamespace(name="d", type_code=1114)]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            events.append("cursor closed")

        async def execute(self, query):
            events.append(query)

        async def fetchmany(self, size):
            if "fetched" in events:
                return []
            events.append("fetched")
            return [(Decimal("12.50"), datetime(2009, 1, 1))]

    class Connection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            events.append("connection closed")

        def cursor(self):
            return Cursor()

    async def connect(**kwargs):
        assert kwargs["autocommit"] is True
        assert kwargs["password"]  # ephemeral dev response, never persisted
        return Connection()

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", connect)
    result = E.CubeSqlExecutor().execute("SELECT 1")
    assert result.rows == [[Decimal("12.50"), "2009-01-01 00:00:00"]]
    assert result.columns == [{"name": "n", "type": "pg:1700"}, {"name": "d", "type": "pg:1114"}]
    assert events[-2:] == ["cursor closed", "connection closed"]
    assert "result_sha256" in result.summary() and "rows" not in result.summary()


def test_sql_row_limit_and_cleanup(monkeypatch):
    closed = []

    class Cursor:
        description = [SimpleNamespace(name="n", type_code=23)]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            closed.append("cursor")

        async def execute(self, query):
            pass

        async def fetchmany(self, size):
            return [(i,) for i in range(size)]

    class Connection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            closed.append("connection")

        def cursor(self):
            return Cursor()

    async def connect(**kwargs):
        return Connection()

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", connect)
    result = E.CubeSqlExecutor(max_result_rows=1).execute("SELECT 1")
    assert (result.error_class, result.limit, result.rows) == (E.RESOURCE_LIMIT, "result_rows", None)
    assert closed == ["cursor", "connection"]


@pytest.mark.parametrize("exc,expected", [
    (TimeoutError(), E.TIMEOUT),
    (psycopg.OperationalError("transport diagnostics"), E.TRANSPORT_ERROR),
    (psycopg.errors.FeatureNotSupported("unsupported operation"), E.INTERFACE_LIMITATION),
    (psycopg.errors.SyntaxError("syntax error"), E.ENGINE_ERROR),
])
def test_sql_errors(monkeypatch, exc, expected):
    async def connect(**kwargs):
        raise exc
    monkeypatch.setattr(psycopg.AsyncConnection, "connect", connect)
    result = E.CubeSqlExecutor().execute("SELECT 1")
    assert result.error_class == expected and result.rows is None
    if expected == E.TRANSPORT_ERROR:
        assert "diagnostics" not in (result.error or "")


def test_sql_deadline_cancels_query(monkeypatch):
    cancelled = []

    async def query(self, sql):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.append(True)

    monkeypatch.setattr(E.CubeSqlExecutor, "_query", query)
    executor = E.CubeSqlExecutor()
    executor.timeout_s = 0.001
    assert executor.execute("SELECT 1").error_class == E.TIMEOUT
    assert cancelled == [True]


def test_json_wire_format_types_and_time_alias(monkeypatch):
    query = {"measures": ["sales.amount"], "dimensions": ["sales.code"],
             "timeDimensions": [{"dimension": "sales.DateKey", "granularity": "month"}]}
    payload = {"data": [{"sales.code": "001", "sales.DateKey": "2009-01-01T00:00:00.000",
                         "sales.DateKey.month": "2009-01-01T00:00:00.000", "sales.amount": "9007199254740993"}],
               "annotation": {"dimensions": {"sales.code": {"type": "string"}, "sales.DateKey": {"type": "time"}},
                              "timeDimensions": {"sales.DateKey.month": {"type": "time"}, "sales.DateKey": {"type": "time"}},
                              "measures": {"sales.amount": {"type": "number"}}}}
    calls = []

    def urlopen(req, timeout):
        calls.append(req)
        assert req.full_url.endswith("/cubejs-api/v1/load")
        assert json.loads(req.data) == {"query": query}
        assert req.get_method() == "POST" and 0 < timeout <= 120
        response = io.BytesIO(json.dumps(payload).encode())
        response.status = 200
        return response

    monkeypatch.setattr(E.urllib.request, "urlopen", urlopen)
    result = E.CubeJsonExecutor().execute(json.dumps(query))
    assert result.rows == [["001", "2009-01-01 00:00:00", 9007199254740993]]
    assert len(result.columns) == 3 and len(calls) == 1


def test_json_continue_wait_and_empty_result(monkeypatch):
    payloads = [{"error": "Continue wait"}, {"data": [], "annotation": {"measures": {"sales.n": {"type": "number"}}}}]

    def urlopen(req, timeout):
        response = io.BytesIO(json.dumps(payloads.pop(0)).encode())
        response.status = 200
        return response

    monkeypatch.setattr(E.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(E.time, "sleep", lambda value: None)
    result = E.CubeJsonExecutor().execute('{"measures":["sales.n"]}')
    assert result.ok and result.rows == [] and result.columns == [{"name": "sales.n", "type": "number"}]
    assert payloads == []


@pytest.mark.parametrize("query", ["not json", "[]", "null", "42"])
def test_json_invalid_query_does_not_call_endpoint(monkeypatch, query):
    monkeypatch.setattr(E.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("No request expected"))
    assert E.CubeJsonExecutor().execute(query).error_class == E.ENGINE_ERROR


@pytest.mark.parametrize("payload,status,kind", [
    ({"error": "unknown member"}, 400, E.ENGINE_ERROR),
    ({"error": "multi-stage calculation not supported"}, 400, E.INTERFACE_LIMITATION),
    ({"error": "TIMEOUT_EXCEEDED"}, 400, E.TIMEOUT),
    ({"error": "MEMORY_LIMIT_EXCEEDED"}, 400, E.RESOURCE_LIMIT),
    ({"data": []}, 200, E.INVALID_RESPONSE),
    ({"data": [{"n": "oops"}], "annotation": {"measures": {"n": {"type": "number"}}}}, 200, E.INVALID_RESPONSE),
    ([], 200, E.INVALID_RESPONSE),
    ({"data": [], "annotation": {"measures": []}}, 200, E.INVALID_RESPONSE),
    ({"data": [], "annotation": {"measures": {"n": None}}}, 200, E.INVALID_RESPONSE),
])
def test_json_response_errors_are_not_retried(monkeypatch, payload, status, kind):
    calls = []

    def urlopen(req, timeout):
        calls.append(req)
        stream = io.BytesIO(json.dumps(payload).encode())
        if status >= 400:
            raise urllib.error.HTTPError(req.full_url, status, "error", {}, stream)
        stream.status = status
        return stream

    monkeypatch.setattr(E.urllib.request, "urlopen", urlopen)
    result = E.CubeJsonExecutor().execute("{}")
    assert result.error_class == kind and result.rows is None and len(calls) == 1


@pytest.mark.parametrize("exc,kind", [
    (TimeoutError(), E.TIMEOUT), (urllib.error.URLError(TimeoutError()), E.TIMEOUT),
    (urllib.error.URLError("offline"), E.TRANSPORT_ERROR),
])
def test_json_transport_failure(monkeypatch, exc, kind):
    def urlopen(*args, **kwargs):
        raise exc
    monkeypatch.setattr(E.urllib.request, "urlopen", urlopen)
    assert E.CubeJsonExecutor().execute("{}").error_class == kind


def test_json_continue_wait_has_total_deadline(monkeypatch):
    ticks = iter([0, 0, 0.5, 2, 2])
    monkeypatch.setattr(E.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(E.time, "sleep", lambda value: None)

    def urlopen(*args, **kwargs):
        response = io.BytesIO(b'{"error":"Continue wait"}')
        response.status = 200
        return response

    monkeypatch.setattr(E.urllib.request, "urlopen", urlopen)
    assert E.CubeJsonExecutor(timeout_s=1).execute("{}").error_class == E.TIMEOUT


def test_json_row_limit(monkeypatch):
    def urlopen(*args, **kwargs):
        response = io.BytesIO(b'{"data":[{"n":"1"},{"n":"2"}],"annotation":{"measures":{"n":{"type":"number"}}}}')
        response.status = 200
        return response

    monkeypatch.setattr(E.urllib.request, "urlopen", urlopen)
    result = E.CubeJsonExecutor(max_result_rows=1).execute("{}")
    assert (result.error_class, result.limit, result.rows) == (E.RESOURCE_LIMIT, "result_rows", None)
