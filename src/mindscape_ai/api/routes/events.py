"""Events API routes (Server-Sent Events).

Implements T012: GET /api/v1/events/stream with heartbeat + event objects.

Notes:
- SSE uses a long-lived HTTP response with `text/event-stream`.
- This endpoint is intentionally minimal and emits:
  - a one-time "hello" event
  - periodic "heartbeat" events to keep proxies/connections alive
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Awaitable
from datetime import datetime, timezone
from typing import Any, Protocol

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/events", tags=["events"])


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sse_frame(*, event: str | None = None, data: Any = None, id: str | None = None) -> str:
    """Format a single SSE frame.

    SSE frame format:
        id: <id>\n
        event: <name>\n
        data: <line1>\n
        data: <line2>\n
        \n

    Data must be line-oriented; if JSON is used, we encode it into one line.
    """
    lines: list[str] = []

    if id is not None:
        lines.append(f"id: {id}")

    if event is not None:
        lines.append(f"event: {event}")

    if data is None:
        lines.append("data: null")
    elif isinstance(data, str):
        # For multiline strings, split into multiple data lines.
        for chunk in data.splitlines() or [""]:
            lines.append(f"data: {chunk}")
    else:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        lines.append(f"data: {payload}")

    return "\n".join(lines) + "\n\n"


class _DisconnectAware(Protocol):
    def is_disconnected(self) -> Awaitable[bool]: ...


async def _stream_events(
    request: _DisconnectAware, *, heartbeat_seconds: int
) -> AsyncGenerator[bytes, None]:
    # Let clients know they can reconnect after a delay if disconnected.
    yield "retry: 10000\n\n".encode("utf-8")

    hello = {
        "type": "hello",
        "ts": _utc_now_iso(),
        "data": {"service": "mindscape-ai", "protocol": "sse-v1"},
    }
    yield _sse_frame(event="hello", data=hello).encode("utf-8")

    # NOTE:
    # `request.is_disconnected()` can block indefinitely under some test transports.
    # To keep the stream responsive (and tests non-hanging), do a short-timeout check.
    async def _is_disconnected_nonblocking() -> bool:
        try:
            return await asyncio.wait_for(request.is_disconnected(), timeout=0.001)
        except TimeoutError:
            return False

    while True:
        heartbeat = {"type": "heartbeat", "ts": _utc_now_iso(), "data": {}}
        yield _sse_frame(event="heartbeat", data=heartbeat).encode("utf-8")

        await asyncio.sleep(heartbeat_seconds)

        if await _is_disconnected_nonblocking():
            return


@router.get("/stream")
async def events_stream(
    request: Request,
    heartbeat_seconds: int = Query(default=15, ge=5, le=60),
) -> StreamingResponse:
    """Stream server events.

    Heartbeats are emitted periodically as SSE events to keep connections alive.
    """
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # Nginx: disable response buffering for streaming.
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        _stream_events(request, heartbeat_seconds=heartbeat_seconds),
        media_type="text/event-stream",
        headers=headers,
    )