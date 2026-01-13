from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mindscape_ai.api.app import create_app
from mindscape_ai.apps.supabase_store import AppStoreError, MindscapeApp, SupabaseUnavailableError


def _client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_apps_list_falls_back_to_env_when_supabase_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    # Supabase path is preferred; if unavailable we fall back to MINDSCAPE_APP_ROOTS.
    # Disable the "self app" convenience so we can assert the strict fail-closed baseline.
    import mindscape_ai.api.routes.apps as apps_routes

    monkeypatch.setattr(
        apps_routes,
        "list_apps_from_supabase",
        lambda *, include_disabled=False: (_ for _ in ()).throw(SupabaseUnavailableError("no supabase")),
    )
    monkeypatch.delenv("MINDSCAPE_APP_ROOTS", raising=False)
    monkeypatch.setenv("MINDSCAPE_INCLUDE_SELF_APP", "false")

    client = _client()
    resp = client.get("/api/v1/apps")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["apps"] == []
    assert payload["source"]["configured"] is False
    assert payload["source"]["env"] == "MINDSCAPE_APP_ROOTS"
    assert payload["source"]["count"] == 0


def test_apps_list_includes_self_app_when_not_configured_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Local/dev UX: even without Supabase + MINDSCAPE_APP_ROOTS, the API should include
    # this Mindscape-AI instance so the UI dropdown isn't empty.
    import mindscape_ai.api.routes.apps as apps_routes

    monkeypatch.setattr(
        apps_routes,
        "list_apps_from_supabase",
        lambda *, include_disabled=False: (_ for _ in ()).throw(SupabaseUnavailableError("no supabase")),
    )
    monkeypatch.delenv("MINDSCAPE_APP_ROOTS", raising=False)
    monkeypatch.delenv("MINDSCAPE_INCLUDE_SELF_APP", raising=False)

    client = _client()
    resp = client.get("/api/v1/apps")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["apps"] == [{"app_id": "mindscape-ai", "has_conport": True}]
    assert payload["source"]["configured"] is False
    assert payload["source"]["env"] == "MINDSCAPE_APP_ROOTS"
    assert payload["source"]["count"] == 1


def test_apps_list_uses_supabase_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    import mindscape_ai.api.routes.apps as apps_routes

    monkeypatch.setattr(
        apps_routes,
        "list_apps_from_supabase",
        lambda *, include_disabled=False: [
            MindscapeApp(
                app_id="mindscape-ai",
                display_name="Mindscape AI",
                enabled=True,
                sort_order=0,
                has_conport=True,
            )
        ],
    )

    client = _client()
    resp = client.get("/api/v1/apps")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["apps"] == [{"app_id": "mindscape-ai", "has_conport": True}]
    assert payload["source"]["type"] == "supabase"
    assert payload["source"]["table"] == "mindscape_ai_apps"
    assert payload["source"]["configured"] is True
    assert payload["source"]["count"] == 1


def test_apps_create_is_write_gated_by_default(tmp_path: Path) -> None:
    client = _client()
    resp = client.post(
        "/api/v1/apps",
        json={
            "app_id": "test-app",
            "root_path": str(tmp_path),
        },
    )
    assert resp.status_code == 403


def test_apps_create_validates_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mindscape_ai.api.routes.apps as apps_routes

    monkeypatch.setenv("MINDSCAPE_APPS_WRITE", "true")

    # Invalid app_id characters
    client = _client()
    resp = client.post(
        "/api/v1/apps",
        json={
            "app_id": "bad/app",
            "root_path": str(tmp_path),
        },
    )
    assert resp.status_code == 400

    # Non-absolute root_path rejected
    rel = tmp_path / "rel"
    rel.mkdir()
    resp2 = client.post(
        "/api/v1/apps",
        json={
            "app_id": "ok-app",
            "root_path": "relative/path",
        },
    )
    assert resp2.status_code == 400

    # root_path must exist and be a directory
    missing = tmp_path / "missing"
    resp3 = client.post(
        "/api/v1/apps",
        json={
            "app_id": "ok-app",
            "root_path": str(missing),
        },
    )
    assert resp3.status_code == 400

    # Restore baseline so later tests aren't affected.
    monkeypatch.delenv("MINDSCAPE_APPS_WRITE", raising=False)

    # Ensure monkeypatch import isn't flagged as unused
    assert apps_routes is not None


def test_apps_create_calls_store_when_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mindscape_ai.api.routes.apps as apps_routes

    monkeypatch.setenv("MINDSCAPE_APPS_WRITE", "true")

    created: dict[str, object] = {}

    def _fake_create(
        *,
        app_id: str,
        root_path: str,
        display_name: str | None = None,
        enabled: bool = True,
        sort_order: int = 0,
    ) -> MindscapeApp:
        created.update(
            {
                "app_id": app_id,
                "root_path": root_path,
                "display_name": display_name,
                "enabled": enabled,
                "sort_order": sort_order,
            }
        )
        return MindscapeApp(
            app_id=app_id,
            display_name=display_name,
            enabled=enabled,
            sort_order=sort_order,
            has_conport=True,
        )

    monkeypatch.setattr(apps_routes, "create_app_in_supabase", _fake_create)

    client = _client()
    resp = client.post(
        "/api/v1/apps",
        json={
            "app_id": "test-app",
            "root_path": str(tmp_path),
            "display_name": "Test App",
            "enabled": True,
            "sort_order": 7,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["app"]["app_id"] == "test-app"

    assert created["app_id"] == "test-app"
    assert created["root_path"] == str(Path(str(tmp_path)).resolve())
    assert created["display_name"] == "Test App"
    assert created["enabled"] is True
    assert created["sort_order"] == 7


def test_apps_patch_is_write_gated_by_default() -> None:
    client = _client()
    resp = client.patch("/api/v1/apps/mindscape-ai", json={"enabled": False})
    assert resp.status_code == 403


def test_apps_patch_calls_store_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import mindscape_ai.api.routes.apps as apps_routes

    monkeypatch.setenv("MINDSCAPE_APPS_WRITE", "true")

    def _fake_update(*, app_id: str, patch: dict[str, object]) -> MindscapeApp:
        assert app_id == "mindscape-ai"
        assert patch["enabled"] is False
        assert patch["sort_order"] == 3
        assert patch["display_name"] == "Renamed"
        return MindscapeApp(
            app_id=app_id,
            display_name=patch.get("display_name"),  # type: ignore[arg-type]
            enabled=patch.get("enabled", True),  # type: ignore[arg-type]
            sort_order=patch.get("sort_order", 0),  # type: ignore[arg-type]
            has_conport=True,
        )

    monkeypatch.setattr(apps_routes, "update_app_in_supabase", _fake_update)

    client = _client()
    resp = client.patch(
        "/api/v1/apps/mindscape-ai",
        json={"enabled": False, "sort_order": 3, "display_name": "Renamed"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["app"]["app_id"] == "mindscape-ai"


def test_apps_patch_rejects_empty_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    import mindscape_ai.api.routes.apps as apps_routes

    monkeypatch.setenv("MINDSCAPE_APPS_WRITE", "true")

    def _fake_update(*, app_id: str, patch: dict[str, object]) -> MindscapeApp:
        raise AppStoreError("No supported fields to update")

    monkeypatch.setattr(apps_routes, "update_app_in_supabase", _fake_update)

    client = _client()
    resp = client.patch("/api/v1/apps/mindscape-ai", json={})
    assert resp.status_code == 400


def test_apps_delete_is_write_gated_by_default() -> None:
    client = _client()
    resp = client.delete("/api/v1/apps/mindscape-ai")
    assert resp.status_code == 403


def test_apps_delete_calls_store_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import mindscape_ai.api.routes.apps as apps_routes

    monkeypatch.setenv("MINDSCAPE_APPS_WRITE", "true")
    monkeypatch.setattr(apps_routes, "delete_app_in_supabase", lambda *, app_id: 1)

    client = _client()
    resp = client.delete("/api/v1/apps/mindscape-ai")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["deleted"] == 1
    assert payload["app_id"] == "mindscape-ai"