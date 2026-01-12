<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import type { ConportViewsListResponse } from "$lib/api/conport";
    import { conportViewsList } from "$lib/api/conport";

    let limit = $state<number>(50);

    let loading = $state(true);
    let error = $state<string | null>(null);
    let views = $state<ConportViewsListResponse["views"]>([]);
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
            const resp: ConportViewsListResponse = await conportViewsList(
                fetch,
                { limit, db },
            );
            dbResolved = resp.db;
            views = resp.views;
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
    <title>ConPort • Views</title>
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
    {:else if views.length === 0}
        <p style="opacity: 0.7;">No views found.</p>
    {:else}
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr>
                    <th
                        style="text-align: left; padding: 6px 0; border-bottom: 1px solid #eee;"
                        >Key</th
                    >
                    <th
                        style="text-align: left; padding: 6px 0; border-bottom: 1px solid #eee;"
                        >Value (preview)</th
                    >
                    <th
                        style="text-align: left; padding: 6px 0; border-bottom: 1px solid #eee;"
                        >Timestamp</th
                    >
                </tr>
            </thead>
            <tbody>
                {#each views as v (v.id)}
                    <tr>
                        <td
                            style="padding: 8px 0; border-bottom: 1px solid #f3f4f6;"
                        >
                            <div style="font-weight: 600;">
                                <a
                                    href={withDb(
                                        `/conport/item?type=custom_data&id=${v.id}`,
                                    )}
                                    style="text-decoration: none;"
                                >
                                    {v.key}
                                </a>
                            </div>
                            <div style="font-size: 12px; opacity: 0.75;">
                                id={v.id}
                            </div>
                        </td>
                        <td
                            style="padding: 8px 0; border-bottom: 1px solid #f3f4f6; font-size: 12px;"
                        >
                            <code style="white-space: pre-wrap;"
                                >{JSON.stringify(v.value)}</code
                            >
                        </td>
                        <td
                            style="padding: 8px 0; border-bottom: 1px solid #f3f4f6; font-size: 12px; opacity: 0.8;"
                        >
                            {v.timestamp}
                        </td>
                    </tr>
                {/each}
            </tbody>
        </table>
    {/if}
</main>
