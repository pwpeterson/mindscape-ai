"""Apps registry API routes.

Provides a safe way for the UI to discover which apps/projects are available
in this Mindscape instance, keyed by `app_id` (from each app's pyproject.toml).

Security:
- The backend determines allowed app roots (env/config).
- Clients never provide paths; they only select an `app_id`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from mindscape_ai.apps.registry import (
    AppRegistryError,
    discover_apps,
    normalize_app_roots,
)

router = APIRouter(prefix="/apps", tags=["apps"])


def _parse_app_roots_env(raw: str | None) -> list[str]:
    """Parse MINDSCAPE_APP_ROOTS as a comma-separated list of absolute/relative paths."""
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


@router.get("")
@router.get("/")
async def list_apps() -> dict[str, Any]:
    """List available apps/projects.

    Env:
        MINDSCAPE_APP_ROOTS: comma-separated list of app root directories.
            Each must contain a pyproject.toml with [project].name.
    """
    roots_raw = _parse_app_roots_env(os.getenv("MINDSCAPE_APP_ROOTS"))
    if not roots_raw:
        # Fail closed: no implicit filesystem scanning.
        return {"apps": [], "source": {"env": "MINDSCAPE_APP_ROOTS", "configured": False}}

    try:
        roots = normalize_app_roots([Path(p) for p in roots_raw])
        apps = discover_apps(roots)
    except AppRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Avoid leaking filesystem paths to the UI; only expose what the UI needs.
    return {
        "apps": [
            {
                "app_id": app.app_id,
                "has_conport": app.conport_db_path is not None,
            }
            for app in apps
        ],
        "source": {"env": "MINDSCAPE_APP_ROOTS", "configured": True, "count": len(apps)},
    }
