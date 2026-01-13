<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    type Mem0Health = {
        status: "ok" | "degraded";
        mem0?: "available" | "unavailable";
        detail?: string;
    };

    const appId = $derived($page.url.searchParams.get("app_id") ?? undefined);

    let query = $state("");
    let health = $state<Mem0Health | null>(null);
    let memories = $state<any[]>([]);
    let results = $state<any[]>([]);
    let loading = $state(false);
    let error = $state<string | null>(null);

    function apiUrl(
        path: string,
        params?: Record<string, string | undefined>,
    ): string {
        // Avoid `window` so this stays SSR-safe. We only need pathname+search.
        const url = new URL(path, "http://local");

        // Preserve current scope (app_id) for mem0 filtering
        const app_id = appId;
        if (app_id) url.searchParams.set("app_id", app_id);

        if (params) {
            for (const [k, v] of Object.entries(params)) {
                if (v === undefined || v === "") continue;
                url.searchParams.set(k, v);
            }
        }

        return url.pathname + url.search;
    }

    async function fetchJson(url: string): Promise<any> {
        const resp = await fetch(url, {
            headers: { Accept: "application/json" },
        });
        const text = await resp.text();

        let data: any;
        try {
            data = text ? JSON.parse(text) : null;
        } catch {
            data = { detail: text };
        }

        if (!resp.ok) {
            const detail = data?.detail
                ? String(data.detail)
                : `HTTP ${resp.status}`;
            throw new Error(detail);
        }

        return data;
    }

    async function refreshHealth(): Promise<void> {
        error = null;
        try {
            health = await fetchJson(apiUrl("/api/v1/mem0/health"));
        } catch (e) {
            health = {
                status: "degraded",
                mem0: "unavailable",
                detail: String(e),
            };
        }
    }

    async function listMemories(): Promise<void> {
        loading = true;
        error = null;
        results = [];
        try {
            const data = await fetchJson(
                apiUrl("/api/v1/mem0/memories", { limit: "50" }),
            );
            memories = Array.isArray(data?.memories) ? data.memories : [];
        } catch (e) {
            memories = [];
            error = String(e);
        } finally {
            loading = false;
        }
    }

    async function search(): Promise<void> {
        if (!query.trim()) return;

        loading = true;
        error = null;
        try {
            const data = await fetchJson(
                apiUrl("/api/v1/mem0/search", { q: query.trim(), limit: "10" }),
            );
            results = Array.isArray(data?.results) ? data.results : [];
        } catch (e) {
            results = [];
            error = String(e);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        // Initial load in browser only (avoid SSR fetch + keep window-free anyway)
        void refreshHealth();
    });
</script>

<svelte:head>
    <title>Mem0</title>
</svelte:head>

<main class="page-container">
    <header class="page-header">
        <div>
            <h1 class="page-title">Mem0</h1>
            <p class="page-subtitle">
                User memory operations via <code>/api/v1/mem0</code>. Reads are
                always enabled; writes are gated by
                <code>MINDSCAPE_MEM0_WRITE=true</code>.
            </p>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-2">
            <button class="btn" onclick={refreshHealth} disabled={loading}>
                Refresh status
            </button>
            <button class="btn" onclick={listMemories} disabled={loading}>
                List memories
            </button>
        </div>
    </header>

    <section class="card">
        <h2 class="card-title">Current scope</h2>

        <div class="mt-2 text-sm text-gray-200">
            app_id:
            <code
                class="rounded bg-white/5 px-1.5 py-0.5 text-xs text-gray-300"
            >
                {appId ?? "(none)"}
            </code>
        </div>

        <div class="mt-3 text-sm text-gray-200">
            Status:
            {#if health}
                <code
                    class="rounded bg-white/5 px-1.5 py-0.5 text-xs text-gray-300"
                >
                    {health.status}{health.mem0 ? ` (${health.mem0})` : ""}
                </code>
                {#if health.detail}
                    <div class="mt-2 text-xs text-gray-300/80">
                        {health.detail}
                    </div>
                {/if}
            {:else}
                <span class="text-gray-300/80">Loading…</span>
            {/if}
        </div>

        {#if error}
            <div
                class="mt-4 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-100"
            >
                {error}
            </div>
        {/if}
    </section>

    <section class="card mt-6">
        <h2 class="card-title">Search</h2>

        <div class="mt-3 flex flex-wrap items-center gap-2">
            <input
                class="w-full max-w-xl rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                placeholder="Search memories…"
                bind:value={query}
                onkeydown={(e) => e.key === "Enter" && void search()}
            />
            <button
                class="btn"
                onclick={search}
                disabled={loading || !query.trim()}
            >
                Search
            </button>
        </div>

        {#if results.length}
            <div class="mt-4 text-sm text-gray-200">
                Results ({results.length})
            </div>
            <ul class="mt-2 space-y-2">
                {#each results as r, i (r.id ?? r.memory_id ?? r._id ?? i)}
                    <li
                        class="rounded bg-white/5 px-3 py-2 text-sm text-gray-200"
                    >
                        <div class="text-xs text-gray-300/80">
                            id: {r.id ?? r.memory_id ?? r._id ?? "(unknown)"}
                        </div>
                        <pre
                            class="mt-1 whitespace-pre-wrap text-xs text-gray-200">{JSON.stringify(
                                r,
                                null,
                                2,
                            )}</pre>
                    </li>
                {/each}
            </ul>
        {:else if !loading && query.trim()}
            <div class="mt-4 text-sm text-gray-300/80">No results.</div>
        {/if}
    </section>

    <section class="card mt-6">
        <h2 class="card-title">Memories</h2>

        {#if loading}
            <div class="mt-3 text-sm text-gray-300/80">Loading…</div>
        {:else if memories.length}
            <div class="mt-3 text-sm text-gray-200">
                Items ({memories.length})
            </div>
            <ul class="mt-2 space-y-2">
                {#each memories as m, i (m.id ?? m.memory_id ?? m._id ?? i)}
                    <li
                        class="rounded bg-white/5 px-3 py-2 text-sm text-gray-200"
                    >
                        <div class="text-xs text-gray-300/80">
                            id: {m.id ?? m.memory_id ?? m._id ?? "(unknown)"}
                        </div>
                        <pre
                            class="mt-1 whitespace-pre-wrap text-xs text-gray-200">{JSON.stringify(
                                m,
                                null,
                                2,
                            )}</pre>
                    </li>
                {/each}
            </ul>
        {:else}
            <div class="mt-3 text-sm text-gray-300/80">
                Click <span class="font-medium text-gray-200"
                    >List memories</span
                >
                to load items. If you see “mem0 SDK not available”, install the backend
                extra:
                <code
                    class="rounded bg-white/5 px-1.5 py-0.5 text-xs text-gray-300"
                    >uv sync --extra mem0 --extra web</code
                >.
            </div>
        {/if}
    </section>
</main>
