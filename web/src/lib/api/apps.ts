import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';

export type MindscapeAppSummary = {
    app_id: string;
    has_conport: boolean;
};

export type MindscapeApp = {
    app_id: string;
    display_name: string | null;
    enabled: boolean;
    sort_order: number;
    has_conport: boolean;
};

export type AppsListSource =
    | {
        type: 'supabase';
        table: string;
        configured: boolean;
        count?: number;
    }
    | {
        env: string;
        configured: boolean;
        count?: number;
    };

export type AppsListResponse = {
    apps: MindscapeAppSummary[];
    source: AppsListSource;
};

export type CreateAppRequest = {
    app_id: string;
    root_path: string;
    display_name?: string | null;
    enabled?: boolean;
    sort_order?: number;
};

export type PatchAppRequest = Partial<Omit<CreateAppRequest, 'app_id'>>;

export type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function apiBase(): string {
    // Never use an absolute base in the browser; it breaks remote access scenarios
    // where 127.0.0.1 refers to the client machine (not the server running containers).
    // Always prefer same-origin "/api/*" which can be reverse-proxied by SvelteKit.
    if (browser) return '';

    const configured = env.PUBLIC_MINDSCAPE_API_BASE?.trim();
    return configured ? configured.replace(/\/$/, '') : '';
}

function buildUrl(path: string, params: Record<string, string | null | undefined> = {}): string {
    const base = apiBase();

    if (base) {
        const url = new URL(`${base}${path}`);
        for (const [k, v] of Object.entries(params)) {
            if (v != null && v !== '') url.searchParams.set(k, v);
        }
        return url.toString();
    }

    const url = new URL(path, 'http://local');
    for (const [k, v] of Object.entries(params)) {
        if (v != null && v !== '') url.searchParams.set(k, v);
    }
    return url.pathname + url.search;
}

async function getJson<T>(
    fetchFn: FetchLike,
    url: string,
    init: RequestInit = {}
): Promise<T> {
    // Prevent UI hangs when the dev proxy target is unreachable.
    // Can be overridden via PUBLIC_MINDSCAPE_API_TIMEOUT_MS.
    const timeoutMs = Number(env.PUBLIC_MINDSCAPE_API_TIMEOUT_MS ?? '10000');
    const controller = new AbortController();
    const timer = setTimeout(
        () => controller.abort(),
        Number.isFinite(timeoutMs) ? timeoutMs : 10000
    );

    try {
        const resp = await fetchFn(url, {
            ...init,
            headers: {
                accept: 'application/json',
                ...(init.headers ?? {})
            },
            signal: controller.signal
        });

        if (!resp.ok) {
            const text = await resp.text().catch(() => '');
            throw new Error(
                `Request failed: ${resp.status} ${resp.statusText}${text ? ` — ${text}` : ''}`
            );
        }

        // Some endpoints may return 204 in the future; handle safely.
        if (resp.status === 204) return undefined as T;
        return (await resp.json()) as T;
    } catch (err) {
        const name = (err as { name?: string } | null)?.name;
        if (name === 'AbortError') {
            throw new Error(`Request timed out after ${timeoutMs}ms`);
        }
        throw err;
    } finally {
        clearTimeout(timer);
    }
}

export async function listApps(fetchFn: FetchLike): Promise<AppsListResponse> {
    return getJson(fetchFn, buildUrl('/api/v1/apps'));
}

export async function createApp(fetchFn: FetchLike, req: CreateAppRequest): Promise<{ app: MindscapeApp }> {
    return getJson(fetchFn, buildUrl('/api/v1/apps'), {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(req)
    });
}

export async function patchApp(
    fetchFn: FetchLike,
    app_id: string,
    patch: PatchAppRequest
): Promise<{ app: MindscapeApp }> {
    return getJson(fetchFn, buildUrl(`/api/v1/apps/${encodeURIComponent(app_id)}`), {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(patch)
    });
}

export async function deleteApp(fetchFn: FetchLike, app_id: string): Promise<{ deleted: number; app_id: string }> {
    return getJson(fetchFn, buildUrl(`/api/v1/apps/${encodeURIComponent(app_id)}`), {
        method: 'DELETE'
    });
}