from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mindscape_ai.api.app import create_app


def test_health_ok() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_conport_now_ok_default_db() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/conport/now")
    assert resp.status_code == 200

    payload = resp.json()
    assert "db" in payload
    assert "product_context" in payload
    assert "active_context" in payload
    assert "recent_activity" in payload

    recent = payload["recent_activity"]
    assert "decisions" in recent
    assert "progress_entries" in recent
    assert "system_patterns" in recent
    assert "custom_data" in recent
    assert "links" in recent


def test_conport_now_ok_when_cwd_not_repo_root(tmp_path: Path, monkeypatch) -> None:
    # T007 regression: API must resolve the default DB path even if CWD is elsewhere.
    monkeypatch.chdir(tmp_path)

    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/conport/now")
    assert resp.status_code == 200


def test_conport_search_rejects_empty_query() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/conport/search", params={"q": ""})
    # FastAPI validation error
    assert resp.status_code == 422


def test_conport_db_traversal_rejected() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/conport/now", params={"db": "../context_portal/context.db"})
    assert resp.status_code == 400


def test_conport_db_too_long_rejected() -> None:
    app = create_app()
    client = TestClient(app)

    # T017: DoS guardrail for pathological db query param length
    resp = client.get("/api/v1/conport/now", params={"db": "x" * 5000})
    assert resp.status_code == 400


def test_conport_db_invalid_characters_rejected() -> None:
    app = create_app()
    client = TestClient(app)

    # T017: avoid URI/query-string injection attempts in db param
    resp = client.get("/api/v1/conport/now", params={"db": "context_portal/context.db?mode=rw"})
    assert resp.status_code == 400


def test_progress_patch_write_gated_by_default() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.patch("/api/v1/conport/progress/1", json={"status": "DONE"})
    assert resp.status_code == 403


def test_views_put_write_gated_by_default() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.put("/api/v1/conport/views/example", json={"hello": "world"})
    assert resp.status_code == 403


def test_conport_dashboard_ok_default_db() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/conport/dashboard")
    assert resp.status_code == 200

    payload = resp.json()
    assert "db" in payload
    assert "progress" in payload
    assert "graph_health" in payload
    assert "by_status" in payload["progress"]


def test_conport_progress_list_ok_default_db() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/conport/progress", params={"limit": 5})
    assert resp.status_code == 200

    payload = resp.json()
    assert "db" in payload
    assert "progress_entries" in payload
    assert isinstance(payload["progress_entries"], list)


def test_conport_links_list_ok_default_db() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/conport/links", params={"limit": 5})
    assert resp.status_code == 200

    payload = resp.json()
    assert "db" in payload
    assert "links" in payload
    assert isinstance(payload["links"], list)


def test_conport_item_ok_progress_default_db() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/conport/item", params={"type": "progress", "id": 1})
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["type"] == "progress"
    assert "item" in payload
    assert payload["item"]["id"] == 1


def test_conport_item_404_when_missing() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/conport/item", params={"type": "progress", "id": 999999})
    assert resp.status_code == 404


def test_conport_db_traversal_rejected_across_endpoints() -> None:
    app = create_app()
    client = TestClient(app)

    bad_db = "../context_portal/context.db"

    # Ensure multiple endpoints consistently reject traversal attempts.
    resp1 = client.get("/api/v1/conport/dashboard", params={"db": bad_db})
    assert resp1.status_code == 400

    resp2 = client.get("/api/v1/conport/progress", params={"db": bad_db})
    assert resp2.status_code == 400

    resp3 = client.get("/api/v1/conport/links", params={"db": bad_db})
    assert resp3.status_code == 400

    resp4 = client.get("/api/v1/conport/item", params={"db": bad_db, "type": "progress", "id": 1})
    assert resp4.status_code == 400
