"""ConPort Workbench (SQLite) database path resolution and safe read-only access.

Requirements (from PRD):
- Detect workspace root by walking upward until `context_portal/` exists.
- Resolve DB paths relative to that root.
- DB path must:
  - be under `context_portal/`
  - end in `.db`
  - disallow `..` traversal
- Prefer read-only access for Workbench mode.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConPortDbPathError(ValueError):
    """Raised when a ConPort Workbench DB path is unsafe or invalid."""

    message: str

    def __str__(self) -> str:  # pragma: no cover
        return self.message


def find_workspace_root(start: Path | None = None) -> Path:
    """Find the workspace root by walking upward until `context_portal/` exists.

    Args:
        start: Directory to start searching from (defaults to CWD).

    Returns:
        The workspace root path.

    Raises:
        ConPortDbPathError: If a root cannot be found.
    """

    cursor = (start or Path.cwd()).resolve()
    # If passed a file path, start from its parent.
    if cursor.is_file():
        cursor = cursor.parent

    for candidate in (cursor, *cursor.parents):
        if (candidate / "context_portal").is_dir():
            return candidate

    raise ConPortDbPathError(
        "Unable to locate workspace root (no 'context_portal/' directory found when walking "
        "upward)."
    )


def resolve_conport_db_path(db: str | Path | None = None, *, start: Path | None = None) -> Path:
    """Resolve and validate a ConPort SQLite DB path for Workbench mode.

    Args:
        db: Requested DB path.
            - None -> defaults to `context_portal/context.db` under the detected workspace root.
            - Relative paths are resolved against the detected workspace root.
            - Absolute paths are allowed only if they are under `<root>/context_portal/`.
        start: Directory to start searching for workspace root (defaults to CWD).

    Returns:
        A normalized absolute Path to the DB.

    Raises:
        ConPortDbPathError: If the DB path is invalid or unsafe.
    """

    root = find_workspace_root(start)
    context_dir = (root / "context_portal").resolve()

    if db is None:
        candidate = context_dir / "context.db"
    else:
        try:
            db_str = str(db)
        except Exception as exc:  # noqa: BLE001
            raise ConPortDbPathError("DB path is invalid.") from exc

        # Avoid bubbling up raw ValueErrors/OSErrors (e.g. embedded NUL byte) as 500s.
        if "\x00" in db_str:
            raise ConPortDbPathError("DB path is invalid (NUL byte).")

        try:
            db_path = Path(db_str)
        except Exception as exc:  # noqa: BLE001
            raise ConPortDbPathError("DB path is invalid.") from exc

        # Explicitly forbid traversal attempts regardless of whether the final resolved path would
        # land inside context_portal.
        if ".." in db_path.parts:
            raise ConPortDbPathError("DB path traversal is not allowed ('..' detected).")

        candidate = db_path if db_path.is_absolute() else root / db_path

    try:
        resolved = candidate.resolve()
    except Exception as exc:  # noqa: BLE001
        raise ConPortDbPathError("DB path is invalid.") from exc

    if resolved.suffix.lower() != ".db":
        raise ConPortDbPathError("DB path must end with '.db'.")

    # Must be under context_portal/
    try:
        resolved.relative_to(context_dir)
    except ValueError as exc:
        raise ConPortDbPathError(
            "DB path must be located under the workspace 'context_portal/' directory."
        ) from exc

    if not resolved.exists() or not resolved.is_file():
        raise ConPortDbPathError(f"DB file not found: {resolved}")

    return resolved


def open_readonly_sqlite(db_path: Path) -> sqlite3.Connection:
    """Open a read-only SQLite connection.

    Notes:
        - Uses SQLite URI mode with `mode=ro`.
        - Creates a new connection per call (caller owns closing).

    Raises:
        sqlite3.OperationalError: If connection fails (e.g. file unreadable).
    """

    # URI requires forward slashes; Path.as_posix() is correct on Linux/macOS.
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)

    # Some sane defaults for read-heavy workloads.
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA foreign_keys = ON")

    return conn
