"""SQLite-backed apps registry for Mindscape-AI (fallback when Supabase is unavailable).

This store is intentionally simple and local-dev friendly:

- It persists a registry of `app_id -> root_path` on disk in a SQLite file.
- It is used as a fallback when Supabase isn't configured (or is unavailable).
- It NEVER returns filesystem paths to browser clients; paths are for internal resolution only.

DB location:
- Env override: MINDSCAPE_APPS_SQLITE_DB (absolute or relative to workspace root)
- Default: <workspace_root>/context_portal/apps_registry.db

Security notes:
- Root paths are validated at the API layer before being inserted.
- App ids are validated at the API layer before being inserted.
- This file is expected to be ignored by git (repo already ignores *.db).
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mindscape_ai.apps.path_mapping import map_runtime_path
from mindscape_ai.apps.supabase_store import AppStoreError, MindscapeApp
from mindscape_ai.conport.db import find_workspace_root

_TABLE = "mindscape_ai_apps"


@dataclass(frozen=True)
class _AppRow:
    app_id: str
    root_path: Path
    display_name: str | None
    enabled: bool
    sort_order: int


def _bool_int(v: bool) -> int:
    return 1 if v else 0


def _apps_db_path(*, start: Path | None = None) -> Path:
    """Return the SQLite DB path for the local apps registry.

    If MINDSCAPE_APPS_SQLITE_DB is relative, it is resolved relative to the workspace root.
    """
    root = find_workspace_root(start=start or Path(__file__))
    raw = os.getenv("MINDSCAPE_APPS_SQLITE_DB", "").strip()

    if raw:
        p = Path(raw).expanduser()
        return (p if p.is_absolute() else (root / p)).resolve()

    return (root / "context_portal" / "apps_registry.db").resolve()


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path.as_posix(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    # Keep schema minimal; timestamps are not required for current UX/tests.
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            app_id TEXT PRIMARY KEY,
            display_name TEXT NULL,
            root_path TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS {_TABLE}_enabled_sort_idx ON {_TABLE} (enabled, sort_order, app_id)"
    )
    conn.commit()


def _rows_to_apps(rows: Iterable[sqlite3.Row]) -> list[MindscapeApp]:
    out: list[MindscapeApp] = []
    for r in rows:
        try:
            app_id = str(r["app_id"])
            root_path = Path(str(r["root_path"])).expanduser()
        except Exception as exc:  # noqa: BLE001
            raise AppStoreError("Invalid row in local apps registry") from exc

        display_name = r["display_name"]
        if display_name is not None and not isinstance(display_name, str):
            display_name = None

        enabled = bool(int(r["enabled"]) if r["enabled"] is not None else 1)
        sort_order = int(r["sort_order"]) if r["sort_order"] is not None else 0

        has_conport = _has_conport_db(root_path)

        out.append(
            MindscapeApp(
                app_id=app_id,
                display_name=display_name.strip() if isinstance(display_name, str) and display_name.strip() else None,
                enabled=enabled,
                sort_order=sort_order,
                has_conport=has_conport,
            )
        )

    return out


def _runtime_root(root_path: Path) -> Path:
    return map_runtime_path(root_path)


def _candidate_conport_db_paths(root_path: Path) -> list[Path]:
    root = root_path.expanduser()

    candidates: list[Path] = []

    if root.name == "context_portal":
        candidates.append((root / "context.db").resolve())

    candidates.append((root / "context_portal" / "context.db").resolve())

    for p in root.glob("*/context_portal/context.db"):
        candidates.append(p.resolve())
    for p in root.glob("*/*/context_portal/context.db"):
        candidates.append(p.resolve())

    seen: set[str] = set()
    out: list[Path] = []
    for c in candidates:
        key = c.as_posix()
        if key in seen:
            continue
        seen.add(key)
        out.append(c)

    return out


def _find_conport_db_for_root(root_path: Path) -> Path | None:
    for candidate in _candidate_conport_db_paths(root_path):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _has_conport_db(root_path: Path) -> bool:
    runtime_root = _runtime_root(root_path)
    return _find_conport_db_for_root(runtime_root) is not None


def list_apps_from_sqlite(*, include_disabled: bool = False) -> list[MindscapeApp]:
    """List apps from the local SQLite registry for the UI dropdown."""
    db_path = _apps_db_path()
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)

        where = "" if include_disabled else "WHERE enabled = 1"
        cur = conn.execute(
            f"SELECT app_id, display_name, enabled, sort_order, root_path FROM {_TABLE} {where} "
            "ORDER BY sort_order ASC, app_id ASC"
        )
        rows = cur.fetchall()
        return _rows_to_apps(rows)
    finally:
        conn.close()


def create_app_in_sqlite(
    *,
    app_id: str,
    root_path: str,
    display_name: str | None = None,
    enabled: bool = True,
    sort_order: int = 0,
) -> MindscapeApp:
    db_path = _apps_db_path()
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)

        payload: dict[str, Any] = {
            "app_id": app_id,
            "root_path": root_path,
            "display_name": display_name,
            "enabled": _bool_int(bool(enabled)),
            "sort_order": int(sort_order),
        }

        try:
            conn.execute(
                f"INSERT INTO {_TABLE} (app_id, display_name, root_path, enabled, sort_order) "
                "VALUES (:app_id, :display_name, :root_path, :enabled, :sort_order)",
                payload,
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise AppStoreError(f"App already exists: {app_id}") from exc

        # Return inserted row
        cur = conn.execute(
            f"SELECT app_id, display_name, enabled, sort_order, root_path FROM {_TABLE} WHERE app_id = ? LIMIT 1",
            (app_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise AppStoreError("Unexpected response from local insert")
        return _rows_to_apps([row])[0]
    finally:
        conn.close()


def update_app_in_sqlite(*, app_id: str, patch: dict[str, Any]) -> MindscapeApp:
    db_path = _apps_db_path()
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)

        allowed: dict[str, Any] = {}
        for key in ("display_name", "root_path", "enabled", "sort_order"):
            if key in patch:
                allowed[key] = patch[key]

        if not allowed:
            raise AppStoreError("No supported fields to update")

        # Ensure exists
        cur0 = conn.execute(f"SELECT 1 FROM {_TABLE} WHERE app_id = ? LIMIT 1", (app_id,))
        if cur0.fetchone() is None:
            raise AppStoreError("App not found (or no update returned)")

        sets: list[str] = []
        params: list[Any] = []
        for k, v in allowed.items():
            if k == "enabled":
                sets.append("enabled = ?")
                params.append(_bool_int(bool(v)))
            elif k == "sort_order":
                sets.append("sort_order = ?")
                params.append(int(v))
            else:
                sets.append(f"{k} = ?")
                params.append(v)

        params.append(app_id)
        conn.execute(f"UPDATE {_TABLE} SET {', '.join(sets)} WHERE app_id = ?", tuple(params))
        conn.commit()

        cur = conn.execute(
            f"SELECT app_id, display_name, enabled, sort_order, root_path FROM {_TABLE} WHERE app_id = ? LIMIT 1",
            (app_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise AppStoreError("App not found (or no update returned)")
        return _rows_to_apps([row])[0]
    finally:
        conn.close()


def delete_app_in_sqlite(*, app_id: str) -> int:
    db_path = _apps_db_path()
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        cur = conn.execute(f"DELETE FROM {_TABLE} WHERE app_id = ?", (app_id,))
        conn.commit()
        return int(cur.rowcount)
    finally:
        conn.close()


def resolve_app_root_from_sqlite(app_id: str) -> Path:
    """Resolve app_id -> root_path using local SQLite registry (internal only)."""
    db_path = _apps_db_path()
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        cur = conn.execute(
            f"SELECT app_id, root_path, enabled FROM {_TABLE} WHERE app_id = ? LIMIT 1",
            (app_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise AppStoreError(f"Unknown app_id: {app_id}")

        enabled = bool(int(row["enabled"]) if row["enabled"] is not None else 1)
        if not enabled:
            raise AppStoreError(f"App is disabled: {app_id}")

        root_raw = row["root_path"]
        if not isinstance(root_raw, str) or not root_raw.strip():
            raise AppStoreError(f"Invalid root_path for app_id: {app_id}")

        root = Path(root_raw).expanduser()
        try:
            resolved = root.resolve()
        except Exception as exc:  # noqa: BLE001
            raise AppStoreError("Invalid root_path for app_id") from exc

        runtime_root = _runtime_root(resolved)

        if not runtime_root.exists() or not runtime_root.is_dir():
            raise AppStoreError("Resolved app root does not exist or is not a directory.")
        return runtime_root
    finally:
        conn.close()


def resolve_conport_db_path_from_sqlite(app_id: str) -> Path:
    """Resolve `app_id` -> ConPort DB path using local registry.

    Note: root_path is mapped to a runtime-visible path (containers, etc.) before resolution.
    """
    root = resolve_app_root_from_sqlite(app_id)

    db_path = _find_conport_db_for_root(root)
    if db_path is None:
        raise AppStoreError("Resolved ConPort DB not found.")

    if db_path.suffix.lower() != ".db":
        raise AppStoreError("Resolved ConPort DB must end with '.db'.")
    return db_path


__all__ = [
    "create_app_in_sqlite",
    "delete_app_in_sqlite",
    "list_apps_from_sqlite",
    "resolve_app_root_from_sqlite",
    "resolve_conport_db_path_from_sqlite",
    "update_app_in_sqlite",
]
