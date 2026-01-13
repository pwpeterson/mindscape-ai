import { browser } from "$app/environment";
import { env } from "$env/dynamic/public";

export type FetchLike = (
    input: RequestInfo | URL,
    init?: RequestInit,
) => Promise<Response>;

export type Mem0HealthResponse = {
    status: "ok" | "degraded";
    mem0?: "available" | "unavailable";
    detail?: string;
};

export type Mem0Memory = {
    // mem0 may return one of these; we preserve as-is for now.
    id?: string;
    memory_id?: string;
    _id?: string;

    // common fields
    memory?: string;
    content?: string;
    metadata?: Record<string, unknown>;

    // search result score (provider-dependent)
    score?: number;
    similarity?: number;

    // allow extra fields
    [key: string]: unknown;
};

export type Mem0ListMemoriesResponse = {
    success: boolean;
    user_id: string;
    app_id?: string | null;
    project_id?: string | null;
    count: number;
    memories: Mem0Memory[];
};

export type Mem0SearchResponse = {
    success: boolean;
    query: string;
    user_id: string;
    app_id?: string | null;
    project_id?: string | null;
    results: Mem0Memory[];
};

function apiBase(): string {
    // Never use an absolute base in the browser; it breaks remote access scenarios
    // where 127.0.0.1 refers to the client machine (not the server running containers).
    // Prefer same-origin "/api/*" (reverse-proxied by SvelteKit in hooks.server.ts).
    if (browser) return "";

    const configured = env.PUBLIC_MINDSCAPE_API_BASE?.trim();
    return configured ? configured.replace(/\/$/, "") : "";
}

function buildUrl(
    path: string,
    params: Record<string, string | null | undefined> = {},
): string {
    const base = apiBase();

    if (base) {
        const url = new URL(`${base}${path}`);
        for (const [k, v] of Object.entries(params)) {
            if (v != null && v !== "") url.searchParams.set(k, v);
        }
        return url.toString();
    }

    const url = new URL(path, "http://local");
    for (const [k, v] of Object.entries(params)) {
        if (v != null && v !== "") url.searchParams.set(k, v);
    }
    return url.pathname + url.search;
}

async function getJson<T>(
    fetchFn: FetchLike,
    url: string,
    init: RequestInit = {},
): Promise<T> {
    // Prevent UI hangs when the dev proxy target is unreachable.
    // Can be overridden via PUBLIC_MINDSCAPE_API_TIMEOUT_MS.
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

export async function mem0Health(fetchFn: FetchLike): Promise<Mem0HealthResponse> {
    return getJson(fetchFn, buildUrl("/api/v1/mem0/health"));
}

export async function mem0ListMemories(
    fetchFn: FetchLike,
    params: {
        user_id?: string | null;
        app_id?: string | null;
        project_id?: string | null;
        limit?: number;
    } = {},
): Promise<Mem0ListMemoriesResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/mem0/memories", {
            user_id: params.user_id ?? undefined,
            app_id: params.app_id ?? undefined,
            project_id: params.project_id ?? undefined,
            limit: params.limit != null ? String(params.limit) : undefined,
        }),
    );
}

export async function mem0Search(
    fetchFn: FetchLike,
    params: {
        q: string;
        user_id?: string | null;
        app_id?: string | null;
        project_id?: string | null;
        limit?: number;
    },
): Promise<Mem0SearchResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/mem0/search", {
            q: params.q,
            user_id: params.user_id ?? undefined,
            app_id: params.app_id ?? undefined,
            project_id: params.project_id ?? undefined,
            limit: params.limit != null ? String(params.limit) : undefined,
        }),
    );
}
