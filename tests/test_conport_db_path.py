from __future__ import annotations

from pathlib import Path

import pytest

from mindscape_ai.conport.db import (
    ConPortDbPathError,
    find_workspace_root,
    resolve_conport_db_path,
)


def test_find_workspace_root_from_repo_root() -> None:
    root = find_workspace_root(Path.cwd())
    assert (root / "context_portal").is_dir()


def test_resolve_conport_db_path_default() -> None:
    db_path = resolve_conport_db_path(None)
    assert db_path.name == "context.db"
    assert "context_portal" in db_path.parts
    assert db_path.exists()


def test_resolve_conport_db_path_rejects_traversal() -> None:
    with pytest.raises(ConPortDbPathError):
        resolve_conport_db_path("../context_portal/context.db")


def test_resolve_conport_db_path_rejects_non_db_extension() -> None:
    with pytest.raises(ConPortDbPathError):
        resolve_conport_db_path("context_portal/context.txt")


def test_resolve_conport_db_path_rejects_outside_context_portal(tmp_path: Path) -> None:
    rogue = tmp_path / "rogue.db"
    rogue.write_text("", encoding="utf-8")
    with pytest.raises(ConPortDbPathError):
        resolve_conport_db_path(str(rogue))


def test_resolve_conport_db_path_rejects_nul_byte() -> None:
    with pytest.raises(ConPortDbPathError):
        resolve_conport_db_path("context_portal/context.db\x00")


def test_resolve_conport_db_path_rejects_invalid_path_type() -> None:
    # Some objects can raise on __fspath__/str or be otherwise invalid.
    class BadPath:
        def __str__(self) -> str:
            raise ValueError("boom")

    with pytest.raises(ConPortDbPathError):
        resolve_conport_db_path(BadPath())
