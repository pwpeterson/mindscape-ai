"""ConPort Workbench (SQLite) API routes.

Implements the Phase 1 Workbench API surface from [`docs/projectPRD.MD`](docs/projectPRD.MD:95)
using direct SQLite access.

Write operations are gated via MINDSCAPE_WORKBENCH_WRITE=true.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

import aiosqlite
from fastapi import APIRouter, Body, HTTPException, Query

from mindscape_ai.conport import ConPortDbPathError, resolve_conport_db_path

router = APIRouter(prefix="/conport", tags=["conport"])


def _write_enabled() -> bool:
    return os.getenv("MINDSCAPE_WORKBENCH_WRITE", "false").strip().lower() in {"1", "true", "yes"}


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


async def _open_aiosqlite(
    db_path: str | None, *, read_only: bool
) -> tuple[aiosqlite.Connection, str]:
    try:
        # Make DB resolution CWD-independent by anchoring the workspace-root search
        # to this module’s location (inside the repo).
        resolved = resolve_conport_db_path(db_path, start=Path(__file__))
    except ConPortDbPathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    mode = "ro" if read_only else "rw"
    uri = f"file:{resolved.as_posix()}?mode={mode}"
    conn = await aiosqlite.connect(uri, uri=True)

    await conn.execute("PRAGMA foreign_keys = ON")
    if read_only:
        await conn.execute("PRAGMA query_only = ON")

    conn.row_factory = aiosqlite.Row

    return conn, str(resolved)


@router.get("/now")
async def conport_now(db: str | None = Query(default=None)) -> dict[str, Any]:
    """Return product_context, active_context, and recent_activity."""

    conn, db_resolved = await _open_aiosqlite(db, read_only=True)
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
                        "status": r["status"],
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
async def conport_dashboard(db: str | None = Query(default=None)) -> dict[str, Any]:
    """Return progress rollups and basic knowledge graph health."""

    conn, db_resolved = await _open_aiosqlite(db, read_only=True)
    try:
        status_rows = await _fetchall(
            conn, "SELECT status, COUNT(*) AS count FROM progress_entries GROUP BY status"
        )
        progress_rollup = {row["status"]: row["count"] for row in status_rows}

        link_count = await _fetchone(conn, "SELECT COUNT(*) AS count FROM context_links")
        decision_count = await _fetchone(conn, "SELECT COUNT(*) AS count FROM decisions")
        custom_count = await _fetchone(conn, "SELECT COUNT(*) AS count FROM custom_data")

        return {
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
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """List decisions (newest first)."""
    conn, db_resolved = await _open_aiosqlite(db, read_only=True)
    try:
        rows = await _fetchall(
            conn,
            "SELECT id, timestamp, summary, rationale, implementation_details, tags "
            "FROM decisions ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return {
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
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """List custom_data records (newest first), with optional category/key filters."""
    conn, db_resolved = await _open_aiosqlite(db, read_only=True)
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
            f"FROM custom_data {where_sql} ORDER BY id DESC LIMIT ?",
            (*params, limit),
        )
        return {
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
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """List system patterns (newest first)."""
    conn, db_resolved = await _open_aiosqlite(db, read_only=True)
    try:
        rows = await _fetchall(
            conn,
            "SELECT id, timestamp, name, description, tags "
            "FROM system_patterns ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return {
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
    status: str | None = Query(default=None),
    parent_id: int | None = Query(default=None, ge=1),
    description_prefix: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=50, ge=1, le=500),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """List progress entries (newest first), with optional filters.

    Filters:
    - status: exact match
    - parent_id: exact match
    - description_prefix: case-insensitive prefix match (e.g. "Phase 1:")
    """
    conn, db_resolved = await _open_aiosqlite(db, read_only=True)
    try:
        where: list[str] = []
        params: list[Any] = []

        if status is not None and status != "":
            where.append("status = ?")
            params.append(status)

        if parent_id is not None:
            where.append("parent_id = ?")
            params.append(parent_id)

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
            f"FROM progress_entries {where_sql} ORDER BY id DESC LIMIT ?",
            (*params, limit),
        )
        return {"db": db_resolved, "progress_entries": [dict(r) for r in rows]}
    finally:
        await conn.close()


@router.get("/views")
async def conport_views_list(
    limit: int = Query(default=50, ge=1, le=500),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """List saved workbench views stored in custom_data(category='workbench_views')."""
    conn, db_resolved = await _open_aiosqlite(db, read_only=True)
    try:
        rows = await _fetchall(
            conn,
            "SELECT id, timestamp, category, key, value "
            "FROM custom_data WHERE category = ? ORDER BY id DESC LIMIT ?",
            ("workbench_views", limit),
        )
        return {
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
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """Get an item by type and numeric id."""

    table_map: dict[str, str] = {
        "decision": "decisions",
        "progress": "progress_entries",
        "system_pattern": "system_patterns",
        "custom_data": "custom_data",
        "context_link": "context_links",
        "product_context": "product_context",
        "active_context": "active_context",
    }

    conn, db_resolved = await _open_aiosqlite(db, read_only=True)
    try:
        table = table_map[type]
        row = await _fetchone(conn, f"SELECT * FROM {table} WHERE id = ?", (id,))
        if row is None:
            raise HTTPException(status_code=404, detail="Item not found")

        data = dict(row)
        if type in {"product_context", "active_context"}:
            data["content"] = _json_loads_maybe(data.get("content"))
        if type == "custom_data":
            data["value"] = _json_loads_maybe(data.get("value"))
        if type in {"decision", "system_pattern"}:
            data["tags"] = _json_loads_maybe(data.get("tags"))

        return {"db": db_resolved, "type": type, "item": data}
    finally:
        await conn.close()


@router.get("/search")
async def conport_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=100),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    """Search decisions/custom_data.

    Uses FTS tables (`decisions_fts`, `custom_data_fts`) when present.
    Falls back to LIKE search when FTS is unavailable.
    """

    conn, db_resolved = await _open_aiosqlite(db, read_only=True)
    try:
        has_decisions_fts = await _table_exists(conn, "decisions_fts")
        has_custom_fts = await _table_exists(conn, "custom_data_fts")

        decisions: list[dict[str, Any]] = []
        custom_data: list[dict[str, Any]] = []

        if has_decisions_fts:
            rows = await _fetchall(
                conn,
                "SELECT d.id, d.timestamp, d.summary, d.rationale, "
                "d.implementation_details, d.tags "
                "FROM decisions_fts f JOIN decisions d ON d.id = f.rowid "
                "WHERE decisions_fts MATCH ? "
                "ORDER BY d.id DESC LIMIT ?",
                (q, limit),
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

        if has_custom_fts:
            rows2 = await _fetchall(
                conn,
                "SELECT c.id, c.timestamp, c.category, c.key, c.value "
                "FROM custom_data_fts f JOIN custom_data c ON c.id = f.rowid "
                "WHERE custom_data_fts MATCH ? "
                "ORDER BY c.id DESC LIMIT ?",
                (q, limit),
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
            "db": db_resolved,
            "query": q,
            "fts": {"decisions": has_decisions_fts, "custom_data": has_custom_fts},
            "results": {"decisions": decisions, "custom_data": custom_data},
        }
    finally:
        await conn.close()


@router.get("/progress/{progress_id}")
async def conport_progress(
    progress_id: int, db: str | None = Query(default=None)
) -> dict[str, Any]:
    conn, db_resolved = await _open_aiosqlite(db, read_only=True)
    try:
        row = await _fetchone(
            conn,
            "SELECT id, timestamp, status, description, parent_id "
            "FROM progress_entries WHERE id = ?",
            (progress_id,),
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Progress entry not found")
        return {"db": db_resolved, "progress": dict(row)}
    finally:
        await conn.close()


@router.patch("/progress/{progress_id}")
async def conport_progress_update(
    progress_id: int,
    payload: dict[str, Any] = Body(default_factory=dict),
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

    conn, db_resolved = await _open_aiosqlite(db, read_only=False)
    try:
        # Ensure exists
        exists = await _fetchone(
            conn, "SELECT 1 FROM progress_entries WHERE id = ?", (progress_id,)
        )
        if exists is None:
            raise HTTPException(status_code=404, detail="Progress entry not found")

        sql = f"UPDATE progress_entries SET {', '.join(updates)} WHERE id = ?"
        params.append(progress_id)
        await conn.execute(sql, tuple(params))
        await conn.commit()

        row = await _fetchone(
            conn,
            "SELECT id, timestamp, status, description, parent_id "
            "FROM progress_entries WHERE id = ?",
            (progress_id,),
        )
        return {"db": db_resolved, "progress": dict(row) if row else None}
    finally:
        await conn.close()


@router.get("/views/{view_key}")
async def conport_get_view(view_key: str, db: str | None = Query(default=None)) -> dict[str, Any]:
    conn, db_resolved = await _open_aiosqlite(db, read_only=True)
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
        return {"db": db_resolved, "view": data}
    finally:
        await conn.close()


@router.put("/views/{view_key}")
async def conport_put_view(
    view_key: str,
    value: Any = Body(...),
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

    conn, db_resolved = await _open_aiosqlite(db, read_only=False)
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
        return {"db": db_resolved, "view": data}
    finally:
        await conn.close()


@router.delete("/views/{view_key}")
async def conport_delete_view(
    view_key: str, db: str | None = Query(default=None)
) -> dict[str, Any]:
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Workbench write operations are disabled. "
                "Set MINDSCAPE_WORKBENCH_WRITE=true to enable."
            ),
        )

    conn, db_resolved = await _open_aiosqlite(db, read_only=False)
    try:
        cur = await conn.execute(
            "DELETE FROM custom_data WHERE category = ? AND key = ?",
            ("workbench_views", view_key),
        )
        await conn.commit()
        return {"db": db_resolved, "deleted": int(cur.rowcount)}
    finally:
        await conn.close()


@router.get("/links")
async def conport_links(
    source_item_type: str | None = Query(default=None),
    source_item_id: str | None = Query(default=None),
    target_item_type: str | None = Query(default=None),
    target_item_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: str | None = Query(default=None),
) -> dict[str, Any]:
    conn, db_resolved = await _open_aiosqlite(db, read_only=True)
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
            f"FROM context_links {where_sql} ORDER BY id DESC LIMIT ?",
            (*params, limit),
        )
        return {"db": db_resolved, "links": [dict(r) for r in rows]}
    finally:
        await conn.close()


@router.post("/links")
async def conport_links_create(
    payload: dict[str, Any] = Body(...),
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

    conn, db_resolved = await _open_aiosqlite(db, read_only=False)
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
        return {"db": db_resolved, "link": dict(created) if created else None}
    finally:
        await conn.close()


@router.delete("/links")
async def conport_links_delete(
    id: int = Query(..., ge=1),
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

    conn, db_resolved = await _open_aiosqlite(db, read_only=False)
    try:
        cur = await conn.execute("DELETE FROM context_links WHERE id = ?", (id,))
        await conn.commit()
        return {"db": db_resolved, "deleted": int(cur.rowcount)}
    finally:
        await conn.close()
