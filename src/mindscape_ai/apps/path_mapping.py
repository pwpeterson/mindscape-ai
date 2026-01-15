"""Runtime path mapping helpers for Mindscape-AI.

Problem:
- The apps registry stores `root_path` values that are meaningful on the machine where they
  were created/managed (often the host).
- The API may run inside a container where those host paths are not mounted at the same
  absolute location.
- Mindscape uses `root_path` to compute:
  - has_conport: does <root_path>/context_portal/context.db exist?
  - app_id -> conport db path resolution for ConPort routes
If the API runtime cannot see the stored host path, these checks fail even when the DB exists.

Solution:
- Provide a small, explicit, server-side prefix-mapping layer that translates stored paths
  to runtime-visible paths before any filesystem existence checks.

Configuration:
- Preferred: MINDSCAPE_PATH_MAP_JSON
    JSON array of objects: [{"from": "/host/path", "to": "/container/path"}, ...]
- Fallback: MINDSCAPE_PATH_MAP
    Comma-separated pairs: "/host/path=/container/path,/other=/mapped"

Matching:
- Longest-prefix wins (more specific mappings take precedence).
- Mapping applies only to absolute paths.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class PathMapping:
    src: Path
    dst: Path


def _parse_map_json(raw: str) -> list[PathMapping]:
    try:
        parsed = json.loads(raw)
    except Exception:
        return []

    if not isinstance(parsed, list):
        return []

    out: list[PathMapping] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        src = item.get("from")
        dst = item.get("to")
        if not isinstance(src, str) or not isinstance(dst, str):
            continue
        src_p = Path(src).expanduser()
        dst_p = Path(dst).expanduser()
        if not src_p.is_absolute() or not dst_p.is_absolute():
            continue
        out.append(PathMapping(src=src_p, dst=dst_p))
    return out


def _parse_map_pairs(raw: str) -> list[PathMapping]:
    out: list[PathMapping] = []
    for part in [p.strip() for p in raw.split(",") if p.strip()]:
        # Support either "=" or "=>" if copied from docs
        if "=>" in part:
            left, right = part.split("=>", 1)
        elif "=" in part:
            left, right = part.split("=", 1)
        else:
            continue

        left = left.strip()
        right = right.strip()
        if not left or not right:
            continue

        src_p = Path(left).expanduser()
        dst_p = Path(right).expanduser()
        if not src_p.is_absolute() or not dst_p.is_absolute():
            continue
        out.append(PathMapping(src=src_p, dst=dst_p))
    return out


def _load_mappings() -> list[PathMapping]:
    raw_json = os.getenv("MINDSCAPE_PATH_MAP_JSON", "").strip()
    if raw_json:
        mappings = _parse_map_json(raw_json)
        if mappings:
            return mappings

    raw_pairs = os.getenv("MINDSCAPE_PATH_MAP", "").strip()
    if raw_pairs:
        mappings = _parse_map_pairs(raw_pairs)
        if mappings:
            return mappings

    return []


def _iter_sorted_by_specificity(mappings: Iterable[PathMapping]) -> list[PathMapping]:
    # Longest src path wins (most specific prefix).
    return sorted(mappings, key=lambda m: len(m.src.as_posix()), reverse=True)


def map_runtime_path(path: Path) -> Path:
    """Translate a stored host path to a runtime-visible path.

    If no mapping applies, returns the original path unchanged.

    Args:
        path: The stored path (usually from registry).

    Returns:
        A Path that should be used for filesystem operations on this API runtime.
    """
    try:
        p = path.expanduser()
    except Exception:
        return path

    # Only map absolute paths; relative paths are interpreted by callers.
    if not p.is_absolute():
        return p

    mappings = _iter_sorted_by_specificity(_load_mappings())
    if not mappings:
        return p

    for m in mappings:
        try:
            rel = p.relative_to(m.src)
        except ValueError:
            continue

        # Preserve subpath under the mapped destination.
        return (m.dst / rel)

    return p