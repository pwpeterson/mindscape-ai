import { browser } from "$app/environment";
import { env } from "$env/dynamic/public";

export type FetchLike = (
    input: RequestInfo | URL,
    init?: RequestInit,
) => Promise<Response>;

export type LlmUsageEventRow = {
    id: string;
    request_id: string;

    app_id: string | null;
    task: string | null;

    user_id: string | null;
    agent_id: string | null;
    project_id: string | null;

    provider: string;
    model: string;

    input_tokens: number;
    output_tokens: number;
    total_tokens: number;

    // Supabase numeric comes back as string in many clients; support both.
    estimated_cost: number | string;

    prompt_sha256: string | null;
    prompt_chars: number | null;
    message_count: number | null;

    route: string | null;
    status_code: number | null;
    latency_ms: number | null;
    stream: boolean;

    created_at: string;
};

export type LlmUsageEventsResponse = {
    app_id: string | null;
    filters: {
        task: string | null;
        provider: string | null;
        model: string | null;
        route: string | null;
        since_hours: number;
        limit: number;
    };
    count: number;
    events: LlmUsageEventRow[];
    source: {
        type: "supabase";
        table: "llm_usage_events";
    };
};

export type LlmUsageDailyRow = {
    day: string; // timestamptz / date_trunc output
    app_id: string | null;
    task: string | null;
    provider: string | null;
    model: string | null;

    requests: number;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    estimated_cost: number | string;
};

export type LlmUsageDailyResponse = {
    app_id: string | null;
    filters: {
        task: string | null;
        provider: string | null;
        model: string | null;
        days: number;
        limit: number;
    };
    count: number;
    rows: LlmUsageDailyRow[];
    source: {
        type: "supabase";
        view: "llm_usage_daily";
    };
};

export type LlmRawPromptRow = {
    request_id: string;
    app_id: string | null;
    task: string | null;
    provider: string | null;
    model: string | null;

    messages: unknown; // JSONB - array of message objects
    prompt_text: string;

    prompt_sha256: string | null;
    prompt_chars: number | null;
    message_count: number | null;

    metadata: Record<string, unknown>;
    created_at: string;
};

export type LlmRawPromptsResponse = {
    app_id: string | null;
    filters: {
        task: string | null;
        provider: string | null;
        model: string | null;
        since_hours: number;
        limit: number;
    };
    count: number;
    prompts: LlmRawPromptRow[];
    source: {
        type: "supabase";
        table: "llm_raw_prompts";
    };
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

export async function llmUsageEvents(
    fetchFn: FetchLike,
    params: {
        app_id?: string | null;
        task?: string | null;
        provider?: string | null;
        model?: string | null;
        route?: string | null;
        since_hours?: number | null;
        limit?: number | null;
    } = {},
): Promise<LlmUsageEventsResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/llm-usage/events", {
            app_id: params.app_id ?? null,
            task: params.task ?? null,
            provider: params.provider ?? null,
            model: params.model ?? null,
            route: params.route ?? null,
            since_hours: params.since_hours != null ? String(params.since_hours) : null,
            limit: params.limit != null ? String(params.limit) : null,
        }),
    );
}

export async function llmUsageDaily(
    fetchFn: FetchLike,
    params: {
        app_id?: string | null;
        task?: string | null;
        provider?: string | null;
        model?: string | null;
        days?: number | null;
        limit?: number | null;
    } = {},
): Promise<LlmUsageDailyResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/llm-usage/daily", {
            app_id: params.app_id ?? null,
            task: params.task ?? null,
            provider: params.provider ?? null,
            model: params.model ?? null,
            days: params.days != null ? String(params.days) : null,
            limit: params.limit != null ? String(params.limit) : null,
        }),
    );
}

export async function llmRawPrompts(
    fetchFn: FetchLike,
    params: {
        app_id?: string | null;
        task?: string | null;
        provider?: string | null;
        model?: string | null;
        since_hours?: number | null;
        limit?: number | null;
    } = {},
): Promise<LlmRawPromptsResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/llm-usage/raw-prompts", {
            app_id: params.app_id ?? null,
            task: params.task ?? null,
            provider: params.provider ?? null,
            model: params.model ?? null,
            since_hours: params.since_hours != null ? String(params.since_hours) : null,
            limit: params.limit != null ? String(params.limit) : null,
        }),
    );
}