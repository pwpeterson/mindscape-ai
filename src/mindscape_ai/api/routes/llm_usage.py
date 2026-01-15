"""LLM usage analytics API routes (Supabase-backed).

Backed by Supabase Postgres objects created in:
- `supabase/migrations/20260115_0001_llm_usage_events.sql`

Design goals:
- Server-side only: the browser UI never talks to Supabase directly.
- Privacy: no raw prompts; only hashes/aggregates already stored in Supabase.
- Simple filters suitable for the Prompts panel: app_id/task/model/provider + time range.

Endpoints:
- GET /api/v1/llm-usage/events
- GET /api/v1/llm-usage/daily
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import httpx
from fastapi import APIRouter, HTTPException, Query

from mindscape_ai.supabase.client import SupabaseUnavailableError, get_supabase_client

router = APIRouter(prefix="/llm-usage", tags=["llm-usage"])

# Hard limits for untrusted query params (DoS guardrails)
APP_ID_QUERY_MAX_LEN: Final[int] = 200
TASK_QUERY_MAX_LEN: Final[int] = 200
PROVIDER_QUERY_MAX_LEN: Final[int] = 50
MODEL_QUERY_MAX_LEN: Final[int] = 200
ROUTE_QUERY_MAX_LEN: Final[int] = 200

# Patterns based on migration constraints
APP_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_.-]+$")
TASK_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_.:-]+$")
PROVIDER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_.-]+$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    # Supabase works well with RFC3339/ISO; include timezone offset.
    return dt.isoformat()


def _validate_len(name: str, value: str | None, max_len: int) -> None:
    if value is None:
        return
    if len(value) > max_len:
        raise HTTPException(status_code=400, detail=f"{name} parameter too long")


def _validate_app_id(app_id: str | None) -> None:
    if app_id is None:
        return
    _validate_len("app_id", app_id, APP_ID_QUERY_MAX_LEN)
    if APP_ID_RE.fullmatch(app_id) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in app_id parameter")


def _validate_task(task: str | None) -> None:
    if task is None:
        return
    _validate_len("task", task, TASK_QUERY_MAX_LEN)
    if TASK_RE.fullmatch(task) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in task parameter")


def _validate_provider(provider: str | None) -> None:
    if provider is None:
        return
    _validate_len("provider", provider, PROVIDER_QUERY_MAX_LEN)
    if PROVIDER_RE.fullmatch(provider) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in provider parameter")


def _validate_model(model: str | None) -> None:
    if model is None:
        return
    _validate_len("model", model, MODEL_QUERY_MAX_LEN)
    # Model names vary widely; only enforce max length here.


def _validate_route(route: str | None) -> None:
    if route is None:
        return
    _validate_len("route", route, ROUTE_QUERY_MAX_LEN)
    # Allow almost anything (route is server-generated); only length-guard.


def _get_client_or_503() -> Any:
    try:
        return get_supabase_client()
    except SupabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/events")
async def llm_usage_events(
    app_id: str | None = Query(default=None),
    task: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    route: str | None = Query(default=None),
    since_hours: int = Query(default=24, ge=0, le=24 * 365),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    """List recent LLM usage events.

    Returns a subset of safe columns for display in the UI.
    """
    _validate_app_id(app_id)
    _validate_task(task)
    _validate_provider(provider)
    _validate_model(model)
    _validate_route(route)

    client = _get_client_or_503()

    since_dt = _utc_now() - timedelta(hours=int(since_hours))
    since_iso = _iso(since_dt)

    try:
        query = client.table("llm_usage_events").select(
            ",".join(
                [
                    "id",
                    "request_id",
                    "app_id",
                    "task",
                    "user_id",
                    "agent_id",
                    "project_id",
                    "provider",
                    "model",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "estimated_cost",
                    "prompt_sha256",
                    "prompt_chars",
                    "message_count",
                    "route",
                    "status_code",
                    "latency_ms",
                    "stream",
                    "created_at",
                ]
            )
        )

        if app_id is not None:
            query = query.eq("app_id", app_id)
        if task is not None:
            query = query.eq("task", task)
        if provider is not None:
            query = query.eq("provider", provider)
        if model is not None:
            query = query.eq("model", model)
        if route is not None:
            query = query.eq("route", route)

        query = query.gte("created_at", since_iso).order("created_at", desc=True).limit(limit)

        resp = query.execute()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Supabase is unreachable (llm usage).") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to query llm usage events: {exc}") from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail="Unexpected response from Supabase (llm_usage_events)")

    return {
        "app_id": app_id,
        "filters": {
            "task": task,
            "provider": provider,
            "model": model,
            "route": route,
            "since_hours": since_hours,
            "limit": limit,
        },
        "count": len(data),
        "events": [r for r in data if isinstance(r, dict)],
        "source": {"type": "supabase", "table": "llm_usage_events"},
    }


@router.get("/daily")
async def llm_usage_daily(
    app_id: str | None = Query(default=None),
    task: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=90, ge=1, le=365),
) -> dict[str, Any]:
    """Return daily rollups from Supabase `public.llm_usage_daily` view."""
    _validate_app_id(app_id)
    _validate_task(task)
    _validate_provider(provider)
    _validate_model(model)

    client = _get_client_or_503()

    since_dt = _utc_now() - timedelta(days=int(days))
    since_iso = _iso(since_dt)

    try:
        query = client.table("llm_usage_daily").select(
            ",".join(
                [
                    "day",
                    "app_id",
                    "task",
                    "provider",
                    "model",
                    "requests",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "estimated_cost",
                ]
            )
        )

        if app_id is not None:
            query = query.eq("app_id", app_id)
        if task is not None:
            query = query.eq("task", task)
        if provider is not None:
            query = query.eq("provider", provider)
        if model is not None:
            query = query.eq("model", model)

        query = query.gte("day", since_iso).order("day", desc=True).limit(limit)

        resp = query.execute()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Supabase is unreachable (llm usage).") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to query llm usage daily rollups: {exc}") from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail="Unexpected response from Supabase (llm_usage_daily)")

    return {
        "app_id": app_id,
        "filters": {"task": task, "provider": provider, "model": model, "days": days, "limit": limit},
        "count": len(data),
        "rows": [r for r in data if isinstance(r, dict)],
        "source": {"type": "supabase", "view": "llm_usage_daily"},
    }