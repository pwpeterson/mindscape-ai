from __future__ import annotations

from fastapi.testclient import TestClient

from mindscape_ai.api.app import create_app


def test_mem0_health_degraded_when_mem0_unavailable() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/mem0/health")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["status"] in {"ok", "degraded"}

    # In CI/dev environments where mem0 isn't installed, we expect degraded.
    if payload["status"] == "degraded":
        assert payload["mem0"] == "unavailable"
        assert "detail" in payload


def test_mem0_list_memories_returns_503_when_mem0_unavailable() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/mem0/memories")
    if resp.status_code == 503:
        detail = resp.json().get("detail", "")
        assert "mem0" in detail.lower()
    else:
        # If mem0 is installed locally, just ensure schema shape.
        payload = resp.json()
        assert payload["success"] is True
        assert "memories" in payload


def test_mem0_search_empty_query_rejected() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/mem0/search", params={"q": ""})
    # FastAPI validation
    assert resp.status_code == 422


def test_mem0_app_id_validation_rejects_invalid_characters() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/mem0/memories", params={"app_id": "bad/app"})
    assert resp.status_code == 400


def test_mem0_project_id_validation_rejects_invalid_characters() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/mem0/memories", params={"project_id": "bad/project"})
    assert resp.status_code == 400


def test_mem0_write_endpoints_are_gated_by_default_add() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.post("/api/v1/mem0/memories", json={"content": "hello"})
    assert resp.status_code == 403


def test_mem0_write_endpoints_are_gated_by_default_delete_all() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.post("/api/v1/mem0/delete-all", json={"confirm": True})
    assert resp.status_code == 403
