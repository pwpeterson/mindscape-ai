from __future__ import annotations

from pathlib import Path

import pytest

from mindscape_ai.apps.path_mapping import map_runtime_path
from mindscape_ai.apps.sqlite_store import create_app_in_sqlite, list_apps_from_sqlite


def _touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"")


def test_map_runtime_path_uses_longest_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Two mappings where one is a more specific prefix; ensure longest prefix wins.
    dst1 = tmp_path / "dst1"
    dst2 = tmp_path / "dst2"

    monkeypatch.setenv(
        "MINDSCAPE_PATH_MAP_JSON",
        (
            '[{"from":"/host","to":"'
            + dst1.as_posix()
            + '"},{"from":"/host/app","to":"'
            + dst2.as_posix()
            + '"}]'
        ),
    )

    out = map_runtime_path(Path("/host/app/subdir"))
    assert out.as_posix() == (dst2 / "subdir").as_posix()


def test_sqlite_store_has_conport_respects_path_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Simulate a registry row that stores a host-only root path.
    stored_root = Path("/host/apps/mindscape-ai")

    # Simulate the runtime-visible path where the app actually exists.
    runtime_root = tmp_path / "workspace"
    _touch(runtime_root / "context_portal" / "context.db")

    monkeypatch.setenv(
        "MINDSCAPE_PATH_MAP_JSON",
        f'[{{"from":"{stored_root.as_posix()}","to":"{runtime_root.as_posix()}"}}]',
    )
    monkeypatch.setenv("MINDSCAPE_APPS_SQLITE_DB", str(tmp_path / "apps_registry.db"))

    # Insert the host path (which does not exist on this test filesystem).
    create_app_in_sqlite(
        app_id="mindscape-ai",
        root_path=stored_root.as_posix(),
        display_name="Mindscape AI",
        enabled=True,
        sort_order=1,
    )

    apps = list_apps_from_sqlite(include_disabled=False)
    assert [a.app_id for a in apps] == ["mindscape-ai"]
    assert apps[0].has_conport is True


def test_supabase_store_internal_has_conport_respects_path_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Supabase store computes has_conport by searching for context_portal/context.db under the
    # runtime-mapped root path. Validate that behavior directly.
    from mindscape_ai.apps import supabase_store as store

    stored_root = Path("/home/pwp/srv/apps/mindscape-ai")
    runtime_root = tmp_path / "runtime" / "workspace"
    _touch(runtime_root / "context_portal" / "context.db")

    monkeypatch.setenv(
        "MINDSCAPE_PATH_MAP_JSON",
        f'[{{"from":"{stored_root.as_posix()}","to":"{runtime_root.as_posix()}"}}]',
    )

    assert store._has_conport_db(stored_root) is True
