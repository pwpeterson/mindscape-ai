"""ConPort integration.

Phase 1: Workbench (SQLite) mode with strict DB path resolution and read-only querying.
"""

from __future__ import annotations

__all__ = [
    "ConPortDbPathError",
    "find_workspace_root",
    "open_readonly_aiosqlite",
    "open_readonly_sqlite",
    "resolve_conport_db_path",
]

from mindscape_ai.conport.adb import open_readonly_aiosqlite
from mindscape_ai.conport.db import (
    ConPortDbPathError,
    find_workspace_root,
    open_readonly_sqlite,
    resolve_conport_db_path,
)
