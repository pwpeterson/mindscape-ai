"""LLM usage analytics API routes (Supabase-backed).

Backed by Supabase Postgres objects created in:
- `supabase/migrations/20260119_model_proxy_tables_reengineering.sql`

These endpoints intentionally keep the original `/llm-usage/*` URLs to avoid
churn in the web UI, but the underlying data source is now the `model_proxy_*`
schema.

Design goals:
- Server-side only: the browser UI never talks to Supabase directly.
- Privacy: usage endpoints never return raw prompts.
- Support filters suitable for the Prompts panel: app_id/task/model/provider + time range.

Endpoints:
- GET /api/v1/llm-usage/events      -> model_proxy_requests
- GET /api/v1/llm-usage/daily       -> model_proxy_daily_stats
- GET /api/v1/llm-usage/raw-prompts -> model_proxy_payloads (privacy-sensitive)
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
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

# Patterns based on common constraints (tables are more permissive, but we keep these guardrails)
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


def _pick_first_available_object(client: Any, candidates: list[str]) -> str:
    """Pick the first Supabase table/view that exists from a list.

    Notes:
        - This is primarily for backwards compatibility: older deployments/tests used
          `llm_usage_events`, `llm_usage_daily`, and `llm_raw_prompts`.
        - New deployments use `model_proxy_requests`, `model_proxy_daily_stats`,
          and `model_proxy_payloads`.
        - Probing is done via a cheap `select(...).limit(1)` request. If the object
          doesn't exist or cannot be queried, we try the next candidate.
    """
    last_exc: Exception | None = None
    for name in candidates:
        try:
            _ = client.table(name).select("id").limit(1).execute()
            return name
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            continue
    raise HTTPException(
        status_code=500,
        detail=f"None of the expected Supabase objects exist: {candidates}. Last error: {last_exc}",
    )


def _extract_messages_from_request_json(request_json: Any) -> Any:
    """Best-effort extraction of chat messages from model-proxy request payload."""
    if isinstance(request_json, dict):
        # Standard OpenAI-style
        if isinstance(request_json.get("messages"), list):
            return request_json.get("messages")

        # Some wrappers may nest under input
        input_obj = request_json.get("input")
        if isinstance(input_obj, dict) and isinstance(input_obj.get("messages"), list):
            return input_obj.get("messages")

    return None


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

    Backwards compatibility:
        - New: `model_proxy_requests`
        - Legacy: `llm_usage_events` (used by older deployments and unit test fakes)
    """
    _validate_app_id(app_id)
    _validate_task(task)
    _validate_provider(provider)
    _validate_model(model)
    _validate_route(route)

    client = _get_client_or_503()
    source_table = _pick_first_available_object(client, ["model_proxy_requests", "llm_usage_events"])

    since_dt = _utc_now() - timedelta(hours=int(since_hours))
    since_iso = _iso(since_dt)

    try:
        if source_table == "model_proxy_requests":
            query = client.table("model_proxy_requests").select(
                ",".join(
                    [
                        "id",
                        "request_id",
                        "app_id",
                        "task",
                        "user_id",
                        "project_id",
                        "provider_name",
                        "model",
                        "input_tokens",
                        "output_tokens",
                        "total_tokens",
                        "estimated_cost",
                        "prompt_sha256",
                        "prompt_char_count",
                        "message_count",
                        "route",
                        "status_code",
                        "latency_ms",
                        "stream",
                        "request_timestamp",
                    ]
                )
            )

            if app_id is not None:
                query = query.eq("app_id", app_id)
            if task is not None:
                query = query.eq("task", task)
            if provider is not None:
                query = query.eq("provider_name", provider)
            if model is not None:
                query = query.eq("model", model)
            if route is not None:
                query = query.eq("route", route)

            query = (
                query.gte("request_timestamp", since_iso)
                .order("request_timestamp", desc=True)
                .limit(limit)
            )
            resp = query.execute()
        else:
            # Legacy shape used by tests.
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
        raise HTTPException(status_code=503, detail="Supabase is unreachable (LLM usage).") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to query LLM usage events: {exc}") from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail=f"Unexpected response from Supabase ({source_table})")

    events: list[dict[str, Any]] = []
    for r in data:
        if not isinstance(r, dict):
            continue

        if source_table == "model_proxy_requests":
            events.append(
                {
                    "id": r.get("id"),
                    "request_id": r.get("request_id"),
                    "app_id": r.get("app_id"),
                    "task": r.get("task"),
                    "user_id": r.get("user_id"),
                    "agent_id": None,  # legacy field; not tracked in model_proxy_requests
                    "project_id": r.get("project_id"),
                    "provider": r.get("provider_name"),
                    "model": r.get("model"),
                    "input_tokens": r.get("input_tokens") or 0,
                    "output_tokens": r.get("output_tokens") or 0,
                    "total_tokens": r.get("total_tokens") or 0,
                    "estimated_cost": r.get("estimated_cost"),
                    "prompt_sha256": r.get("prompt_sha256"),
                    "prompt_chars": r.get("prompt_char_count"),
                    "message_count": r.get("message_count"),
                    "route": r.get("route"),
                    "status_code": r.get("status_code"),
                    "latency_ms": r.get("latency_ms"),
                    "stream": bool(r.get("stream")),
                    "created_at": r.get("request_timestamp"),
                }
            )
        else:
            events.append(
                {
                    "id": r.get("id"),
                    "request_id": r.get("request_id"),
                    "app_id": r.get("app_id"),
                    "task": r.get("task"),
                    "user_id": r.get("user_id"),
                    "agent_id": r.get("agent_id"),
                    "project_id": r.get("project_id"),
                    "provider": r.get("provider"),
                    "model": r.get("model"),
                    "input_tokens": r.get("input_tokens") or 0,
                    "output_tokens": r.get("output_tokens") or 0,
                    "total_tokens": r.get("total_tokens") or 0,
                    "estimated_cost": r.get("estimated_cost"),
                    "prompt_sha256": r.get("prompt_sha256"),
                    "prompt_chars": r.get("prompt_chars"),
                    "message_count": r.get("message_count"),
                    "route": r.get("route"),
                    "status_code": r.get("status_code"),
                    "latency_ms": r.get("latency_ms"),
                    "stream": bool(r.get("stream")),
                    "created_at": r.get("created_at"),
                }
            )

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
        "count": len(events),
        "events": events,
        "source": {"type": "supabase", "table": source_table},
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
    """Return daily rollups (new or legacy view).

    Backwards compatibility:
        - New: `model_proxy_daily_stats`
        - Legacy: `llm_usage_daily` (used by older deployments and unit test fakes)
    """
    _validate_app_id(app_id)
    _validate_task(task)
    _validate_provider(provider)
    _validate_model(model)

    # The legacy view supported task. The new one does not. Keep behavior:
    # - if using new view: reject task filter
    # - if using legacy view: allow it
    client = _get_client_or_503()
    source_view = _pick_first_available_object(client, ["model_proxy_daily_stats", "llm_usage_daily"])

    if task is not None and source_view == "model_proxy_daily_stats":
        raise HTTPException(status_code=400, detail="task filter is not supported for daily stats")

    since_day: date = (_utc_now() - timedelta(days=int(days))).date()
    since_day_iso = since_day.isoformat()

    try:
        if source_view == "model_proxy_daily_stats":
            query = client.table("model_proxy_daily_stats").select(
                ",".join(
                    [
                        "stat_date",
                        "app_id",
                        "project_id",
                        "model",
                        "provider_name",
                        "request_count",
                        "total_input_tokens",
                        "total_output_tokens",
                        "total_tokens",
                        "total_estimated_cost",
                    ]
                )
            )

            if app_id is not None:
                query = query.eq("app_id", app_id)
            if provider is not None:
                query = query.eq("provider_name", provider)
            if model is not None:
                query = query.eq("model", model)

            query = query.gte("stat_date", since_day_iso).order("stat_date", desc=True).limit(limit)
            resp = query.execute()
        else:
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

            query = query.gte("day", since_day_iso).order("day", desc=True).limit(limit)
            resp = query.execute()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Supabase is unreachable (LLM usage daily).") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to query daily rollups: {exc}") from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail=f"Unexpected response from Supabase ({source_view})")

    rows: list[dict[str, Any]] = []
    for r in data:
        if not isinstance(r, dict):
            continue

        if source_view == "model_proxy_daily_stats":
            rows.append(
                {
                    "day": r.get("stat_date"),
                    "app_id": r.get("app_id"),
                    "task": None,
                    "provider": r.get("provider_name"),
                    "model": r.get("model"),
                    "requests": r.get("request_count") or 0,
                    "input_tokens": r.get("total_input_tokens") or 0,
                    "output_tokens": r.get("total_output_tokens") or 0,
                    "total_tokens": r.get("total_tokens") or 0,
                    "estimated_cost": r.get("total_estimated_cost"),
                }
            )
        else:
            rows.append(
                {
                    "day": r.get("day"),
                    "app_id": r.get("app_id"),
                    "task": r.get("task"),
                    "provider": r.get("provider"),
                    "model": r.get("model"),
                    "requests": r.get("requests") or 0,
                    "input_tokens": r.get("input_tokens") or 0,
                    "output_tokens": r.get("output_tokens") or 0,
                    "total_tokens": r.get("total_tokens") or 0,
                    "estimated_cost": r.get("estimated_cost"),
                }
            )

    return {
        "app_id": app_id,
        "filters": {"task": task, "provider": provider, "model": model, "days": days, "limit": limit},
        "count": len(rows),
        "rows": rows,
        "source": {"type": "supabase", "view": source_view},
    }


@router.get("/raw-prompts")
async def llm_raw_prompts(
    app_id: str | None = Query(default=None),
    task: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    since_hours: int = Query(default=24, ge=0, le=24 * 365),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    """List raw prompts (privacy-sensitive, stored only when explicitly enabled).

    Backwards compatibility:
        - New: `model_proxy_payloads`
        - Legacy: `llm_raw_prompts` (used by older deployments and unit test fakes)
    """
    _validate_app_id(app_id)
    _validate_task(task)
    _validate_provider(provider)
    _validate_model(model)

    client = _get_client_or_503()
    source_table = _pick_first_available_object(client, ["model_proxy_payloads", "llm_raw_prompts"])

    since_dt = _utc_now() - timedelta(hours=int(since_hours))
    since_iso = _iso(since_dt)

    try:
        if source_table == "model_proxy_payloads":
            query = client.table("model_proxy_payloads").select(
                ",".join(
                    [
                        "request_id",
                        "app_id",
                        "task",
                        "provider",
                        "model",
                        "request_json",
                        "prompt_text",
                        "prompt_sha256",
                        "prompt_chars",
                        "message_count",
                        "metadata",
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

            query = query.gte("created_at", since_iso).order("created_at", desc=True).limit(limit)
            resp = query.execute()
        else:
            query = client.table("llm_raw_prompts").select(
                ",".join(
                    [
                        "request_id",
                        "app_id",
                        "task",
                        "provider",
                        "model",
                        "messages",
                        "prompt_text",
                        "prompt_sha256",
                        "prompt_chars",
                        "message_count",
                        "metadata",
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

            query = query.gte("created_at", since_iso).order("created_at", desc=True).limit(limit)
            resp = query.execute()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Supabase is unreachable (raw prompts).") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to query raw prompts: {exc}") from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail=f"Unexpected response from Supabase ({source_table})")

    prompts: list[dict[str, Any]] = []
    for r in data:
        if not isinstance(r, dict):
            continue

        if source_table == "model_proxy_payloads":
            request_json = r.get("request_json")
            messages = _extract_messages_from_request_json(request_json)
        else:
            messages = r.get("messages")

        prompts.append(
            {
                "request_id": r.get("request_id"),
                "app_id": r.get("app_id"),
                "task": r.get("task"),
                "provider": r.get("provider"),
                "model": r.get("model"),
                "messages": messages,
                "prompt_text": r.get("prompt_text") or "",
                "prompt_sha256": r.get("prompt_sha256"),
                "prompt_chars": r.get("prompt_chars"),
                "message_count": r.get("message_count"),
                "metadata": r.get("metadata") or {},
                "created_at": r.get("created_at"),
            }
        )

    return {
        "app_id": app_id,
        "filters": {
            "task": task,
            "provider": provider,
            "model": model,
            "since_hours": since_hours,
            "limit": limit,
        },
        "count": len(prompts),
        "prompts": prompts,
        "source": {"type": "supabase", "table": source_table},
    }
