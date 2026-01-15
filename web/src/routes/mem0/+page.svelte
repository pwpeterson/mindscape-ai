<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import {
        mem0Health,
        mem0ListMemories,
        mem0Search,
        type Mem0HealthResponse,
        type Mem0Memory,
    } from "$lib/api/mem0";

    const scopedAppId = $derived(
        $page.url.searchParams.get("app_id") ?? undefined,
    );

    // Filters
    let userId = $state("");
    let appIdFilter = $state("");
    let projectId = $state("");

    // Search
    let query = $state("");

    // Data
    let health = $state<Mem0HealthResponse | null>(null);
    let memories = $state<Mem0Memory[]>([]);
    let results = $state<Mem0Memory[]>([]);

    // UI state
    let loading = $state(false);
    let error = $state<string | null>(null);

    function effectiveAppId(): string | null {
        // Prefer explicit filter, fall back to URL scope.
        const v = appIdFilter.trim();
        if (v) return v;
        if (scopedAppId && scopedAppId.trim()) return scopedAppId.trim();
        return null;
    }

    function effectiveUserId(): string | null {
        const v = userId.trim();
        return v ? v : null;
    }

    function effectiveProjectId(): string | null {
        const v = projectId.trim();
        return v ? v : null;
    }

    function memoryId(m: Mem0Memory): string {
        const id = (m.id ?? m.memory_id ?? m._id) as unknown;
        return typeof id === "string" && id.trim() ? id : "(unknown)";
    }

    function memoryText(m: Mem0Memory): string {
        const v = (m.memory ?? m.content) as unknown;
        return typeof v === "string" ? v : JSON.stringify(v ?? "", null, 2);
    }

    function memoryScore(m: Mem0Memory): number | null {
        const s = (m.score ?? m.similarity) as unknown;
        if (typeof s === "number" && Number.isFinite(s)) return s;
        return null;
    }

    function memoryMetadata(m: Mem0Memory): Record<string, unknown> {
        const meta = m.metadata as unknown;
        if (meta && typeof meta === "object" && !Array.isArray(meta)) {
            return meta as Record<string, unknown>;
        }
        return {};
    }

    async function refreshHealth(): Promise<void> {
        error = null;
        try {
            health = await mem0Health(fetch);
        } catch (e) {
            health = {
                status: "degraded",
                mem0: "unavailable",
                detail: e instanceof Error ? e.message : String(e),
            };
        }
    }

    async function listMemories(): Promise<void> {
        loading = true;
        error = null;
        results = [];

        try {
            const data = await mem0ListMemories(fetch, {
                user_id: effectiveUserId(),
                app_id: effectiveAppId(),
                project_id: effectiveProjectId(),
                limit: 200,
            });
            memories = Array.isArray(data?.memories) ? data.memories : [];
        } catch (e) {
            memories = [];
            error = e instanceof Error ? e.message : String(e);
        } finally {
            loading = false;
        }
    }

    async function search(): Promise<void> {
        if (!query.trim()) return;

        loading = true;
        error = null;

        try {
            const data = await mem0Search(fetch, {
                q: query.trim(),
                user_id: effectiveUserId(),
                app_id: effectiveAppId(),
                project_id: effectiveProjectId(),
                limit: 25,
            });
            results = Array.isArray(data?.results) ? data.results : [];
        } catch (e) {
            results = [];
            error = e instanceof Error ? e.message : String(e);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        // Default the filter app_id to the URL-scoped app_id (if present).
        if (!appIdFilter.trim() && scopedAppId) {
            appIdFilter = scopedAppId;
        }

        // Initial load in browser only (avoid SSR fetch).
        void refreshHealth();
    });
</script>

<svelte:head>
    <title>Mem0</title>
</svelte:head>

<div>
    <section class="card">
        <div class="flex flex-wrap items-start justify-between gap-3">
            <h2 class="card-title">Filters</h2>

            <div class="flex flex-wrap items-center gap-2">
                <button class="btn" onclick={refreshHealth} disabled={loading}>
                    Refresh status
                </button>
                <button class="btn" onclick={listMemories} disabled={loading}>
                    List memories
                </button>
            </div>
        </div>

        <div class="mt-2 text-sm text-gray-200">
            URL scope app_id:
            <code
                class="rounded bg-white/5 px-1.5 py-0.5 text-xs text-gray-300"
            >
                {scopedAppId ?? "(none)"}
            </code>
        </div>

        <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
            <div>
                <label class="text-xs text-gray-300/80" for="mem0-user-id"
                    >user_id</label
                >
                <input
                    id="mem0-user-id"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    placeholder="default"
                    bind:value={userId}
                />
                <div class="mt-1 text-xs text-gray-300/70">
                    Blank uses <code>MEM0_DEFAULT_USER_ID</code> (default:
                    <code>default</code>).
                </div>
            </div>

            <div>
                <label class="text-xs text-gray-300/80" for="mem0-app-id"
                    >app_id</label
                >
                <input
                    id="mem0-app-id"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    placeholder={scopedAppId ?? "mindscape-ai"}
                    bind:value={appIdFilter}
                />
                <div class="mt-1 text-xs text-gray-300/70">
                    Blank falls back to URL scope (if set).
                </div>
            </div>

            <div>
                <label class="text-xs text-gray-300/80" for="mem0-project-id"
                    >project_id</label
                >
                <input
                    id="mem0-project-id"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    placeholder="(optional)"
                    bind:value={projectId}
                />
            </div>
        </div>

        <div class="mt-4 text-sm text-gray-200">
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

            <div class="mt-3 overflow-x-auto">
                <table class="w-full text-left text-sm">
                    <thead class="text-xs text-gray-300/80">
                        <tr class="border-b border-white/10">
                            <th class="py-2 pr-3">id</th>
                            <th class="py-2 pr-3">score</th>
                            <th class="py-2 pr-3">app_id</th>
                            <th class="py-2 pr-3">project_id</th>
                            <th class="py-2 pr-3">content</th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each results as r, i (r.id ?? r.memory_id ?? r._id ?? i)}
                            {@const meta = memoryMetadata(r)}
                            <tr class="border-b border-white/10 align-top">
                                <td class="py-3 pr-3 font-mono text-xs"
                                    >{memoryId(r)}</td
                                >
                                <td class="py-3 pr-3 font-mono text-xs">
                                    {#if memoryScore(r) !== null}
                                        {memoryScore(r)}
                                    {:else}
                                        <span class="text-gray-300/60">—</span>
                                    {/if}
                                </td>
                                <td class="py-3 pr-3 font-mono text-xs"
                                    >{String(meta.app_id ?? "")}</td
                                >
                                <td class="py-3 pr-3 font-mono text-xs"
                                    >{String(meta.project_id ?? "")}</td
                                >
                                <td class="py-3 pr-3">
                                    <pre
                                        class="whitespace-pre-wrap text-xs text-gray-200">{memoryText(
                                            r,
                                        )}</pre>
                                    {#if Object.keys(meta).length}
                                        <details class="mt-2">
                                            <summary
                                                class="cursor-pointer text-xs text-gray-300/80"
                                                >metadata</summary
                                            >
                                            <pre
                                                class="mt-1 whitespace-pre-wrap text-xs text-gray-300/80">{JSON.stringify(
                                                    meta,
                                                    null,
                                                    2,
                                                )}</pre>
                                        </details>
                                    {/if}
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
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

            <div class="mt-3 overflow-x-auto">
                <table class="w-full text-left text-sm">
                    <thead class="text-xs text-gray-300/80">
                        <tr class="border-b border-white/10">
                            <th class="py-2 pr-3">id</th>
                            <th class="py-2 pr-3">app_id</th>
                            <th class="py-2 pr-3">project_id</th>
                            <th class="py-2 pr-3">content</th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each memories as m, i (m.id ?? m.memory_id ?? m._id ?? i)}
                            {@const meta = memoryMetadata(m)}
                            <tr class="border-b border-white/10 align-top">
                                <td class="py-3 pr-3 font-mono text-xs"
                                    >{memoryId(m)}</td
                                >
                                <td class="py-3 pr-3 font-mono text-xs"
                                    >{String(meta.app_id ?? "")}</td
                                >
                                <td class="py-3 pr-3 font-mono text-xs"
                                    >{String(meta.project_id ?? "")}</td
                                >
                                <td class="py-3 pr-3">
                                    <pre
                                        class="whitespace-pre-wrap text-xs text-gray-200">{memoryText(
                                            m,
                                        )}</pre>
                                    {#if Object.keys(meta).length}
                                        <details class="mt-2">
                                            <summary
                                                class="cursor-pointer text-xs text-gray-300/80"
                                                >metadata</summary
                                            >
                                            <pre
                                                class="mt-1 whitespace-pre-wrap text-xs text-gray-300/80">{JSON.stringify(
                                                    meta,
                                                    null,
                                                    2,
                                                )}</pre>
                                        </details>
                                    {/if}
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
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
</div>
