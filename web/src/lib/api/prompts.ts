import { browser } from "$app/environment";
import { env } from "$env/dynamic/public";

export type PromptsSignatureResponse = {
    app_id: string | null;
    signature: string;
    file_count: number;
    configured: boolean;
};

export type PromptsFileRow = {
    path: string;
    relpath: string;
    prompt_dir: string;
    bytes: number;
    mtime_ns: number;
    is_text: boolean;
    char_count: number | null;
    line_count: number | null;
    approx_tokens: number | null;
};

export type PromptsFilesResponse = {
    app_id: string | null;
    configured: boolean;
    dir_count: number;
    file_count: number;
    files: PromptsFileRow[];
    notes: {
        prompts_max_file_bytes: number;
        max_files: number;
    };
};

export type PromptsStreamHello = {
    type: "hello";
    ts: string;
    data: {
        service: string;
        protocol: string;
    };
};

export type PromptsStreamSignature = {
    type: "signature";
    ts: string;
    data: {
        signature: string;
        file_count: number;
    };
};

export type PromptsStreamChanged = {
    type: "changed";
    ts: string;
    data: {
        prev_signature: string;
        signature: string;
        file_count: number;
    };
};

export type PromptsStreamError = {
    type: "error";
    ts: string;
    data: {
        message: string;
    };
};

export type PromptsStreamEvent =
    | PromptsStreamHello
    | PromptsStreamSignature
    | PromptsStreamChanged
    | PromptsStreamError;

export type PromptsStreamHandlers = {
    onHello?: (event: PromptsStreamHello) => void;
    onSignature?: (event: PromptsStreamSignature) => void;
    onChanged?: (event: PromptsStreamChanged) => void;
    onErrorEvent?: (event: PromptsStreamError) => void;
    onError?: (event: Event) => void;
    onOpen?: () => void;
};

export type PromptsStreamConnection = {
    close: () => void;
};

export type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

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

export async function promptsSignature(
    fetchFn: FetchLike,
    opts: { app_id?: string | null } = {},
): Promise<PromptsSignatureResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/prompts/signature", {
            app_id: opts.app_id ?? null,
        }),
    );
}

export async function promptsFiles(
    fetchFn: FetchLike,
    opts: {
        app_id?: string | null;
        max_files?: number | null;
        max_file_bytes?: number | null;
    } = {},
): Promise<PromptsFilesResponse> {
    return getJson(
        fetchFn,
        buildUrl("/api/v1/prompts/files", {
            app_id: opts.app_id ?? null,
            max_files: opts.max_files != null ? String(opts.max_files) : null,
            max_file_bytes:
                opts.max_file_bytes != null ? String(opts.max_file_bytes) : null,
        }),
    );
}

export function promptsStreamUrl(opts: {
    app_id?: string | null;
    poll_seconds?: number | null;
} = {}): string {
    return buildUrl("/api/v1/prompts/stream", {
        app_id: opts.app_id ?? null,
        poll_seconds:
            opts.poll_seconds != null ? String(opts.poll_seconds) : null,
    });
}

/**
 * Open an EventSource connection to the prompts SSE stream.
 *
 * Browser-only; call inside onMount().
 */
export function connectPromptsStream(
    handlers: PromptsStreamHandlers,
    opts: { app_id?: string | null; poll_seconds?: number | null } = {},
): PromptsStreamConnection {
    const url = promptsStreamUrl(opts);
    const es = new EventSource(url);

    const onOpen = () => handlers.onOpen?.();
    const onError = (event: Event) => handlers.onError?.(event);

    es.addEventListener("open", onOpen);
    es.addEventListener("error", onError);

    es.addEventListener("hello", (ev: MessageEvent) => {
        try {
            handlers.onHello?.(JSON.parse(ev.data) as PromptsStreamHello);
        } catch {
            // ignore malformed events
        }
    });

    es.addEventListener("signature", (ev: MessageEvent) => {
        try {
            handlers.onSignature?.(JSON.parse(ev.data) as PromptsStreamSignature);
        } catch {
            // ignore malformed events
        }
    });

    es.addEventListener("changed", (ev: MessageEvent) => {
        try {
            handlers.onChanged?.(JSON.parse(ev.data) as PromptsStreamChanged);
        } catch {
            // ignore malformed events
        }
    });

    es.addEventListener("error", (ev: MessageEvent) => {
        try {
            handlers.onErrorEvent?.(JSON.parse(ev.data) as PromptsStreamError);
        } catch {
            // ignore malformed events
        }
    });

    return {
        close: () => es.close(),
    };
}
