<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import TaskExplorerTree from "$lib/components/TaskExplorerTree.svelte";
    import type { ProgressTreeNode } from "$lib/types/progress";

    import type {
        ConportProgressEntry,
        ConportProgressListResponse,
    } from "$lib/api/conport";
    import { conportProgressList } from "$lib/api/conport";

    const BOARD_LIMIT = 500;

    let status = $state<string>("");
    let parent_id = $state<string>(""); // keep as string for input UX
    let limit = $state<number>(50);

    let loading = $state(true);
    let error = $state<string | null>(null);

    // Existing list view (honors status/parent/limit)
    let entries = $state<ConportProgressEntry[]>([]);

    // Project-manager board (always grouped by status; honors parent_id only)
    let todoEntries = $state<ConportProgressEntry[]>([]);
    let inProgressEntries = $state<ConportProgressEntry[]>([]);
    let doneEntries = $state<ConportProgressEntry[]>([]);

    // Explorer tree built from board entries (all statuses).
    let tree = $state<ProgressTreeNode[]>([]);

    let dbResolved = $state<string>("");

    function parseParentId(value: string): number | null {
        const trimmed = value.trim();
        if (!trimmed) return null;
        const n = Number(trimmed);
        if (!Number.isFinite(n) || n < 1) return null;
        return n;
    }

    function withDb(url: string): string {
        const db = $page.url.searchParams.get("db");
        if (!db) return url;
        const sp = new URLSearchParams({ db });
        return url.includes("?") ? `${url}&${sp}` : `${url}?${sp}`;
    }

    function displayDescription(description: string): string {
        // Hide the [P#] prefix in the UI, but keep it in the stored ConPort description.
        return description.trim().replace(/^\[p\d+\]\s*/i, "");
    }

    function statusDotColor(statusValue: string): string {
        switch (statusValue) {
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
        // keep limit as-is; only clear non-numeric filters
        persistFiltersToUrl();
        void refresh();
    }

    function progressItemHref(id: number): string {
        return withDb(`/conport/item?type=progress&id=${id}`);
    }

    function extractPhaseNumber(description: string): number | null {
        // Only treat entries like "Phase 1 — ..." as phases.
        // (Avoid matching child tasks like "Phase 1: ...".)
        const m = description.match(/\bphase\s*(\d+)\s*[—-]/i);
        return m ? Number(m[1]) : null;
    }

    function extractPriorityNumber(description: string): number | null {
        const m = description.match(/^\s*\[p(\d+)\]/i);
        return m ? Number(m[1]) : null;
    }

    function cleanSortTitle(description: string): string {
        return description
            .trim()
            .replace(/^\s*\[p\d+\]\s*/i, "")
            .toLowerCase();
    }

    function compareTreeNodes(
        a: ProgressTreeNode,
        b: ProgressTreeNode,
    ): number {
        const aPhase = extractPhaseNumber(a.entry.description);
        const bPhase = extractPhaseNumber(b.entry.description);
        const aIsPhase = aPhase !== null;
        const bIsPhase = bPhase !== null;

        // 1) phases first
        if (aIsPhase !== bIsPhase) return aIsPhase ? -1 : 1;

        // 2) phase number (Phase 0 -> 1 -> 2 ...)
        if (aIsPhase && bIsPhase && aPhase !== bPhase) return aPhase - bPhase;

        // 3) priority tag ([P0] -> [P1] -> ...)
        const aPri = extractPriorityNumber(a.entry.description) ?? 9999;
        const bPri = extractPriorityNumber(b.entry.description) ?? 9999;
        if (aPri !== bPri) return aPri - bPri;

        // 4) title (stable-ish)
        const at = cleanSortTitle(a.entry.description);
        const bt = cleanSortTitle(b.entry.description);
        if (at < bt) return -1;
        if (at > bt) return 1;

        // 5) deterministic tie-breaker
        return a.entry.id - b.entry.id;
    }

    function buildTree(
        fromEntries: ConportProgressEntry[],
    ): ProgressTreeNode[] {
        const nodes: Record<number, ProgressTreeNode> = {};

        for (const e of fromEntries) {
            nodes[e.id] = { entry: e, children: [] };
        }

        const roots: ProgressTreeNode[] = [];

        for (const node of Object.values(nodes)) {
            const parentId = node.entry.parent_id;
            const parent = parentId != null ? nodes[parentId] : undefined;
            if (parent) parent.children.push(node);
            else roots.push(node);
        }

        const sortRecursive = (arr: ProgressTreeNode[]) => {
            arr.sort(compareTreeNodes);
            for (const n of arr) sortRecursive(n.children);
        };
        sortRecursive(roots);

        return roots;
    }

    async function refresh() {
        loading = true;
        error = null;

        try {
            const db = $page.url.searchParams.get("db");
            const parsedParentId = parseParentId(parent_id);

            const [listResp, todoResp, inProgressResp, doneResp] =
                await Promise.all([
                    conportProgressList(fetch, {
                        status: status.trim() || null,
                        parent_id: parsedParentId,
                        limit,
                        db,
                    }),
                    conportProgressList(fetch, {
                        status: "TODO",
                        parent_id: parsedParentId,
                        limit: BOARD_LIMIT,
                        db,
                    }),
                    conportProgressList(fetch, {
                        status: "IN_PROGRESS",
                        parent_id: parsedParentId,
                        limit: BOARD_LIMIT,
                        db,
                    }),
                    conportProgressList(fetch, {
                        status: "DONE",
                        parent_id: parsedParentId,
                        limit: BOARD_LIMIT,
                        db,
                    }),
                ]);

            const list = listResp as ConportProgressListResponse;
            const todo = todoResp as ConportProgressListResponse;
            const inProgress = inProgressResp as ConportProgressListResponse;
            const done = doneResp as ConportProgressListResponse;

            dbResolved = list.db;
            entries = list.progress_entries;

            todoEntries = todo.progress_entries;
            inProgressEntries = inProgress.progress_entries;
            doneEntries = done.progress_entries;

            // Tree is built from the board entries, which are already fetched at a high limit.
            // This keeps the explorer view consistent with the board scope (parent_id filter).
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
    <title>ConPort • Progress</title>
</svelte:head>

<main class="page-container">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div class="min-w-0">
            {#if dbResolved}
                <div class="break-all text-xs text-gray-400">
                    DB: <code>{dbResolved}</code>
                </div>
            {/if}
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

            <button
                type="submit"
                disabled={loading}
                style="padding: 8px 12px; border: 1px solid #ccc; border-radius: 8px; background: white; cursor: pointer;"
            >
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

        <section style="margin-bottom: 18px;">
            <div
                style="display: flex; justify-content: space-between; align-items: end; gap: 12px;"
            >
                <div>
                    <h2 style="margin: 0; font-size: 16px;">Project board</h2>
                    <p style="margin: 6px 0 0; font-size: 12px; opacity: 0.7;">
                        Grouped by status {#if parent_id.trim()}for parent_id={parent_id.trim()}{:else}(all
                            tasks){/if}
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
                                style="display: inline-block; width: 8px; height: 8px; border-radius: 999px; background: #0ea5e9;"
                            ></span>
                            TODO
                        </div>
                        <span style="font-size: 12px; opacity: 0.75;"
                            >{todoEntries.length}</span
                        >
                    </div>
                    {#if todoEntries.length === 0}
                        <p
                            style="margin: 10px 0 0; font-size: 12px; opacity: 0.7;"
                        >
                            No TODO tasks.
                        </p>
                    {:else}
                        <ul
                            style="margin: 10px 0 0; padding-left: 18px; display: grid; gap: 6px; max-height: 520px; overflow: auto;"
                        >
                            {#each todoEntries as e (e.id)}
                                <li
                                    style="display: flex; gap: 8px; align-items: baseline;"
                                >
                                    <span
                                        style={`display: inline-block; width: 8px; height: 8px; border-radius: 999px; background: ${statusDotColor(e.status)}; flex: 0 0 auto; margin-top: 5px;`}
                                    ></span>
                                    <a
                                        href={progressItemHref(e.id)}
                                        style="text-decoration: none;"
                                        title={`id=${e.id}`}
                                    >
                                        {displayDescription(e.description)}
                                    </a>
                                </li>
                            {/each}
                        </ul>
                    {/if}
                </div>

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
                                style="display: inline-block; width: 8px; height: 8px; border-radius: 999px; background: #f59e0b;"
                            ></span>
                            IN_PROGRESS
                        </div>
                        <span style="font-size: 12px; opacity: 0.75;"
                            >{inProgressEntries.length}</span
                        >
                    </div>
                    {#if inProgressEntries.length === 0}
                        <p
                            style="margin: 10px 0 0; font-size: 12px; opacity: 0.7;"
                        >
                            No in-progress tasks.
                        </p>
                    {:else}
                        <ul
                            style="margin: 10px 0 0; padding-left: 18px; display: grid; gap: 6px; max-height: 520px; overflow: auto;"
                        >
                            {#each inProgressEntries as e (e.id)}
                                <li
                                    style="display: flex; gap: 8px; align-items: baseline;"
                                >
                                    <span
                                        style={`display: inline-block; width: 8px; height: 8px; border-radius: 999px; background: ${statusDotColor(e.status)}; flex: 0 0 auto; margin-top: 5px;`}
                                    ></span>
                                    <a
                                        href={progressItemHref(e.id)}
                                        style="text-decoration: none;"
                                        title={`id=${e.id}`}
                                    >
                                        {displayDescription(e.description)}
                                    </a>
                                </li>
                            {/each}
                        </ul>
                    {/if}
                </div>

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
                                style="display: inline-block; width: 8px; height: 8px; border-radius: 999px; background: #10b981;"
                            ></span>
                            DONE
                        </div>
                        <span style="font-size: 12px; opacity: 0.75;"
                            >{doneEntries.length}</span
                        >
                    </div>
                    {#if doneEntries.length === 0}
                        <p
                            style="margin: 10px 0 0; font-size: 12px; opacity: 0.7;"
                        >
                            No done tasks.
                        </p>
                    {:else}
                        <ul
                            style="margin: 10px 0 0; padding-left: 18px; display: grid; gap: 6px; max-height: 520px; overflow: auto;"
                        >
                            {#each doneEntries as e (e.id)}
                                <li
                                    style="display: flex; gap: 8px; align-items: baseline;"
                                >
                                    <span
                                        style={`display: inline-block; width: 8px; height: 8px; border-radius: 999px; background: ${statusDotColor(e.status)}; flex: 0 0 auto; margin-top: 5px;`}
                                    ></span>
                                    <a
                                        href={progressItemHref(e.id)}
                                        style="text-decoration: none;"
                                        title={`id=${e.id}`}
                                    >
                                        {displayDescription(e.description)}
                                    </a>
                                </li>
                            {/each}
                        </ul>
                    {/if}
                </div>
            </div>
        </section>

        {#if entries.length === 0}
            <p style="opacity: 0.7;">No progress entries found.</p>
        {:else}
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr>
                        <th
                            style="text-align: left; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.12);"
                            >Description</th
                        >
                        <th
                            style="text-align: left; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.12);"
                            >Status</th
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
                        <tr>
                            <td
                                style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.08);"
                            >
                                <div style="font-weight: 600;">
                                    <a
                                        href={progressItemHref(e.id)}
                                        style="text-decoration: none;"
                                    >
                                        {displayDescription(e.description)}
                                    </a>
                                </div>
                                <div style="font-size: 12px; opacity: 0.75;">
                                    id={e.id}
                                </div>
                            </td>
                            <td
                                style="padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.08);"
                            >
                                <code>{e.status}</code>
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
