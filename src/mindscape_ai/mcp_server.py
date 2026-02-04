"""Mindscape-AI MCP Server (stdio).

Implements Phase 4 (P-28/P-29): expose Mindscape-AI's aggregated view as a local
stdio MCP server using FastMCP.

Tools:
- conport_now
- conport_search
- mem0_search
- prompts_files
- tokens_breakdown
- add_app

Resources:
- conport://now
- tokens://breakdown

Notes:
- This MCP server directly reuses the same underlying implementations as the
  FastAPI routes (e.g. `mindscape_ai.api.routes.conport.conport_now`).
- Those implementations raise FastAPI `HTTPException` for validation and error
  reporting; we convert those to plain `RuntimeError` for MCP clients.

Runtime:
    python -m mindscape_ai.mcp_server

Environment variables (used by resources only):
- MINDSCAPE_MCP_APP_ID
- MINDSCAPE_MCP_DB
- MINDSCAPE_MCP_USER_ID
- MINDSCAPE_MCP_PROJECT_ID
- MINDSCAPE_MCP_PROMPTS_MAX_FILE_BYTES
"""

from __future__ import annotations

import os
from functools import partial
from typing import Any

from anyio import to_thread
from fastapi import HTTPException
from fastmcp import FastMCP

from mindscape_ai.api.routes.apps import create_app as _apps_create_app
from mindscape_ai.api.routes.conport import conport_now as _conport_now
from mindscape_ai.api.routes.conport import conport_search as _conport_search
from mindscape_ai.api.routes.mem0 import mem0_search as _mem0_search
from mindscape_ai.api.routes.prompts import prompts_files as _prompts_files
from mindscape_ai.api.routes.tokens import tokens_breakdown as _tokens_breakdown
from mindscape_ai.apps.sqlite_store import create_app_in_sqlite

mcp = FastMCP(name="Mindscape-AI")


def _env_str(name: str) -> str | None:
    v = os.getenv(name)
    if v is None:
        return None
    v = v.strip()
    return v or None


def _env_int(name: str) -> int | None:
    v = _env_str(name)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _raise_as_runtime(exc: Exception) -> None:
    """Normalize common app exceptions to RuntimeError for MCP clients."""
    if isinstance(exc, HTTPException):
        # Keep it terse; clients typically display the message directly.
        raise RuntimeError(f"{exc.status_code}: {exc.detail}") from exc
    raise RuntimeError(str(exc)) from exc


@mcp.tool(
    name="conport_now",
    description="Return ConPort product_context, active_context, and recent activity.",
    tags={"conport", "read"},
)
async def tool_conport_now(app_id: str | None = None, db: str | None = None) -> dict[str, Any]:
    try:
        return await _conport_now(app_id=app_id, db=db)
    except Exception as exc:  # noqa: BLE001
        _raise_as_runtime(exc)
        raise


@mcp.tool(
    name="conport_search",
    description="Search ConPort decisions and custom_data (FTS when available).",
    tags={"conport", "search", "read"},
)
async def tool_conport_search(
    q: str,
    limit: int = 10,
    app_id: str | None = None,
    db: str | None = None,
) -> dict[str, Any]:
    try:
        return await _conport_search(q=q, limit=limit, app_id=app_id, db=db)
    except Exception as exc:  # noqa: BLE001
        _raise_as_runtime(exc)
        raise


@mcp.tool(
    name="mem0_search",
    description="Semantic search over Mem0 memories with optional metadata filtering.",
    tags={"mem0", "search", "read"},
)
async def tool_mem0_search(
    q: str,
    user_id: str | None = None,
    app_id: str | None = None,
    project_id: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    try:
        return await _mem0_search(q=q, user_id=user_id, app_id=app_id, project_id=project_id, limit=limit)
    except Exception as exc:  # noqa: BLE001
        _raise_as_runtime(exc)
        raise


@mcp.tool(
    name="prompts_files",
    description="List prompt files with per-file stats (including approx token counts).",
    tags={"prompts", "read"},
)
async def tool_prompts_files(
    app_id: str | None = None,
    max_files: int = 500,
    max_file_bytes: int = 200_000,
) -> dict[str, Any]:
    try:
        return await _prompts_files(app_id=app_id, max_files=max_files, max_file_bytes=max_file_bytes)
    except Exception as exc:  # noqa: BLE001
        _raise_as_runtime(exc)
        raise


@mcp.tool(
    name="tokens_breakdown",
    description="Return approximate token breakdown across ConPort, Mem0, and prompts.",
    tags={"tokens", "read"},
)
async def tool_tokens_breakdown(
    app_id: str | None = None,
    user_id: str | None = None,
    project_id: str | None = None,
    db: str | None = None,
    prompts_max_file_bytes: int = 200_000,
) -> dict[str, Any]:
    try:
        return await _tokens_breakdown(
            app_id=app_id,
            user_id=user_id,
            project_id=project_id,
            db=db,
            prompts_max_file_bytes=prompts_max_file_bytes,
        )
    except Exception as exc:  # noqa: BLE001
        _raise_as_runtime(exc)
        raise


@mcp.tool(
    name="add_app",
    description=(
        "Add a new app to the mindscape_ai_apps registry table (write-gated). "
        "Requires MINDSCAPE_APPS_WRITE=true."
    ),
    tags={"apps", "write"},
)
async def tool_add_app(
    app_id: str,
    root_path: str,
    display_name: str | None = None,
    enabled: bool = True,
    sort_order: int = 0,
) -> dict[str, Any]:
    """Create an app record in Supabase-backed registry.

    Mirrors the FastAPI endpoint POST /apps (validation + write-gating included).
    """
    payload: dict[str, Any] = {
        "app_id": app_id,
        "root_path": root_path,
        "display_name": display_name,
        "enabled": enabled,
        "sort_order": sort_order,
    }

    try:
        return await _apps_create_app(payload=payload)
    except HTTPException as exc:
        # Robust fallback: if Supabase is unavailable/misconfigured, write to local SQLite registry
        # so `add_app` remains usable for local/dev deployments.
        if exc.status_code == 503 and isinstance(exc.detail, str) and "Supabase is not configured" in exc.detail:
            try:
                created = await to_thread.run_sync(
                    partial(
                        create_app_in_sqlite,
                        app_id=app_id,
                        root_path=root_path,
                        display_name=display_name,
                        enabled=enabled,
                        sort_order=sort_order,
                    )
                )
                return {"app": created.__dict__}
            except Exception as exc2:  # noqa: BLE001
                _raise_as_runtime(exc2)
                raise
        _raise_as_runtime(exc)
        raise
    except Exception as exc:  # noqa: BLE001
        _raise_as_runtime(exc)
        raise


@mcp.resource("conport://now")
async def resource_conport_now() -> dict[str, Any]:
    """Resource snapshot of ConPort now() using env defaults."""
    try:
        return await _conport_now(app_id=_env_str("MINDSCAPE_MCP_APP_ID"), db=_env_str("MINDSCAPE_MCP_DB"))
    except Exception as exc:  # noqa: BLE001
        _raise_as_runtime(exc)
        raise


@mcp.resource("tokens://breakdown")
async def resource_tokens_breakdown() -> dict[str, Any]:
    """Resource snapshot of tokens_breakdown using env defaults."""
    prompts_max_file_bytes = _env_int("MINDSCAPE_MCP_PROMPTS_MAX_FILE_BYTES") or 200_000
    try:
        return await _tokens_breakdown(
            app_id=_env_str("MINDSCAPE_MCP_APP_ID"),
            user_id=_env_str("MINDSCAPE_MCP_USER_ID"),
            project_id=_env_str("MINDSCAPE_MCP_PROJECT_ID"),
            db=_env_str("MINDSCAPE_MCP_DB"),
            prompts_max_file_bytes=prompts_max_file_bytes,
        )
    except Exception as exc:  # noqa: BLE001
        _raise_as_runtime(exc)
        raise


if __name__ == "__main__":
    # IMPORTANT for stdio MCP servers:
    # stdout must be reserved for MCP protocol frames. Any non-protocol output can cause
    # MCP hosts to error with "MCP error -32000: Connection closed".
    #
    # In fastmcp==2.2.10, FastMCP.run() logs "Starting server ..." before starting stdio.
    # Avoid that by calling run_async directly (no startup log).
    import anyio

    anyio.run(mcp.run_async, "stdio")
