"""Mem0 API routes.

Mirrors the mem0-mcp tool surface behind HTTP endpoints for the Mindscape UI.

Security:
- Mutating operations are gated behind MINDSCAPE_MEM0_WRITE=true (fail-closed).
- Query params are validated with basic DoS/character guardrails.

Notes:
- This implementation embeds a Mem0 client in-process; it does NOT call the mem0 MCP server.
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from loguru import logger

from mindscape_ai.mem0.client import Mem0Settings, Mem0UnavailableError, get_mem0_client

router = APIRouter(prefix="/mem0", tags=["mem0"])

# Hard limits for untrusted query params (DoS guardrails)
USER_ID_QUERY_MAX_LEN = 200
APP_ID_QUERY_MAX_LEN = 200
PROJECT_ID_QUERY_MAX_LEN = 200
QUERY_MAX_LEN = 2000


def _write_enabled() -> bool:
    """Whether mem0 write endpoints are enabled.

    Fail-closed: unknown values disable writes.
    """
    raw = os.getenv("MINDSCAPE_MEM0_WRITE", "false").strip().lower()
    if raw in {"1", "true", "yes"}:
        return True
    if raw in {"0", "false", "no", ""}:
        return False
    return False


def _validate_user_id(user_id: str | None) -> None:
    if user_id is None:
        return
    if len(user_id) > USER_ID_QUERY_MAX_LEN:
        raise HTTPException(status_code=400, detail="user_id parameter too long")
    # Allow typical identifiers (letters/digits/underscore/dash/dot)
    if re.fullmatch(r"[A-Za-z0-9_.-]+", user_id) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in user_id parameter")


def _validate_app_id(app_id: str | None) -> None:
    if app_id is None:
        return
    if len(app_id) > APP_ID_QUERY_MAX_LEN:
        raise HTTPException(status_code=400, detail="app_id parameter too long")
    if re.fullmatch(r"[A-Za-z0-9_.-]+", app_id) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in app_id parameter")


def _validate_project_id(project_id: str | None) -> None:
    if project_id is None:
        return
    if len(project_id) > PROJECT_ID_QUERY_MAX_LEN:
        raise HTTPException(status_code=400, detail="project_id parameter too long")
    if re.fullmatch(r"[A-Za-z0-9_.-]+", project_id) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in project_id parameter")


def _validate_query(q: str) -> None:
    if len(q) > QUERY_MAX_LEN:
        raise HTTPException(status_code=400, detail="query too long")


def _get_client_or_503() -> Any:
    try:
        return get_mem0_client()
    except Mem0UnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _filter_by_metadata(
    items: list[Any], *, app_id: str | None, project_id: str | None
) -> list[dict[str, Any]]:
    if not app_id and not project_id:
        return [i for i in items if isinstance(i, dict)]

    filtered: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") or {}
        if app_id and metadata.get("app_id") != app_id:
            continue
        if project_id and metadata.get("project_id") != project_id:
            continue
        filtered.append(item)
    return filtered


@router.get("/health")
async def mem0_health() -> dict[str, Any]:
    """Health check for Mem0 integration."""
    # If mem0 is not installed, this endpoint should report that clearly.
    try:
        _get_client_or_503()
    except HTTPException as exc:
        return {"status": "degraded", "mem0": "unavailable", "detail": exc.detail}
    return {"status": "ok", "mem0": "available"}


@router.get("/memories")
async def mem0_list_memories(
    user_id: str | None = Query(default=None),
    app_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    """List memories for a user, optionally filtered by app_id/project_id."""
    _validate_user_id(user_id)
    _validate_app_id(app_id)
    _validate_project_id(project_id)

    defaults = Mem0Settings.from_env()
    effective_user_id = user_id or defaults.default_user_id

    client = _get_client_or_503()
    result = await asyncio.to_thread(client.get_all, user_id=effective_user_id)

    memories: list[Any] = result.get("results", []) if isinstance(result, dict) else (result or [])
    memories_dict = _filter_by_metadata(memories, app_id=app_id, project_id=project_id)
    memories_dict = memories_dict[:limit]

    return {
        "success": True,
        "user_id": effective_user_id,
        "app_id": app_id,
        "project_id": project_id,
        "count": len(memories_dict),
        "memories": memories_dict,
    }


@router.get("/search")
async def mem0_search(
    q: str = Query(..., min_length=1),
    user_id: str | None = Query(default=None),
    app_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
) -> dict[str, Any]:
    """Search memories via vector similarity, optionally filtered by metadata."""
    _validate_query(q)
    _validate_user_id(user_id)
    _validate_app_id(app_id)
    _validate_project_id(project_id)

    defaults = Mem0Settings.from_env()
    effective_user_id = user_id or defaults.default_user_id

    client = _get_client_or_503()
    result = await asyncio.to_thread(client.search, query=q, user_id=effective_user_id, limit=limit)
    results: list[Any] = result.get("results", []) if isinstance(result, dict) else (result or [])
    results_dict = _filter_by_metadata(results, app_id=app_id, project_id=project_id)

    return {
        "success": True,
        "query": q,
        "user_id": effective_user_id,
        "app_id": app_id,
        "project_id": project_id,
        "results": results_dict,
    }


@router.get("/memories/{memory_id}")
async def mem0_get_memory(memory_id: str) -> dict[str, Any]:
    """Get a specific memory by ID."""
    client = _get_client_or_503()
    memory = await asyncio.to_thread(client.get, memory_id=memory_id)
    return {"success": True, "memory_id": memory_id, "memory": memory}


@router.get("/memories/{memory_id}/history")
async def mem0_get_memory_history(memory_id: str) -> dict[str, Any]:
    """Get the change history for a memory."""
    client = _get_client_or_503()
    history = await asyncio.to_thread(client.history, memory_id=memory_id)
    return {"success": True, "memory_id": memory_id, "history": history}


@router.post("/memories")
async def mem0_add_memory(
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Add a memory (write-gated)."""
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Mem0 write operations are disabled. "
                "Set MINDSCAPE_MEM0_WRITE=true to enable."
            ),
        )

    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=400, detail="content is required")

    user_id = payload.get("user_id")
    app_id = payload.get("app_id")
    project_id = payload.get("project_id")
    metadata = payload.get("metadata")

    if user_id is not None and not isinstance(user_id, str):
        raise HTTPException(status_code=400, detail="Invalid user_id")
    if app_id is not None and not isinstance(app_id, str):
        raise HTTPException(status_code=400, detail="Invalid app_id")
    if project_id is not None and not isinstance(project_id, str):
        raise HTTPException(status_code=400, detail="Invalid project_id")
    if metadata is not None and not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="Invalid metadata")

    _validate_user_id(user_id)
    _validate_app_id(app_id)
    _validate_project_id(project_id)

    defaults = Mem0Settings.from_env()
    effective_user_id = user_id or defaults.default_user_id

    # Mirror mem0-mcp metadata behavior: defaults + allow caller overrides.
    final_meta: dict[str, Any] = dict(metadata or {})
    final_meta["app_id"] = app_id or final_meta.get("app_id") or defaults.default_app_id
    if project_id is not None:
        final_meta["project_id"] = project_id
    final_meta["created_via"] = "mindscape-api"
    final_meta["timestamp"] = datetime.utcnow().isoformat()

    client = _get_client_or_503()

    # Match mem0-mcp behavior: pass a string `content` and metadata.
    result = await asyncio.to_thread(
        client.add,
        content,
        user_id=effective_user_id,
        metadata=final_meta,
    )

    return {
        "success": True,
        "result": result,
        "user_id": effective_user_id,
        "app_id": final_meta.get("app_id"),
        "project_id": final_meta.get("project_id"),
    }


@router.put("/memories/{memory_id}")
async def mem0_update_memory(memory_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Update a memory (write-gated)."""
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Mem0 write operations are disabled. "
                "Set MINDSCAPE_MEM0_WRITE=true to enable."
            ),
        )

    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=400, detail="content is required")

    client = _get_client_or_503()
    result = await asyncio.to_thread(client.update, memory_id=memory_id, data=content)
    return {"success": True, "memory_id": memory_id, "result": result}


@router.delete("/memories/{memory_id}")
async def mem0_delete_memory(memory_id: str) -> dict[str, Any]:
    """Delete a memory (write-gated)."""
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Mem0 write operations are disabled. "
                "Set MINDSCAPE_MEM0_WRITE=true to enable."
            ),
        )

    client = _get_client_or_503()
    result = await asyncio.to_thread(client.delete, memory_id=memory_id)
    return {"success": True, "memory_id": memory_id, "result": result}


@router.post("/delete-all")
async def mem0_delete_all(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Delete all memories for a user, optionally filtered by metadata (write-gated)."""
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Mem0 write operations are disabled. "
                "Set MINDSCAPE_MEM0_WRITE=true to enable."
            ),
        )

    confirm = payload.get("confirm", False)
    if confirm is not True:
        raise HTTPException(status_code=400, detail="Must set confirm=true")

    user_id = payload.get("user_id")
    app_id = payload.get("app_id")
    project_id = payload.get("project_id")

    if user_id is not None and not isinstance(user_id, str):
        raise HTTPException(status_code=400, detail="Invalid user_id")
    if app_id is not None and not isinstance(app_id, str):
        raise HTTPException(status_code=400, detail="Invalid app_id")
    if project_id is not None and not isinstance(project_id, str):
        raise HTTPException(status_code=400, detail="Invalid project_id")

    _validate_user_id(user_id)
    _validate_app_id(app_id)
    _validate_project_id(project_id)

    defaults = Mem0Settings.from_env()
    effective_user_id = user_id or defaults.default_user_id

    client = _get_client_or_503()

    # Bulk-delete only supports user_id; for scoped deletes we list + delete like mem0-mcp.
    if not app_id and not project_id:
        logger.warning("Deleting ALL mem0 memories for user={}", effective_user_id)
        result = await asyncio.to_thread(client.delete_all, user_id=effective_user_id)
        return {"success": True, "user_id": effective_user_id, "result": result}

    listed = await mem0_list_memories(
        user_id=user_id,
        app_id=app_id,
        project_id=project_id,
        limit=500,
    )
    memories = listed.get("memories", []) if isinstance(listed, dict) else []
    attempted = 0
    deleted = 0
    errors: list[dict[str, Any]] = []

    for memory in memories:
        if not isinstance(memory, dict):
            continue

        memory_id = memory.get("id") or memory.get("memory_id") or memory.get("_id")
        if not memory_id or not isinstance(memory_id, str):
            errors.append({"error": "Unable to determine memory id for item", "memory": memory})
            continue

        attempted += 1
        try:
            await asyncio.to_thread(client.delete, memory_id=memory_id)
            deleted += 1
        except Exception as e:  # noqa: BLE001
            errors.append({"memory_id": memory_id, "error": str(e), "error_type": type(e).__name__})

    return {
        "success": len(errors) == 0,
        "user_id": effective_user_id,
        "app_id": app_id,
        "project_id": project_id,
        "attempted": attempted,
        "deleted": deleted,
        "errors": errors,
    }