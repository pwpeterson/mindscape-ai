"""Multi-app registry for Mindscape-AI.

Mindscape tracks multiple *external* apps/projects. Each app has its own:
- ConPort DB (typically: <app_root>/context_portal/context.db)
- Mem0 memories keyed by app_id (same identifier)
- Prompts store keyed by app_id (Supabase, planned)

Security model:
- The backend owns the list of allowed app roots (config/env).
- The frontend only selects by `app_id`.
- No arbitrary filesystem paths are accepted from clients.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    # Python 3.11+
    import tomllib as _toml  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    # Python 3.10 fallback (add tomli dependency for production)
    import tomli as _toml  # type: ignore[no-redef]


@dataclass(frozen=True)
class AppRef:
    """Resolved app/project reference."""

    app_id: str
    root_path: Path
    conport_db_path: Path | None


class AppRegistryError(RuntimeError):
    """Raised when an app registry operation fails."""


def _safe_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def read_app_id_from_pyproject(pyproject_path: Path) -> str:
    """Read `app_id` from `[project].name` in a pyproject.toml."""
    try:
        raw = _toml.loads(pyproject_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AppRegistryError(f"pyproject.toml not found: {pyproject_path}") from exc
    except Exception as exc:  # noqa: BLE001
        raise AppRegistryError(f"Unable to parse pyproject.toml: {pyproject_path}") from exc

    project = raw.get("project")
    if not isinstance(project, dict):
        raise AppRegistryError(f"Missing [project] table in {pyproject_path}")

    name = _safe_str(project.get("name"))
    if name is None:
        raise AppRegistryError(f"Missing [project].name in {pyproject_path}")

    return name


def resolve_conport_db_for_app_root(app_root: Path) -> Path | None:
    """Resolve a ConPort DB path for an app root.

    Convention: <app_root>/context_portal/context.db
    """
    candidate = (app_root / "context_portal" / "context.db").resolve()
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def normalize_app_roots(roots: list[str | Path]) -> list[Path]:
    """Normalize and validate app roots.

    Notes:
        - Roots must exist and be directories.
        - We resolve them to absolute paths for consistency.
    """
    out: list[Path] = []
    for root in roots:
        p = Path(root).expanduser()
        try:
            resolved = p.resolve()
        except Exception as exc:  # noqa: BLE001
            raise AppRegistryError(f"Invalid app root path: {p}") from exc
        if not resolved.exists() or not resolved.is_dir():
            raise AppRegistryError(f"App root does not exist or is not a directory: {resolved}")
        out.append(resolved)
    return out


def discover_apps(app_roots: list[Path]) -> list[AppRef]:
    """Discover apps from explicit app roots.

    Each root is expected to contain a pyproject.toml.
    """
    apps: list[AppRef] = []
    for root in app_roots:
        pyproject = root / "pyproject.toml"
        app_id = read_app_id_from_pyproject(pyproject)

        apps.append(
            AppRef(
                app_id=app_id,
                root_path=root,
                conport_db_path=resolve_conport_db_for_app_root(root),
            )
        )

    # Deterministic ordering for UI + tests
    return sorted(apps, key=lambda a: a.app_id.lower())
