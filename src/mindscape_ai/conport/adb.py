"""Async SQLite helpers for ConPort Workbench mode.

Workbench mode is read-only by default. This module opens the DB using SQLite URI mode
(`mode=ro`) and enforces query-only semantics.
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite


async def open_readonly_aiosqlite(db_path: Path) -> aiosqlite.Connection:
    """Open a read-only aiosqlite connection."""

    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = await aiosqlite.connect(uri, uri=True)

    # Read-only guardrails.
    await conn.execute("PRAGMA query_only = ON")
    await conn.execute("PRAGMA foreign_keys = ON")

    # Row access by column name.
    conn.row_factory = aiosqlite.Row

    return conn
