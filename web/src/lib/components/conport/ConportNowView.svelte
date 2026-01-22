<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import type {
        ConportNowResponse,
        ConportProgressEntry,
        ConportProgressListResponse,
        ConportCustomDataListResponse,
    } from "$lib/api/conport";
    import {
        conportNow,
        conportProgressList,
        conportCustomDataList,
    } from "$lib/api/conport";
    import { connectEventsStream } from "$lib/api/events";

    import type { ProgressEntryWithWbs, WbsMeta } from "$lib/types/progress";

    const PANEL_LIMIT = 50;
    const PREVIEW_LIMIT = 12;

    let loading = $state(true);
    let error = $state<string | null>(null);
    let data = $state<ConportNowResponse | null>(null);

    let todoEntries = $state<ProgressEntryWithWbs[]>([]);
    let inProgressEntries = $state<ProgressEntryWithWbs[]>([]);
    let doneEntries = $state<ProgressEntryWithWbs[]>([]);

    let wbsMetaMap = $state<Map<number, WbsMeta>>(new Map());

    const AUTO_REFRESH_MIN_INTERVAL_MS = 600_000; // 10 minutes
    let lastAutoRefreshAtMs = $state<number>(0);

    function maybeAutoRefresh() {
        if (loading) return;
        const now = Date.now();
        if (now - lastAutoRefreshAtMs < AUTO_REFRESH_MIN_INTERVAL_MS) return;
        lastAutoRefreshAtMs = now;
        void refresh();
    }

    function buildQuery(params: Record<string, string>): string {
        const sp = new URLSearchParams(params);

        const app_id = $page.url.searchParams.get("app_id");
        const db = $page.url.searchParams.get("db");

        if (app_id) {
            sp.set("app_id", app_id);
            sp.delete("db");
        } else if (db) {
            sp.set("db", db);
        }

        const qs = sp.toString();
        return qs ? `?${qs}` : "";
    }

    function progressItemHref(id: number): string {
        return `/conport/item${buildQuery({ type: "progress", id: String(id) })}`;
    }

    function progressHref(status: string | null = null): string {
        return `/conport/progress${buildQuery({ limit: String(PANEL_LIMIT), status: status ?? "" })}`;
    }

    function getTitle(entry: ProgressEntryWithWbs): string {
        return entry.wbs_meta?.title ?? stripPriorityPrefix(entry.description);
    }

    function stripPriorityPrefix(description: string): string {
        return description.replace(/^\s*\[p\d+\]\s*/i, "");
    }

    function displayDescription(description: string): string {
        return description.trim().replace(/^\[p\d+\]\s*/i, "");
    }

    function enrichEntriesWithWbs(
        entries: ConportProgressEntry[],
    ): ProgressEntryWithWbs[] {
        return entries.map((e) => ({
            ...e,
            wbs_meta: wbsMetaMap.get(e.id),
        }));
    }

    async function refresh() {
        loading = true;
        error = null;

        try {
            const app_id = $page.url.searchParams.get("app_id");
            const db = $page.url.searchParams.get("db");

            // Fetch WBS metadata first
            const wbsResp = await conportCustomDataList(fetch, {
                category: "wbs_meta",
                db,
            });

            wbsMetaMap.clear();
            for (const item of wbsResp.custom_data) {
                const match = item.key.match(/^progress:(\d+)$/);
                if (match) {
                    const progressId = Number(match[1]);
                    wbsMetaMap.set(progressId, item.value as WbsMeta);
                }
            }

            const [nowResp, todoResp, inProgressResp, doneResp] =
                await Promise.all([
                    conportNow(fetch, { app_id, db }),
                    conportProgressList(fetch, {
                        status: "TODO",
                        limit: PANEL_LIMIT,
                        app_id,
                        db,
                    }),
                    conportProgressList(fetch, {
                        status: "IN_PROGRESS",
                        limit: PANEL_LIMIT,
                        app_id,
                        db,
                    }),
                    conportProgressList(fetch, {
                        status: "DONE",
                        limit: PANEL_LIMIT,
                        app_id,
                        db,
                    }),
                ]);

            data = nowResp;
            todoEntries = enrichEntriesWithWbs(
                (todoResp as ConportProgressListResponse).progress_entries,
            );
            inProgressEntries = enrichEntriesWithWbs(
                (inProgressResp as ConportProgressListResponse)
                    .progress_entries,
            );
            doneEntries = enrichEntriesWithWbs(
                (doneResp as ConportProgressListResponse).progress_entries,
            );
        } catch (err) {
            error = err instanceof Error ? err.message : String(err);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        void refresh();

        // Auto-refresh disabled
        // const conn = connectEventsStream(
        //     {
        //         onHeartbeat: () => maybeAutoRefresh(),
        //     },
        //     { heartbeat_seconds: 15 },
        // );

        // return () => conn.close();
    });
</script>

<main class="page-container">
    <div class="mb-4 flex items-center justify-between gap-3">
        <div class="text-xs text-gray-500">
            {#if wbsMetaMap.size > 0}
                WBS v1.0 • {wbsMetaMap.size} records with metadata
            {/if}
        </div>
        <button
            onclick={() => refresh()}
            disabled={loading}
            class="btn btn-primary"
        >
            {loading ? "Loading…" : "Refresh"}
        </button>
    </div>

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
    {:else if data}
        <section class="flex gap-4 overflow-x-auto pb-1">
            <details class="card min-w-[260px] shrink-0" open>
                <summary
                    class="cursor-pointer list-none [&::-webkit-details-marker]:hidden"
                >
                    <div class="flex items-center justify-between gap-3">
                        <div class="card-title">Database</div>
                    </div>
                </summary>
                <div class="mt-2 break-all font-mono text-xs text-gray-300">
                    {data.db}
                </div>
            </details>

            <details class="card min-w-[280px] shrink-0" open>
                <summary
                    class="cursor-pointer list-none [&::-webkit-details-marker]:hidden"
                >
                    <div class="flex items-center justify-between gap-3">
                        <div class="card-title">Recent Activity (last 10)</div>
                    </div>
                </summary>
                <ul class="mt-3 list-disc space-y-1 pl-5 text-sm text-gray-200">
                    <li>Decisions: {data.recent_activity.decisions.length}</li>
                    <li>
                        Progress entries: {data.recent_activity.progress_entries
                            .length}
                    </li>
                    <li>
                        System patterns: {data.recent_activity.system_patterns
                            .length}
                    </li>
                    <li>
                        Custom data: {data.recent_activity.custom_data.length}
                    </li>
                    <li>Links: {data.recent_activity.links.length}</li>
                </ul>
            </details>

            <details class="card min-w-[520px] shrink-0" open>
                <summary
                    class="cursor-pointer list-none [&::-webkit-details-marker]:hidden"
                >
                    <div class="flex items-start justify-between gap-3">
                        <div>
                            <div class="card-title">Progress</div>
                            <div class="mt-1 text-xs text-gray-300/80">
                                Grouped by status (latest {PANEL_LIMIT} each).
                            </div>
                        </div>
                        <a
                            href={progressHref()}
                            class="text-xs text-gray-200/80 hover:text-gray-100 hover:underline"
                            onclick={(e) => e.stopPropagation()}
                        >
                            Open Progress
                        </a>
                    </div>
                </summary>

                <div class="mt-4 space-y-2">
                    <details
                        class="rounded-lg border border-white/10 bg-black/10 p-3"
                        open
                    >
                        <summary
                            class="cursor-pointer text-sm font-semibold text-gray-100"
                        >
                            <span class="inline-flex items-center gap-2">
                                <span
                                    class="inline-block h-2 w-2 rounded-full bg-emerald-400"
                                ></span>
                                IN PROGRESS ({inProgressEntries.length})
                            </span>
                        </summary>
                        {#if inProgressEntries.length === 0}
                            <p class="mt-2 text-xs text-gray-300/80">
                                No IN_PROGRESS tasks.
                            </p>
                        {:else}
                            <ul
                                class="mt-2 max-h-56 space-y-1 overflow-auto pr-1 text-xs text-gray-200"
                            >
                                {#each inProgressEntries.slice(0, PREVIEW_LIMIT) as e (e.id)}
                                    <li class="truncate">
                                        <a
                                            href={progressItemHref(e.id)}
                                            class="hover:underline"
                                        >
                                            {getTitle(e)}
                                        </a>
                                        {#if e.wbs_meta?.priority}
                                            <span class="ml-1 opacity-60">
                                                [{e.wbs_meta.priority}]
                                            </span>
                                        {/if}
                                    </li>
                                {/each}
                            </ul>
                            {#if inProgressEntries.length > PREVIEW_LIMIT}
                                <div
                                    class="mt-2 flex items-center justify-between text-xs text-gray-300/80"
                                >
                                    <span
                                        >Showing {PREVIEW_LIMIT} of {inProgressEntries.length}</span
                                    >
                                    <a
                                        href={progressHref("IN_PROGRESS")}
                                        class="hover:text-gray-100 hover:underline"
                                    >
                                        View all
                                    </a>
                                </div>
                            {/if}
                        {/if}
                    </details>

                    <details
                        class="rounded-lg border border-white/10 bg-black/10 p-3"
                    >
                        <summary
                            class="cursor-pointer text-sm font-semibold text-gray-100"
                        >
                            <span class="inline-flex items-center gap-2">
                                <span
                                    class="inline-block h-2 w-2 rounded-full bg-amber-400"
                                ></span>
                                TODO ({todoEntries.length})
                            </span>
                        </summary>
                        {#if todoEntries.length === 0}
                            <p class="mt-2 text-xs text-gray-300/80">
                                No TODO tasks.
                            </p>
                        {:else}
                            <ul
                                class="mt-2 max-h-56 space-y-1 overflow-auto pr-1 text-xs text-gray-200"
                            >
                                {#each todoEntries.slice(0, PREVIEW_LIMIT) as e (e.id)}
                                    <li class="truncate">
                                        <a
                                            href={progressItemHref(e.id)}
                                            class="hover:underline"
                                        >
                                            {getTitle(e)}
                                        </a>
                                        {#if e.wbs_meta?.priority}
                                            <span class="ml-1 opacity-60">
                                                [{e.wbs_meta.priority}]
                                            </span>
                                        {/if}
                                    </li>
                                {/each}
                            </ul>
                            {#if todoEntries.length > PREVIEW_LIMIT}
                                <div
                                    class="mt-2 flex items-center justify-between text-xs text-gray-300/80"
                                >
                                    <span
                                        >Showing {PREVIEW_LIMIT} of {todoEntries.length}</span
                                    >
                                    <a
                                        href={progressHref("TODO")}
                                        class="hover:text-gray-100 hover:underline"
                                    >
                                        View all
                                    </a>
                                </div>
                            {/if}
                        {/if}
                    </details>

                    <details
                        class="rounded-lg border border-white/10 bg-black/10 p-3"
                    >
                        <summary
                            class="cursor-pointer text-sm font-semibold text-gray-100"
                        >
                            <span class="inline-flex items-center gap-2">
                                <span
                                    class="inline-block h-2 w-2 rounded-full bg-sky-400"
                                ></span>
                                DONE ({doneEntries.length})
                            </span>
                        </summary>
                        {#if doneEntries.length === 0}
                            <p class="mt-2 text-xs text-gray-300/80">
                                No DONE tasks.
                            </p>
                        {:else}
                            <ul
                                class="mt-2 max-h-56 space-y-1 overflow-auto pr-1 text-xs text-gray-200"
                            >
                                {#each doneEntries.slice(0, PREVIEW_LIMIT) as e (e.id)}
                                    <li class="truncate">
                                        <a
                                            href={progressItemHref(e.id)}
                                            class="hover:underline"
                                        >
                                            {getTitle(e)}
                                        </a>
                                        {#if e.wbs_meta?.priority}
                                            <span class="ml-1 opacity-60">
                                                [{e.wbs_meta.priority}]
                                            </span>
                                        {/if}
                                    </li>
                                {/each}
                            </ul>
                            {#if doneEntries.length > PREVIEW_LIMIT}
                                <div
                                    class="mt-2 flex items-center justify-between text-xs text-gray-300/80"
                                >
                                    <span
                                        >Showing {PREVIEW_LIMIT} of {doneEntries.length}</span
                                    >
                                    <a
                                        href={progressHref("DONE")}
                                        class="hover:text-gray-100 hover:underline"
                                    >
                                        View all
                                    </a>
                                </div>
                            {/if}
                        {/if}
                    </details>
                </div>
            </details>
        </section>

        <section class="mt-4 grid gap-4 md:grid-cols-2">
            <div class="card">
                <h2 class="card-title">Product Context</h2>
                <pre
                    class="mt-3 max-h-[520px] overflow-auto rounded-lg bg-black/20 p-3 text-xs leading-relaxed text-gray-200">{JSON.stringify(
                        data.product_context,
                        null,
                        2,
                    )}</pre>
            </div>

            <div class="card">
                <h2 class="card-title">Active Context</h2>
                <pre
                    class="mt-3 max-h-[520px] overflow-auto rounded-lg bg-black/20 p-3 text-xs leading-relaxed text-gray-200">{JSON.stringify(
                        data.active_context,
                        null,
                        2,
                    )}</pre>
            </div>
        </section>
    {:else}
        <p class="text-sm text-gray-300">No data.</p>
    {/if}
</main>
