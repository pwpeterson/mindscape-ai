from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mindscape_ai.api.app import create_app
from mindscape_ai.supabase.client import SupabaseUnavailableError


def _client() -> TestClient:
    app = create_app()
    return TestClient(app)


class _FakeResp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table: str, data):
        self._table = table
        self._data = data

    def select(self, _cols: str):
        return self

    def eq(self, _col: str, _value):
        return self

    def gte(self, _col: str, _value):
        return self

    def order(self, _col: str, desc: bool = False):  # noqa: FBT001,FBT002
        _ = desc
        return self

    def limit(self, _n: int):
        return self

    def execute(self):
        return _FakeResp(self._data)


class _FakeSupabaseClient:
    def __init__(self, *, events_data, daily_data):
        self._events_data = events_data
        self._daily_data = daily_data

    def table(self, name: str) -> _FakeQuery:
        if name == "llm_usage_events":
            return _FakeQuery(name, self._events_data)
        if name == "llm_usage_daily":
            return _FakeQuery(name, self._daily_data)
        raise AssertionError(f"Unexpected table name: {name}")


def test_llm_usage_events_validates_app_id() -> None:
    client = _client()
    resp = client.get("/api/v1/llm-usage/events", params={"app_id": "bad/app"})
    assert resp.status_code == 400


def test_llm_usage_daily_validates_app_id() -> None:
    client = _client()
    resp = client.get("/api/v1/llm-usage/daily", params={"app_id": "bad/app"})
    assert resp.status_code == 400


def test_llm_usage_events_returns_503_when_supabase_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mindscape_ai.api.routes.llm_usage as llm_usage_routes

    monkeypatch.setattr(
        llm_usage_routes,
        "get_supabase_client",
        lambda: (_ for _ in ()).throw(SupabaseUnavailableError("no supabase")),
    )

    client = _client()
    resp = client.get("/api/v1/llm-usage/events")
    assert resp.status_code == 503


def test_llm_usage_daily_returns_503_when_supabase_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mindscape_ai.api.routes.llm_usage as llm_usage_routes

    monkeypatch.setattr(
        llm_usage_routes,
        "get_supabase_client",
        lambda: (_ for _ in ()).throw(SupabaseUnavailableError("no supabase")),
    )

    client = _client()
    resp = client.get("/api/v1/llm-usage/daily")
    assert resp.status_code == 503


def test_llm_usage_events_returns_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mindscape_ai.api.routes.llm_usage as llm_usage_routes

    fake_events = [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "request_id": "req_1",
            "app_id": "mindscape-ai",
            "task": "t:prompts",
            "user_id": "default",
            "agent_id": "roo",
            "project_id": "mindscape-ai",
            "provider": "openai",
            "model": "gpt-5.2",
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
            "estimated_cost": "0.001234",
            "prompt_sha256": None,
            "prompt_chars": 123,
            "message_count": 2,
            "route": "/v1/chat/completions",
            "status_code": 200,
            "latency_ms": 345,
            "stream": False,
            "created_at": "2026-01-15T00:00:00+00:00",
        }
    ]
    fake_daily = [
        {
            "day": "2026-01-15T00:00:00+00:00",
            "app_id": "mindscape-ai",
            "task": "t:prompts",
            "provider": "openai",
            "model": "gpt-5.2",
            "requests": 1,
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
            "estimated_cost": "0.001234",
        }
    ]

    monkeypatch.setattr(
        llm_usage_routes,
        "get_supabase_client",
        lambda: _FakeSupabaseClient(events_data=fake_events, daily_data=fake_daily),
    )

    client = _client()
    resp = client.get("/api/v1/llm-usage/events", params={"app_id": "mindscape-ai"})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["source"]["table"] == "llm_usage_events"
    assert payload["count"] == 1
    assert isinstance(payload["events"], list)
    assert payload["events"][0]["request_id"] == "req_1"
    assert payload["events"][0]["total_tokens"] == 30


def test_llm_usage_daily_returns_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mindscape_ai.api.routes.llm_usage as llm_usage_routes

    fake_events = []
    fake_daily = [
        {
            "day": "2026-01-15T00:00:00+00:00",
            "app_id": "mindscape-ai",
            "task": "t:prompts",
            "provider": "openai",
            "model": "gpt-5.2",
            "requests": 2,
            "input_tokens": 100,
            "output_tokens": 200,
            "total_tokens": 300,
            "estimated_cost": "0.012340",
        }
    ]

    monkeypatch.setattr(
        llm_usage_routes,
        "get_supabase_client",
        lambda: _FakeSupabaseClient(events_data=fake_events, daily_data=fake_daily),
    )

    client = _client()
    resp = client.get("/api/v1/llm-usage/daily", params={"app_id": "mindscape-ai"})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["source"]["view"] == "llm_usage_daily"
    assert payload["count"] == 1
    assert isinstance(payload["rows"], list)
    assert payload["rows"][0]["requests"] == 2
    assert payload["rows"][0]["total_tokens"] == 300


def test_llm_raw_prompts_validates_app_id() -> None:
    client = _client()
    resp = client.get("/api/v1/llm-usage/raw-prompts", params={"app_id": "bad/app"})
    assert resp.status_code == 400


def test_llm_raw_prompts_returns_503_when_supabase_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mindscape_ai.api.routes.llm_usage as llm_usage_routes

    monkeypatch.setattr(
        llm_usage_routes,
        "get_supabase_client",
        lambda: (_ for _ in ()).throw(SupabaseUnavailableError("no supabase")),
    )

    client = _client()
    resp = client.get("/api/v1/llm-usage/raw-prompts")
    assert resp.status_code == 503


def test_llm_raw_prompts_returns_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mindscape_ai.api.routes.llm_usage as llm_usage_routes

    fake_raw_prompts = [
        {
            "request_id": "req_raw_1",
            "app_id": "mindscape-ai",
            "task": "t:prompts",
            "provider": "openai",
            "model": "gpt-5.2",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, world!"},
            ],
            "prompt_text": "You are a helpful assistant.\n\nHello, world!",
            "prompt_sha256": "deadbeef",
            "prompt_chars": 44,
            "message_count": 2,
            "metadata": {"note": "test"},
            "created_at": "2026-01-15T12:00:00+00:00",
        }
    ]

    # Extend _FakeSupabaseClient to support llm_raw_prompts table
    class _FakeSupabaseClientWithRaw(_FakeSupabaseClient):
        def __init__(self, *, events_data, daily_data, raw_prompts_data):
            super().__init__(events_data=events_data, daily_data=daily_data)
            self._raw_prompts_data = raw_prompts_data

        def table(self, name: str) -> _FakeQuery:
            if name == "llm_raw_prompts":
                return _FakeQuery(name, self._raw_prompts_data)
            return super().table(name)

    monkeypatch.setattr(
        llm_usage_routes,
        "get_supabase_client",
        lambda: _FakeSupabaseClientWithRaw(
            events_data=[],
            daily_data=[],
            raw_prompts_data=fake_raw_prompts,
        ),
    )

    client = _client()
    resp = client.get("/api/v1/llm-usage/raw-prompts", params={"app_id": "mindscape-ai"})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["source"]["table"] == "llm_raw_prompts"
    assert payload["count"] == 1
    assert isinstance(payload["prompts"], list)
    assert payload["prompts"][0]["request_id"] == "req_raw_1"
    assert payload["prompts"][0]["provider"] == "openai"
    assert payload["prompts"][0]["model"] == "gpt-5.2"
    assert payload["prompts"][0]["prompt_text"] == "You are a helpful assistant.\n\nHello, world!"
    assert isinstance(payload["prompts"][0]["messages"], list)
    assert payload["prompts"][0]["message_count"] == 2
    assert payload["prompts"][0]["prompt_chars"] == 44
    assert payload["prompts"][0]["prompt_sha256"] == "deadbeef"
    assert payload["prompts"][0]["metadata"]["note"] == "test"