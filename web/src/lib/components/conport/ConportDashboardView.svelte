<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import TaskExplorerTree from "$lib/components/TaskExplorerTree.svelte";
    import type { ProgressTreeNode } from "$lib/types/progress";

    import type {
        ConportDashboardResponse,
        ConportProgressEntry,
        ConportProgressListResponse,
    } from "$lib/api/conport";
    import { conportDashboard, conportProgressList } from "$lib/api/conport";
    import { connectEventsStream } from "$lib/api/events";

    const TASK_TREE_LIMIT = 500;

    let loading = $state(true);
    let error = $state<string | null>(null);

    let data = $state<ConportDashboardResponse | null>(null);
    let treeEntries = $state<ConportProgressEntry[]>([]);
    let tree = $state<ProgressTreeNode[]>([]);

    const AUTO_REFRESH_MIN_INTERVAL_MS = 600_000; // 10 minutes
    let lastAutoRefreshAtMs = $state<number>(0);

    function maybeAutoRefresh() {
        if (loading) return;
        const now = Date.now();
        if (now - lastAutoRefreshAtMs < AUTO_REFRESH_MIN_INTERVAL_MS) return;
        lastAutoRefreshAtMs = now;
        void refresh();
    }

    let planTitle = $state<string | null>(null);
    let panelTree = $state<ProgressTreeNode[]>([]);

    let todoTree = $state<ProgressTreeNode[]>([]);
    let inProgressTree = $state<ProgressTreeNode[]>([]);
    let doneTree = $state<ProgressTreeNode[]>([]);

    let todoCount = $state<number>(0);
    let inProgressCount = $state<number>(0);
    let doneCount = $state<number>(0);

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

    function progressHref(): string {
        return `/conport/progress${buildQuery({ limit: String(TASK_TREE_LIMIT) })}`;
    }

    function extractPhaseNumber(description: string): number | null {
        // Only treat entries like "Phase 1 — ..." as phases.
        // (Avoid matching child tasks like "Phase 1: ...".)
        const m = description.match(/\bphase\s*(\d+)\s*[—–-]/i);
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

    function isPlanRoot(entry: ConportProgressEntry): boolean {
        const d = entry.description.trim().toLowerCase();
        return d.startsWith("[plan]") || d.startsWith("plan:");
    }

    function planDisplayTitle(description: string): string {
        const trimmed = description.trim();
        const lower = trimmed.toLowerCase();

        let title = trimmed;
        if (lower.startsWith("[plan]"))
            title = trimmed.slice("[plan]".length).trim();
        else if (lower.startsWith("plan:"))
            title = trimmed.slice("plan:".length).trim();

        // Normalize verbose titles like:
        // "Mindscape-AI project plan (derived from README + PRD v1.0.0)" -> "Mindscape-AI project plan"
        const lowerTitle = title.toLowerCase();
        const derivedIdx = lowerTitle.indexOf(" (derived from");
        if (derivedIdx >= 0) title = title.slice(0, derivedIdx).trim();

        return title;
    }

    function buildTree(entries: ConportProgressEntry[]): ProgressTreeNode[] {
        // Note: avoid `new Map()` to keep Svelte's static analysis happy.
        const nodes: Record<number, ProgressTreeNode> = {};

        for (const e of entries) {
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

    function mergeProgressEntries(
        base: ConportProgressEntry[],
        extra: ConportProgressEntry[],
    ): ConportProgressEntry[] {
        const byId: Record<number, ConportProgressEntry> = {};
        for (const e of base) byId[e.id] = e;
        for (const e of extra) byId[e.id] = e;
        return Object.values(byId);
    }

    function extractPhaseIdFromEntries(
        entries: ConportProgressEntry[],
        phaseNumber: number,
    ): number | null {
        const re = new RegExp(`\\bphase\\s*${phaseNumber}\\s*[—–-]`, "i");
        for (const e of entries) {
            if (re.test(e.description)) return e.id;
        }
        return null;
    }

    type LaneStatus = "TODO" | "IN_PROGRESS" | "DONE";

    function normalizeLaneStatus(status: string): LaneStatus {
        switch (status) {
            case "IN_PROGRESS":
                return "IN_PROGRESS";
            case "DONE":
                return "DONE";
            case "TODO":
            default:
                return "TODO";
        }
    }

    function partitionTreeByLane(nodes: ProgressTreeNode[]): {
        lanes: Record<LaneStatus, ProgressTreeNode[]>;
        counts: Record<LaneStatus, number>;
    } {
        const lanes: Record<LaneStatus, ProgressTreeNode[]> = {
            IN_PROGRESS: [],
            TODO: [],
            DONE: [],
        };
        const counts: Record<LaneStatus, number> = {
            IN_PROGRESS: 0,
            TODO: 0,
            DONE: 0,
        };

        const cloneIntoLane = (
            node: ProgressTreeNode,
            lane: LaneStatus,
        ): ProgressTreeNode => {
            counts[lane] += 1;
            return {
                entry: node.entry,
                children: node.children.map((c: ProgressTreeNode) =>
                    cloneIntoLane(c, lane),
                ),
            };
        };

        for (const n of nodes) {
            const lane = normalizeLaneStatus(n.entry.status);
            lanes[lane].push(cloneIntoLane(n, lane));
        }

        return { lanes, counts };
    }

    async function refresh() {
        loading = true;
        error = null;

        try {
            const app_id = $page.url.searchParams.get("app_id");
            const db = $page.url.searchParams.get("db");

            const [dash, list] = await Promise.all([
                conportDashboard(fetch, { app_id, db }),
                conportProgressList(fetch, {
                    status: null,
                    parent_id: null,
                    limit: TASK_TREE_LIMIT,
                    app_id,
                    db,
                }),
            ]);

            data = dash;
            treeEntries = (list as ConportProgressListResponse)
                .progress_entries;

            // Robustness: Phase nodes and their notes can be older than the latest TASK_TREE_LIMIT
            // rows and therefore omitted.
            //
            // Backfill any root-level rows that start with "Phase" or "[P" (covers both:
            // - "Phase N — ..." / "Phase N: ..."
            // - "[P1] Phase N — ..." / "[P1] Phase N: ..."
            const [phaseBackfill, phaseBackfillPrioritized] = await Promise.all(
                [
                    conportProgressList(fetch, {
                        status: null,
                        parent_id: null,
                        description_prefix: "Phase",
                        limit: 200,
                        app_id,
                        db,
                    }),
                    conportProgressList(fetch, {
                        status: null,
                        parent_id: null,
                        description_prefix: "[P",
                        limit: 200,
                        app_id,
                        db,
                    }),
                ],
            );

            treeEntries = mergeProgressEntries(
                treeEntries,
                (phaseBackfill as ConportProgressListResponse).progress_entries,
            );
            treeEntries = mergeProgressEntries(
                treeEntries,
                (phaseBackfillPrioritized as ConportProgressListResponse)
                    .progress_entries,
            );

            // Ensure each Phase node has its notes attached as children so TaskExplorerTree can
            // render the Notes subpanel.
            const phaseNumbers = Array.from(
                new Set(
                    treeEntries
                        .map((e) => extractPhaseNumber(e.description))
                        .filter((n): n is number => n != null),
                ),
            ).sort((a, b) => a - b);

            for (const phaseNumber of phaseNumbers) {
                const phaseId = extractPhaseIdFromEntries(
                    treeEntries,
                    phaseNumber,
                );
                if (phaseId == null) continue;

                const [phaseChildrenAll, phaseNotesRoot, phaseNotesAttached] =
                    await Promise.all([
                        conportProgressList(fetch, {
                            status: null,
                            parent_id: phaseId,
                            limit: 500,
                            app_id,
                            db,
                        }),
                        // Notes are often stored as root-level rows (parent_id = null)
                        conportProgressList(fetch, {
                            parent_id: null,
                            description_prefix: `Phase ${phaseNumber}:`,
                            limit: 50,
                            app_id,
                            db,
                        }),
                        // ...but support DBs where notes were already attached under the phase
                        conportProgressList(fetch, {
                            parent_id: phaseId,
                            description_prefix: `Phase ${phaseNumber}:`,
                            limit: 50,
                            app_id,
                            db,
                        }),
                    ]);

                treeEntries = mergeProgressEntries(
                    treeEntries,
                    (phaseChildrenAll as ConportProgressListResponse)
                        .progress_entries,
                );
                treeEntries = mergeProgressEntries(
                    treeEntries,
                    (phaseNotesAttached as ConportProgressListResponse)
                        .progress_entries,
                );

                const rootNotes = (
                    phaseNotesRoot as ConportProgressListResponse
                ).progress_entries;
                const re = new RegExp(
                    `^\\s*(?:\\[p\\d+\\]\\s*)?phase\\s+${phaseNumber}\\s*:`,
                    "i",
                );
                const attachedNotes = rootNotes.map((n) => {
                    if (n.parent_id == null && re.test(n.description)) {
                        return { ...n, parent_id: phaseId };
                    }
                    return n;
                });

                treeEntries = mergeProgressEntries(treeEntries, attachedNotes);
            }

            tree = buildTree(treeEntries);

            const planRoot = tree.find((n) => isPlanRoot(n.entry)) ?? null;
            planTitle = planRoot
                ? planDisplayTitle(planRoot.entry.description)
                : null;

            // Render plan children in the status panels (exclude the plan root itself).
            // But ALSO include any other root-level nodes (not just phases), because many
            // parent tasks (e.g. T030) are not direct children of the [plan] node.
            const planChildren = planRoot ? planRoot.children : [];
            const planChildIds = new Set(planChildren.map((n) => n.entry.id));

            const rootsExcludingPlan = planRoot
                ? tree.filter((n) => n.entry.id !== planRoot.entry.id)
                : tree;

            const otherRoots = rootsExcludingPlan.filter(
                (n) => !planChildIds.has(n.entry.id),
            );

            const mergedRoots = planRoot
                ? [...planChildren, ...otherRoots]
                : tree;

            panelTree = mergedRoots;

            const { lanes, counts } = partitionTreeByLane(panelTree);

            inProgressTree = lanes.IN_PROGRESS;
            inProgressCount = counts.IN_PROGRESS;

            todoTree = lanes.TODO;
            todoCount = counts.TODO;

            doneTree = lanes.DONE;
            doneCount = counts.DONE;
        } catch (err) {
            error = err instanceof Error ? err.message : String(err);
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        void refresh();

        // Note: events stream doesn't scope by app_id yet; we keep this connection global.
        const conn = connectEventsStream(
            {
                onHeartbeat: () => maybeAutoRefresh(),
            },
            { heartbeat_seconds: 15 },
        );

        return () => conn.close();
    });
</script>

<main class="page-container">
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
        <section class="grid gap-4 md:grid-cols-1">
            <div class="card">
                <div class="flex flex-wrap items-start justify-between gap-3">
                    <div>
                        <h2 class="card-title">
                            {planTitle ?? "Project plan"} — Explorer
                        </h2>
                        <div class="mt-2 text-xs text-gray-300/90">
                            Explorer-style outline (collapsible by status).
                        </div>
                    </div>

                    <div class="flex flex-wrap items-center justify-end gap-3">
                        <a
                            href={progressHref()}
                            class="text-xs text-gray-200/80 hover:text-gray-100 hover:underline"
                        >
                            Open Progress
                        </a>

                        {#if data}
                            <div class="text-xs text-gray-200">
                                Graph Health:&nbsp;&nbsp;Links: {data
                                    .graph_health.links},&nbsp;&nbsp;Decisions:
                                {data.graph_health.decisions},&nbsp;&nbsp;Custom
                                data: {data.graph_health.custom_data}
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
                </div>

                {#if panelTree.length === 0}
                    <p class="mt-3 text-sm text-gray-300">No tasks found.</p>
                {:else}
                    <div class="mt-4 space-y-2">
                        <details
                            class="rounded-lg border border-white/10 bg-black/10 p-3"
                            open
                        >
                            <summary
                                class="cursor-pointer text-sm font-semibold text-gray-100"
                            >
                                IN PROGRESS ({inProgressCount})
                            </summary>
                            {#if inProgressCount === 0}
                                <p class="mt-2 text-xs text-gray-300/80">
                                    No IN_PROGRESS tasks.
                                </p>
                            {:else}
                                <div class="mt-2">
                                    <TaskExplorerTree
                                        nodes={inProgressTree}
                                        itemHref={progressItemHref}
                                        showIdPrefix
                                    />
                                </div>
                            {/if}
                        </details>

                        <details
                            class="rounded-lg border border-white/10 bg-black/10 p-3"
                            open
                        >
                            <summary
                                class="cursor-pointer text-sm font-semibold text-gray-100"
                            >
                                TODO ({todoCount})
                            </summary>
                            {#if todoCount === 0}
                                <p class="mt-2 text-xs text-gray-300/80">
                                    No TODO tasks.
                                </p>
                            {:else}
                                <div class="mt-2">
                                    <TaskExplorerTree
                                        nodes={todoTree}
                                        itemHref={progressItemHref}
                                        showIdPrefix
                                    />
                                </div>
                            {/if}
                        </details>

                        <details
                            class="rounded-lg border border-white/10 bg-black/10 p-3"
                            open
                        >
                            <summary
                                class="cursor-pointer text-sm font-semibold text-gray-100"
                            >
                                DONE ({doneCount})
                            </summary>
                            {#if doneCount === 0}
                                <p class="mt-2 text-xs text-gray-300/80">
                                    No DONE tasks.
                                </p>
                            {:else}
                                <div class="mt-2">
                                    <TaskExplorerTree
                                        nodes={doneTree}
                                        itemHref={progressItemHref}
                                        showIdPrefix
                                    />
                                </div>
                            {/if}
                        </details>
                    </div>
                {/if}
            </div>
        </section>
    {:else}
        <p class="text-sm text-gray-300">No data.</p>
    {/if}
</main>
