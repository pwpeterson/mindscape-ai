<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import TaskExplorerTree from "$lib/components/TaskExplorerTree.svelte";
    import type {
        ProgressEntryWithWbs,
        ProgressTreeNodeWithWbs,
        WbsMeta,
    } from "$lib/types/progress";

    import type {
        ConportProgressEntry,
        ConportProgressListResponse,
    } from "$lib/api/conport";
    import {
        conportCustomDataList,
        conportProgressList,
    } from "$lib/api/conport";

    const BOARD_LIMIT = 500;

    let status = $state<string>("");
    let parent_id = $state<string>("");
    let limit = $state<number>(50);

    let loading = $state(true);
    let error = $state<string | null>(null);

    let entries = $state<ProgressEntryWithWbs[]>([]);
    let todoEntries = $state<ProgressEntryWithWbs[]>([]);
    let inProgressEntries = $state<ProgressEntryWithWbs[]>([]);
    let doneEntries = $state<ProgressEntryWithWbs[]>([]);

    let tree = $state<ProgressTreeNodeWithWbs[]>([]);
    let dbResolved = $state<string>("");

    // WBS metadata cache
    let wbsMetaMap = $state<Map<number, WbsMeta>>(new Map());

    function parseParentId(value: string): number | null {
        const trimmed = value.trim();
        if (!trimmed) return null;
        const n = Number(trimmed);
        if (!Number.isFinite(n) || n < 1) return null;
        return n;
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

    function withDb(url: string): string {
        return url + buildQuery({});
    }

    function getEntityType(
        entry: ProgressEntryWithWbs,
    ): "project" | "phase" | "task" | "unknown" {
        return entry.wbs_meta?.entity_type ?? "unknown";
    }

    function getTitle(entry: ProgressEntryWithWbs): string {
        return entry.wbs_meta?.title ?? stripPriorityPrefix(entry.description);
    }

    function stripPriorityPrefix(description: string): string {
        return description.replace(/^\s*\[p\d+\]\s*/i, "");
    }

    function entityIcon(
        type: "project" | "phase" | "task" | "unknown",
        statusValue: string,
    ): string {
        const normalizedStatus = statusValue.toUpperCase();
        switch (type) {
            case "project":
                return "📦";
            case "phase":
                return "📋";
            case "task":
                // DONE: gray X, TODO: blue check, IN_PROGRESS: green check
                return normalizedStatus === "DONE" ? "X" : "✓";
            default:
                return "•";
        }
    }

    function phaseMarker(statusValue: string): string {
        const normalized = statusValue.toUpperCase();
        switch (normalized) {
            case "IN_PROGRESS":
                return "🟩";
            case "DONE":
                return "🟦";
            case "TODO":
            default:
                return "🟨";
        }
    }

    function phaseMarkerLabel(statusValue: string): string {
        const normalized = statusValue.toUpperCase();
        switch (normalized) {
            case "IN_PROGRESS":
                return "Phase (In progress)";
            case "DONE":
                return "Phase (Done)";
            case "TODO":
            default:
                return "Phase (Pending action)";
        }
    }

    function statusDotColor(statusValue: string): string {
        const normalized = statusValue.toUpperCase();
        switch (normalized) {
            case "DONE":
                return "#10b981";
            case "IN_PROGRESS":
                return "#f59e0b";
            case "TODO":
            default:
                return "#0ea5e9";
        }
    }

    function persistFiltersToUrl(): void {
        if (typeof window === "undefined") return;

        const u = new URL(window.location.href);
        const s = status.trim();
        const p = parent_id.trim();

        if (s) u.searchParams.set("status", s);
        else u.searchParams.delete("status");

        if (p) u.searchParams.set("parent_id", p);
        else u.searchParams.delete("parent_id");

        u.searchParams.set("limit", String(limit));

        window.history.replaceState({}, "", u);
    }

    let linkToast = $state<string | null>(null);

    async function copyLink(): Promise<void> {
        if (typeof window === "undefined") return;

        try {
            await navigator.clipboard.writeText(window.location.href);
            linkToast = "Link copied";
            window.setTimeout(() => {
                linkToast = null;
            }, 1500);
        } catch (err) {
            linkToast =
                err instanceof Error
                    ? `Copy failed: ${err.message}`
                    : `Copy failed: ${String(err)}`;
            window.setTimeout(() => {
                linkToast = null;
            }, 2500);
        }
    }

    function setStatusAndRefresh(nextStatus: string): void {
        status = nextStatus;
        persistFiltersToUrl();
        void refresh();
    }

    function clearFilters(): void {
        status = "";
        parent_id = "";
        persistFiltersToUrl();
        void refresh();
    }

    function progressItemHref(id: number): string {
        return `/conport/item${buildQuery({ type: "progress", id: String(id) })}`;
    }

    function compareTreeNodes(
        a: ProgressTreeNodeWithWbs,
        b: ProgressTreeNodeWithWbs,
    ): number {
        const aType = getEntityType(a.entry);
        const bType = getEntityType(b.entry);

        // 1) Sort by entity type: project < phase < task
        const typeOrder = { project: 0, phase: 1, task: 2, unknown: 3 };
        if (aType !== bType) {
            return typeOrder[aType] - typeOrder[bType];
        }

        // 2) Sort by order field if present
        const aOrder = a.entry.wbs_meta?.order ?? null;
        const bOrder = b.entry.wbs_meta?.order ?? null;
        if (aOrder != null && bOrder != null && aOrder !== bOrder) {
            return aOrder - bOrder;
        }

        // 3) Sort by priority (P0 < P1 < P2 < P3)
        const aPri = a.entry.wbs_meta?.priority;
        const bPri = b.entry.wbs_meta?.priority;
        if (aPri && bPri && aPri !== bPri) {
            const priOrder = { P0: 0, P1: 1, P2: 2, P3: 3 };
            return priOrder[aPri] - priOrder[bPri];
        }

        // 4) Sort by title
        const aTitle = getTitle(a.entry).toLowerCase();
        const bTitle = getTitle(b.entry).toLowerCase();
        if (aTitle < bTitle) return -1;
        if (aTitle > bTitle) return 1;

        // 5) Deterministic tie-breaker
        return a.entry.id - b.entry.id;
    }

    function buildTree(
        fromEntries: ProgressEntryWithWbs[],
    ): ProgressTreeNodeWithWbs[] {
        const nodes: Record<number, ProgressTreeNodeWithWbs> = {};

        for (const e of fromEntries) {
            nodes[e.id] = { entry: e, children: [] };
        }

        const roots: ProgressTreeNodeWithWbs[] = [];

        for (const node of Object.values(nodes)) {
            const parentId = node.entry.parent_id;
            const parent = parentId != null ? nodes[parentId] : undefined;
            if (parent) parent.children.push(node);
            else roots.push(node);
        }

        const sortRecursive = (arr: ProgressTreeNodeWithWbs[]) => {
            arr.sort(compareTreeNodes);
            for (const n of arr) sortRecursive(n.children);
        };
        sortRecursive(roots);

        return roots;
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
            const parsedParentId = parseParentId(parent_id);

            console.log("[Progress Page] refresh() called with filters:", {
                status: status.trim() || null,
                parent_id: parsedParentId,
                limit,
                app_id,
                db,
            });

            // Fetch WBS metadata first
            const wbsResp = await conportCustomDataList(fetch, {
                category: "wbs_meta",
                app_id,
                db,
            });

            // Build metadata map
            wbsMetaMap.clear();
            for (const item of wbsResp.custom_data) {
                const match = item.key.match(/^progress:(\d+)$/);
                if (match) {
                    const progressId = Number(match[1]);
                    wbsMetaMap.set(progressId, item.value as WbsMeta);
                }
            }

            // Fetch progress entries
            const [listResp, todoResp, inProgressResp, doneResp] =
                await Promise.all([
                    conportProgressList(fetch, {
                        status: status.trim() || null,
                        parent_id: parsedParentId,
                        limit,
                        app_id,
                        db,
                    }),
                    conportProgressList(fetch, {
                        status: "TODO",
                        parent_id: parsedParentId,
                        limit: BOARD_LIMIT,
                        app_id,
                        db,
                    }),
                    conportProgressList(fetch, {
                        status: "IN_PROGRESS",
                        parent_id: parsedParentId,
                        limit: BOARD_LIMIT,
                        app_id,
                        db,
                    }),
                    conportProgressList(fetch, {
                        status: "DONE",
                        parent_id: parsedParentId,
                        limit: BOARD_LIMIT,
                        app_id,
                        db,
                    }),
                ]);

            const list = listResp as ConportProgressListResponse;
            const todo = todoResp as ConportProgressListResponse;
            const inProgress = inProgressResp as ConportProgressListResponse;
            const done = doneResp as ConportProgressListResponse;

            dbResolved = list.db;

            entries = enrichEntriesWithWbs(list.progress_entries);
            todoEntries = enrichEntriesWithWbs(todo.progress_entries);
            inProgressEntries = enrichEntriesWithWbs(
                inProgress.progress_entries,
            );
            doneEntries = enrichEntriesWithWbs(done.progress_entries);

            const combined = [
                ...todoEntries,
                ...inProgressEntries,
                ...doneEntries,
            ];
            tree = buildTree(combined);
        } catch (err) {
            error = err instanceof Error ? err.message : String(err);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        const params = $page.url.searchParams;

        const s = params.get("status");
        const p = params.get("parent_id");
        const rawLimit = params.get("limit");

        if (s) status = s;
        if (p) parent_id = p;
        if (rawLimit) {
            const n = Number(rawLimit);
            if (Number.isFinite(n) && n >= 1 && n <= 500) limit = n;
        }

        void refresh();
    });
</script>

<svelte:head>
    <title>ConPort • Progress (WBS)</title>
</svelte:head>

<main class="page-container">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div class="min-w-0">
            {#if dbResolved}
                <div class="break-all text-xs text-gray-400">
                    DB: <code>{dbResolved}</code>
                </div>
            {/if}
            <div class="mt-1 text-xs text-gray-500">
                WBS v1.0 • {wbsMetaMap.size} records with metadata
            </div>
            {#if linkToast}
                <div class="mt-1 text-xs text-gray-300/80">
                    {linkToast}
                </div>
            {/if}
        </div>

        <div class="flex flex-wrap items-center justify-end gap-2">
            <button
                onclick={() => setStatusAndRefresh("IN_PROGRESS")}
                disabled={loading}
                class="btn"
                title="Filter to IN_PROGRESS"
            >
                IN_PROGRESS
            </button>
            <button
                onclick={() => setStatusAndRefresh("TODO")}
                disabled={loading}
                class="btn"
                title="Filter to TODO"
            >
                TODO
            </button>
            <button
                onclick={() => setStatusAndRefresh("DONE")}
                disabled={loading}
                class="btn"
                title="Filter to DONE"
            >
                DONE
            </button>
            <button
                onclick={() => clearFilters()}
                disabled={loading}
                class="btn"
                title="Clear status/parent_id filters"
            >
                Clear
            </button>
            <button
                onclick={() => void copyLink()}
                class="btn"
                title="Copy current URL (including filters) to clipboard"
            >
                Copy link
            </button>
            <button
                onclick={() => {
                    persistFiltersToUrl();
                    void refresh();
                }}
                disabled={loading}
                class="btn btn-primary"
            >
                {loading ? "Loading…" : "Refresh"}
            </button>
        </div>
    </div>

    <form
        onsubmit={(e) => {
            e.preventDefault();
            persistFiltersToUrl();
            void refresh();
        }}
        style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px;"
    >
        <label style="display: grid; gap: 6px;">
            <span style="font-size: 12px; opacity: 0.8;">Status (optional)</span
            >
            <input
                bind:value={status}
                style="padding: 8px 10px; border: 1px solid #ccc; border-radius: 8px;"
            />
        </label>

        <label style="display: grid; gap: 6px;">
            <span style="font-size: 12px; opacity: 0.8;"
                >Parent ID (optional)</span
            >
            <input
                bind:value={parent_id}
                style="padding: 8px 10px; border: 1px solid #ccc; border-radius: 8px;"
            />
        </label>

        <div style="display: flex; gap: 10px; align-items: end;">
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

            <button type="submit" disabled={loading} class="btn btn-primary">
                {loading ? "Loading…" : "Apply"}
            </button>
        </div>
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
    {:else}
        {#if parent_id.trim()}
            <div style="margin-bottom: 12px; font-size: 12px; opacity: 0.85;">
                Scoped to parent_id={parent_id.trim()} •
                <a
                    href={progressItemHref(Number(parent_id.trim()))}
                    style="text-decoration: none;"
                >
                    Open parent
                </a>
            </div>
        {/if}

        <details
            open
            style="margin-bottom: 18px; border: 1px solid rgba(255,255,255,0.12); border-radius: 10px; padding: 10px; background: rgba(0,0,0,0.25);"
        >
            <summary style="cursor: pointer; font-weight: 700;">
                Explorer tree ({tree.length} roots)
            </summary>
            {#if tree.length === 0}
                <p style="margin: 10px 0 0; font-size: 12px; opacity: 0.7;">
                    No tasks found for this scope.
                </p>
            {:else}
                <div style="margin-top: 10px;">
                    <TaskExplorerTree
                        nodes={tree}
                        itemHref={progressItemHref}
                        showIdPrefix
                    />
                </div>
            {/if}
        </details>

        {#if !status.trim()}
            <section style="margin-bottom: 18px;">
                <div
                    style="display: flex; justify-content: space-between; align-items: end; gap: 12px;"
                >
                    <div>
                        <h2 style="margin: 0; font-size: 16px;">
                            Project board
                        </h2>
                        <p
                            style="margin: 6px 0 0; font-size: 12px; opacity: 0.7;"
                        >
                            Grouped by status {#if parent_id.trim()}for
                                parent_id={parent_id.trim()}{:else}(all tasks){/if}
                        </p>
                    </div>
                    <div style="font-size: 12px; opacity: 0.75;">
                        TODO: {todoEntries.length} • IN_PROGRESS: {inProgressEntries.length}
                        • DONE: {doneEntries.length}
                    </div>
                </div>

                <div
                    style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 12px;"
                >
                    {#each [{ label: "TODO", entries: todoEntries, color: "#0ea5e9" }, { label: "IN_PROGRESS", entries: inProgressEntries, color: "#f59e0b" }, { label: "DONE", entries: doneEntries, color: "#10b981" }] as column}
                        <div
                            style="border: 1px solid rgba(255,255,255,0.12); border-radius: 10px; padding: 10px; background: rgba(0,0,0,0.25);"
                        >
                            <div
                                style="display: flex; align-items: center; justify-content: space-between; gap: 8px;"
                            >
                                <div
                                    style="display: flex; align-items: center; gap: 8px; font-weight: 700;"
                                >
                                    <span
                                        style={`display: inline-block; width: 8px; height: 8px; border-radius: 999px; background: ${column.color};`}
                                    ></span>
                                    {column.label}
                                </div>
                                <span style="font-size: 12px; opacity: 0.75;"
                                    >{column.entries.length}</span
                                >
                            </div>
                            {#if column.entries.length === 0}
                                <p
                                    style="margin: 10px 0 0; font-size: 12px; opacity: 0.7;"
                                >
                                    No {column.label.toLowerCase()} tasks.
                                </p>
                            {:else}
                                <ul
                                    style="margin: 10px 0 0; padding-left: 18px; display: grid; gap: 6px; max-height: 520px; overflow: auto;"
                                >
                                    {#each column.entries as e (e.id)}
                                        {@const entityType = getEntityType(e)}
                                        {@const title = getTitle(e)}
                                        <li
                                            style="display: flex; gap: 8px; align-items: baseline;"
                                        >
                                            <span
                                                style="flex: 0 0 auto; margin-top: 2px;"
                                                title={entityType}
                                            >
                                                {#if entityType === "phase"}
                                                    {phaseMarker(e.status)}
                                                {:else}
                                                    <span
                                                        style={`color: ${
                                                            e.status.toUpperCase() ===
                                                            "DONE"
                                                                ? "rgba(156,163,175,0.9)"
                                                                : e.status.toUpperCase() ===
                                                                    "TODO"
                                                                  ? "rgb(59,130,246)"
                                                                  : "rgb(34,197,94)"
                                                        };`}
                                                        >{entityIcon(
                                                            entityType,
                                                            e.status,
                                                        )}</span
                                                    >
                                                {/if}
                                            </span>
                                            <div style="min-w-0; flex: 1;">
                                                <a
                                                    href={progressItemHref(
                                                        e.id,
                                                    )}
                                                    style="text-decoration: none;"
                                                    title={`id=${e.id}`}
                                                >
                                                    {title}
                                                </a>
                                                {#if e.wbs_meta?.priority}
                                                    <span
                                                        class="ml-1 text-xs opacity-60"
                                                    >
                                                        [{e.wbs_meta.priority}]
                                                    </span>
                                                {/if}
                                                {#if e.wbs_meta?.tags && e.wbs_meta.tags.length > 0}
                                                    <div
                                                        class="mt-1 flex flex-wrap gap-1"
                                                    >
                                                        {#each e.wbs_meta.tags.slice(0, 3) as tag}
                                                            <span
                                                                class="rounded bg-gray-700 px-1 py-0.5 text-xs"
                                                            >
                                                                {tag}
                                                            </span>
                                                        {/each}
                                                    </div>
                                                {/if}
                                            </div>
                                        </li>
                                    {/each}
                                </ul>
                            {/if}
                        </div>
                    {/each}
                </div>
            </section>
        {:else}
            <div
                style="margin-bottom: 18px; padding: 12px; border: 1px solid rgba(255,255,255,0.12); border-radius: 10px; background: rgba(0,0,0,0.15); font-size: 12px; opacity: 0.7;"
            >
                Project board hidden when status filter is active. Clear filter
                to see all status columns.
            </div>
        {/if}

        {#if entries.length === 0}
            <p style="opacity: 0.7;">No progress entries found.</p>
        {:else}
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr>
                        <th
                            style="text-align: left; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.12);"
                            >Title</th
                        >
                        <th
                            style="text-align: left; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.12);"
                            >Type</th
                        >
                        <th
                            style="text-align: left; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.12);"
                            >Status</th
                        >
                        <th
                            style="text-align: left; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.12);"
                            >Priority</th
                        >
                        <th
                            style="text-align: left; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.12);"
                            >Parent</th
                        >
                        <th
                            style="text-align: left; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.12);"
                            >Timestamp</th
                        >
                    </tr>
                </thead>
                <tbody>
                    {#each entries as e (e.id)}
                        {@const entityType = getEntityType(e)}
                        {@const title = getTitle(e)}
                        <tr>
                            <td
                                style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.08);"
                            >
                                <div
                                    style="font-weight: 600; display: flex; gap: 6px; align-items: baseline;"
                                >
                                    <span title={entityType}>
                                        {#if entityType === "phase"}
                                            {phaseMarker(e.status)}
                                        {:else}
                                            <span
                                                style={`color: ${
                                                    e.status.toUpperCase() ===
                                                    "DONE"
                                                        ? "rgba(156,163,175,0.9)"
                                                        : e.status.toUpperCase() ===
                                                            "TODO"
                                                          ? "rgb(59,130,246)"
                                                          : "rgb(34,197,94)"
                                                };`}
                                                >{entityIcon(
                                                    entityType,
                                                    e.status,
                                                )}</span
                                            >
                                        {/if}
                                    </span>
                                    <a
                                        href={progressItemHref(e.id)}
                                        style="text-decoration: none;"
                                    >
                                        {title}
                                    </a>
                                </div>
                                <div style="font-size: 12px; opacity: 0.75;">
                                    id={e.id}
                                </div>
                                {#if e.wbs_meta?.tags && e.wbs_meta.tags.length > 0}
                                    <div class="mt-1 flex flex-wrap gap-1">
                                        {#each e.wbs_meta.tags as tag}
                                            <span
                                                class="rounded bg-gray-700 px-1 py-0.5 text-xs"
                                            >
                                                {tag}
                                            </span>
                                        {/each}
                                    </div>
                                {/if}
                            </td>
                            <td
                                style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.08);"
                            >
                                <code>{entityType}</code>
                            </td>
                            <td
                                style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.08);"
                            >
                                <code>{e.status}</code>
                            </td>
                            <td
                                style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.08);"
                            >
                                {#if e.wbs_meta?.priority}
                                    <code>{e.wbs_meta.priority}</code>
                                {:else}
                                    <span style="opacity: 0.7;">—</span>
                                {/if}
                            </td>
                            <td
                                style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.08);"
                            >
                                {#if e.parent_id != null}
                                    <a
                                        href={progressItemHref(e.parent_id)}
                                        style="text-decoration: none;"
                                    >
                                        {e.parent_id}
                                    </a>
                                {:else}
                                    <span style="opacity: 0.7;">—</span>
                                {/if}
                            </td>
                            <td
                                style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.08); font-size: 12px; opacity: 0.8;"
                            >
                                {e.timestamp}
                            </td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        {/if}
    {/if}
</main>
