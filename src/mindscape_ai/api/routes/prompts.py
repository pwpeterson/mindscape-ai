"""Prompts API routes.

Task 22: Prompt hot reload (file watching + UI updates).

This module exposes:
- GET /api/v1/prompts/signature: returns a stable signature representing prompt file state
- GET /api/v1/prompts/stream: SSE stream emitting signature updates when prompt files change

Notes:
- No filesystem paths are accepted from clients.
- No filesystem paths are returned to clients.
- Resolution is app_id-scoped and uses the same registry patterns as ConPort.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncGenerator, Awaitable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from mindscape_ai.prompts.fs import (
    PromptsFsError,
    iter_prompt_files,
    prompts_dirnames,
    prompts_signature,
    resolve_prompt_dirs,
)
from mindscape_ai.prompts.stats import compute_file_stats

router = APIRouter(prefix="/prompts", tags=["prompts"])

APP_ID_QUERY_MAX_LEN = 200


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_app_id_query_param(app_id: str | None) -> None:
    if app_id is None:
        return

    if len(app_id) > APP_ID_QUERY_MAX_LEN:
        raise HTTPException(status_code=400, detail="app_id parameter too long")

    if re.fullmatch(r"[A-Za-z0-9_.-]+", app_id) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in app_id parameter")


@router.get("/signature")
async def prompts_signature_endpoint(
    app_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return a stable signature for the current prompt files.

    The signature changes when any prompt file is added/removed or when size/mtime changes.
    """

    _validate_app_id_query_param(app_id)

    try:
        dirs = resolve_prompt_dirs(app_id=app_id)
        files = iter_prompt_files(dirs)
        sig = prompts_signature(dirs)
    except PromptsFsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "app_id": app_id,
        "signature": sig,
        "file_count": len(files),
        "configured": bool(dirs),
    }


def _virtual_prefix_for_dir(dir_path: Path, candidates: list[str]) -> str:
    """Return the best-matching configured prompts dirname for a resolved directory.

    This creates a stable, non-sensitive "virtual" prefix for returning prompt file paths
    without leaking absolute filesystem roots.
    """
    p = dir_path.as_posix().lower().rstrip("/")
    best = ""
    for dn in candidates:
        dn_norm = dn.strip().lower().strip("/")
        if not dn_norm:
            continue
        if p.endswith("/" + dn_norm) or p == dn_norm:
            # Prefer the longest match (handles nested names like "prompts/shared").
            if len(dn_norm) > len(best):
                best = dn_norm
    return best or dir_path.name


@router.get("/files")
async def prompts_files(
    app_id: str | None = Query(default=None),
    max_files: int = Query(default=500, ge=1, le=5000),
    max_file_bytes: int = Query(default=200_000, ge=1_000, le=5_000_000),
) -> dict[str, Any]:
    """List prompt files with per-file stats (approx token counts).

    Notes:
    - No filesystem paths are accepted from clients.
    - No filesystem paths are returned to clients.
    - Returned file paths are "virtual": <prompts_dir>/<relpath>.
    """
    _validate_app_id_query_param(app_id)

    try:
        dirs = resolve_prompt_dirs(app_id=app_id)
    except PromptsFsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not dirs:
        return {
            "app_id": app_id,
            "configured": False,
            "dir_count": 0,
            "file_count": 0,
            "files": [],
            "notes": {"prompts_max_file_bytes": max_file_bytes, "max_files": max_files},
        }

    configured_names = prompts_dirnames()

    files_out: list[dict[str, Any]] = []
    for base in dirs:
        base_files = iter_prompt_files([base], max_files=max_files)
        prefix = _virtual_prefix_for_dir(base, configured_names)
        for info in base_files:
            stats = compute_file_stats(base, info, max_file_bytes=max_file_bytes)
            virtual_path = f"{prefix}/{stats.relpath}".replace("//", "/")
            files_out.append(
                {
                    "path": virtual_path,
                    "relpath": stats.relpath,
                    "prompt_dir": prefix,
                    "bytes": stats.bytes,
                    "mtime_ns": stats.mtime_ns,
                    "is_text": stats.is_text,
                    "char_count": stats.char_count,
                    "line_count": stats.line_count,
                    "approx_tokens": stats.approx_tokens,
                }
            )

            if len(files_out) >= max_files:
                break
        if len(files_out) >= max_files:
            break

    # Deterministic ordering by virtual path.
    files_out.sort(key=lambda r: str(r.get("path", "")).lower())

    return {
        "app_id": app_id,
        "configured": True,
        "dir_count": len(dirs),
        "file_count": len(files_out),
        "files": files_out,
        "notes": {"prompts_max_file_bytes": max_file_bytes, "max_files": max_files},
    }


class _DisconnectAware(Protocol):
    def is_disconnected(self) -> Awaitable[bool]: ...


def _sse_frame(*, event: str | None = None, data: Any = None, id: str | None = None) -> str:
    """Format a single SSE frame (copied from events router to keep this module standalone)."""

    lines: list[str] = []

    if id is not None:
        lines.append(f"id: {id}")

    if event is not None:
        lines.append(f"event: {event}")

    if data is None:
        lines.append("data: null")
    elif isinstance(data, str):
        for chunk in data.splitlines() or [""]:
            lines.append(f"data: {chunk}")
    else:
        # Encode JSON on one line.
        import json

        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        lines.append(f"data: {payload}")

    return "\n".join(lines) + "\n\n"


@dataclass(frozen=True)
class _SigState:
    signature: str
    file_count: int


async def _stream_prompts(
    request: _DisconnectAware,
    *,
    app_id: str | None,
    poll_seconds: float,
) -> AsyncGenerator[bytes, None]:
    # Tell clients they can retry after a delay.
    yield b"retry: 5000\n\n"

    yield _sse_frame(
        event="hello",
        data={"type": "hello", "ts": _utc_now_iso(), "data": {"service": "mindscape-ai", "protocol": "prompts-sse-v1"}},
    ).encode("utf-8")

    def compute() -> _SigState:
        dirs = resolve_prompt_dirs(app_id=app_id)
        files = iter_prompt_files(dirs)
        return _SigState(signature=prompts_signature(dirs), file_count=len(files))

    try:
        state = compute()
    except PromptsFsError as exc:
        yield _sse_frame(event="error", data={"type": "error", "ts": _utc_now_iso(), "data": {"message": str(exc)}}).encode(
            "utf-8"
        )
        return

    # Emit initial state.
    yield _sse_frame(
        event="signature",
        data={
            "type": "signature",
            "ts": _utc_now_iso(),
            "data": {"signature": state.signature, "file_count": state.file_count},
        },
    ).encode("utf-8")

    async def _is_disconnected_nonblocking() -> bool:
        try:
            return await asyncio.wait_for(request.is_disconnected(), timeout=0.001)
        except TimeoutError:
            return False

    while True:
        await asyncio.sleep(poll_seconds)

        if await _is_disconnected_nonblocking():
            return

        try:
            next_state = compute()
        except PromptsFsError:
            # Treat as transient/unavailable.
            continue

        if next_state.signature != state.signature or next_state.file_count != state.file_count:
            yield _sse_frame(
                event="changed",
                data={
                    "type": "changed",
                    "ts": _utc_now_iso(),
                    "data": {
                        "prev_signature": state.signature,
                        "signature": next_state.signature,
                        "file_count": next_state.file_count,
                    },
                },
            ).encode("utf-8")
            state = next_state


@router.get("/stream")
async def prompts_stream(
    request: Request,
    app_id: str | None = Query(default=None),
    poll_seconds: float = Query(default=2.0, ge=0.25, le=10.0),
) -> StreamingResponse:
    """Stream prompt signature updates via SSE."""

    _validate_app_id_query_param(app_id)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    return StreamingResponse(
        _stream_prompts(request, app_id=app_id, poll_seconds=poll_seconds),
        media_type="text/event-stream",
        headers=headers,
    )
