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

<main
    style="max-width: 1100px; margin: 0 auto; padding: 24px; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;"
>
    <header
        style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px;"
    >
        <div>
            <h1 style="margin: 0; font-size: 24px;">
                ConPort — System Patterns
            </h1>
            <p style="margin: 6px 0 0; opacity: 0.8;">
                Browse system/coding patterns (newest first).
            </p>
            {#if dbResolved}
                <div
                    style="margin-top: 6px; font-size: 12px; opacity: 0.7; word-break: break-all;"
                >
                    DB: <code>{dbResolved}</code>
                </div>
            {/if}
        </div>
        <button
            onclick={() => refresh()}
            disabled={loading}
            style="padding: 8px 12px; border: 1px solid #ccc; border-radius: 8px; background: white; cursor: pointer;"
        >
            {loading ? "Loading…" : "Refresh"}
        </button>
    </header>

    <form
        onsubmit={(e) => {
            e.preventDefault();
            persistFiltersToUrl();
            void refresh();
        }}
        style="display: flex; gap: 10px; align-items: end; margin-bottom: 16px; flex-wrap: wrap;"
    >
        <label style="display: grid; gap: 6px;">
            <span style="font-size: 12px; opacity: 0.8;">Limit</span>
            <input
                type="number"
                min="1"
                max="500"
                bind:value={limit}
                style="padding: 8px 10px; border: 1px solid #ccc; border-radius: 8px; width: 110px;"
            />
        </label>

        <button
            type="submit"
            disabled={loading}
            style="padding: 8px 12px; border: 1px solid #ccc; border-radius: 8px; background: white; cursor: pointer;"
        >
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
