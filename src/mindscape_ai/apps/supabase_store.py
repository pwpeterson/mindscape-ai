"""Supabase-backed apps registry for Mindscape-AI.

This module treats Supabase as the source-of-truth for apps Mindscape manages.

Key behaviors:
- List apps for the UI dropdown (no filesystem paths in responses).
- CRUD operations for apps (server-side only, should be write-gated at API layer).
- Resolve `app_id -> conport_db_path` for ConPort routes using stored `root_path`.

Security notes:
- The backend uses the Supabase service role key (server-side).
- Do not return root_path / conport db paths to browser clients.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from mindscape_ai.supabase.client import SupabaseUnavailableError, get_supabase_client


class AppStoreError(RuntimeError):
    """Raised when an apps store operation fails."""


@dataclass(frozen=True)
class MindscapeApp:
    """App record returned to UI/API callers (no sensitive paths)."""

    app_id: str
    display_name: str | None
    enabled: bool
    sort_order: int
    has_conport: bool


@dataclass(frozen=True)
class MindscapeAppRegistry:
    """App record for the Apps Manager UI (includes paths from the registry table).

    NOTE: This is intended for the admin/manager panel where showing `root_path` is useful.
    """

    app_id: str
    display_name: str | None
    enabled: bool
    sort_order: int
    root_path: str
    has_conport: bool


@dataclass(frozen=True)
class MindscapeAppInternal:
    """Internal app record (includes paths)."""

    app_id: str
    display_name: str | None
    enabled: bool
    sort_order: int
    root_path: Path


def _resolve_conport_db_for_root(root_path: Path) -> Path:
    return (root_path / "context_portal" / "context.db").resolve()


def _has_conport_db(root_path: Path) -> bool:
    db = _resolve_conport_db_for_root(root_path)
    return db.exists() and db.is_file()


def _row_to_internal(row: dict[str, Any]) -> MindscapeAppInternal:
    app_id = row.get("app_id")
    root_path = row.get("root_path")
    if not isinstance(app_id, str) or not app_id.strip():
        raise AppStoreError("Invalid app_id in DB row")
    if not isinstance(root_path, str) or not root_path.strip():
        raise AppStoreError("Invalid root_path in DB row")

    display_name = row.get("display_name")
    if display_name is not None and not isinstance(display_name, str):
        display_name = None

    enabled = bool(row.get("enabled", True))
    sort_order_raw = row.get("sort_order", 0)
    sort_order = int(sort_order_raw) if isinstance(sort_order_raw, (int, float, str)) else 0

    return MindscapeAppInternal(
        app_id=app_id.strip(),
        display_name=display_name.strip() if isinstance(display_name, str) and display_name.strip() else None,
        enabled=enabled,
        sort_order=sort_order,
        root_path=Path(root_path).expanduser(),
    )


def _internal_to_public(app: MindscapeAppInternal) -> MindscapeApp:
    return MindscapeApp(
        app_id=app.app_id,
        display_name=app.display_name,
        enabled=app.enabled,
        sort_order=app.sort_order,
        has_conport=_has_conport_db(app.root_path),
    )


def _internal_to_registry(app: MindscapeAppInternal) -> MindscapeAppRegistry:
    return MindscapeAppRegistry(
        app_id=app.app_id,
        display_name=app.display_name,
        enabled=app.enabled,
        sort_order=app.sort_order,
        root_path=str(app.root_path.expanduser().resolve()),
        has_conport=_has_conport_db(app.root_path),
    )


def list_apps_from_supabase(*, include_disabled: bool = False) -> list[MindscapeApp]:
    """List apps from Supabase for use in the UI dropdown."""
    client = get_supabase_client()

    query = client.table("mindscape_ai_apps").select(
        "app_id,display_name,enabled,sort_order,root_path"
    )

    if not include_disabled:
        query = query.eq("enabled", True)

    # Stable ordering
    try:
        resp = query.order("sort_order", desc=False).order("app_id", desc=False).execute()
    except httpx.HTTPError as exc:
        # Treat connectivity issues (DNS, refused, timeouts) as "Supabase unavailable" so API
        # routes can fall back to legacy app discovery instead of returning 500.
        raise SupabaseUnavailableError("Supabase is unreachable (apps registry).") from exc

    data = getattr(resp, "data", None)

    if not isinstance(data, list):
        raise AppStoreError("Unexpected response from Supabase apps list")

    out_internal = [_row_to_internal(r) for r in data if isinstance(r, dict)]
    return [_internal_to_public(a) for a in out_internal]


def list_apps_registry_from_supabase(*, include_disabled: bool = True) -> list[MindscapeAppRegistry]:
    """List full app registry rows (including root_path) from Supabase.

    Intended for the Apps Manager panel (admin-ish UI), not for the global dropdown.
    """
    client = get_supabase_client()

    query = client.table("mindscape_ai_apps").select(
        "app_id,display_name,enabled,sort_order,root_path"
    )

    if not include_disabled:
        query = query.eq("enabled", True)

    try:
        resp = query.order("sort_order", desc=False).order("app_id", desc=False).execute()
    except httpx.HTTPError as exc:
        raise SupabaseUnavailableError("Supabase is unreachable (apps registry).") from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list):
        raise AppStoreError("Unexpected response from Supabase apps list")

    out_internal = [_row_to_internal(r) for r in data if isinstance(r, dict)]
    return [_internal_to_registry(a) for a in out_internal]


def resolve_conport_db_path_from_supabase(app_id: str) -> Path:
    """Resolve `app_id` -> <root_path>/context_portal/context.db.

    Used by ConPort routes in app-scoped mode.
    """
    client = get_supabase_client()

    try:
        resp = (
            client.table("mindscape_ai_apps")
            .select("app_id,root_path,enabled")
            .eq("app_id", app_id)
            .limit(1)
            .execute()
        )
    except httpx.HTTPError as exc:
        raise SupabaseUnavailableError("Supabase is unreachable (apps lookup).") from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list) or not data:
        raise AppStoreError(f"Unknown app_id: {app_id}")

    row = data[0]
    if not isinstance(row, dict):
        raise AppStoreError("Unexpected response row for app lookup")

    enabled = bool(row.get("enabled", True))
    if not enabled:
        raise AppStoreError(f"App is disabled: {app_id}")

    root_raw = row.get("root_path")
    if not isinstance(root_raw, str) or not root_raw.strip():
        raise AppStoreError(f"Invalid root_path for app_id: {app_id}")

    db_path = _resolve_conport_db_for_root(Path(root_raw).expanduser())
    if db_path.suffix.lower() != ".db":
        raise AppStoreError("Resolved ConPort DB must end with '.db'.")
    if not db_path.exists() or not db_path.is_file():
        raise AppStoreError("Resolved ConPort DB not found.")
    return db_path


def create_app_in_supabase(
    *,
    app_id: str,
    root_path: str,
    display_name: str | None = None,
    enabled: bool = True,
    sort_order: int = 0,
) -> MindscapeApp:
    client = get_supabase_client()

    payload: dict[str, Any] = {
        "app_id": app_id,
        "root_path": root_path,
        "enabled": bool(enabled),
        "sort_order": int(sort_order),
    }
    if display_name is not None:
        payload["display_name"] = display_name

    try:
        resp = client.table("mindscape_ai_apps").insert(payload).execute()
    except httpx.HTTPError as exc:
        raise SupabaseUnavailableError("Supabase is unreachable (apps insert).") from exc
    data = getattr(resp, "data", None)

    if not isinstance(data, list) or not data:
        raise AppStoreError("Unexpected response from Supabase insert")

    internal = _row_to_internal(data[0])
    return _internal_to_public(internal)


def update_app_in_supabase(
    *,
    app_id: str,
    patch: dict[str, Any],
) -> MindscapeApp:
    client = get_supabase_client()

    allowed: dict[str, Any] = {}
    for key in ("display_name", "root_path", "enabled", "sort_order"):
        if key in patch:
            allowed[key] = patch[key]

    if not allowed:
        raise AppStoreError("No supported fields to update")

    try:
        resp = client.table("mindscape_ai_apps").update(allowed).eq("app_id", app_id).execute()
    except httpx.HTTPError as exc:
        raise SupabaseUnavailableError("Supabase is unreachable (apps update).") from exc
    data = getattr(resp, "data", None)

    if not isinstance(data, list) or not data:
        raise AppStoreError("App not found (or no update returned)")

    internal = _row_to_internal(data[0])
    return _internal_to_public(internal)


def delete_app_in_supabase(*, app_id: str) -> int:
    client = get_supabase_client()
    try:
        resp = client.table("mindscape_ai_apps").delete().eq("app_id", app_id).execute()
    except httpx.HTTPError as exc:
        raise SupabaseUnavailableError("Supabase is unreachable (apps delete).") from exc
    data = getattr(resp, "data", None)

    # supabase-py returns deleted rows in data; count them.
    if isinstance(data, list):
        return len(data)
    return 0


__all__ = [
    "AppStoreError",
    "MindscapeApp",
    "MindscapeAppRegistry",
    "SupabaseUnavailableError",
    "create_app_in_supabase",
    "delete_app_in_supabase",
    "list_apps_from_supabase",
    "list_apps_registry_from_supabase",
    "resolve_conport_db_path_from_supabase",
    "update_app_in_supabase",
]