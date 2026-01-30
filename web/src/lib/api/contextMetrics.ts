import { browser } from "$app/environment";
import { env } from "$env/dynamic/public";

export type FetchLike = (
    input: RequestInfo | URL,
    init?: RequestInit,
) => Promise<Response>;

export type ContextMetricsSource = {
    type: "supabase";
    table: string;
};

export type ContextMetricsRoiStats = {
    total_requests: number;
    condensed_requests: number;
    condensation_rate_pct: number | null;
    avg_tokens_condensed: number | null;
    avg_tokens_not_condensed: number | null;
    avg_tokens_saved_per_request: number | null;
    token_reduction_pct: number | null;
    total_cost_usd: number;
    estimated_savings_usd: number | null;
};

export type ContextMetricsRoiResponse = {
    filters: Record<string, unknown>;
    source: ContextMetricsSource;
    stats: ContextMetricsRoiStats;
};

export type ContextMetricsDailyRow = {
    date: string;
    model: string;
    request_count: number;

    avg_prompt_tokens: number | null;
    median_prompt_tokens: number | null;
    p95_prompt_tokens: number | null;
    max_prompt_tokens: number | null;

    avg_completion_tokens: number | null;

    avg_cost_usd: number | null;
    total_cost_usd: number;
};

export type ContextMetricsDailyResponse = {
    filters: Record<string, unknown>;
    source: ContextMetricsSource;
    count: number;
    rows: ContextMetricsDailyRow[];
    notes?: Record<string, unknown>;
};

export type ContextMetricsByTypeRow = {
    date: string;
    model: string;

    total_requests: number;

    rules_injected_count: number;
    avg_rules_tokens: number | null;

    code_jit_count: number;
    avg_code_jit_tokens: number | null;

    condensed_count: number;
    avg_tokens_saved: number | null;

    avg_prompt_tokens: number | null;
    avg_cost_usd: number | null;
};

export type ContextMetricsByTypeResponse = {
    filters: Record<string, unknown>;
    source: ContextMetricsSource;
    count: number;
    rows: ContextMetricsByTypeRow[];
    notes?: Record<string, unknown>;
};

export type ContextMetricsTopCostRow = {
    request_id: string;
    timestamp: string;
    provider: string | null;
    model: string | null;

    prompt_tokens: number;
    completion_tokens: number;
    total_cost_usd: number;

    duration_ms: number;
    status_code: number | null;
    message_count: number | null;

    prompt_char_count: number | null;
    app_id: string | number | null;
    project_id: string | null;

    rules_injected: boolean;
    context_condensed: boolean;
};

export type ContextMetricsTopCostResponse = {
    filters: Record<string, unknown>;
    source: ContextMetricsSource;
    count: number;
    rows: ContextMetricsTopCostRow[];
};

export type ContextMetricsHourlyRow = {
    hour: string;
    model: string;
    request_count: number;
    avg_prompt_tokens: number | null;
    total_cost_usd: number;
    avg_latency_ms: number | null;
};

export type ContextMetricsHourlyResponse = {
    filters: Record<string, unknown>;
    source: ContextMetricsSource;
    count: number;
    rows: ContextMetricsHourlyRow[];
    notes?: Record<string, unknown>;
};

export type ContextMetricsErrorsRow = {
    date: string;
    total_requests: number;
    error_count: number;
    error_rate_pct: number | null;

    bad_request_errors: number;
    rate_limit_errors: number;
    server_errors: number;

    avg_latency_ms: number | null;
};

export type ContextMetricsErrorsResponse = {
    filters: Record<string, unknown>;
    source: ContextMetricsSource;
    count: number;
    rows: ContextMetricsErrorsRow[];
    notes?: Record<string, unknown>;
};

function apiBase(): string {
    // Never use an absolute base in the browser; it breaks remote access scenarios
    // where 127.0.0.1 refers to the client machine (not the server running containers).
    // Always prefer same-origin "/api/*" which is reverse-proxied by SvelteKit.
    if (browser) return "";

    const configured = env.PUBLIC_MINDSCAPE_API_BASE?.trim();
    return configured ? configured.replace(/\/$/, "") : "";
}

function buildUrl(
    path: string,
    params: Record<string, string | null | undefined> = {},
): string {
    // Prefer same-origin relative path (works with SvelteKit reverse-proxy).
    const url = new URL(path, "http://local");
    for (const [k, v] of Object.entries(params)) {
        if (v != null && v !== "") url.searchParams.set(k, v);
    }

    const base = apiBase();
    return base ? `${base}${url.pathname}${url.search}` : url.pathname + url.search;
}

async function getJson<T>(
    fetchFn: FetchLike,
    url: string,
    init: RequestInit = {},
): Promise<T> {
    const timeoutMs = Number(env.PUBLIC_MINDSCAPE_API_TIMEOUT_MS ?? "10000");
    const controller = new AbortController();
    const timer = setTimeout(
        () => controller.abort(),
        Number.isFinite(timeoutMs) ? timeoutMs : 10000,
    );

    try {
        const resp = await fetchFn(url, {
            ...init,
            headers: {
                accept: "application/json",
                ...(init.headers ?? {}),
            },
            signal: controller.signal,
        });

        if (!resp.ok) {
            const text = await resp.text().catch(() => "");
            throw new Error(
                `Request failed: ${resp.status} ${resp.statusText}${text ? ` — ${text}` : ""}`,
            );
        }

        if (resp.status === 204) return undefined as T;
        return (await resp.json()) as T;
    } catch (err) {
        const name = (err as { name?: string } | null)?.name;
        if (name === "AbortError") {
            throw new Error(`Request timed out after ${timeoutMs}ms`);
        }
        throw err;
    } finally {
        clearTimeout(timer);
    }
}

export async function contextMetricsRoi(
    fetchFn: FetchLike,
    params: {
        app_id?: string | null;
        project_id?: string | null;
        provider?: string | null;
        model?: string | null;
        since_days?: number | null;
        max_rows?: number | null;
    } = {},
): Promise<ContextMetricsRoiResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/context-metrics/roi", {
            app_id: params.app_id ?? null,
            project_id: params.project_id ?? null,
            provider: params.provider ?? null,
            model: params.model ?? null,
            since_days: params.since_days != null ? String(params.since_days) : null,
            max_rows: params.max_rows != null ? String(params.max_rows) : null,
        }),
    );
}

export async function contextMetricsDaily(
    fetchFn: FetchLike,
    params: {
        app_id?: string | null;
        project_id?: string | null;
        provider?: string | null;
        model?: string | null;
        days?: number | null;
        max_rows?: number | null;
    } = {},
): Promise<ContextMetricsDailyResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/context-metrics/daily", {
            app_id: params.app_id ?? null,
            project_id: params.project_id ?? null,
            provider: params.provider ?? null,
            model: params.model ?? null,
            days: params.days != null ? String(params.days) : null,
            max_rows: params.max_rows != null ? String(params.max_rows) : null,
        }),
    );
}

export async function contextMetricsByType(
    fetchFn: FetchLike,
    params: {
        app_id?: string | null;
        project_id?: string | null;
        provider?: string | null;
        model?: string | null;
        days?: number | null;
        max_rows?: number | null;
    } = {},
): Promise<ContextMetricsByTypeResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/context-metrics/by-type", {
            app_id: params.app_id ?? null,
            project_id: params.project_id ?? null,
            provider: params.provider ?? null,
            model: params.model ?? null,
            days: params.days != null ? String(params.days) : null,
            max_rows: params.max_rows != null ? String(params.max_rows) : null,
        }),
    );
}

export async function contextMetricsTopCost(
    fetchFn: FetchLike,
    params: {
        app_id?: string | null;
        project_id?: string | null;
        provider?: string | null;
        model?: string | null;
        since_days?: number | null;
        limit?: number | null;
    } = {},
): Promise<ContextMetricsTopCostResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/context-metrics/top-cost", {
            app_id: params.app_id ?? null,
            project_id: params.project_id ?? null,
            provider: params.provider ?? null,
            model: params.model ?? null,
            since_days: params.since_days != null ? String(params.since_days) : null,
            limit: params.limit != null ? String(params.limit) : null,
        }),
    );
}

export async function contextMetricsHourly(
    fetchFn: FetchLike,
    params: {
        app_id?: string | null;
        project_id?: string | null;
        provider?: string | null;
        model?: string | null;
        since_hours?: number | null;
        max_rows?: number | null;
    } = {},
): Promise<ContextMetricsHourlyResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/context-metrics/hourly", {
            app_id: params.app_id ?? null,
            project_id: params.project_id ?? null,
            provider: params.provider ?? null,
            model: params.model ?? null,
            since_hours: params.since_hours != null ? String(params.since_hours) : null,
            max_rows: params.max_rows != null ? String(params.max_rows) : null,
        }),
    );
}

export async function contextMetricsErrors(
    fetchFn: FetchLike,
    params: {
        app_id?: string | null;
        project_id?: string | null;
        provider?: string | null;
        model?: string | null;
        days?: number | null;
        max_rows?: number | null;
    } = {},
): Promise<ContextMetricsErrorsResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/context-metrics/errors", {
            app_id: params.app_id ?? null,
            project_id: params.project_id ?? null,
            provider: params.provider ?? null,
            model: params.model ?? null,
            days: params.days != null ? String(params.days) : null,
            max_rows: params.max_rows != null ? String(params.max_rows) : null,
        }),
    );
}