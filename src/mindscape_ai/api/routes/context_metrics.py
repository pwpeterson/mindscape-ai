"""Context condensation metrics API routes (Supabase-backed).

Purpose
-------
Expose "context metrics" endpoints for monitoring and tuning how model-proxy condenses
prompts/requests.

The user-provided reference queries live in:
- docs/CONDENSATION_METRICS_QUERIES.sql

Data sources
------------
model-proxy has had multiple schema iterations. In this repo we already query:

- public.model_proxy_requests
  (string app_id, request_timestamp, input_tokens/output_tokens, estimated_cost)

The updated model-proxy schema (as provided by the user) uses:

- public.model_proxy_api_requests
  (integer app_id, timestamp, prompt_tokens/completion_tokens, total_cost_usd)

This router supports BOTH by detecting which table exists at runtime and mapping columns
accordingly.

Design goals
------------
- Server-side only: the browser UI never talks to Supabase directly.
- Fail-soft: if the preferred table isn't present, fall back to the older one.
- Safe query guardrails: limit time windows, validate query params, cap rows fetched.
- Avoid heavy dependencies: percentiles are computed in Python.

Endpoints (v1)
--------------
- GET /api/v1/context-metrics/roi
- GET /api/v1/context-metrics/daily
- GET /api/v1/context-metrics/by-type
- GET /api/v1/context-metrics/top-cost
- GET /api/v1/context-metrics/hourly
- GET /api/v1/context-metrics/errors

Request drill-down (v1)
-----------------------
- GET /api/v1/context-metrics/request/lookup
- GET /api/v1/context-metrics/request/details
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Final, Literal

import httpx
from fastapi import APIRouter, HTTPException, Query

from mindscape_ai.supabase.client import SupabaseUnavailableError, get_supabase_client

router = APIRouter(prefix="/context-metrics", tags=["context-metrics"])

# Hard limits for untrusted query params (DoS guardrails)
APP_ID_QUERY_MAX_LEN: Final[int] = 200
PROVIDER_QUERY_MAX_LEN: Final[int] = 100
MODEL_QUERY_MAX_LEN: Final[int] = 200

# Hard limits for query sizes (avoid downloading unbounded tables)
MAX_ROWS_PER_QUERY: Final[int] = 20_000
MAX_TOP_COST_LIMIT: Final[int] = 200

# Drill-down guardrails
MAX_REQUEST_LOOKUP_LIMIT: Final[int] = 200
MAX_REQUEST_CHILD_ROWS: Final[int] = 2_000

# Time window guardrails
MAX_DAYS: Final[int] = 365
MAX_HOURS: Final[int] = 24 * 365

APP_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_.-]+$")  # Mindscape-style
PROVIDER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_.-]+$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
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


def _get_client_or_503() -> Any:
    try:
        return get_supabase_client()
    except SupabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@dataclass(frozen=True)
class _SourceSpec:
    kind: Literal["api_requests", "requests"]
    table: str

    # common columns (mapped)
    ts_col: str
    model_col: str
    provider_col: str

    # optional metrics columns (vary by schema iteration)
    prompt_tokens_col: str | None
    completion_tokens_col: str | None
    total_cost_col: str | None
    duration_ms_col: str | None
    status_code_col: str | None
    message_count_col: str | None
    metadata_col: str | None

    # optional filters
    app_id_col: str | None
    project_id_col: str | None

    # optional identity columns (not guaranteed across schema iterations)
    request_id_col: str | None = None


def _is_fastapi_style_not_found(exc: Exception) -> bool:
    """Detect when SUPABASE_URL is pointing at a non-Supabase service.

    Symptom we see in this project:
    - supabase-py raises an error like "JSON could not be generated" with embedded
      response bytes `b'{"detail":"Not Found"}'`.

    That `{"detail":"Not Found"}` shape is typical of FastAPI/Starlette 404s, not
    PostgREST errors. It usually means SUPABASE_URL is wrong (wrong host/port).
    """
    s = str(exc)
    # Be permissive; error strings differ across supabase-py versions.
    if "JSON could not be generated" not in s:
        return False
    return '"detail":"Not Found"' in s or "{'detail': 'Not Found'}" in s


def _supabase_url_hint() -> str:
    url = (
        os.getenv("SUPABASE_URL")
        or os.getenv("SUPABASE_PUBLIC_URL")
        or os.getenv("API_EXTERNAL_URL")
        or os.getenv("MINDSCAPE_SUPABASE_URL")
        or ""
    )
    return (
        "SUPABASE_URL appears to point at a non-Supabase service (FastAPI-style 404). "
        "Context Metrics requires Supabase Kong/PostgREST (base URL, e.g. http://127.0.0.1:8100 "
        "in your setup; sometimes :8000 in others), not model-proxy (often http://127.0.0.1:8002). "
        f"Configured SUPABASE_URL={url!r}"
    )


def _detect_source(client: Any) -> _SourceSpec:
    """Detect which model-proxy schema exists in the connected Supabase.

    Preference order:
    1) model_proxy_api_requests (newer model-proxy schema; column names vary by deployment)
    2) model_proxy_requests (older Mindscape schema)
    """

    def _probe_select(table: str, cols: list[str]) -> bool:
        """Return True if selecting the given columns succeeds."""
        try:
            client.table(table).select(",".join(cols)).limit(1).execute()
            return True
        except Exception as exc:
            if _is_fastapi_style_not_found(exc):
                raise HTTPException(status_code=503, detail=_supabase_url_hint()) from exc
            return False

    # Try new table first (but be defensive about column names).
    try:
        client.table("model_proxy_api_requests").select("id").limit(1).execute()

        # Column candidates observed across model-proxy iterations.
        ts_candidates = ["timestamp", "request_timestamp", "created_at"]
        provider_candidates = ["provider_name", "provider", "provider_id"]
        model_candidates = ["model", "model_name"]
        prompt_tok_candidates = ["prompt_tokens", "input_tokens"]
        completion_tok_candidates = ["completion_tokens", "output_tokens"]
        cost_candidates = ["total_cost_usd", "total_cost", "estimated_cost", "cost_usd"]
        duration_candidates = ["duration_ms", "latency_ms"]
        status_candidates = ["status_code", "http_status", "status"]
        msg_count_candidates = ["message_count", "messages_count"]
        metadata_candidates = ["metadata", "meta"]

        # Optional identity/scope columns
        request_id_candidates = ["request_id", "id"]
        app_id_candidates = ["app_id", "app"]
        project_id_candidates = ["project_id", "project"]

        def _pick_first(table: str, candidates: list[str]) -> str | None:
            for c in candidates:
                if _probe_select(table, [c]):
                    return c
            return None

        table = "model_proxy_api_requests"

        ts_col = _pick_first(table, ts_candidates)
        model_col = _pick_first(table, model_candidates)
        provider_col = _pick_first(table, provider_candidates)
        prompt_tokens_col = _pick_first(table, prompt_tok_candidates)
        completion_tokens_col = _pick_first(table, completion_tok_candidates)
        total_cost_col = _pick_first(table, cost_candidates)
        duration_ms_col = _pick_first(table, duration_candidates)
        status_code_col = _pick_first(table, status_candidates)
        message_count_col = _pick_first(table, msg_count_candidates)
        metadata_col = _pick_first(table, metadata_candidates)

        required = {
            "timestamp": ts_col,
            "model": model_col,
            "provider": provider_col,
            "prompt_tokens": prompt_tokens_col,
            "completion_tokens": completion_tokens_col,
            "total_cost": total_cost_col,
            "duration_ms": duration_ms_col,
            "status_code": status_code_col,
            "message_count": message_count_col,
            "metadata": metadata_col,
        }
        missing = [k for k, v in required.items() if v is None]
        if missing:
            raise HTTPException(
                status_code=500,
                detail=(
                    "model_proxy_api_requests exists but required columns could not be detected: "
                    f"{missing}. Please update context-metrics column mapping."
                ),
            )

        request_id_col = _pick_first(table, request_id_candidates)
        app_id_col = _pick_first(table, app_id_candidates)
        project_id_col = _pick_first(table, project_id_candidates)

        return _SourceSpec(
            kind="api_requests",
            table=table,
            ts_col=ts_col or "timestamp",
            model_col=model_col or "model",
            provider_col=provider_col or "provider_name",
            prompt_tokens_col=prompt_tokens_col or "prompt_tokens",
            completion_tokens_col=completion_tokens_col or "completion_tokens",
            total_cost_col=total_cost_col or "total_cost_usd",
            duration_ms_col=duration_ms_col or "duration_ms",
            status_code_col=status_code_col or "status_code",
            message_count_col=message_count_col or "message_count",
            metadata_col=metadata_col or "metadata",
            app_id_col=app_id_col,
            project_id_col=project_id_col,
            request_id_col=request_id_col,
        )
    except HTTPException:
        raise
    except Exception as exc:
        if _is_fastapi_style_not_found(exc):
            raise HTTPException(status_code=503, detail=_supabase_url_hint()) from exc
        pass

    # Fall back to table used by existing Mindscape endpoints (but detect column names).
    table = "model_proxy_requests"
    try:
        client.table(table).select("id").limit(1).execute()
    except Exception as exc:  # noqa: BLE001
        if _is_fastapi_style_not_found(exc):
            raise HTTPException(status_code=503, detail=_supabase_url_hint()) from exc
        raise HTTPException(
            status_code=503,
            detail=(
                "Supabase is reachable, but neither model_proxy_api_requests nor "
                f"model_proxy_requests could be queried: {exc}"
            ),
        ) from exc

    # Column candidates observed across model-proxy iterations (minimal vs older Mindscape).
    ts_candidates = ["request_timestamp", "timestamp", "created_at"]
    provider_candidates = ["provider_name", "provider"]
    model_candidates = ["model", "model_name"]
    prompt_tok_candidates = ["request_token_count", "input_tokens", "prompt_tokens"]
    completion_tok_candidates = ["response_token_count", "output_tokens", "completion_tokens"]
    cost_candidates = ["estimated_cost", "total_cost_usd", "total_cost", "cost_usd"]
    duration_candidates = ["latency_ms", "duration_ms"]
    status_candidates = ["status_code", "http_status", "status"]
    msg_count_candidates = ["message_count", "messages_count"]
    metadata_candidates = ["metadata", "meta"]

    request_id_candidates = ["request_id", "id"]
    app_id_candidates = ["app_id", "app"]
    project_id_candidates = ["project_id", "project"]

    def _pick_first(table: str, candidates: list[str]) -> str | None:
        for c in candidates:
            if _probe_select(table, [c]):
                return c
        return None

    ts_col = _pick_first(table, ts_candidates) or "request_timestamp"
    provider_col = _pick_first(table, provider_candidates) or "provider"
    model_col = _pick_first(table, model_candidates) or "model"

    prompt_tokens_col = _pick_first(table, prompt_tok_candidates)
    completion_tokens_col = _pick_first(table, completion_tok_candidates)
    total_cost_col = _pick_first(table, cost_candidates)
    duration_ms_col = _pick_first(table, duration_candidates)
    status_code_col = _pick_first(table, status_candidates)
    message_count_col = _pick_first(table, msg_count_candidates)
    metadata_col = _pick_first(table, metadata_candidates)

    request_id_col = _pick_first(table, request_id_candidates)
    app_id_col = _pick_first(table, app_id_candidates)
    project_id_col = _pick_first(table, project_id_candidates)

    return _SourceSpec(
        kind="requests",
        table=table,
        ts_col=ts_col,
        model_col=model_col,
        provider_col=provider_col,
        prompt_tokens_col=prompt_tokens_col,
        completion_tokens_col=completion_tokens_col,
        total_cost_col=total_cost_col,  # may be None in minimal schema
        duration_ms_col=duration_ms_col,
        status_code_col=status_code_col,
        message_count_col=message_count_col,
        metadata_col=metadata_col,
        app_id_col=app_id_col,
        project_id_col=project_id_col,
        request_id_col=request_id_col,
    )


def _percentile_sorted(values_sorted: list[int], p: float) -> int | None:
    """Nearest-rank percentile.

    - p is in [0, 1]
    - returns an int (tokens are ints), or None if values is empty
    """
    if not values_sorted:
        return None
    if p <= 0:
        return values_sorted[0]
    if p >= 1:
        return values_sorted[-1]
    # nearest-rank: ceil(p * n) - 1
    n = len(values_sorted)

    # Use ceil by computing rank and subtracting 1
    import math

    rank = max(1, int(math.ceil(p * n)))
    idx = min(n - 1, rank - 1)
    return values_sorted[idx]


def _safe_int(v: Any) -> int:
    try:
        if v is None:
            return 0
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str) and v.strip():
            return int(float(v))
    except Exception:
        return 0
    return 0


def _safe_float(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        if isinstance(v, bool):
            return float(int(v))
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str) and v.strip():
            return float(v)
    except Exception:
        return 0.0
    return 0.0


def _meta_bool(meta: Any, key: str) -> bool:
    if not isinstance(meta, dict):
        return False
    v = meta.get(key)
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _meta_int(meta: Any, key: str) -> int | None:
    if not isinstance(meta, dict):
        return None
    v = meta.get(key)
    if v is None:
        return None
    try:
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str) and v.strip():
            return int(float(v))
    except Exception:
        return None
    return None


def _apply_scope_filters(
    *,
    client: Any,
    query: Any,
    src: _SourceSpec,
    app_id: str | None,
    project_id: str | None,
    provider: str | None,
    model: str | None,
) -> Any:
    """Apply common filters.

    app_id handling:
    - If app_id is digits-only, filter as int (works for integer columns; Postgres will also
      coerce for text columns in many cases).
    - Otherwise, filter as string.
    """
    if provider is not None:
        query = query.eq(src.provider_col, provider)
    if model is not None:
        query = query.eq(src.model_col, model)

    if project_id is not None and src.project_id_col is not None:
        query = query.eq(src.project_id_col, project_id)

    if app_id is not None and src.app_id_col is not None:
        if app_id.isdigit():
            query = query.eq(src.app_id_col, int(app_id))
        else:
            query = query.eq(src.app_id_col, app_id)

    return query


def _fetch_rows(
    *,
    client: Any,
    src: _SourceSpec,
    since_dt: datetime,
    app_id: str | None,
    project_id: str | None,
    provider: str | None,
    model: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    # Keep selects minimal; we do aggregation in Python.
    cols: list[str] = [src.ts_col, src.model_col, src.provider_col]

    for c in (
        src.prompt_tokens_col,
        src.completion_tokens_col,
        src.total_cost_col,
        src.duration_ms_col,
        src.status_code_col,
        src.message_count_col,
        src.metadata_col,
    ):
        if c is not None:
            cols.append(c)

    # Identity columns are not guaranteed across schema iterations; only select if detected.
    if src.request_id_col:
        cols.append(src.request_id_col)
    if src.project_id_col:
        cols.append(src.project_id_col)
    if src.app_id_col:
        cols.append(src.app_id_col)

    select_cols = ",".join(dict.fromkeys(cols))  # preserve order, de-dupe

    since_iso = _iso(since_dt)

    try:
        query = client.table(src.table).select(select_cols)
        query = _apply_scope_filters(
            client=client,
            query=query,
            src=src,
            app_id=app_id,
            project_id=project_id,
            provider=provider,
            model=model,
        )
        query = query.gte(src.ts_col, since_iso).order(src.ts_col, desc=True).limit(limit)

        resp = query.execute()
    except HTTPException:
        # Preserve intended status codes (e.g., 400 for invalid scope/mapping).
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail="Supabase is unreachable (context metrics).",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "invalid input syntax for type integer" in msg or "22P02" in msg:
            raise HTTPException(
                status_code=400,
                detail="app_id must be numeric for this model-proxy schema.",
            ) from exc
        raise HTTPException(status_code=500, detail=f"Failed to query {src.table}: {exc}") from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list):
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected response from Supabase ({src.table})",
        )

    return [r for r in data if isinstance(r, dict)]


def _date_key(dt: datetime) -> str:
    return dt.date().isoformat()


def _parse_ts(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v.strip():
        return None
    # ISO8601/RFC3339. Use fromisoformat with minor normalization.
    s = v.strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


@router.get("/roi")
async def condensation_roi(
    app_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    since_days: int = Query(default=7, ge=1, le=MAX_DAYS),
    max_rows: int = Query(default=10_000, ge=100, le=MAX_ROWS_PER_QUERY),
) -> dict[str, Any]:
    """Condensation ROI summary.

    This endpoint must tolerate multiple model-proxy schema iterations.

    Data sources (best-effort):
    - Requests: auto-detected via [`_detect_source()`](src/mindscape_ai/api/routes/context_metrics.py:152)
      - public.model_proxy_api_requests (newer)
      - public.model_proxy_requests (older)
    - Condensation details: if `model_proxy_request_contexts` is present, join on request_id.
      Otherwise, attempt to read condensation hints from the request metadata JSON.

    Notes:
    - `estimated_savings_usd` is a heuristic based on saved tokens.
    """
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        _validate_len("project_id", project_id, 255)

    client = _get_client_or_503()
    src = _detect_source(client)

    since_dt = _utc_now() - timedelta(days=int(since_days))

    # ---- Step 1: fetch recent requests in scope (cap by max_rows) ----
    request_rows = _fetch_rows(
        client=client,
        src=src,
        since_dt=since_dt,
        app_id=app_id,
        project_id=project_id,
        provider=provider,
        model=model,
        limit=int(max_rows),
    )

    total_requests = len(request_rows)

    # Collect request_ids for optional join to contexts table (if possible).
    request_ids: list[str] = []
    if src.request_id_col is not None:
        for r in request_rows:
            rid = r.get(src.request_id_col)
            if rid is None:
                continue
            s = str(rid).strip()
            if s:
                request_ids.append(s)

    # Dedupe while preserving order.
    request_ids = list(dict.fromkeys(request_ids))

    # Cost is available only if a cost column exists.
    total_cost_usd = None
    if src.total_cost_col is not None:
        try:
            total_cost_usd = sum(_safe_float(r.get(src.total_cost_col)) for r in request_rows)
        except Exception:
            total_cost_usd = None

    # ---- Step 2: fetch contexts for those request_ids (if contexts table exists) ----
    def _chunks(items: list[str], size: int) -> list[list[str]]:
        return [items[i : i + size] for i in range(0, len(items), size)]

    context_table = _pick_first_available_object(client, ["model_proxy_request_contexts"])
    context_rows: list[dict[str, Any]] = []

    if context_table is not None and request_ids:
        for chunk in _chunks(request_ids, 200):
            try:
                ctx_resp = (
                    client.table(context_table)
                    .select(
                        ",".join(
                            [
                                "request_id",
                                "raw_context_token_count",
                                "condensed_context_token_count",
                                "tokens_saved",
                            ]
                        )
                    )
                    .in_("request_id", chunk)
                    .execute()
                )
            except Exception:
                continue

            ctx_data = getattr(ctx_resp, "data", None)
            if isinstance(ctx_data, list):
                for r in ctx_data:
                    if isinstance(r, dict):
                        context_rows.append(r)

    # Compute ROI metrics from either contexts table or request metadata.
    condensed_requests = 0

    raw_tok_sum = 0
    raw_tok_n = 0

    condensed_tok_sum = 0
    condensed_tok_n = 0

    tokens_saved_sum = 0
    tokens_saved_n = 0

    condensation_source: str | None = None

    if context_rows:
        condensation_source = "model_proxy_request_contexts"
        for r in context_rows:
            raw_tok = _meta_int(r, "raw_context_token_count")
            condensed_tok = _meta_int(r, "condensed_context_token_count")
            saved = _meta_int(r, "tokens_saved")

            if raw_tok is not None or condensed_tok is not None or saved is not None:
                condensed_requests += 1

            if raw_tok is not None:
                raw_tok_sum += raw_tok
                raw_tok_n += 1
            if condensed_tok is not None:
                condensed_tok_sum += condensed_tok
                condensed_tok_n += 1
            if saved is not None:
                tokens_saved_sum += saved
                tokens_saved_n += 1
    else:
        # Fall back to request metadata hints (schema-dependent; best-effort).
        condensation_source = "request_metadata"
        for r in request_rows:
            meta = r.get(src.metadata_col) if src.metadata_col is not None else None
            raw_tok = _meta_int(meta, "raw_context_token_count")
            condensed_tok = _meta_int(meta, "condensed_context_token_count")
            saved = _meta_int(meta, "tokens_saved")

            condensed_flag = _meta_bool(meta, "context_condensed")
            if raw_tok is not None or condensed_tok is not None or saved is not None:
                condensed_flag = True

            if condensed_flag:
                condensed_requests += 1

            if raw_tok is not None:
                raw_tok_sum += raw_tok
                raw_tok_n += 1
            if condensed_tok is not None:
                condensed_tok_sum += condensed_tok
                condensed_tok_n += 1
            if saved is not None:
                tokens_saved_sum += saved
                tokens_saved_n += 1

    avg_raw = (raw_tok_sum / raw_tok_n) if raw_tok_n else None
    avg_condensed = (condensed_tok_sum / condensed_tok_n) if condensed_tok_n else None
    avg_saved = (tokens_saved_sum / tokens_saved_n) if tokens_saved_n else None

    condensation_rate_pct = (
        (condensed_requests / total_requests * 100.0) if total_requests else None
    )

    token_reduction_pct = None
    if avg_raw is not None and avg_raw not in (None, 0) and avg_condensed is not None:
        token_reduction_pct = ((avg_raw - avg_condensed) / avg_raw) * 100.0

    estimated_savings_usd = None
    if avg_saved is not None:
        estimated_savings_usd = float(avg_saved) * condensed_requests * 0.000005

    return {
        "filters": {
            "app_id": app_id,
            "project_id": project_id,
            "provider": provider,
            "model": model,
            "since_days": since_days,
            "max_rows": max_rows,
        },
        "source": {
            "type": "supabase",
            "requests_table": src.table,
            "contexts_table": context_table,
        },
        "stats": {
            "total_requests": total_requests,
            "condensed_requests": condensed_requests,
            "condensation_rate_pct": None
            if condensation_rate_pct is None
            else round(condensation_rate_pct, 1),
            "avg_tokens_condensed": None if avg_condensed is None else round(avg_condensed, 0),
            "avg_tokens_not_condensed": None if avg_raw is None else round(avg_raw, 0),
            "avg_tokens_saved_per_request": None if avg_saved is None else round(avg_saved, 0),
            "token_reduction_pct": None
            if token_reduction_pct is None
            else round(token_reduction_pct, 1),
            "total_cost_usd": None if total_cost_usd is None else round(total_cost_usd, 6),
            "estimated_savings_usd": None
            if estimated_savings_usd is None
            else round(estimated_savings_usd, 4),
        },
        "notes": {
            "schema_kind": src.kind,
            "condensation_source": condensation_source,
            "cost_available": total_cost_usd is not None,
        },
    }


@router.get("/daily")
async def daily_token_trends(
    app_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=MAX_DAYS),
    max_rows: int = Query(default=20_000, ge=100, le=MAX_ROWS_PER_QUERY),
) -> dict[str, Any]:
    """Daily request token trends (minimal schema).

    Minimal schema has:
    - model_proxy_requests.request_token_count (treated as "prompt" tokens)
    - model_proxy_requests.response_token_count (treated as "completion" tokens)

    Cost is not available in the minimal schema, so avg_cost_usd/total_cost_usd are null.
    """
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        _validate_len("project_id", project_id, 255)

    client = _get_client_or_503()

    since_dt = _utc_now() - timedelta(days=int(days))
    since_iso = _iso(since_dt)

    try:
        q = (
            client.table("model_proxy_requests")
            .select(
                ",".join(
                    [
                        "request_timestamp",
                        "model",
                        "provider",
                        "app_id",
                        "request_token_count",
                        "response_token_count",
                    ]
                )
            )
            .gte("request_timestamp", since_iso)
            .order("request_timestamp", desc=True)
            .limit(int(max_rows))
        )

        if app_id is not None:
            q = q.eq("app_id", app_id)
        if provider is not None:
            q = q.eq("provider", provider)
        if model is not None:
            q = q.eq("model", model)

        resp = q.execute()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503, detail="Supabase is unreachable (daily context metrics)."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Failed to query model_proxy_requests (daily): {exc}"
        ) from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list):
        raise HTTPException(
            status_code=500, detail="Unexpected response from Supabase (model_proxy_requests)"
        )

    rows: list[dict[str, Any]] = [r for r in data if isinstance(r, dict)]

    # group by (date, model)
    groups: dict[tuple[str, str], dict[str, Any]] = {}

    for r in rows:
        ts = _parse_ts(r.get("request_timestamp"))
        if ts is None:
            continue
        date = _date_key(ts)
        m = str(r.get("model") or "unknown")

        key = (date, m)
        g = groups.get(key)
        if g is None:
            g = {
                "date": date,
                "model": m,
                "request_count": 0,
                "prompt_tokens": [],
                "completion_tokens_sum": 0,
                "completion_tokens_n": 0,
            }
            groups[key] = g

        g["request_count"] += 1
        pt = _safe_int(r.get("request_token_count"))
        g["prompt_tokens"].append(pt)

        ct = _safe_int(r.get("response_token_count"))
        g["completion_tokens_sum"] += ct
        g["completion_tokens_n"] += 1

    out: list[dict[str, Any]] = []
    for (_date, _model), g in groups.items():
        pts = sorted(g["prompt_tokens"])
        avg_prompt = (sum(pts) / len(pts)) if pts else None

        median = _percentile_sorted(pts, 0.50)
        p95 = _percentile_sorted(pts, 0.95)
        mx = pts[-1] if pts else None

        avg_completion = (
            (g["completion_tokens_sum"] / g["completion_tokens_n"])
            if g["completion_tokens_n"]
            else None
        )

        out.append(
            {
                "date": g["date"],
                "model": g["model"],
                "request_count": g["request_count"],
                "avg_prompt_tokens": None if avg_prompt is None else round(avg_prompt, 0),
                "median_prompt_tokens": median,
                "p95_prompt_tokens": p95,
                "max_prompt_tokens": mx,
                "avg_completion_tokens": None
                if avg_completion is None
                else round(avg_completion, 0),
                "avg_cost_usd": None,
                "total_cost_usd": None,
            }
        )

    out.sort(key=lambda r: (r["date"], r["model"]), reverse=True)

    return {
        "filters": {
            "app_id": app_id,
            "project_id": project_id,
            "provider": provider,
            "model": model,
            "days": days,
        },
        "source": {"type": "supabase", "table": "model_proxy_requests"},
        "count": len(out),
        "rows": out,
        "notes": {
            "percentiles": "nearest-rank in Python",
            "max_rows": max_rows,
            "cost_available": False,
        },
    }


@router.get("/by-type")
async def condensation_effectiveness_by_type(
    app_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=MAX_DAYS),
    max_rows: int = Query(default=20_000, ge=100, le=MAX_ROWS_PER_QUERY),
) -> dict[str, Any]:
    """Condensation effectiveness breakdown (minimal schema).

    The prior "by-type" endpoint relied on metadata keys (rules injected, code-jit injected)
    that no longer exist in the minimal schema.

    For now this endpoint returns an empty set to preserve API stability for the UI.
    """
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        _validate_len("project_id", project_id, 255)

    return {
        "filters": {
            "app_id": app_id,
            "project_id": project_id,
            "provider": provider,
            "model": model,
            "days": days,
        },
        "source": {"type": "supabase", "table": "model_proxy_request_contexts"},
        "count": 0,
        "rows": [],
        "notes": {
            "max_rows": max_rows,
            "supported": False,
            "reason": "Minimal schema does not include rules/code-jit metadata.",
        },
    }


@router.get("/top-cost")
async def top_cost_requests(
    app_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    since_days: int = Query(default=7, ge=1, le=MAX_DAYS),
    limit: int = Query(default=50, ge=1, le=MAX_TOP_COST_LIMIT),
) -> dict[str, Any]:
    """Top requests by tokens_saved (minimal schema).

    The minimal schema does not include cost, so this endpoint is repurposed to rank by
    `model_proxy_request_contexts.tokens_saved` to help identify best condensation wins.
    """
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        _validate_len("project_id", project_id, 255)

    client = _get_client_or_503()

    since_dt = _utc_now() - timedelta(days=int(since_days))
    since_iso = _iso(since_dt)

    # 1) Get top contexts by tokens_saved within window.
    try:
        ctx_q = (
            client.table("model_proxy_request_contexts")
            .select(
                ",".join(
                    [
                        "request_id",
                        "raw_context_token_count",
                        "condensed_context_token_count",
                        "tokens_saved",
                        "created_at",
                    ]
                )
            )
            .gte("created_at", since_iso)
            .order("tokens_saved", desc=True)
            .limit(int(limit) * 5)
        )
        ctx_resp = ctx_q.execute()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503, detail="Supabase is unreachable (top requests)."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Failed to query model_proxy_request_contexts (top): {exc}"
        ) from exc

    ctx_data = getattr(ctx_resp, "data", None)
    if not isinstance(ctx_data, list):
        raise HTTPException(
            status_code=500,
            detail="Unexpected response from Supabase (model_proxy_request_contexts)",
        )

    ctx_rows: list[dict[str, Any]] = [r for r in ctx_data if isinstance(r, dict)]
    ctx_request_ids = [
        str(r.get("request_id")).strip()
        for r in ctx_rows
        if isinstance(r.get("request_id"), str) and str(r.get("request_id")).strip()
    ]
    ctx_request_ids = list(dict.fromkeys(ctx_request_ids))
    if not ctx_request_ids:
        return {
            "filters": {
                "app_id": app_id,
                "project_id": project_id,
                "provider": provider,
                "model": model,
                "since_days": since_days,
            },
            "source": {"type": "supabase", "table": "model_proxy_request_contexts"},
            "count": 0,
            "rows": [],
            "notes": {"cost_available": False, "ranking": "tokens_saved"},
        }

    # 2) Join with request headers (apply scope filters here).
    def _chunks(items: list[str], size: int) -> list[list[str]]:
        out: list[list[str]] = []
        for i in range(0, len(items), size):
            out.append(items[i : i + size])
        return out

    req_by_id: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(ctx_request_ids, 200):
        try:
            req_q = (
                client.table("model_proxy_requests")
                .select(
                    ",".join(
                        [
                            "request_id",
                            "request_timestamp",
                            "provider",
                            "model",
                            "request_token_count",
                            "response_token_count",
                            "latency_ms",
                            "status_code",
                            "app_id",
                        ]
                    )
                )
                .in_("request_id", chunk)
                .gte("request_timestamp", since_iso)
            )

            if app_id is not None:
                req_q = req_q.eq("app_id", app_id)
            if provider is not None:
                req_q = req_q.eq("provider", provider)
            if model is not None:
                req_q = req_q.eq("model", model)

            req_resp = req_q.execute()
        except Exception:
            continue

        req_data = getattr(req_resp, "data", None)
        if not isinstance(req_data, list):
            continue

        for r in req_data:
            if not isinstance(r, dict):
                continue
            rid = r.get("request_id")
            if isinstance(rid, str) and rid.strip():
                req_by_id[rid.strip()] = r

    out: list[dict[str, Any]] = []
    for c in ctx_rows:
        rid = c.get("request_id")
        if not isinstance(rid, str) or not rid.strip():
            continue
        rid = rid.strip()
        req = req_by_id.get(rid)
        if req is None:
            continue

        prompt_tokens = _safe_int(req.get("request_token_count"))
        completion_tokens = _safe_int(req.get("response_token_count"))

        out.append(
            {
                "request_id": rid,
                "timestamp": req.get("request_timestamp"),
                "provider": req.get("provider"),
                "model": req.get("model"),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_cost_usd": None,
                "duration_ms": _safe_int(req.get("latency_ms")),
                "status_code": req.get("status_code"),
                "message_count": None,
                "prompt_char_count": None,
                "app_id": req.get("app_id"),
                "project_id": None,
                "rules_injected": False,
                "context_condensed": True,
                "tokens_saved": _safe_int(c.get("tokens_saved"))
                if c.get("tokens_saved") is not None
                else None,
                "raw_context_token_count": _safe_int(c.get("raw_context_token_count"))
                if c.get("raw_context_token_count") is not None
                else None,
                "condensed_context_token_count": _safe_int(c.get("condensed_context_token_count"))
                if c.get("condensed_context_token_count") is not None
                else None,
            }
        )

    out.sort(
        key=lambda r: (_safe_int(r.get("tokens_saved")), str(r.get("timestamp") or "")),
        reverse=True,
    )
    out = out[: int(limit)]

    return {
        "filters": {
            "app_id": app_id,
            "project_id": project_id,
            "provider": provider,
            "model": model,
            "since_days": since_days,
        },
        "source": {
            "type": "supabase",
            "table": "model_proxy_requests+model_proxy_request_contexts",
        },
        "count": len(out),
        "rows": out,
        "notes": {"cost_available": False, "ranking": "tokens_saved"},
    }


@router.get("/hourly")
async def hourly_usage(
    app_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    since_hours: int = Query(default=24 * 7, ge=1, le=MAX_HOURS),
    max_rows: int = Query(default=20_000, ge=100, le=MAX_ROWS_PER_QUERY),
) -> dict[str, Any]:
    """Hourly usage patterns (minimal schema).

    - avg_prompt_tokens is derived from model_proxy_requests.request_token_count
    - total_cost_usd is null (not in minimal schema)
    """
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        _validate_len("project_id", project_id, 255)

    client = _get_client_or_503()

    since_dt = _utc_now() - timedelta(hours=int(since_hours))
    since_iso = _iso(since_dt)

    try:
        q = (
            client.table("model_proxy_requests")
            .select(
                ",".join(
                    [
                        "request_timestamp",
                        "model",
                        "provider",
                        "app_id",
                        "request_token_count",
                        "latency_ms",
                    ]
                )
            )
            .gte("request_timestamp", since_iso)
            .order("request_timestamp", desc=True)
            .limit(int(max_rows))
        )

        if app_id is not None:
            q = q.eq("app_id", app_id)
        if provider is not None:
            q = q.eq("provider", provider)
        if model is not None:
            q = q.eq("model", model)

        resp = q.execute()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503, detail="Supabase is unreachable (hourly context metrics)."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Failed to query model_proxy_requests (hourly): {exc}"
        ) from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list):
        raise HTTPException(
            status_code=500, detail="Unexpected response from Supabase (model_proxy_requests)"
        )

    rows: list[dict[str, Any]] = [r for r in data if isinstance(r, dict)]

    groups: dict[tuple[str, str], dict[str, Any]] = {}

    for r in rows:
        ts = _parse_ts(r.get("request_timestamp"))
        if ts is None:
            continue
        hour = ts.replace(minute=0, second=0, microsecond=0).isoformat()
        m = str(r.get("model") or "unknown")
        key = (hour, m)

        g = groups.get(key)
        if g is None:
            g = {
                "hour": hour,
                "model": m,
                "request_count": 0,
                "prompt_tokens_sum": 0,
                "prompt_tokens_n": 0,
                "latency_sum": 0,
                "latency_n": 0,
            }
            groups[key] = g

        g["request_count"] += 1
        g["prompt_tokens_sum"] += _safe_int(r.get("request_token_count"))
        g["prompt_tokens_n"] += 1

        lat = r.get("latency_ms")
        if isinstance(lat, (int, float)) and lat is not None:
            g["latency_sum"] += int(lat)
            g["latency_n"] += 1

    out: list[dict[str, Any]] = []
    for (_hour, _model), g in groups.items():
        out.append(
            {
                "hour": g["hour"],
                "model": g["model"],
                "request_count": g["request_count"],
                "avg_prompt_tokens": None
                if not g["prompt_tokens_n"]
                else round(g["prompt_tokens_sum"] / g["prompt_tokens_n"], 0),
                "total_cost_usd": None,
                "avg_latency_ms": None
                if not g["latency_n"]
                else round(g["latency_sum"] / g["latency_n"], 0),
            }
        )

    out.sort(key=lambda r: (r["hour"], r["model"]), reverse=True)

    return {
        "filters": {
            "app_id": app_id,
            "project_id": project_id,
            "provider": provider,
            "model": model,
            "since_hours": since_hours,
        },
        "source": {"type": "supabase", "table": "model_proxy_requests"},
        "count": len(out),
        "rows": out,
        "notes": {"max_rows": max_rows, "cost_available": False},
    }


@router.get("/errors")
async def error_rate(
    app_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=MAX_DAYS),
    max_rows: int = Query(default=20_000, ge=100, le=MAX_ROWS_PER_QUERY),
) -> dict[str, Any]:
    """Error rate monitoring (minimal schema)."""
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        _validate_len("project_id", project_id, 255)

    client = _get_client_or_503()

    since_dt = _utc_now() - timedelta(days=int(days))
    since_iso = _iso(since_dt)

    try:
        q = (
            client.table("model_proxy_requests")
            .select("request_timestamp,model,provider,app_id,status_code,latency_ms")
            .gte("request_timestamp", since_iso)
            .order("request_timestamp", desc=True)
            .limit(int(max_rows))
        )

        if app_id is not None:
            q = q.eq("app_id", app_id)
        if provider is not None:
            q = q.eq("provider", provider)
        if model is not None:
            q = q.eq("model", model)

        resp = q.execute()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503, detail="Supabase is unreachable (error-rate context metrics)."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Failed to query model_proxy_requests (errors): {exc}"
        ) from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list):
        raise HTTPException(
            status_code=500, detail="Unexpected response from Supabase (model_proxy_requests)"
        )

    rows: list[dict[str, Any]] = [r for r in data if isinstance(r, dict)]

    groups: dict[str, dict[str, Any]] = {}

    for r in rows:
        ts = _parse_ts(r.get("request_timestamp"))
        if ts is None:
            continue
        d = _date_key(ts)
        g = groups.get(d)
        if g is None:
            g = {
                "date": d,
                "total_requests": 0,
                "error_count": 0,
                "bad_request_errors": 0,
                "rate_limit_errors": 0,
                "server_errors": 0,
                "latency_sum": 0,
                "latency_n": 0,
            }
            groups[d] = g

        g["total_requests"] += 1

        status = r.get("status_code")
        status_i = int(status) if isinstance(status, (int, float)) else None
        if status_i is not None and status_i >= 400:
            g["error_count"] += 1
            if status_i == 400:
                g["bad_request_errors"] += 1
            if status_i == 429:
                g["rate_limit_errors"] += 1
            if status_i >= 500:
                g["server_errors"] += 1

        lat = r.get("latency_ms")
        if isinstance(lat, (int, float)) and lat is not None:
            g["latency_sum"] += int(lat)
            g["latency_n"] += 1

    out: list[dict[str, Any]] = []
    for d, g in groups.items():
        total = g["total_requests"]
        err = g["error_count"]
        rate = (err / total * 100.0) if total else None
        out.append(
            {
                "date": d,
                "total_requests": total,
                "error_count": err,
                "error_rate_pct": None if rate is None else round(rate, 2),
                "bad_request_errors": g["bad_request_errors"],
                "rate_limit_errors": g["rate_limit_errors"],
                "server_errors": g["server_errors"],
                "avg_latency_ms": None
                if not g["latency_n"]
                else round(g["latency_sum"] / g["latency_n"], 0),
            }
        )

    out.sort(key=lambda r: r["date"], reverse=True)

    return {
        "filters": {
            "app_id": app_id,
            "project_id": project_id,
            "provider": provider,
            "model": model,
            "days": days,
        },
        "source": {"type": "supabase", "table": "model_proxy_requests"},
        "count": len(out),
        "rows": out,
        "notes": {"max_rows": max_rows},
    }


def _validate_request_id(request_id: str | None) -> str:
    if request_id is None:
        raise HTTPException(status_code=400, detail="request_id is required")
    rid = request_id.strip()
    if not rid:
        raise HTTPException(status_code=400, detail="request_id is required")
    if len(rid) > 200:
        raise HTTPException(status_code=400, detail="request_id too long")
    # Support both UUIDs and opaque req_* ids; keep it permissive but safe.
    if re.fullmatch(r"[A-Za-z0-9_.:-]+", rid) is None:
        raise HTTPException(status_code=400, detail="Invalid characters in request_id")
    return rid


def _pick_first_available_object(client: Any, candidates: list[str]) -> str | None:
    for name in candidates:
        try:
            client.table(name).select("id").limit(1).execute()
            return name
        except Exception:
            continue
    return None


def _request_id_to_uuid_or_none(request_id: str) -> str | None:
    rid = request_id.strip()
    if re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", rid
    ):
        return rid.lower()
    return None


@router.get("/request/lookup")
async def request_lookup(
    q: str | None = Query(default=None, description="Search by request_id substring"),
    app_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    since_days: int = Query(default=7, ge=1, le=MAX_DAYS),
    limit: int = Query(default=50, ge=1, le=MAX_REQUEST_LOOKUP_LIMIT),
) -> dict[str, Any]:
    """Lookup recent request contexts for drill-down (minimal schema).

    Returns rows built from:
    - public.model_proxy_request_contexts (token counts + raw/condensed contexts)
    - public.model_proxy_requests (timestamp/provider/model/app_id/status/latency)

    The UI uses this as the table you can click to expand raw vs condensed context.
    """
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        # minimal schema doesn't have project_id; keep param for API stability
        _validate_len("project_id", project_id, 255)
    if q is not None:
        _validate_len("q", q, 200)

    client = _get_client_or_503()

    since_dt = _utc_now() - timedelta(days=int(since_days))
    since_iso = _iso(since_dt)

    # Step 1: fetch candidate context rows by time and request_id substring.
    try:
        ctx_q = (
            client.table("model_proxy_request_contexts")
            .select(
                ",".join(
                    [
                        "id",
                        "request_id",
                        "raw_context_token_count",
                        "condensed_context_token_count",
                        "tokens_saved",
                        "raw_context_chars",
                        "condensed_context_chars",
                        "condensation_method",
                        "condensation_version",
                        "condensation_trigger",
                        "created_at",
                    ]
                )
            )
            .gte("created_at", since_iso)
            .order("created_at", desc=True)
            .limit(int(limit) * 5)
        )

        if q is not None and q.strip():
            ctx_q = ctx_q.ilike("request_id", f"%{q.strip()}%")

        ctx_resp = ctx_q.execute()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503, detail="Supabase is unreachable (request lookup)."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Failed to query model_proxy_request_contexts: {exc}"
        ) from exc

    ctx_data = getattr(ctx_resp, "data", None)
    if not isinstance(ctx_data, list):
        raise HTTPException(
            status_code=500,
            detail="Unexpected response from Supabase (model_proxy_request_contexts)",
        )

    ctx_rows: list[dict[str, Any]] = [r for r in ctx_data if isinstance(r, dict)]
    ctx_request_ids = [
        str(r.get("request_id")).strip()
        for r in ctx_rows
        if isinstance(r.get("request_id"), str) and str(r.get("request_id")).strip()
    ]
    ctx_request_ids = list(dict.fromkeys(ctx_request_ids))

    if not ctx_request_ids:
        return {
            "filters": {
                "q": q,
                "app_id": app_id,
                "project_id": project_id,
                "provider": provider,
                "model": model,
                "since_days": since_days,
                "limit": limit,
            },
            "source": {"type": "supabase", "table": "model_proxy_request_contexts"},
            "count": 0,
            "rows": [],
        }

    # Step 2: fetch matching request headers for those request_ids (apply filters here).
    # Chunk to avoid large IN() payloads.
    def _chunks(items: list[str], size: int) -> list[list[str]]:
        out: list[list[str]] = []
        for i in range(0, len(items), size):
            out.append(items[i : i + size])
        return out

    req_by_id: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(ctx_request_ids, 200):
        try:
            req_q = (
                client.table("model_proxy_requests")
                .select(
                    ",".join(
                        [
                            "request_id",
                            "request_timestamp",
                            "provider",
                            "model",
                            "status_code",
                            "latency_ms",
                            "app_id",
                            "request_token_count",
                            "response_token_count",
                        ]
                    )
                )
                .in_("request_id", chunk)
                .gte("request_timestamp", since_iso)
            )

            if app_id is not None:
                req_q = req_q.eq("app_id", app_id)
            if provider is not None:
                req_q = req_q.eq("provider", provider)
            if model is not None:
                req_q = req_q.eq("model", model)

            req_resp = req_q.execute()
        except Exception:
            continue

        req_data = getattr(req_resp, "data", None)
        if not isinstance(req_data, list):
            continue

        for r in req_data:
            if not isinstance(r, dict):
                continue
            rid = r.get("request_id")
            if isinstance(rid, str) and rid.strip():
                req_by_id[rid.strip()] = r

    # Build final rows (only keep contexts whose request header survived filters).
    out_rows: list[dict[str, Any]] = []
    for c in ctx_rows:
        rid = c.get("request_id")
        if not isinstance(rid, str) or not rid.strip():
            continue
        rid = rid.strip()
        req = req_by_id.get(rid)
        if req is None:
            continue

        out_rows.append(
            {
                "schema": "model_proxy_minimal",
                "context_id": c.get("id"),
                "request_id": rid,
                "timestamp": req.get("request_timestamp"),
                "provider": req.get("provider"),
                "model": req.get("model"),
                "status_code": req.get("status_code"),
                "latency_ms": req.get("latency_ms"),
                "app_id": req.get("app_id"),
                "request_token_count": _safe_int(req.get("request_token_count")),
                "response_token_count": _safe_int(req.get("response_token_count")),
                "raw_context_token_count": _safe_int(c.get("raw_context_token_count"))
                if c.get("raw_context_token_count") is not None
                else None,
                "condensed_context_token_count": _safe_int(c.get("condensed_context_token_count"))
                if c.get("condensed_context_token_count") is not None
                else None,
                "tokens_saved": _safe_int(c.get("tokens_saved"))
                if c.get("tokens_saved") is not None
                else None,
                "raw_context_chars": _safe_int(c.get("raw_context_chars"))
                if c.get("raw_context_chars") is not None
                else None,
                "condensed_context_chars": _safe_int(c.get("condensed_context_chars"))
                if c.get("condensed_context_chars") is not None
                else None,
                "condensation_method": c.get("condensation_method"),
                "condensation_version": c.get("condensation_version"),
                "condensation_trigger": c.get("condensation_trigger"),
            }
        )

    out_rows.sort(key=lambda r: (r.get("timestamp") or ""), reverse=True)
    out_rows = out_rows[: int(limit)]

    return {
        "filters": {
            "q": q,
            "app_id": app_id,
            "project_id": project_id,
            "provider": provider,
            "model": model,
            "since_days": since_days,
            "limit": limit,
        },
        "source": {
            "type": "supabase",
            "table": "model_proxy_requests+model_proxy_request_contexts",
        },
        "count": len(out_rows),
        "rows": out_rows,
    }


@router.get("/request/details")
async def request_details(
    request_id: str | None = Query(default=None),
    context_id: str | None = Query(
        default=None,
        description="Optional model_proxy_request_contexts.id to select an exact context row",
    ),
    include_payloads: bool = Query(default=True),
    include_messages: bool = Query(default=True),
    include_tools: bool = Query(default=True),
    include_tool_executions: bool = Query(default=True),
    max_child_rows: int = Query(default=500, ge=1, le=MAX_REQUEST_CHILD_ROWS),
) -> dict[str, Any]:
    """Fetch minimal request + context details for a single request_id.

    Minimal schema sources:
    - public.model_proxy_requests
    - public.model_proxy_request_contexts

    If context_id is provided, the API will try to fetch that exact context row. This enables
    deterministic UI expansion even if multiple context rows exist for the same request_id.

    The include_* params are kept for backward compatibility but are ignored (no child tables).
    """
    rid = _validate_request_id(request_id)
    if context_id is not None:
        _validate_len("context_id", context_id, 200)
        cid = context_id.strip()
        if not cid:
            context_id = None
        elif re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            cid,
        ) is None:
            raise HTTPException(status_code=400, detail="context_id must be a UUID")
        else:
            context_id = cid.lower()

    client = _get_client_or_503()

    # ---- request row ----
    try:
        req_resp = (
            client.table("model_proxy_requests")
            .select("*")
            .eq("request_id", rid)
            .limit(1)
            .execute()
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503, detail="Supabase is unreachable (request details)."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Failed to query model_proxy_requests: {exc}"
        ) from exc

    req_data = getattr(req_resp, "data", None)
    request_row = (
        req_data[0]
        if isinstance(req_data, list) and req_data and isinstance(req_data[0], dict)
        else None
    )
    if request_row is None:
        raise HTTPException(status_code=404, detail="request_id not found")

    # ---- request context row ----
    request_context_row: dict[str, Any] | None = None
    try:
        if context_id is not None:
            ctx_resp = (
                client.table("model_proxy_request_contexts")
                .select("*")
                .eq("id", context_id)
                .limit(1)
                .execute()
            )
        else:
            ctx_resp = (
                client.table("model_proxy_request_contexts")
                .select("*")
                .eq("request_id", rid)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

        ctx_data = getattr(ctx_resp, "data", None)
        if isinstance(ctx_data, list) and ctx_data and isinstance(ctx_data[0], dict):
            row0 = ctx_data[0]
            # Safety: if a context_id was provided, ensure it belongs to this request_id.
            if context_id is None or row0.get("request_id") == rid:
                request_context_row = row0
    except Exception:
        request_context_row = None

    return {
        "request_id": rid,
        "schema": "model_proxy_minimal",
        "request": request_row,
        "request_context": request_context_row,
        "children": {
            # Kept for compatibility with older clients; always empty in minimal schema.
            "payloads": [],
            "messages": [],
            "tools": [],
            "tool_executions": [],
        },
        "notes": {
            "payloads_available": False,
            "messages_available": False,
            "tools_available": False,
            "tool_executions_available": False,
            "context_id": context_id,
        },
    }
