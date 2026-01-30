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

- public.model_proxy_requests (string app_id, request_timestamp, input_tokens/output_tokens, estimated_cost)

The updated model-proxy schema (as provided by the user) uses:

- public.model_proxy_api_requests (integer app_id, timestamp, prompt_tokens/completion_tokens, total_cost_usd)

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
"""

from __future__ import annotations

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
    prompt_tokens_col: str
    completion_tokens_col: str
    total_cost_col: str
    duration_ms_col: str
    status_code_col: str
    message_count_col: str
    metadata_col: str

    # optional filters
    app_id_col: str | None
    project_id_col: str | None


def _detect_source(client: Any) -> _SourceSpec:
    """Detect which model-proxy schema exists in the connected Supabase.

    Preference order:
    1) model_proxy_api_requests (new, per user docs)
    2) model_proxy_requests (existing in this repo)
    """
    # Try new table first
    try:
        client.table("model_proxy_api_requests").select("id").limit(1).execute()
        return _SourceSpec(
            kind="api_requests",
            table="model_proxy_api_requests",
            ts_col="timestamp",
            model_col="model",
            provider_col="provider_name",
            prompt_tokens_col="prompt_tokens",
            completion_tokens_col="completion_tokens",
            total_cost_col="total_cost_usd",
            duration_ms_col="duration_ms",
            status_code_col="status_code",
            message_count_col="message_count",
            metadata_col="metadata",
            app_id_col="app_id",  # integer in this schema
            project_id_col="project_id",
        )
    except Exception:
        pass

    # Fall back to table used by existing Mindscape endpoints
    try:
        client.table("model_proxy_requests").select("id").limit(1).execute()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=(
                "Supabase is reachable, but neither model_proxy_api_requests nor "
                f"model_proxy_requests could be queried: {exc}"
            ),
        ) from exc

    return _SourceSpec(
        kind="requests",
        table="model_proxy_requests",
        ts_col="request_timestamp",
        model_col="model",
        provider_col="provider_name",
        prompt_tokens_col="input_tokens",
        completion_tokens_col="output_tokens",
        total_cost_col="estimated_cost",
        duration_ms_col="latency_ms",
        status_code_col="status_code",
        message_count_col="message_count",
        metadata_col="metadata",
        app_id_col="app_id",  # varchar in this schema
        project_id_col="project_id",
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
    idx = int((p * n + (1.0 - 1e-12)) // 1)  # floor-ish, then adjust to nearest rank
    # Use ceil by computing rank and subtracting 1
    import math

    rank = max(1, int(math.ceil(p * n)))
    idx2 = min(n - 1, rank - 1)
    return values_sorted[idx2]


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
    query: Any,
    src: _SourceSpec,
    app_id: str | None,
    project_id: str | None,
    provider: str | None,
    model: str | None,
) -> Any:
    """Apply common filters.

    Scope heuristics:
    - If src.kind == api_requests and app_id is digits-only: filter on integer app_id.
    - If src.kind == api_requests and app_id is NOT digits-only:
        try treating it as project_id (common deployment pattern).
    - Otherwise: filter on app_id (string) when available.
    - project_id param always filters on project_id when that column exists.
    """
    if provider is not None:
        query = query.eq(src.provider_col, provider)
    if model is not None:
        query = query.eq(src.model_col, model)

    if project_id is not None and src.project_id_col is not None:
        query = query.eq(src.project_id_col, project_id)

    if app_id is not None and src.app_id_col is not None:
        if src.kind == "api_requests":
            if app_id.isdigit():
                query = query.eq(src.app_id_col, int(app_id))
            elif src.project_id_col is not None:
                query = query.eq(src.project_id_col, app_id)
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
    select_cols = ",".join(
        [
            src.ts_col,
            src.model_col,
            src.provider_col,
            src.prompt_tokens_col,
            src.completion_tokens_col,
            src.total_cost_col,
            src.duration_ms_col,
            src.status_code_col,
            src.message_count_col,
            src.metadata_col,
            # identity columns to return where useful
            "request_id",
            "project_id",
            "app_id",
        ]
    )

    since_iso = _iso(since_dt)

    try:
        query = client.table(src.table).select(select_cols)
        query = _apply_scope_filters(
            query=query,
            src=src,
            app_id=app_id,
            project_id=project_id,
            provider=provider,
            model=model,
        )
        query = query.gte(src.ts_col, since_iso).order(src.ts_col, desc=True).limit(limit)

        resp = query.execute()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Supabase is unreachable (context metrics).") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to query {src.table}: {exc}") from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail=f"Unexpected response from Supabase ({src.table})")

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
    """Condensation ROI summary (based on Query 8).

    Computes:
    - condensation_rate_pct
    - avg_tokens_saved_per_request (from metadata.context_tokens_saved)
    - token_reduction_pct (avg non-condensed prompt tokens vs condensed prompt tokens)
    - total_cost_usd
    - estimated_savings_usd (rough, configurable by client later)
    """
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        _validate_len("project_id", project_id, 255)

    client = _get_client_or_503()
    src = _detect_source(client)

    since_dt = _utc_now() - timedelta(days=int(since_days))
    rows = _fetch_rows(
        client=client,
        src=src,
        since_dt=since_dt,
        app_id=app_id,
        project_id=project_id,
        provider=provider,
        model=model,
        limit=int(max_rows),
    )

    total_requests = len(rows)
    condensed_requests = 0

    tokens_condensed_sum = 0
    tokens_condensed_n = 0

    tokens_not_condensed_sum = 0
    tokens_not_condensed_n = 0

    tokens_saved_sum = 0
    tokens_saved_n = 0

    total_cost = 0.0

    for r in rows:
        meta = r.get(src.metadata_col)
        is_condensed = _meta_bool(meta, "context_condensed")
        prompt_tokens = _safe_int(r.get(src.prompt_tokens_col))
        total_cost += _safe_float(r.get(src.total_cost_col))

        if is_condensed:
            condensed_requests += 1
            tokens_condensed_sum += prompt_tokens
            tokens_condensed_n += 1
        else:
            tokens_not_condensed_sum += prompt_tokens
            tokens_not_condensed_n += 1

        saved = _meta_int(meta, "context_tokens_saved")
        if saved is not None:
            tokens_saved_sum += saved
            tokens_saved_n += 1

    avg_tokens_condensed = (tokens_condensed_sum / tokens_condensed_n) if tokens_condensed_n else None
    avg_tokens_not_condensed = (tokens_not_condensed_sum / tokens_not_condensed_n) if tokens_not_condensed_n else None
    avg_tokens_saved = (tokens_saved_sum / tokens_saved_n) if tokens_saved_n else None

    if total_requests:
        condensation_rate_pct = (condensed_requests / total_requests) * 100.0
    else:
        condensation_rate_pct = None

    token_reduction_pct = None
    if avg_tokens_condensed is not None and avg_tokens_not_condensed not in (None, 0):
        token_reduction_pct = ((avg_tokens_not_condensed - avg_tokens_condensed) / avg_tokens_not_condensed) * 100.0

    # Keep same "rough" constant from docs query (assumes $0.000005/token).
    estimated_savings_usd = None
    if avg_tokens_saved is not None:
        estimated_savings_usd = float(avg_tokens_saved) * condensed_requests * 0.000005

    return {
        "filters": {
            "app_id": app_id,
            "project_id": project_id,
            "provider": provider,
            "model": model,
            "since_days": since_days,
            "max_rows": max_rows,
        },
        "source": {"type": "supabase", "table": src.table},
        "stats": {
            "total_requests": total_requests,
            "condensed_requests": condensed_requests,
            "condensation_rate_pct": None if condensation_rate_pct is None else round(condensation_rate_pct, 1),
            "avg_tokens_condensed": None if avg_tokens_condensed is None else round(avg_tokens_condensed, 0),
            "avg_tokens_not_condensed": None if avg_tokens_not_condensed is None else round(avg_tokens_not_condensed, 0),
            "avg_tokens_saved_per_request": None if avg_tokens_saved is None else round(avg_tokens_saved, 0),
            "token_reduction_pct": None if token_reduction_pct is None else round(token_reduction_pct, 1),
            "total_cost_usd": round(total_cost, 4),
            "estimated_savings_usd": None if estimated_savings_usd is None else round(estimated_savings_usd, 4),
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
    """Daily token usage trends (based on Query 1).

    Computes per (date, model):
    - request_count
    - avg_prompt_tokens, median_prompt_tokens, p95_prompt_tokens, max_prompt_tokens
    - avg_completion_tokens
    - avg_cost, total_cost
    """
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        _validate_len("project_id", project_id, 255)

    client = _get_client_or_503()
    src = _detect_source(client)

    since_dt = _utc_now() - timedelta(days=int(days))
    rows = _fetch_rows(
        client=client,
        src=src,
        since_dt=since_dt,
        app_id=app_id,
        project_id=project_id,
        provider=provider,
        model=model,
        limit=int(max_rows),
    )

    # group by (date, model)
    groups: dict[tuple[str, str], dict[str, Any]] = {}

    for r in rows:
        ts = _parse_ts(r.get(src.ts_col))
        if ts is None:
            continue
        date = _date_key(ts)
        m = str(r.get(src.model_col) or "unknown")

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
                "cost_sum": 0.0,
            }
            groups[key] = g

        g["request_count"] += 1
        pt = _safe_int(r.get(src.prompt_tokens_col))
        g["prompt_tokens"].append(pt)

        ct = _safe_int(r.get(src.completion_tokens_col))
        g["completion_tokens_sum"] += ct
        g["completion_tokens_n"] += 1

        g["cost_sum"] += _safe_float(r.get(src.total_cost_col))

    out: list[dict[str, Any]] = []
    for (_date, _model), g in groups.items():
        pts = sorted(g["prompt_tokens"])
        avg_prompt = (sum(pts) / len(pts)) if pts else None

        median = _percentile_sorted(pts, 0.50)
        p95 = _percentile_sorted(pts, 0.95)
        mx = pts[-1] if pts else None

        avg_completion = (
            (g["completion_tokens_sum"] / g["completion_tokens_n"]) if g["completion_tokens_n"] else None
        )
        avg_cost = (g["cost_sum"] / g["request_count"]) if g["request_count"] else None

        out.append(
            {
                "date": g["date"],
                "model": g["model"],
                "request_count": g["request_count"],
                "avg_prompt_tokens": None if avg_prompt is None else round(avg_prompt, 0),
                "median_prompt_tokens": median,
                "p95_prompt_tokens": p95,
                "max_prompt_tokens": mx,
                "avg_completion_tokens": None if avg_completion is None else round(avg_completion, 0),
                "avg_cost_usd": None if avg_cost is None else round(avg_cost, 6),
                "total_cost_usd": round(g["cost_sum"], 4),
            }
        )

    out.sort(key=lambda r: (r["date"], r["model"]), reverse=True)

    return {
        "filters": {"app_id": app_id, "project_id": project_id, "provider": provider, "model": model, "days": days},
        "source": {"type": "supabase", "table": src.table},
        "count": len(out),
        "rows": out,
        "notes": {"percentiles": "nearest-rank in Python", "max_rows": max_rows},
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
    """Condensation effectiveness by type (based on Query 3)."""
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        _validate_len("project_id", project_id, 255)

    client = _get_client_or_503()
    src = _detect_source(client)

    since_dt = _utc_now() - timedelta(days=int(days))
    rows = _fetch_rows(
        client=client,
        src=src,
        since_dt=since_dt,
        app_id=app_id,
        project_id=project_id,
        provider=provider,
        model=model,
        limit=int(max_rows),
    )

    # group by (date, model)
    groups: dict[tuple[str, str], dict[str, Any]] = {}

    def _get_group(date: str, m: str) -> dict[str, Any]:
        key = (date, m)
        g = groups.get(key)
        if g is None:
            g = {
                "date": date,
                "model": m,
                "total_requests": 0,
                "rules_injected_count": 0,
                "rules_tokens_sum": 0,
                "rules_tokens_n": 0,
                "code_jit_count": 0,
                "code_jit_tokens_sum": 0,
                "code_jit_tokens_n": 0,
                "condensed_count": 0,
                "tokens_saved_sum": 0,
                "tokens_saved_n": 0,
                "prompt_tokens_sum": 0,
                "prompt_tokens_n": 0,
                "cost_sum": 0.0,
            }
            groups[key] = g
        return g

    for r in rows:
        ts = _parse_ts(r.get(src.ts_col))
        if ts is None:
            continue
        date = _date_key(ts)
        m = str(r.get(src.model_col) or "unknown")
        g = _get_group(date, m)

        g["total_requests"] += 1

        meta = r.get(src.metadata_col)
        if _meta_bool(meta, "rules_injected"):
            g["rules_injected_count"] += 1
        rules_tokens = _meta_int(meta, "rules_tokens")
        if rules_tokens is not None:
            g["rules_tokens_sum"] += rules_tokens
            g["rules_tokens_n"] += 1

        if _meta_bool(meta, "code_jit_injected"):
            g["code_jit_count"] += 1
        code_tokens = _meta_int(meta, "code_jit_tokens")
        if code_tokens is not None:
            g["code_jit_tokens_sum"] += code_tokens
            g["code_jit_tokens_n"] += 1

        if _meta_bool(meta, "context_condensed"):
            g["condensed_count"] += 1
        saved = _meta_int(meta, "context_tokens_saved")
        if saved is not None:
            g["tokens_saved_sum"] += saved
            g["tokens_saved_n"] += 1

        pt = _safe_int(r.get(src.prompt_tokens_col))
        g["prompt_tokens_sum"] += pt
        g["prompt_tokens_n"] += 1

        g["cost_sum"] += _safe_float(r.get(src.total_cost_col))

    out: list[dict[str, Any]] = []
    for (_date, _model), g in groups.items():
        out.append(
            {
                "date": g["date"],
                "model": g["model"],
                "total_requests": g["total_requests"],
                "rules_injected_count": g["rules_injected_count"],
                "avg_rules_tokens": None
                if not g["rules_tokens_n"]
                else round(g["rules_tokens_sum"] / g["rules_tokens_n"], 0),
                "code_jit_count": g["code_jit_count"],
                "avg_code_jit_tokens": None
                if not g["code_jit_tokens_n"]
                else round(g["code_jit_tokens_sum"] / g["code_jit_tokens_n"], 0),
                "condensed_count": g["condensed_count"],
                "avg_tokens_saved": None
                if not g["tokens_saved_n"]
                else round(g["tokens_saved_sum"] / g["tokens_saved_n"], 0),
                "avg_prompt_tokens": None
                if not g["prompt_tokens_n"]
                else round(g["prompt_tokens_sum"] / g["prompt_tokens_n"], 0),
                "avg_cost_usd": None if not g["total_requests"] else round(g["cost_sum"] / g["total_requests"], 6),
            }
        )

    out.sort(key=lambda r: (r["date"], r["model"]), reverse=True)

    return {
        "filters": {"app_id": app_id, "project_id": project_id, "provider": provider, "model": model, "days": days},
        "source": {"type": "supabase", "table": src.table},
        "count": len(out),
        "rows": out,
        "notes": {"max_rows": max_rows},
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
    """Top cost requests to identify optimization targets (based on Query 6)."""
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        _validate_len("project_id", project_id, 255)

    client = _get_client_or_503()
    src = _detect_source(client)

    since_dt = _utc_now() - timedelta(days=int(since_days))
    since_iso = _iso(since_dt)

    select_cols = ",".join(
        [
            "request_id",
            src.ts_col,
            src.model_col,
            src.provider_col,
            src.prompt_tokens_col,
            src.completion_tokens_col,
            src.total_cost_col,
            src.duration_ms_col,
            src.status_code_col,
            src.message_count_col,
            "prompt_char_count",
            "project_id",
            "app_id",
            src.metadata_col,
        ]
    )

    try:
        query = client.table(src.table).select(select_cols)
        query = _apply_scope_filters(
            query=query,
            src=src,
            app_id=app_id,
            project_id=project_id,
            provider=provider,
            model=model,
        )
        query = query.gte(src.ts_col, since_iso).order(src.total_cost_col, desc=True).limit(int(limit))
        resp = query.execute()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Supabase is unreachable (top cost requests).") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to query {src.table} top-cost: {exc}") from exc

    data = getattr(resp, "data", None)
    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail=f"Unexpected response from Supabase ({src.table})")

    out: list[dict[str, Any]] = []
    for r in data:
        if not isinstance(r, dict):
            continue
        meta = r.get(src.metadata_col)
        out.append(
            {
                "request_id": r.get("request_id"),
                "timestamp": r.get(src.ts_col),
                "provider": r.get(src.provider_col),
                "model": r.get(src.model_col),
                "prompt_tokens": _safe_int(r.get(src.prompt_tokens_col)),
                "completion_tokens": _safe_int(r.get(src.completion_tokens_col)),
                "total_cost_usd": round(_safe_float(r.get(src.total_cost_col)), 6),
                "duration_ms": _safe_int(r.get(src.duration_ms_col)),
                "status_code": r.get(src.status_code_col),
                "message_count": r.get(src.message_count_col),
                "prompt_char_count": r.get("prompt_char_count"),
                "app_id": r.get("app_id"),
                "project_id": r.get("project_id"),
                "rules_injected": _meta_bool(meta, "rules_injected"),
                "context_condensed": _meta_bool(meta, "context_condensed"),
            }
        )

    return {
        "filters": {"app_id": app_id, "project_id": project_id, "provider": provider, "model": model, "since_days": since_days},
        "source": {"type": "supabase", "table": src.table},
        "count": len(out),
        "rows": out,
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
    """Hourly usage patterns (based on Query 7).

    Returns per (hour, model):
    - request_count
    - avg_prompt_tokens
    - total_cost_usd
    - avg_latency_ms
    """
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        _validate_len("project_id", project_id, 255)

    client = _get_client_or_503()
    src = _detect_source(client)

    since_dt = _utc_now() - timedelta(hours=int(since_hours))
    rows = _fetch_rows(
        client=client,
        src=src,
        since_dt=since_dt,
        app_id=app_id,
        project_id=project_id,
        provider=provider,
        model=model,
        limit=int(max_rows),
    )

    groups: dict[tuple[str, str], dict[str, Any]] = {}

    for r in rows:
        ts = _parse_ts(r.get(src.ts_col))
        if ts is None:
            continue
        hour = ts.replace(minute=0, second=0, microsecond=0).isoformat()
        m = str(r.get(src.model_col) or "unknown")
        key = (hour, m)

        g = groups.get(key)
        if g is None:
            g = {
                "hour": hour,
                "model": m,
                "request_count": 0,
                "prompt_tokens_sum": 0,
                "prompt_tokens_n": 0,
                "cost_sum": 0.0,
                "latency_sum": 0,
                "latency_n": 0,
            }
            groups[key] = g

        g["request_count"] += 1
        g["prompt_tokens_sum"] += _safe_int(r.get(src.prompt_tokens_col))
        g["prompt_tokens_n"] += 1
        g["cost_sum"] += _safe_float(r.get(src.total_cost_col))

        lat = r.get(src.duration_ms_col)
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
                "total_cost_usd": round(g["cost_sum"], 4),
                "avg_latency_ms": None if not g["latency_n"] else round(g["latency_sum"] / g["latency_n"], 0),
            }
        )

    out.sort(key=lambda r: (r["hour"], r["model"]), reverse=True)

    return {
        "filters": {"app_id": app_id, "project_id": project_id, "provider": provider, "model": model, "since_hours": since_hours},
        "source": {"type": "supabase", "table": src.table},
        "count": len(out),
        "rows": out,
        "notes": {"max_rows": max_rows},
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
    """Error rate monitoring (based on Query 9)."""
    _validate_app_id(app_id)
    _validate_provider(provider)
    _validate_model(model)
    if project_id is not None:
        _validate_len("project_id", project_id, 255)

    client = _get_client_or_503()
    src = _detect_source(client)

    since_dt = _utc_now() - timedelta(days=int(days))
    rows = _fetch_rows(
        client=client,
        src=src,
        since_dt=since_dt,
        app_id=app_id,
        project_id=project_id,
        provider=provider,
        model=model,
        limit=int(max_rows),
    )

    groups: dict[str, dict[str, Any]] = {}

    for r in rows:
        ts = _parse_ts(r.get(src.ts_col))
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

        status = r.get(src.status_code_col)
        status_i = int(status) if isinstance(status, (int, float)) else None
        if status_i is not None and status_i >= 400:
            g["error_count"] += 1
            if status_i == 400:
                g["bad_request_errors"] += 1
            if status_i == 429:
                g["rate_limit_errors"] += 1
            if status_i >= 500:
                g["server_errors"] += 1

        lat = r.get(src.duration_ms_col)
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
                "avg_latency_ms": None if not g["latency_n"] else round(g["latency_sum"] / g["latency_n"], 0),
            }
        )

    out.sort(key=lambda r: r["date"], reverse=True)

    return {
        "filters": {"app_id": app_id, "project_id": project_id, "provider": provider, "model": model, "days": days},
        "source": {"type": "supabase", "table": src.table},
        "count": len(out),
        "rows": out,
        "notes": {"max_rows": max_rows},
    }