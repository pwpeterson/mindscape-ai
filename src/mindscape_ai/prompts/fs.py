"""Prompt filesystem utilities (Phase 2).

Task 22: Prompt hot reload

This module provides two primitives:
- Resolve prompt directories for the current scope (app_id-scoped)
- Compute a stable signature of prompt content so UIs can refresh when files change

Design goals:
- No client-supplied filesystem paths
- Reuse existing multi-app resolution patterns (Supabase registry, MINDSCAPE_APP_ROOTS fallback,
  implicit self-app)
- Avoid extra runtime deps (no watchdog). The backend can expose a polling or SSE surface on top
  of `prompts_signature()`.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from mindscape_ai.apps.registry import (
    AppRegistryError,
    discover_apps,
    normalize_app_roots,
    read_app_id_from_pyproject,
)
from mindscape_ai.apps.supabase_store import AppStoreError
from mindscape_ai.conport.db import find_workspace_root
from mindscape_ai.supabase.client import SupabaseUnavailableError, get_supabase_client


class PromptsFsError(RuntimeError):
    """Raised when prompt filesystem resolution fails."""


PROMPTS_DIRNAME_DEFAULT = "prompts"


def _parse_prompts_dirnames(raw: str | None) -> list[str]:
    """Parse prompt directory names.

    Format:
        MINDSCAPE_PROMPTS_DIRS="prompts,prompts/shared,assets/prompts"

    Security:
        - entries must be relative (no absolute paths)
        - no traversal (..)
        - allow only [A-Za-z0-9_./-]
    """
    if not raw:
        return []

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    out: list[str] = []

    for p in parts:
        if not p:
            continue
        if "\x00" in p:
            continue
        if Path(p).is_absolute():
            continue
        if ".." in Path(p).parts:
            continue
        # strict allowlist
        import re

        if re.fullmatch(r"[A-Za-z0-9_./-]+", p) is None:
            continue

        out.append(p)

    # de-dupe deterministically
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)

    return uniq


def prompts_dirnames() -> list[str]:
    """Directory names under an app root that contain prompt files.

    Precedence:
        1) MINDSCAPE_PROMPTS_DIRS (comma-separated list)
        2) MINDSCAPE_PROMPTS_DIRNAME (single dir name)
        3) default: "prompts"
    """
    dirs_raw = os.getenv("MINDSCAPE_PROMPTS_DIRS")
    parsed = _parse_prompts_dirnames(dirs_raw)
    if parsed:
        return parsed

    raw = os.getenv("MINDSCAPE_PROMPTS_DIRNAME", PROMPTS_DIRNAME_DEFAULT)
    value = raw.strip() if isinstance(raw, str) else ""
    return [value or PROMPTS_DIRNAME_DEFAULT]


def _self_app_flag_raw() -> str:
    return os.getenv("MINDSCAPE_INCLUDE_SELF_APP", "true").strip().lower()


def _self_app_enabled(flag_raw: str) -> bool:
    return flag_raw in {"1", "true", "yes"}


def _try_resolve_self_app_root() -> Path | None:
    """Resolve the current repo root when treated as an implicit app.

    This mirrors how ConPort resolution treats the repo as a valid app.
    """
    if not _self_app_enabled(_self_app_flag_raw()):
        return None

    try:
        root = find_workspace_root(start=Path(__file__))
        # Validate this looks like an app root.
        read_app_id_from_pyproject(root / "pyproject.toml")
        return root
    except Exception:  # noqa: BLE001
        return None


def _resolve_app_root_from_supabase(app_id: str) -> Path:
    """Resolve app_id -> root_path using Supabase (internal only).

    Security:
        root_path is never returned to browser clients; used only for local filesystem resolution.
    """
    client = get_supabase_client()

    resp = (
        client.table("mindscape_ai_apps")
        .select("app_id,root_path,enabled")
        .eq("app_id", app_id)
        .limit(1)
        .execute()
    )

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

    root = Path(root_raw).expanduser()
    try:
        resolved = root.resolve()
    except Exception as exc:  # noqa: BLE001
        raise AppStoreError("Invalid root_path for app_id") from exc

    if not resolved.exists() or not resolved.is_dir():
        raise AppStoreError("Resolved app root does not exist or is not a directory.")

    return resolved


def _apps_roots_by_id_from_env(app_roots_env: str) -> dict[str, Path]:
    raw = app_roots_env.strip()
    if not raw:
        return {}

    roots_raw = [p.strip() for p in raw.split(",") if p.strip()]
    roots = normalize_app_roots([Path(p) for p in roots_raw])
    apps = discover_apps(roots)

    out: dict[str, Path] = {}
    for app in apps:
        out[app.app_id] = app.root_path
    return out


def resolve_prompt_dirs(*, app_id: str | None) -> list[Path]:
    """Resolve prompt directories for a given scope.

    Resolution:
        - If app_id is None: attempt implicit self-app root.
        - If app_id is set: Supabase registry preferred; MINDSCAPE_APP_ROOTS fallback.

    Returns:
        List of existing directories (may be empty).

    Raises:
        PromptsFsError: if app_id is specified but cannot be resolved.
    """
    dirnames = prompts_dirnames()

    root: Path | None
    if app_id is None:
        root = _try_resolve_self_app_root()
        if root is None:
            return []
    else:
        root = None

        # Preferred: Supabase registry
        try:
            root = _resolve_app_root_from_supabase(app_id)
        except SupabaseUnavailableError:
            root = None
        except AppStoreError as exc:
            raise PromptsFsError(str(exc)) from exc

        # Fallback: MINDSCAPE_APP_ROOTS
        if root is None:
            try:
                mapping = _apps_roots_by_id_from_env(os.getenv("MINDSCAPE_APP_ROOTS", ""))
            except AppRegistryError as exc:
                raise PromptsFsError(str(exc)) from exc

            if not mapping:
                raise PromptsFsError(
                    "App registry is not configured. Configure Supabase "
                    "(SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY) "
                    "or set MINDSCAPE_APP_ROOTS."
                )

            if app_id not in mapping:
                raise PromptsFsError(f"Unknown app_id: {app_id}")

            root = mapping[app_id]

    out: list[Path] = []
    for dn in dirnames:
        candidate = (root / dn).resolve()
        if candidate.exists() and candidate.is_dir():
            out.append(candidate)

    # Deterministic ordering
    out = sorted(out, key=lambda p: p.as_posix().lower())
    return out


@dataclass(frozen=True)
class PromptFileInfo:
    relpath: str
    bytes: int
    mtime_ns: int


def iter_prompt_files(dirs: Iterable[Path], *, max_files: int = 2000) -> list[PromptFileInfo]:
    """List prompt files under one or more directories.

    Safety:
        - Only lists regular files
        - Uses deterministic ordering by relative path
        - Hard limit to avoid pathological trees
    """
    out: list[PromptFileInfo] = []

    for base in dirs:
        base = base.resolve()
        if not base.exists() or not base.is_dir():
            continue

        for p in base.rglob("*"):
            if len(out) >= max_files:
                break
            if not p.exists() or not p.is_file():
                continue

            try:
                rel = p.relative_to(base).as_posix()
            except Exception:  # noqa: BLE001
                continue

            try:
                stat = p.stat()
            except OSError:
                continue

            out.append(
                PromptFileInfo(
                    relpath=rel,
                    bytes=int(stat.st_size),
                    mtime_ns=int(stat.st_mtime_ns),
                )
            )

    out.sort(key=lambda x: x.relpath.lower())
    return out


def prompts_signature(dirs: Iterable[Path]) -> str:
    """Compute a stable signature for prompt directories.

    Uses (relpath, bytes, mtime_ns) for each file. Fast enough for dev hot reload.
    Not intended as a cryptographic integrity check.
    """
    files = iter_prompt_files(dirs)

    h = hashlib.sha256()
    for f in files:
        h.update(f.relpath.encode("utf-8", errors="ignore"))
        h.update(b"\0")
        h.update(str(f.bytes).encode("ascii"))
        h.update(b"\0")
        h.update(str(f.mtime_ns).encode("ascii"))
        h.update(b"\n")

    return h.hexdigest()
