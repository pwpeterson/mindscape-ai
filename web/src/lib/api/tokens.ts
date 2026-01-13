import { browser } from "$app/environment";
import { env } from "$env/dynamic/public";

export type FetchLike = (
    input: RequestInfo | URL,
    init?: RequestInit,
) => Promise<Response>;

export type TokensBreakdownSource = {
    configured: boolean;
    chars: number;
    approx_tokens: number;
    error?: string | null;

    // ConPort
    db?: string;
    items?: Record<string, number>;

    // Prompts
    file_count?: number;

    // Mem0
    item_count?: number;
};

export type TokensBreakdownResponse = {
    app_id: string | null;
    user_id: string | null;
    project_id: string | null;
    sources: {
        conport: TokensBreakdownSource;
        prompts: TokensBreakdownSource;
        mem0: TokensBreakdownSource;
    };
    total: {
        approx_tokens: number;
    };
    notes?: Record<string, unknown>;
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

export async function tokensBreakdown(
    fetchFn: FetchLike,
    params: {
        app_id?: string | null;
        user_id?: string | null;
        project_id?: string | null;
        db?: string | null;
    } = {},
): Promise<TokensBreakdownResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/tokens/breakdown", {
            app_id: params.app_id ?? undefined,
            user_id: params.user_id ?? undefined,
            project_id: params.project_id ?? undefined,
            db: params.db ?? undefined,
        }),
    );
}
