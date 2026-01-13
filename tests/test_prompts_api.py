from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mindscape_ai.api.app import create_app
from mindscape_ai.api.routes.prompts import _stream_prompts


class _DummyRequest:
    async def is_disconnected(self) -> bool:
        return False


def test_openapi_includes_prompts_endpoints() -> None:
    app = create_app()
    client = TestClient(app)

    resp = client.get("/openapi.json")
    assert resp.status_code == 200

    payload = resp.json()
    paths = payload.get("paths", {})

    assert "/api/v1/prompts/signature" in paths
    assert "/api/v1/prompts/stream" in paths
    assert "/api/v1/prompts/files" in paths


def test_prompts_signature_for_temp_app_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Create a fake app root with a pyproject.toml + prompts dir.
    app_root = tmp_path / "myapp"
    app_root.mkdir(parents=True)

    (app_root / "pyproject.toml").write_text(
        """[project]\nname = \"my-app\"\nversion = \"0.0.0\"\n""",
        encoding="utf-8",
    )

    prompts_dir = app_root / "prompts"
    prompts_dir.mkdir()

    (prompts_dir / "hello.txt").write_text("hello", encoding="utf-8")

    # Force env-based app root resolution.
    monkeypatch.setenv("MINDSCAPE_APP_ROOTS", str(app_root))
    monkeypatch.setenv("MINDSCAPE_INCLUDE_SELF_APP", "false")
    # Clear both the preferred env vars and the legacy Mindscape-prefixed aliases.
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("MINDSCAPE_SUPABASE_URL", raising=False)
    monkeypatch.delenv("MINDSCAPE_SUPABASE_SERVICE_ROLE_KEY", raising=False)

    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/prompts/signature?app_id=my-app")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["app_id"] == "my-app"
    assert payload["configured"] is True
    assert payload["file_count"] == 1
    assert isinstance(payload["signature"], str)
    assert len(payload["signature"]) == 64


def test_prompts_files_unconfigured_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    # Make deterministic: no prompts directories resolved.
    import mindscape_ai.api.routes.prompts as prompts_routes

    monkeypatch.setattr(prompts_routes, "resolve_prompt_dirs", lambda *, app_id: [])

    app = create_app()
    client = TestClient(app)

    resp = client.get("/api/v1/prompts/files")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["configured"] is False
    assert payload["file_count"] == 0
    assert payload["files"] == []


def test_prompts_files_for_temp_app_root_includes_virtual_paths_and_tokens(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Create a fake app root with a pyproject.toml + prompts dir.
    app_root = tmp_path / "myapp"
    app_root.mkdir(parents=True)

    (app_root / "pyproject.toml").write_text(
        """[project]\nname = "my-app"\nversion = "0.0.0"\n""",
        encoding="utf-8",
    )

    prompts_dir = app_root / "prompts"
    prompts_dir.mkdir()

    (prompts_dir / "hello.txt").write_text("hello world\n", encoding="utf-8")

    # Also create an oversized file to verify max_file_bytes behavior.
    # Endpoint enforces max_file_bytes >= 1000, so make this larger than 1000.
    (prompts_dir / "big.txt").write_bytes(b"a" * 2000)

    # Force env-based app root resolution.
    monkeypatch.setenv("MINDSCAPE_APP_ROOTS", str(app_root))
    monkeypatch.setenv("MINDSCAPE_INCLUDE_SELF_APP", "false")
    # Clear both the preferred env vars and the legacy Mindscape-prefixed aliases.
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("MINDSCAPE_SUPABASE_URL", raising=False)
    monkeypatch.delenv("MINDSCAPE_SUPABASE_SERVICE_ROLE_KEY", raising=False)

    app = create_app()
    client = TestClient(app)

    resp = client.get(
        "/api/v1/prompts/files",
        params={"app_id": "my-app", "max_files": 50, "max_file_bytes": 1000},
    )
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["app_id"] == "my-app"
    assert payload["configured"] is True
    assert payload["dir_count"] >= 1
    assert payload["file_count"] == 2

    files = payload["files"]
    paths = [f["path"] for f in files]
    assert "prompts/hello.txt" in paths
    assert "prompts/big.txt" in paths

    # Ensure we never leak absolute filesystem paths.
    # (Paths must not contain tmp_path segments.)
    tmp_piece = tmp_path.as_posix()
    assert all(tmp_piece not in p for p in paths)

    hello = next(f for f in files if f["path"] == "prompts/hello.txt")
    assert hello["is_text"] is True
    assert hello["char_count"] is not None
    assert hello["approx_tokens"] is not None
    assert isinstance(hello["approx_tokens"], int)

    big = next(f for f in files if f["path"] == "prompts/big.txt")
    # Too large to read under max_file_bytes=10 -> deep stats are None but bytes still present.
    assert big["is_text"] is True
    assert big["char_count"] is None
    assert big["approx_tokens"] is None


@pytest.mark.anyio
async def test_prompts_stream_generator_emits_retry_hello_and_signature(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Create a fake app root so the generator has something deterministic.
    app_root = tmp_path / "myapp"
    app_root.mkdir(parents=True)

    (app_root / "pyproject.toml").write_text(
        """[project]\nname = \"my-app\"\nversion = \"0.0.0\"\n""",
        encoding="utf-8",
    )

    prompts_dir = app_root / "prompts"
    prompts_dir.mkdir()

    (prompts_dir / "hello.txt").write_text("hello", encoding="utf-8")

    monkeypatch.setenv("MINDSCAPE_APP_ROOTS", str(app_root))
    monkeypatch.setenv("MINDSCAPE_INCLUDE_SELF_APP", "false")

    req = _DummyRequest()

    gen = _stream_prompts(req, app_id="my-app", poll_seconds=10.0)

    retry = (await anext(gen)).decode("utf-8")
    hello = (await anext(gen)).decode("utf-8")
    sig = (await anext(gen)).decode("utf-8")

    await gen.aclose()

    assert "retry:" in retry

    assert "event: hello" in hello
    assert '"type":"hello"' in hello

    assert "event: signature" in sig
    assert '"type":"signature"' in sig
    assert '"file_count":1' in sig
