<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import type {
        ConportCustomData,
        ConportCustomDataListResponse,
    } from "$lib/api/conport";
    import { conportCustomDataList } from "$lib/api/conport";

    let category = $state<string>("");
    let key = $state<string>("");
    let limit = $state<number>(50);

    let loading = $state(true);
    let error = $state<string | null>(null);
    let data = $state<ConportCustomData[]>([]);
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

        const c = category.trim();
        const k = key.trim();

        if (c) u.searchParams.set("category", c);
        else u.searchParams.delete("category");

        if (k) u.searchParams.set("key", k);
        else u.searchParams.delete("key");

        u.searchParams.set("limit", String(limit));

        window.history.replaceState({}, "", u);
    }

    async function refresh() {
        loading = true;
        error = null;

        try {
            const db = $page.url.searchParams.get("db");
            const resp: ConportCustomDataListResponse =
                await conportCustomDataList(fetch, {
                    category: category.trim() || null,
                    key: key.trim() || null,
                    limit,
                    db,
                });
            dbResolved = resp.db;
            data = resp.custom_data;
        } catch (err) {
            error = err instanceof Error ? err.message : String(err);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        // Prefill filters from query string when present.
        const params = $page.url.searchParams;
        const c = params.get("category");
        const k = params.get("key");
        const rawLimit = params.get("limit");

        if (c) category = c;
        if (k) key = k;
        if (rawLimit) {
            const n = Number(rawLimit);
            if (Number.isFinite(n) && n >= 1 && n <= 500) limit = n;
        }

        void refresh();
    });
</script>

<svelte:head>
    <title>ConPort • Custom Data</title>
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
        class="mb-6 grid gap-4 md:grid-cols-3"
    >
        <label class="field">
            <span class="field-label">Category (optional)</span>
            <input bind:value={category} class="input" />
        </label>

        <label class="field">
            <span class="field-label">Key (optional)</span>
            <input bind:value={key} class="input" />
        </label>

        <div class="flex flex-wrap items-end gap-3">
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
        </div>
    </form>

    {#if error}
        <div
            class="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-100"
        >
            <div class="text-sm font-semibold">Error</div>
            <div class="mt-2 whitespace-pre-wrap text-sm text-red-100/90">
                {error}
            </div>
        </div>
    {:else if loading}
        <p class="text-sm text-gray-300">Loading…</p>
    {:else if data.length === 0}
        <p class="text-sm text-gray-300">No custom data found.</p>
    {:else}
        <div class="overflow-x-auto rounded-xl border border-white/10">
            <table class="table">
                <thead>
                    <tr>
                        <th>Category / Key</th>
                        <th>Value (preview)</th>
                        <th>Timestamp</th>
                    </tr>
                </thead>
                <tbody>
                    {#each data as c (c.id)}
                        <tr>
                            <td>
                                <div class="font-medium text-gray-100">
                                    <a
                                        href={withDb(
                                            `/conport/item?type=custom_data&id=${c.id}`,
                                        )}
                                        class="hover:underline underline-offset-2"
                                    >
                                        {c.category} / {c.key}
                                    </a>
                                </div>
                                <div class="mt-1 text-xs text-gray-400">
                                    id={c.id}
                                </div>
                            </td>

                            <td class="text-xs">
                                <code
                                    class="block whitespace-pre-wrap break-words text-gray-200"
                                    >{JSON.stringify(c.value)}</code
                                >
                            </td>

                            <td class="text-xs text-gray-400">{c.timestamp}</td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        </div>
    {/if}
</main>
