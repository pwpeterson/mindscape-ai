<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import type {
        ConportSystemPattern,
        ConportSystemPatternsListResponse,
    } from "$lib/api/conport";
    import { conportSystemPatternsList } from "$lib/api/conport";

    let limit = $state<number>(50);

    let loading = $state(true);
    let error = $state<string | null>(null);
    let patterns = $state<ConportSystemPattern[]>([]);
    let dbResolved = $state<string>("");

    function withDb(url: string): string {
        const db = $page.url.searchParams.get("db");
        if (!db) return url;
        const u = new URL(url, "http://local");
        u.searchParams.set("db", db);
        return u.pathname + u.search;
    }

    function persistFiltersToUrl(): void {
        if (typeof window === "undefined") return;
        const u = new URL(window.location.href);
        u.searchParams.set("limit", String(limit));
        window.history.replaceState({}, "", u);
    }

    async function refresh() {
        loading = true;
        error = null;

        try {
            const db = $page.url.searchParams.get("db");
            const resp: ConportSystemPatternsListResponse =
                await conportSystemPatternsList(fetch, { limit, db });
            dbResolved = resp.db;
            patterns = resp.system_patterns;
        } catch (err) {
            error = err instanceof Error ? err.message : String(err);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        const rawLimit = $page.url.searchParams.get("limit");
        if (rawLimit) {
            const n = Number(rawLimit);
            if (Number.isFinite(n) && n >= 1 && n <= 500) limit = n;
        }
        void refresh();
    });
</script>

<svelte:head>
    <title>ConPort • System Patterns</title>
</svelte:head>

<main class="page-container">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        {#if dbResolved}
            <div class="break-all text-xs text-gray-400">
                DB: <code>{dbResolved}</code>
            </div>
        {/if}

        <button
            onclick={() => refresh()}
            disabled={loading}
            class="btn btn-primary"
        >
            {loading ? "Loading…" : "Refresh"}
        </button>
    </div>

    <form
        onsubmit={(e) => {
            e.preventDefault();
            persistFiltersToUrl();
            void refresh();
        }}
        class="form-row mb-6"
    >
        <label class="field w-[140px]">
            <span class="field-label">Limit</span>
            <input
                type="number"
                min="1"
                max="500"
                bind:value={limit}
                class="input"
            />
        </label>

        <button type="submit" disabled={loading} class="btn">
            {loading ? "Loading…" : "Apply"}
        </button>
    </form>

    {#if error}
        <div
            style="padding: 12px; border: 1px solid #f5c2c7; background: #f8d7da; color: #842029; border-radius: 8px;"
        >
            <strong>Error</strong>
            <div style="margin-top: 6px; white-space: pre-wrap;">{error}</div>
        </div>
    {:else if loading}
        <p>Loading…</p>
    {:else if patterns.length === 0}
        <p style="opacity: 0.7;">No patterns found.</p>
    {:else}
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr>
                    <th
                        style="text-align: left; padding: 6px 0; border-bottom: 1px solid #eee;"
                        >Name</th
                    >
                    <th
                        style="text-align: left; padding: 6px 0; border-bottom: 1px solid #eee;"
                        >Description</th
                    >
                    <th
                        style="text-align: left; padding: 6px 0; border-bottom: 1px solid #eee;"
                        >Timestamp</th
                    >
                </tr>
            </thead>
            <tbody>
                {#each patterns as p (p.id)}
                    <tr>
                        <td
                            style="padding: 8px 0; border-bottom: 1px solid #f3f4f6;"
                        >
                            <div style="font-weight: 600;">
                                <a
                                    href={withDb(
                                        `/conport/item?type=system_pattern&id=${p.id}`,
                                    )}
                                    style="text-decoration: none;"
                                >
                                    {p.name}
                                </a>
                            </div>
                            <div style="font-size: 12px; opacity: 0.75;">
                                id={p.id}
                            </div>
                        </td>
                        <td
                            style="padding: 8px 0; border-bottom: 1px solid #f3f4f6; font-size: 12px;"
                        >
                            {p.description ?? ""}
                        </td>
                        <td
                            style="padding: 8px 0; border-bottom: 1px solid #f3f4f6; font-size: 12px; opacity: 0.8;"
                        >
                            {p.timestamp}
                        </td>
                    </tr>
                {/each}
            </tbody>
        </table>
    {/if}
</main>
