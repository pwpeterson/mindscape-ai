from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mindscape_ai.api.app import create_app
from mindscape_ai.api.routes.events import _stream_events


class _DummyRequest:
    async def is_disconnected(self) -> bool:
        return False


@pytest.mark.anyio
async def test_events_stream_generator_emits_retry_hello_and_heartbeat() -> None:
    # Unit-test the generator directly to avoid transport buffering/hangs that can
    # occur when testing an infinite SSE stream over TestClient/ASGITransport.
    req = _DummyRequest()

    gen = _stream_events(req, heartbeat_seconds=5)

    retry = (await anext(gen)).decode("utf-8")
    hello = (await anext(gen)).decode("utf-8")
    heartbeat = (await anext(gen)).decode("utf-8")

    await gen.aclose()

    assert "retry:" in retry

    assert "event: hello" in hello
    assert '"type":"hello"' in hello

    assert "event: heartbeat" in heartbeat
    assert '"type":"heartbeat"' in heartbeat


def test_openapi_includes_events_stream() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/openapi.json")
    assert resp.status_code == 200

    payload = resp.json()
    paths = payload.get("paths", {})
    assert "/api/v1/events/stream" in paths
