import { env } from '$env/dynamic/private';
import type { Handle } from '@sveltejs/kit';

/**
 * Reverse-proxy /api/* requests from the SvelteKit server to the Mindscape API.
 *
 * Why:
 * - Avoids browser CORS issues (same-origin from the browser’s perspective)
 * - Avoids "127.0.0.1" pitfalls when UI is accessed remotely
 * - Supports streaming endpoints (SSE/stream responses)
 *
 * Configure:
 * - MINDSCAPE_API_INTERNAL_BASE=http://host.containers.internal:8011  (works without container DNS)
 * - MINDSCAPE_API_INTERNAL_BASE=http://mindscape-ai-api:8000          (only if containers share DNS/network)
 */
const DEFAULT_INTERNAL_BASE = 'http://host.containers.internal:8011';

function getInternalBase(): string {
    const base = (env.MINDSCAPE_API_INTERNAL_BASE ?? DEFAULT_INTERNAL_BASE).trim();
    return base.replace(/\/$/, '');
}

function hasDotSegments(pathname: string): boolean {
    // Prevent path traversal via dot-segments, e.g. "/api/../tokens/breakdown"
    // which can bypass a naive prefix check after URL normalization.
    return pathname.split('/').some((seg) => seg === '.' || seg === '..');
}

export const handle: Handle = async ({ event, resolve }) => {
    if (!event.url.pathname.startsWith('/api/')) {
        return resolve(event);
    }

    if (hasDotSegments(event.url.pathname)) {
        return new Response('Bad Request: invalid path', {
            status: 400,
            headers: { 'content-type': 'text/plain; charset=utf-8' }
        });
    }

    const base = getInternalBase();

    // Build via URL base resolution to avoid string-concatenation quirks,
    // then re-validate the normalized upstream path stays under /api/.
    const upstreamUrl = new URL(`${event.url.pathname}${event.url.search}`, `${base}/`);
    if (!upstreamUrl.pathname.startsWith('/api/')) {
        return new Response('Bad Request: invalid path', {
            status: 400,
            headers: { 'content-type': 'text/plain; charset=utf-8' }
        });
    }

    // Forward the request to the upstream API. Use the original request as init
    // so method/headers/body are preserved.
    const upstreamRequest = new Request(upstreamUrl, event.request);

    let upstreamResponse: Response;
    try {
        upstreamResponse = await fetch(upstreamRequest);
    } catch (err) {
        // If the upstream is down/unreachable from the SvelteKit server, return a 502
        // instead of a generic "Failed to fetch" client-side.
        const message =
            err instanceof Error ? err.message : typeof err === 'string' ? err : 'Upstream request failed';
        return new Response(`Bad Gateway: ${message}`, {
            status: 502,
            headers: { 'content-type': 'text/plain; charset=utf-8' }
        });
    }

    // Clone headers to allow minor adjustments if needed.
    const headers = new Headers(upstreamResponse.headers);

    // Avoid leaking upstream internal details; optional, but safe.
    headers.delete('server');

    // Return streaming body as-is. This is important for SSE and "stream" endpoints.
    return new Response(upstreamResponse.body, {
        status: upstreamResponse.status,
        statusText: upstreamResponse.statusText,
        headers
    });
};