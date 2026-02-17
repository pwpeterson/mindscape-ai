"""ConPort Workbench (SQLite) API routes.

Implements the Phase 1 Workbench API surface from [`docs/projectPRD.MD`](docs/projectPRD.MD:95)
using direct SQLite access.

Write operations are gated via MINDSCAPE_WORKBENCH_WRITE=true.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import aiosqlite
from fastapi import APIRouter, Body, HTTPException, Query, Request
from loguru import logger

from mindscape_ai.apps.registry import (
    AppRegistryError,
    discover_apps,
    normalize_app_roots,
    read_app_id_from_pyproject,
)
from mindscape_ai.apps.supabase_store import (
    AppStoreError,
    SupabaseUnavailableError,
    resolve_conport_db_path_from_supabase,
)
from mindscape_ai.conport import ConPortDbPathError, find_workspace_root, resolve_conport_db_path

router = APIRouter(prefix="/conport", tags=["conport"])

# Hard limits for untrusted query params (DoS guardrails)
DB_QUERY_MAX_LEN = 1024
APP_ID_QUERY_MAX_LEN = 200


def _validate_db_query_param(db_path: str | None) -> None:
    """Validate the `db` query parameter before attempting path resolution.

    Notes:
        `resolve_conport_db_path()` already enforces traversal/NUL and workspace constraints.
        This adds a cheap length guard to prevent pathological inputs.
    """

    if db_path is None:
        return

    if len(db_path) > DB_QUERY_MAX_LEN:
        raise HTTPException(status_code=400, detail="db parameter too long")

    # Strict allowlist of characters to avoid URI/query-string injection attempts.
    # Expected values are relative paths like: context_portal/context.db
    if re.fullmatch(r"[A-Za-z0-9_./-]+", db_path) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in db parameter")


def _validate_app_id_query_param(app_id: str | None) -> None:
    """Validate the `app_id` query parameter.

    `app_id` is not a filesystem path. It should match `[project].name` from the target
    app's pyproject.toml.
    """
    if app_id is None:
        return

    if len(app_id) > APP_ID_QUERY_MAX_LEN:
        raise HTTPException(status_code=400, detail="app_id parameter too long")

    # Allow typical package/project names: letters, digits, underscore, dash, dot.
    if re.fullmatch(r"[A-Za-z0-9_.-]+", app_id) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in app_id parameter")


def _write_enabled() -> bool:
    """Whether write endpoints are enabled.

    Fail-closed: unknown values disable writes.
    """

    raw = os.getenv("MINDSCAPE_WORKBENCH_WRITE", "false").strip().lower()
    if raw in {"1", "true", "yes"}:
        return True
    if raw in {"0", "false", "no", ""}:
        return False
    return False


def _json_loads_maybe(value: str | None) -> Any:
    if value is None:
        return None
    s = value.strip()
    if not s:
        return None
    if s[0] not in '[{"' and s not in {"true", "false", "null"}:
        # Likely not JSON.
        return value
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        return value


async def _fetchone(
    conn: aiosqlite.Connection, sql: str, params: tuple[Any, ...] = ()
) -> aiosqlite.Row | None:
    async with conn.execute(sql, params) as cur:
        return await cur.fetchone()


async def _fetchall(
    conn: aiosqlite.Connection, sql: str, params: tuple[Any, ...] = ()
) -> list[aiosqlite.Row]:
    async with conn.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return list(rows)


async def _table_exists(conn: aiosqlite.Connection, name: str) -> bool:
    row = await _fetchone(
        conn,
        "SELECT 1 FROM sqlite_master WHERE (type='table' OR type='view') AND name = ? LIMIT 1",
        (name,),
    )
    return row is not None


@lru_cache(maxsize=8)
def _apps_by_id_for_env(app_roots_env: str) -> dict[str, Path]:
    """Build an `app_id -> conport_db_path` mapping for a specific env value.

    Notes:
        This function is cached *by* the raw env string so changes to
        MINDSCAPE_APP_ROOTS are reflected without restarting the process.
    """
    raw = app_roots_env.strip()
    if not raw:
        return {}

    roots_raw = [p.strip() for p in raw.split(",") if p.strip()]
    roots = normalize_app_roots([Path(p) for p in roots_raw])
    apps = discover_apps(roots)

    out: dict[str, Path] = {}
    for app in apps:
        if app.conport_db_path is None:
            continue
        out[app.app_id] = app.conport_db_path
    return out


def _apps_by_id() -> dict[str, Path]:
    """Build an `app_id -> conport_db_path` mapping from MINDSCAPE_APP_ROOTS.

    Notes:
        - Fail-closed: if env is not configured, mapping is empty.
        - Does not expose filesystem paths to clients; only used internally.
    """
    return _apps_by_id_for_env(os.getenv("MINDSCAPE_APP_ROOTS", ""))


def _self_app_flag_raw() -> str:
    return os.getenv("MINDSCAPE_INCLUDE_SELF_APP", "true").strip().lower()


def _self_app_enabled(flag_raw: str) -> bool:
    return flag_raw in {"1", "true", "yes"}


@lru_cache(maxsize=4)
def _self_app_db_for_flag(flag_raw: str) -> tuple[str, Path] | None:
    """Return (self_app_id, conport_db_path) for this repo, if resolvable.

    Cache key is the env flag value so tests (and running processes) can toggle
    MINDSCAPE_INCLUDE_SELF_APP without getting stuck with stale cached results.
    """
    if not _self_app_enabled(flag_raw):
        return None

    try:
        root = find_workspace_root(start=Path(__file__))
        app_id = read_app_id_from_pyproject(root / "pyproject.toml")
        db_path = resolve_conport_db_path(None, start=Path(__file__))
        return app_id, db_path
    except (ConPortDbPathError, AppRegistryError, OSError, ValueError):
        return None


def _self_app_db() -> tuple[str, Path] | None:
    return _self_app_db_for_flag(_self_app_flag_raw())


def _resolve_conport_db_from_app_id(app_id: str) -> Path:
    """Resolve app_id -> conport db path.

    Preferred source: Supabase app registry (`mindscape_ai_apps`).
    Fallback: MINDSCAPE_APP_ROOTS filesystem scanning (legacy/dev/tests).

    Additionally, for local/dev UX, we allow resolving this Mindscape-AI repo as an
    implicit app when `app_id` matches its `[project].name`.
    """
    logger.info(f"[ConPort API] Resolving DB for app_id={app_id}")

    self_info = _self_app_db()
    if self_info is not None and app_id == self_info[0]:
        logger.info(f"[ConPort API] Matched self app: {self_info[0]} -> {self_info[1]}")
        return self_info[1]

    # Preferred: Supabase registry
    try:
        db_path = resolve_conport_db_path_from_supabase(app_id)
        logger.info(f"[ConPort API] Resolved via Supabase: {db_path}")
        return db_path
    except SupabaseUnavailableError as exc:
        logger.warning(f"[ConPort API] Supabase unavailable, falling back to env scanning: {exc}")
        # Fall back to env scanning
        pass
    except AppStoreError as exc:
        # Supabase is configured but data is invalid/missing.
        logger.error(f"[ConPort API] Supabase error for app_id={app_id}: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Fallback: legacy env scanning
    logger.info(f"[ConPort API] Attempting legacy env scanning for app_id={app_id}")
    try:
        mapping = _apps_by_id()
    except AppRegistryError as exc:
        logger.error(f"[ConPort API] App registry error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not mapping:
        logger.error("[ConPort API] App registry not configured")
        raise HTTPException(
            status_code=400,
            detail=(
                "App registry is not configured. Configure Supabase "
                "(SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY) "
                "or set MINDSCAPE_APP_ROOTS."
            ),
        )

    if app_id not in mapping:
        logger.error(f"[ConPort API] app_id={app_id} not found in mapping. Available: {list(mapping.keys())}")
        raise HTTPException(status_code=404, detail=f"Unknown app_id: {app_id}")

    resolved = mapping[app_id].resolve()
    logger.info(f"[ConPort API] Resolved via env mapping: {resolved}")

    if resolved.suffix.lower() != ".db":
        logger.error(f"[ConPort API] Invalid DB suffix: {resolved}")
        raise HTTPException(status_code=400, detail="Resolved ConPort DB must end with '.db'.")
    if not resolved.exists() or not resolved.is_file():
        logger.error(f"[ConPort API] DB not found: {resolved}")
        raise HTTPException(status_code=404, detail="Resolved ConPort DB not found.")
    return resolved


async def _open_aiosqlite(
    db_path: str | None, *, app_id: str | None, read_only: bool
) -> tuple[aiosqlite.Connection, str, str | None]:
    """Open an aiosqlite connection for ConPort.

    Resolution precedence:
    1) app_id (multi-app mode) -> DB via registry (MINDSCAPE_APP_ROOTS)
    2) db query param (legacy/workbench) -> DB via resolve_conport_db_path()
    """
    logger.debug(f"[ConPort API] _open_aiosqlite called with app_id={app_id}, db_path={db_path}, read_only={read_only}")

    _validate_app_id_query_param(app_id)
    if app_id is not None:
        resolved = _resolve_conport_db_from_app_id(app_id)
        display = f"app:{app_id}"
        logger.info(f"[ConPort API] Resolved app_id={app_id} to {resolved}")
    else:
        _validate_db_query_param(db_path)
        try:
            # Make DB resolution CWD-independent by anchoring the workspace-root search
            # to this module's location (inside the repo).
            resolved = resolve_conport_db_path(db_path, start=Path(__file__))
            logger.info(f"[ConPort API] Resolved db_path={db_path} to {resolved}")
        except ConPortDbPathError as exc:
            logger.error(f"[ConPort API] ConPort DB path resolution error: {exc}")
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        display = str(resolved)

    mode = "ro" if read_only else "rw"
    uri = f"file:{resolved.as_posix()}?mode={mode}"
    logger.debug(f"[ConPort API] Opening SQLite at {uri}")
    conn = await aiosqlite.connect(uri, uri=True)

    await conn.execute("PRAGMA foreign_keys = ON")
    if read_only:
        await conn.execute("PRAGMA query_only = ON")

    conn.row_factory = aiosqlite.Row

    return conn, display, app_id


@router.get("/now")
async def conport_now(
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return product_context, active_context, and recent_activity."""

    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=True)
    try:
        pc_row = await _fetchone(conn, "SELECT content FROM product_context WHERE id = 1")
        ac_row = await _fetchone(conn, "SELECT content FROM active_context WHERE id = 1")

        recent_decisions = await _fetchall(
            conn,
            "SELECT id, timestamp, summary, rationale, implementation_details, tags "
            "FROM decisions ORDER BY id DESC LIMIT 10",
        )
        recent_progress = await _fetchall(
            conn,
            "SELECT id, timestamp, status, description, parent_id "
            "FROM progress_entries ORDER BY id DESC LIMIT 10",
        )
        recent_patterns = await _fetchall(
            conn,
            "SELECT id, timestamp, name, description, tags "
            "FROM system_patterns ORDER BY id DESC LIMIT 10",
        )
        recent_custom = await _fetchall(
            conn,
            "SELECT id, timestamp, category, key, value "
            "FROM custom_data ORDER BY id DESC LIMIT 10",
        )
        recent_links = await _fetchall(
            conn,
            "SELECT id, timestamp, workspace_id, source_item_type, source_item_id, "
            "target_item_type, target_item_id, relationship_type, description "
            "FROM context_links ORDER BY id DESC LIMIT 10",
        )

        return {
            "app_id": app_id_resolved,
            "db": db_resolved,
            "product_context": _json_loads_maybe(pc_row[0] if pc_row else "{}"),
            "active_context": _json_loads_maybe(ac_row[0] if ac_row else "{}"),
            "recent_activity": {
                "decisions": [
                    {
                        "id": r["id"],
                        "timestamp": r["timestamp"],
                        "summary": r["summary"],
                        "rationale": r["rationale"],
                        "implementation_details": r["implementation_details"],
                        "tags": _json_loads_maybe(r["tags"]),
                    }
                    for r in recent_decisions
                ],
                "progress_entries": [
                    {
                        "id": r["id"],
                        "timestamp": r["timestamp"],
                        "status": (r["status"] or "UNKNOWN").upper(),
                        "description": r["description"],
                        "parent_id": r["parent_id"],
                    }
                    for r in recent_progress
                ],
                "system_patterns": [
                    {
                        "id": r["id"],
                        "timestamp": r["timestamp"],
                        "name": r["name"],
                        "description": r["description"],
                        "tags": _json_loads_maybe(r["tags"]),
                    }
                    for r in recent_patterns
                ],
                "custom_data": [
                    {
                        "id": r["id"],
                        "timestamp": r["timestamp"],
                        "category": r["category"],
                        "key": r["key"],
                        "value": _json_loads_maybe(r["value"]),
                    }
                    for r in recent_custom
                ],
                "links": [dict(r) for r in recent_links],
            },
        }
    finally:
        await conn.close()


@router.get("/dashboard")
async def conport_dashboard(
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return progress rollups and basic knowledge graph health."""

    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=True)
    try:
        status_rows = await _fetchall(
            conn, "SELECT status, COUNT(*) AS count FROM progress_entries GROUP BY status"
        )
        # Normalize status values to uppercase for consistent grouping (e.g., "in_progress" -> "IN_PROGRESS")
        progress_rollup: dict[str, int] = {}
        for row in status_rows:
            normalized_status = (row["status"] or "UNKNOWN").upper()
            progress_rollup[normalized_status] = progress_rollup.get(normalized_status, 0) + row["count"]

        link_count = await _fetchone(conn, "SELECT COUNT(*) AS count FROM context_links")
        decision_count = await _fetchone(conn, "SELECT COUNT(*) AS count FROM decisions")
        custom_count = await _fetchone(conn, "SELECT COUNT(*) AS count FROM custom_data")

        return {
            "app_id": app_id_resolved,
            "db": db_resolved,
            "progress": {"by_status": progress_rollup},
            "graph_health": {
                "links": int(link_count["count"] if link_count else 0),
                "decisions": int(decision_count["count"] if decision_count else 0),
                "custom_data": int(custom_count["count"] if custom_count else 0),
            },
        }
    finally:
        await conn.close()


@router.get("/decisions")
async def conport_decisions(
    limit: int = Query(default=50, ge=1, le=500),
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """List decisions (newest first)."""
    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=True)
    try:
        rows = await _fetchall(
            conn,
            "SELECT id, timestamp, summary, rationale, implementation_details, tags "
            "FROM decisions ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return {
            "app_id": app_id_resolved,
            "db": db_resolved,
            "decisions": [
                {
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "summary": r["summary"],
                    "rationale": r["rationale"],
                    "implementation_details": r["implementation_details"],
                    "tags": _json_loads_maybe(r["tags"]),
                }
                for r in rows
            ],
        }
    finally:
        await conn.close()


@router.get("/custom-data")
async def conport_custom_data(
    category: str | None = Query(default=None),
    key: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """List custom_data records (newest first), with optional category/key filters."""
    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=True)
    try:
        where: list[str] = []
        params: list[Any] = []

        if category is not None and category != "":
            where.append("category = ?")
            params.append(category)

        if key is not None and key != "":
            where.append("key = ?")
            params.append(key)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        rows = await _fetchall(
            conn,
            "SELECT id, timestamp, category, key, value "
            f"FROM custom_data {where_sql} ORDER BY id DESC LIMIT ?",  # nosec B608
            (*params, limit),
        )
        return {
            "app_id": app_id_resolved,
            "db": db_resolved,
            "custom_data": [
                {
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "category": r["category"],
                    "key": r["key"],
                    "value": _json_loads_maybe(r["value"]),
                }
                for r in rows
            ],
        }
    finally:
        await conn.close()


@router.get("/system-patterns")
async def conport_system_patterns(
    limit: int = Query(default=50, ge=1, le=500),
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """List system patterns (newest first)."""
    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=True)
    try:
        rows = await _fetchall(
            conn,
            "SELECT id, timestamp, name, description, tags "
            "FROM system_patterns ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return {
            "app_id": app_id_resolved,
            "db": db_resolved,
            "system_patterns": [
                {
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "name": r["name"],
                    "description": r["description"],
                    "tags": _json_loads_maybe(r["tags"]),
                }
                for r in rows
            ],
        }
    finally:
        await conn.close()


@router.get("/progress")
async def conport_progress_list(
    request: Request,
    status: str | None = Query(default=None),
    parent_id: int | None = Query(default=None, ge=1),
    description_prefix: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=50, ge=1, le=500),
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """List progress entries (newest first), with optional filters.

    Filters:
    - status: case-insensitive exact match (e.g., "TODO", "todo", "In_Progress" all match)
    - parent_id: exact match
    - description_prefix: case-insensitive prefix match (e.g. "Phase 1:")
    """
    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=True)
    try:
        where: list[str] = []
        params: list[Any] = []

        if status is not None and status != "":
            where.append("LOWER(status) = LOWER(?)")
            params.append(status)

        if parent_id is not None:
            where.append("parent_id = ?")
            params.append(parent_id)
        # Note: if parent_id is None or empty, we don't filter - return all entries

        if description_prefix is not None:
            prefix = description_prefix.strip()
            if prefix:
                # Use a prefix match and normalize case for robustness across SQLite collations.
                where.append("LOWER(description) LIKE LOWER(?)")
                params.append(f"{prefix}%")

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        rows = await _fetchall(
            conn,
            "SELECT id, timestamp, status, description, parent_id "
            f"FROM progress_entries {where_sql} ORDER BY id DESC LIMIT ?",  # nosec B608
            (*params, limit),
        )
        return {
            "app_id": app_id_resolved,
            "db": db_resolved,
            "progress_entries": [dict(r) for r in rows],
        }
    finally:
        await conn.close()


@router.get("/views")
async def conport_views_list(
    limit: int = Query(default=50, ge=1, le=500),
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """List saved workbench views stored in custom_data(category='workbench_views')."""
    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=True)
    try:
        rows = await _fetchall(
            conn,
            "SELECT id, timestamp, category, key, value "
            "FROM custom_data WHERE category = ? ORDER BY id DESC LIMIT ?",
            ("workbench_views", limit),
        )
        return {
            "app_id": app_id_resolved,
            "db": db_resolved,
            "views": [
                {
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "category": r["category"],
                    "key": r["key"],
                    "value": _json_loads_maybe(r["value"]),
                }
                for r in rows
            ],
        }
    finally:
        await conn.close()


@router.get("/item")
async def conport_item(
    type: Literal[
        "decision",
        "progress",
        "system_pattern",
        "custom_data",
        "context_link",
        "product_context",
        "active_context",
    ] = Query(...),
    id: int = Query(..., ge=1),
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """Get an item by type and numeric id."""

    sql_by_type: dict[str, str] = {
        "decision": "SELECT * FROM decisions WHERE id = ?",
        "progress": "SELECT * FROM progress_entries WHERE id = ?",
        "system_pattern": "SELECT * FROM system_patterns WHERE id = ?",
        "custom_data": "SELECT * FROM custom_data WHERE id = ?",
        "context_link": "SELECT * FROM context_links WHERE id = ?",
        "product_context": "SELECT * FROM product_context WHERE id = ?",
        "active_context": "SELECT * FROM active_context WHERE id = ?",
    }

    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=True)
    try:
        sql = sql_by_type[type]
        row = await _fetchone(conn, sql, (id,))
        if row is None:
            raise HTTPException(status_code=404, detail="Item not found")

        data = dict(row)
        if type in {"product_context", "active_context"}:
            data["content"] = _json_loads_maybe(data.get("content"))
        if type == "custom_data":
            data["value"] = _json_loads_maybe(data.get("value"))
        if type in {"decision", "system_pattern"}:
            data["tags"] = _json_loads_maybe(data.get("tags"))

        return {"app_id": app_id_resolved, "db": db_resolved, "type": type, "item": data}
    finally:
        await conn.close()


@router.get("/search")
async def conport_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=100),
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """Search decisions/custom_data.

    Uses FTS tables (`decisions_fts`, `custom_data_fts`) when present.
    Falls back to LIKE search when FTS is unavailable.
    """

    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=True)
    try:
        # NOTE:
        # Even when FTS tables exist, SQLite can raise OperationalError for certain MATCH queries
        # (e.g. unbalanced quotes, reserved operators, etc.). Those should not surface as 500s.
        decisions_fts_available = await _table_exists(conn, "decisions_fts")
        custom_fts_available = await _table_exists(conn, "custom_data_fts")

        decisions_fts_used = decisions_fts_available
        custom_fts_used = custom_fts_available

        if decisions_fts_available:
            try:
                rows = await _fetchall(
                    conn,
                    "SELECT d.id, d.timestamp, d.summary, d.rationale, "
                    "d.implementation_details, d.tags "
                    "FROM decisions_fts f JOIN decisions d ON d.id = f.rowid "
                    "WHERE decisions_fts MATCH ? "
                    "ORDER BY d.id DESC LIMIT ?",
                    (q, limit),
                )
            except aiosqlite.Error:
                # Fall back to LIKE search if the MATCH expression is invalid for this SQLite build.
                decisions_fts_used = False
                like = f"%{q}%"
                rows = await _fetchall(
                    conn,
                    "SELECT id, timestamp, summary, rationale, implementation_details, tags "
                    "FROM decisions "
                    "WHERE summary LIKE ? OR rationale LIKE ? OR implementation_details LIKE ? "
                    "OR tags LIKE ? "
                    "ORDER BY id DESC LIMIT ?",
                    (like, like, like, like, limit),
                )
        else:
            like = f"%{q}%"
            rows = await _fetchall(
                conn,
                "SELECT id, timestamp, summary, rationale, implementation_details, tags "
                "FROM decisions "
                "WHERE summary LIKE ? OR rationale LIKE ? OR implementation_details LIKE ? "
                "OR tags LIKE ? "
                "ORDER BY id DESC LIMIT ?",
                (like, like, like, like, limit),
            )

        decisions = [
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "summary": r["summary"],
                "rationale": r["rationale"],
                "implementation_details": r["implementation_details"],
                "tags": _json_loads_maybe(r["tags"]),
            }
            for r in rows
        ]

        if custom_fts_available:
            try:
                rows2 = await _fetchall(
                    conn,
                    "SELECT c.id, c.timestamp, c.category, c.key, c.value "
                    "FROM custom_data_fts f JOIN custom_data c ON c.id = f.rowid "
                    "WHERE custom_data_fts MATCH ? "
                    "ORDER BY c.id DESC LIMIT ?",
                    (q, limit),
                )
            except aiosqlite.Error:
                custom_fts_used = False
                like = f"%{q}%"
                rows2 = await _fetchall(
                    conn,
                    "SELECT id, timestamp, category, key, value "
                    "FROM custom_data "
                    "WHERE category LIKE ? OR key LIKE ? OR value LIKE ? "
                    "ORDER BY id DESC LIMIT ?",
                    (like, like, like, limit),
                )
        else:
            like = f"%{q}%"
            rows2 = await _fetchall(
                conn,
                "SELECT id, timestamp, category, key, value "
                "FROM custom_data "
                "WHERE category LIKE ? OR key LIKE ? OR value LIKE ? "
                "ORDER BY id DESC LIMIT ?",
                (like, like, like, limit),
            )

        custom_data = [
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "category": r["category"],
                "key": r["key"],
                "value": _json_loads_maybe(r["value"]),
            }
            for r in rows2
        ]

        return {
            "app_id": app_id_resolved,
            "db": db_resolved,
            "query": q,
            "fts": {"decisions": decisions_fts_used, "custom_data": custom_fts_used},
            "results": {"decisions": decisions, "custom_data": custom_data},
        }
    finally:
        await conn.close()


@router.get("/progress/{progress_id}")
async def conport_progress(
    progress_id: int,
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=True)
    try:
        row = await _fetchone(
            conn,
            "SELECT id, timestamp, status, description, parent_id "
            "FROM progress_entries WHERE id = ?",
            (progress_id,),
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Progress entry not found")
        return {"app_id": app_id_resolved, "db": db_resolved, "progress": dict(row)}
    finally:
        await conn.close()


@router.patch("/progress/{progress_id}")
async def conport_progress_update(
    progress_id: int,
    payload: dict[str, Any] = Body(default_factory=dict),
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Workbench write operations are disabled. "
                "Set MINDSCAPE_WORKBENCH_WRITE=true to enable."
            ),
        )

    status = payload.get("status")
    description = payload.get("description")
    updates: list[str] = []
    params: list[Any] = []

    if status is not None:
        if not isinstance(status, str) or not status.strip() or len(status) > 50:
            raise HTTPException(status_code=400, detail="Invalid status")
        updates.append("status = ?")
        params.append(status.strip())

    if description is not None:
        if not isinstance(description, str) or not description.strip():
            raise HTTPException(status_code=400, detail="Invalid description")
        updates.append("description = ?")
        params.append(description)

    if "parent_id" in payload:
        parent_id = payload.get("parent_id")
        if parent_id is not None and not isinstance(parent_id, int):
            raise HTTPException(status_code=400, detail="Invalid parent_id")
        updates.append("parent_id = ?")
        params.append(parent_id)

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=False)
    try:
        # Ensure exists
        exists = await _fetchone(
            conn, "SELECT 1 FROM progress_entries WHERE id = ?", (progress_id,)
        )
        if exists is None:
            raise HTTPException(status_code=404, detail="Progress entry not found")

        sql = f"UPDATE progress_entries SET {', '.join(updates)} WHERE id = ?"  # nosec B608
        params.append(progress_id)
        await conn.execute(sql, tuple(params))
        await conn.commit()

        row = await _fetchone(
            conn,
            "SELECT id, timestamp, status, description, parent_id "
            "FROM progress_entries WHERE id = ?",
            (progress_id,),
        )
        return {
            "app_id": app_id_resolved,
            "db": db_resolved,
            "progress": dict(row) if row else None,
        }
    finally:
        await conn.close()


@router.get("/views/{view_key}")
async def conport_get_view(
    view_key: str,
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=True)
    try:
        row = await _fetchone(
            conn,
            "SELECT id, timestamp, category, key, value "
            "FROM custom_data WHERE category = ? AND key = ?",
            ("workbench_views", view_key),
        )
        if row is None:
            raise HTTPException(status_code=404, detail="View not found")
        data = dict(row)
        data["value"] = _json_loads_maybe(data.get("value"))
        return {"app_id": app_id_resolved, "db": db_resolved, "view": data}
    finally:
        await conn.close()


@router.put("/views/{view_key}")
async def conport_put_view(
    view_key: str,
    value: Any = Body(...),
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Workbench write operations are disabled. "
                "Set MINDSCAPE_WORKBENCH_WRITE=true to enable."
            ),
        )

    # Store as JSON when possible.
    value_text = json.dumps(value, ensure_ascii=False)

    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=False)
    try:
        await conn.execute(
            "INSERT INTO custom_data (timestamp, category, key, value) "
            "VALUES (CURRENT_TIMESTAMP, ?, ?, ?) "
            "ON CONFLICT(category, key) DO UPDATE SET "
            "timestamp = CURRENT_TIMESTAMP, value = excluded.value",
            ("workbench_views", view_key, value_text),
        )
        await conn.commit()

        row = await _fetchone(
            conn,
            "SELECT id, timestamp, category, key, value "
            "FROM custom_data WHERE category = ? AND key = ?",
            ("workbench_views", view_key),
        )
        data = (
            dict(row)
            if row
            else {
                "category": "workbench_views",
                "key": view_key,
                "value": value,
            }
        )
        data["value"] = _json_loads_maybe(data.get("value"))
        return {"app_id": app_id_resolved, "db": db_resolved, "view": data}
    finally:
        await conn.close()


@router.delete("/views/{view_key}")
async def conport_delete_view(
    view_key: str,
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Workbench write operations are disabled. "
                "Set MINDSCAPE_WORKBENCH_WRITE=true to enable."
            ),
        )

    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=False)
    try:
        cur = await conn.execute(
            "DELETE FROM custom_data WHERE category = ? AND key = ?",
            ("workbench_views", view_key),
        )
        await conn.commit()
        return {"app_id": app_id_resolved, "db": db_resolved, "deleted": int(cur.rowcount)}
    finally:
        await conn.close()


@router.get("/links")
async def conport_links(
    source_item_type: str | None = Query(default=None),
    source_item_id: str | None = Query(default=None),
    target_item_type: str | None = Query(default=None),
    target_item_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=True)
    try:
        where: list[str] = []
        params: list[Any] = []

        if source_item_type is not None:
            where.append("source_item_type = ?")
            params.append(source_item_type)
        if source_item_id is not None:
            where.append("source_item_id = ?")
            params.append(source_item_id)
        if target_item_type is not None:
            where.append("target_item_type = ?")
            params.append(target_item_type)
        if target_item_id is not None:
            where.append("target_item_id = ?")
            params.append(target_item_id)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        rows = await _fetchall(
            conn,
            "SELECT id, timestamp, workspace_id, source_item_type, source_item_id, "
            "target_item_type, target_item_id, relationship_type, description "
            f"FROM context_links {where_sql} ORDER BY id DESC LIMIT ?",  # nosec B608
            (*params, limit),
        )
        return {"app_id": app_id_resolved, "db": db_resolved, "links": [dict(r) for r in rows]}
    finally:
        await conn.close()


@router.post("/links")
async def conport_links_create(
    payload: dict[str, Any] = Body(...),
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Workbench write operations are disabled. "
                "Set MINDSCAPE_WORKBENCH_WRITE=true to enable."
            ),
        )

    required = [
        "workspace_id",
        "source_item_type",
        "source_item_id",
        "target_item_type",
        "target_item_id",
        "relationship_type",
    ]
    missing = [k for k in required if k not in payload]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")

    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=False)
    try:
        await conn.execute(
            "INSERT INTO context_links (workspace_id, source_item_type, source_item_id, "
            "target_item_type, target_item_id, relationship_type, description) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(payload["workspace_id"]),
                str(payload["source_item_type"]),
                str(payload["source_item_id"]),
                str(payload["target_item_type"]),
                str(payload["target_item_id"]),
                str(payload["relationship_type"]),
                payload.get("description"),
            ),
        )
        await conn.commit()

        row = await _fetchone(conn, "SELECT last_insert_rowid() AS id")
        link_id = int(row["id"]) if row else None
        created = await _fetchone(
            conn,
            "SELECT * FROM context_links WHERE id = ?",
            (link_id,),
        )
        return {
            "app_id": app_id_resolved,
            "db": db_resolved,
            "link": dict(created) if created else None,
        }
    finally:
        await conn.close()


@router.delete("/links")
async def conport_links_delete(
    id: int = Query(..., ge=1),
    app_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Workbench write operations are disabled. "
                "Set MINDSCAPE_WORKBENCH_WRITE=true to enable."
            ),
        )

    conn, db_resolved, app_id_resolved = await _open_aiosqlite(db, app_id=app_id, read_only=False)
    try:
        cur = await conn.execute("DELETE FROM context_links WHERE id = ?", (id,))
        await conn.commit()
        return {"app_id": app_id_resolved, "db": db_resolved, "deleted": int(cur.rowcount)}
    finally:
        await conn.close()
