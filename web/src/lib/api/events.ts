import { browser } from "$app/environment";
import { env } from "$env/dynamic/public";

export type EventsStreamHello = {
    type: "hello";
    ts: string;
    data: {
        service: string;
        protocol: string;
    };
};

export type EventsStreamHeartbeat = {
    type: "heartbeat";
    ts: string;
    data: Record<string, never>;
};

export type EventsStreamEvent = EventsStreamHello | EventsStreamHeartbeat;

export type EventsStreamHandlers = {
    onHello?: (event: EventsStreamHello) => void;
    onHeartbeat?: (event: EventsStreamHeartbeat) => void;
    onError?: (event: Event) => void;
    onOpen?: () => void;
};

/**
 * Build a URL for the SSE events stream.
 *
 * IMPORTANT:
 * Never use an absolute base in the browser; it breaks remote access scenarios
 * where 127.0.0.1 refers to the client machine (not the server running containers).
 * Prefer same-origin "/api/*" so SvelteKit can reverse-proxy server-side.
 */
export function eventsStreamUrl(
    opts: {
        db?: string | null;
        heartbeat_seconds?: number | null;
    } = {},
): string {
    const configured = env.PUBLIC_MINDSCAPE_API_BASE?.trim();
    const base = browser ? "" : configured ? configured.replace(/\/$/, "") : "";
    const path = "/api/v1/events/stream";

    const params = new URLSearchParams();
    if (opts.db) params.set("db", opts.db);
    if (opts.heartbeat_seconds != null)
        params.set("heartbeat_seconds", String(opts.heartbeat_seconds));

    const qs = params.toString();
    if (base) return `${base}${path}${qs ? `?${qs}` : ""}`;

    // Same-origin relative path.
    return `${path}${qs ? `?${qs}` : ""}`;
}

export type EventsStreamConnection = {
    close: () => void;
};

/**
 * Open an EventSource connection to the backend events stream.
 *
 * Note: EventSource is browser-only; call this inside onMount().
 */
export function connectEventsStream(
    handlers: EventsStreamHandlers,
    opts: { db?: string | null; heartbeat_seconds?: number | null } = {},
): EventsStreamConnection {
    const url = eventsStreamUrl(opts);
    const es = new EventSource(url);

    const onOpen = () => handlers.onOpen?.();
    const onError = (event: Event) => handlers.onError?.(event);

    es.addEventListener("open", onOpen);
    es.addEventListener("error", onError);

    es.addEventListener("hello", (ev: MessageEvent) => {
        try {
            handlers.onHello?.(JSON.parse(ev.data) as EventsStreamHello);
        } catch {
            // ignore malformed events
        }
    });

    es.addEventListener("heartbeat", (ev: MessageEvent) => {
        try {
            handlers.onHeartbeat?.(JSON.parse(ev.data) as EventsStreamHeartbeat);
        } catch {
            // ignore malformed events
        }
    });

    return {
        close: () => {
            es.close();
        },
    };
}