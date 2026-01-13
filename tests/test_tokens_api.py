from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mindscape_ai.api.app import create_app


def _client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_tokens_breakdown_returns_shape_and_fails_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    import mindscape_ai.api.routes.tokens as tokens_routes
    from mindscape_ai.conport.db import ConPortDbPathError
    from mindscape_ai.mem0.client import Mem0UnavailableError

    # Make this test deterministic across environments:
    # - ConPort: treat as unconfigured
    # - Prompts: treat as unconfigured
    # - Mem0: treat as unavailable
    monkeypatch.setattr(
        tokens_routes,
        "resolve_conport_db_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConPortDbPathError("no db")),
    )
    monkeypatch.setattr(tokens_routes, "resolve_prompt_dirs", lambda *, app_id: [])
    monkeypatch.setattr(
        tokens_routes,
        "get_mem0_client",
        lambda: (_ for _ in ()).throw(Mem0UnavailableError("mem0 not installed")),
    )

    client = _client()
    resp = client.get("/api/v1/tokens/breakdown")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["sources"]["conport"]["configured"] is False
    assert payload["sources"]["prompts"]["configured"] is False
    assert payload["sources"]["mem0"]["configured"] is False

    # Totals should still be present.
    assert "total" in payload
    assert "approx_tokens" in payload["total"]
    assert isinstance(payload["total"]["approx_tokens"], int)


def test_tokens_breakdown_validates_app_id() -> None:
    client = _client()
    resp = client.get("/api/v1/tokens/breakdown", params={"app_id": "bad/app"})
    assert resp.status_code == 400


def test_tokens_breakdown_validates_user_id() -> None:
    client = _client()
    resp = client.get("/api/v1/tokens/breakdown", params={"user_id": "bad/user"})
    assert resp.status_code == 400


def test_tokens_breakdown_validates_project_id() -> None:
    client = _client()
    resp = client.get("/api/v1/tokens/breakdown", params={"project_id": "bad/project"})
    assert resp.status_code == 400
