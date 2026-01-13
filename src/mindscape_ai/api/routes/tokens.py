"""Token analytics API routes.

Task 23: Unified token breakdown by source (ConPort / Mem0 / prompts).

We intentionally use an approximation (chars/4) rather than a tokenizer dependency.
This keeps the stack lightweight and deterministic.

Design goals:
- Preserve existing scoping rules (app_id preferred; legacy db supported for ConPort).
- Fail-soft per-source where possible (e.g., Mem0 unavailable shouldn't break ConPort/Prompts).
- Do not expose filesystem paths to clients.
"""

from __future__ import annotations

import asyncio
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, Query

from mindscape_ai.apps.registry import AppRegistryError, discover_apps, normalize_app_roots, read_app_id_from_pyproject
from mindscape_ai.apps.supabase_store import AppStoreError, SupabaseUnavailableError, resolve_conport_db_path_from_supabase
from mindscape_ai.conport.db import ConPortDbPathError, find_workspace_root, resolve_conport_db_path
from mindscape_ai.mem0.client import Mem0Settings, Mem0UnavailableError, get_mem0_client
from mindscape_ai.prompts.fs import PromptsFsError, iter_prompt_files, resolve_prompt_dirs
from mindscape_ai.prompts.stats import compute_file_stats

router = APIRouter(prefix="/tokens", tags=["tokens"])

APP_ID_QUERY_MAX_LEN = 200
USER_ID_QUERY_MAX_LEN = 200
PROJECT_ID_QUERY_MAX_LEN = 200
DB_QUERY_MAX_LEN = 1024


def _approx_tokens_from_chars(chars: int) -> int:
    if chars <= 0:
        return 0
    return max(1, int(math.ceil(chars / 4)))


def _validate_app_id(app_id: str | None) -> None:
    if app_id is None:
        return
    if len(app_id) > APP_ID_QUERY_MAX_LEN:
        raise HTTPException(status_code=400, detail="app_id parameter too long")
    if re.fullmatch(r"[A-Za-z0-9_.-]+", app_id) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in app_id parameter")


def _validate_user_id(user_id: str | None) -> None:
    if user_id is None:
        return
    if len(user_id) > USER_ID_QUERY_MAX_LEN:
        raise HTTPException(status_code=400, detail="user_id parameter too long")
    if re.fullmatch(r"[A-Za-z0-9_.-]+", user_id) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in user_id parameter")


def _validate_project_id(project_id: str | None) -> None:
    if project_id is None:
        return
    if len(project_id) > PROJECT_ID_QUERY_MAX_LEN:
        raise HTTPException(status_code=400, detail="project_id parameter too long")
    if re.fullmatch(r"[A-Za-z0-9_.-]+", project_id) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in project_id parameter")


def _validate_db(db_path: str | None) -> None:
    if db_path is None:
        return
    if len(db_path) > DB_QUERY_MAX_LEN:
        raise HTTPException(status_code=400, detail="db parameter too long")
    if re.fullmatch(r"[A-Za-z0-9_./-]+", db_path) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in db parameter")


@dataclass(frozen=True)
class _ConportResolved:
    db_path: Path | None
    display: str


def _apps_by_id_from_env(app_roots_env: str) -> dict[str, Path]:
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


def _try_resolve_self_app_db() -> tuple[str, Path] | None:
    """Resolve (self_app_id, db_path) if this repo has a ConPort DB."""
    raw = os.getenv("MINDSCAPE_INCLUDE_SELF_APP", "true").strip().lower()
    if raw not in {"1", "true", "yes"}:
        return None

    try:
        root = find_workspace_root(start=Path(__file__))
        app_id = read_app_id_from_pyproject(root / "pyproject.toml")
        db_path = resolve_conport_db_path(None, start=Path(__file__))
        return app_id, db_path
    except Exception:  # noqa: BLE001
        return None


def _resolve_conport_db_optional(*, app_id: str | None, db: str | None) -> _ConportResolved:
    """Resolve ConPort DB.

    Behavior:
    - If app_id is provided: resolve via (self app) -> Supabase -> MINDSCAPE_APP_ROOTS.
      Unknown app_id raises.
    - If app_id is not provided: resolve legacy db param under this workspace.
      If db is None and default context.db does not exist, return db_path=None.
    """
    if app_id is not None:
        self_info = _try_resolve_self_app_db()
        if self_info is not None and app_id == self_info[0]:
            return _ConportResolved(db_path=self_info[1], display=f"app:{app_id}")

        try:
            return _ConportResolved(
                db_path=resolve_conport_db_path_from_supabase(app_id),
                display=f"app:{app_id}",
            )
        except SupabaseUnavailableError:
            pass
        except AppStoreError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            mapping = _apps_by_id_from_env(os.getenv("MINDSCAPE_APP_ROOTS", ""))
        except AppRegistryError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if not mapping:
            raise HTTPException(
                status_code=400,
                detail=(
                    "App registry is not configured. Configure Supabase "
                    "(SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY) "
                    "or set MINDSCAPE_APP_ROOTS."
                ),
            )

        if app_id not in mapping:
            raise HTTPException(status_code=404, detail=f"Unknown app_id: {app_id}")

        return _ConportResolved(db_path=mapping[app_id].resolve(), display=f"app:{app_id}")

    # Legacy/workbench db mode
    try:
        resolved = resolve_conport_db_path(db, start=Path(__file__))
        return _ConportResolved(db_path=resolved, display=str(resolved))
    except ConPortDbPathError as exc:
        # Fail-soft: if user didn't pass db explicitly and the default DB doesn't exist yet,
        # treat ConPort as unconfigured rather than erroring the entire breakdown.
        if db is None:
            return _ConportResolved(db_path=None, display="(unconfigured)")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _open_aiosqlite_ro(path: Path) -> aiosqlite.Connection:
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = await aiosqlite.connect(uri, uri=True)
    await conn.execute("PRAGMA query_only = ON")
    await conn.execute("PRAGMA foreign_keys = ON")

    # Row access by column name where needed.
    conn.row_factory = aiosqlite.Row

    return conn


async def _conport_chars(conn: aiosqlite.Connection) -> int:
    """Approximate ConPort token load by summing the length() of primary text columns."""

    async def _sum(sql: str, params: tuple[Any, ...] = ()) -> int:
        async with conn.execute(sql, params) as cur:
            row = await cur.fetchone()
        if not row:
            return 0
        v = row[0]
        return int(v) if isinstance(v, (int, float)) else 0

    # Use COALESCE to treat NULL as empty string.
    total = 0

    total += await _sum(
        "SELECT COALESCE(SUM(LENGTH(COALESCE(summary,'')) + LENGTH(COALESCE(rationale,'')) + "
        "LENGTH(COALESCE(implementation_details,'')) + LENGTH(COALESCE(tags,''))), 0) FROM decisions"
    )
    total += await _sum(
        "SELECT COALESCE(SUM(LENGTH(COALESCE(status,'')) + LENGTH(COALESCE(description,''))), 0) "
        "FROM progress_entries"
    )
    total += await _sum(
        "SELECT COALESCE(SUM(LENGTH(COALESCE(name,'')) + LENGTH(COALESCE(description,'')) + LENGTH(COALESCE(tags,''))), 0) "
        "FROM system_patterns"
    )
    total += await _sum(
        "SELECT COALESCE(SUM(LENGTH(COALESCE(category,'')) + LENGTH(COALESCE(key,'')) + LENGTH(COALESCE(value,''))), 0) "
        "FROM custom_data"
    )
    total += await _sum(
        "SELECT COALESCE(SUM(LENGTH(COALESCE(content,''))), 0) FROM product_context"
    )
    total += await _sum(
        "SELECT COALESCE(SUM(LENGTH(COALESCE(content,''))), 0) FROM active_context"
    )
    total += await _sum(
        "SELECT COALESCE(SUM(LENGTH(COALESCE(workspace_id,'')) + LENGTH(COALESCE(source_item_type,'')) + "
        "LENGTH(COALESCE(source_item_id,'')) + LENGTH(COALESCE(target_item_type,'')) + LENGTH(COALESCE(target_item_id,'')) + "
        "LENGTH(COALESCE(relationship_type,'')) + LENGTH(COALESCE(description,''))), 0) FROM context_links"
    )

    return total


def _mem0_text_for_item(item: dict[str, Any]) -> str:
    v = item.get("memory")
    if isinstance(v, str) and v.strip():
        return v
    v2 = item.get("content")
    if isinstance(v2, str) and v2.strip():
        return v2
    return ""


def _mem0_filter(items: list[Any], *, app_id: str | None, project_id: str | None) -> list[dict[str, Any]]:
    if not app_id and not project_id:
        return [i for i in items if isinstance(i, dict)]

    out: list[dict[str, Any]] = []
    for i in items:
        if not isinstance(i, dict):
            continue
        meta = i.get("metadata") or {}
        if app_id and meta.get("app_id") != app_id:
            continue
        if project_id and meta.get("project_id") != project_id:
            continue
        out.append(i)
    return out


@router.get("/breakdown")
async def tokens_breakdown(
    app_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    db: str | None = Query(default=None),
    prompts_max_file_bytes: int = Query(default=200_000, ge=1_000, le=5_000_000),
) -> dict[str, Any]:
    """Return an approximate token breakdown by source.

    Notes:
    - app_id is the preferred scope across all sources.
    - db is only used for ConPort (legacy workbench mode).
    """

    _validate_app_id(app_id)
    _validate_user_id(user_id)
    _validate_project_id(project_id)
    _validate_db(db)

    # --- ConPort ---
    conport_chars = 0
    conport_items: dict[str, int] = {}
    conport_error: str | None = None

    resolved = _resolve_conport_db_optional(app_id=app_id, db=db)
    if resolved.db_path is None:
        conport_configured = False
    else:
        conport_configured = True
        try:
            conn = await _open_aiosqlite_ro(resolved.db_path)
            try:
                conport_chars = await _conport_chars(conn)
            finally:
                await conn.close()
        except Exception as exc:  # noqa: BLE001
            conport_error = str(exc)
            conport_configured = False
            conport_chars = 0

    conport_tokens = _approx_tokens_from_chars(conport_chars)

    # --- Prompts ---
    prompts_chars = 0
    prompts_files_count = 0
    prompts_error: str | None = None

    try:
        prompt_dirs = resolve_prompt_dirs(app_id=app_id)
        prompts_configured = bool(prompt_dirs)

        # We need per-dir base paths for compute_file_stats(); iter per base dir for correctness.
        for base in prompt_dirs:
            files = iter_prompt_files([base])
            prompts_files_count += len(files)

            for info in files:
                stats = compute_file_stats(base, info, max_file_bytes=prompts_max_file_bytes)

                if stats.char_count is not None:
                    prompts_chars += stats.char_count
                else:
                    # If we didn't read the file (too large), approximate from bytes.
                    prompts_chars += int(stats.bytes)

    except PromptsFsError as exc:
        prompts_configured = False
        prompts_error = str(exc)
        prompts_chars = 0
        prompts_files_count = 0

    prompts_tokens = _approx_tokens_from_chars(prompts_chars)

    # --- Mem0 ---
    mem0_chars = 0
    mem0_items = 0
    mem0_error: str | None = None

    try:
        defaults = Mem0Settings.from_env()
        effective_user = user_id or defaults.default_user_id

        client = get_mem0_client()
        result = await asyncio.to_thread(client.get_all, user_id=effective_user)
        raw_items: list[Any] = result.get("results", []) if isinstance(result, dict) else (result or [])
        items = _mem0_filter(raw_items, app_id=app_id, project_id=project_id)

        mem0_items = len(items)
        for item in items:
            text = _mem0_text_for_item(item)
            mem0_chars += len(text)

        mem0_configured = True

    except Mem0UnavailableError as exc:
        mem0_configured = False
        mem0_error = str(exc)
    except Exception as exc:  # noqa: BLE001
        mem0_configured = False
        mem0_error = str(exc)

    mem0_tokens = _approx_tokens_from_chars(mem0_chars)

    total_tokens = conport_tokens + prompts_tokens + mem0_tokens

    return {
        "app_id": app_id,
        "user_id": user_id,
        "project_id": project_id,
        "sources": {
            "conport": {
                "configured": conport_configured,
                "chars": conport_chars,
                "approx_tokens": conport_tokens,
                "error": conport_error,
                "db": resolved.display,
                "items": conport_items,
            },
            "prompts": {
                "configured": prompts_configured,
                "chars": prompts_chars,
                "approx_tokens": prompts_tokens,
                "file_count": prompts_files_count,
                "error": prompts_error,
            },
            "mem0": {
                "configured": mem0_configured,
                "chars": mem0_chars,
                "approx_tokens": mem0_tokens,
                "item_count": mem0_items,
                "error": mem0_error,
            },
        },
        "total": {"approx_tokens": total_tokens},
        "notes": {
            "estimator": "chars/4",
            "prompts_max_file_bytes": prompts_max_file_bytes,
        },
    }
