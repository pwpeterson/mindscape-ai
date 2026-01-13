"""Apps registry API routes.

Provides a safe way for the UI to discover which apps/projects are available
in this Mindscape instance, keyed by `app_id`.

Data sources:
- Preferred: Supabase table `public.mindscape_ai_apps` (managed registry + CRUD)
- Fallback (dev/tests): MINDSCAPE_APP_ROOTS filesystem scanning

Security:
- The browser UI never sends filesystem paths.
- Paths are stored server-side and used only for local resolution (e.g. ConPort DB).
- Mutating operations are gated behind MINDSCAPE_APPS_WRITE=true (fail-closed).
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from mindscape_ai.apps.registry import (
    AppRegistryError,
    discover_apps,
    normalize_app_roots,
    read_app_id_from_pyproject,
)
from mindscape_ai.apps.supabase_store import (
    AppStoreError,
    MindscapeApp,
    SupabaseUnavailableError,
    create_app_in_supabase,
    delete_app_in_supabase,
    list_apps_from_supabase,
    update_app_in_supabase,
)
from mindscape_ai.conport.db import ConPortDbPathError, find_workspace_root, resolve_conport_db_path

router = APIRouter(prefix="/apps", tags=["apps"])

# Hard limits for untrusted payloads/query params (DoS guardrails)
APP_ID_MAX_LEN = 200
ROOT_PATH_MAX_LEN = 4096


def _write_enabled() -> bool:
    """Whether apps write endpoints are enabled.

    Fail-closed: unknown values disable writes.
    """
    raw = os.getenv("MINDSCAPE_APPS_WRITE", "false").strip().lower()
    if raw in {"1", "true", "yes"}:
        return True
    if raw in {"0", "false", "no", ""}:
        return False
    return False


def _parse_app_roots_env(raw: str | None) -> list[str]:
    """Parse MINDSCAPE_APP_ROOTS as a comma-separated list of absolute/relative paths."""
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _self_app_flag_raw() -> str:
    """Return the raw env value used to control the implicit self-app behavior."""
    return os.getenv("MINDSCAPE_INCLUDE_SELF_APP", "true").strip().lower()


def _self_app_enabled(flag_raw: str) -> bool:
    return flag_raw in {"1", "true", "yes"}


@lru_cache(maxsize=4)
def _self_app_for_flag(flag_raw: str) -> MindscapeApp | None:
    """Return an implicit MindscapeApp for the current repo, if resolvable.

    Cache key is the env flag value so tests (and running processes) can toggle
    MINDSCAPE_INCLUDE_SELF_APP without getting stuck with stale cached results.
    """
    if not _self_app_enabled(flag_raw):
        return None

    try:
        root = find_workspace_root(start=Path(__file__))
        app_id = read_app_id_from_pyproject(root / "pyproject.toml")

        # Ensures the DB exists and is under <root>/context_portal/.
        resolve_conport_db_path(None, start=Path(__file__))

        return MindscapeApp(
            app_id=app_id,
            display_name=None,
            enabled=True,
            sort_order=-1000,
            has_conport=True,
        )
    except (ConPortDbPathError, AppRegistryError, OSError, ValueError):
        return None


def _self_app() -> MindscapeApp | None:
    return _self_app_for_flag(_self_app_flag_raw())


def _validate_app_id(app_id: Any) -> str:
    if not isinstance(app_id, str) or not app_id.strip():
        raise HTTPException(status_code=400, detail="app_id is required")
    value = app_id.strip()
    if len(value) > APP_ID_MAX_LEN:
        raise HTTPException(status_code=400, detail="app_id too long")
    # Allow typical package/project names: letters, digits, underscore, dash, dot.
    if re.fullmatch(r"[A-Za-z0-9_.-]+", value) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in app_id")
    return value


def _validate_root_path(root_path: Any) -> str:
    if not isinstance(root_path, str) or not root_path.strip():
        raise HTTPException(status_code=400, detail="root_path is required")
    value = root_path.strip()
    # Guard against control characters that can lead to confusing logs/headers.
    if "\n" in value or "\r" in value:
        raise HTTPException(status_code=400, detail="Invalid root_path (control characters)")
    if "\x00" in value:
        raise HTTPException(status_code=400, detail="Invalid root_path (NUL byte)")
    if len(value) > ROOT_PATH_MAX_LEN:
        raise HTTPException(status_code=400, detail="root_path too long")

    p = Path(value).expanduser()
    if not p.is_absolute():
        raise HTTPException(status_code=400, detail="root_path must be an absolute path")
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail="root_path does not exist or is not a directory")
    return str(p.resolve())


@router.get("")
@router.get("/")
async def list_apps() -> dict[str, Any]:
    """List available apps/projects for the UI dropdown.

    Preferred source: Supabase (`mindscape_ai_apps`).
    Fallback: MINDSCAPE_APP_ROOTS env scanning (legacy/dev/tests).

    Additionally, for local/dev UX, we may include an implicit "self app" entry for this
    Mindscape-AI instance so the dropdown isn't empty on first run.
    """
    self_app = _self_app()

    # Preferred: Supabase registry
    try:
        apps = list_apps_from_supabase(include_disabled=False)

        if self_app is not None and all(a.app_id != self_app.app_id for a in apps):
            apps = [self_app, *apps]

        return {
            "apps": [{"app_id": a.app_id, "has_conport": a.has_conport} for a in apps],
            "source": {
                "type": "supabase",
                "table": "mindscape_ai_apps",
                "configured": True,
                "count": len(apps),
            },
        }
    except SupabaseUnavailableError:
        # Fall back to env scanning
        pass
    except AppStoreError as exc:
        # Misconfigured Supabase table/rows shouldn't 500 the UI; surface as 400.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Fallback: legacy env scanning
    roots_raw = _parse_app_roots_env(os.getenv("MINDSCAPE_APP_ROOTS"))
    if not roots_raw:
        # Fail closed: no implicit scanning of arbitrary roots. However, it's still safe to
        # include the current repo as a single implicit option when available.
        apps_out: list[dict[str, Any]] = []
        if self_app is not None:
            apps_out.append({"app_id": self_app.app_id, "has_conport": self_app.has_conport})

        return {
            "apps": apps_out,
            "source": {"env": "MINDSCAPE_APP_ROOTS", "configured": False, "count": len(apps_out)},
        }

    try:
        roots = normalize_app_roots([Path(p) for p in roots_raw])
        discovered = discover_apps(roots)
    except AppRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    apps_out = [
        {"app_id": app.app_id, "has_conport": app.conport_db_path is not None} for app in discovered
    ]
    if self_app is not None and all(a["app_id"] != self_app.app_id for a in apps_out):
        apps_out.insert(0, {"app_id": self_app.app_id, "has_conport": self_app.has_conport})

    return {
        "apps": apps_out,
        "source": {"env": "MINDSCAPE_APP_ROOTS", "configured": True, "count": len(apps_out)},
    }


@router.post("")
@router.post("/")
async def create_app(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Create an app in Supabase (write-gated)."""
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Apps write operations are disabled. "
                "Set MINDSCAPE_APPS_WRITE=true to enable."
            ),
        )

    app_id = _validate_app_id(payload.get("app_id"))
    root_path = _validate_root_path(payload.get("root_path"))

    display_name = payload.get("display_name")
    if display_name is not None and not isinstance(display_name, str):
        raise HTTPException(status_code=400, detail="Invalid display_name")

    enabled = payload.get("enabled", True)
    if enabled is not None and not isinstance(enabled, bool):
        raise HTTPException(status_code=400, detail="Invalid enabled")

    sort_order = payload.get("sort_order", 0)
    if sort_order is not None and not isinstance(sort_order, int):
        raise HTTPException(status_code=400, detail="Invalid sort_order")

    try:
        created = create_app_in_supabase(
            app_id=app_id,
            root_path=root_path,
            display_name=display_name,
            enabled=bool(enabled),
            sort_order=int(sort_order),
        )
    except SupabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AppStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"app": created.__dict__}


@router.patch("/{app_id}")
async def update_app(app_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Update an app in Supabase (write-gated)."""
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Apps write operations are disabled. "
                "Set MINDSCAPE_APPS_WRITE=true to enable."
            ),
        )

    app_id_norm = _validate_app_id(app_id)
    patch: dict[str, Any] = {}

    if "display_name" in payload:
        dn = payload.get("display_name")
        if dn is not None and not isinstance(dn, str):
            raise HTTPException(status_code=400, detail="Invalid display_name")
        patch["display_name"] = dn

    if "root_path" in payload:
        patch["root_path"] = _validate_root_path(payload.get("root_path"))

    if "enabled" in payload:
        en = payload.get("enabled")
        if not isinstance(en, bool):
            raise HTTPException(status_code=400, detail="Invalid enabled")
        patch["enabled"] = en

    if "sort_order" in payload:
        so = payload.get("sort_order")
        if not isinstance(so, int):
            raise HTTPException(status_code=400, detail="Invalid sort_order")
        patch["sort_order"] = so

    try:
        updated = update_app_in_supabase(app_id=app_id_norm, patch=patch)
    except SupabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AppStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"app": updated.__dict__}


@router.delete("/{app_id}")
async def delete_app(app_id: str) -> dict[str, Any]:
    """Delete an app in Supabase (write-gated)."""
    if not _write_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Apps write operations are disabled. "
                "Set MINDSCAPE_APPS_WRITE=true to enable."
            ),
        )

    app_id_norm = _validate_app_id(app_id)

    try:
        deleted = delete_app_in_supabase(app_id=app_id_norm)
    except SupabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AppStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"deleted": deleted, "app_id": app_id_norm}
