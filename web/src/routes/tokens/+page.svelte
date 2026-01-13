<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import {
        tokensBreakdown,
        type TokensBreakdownResponse,
    } from "$lib/api/tokens";

    const scopedAppId = $derived($page.url.searchParams.get("app_id") ?? undefined);

    // Filters
    let userId = $state("");
    let projectId = $state("");
    let appIdOverride = $state("");

    // Data
    let breakdown = $state<TokensBreakdownResponse | null>(null);
    let loading = $state(false);
    let error = $state<string | null>(null);

    function effectiveAppId(): string | null {
        const v = appIdOverride.trim();
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

    function fmt(n: number | null | undefined): string {
        if (typeof n !== "number" || !Number.isFinite(n)) return "—";
        return n.toLocaleString();
    }

    async function refresh(): Promise<void> {
        loading = true;
        error = null;
        try {
            breakdown = await tokensBreakdown(fetch, {
                app_id: effectiveAppId(),
                user_id: effectiveUserId(),
                project_id: effectiveProjectId(),
            });
        } catch (e) {
            breakdown = null;
            error = e instanceof Error ? e.message : String(e);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        if (!appIdOverride.trim() && scopedAppId) {
            appIdOverride = scopedAppId;
        }
        void refresh();
    });
</script>

<svelte:head>
    <title>Tokens</title>
</svelte:head>

<main class="page-container">
    <header class="page-header">
        <div>
            <h1 class="page-title">Token analytics</h1>
            <p class="page-subtitle">
                Unified approximate token breakdown across ConPort, Prompts, and Mem0.
                Estimator: <code>chars/4</code>.
            </p>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-2">
            <button class="btn" onclick={refresh} disabled={loading}>
                {loading ? "Loading…" : "Refresh"}
            </button>
        </div>
    </header>

    <section class="card">
        <h2 class="card-title">Filters</h2>

        <div class="mt-2 text-sm text-gray-200">
            URL scope app_id:
            <code class="rounded bg-white/5 px-1.5 py-0.5 text-xs text-gray-300">
                {scopedAppId ?? "(none)"}
            </code>
        </div>

        <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
            <div>
                <label class="text-xs text-gray-300/80" for="tokens-app-id">app_id</label>
                <input
                    id="tokens-app-id"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    placeholder={scopedAppId ?? "mindscape-ai"}
                    bind:value={appIdOverride}
                />
                <div class="mt-1 text-xs text-gray-300/70">
                    Blank falls back to URL scope (if set).
                </div>
            </div>

            <div>
                <label class="text-xs text-gray-300/80" for="tokens-user-id">user_id</label>
                <input
                    id="tokens-user-id"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    placeholder="default"
                    bind:value={userId}
                />
                <div class="mt-1 text-xs text-gray-300/70">
                    Blank uses <code>MEM0_DEFAULT_USER_ID</code>.
                </div>
            </div>

            <div>
                <label class="text-xs text-gray-300/80" for="tokens-project-id">project_id</label>
                <input
                    id="tokens-project-id"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    placeholder="(optional)"
                    bind:value={projectId}
                />
            </div>
        </div>

        {#if error}
            <div class="mt-4 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-100">
                {error}
            </div>
        {/if}
    </section>

    <section class="card mt-6">
        <h2 class="card-title">Total</h2>

        {#if breakdown}
            <div class="mt-2 text-sm text-gray-200">
                Approx tokens:
                <span class="ml-2 font-mono text-base text-gray-100">
                    {fmt(breakdown.total.approx_tokens)}
                </span>
            </div>
        {:else if loading}
            <div class="mt-2 text-sm text-gray-300/80">Loading…</div>
        {:else}
            <div class="mt-2 text-sm text-gray-300/80">No data.</div>
        {/if}
    </section>

    <section class="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div class="card">
            <h2 class="card-title">ConPort</h2>
            {#if breakdown}
                {@const s = breakdown.sources.conport}
                <div class="mt-2 text-sm text-gray-200">
                    configured:
                    <code class="rounded bg-white/5 px-1.5 py-0.5 text-xs text-gray-300">{String(s.configured)}</code>
                </div>
                <div class="mt-2 text-sm text-gray-200">chars: <span class="font-mono">{fmt(s.chars)}</span></div>
                <div class="mt-2 text-sm text-gray-200">approx_tokens: <span class="font-mono">{fmt(s.approx_tokens)}</span></div>
                {#if s.db}
                    <div class="mt-2 text-xs text-gray-300/70">db: <code>{s.db}</code></div>
                {/if}
                {#if s.error}
                    <div class="mt-3 text-xs text-red-200/90 whitespace-pre-wrap">{s.error}</div>
                {/if}
            {:else}
                <div class="mt-2 text-sm text-gray-300/80">—</div>
            {/if}
        </div>

        <div class="card">
            <h2 class="card-title">Prompts</h2>
            {#if breakdown}
                {@const s = breakdown.sources.prompts}
                <div class="mt-2 text-sm text-gray-200">
                    configured:
                    <code class="rounded bg-white/5 px-1.5 py-0.5 text-xs text-gray-300">{String(s.configured)}</code>
                </div>
                <div class="mt-2 text-sm text-gray-200">files: <span class="font-mono">{fmt(s.file_count ?? 0)}</span></div>
                <div class="mt-2 text-sm text-gray-200">chars: <span class="font-mono">{fmt(s.chars)}</span></div>
                <div class="mt-2 text-sm text-gray-200">approx_tokens: <span class="font-mono">{fmt(s.approx_tokens)}</span></div>
                {#if s.error}
                    <div class="mt-3 text-xs text-red-200/90 whitespace-pre-wrap">{s.error}</div>
                {/if}
            {:else}
                <div class="mt-2 text-sm text-gray-300/80">—</div>
            {/if}
        </div>

        <div class="card">
            <h2 class="card-title">Mem0</h2>
            {#if breakdown}
                {@const s = breakdown.sources.mem0}
                <div class="mt-2 text-sm text-gray-200">
                    configured:
                    <code class="rounded bg-white/5 px-1.5 py-0.5 text-xs text-gray-300">{String(s.configured)}</code>
                </div>
                <div class="mt-2 text-sm text-gray-200">items: <span class="font-mono">{fmt(s.item_count ?? 0)}</span></div>
                <div class="mt-2 text-sm text-gray-200">chars: <span class="font-mono">{fmt(s.chars)}</span></div>
                <div class="mt-2 text-sm text-gray-200">approx_tokens: <span class="font-mono">{fmt(s.approx_tokens)}</span></div>
                {#if s.error}
                    <div class="mt-3 text-xs text-red-200/90 whitespace-pre-wrap">{s.error}</div>
                {/if}
            {:else}
                <div class="mt-2 text-sm text-gray-300/80">—</div>
            {/if}
        </div>
    </section>
</main>
