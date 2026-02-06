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
        ConportDashboardResponse,
        ConportProgressEntry,
        ConportProgressListResponse,
    } from "$lib/api/conport";
    import {
        conportCustomDataList,
        conportDashboard,
        conportProgressList,
    } from "$lib/api/conport";

    const TASK_TREE_LIMIT = 500;

    let loading = $state(true);
    let error = $state<string | null>(null);

    let data = $state<ConportDashboardResponse | null>(null);
    let treeEntries = $state<ProgressEntryWithWbs[]>([]);
    let tree = $state<ProgressTreeNodeWithWbs[]>([]);
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

    let planTitle = $state<string | null>(null);
    let panelTree = $state<ProgressTreeNodeWithWbs[]>([]);

    let todoTree = $state<ProgressTreeNodeWithWbs[]>([]);
    let inProgressTree = $state<ProgressTreeNodeWithWbs[]>([]);
    let doneTree = $state<ProgressTreeNodeWithWbs[]>([]);

    let todoCount = $state<number>(0);
    let inProgressCount = $state<number>(0);
    let doneCount = $state<number>(0);

    let priorityScoreById: Record<number, number> = {};

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

    function extractPriorityNumber(entry: ProgressEntryWithWbs): number | null {
        // Check WBS metadata first
        if (entry.wbs_meta?.priority) {
            const match = entry.wbs_meta.priority.match(/^P(\d+)$/);
            if (match) return Number(match[1]);
        }
        // Fallback to description parsing
        const m = entry.description.match(/^\s*\[p(\d+)\]/i);
        return m ? Number(m[1]) : null;
    }

    function cleanSortTitle(entry: ProgressEntryWithWbs): string {
        return getTitle(entry).toLowerCase();
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

        // 3) Priority (WBS or inherited)
        const aPri =
            priorityScoreById[a.entry.id] ??
            extractPriorityNumber(a.entry) ??
            9999;
        const bPri =
            priorityScoreById[b.entry.id] ??
            extractPriorityNumber(b.entry) ??
            9999;
        if (aPri !== bPri) return aPri - bPri;

        // 4) Title
        const at = cleanSortTitle(a.entry);
        const bt = cleanSortTitle(b.entry);
        if (at < bt) return -1;
        if (at > bt) return 1;

        // 5) Deterministic tie-breaker
        return a.entry.id - b.entry.id;
    }

    function isPlanRoot(entry: ProgressEntryWithWbs): boolean {
        if (entry.wbs_meta?.entity_type === "project") return true;
        const d = entry.description.trim().toLowerCase();
        return d.startsWith("[plan]") || d.startsWith("plan:");
    }

    function planDisplayTitle(entry: ProgressEntryWithWbs): string {
        const wbsTitle = entry.wbs_meta?.title;
        if (wbsTitle) return wbsTitle;

        const trimmed = entry.description.trim();
        const lower = trimmed.toLowerCase();

        let title = trimmed;
        if (lower.startsWith("[plan]"))
            title = trimmed.slice("[plan]".length).trim();
        else if (lower.startsWith("plan:"))
            title = trimmed.slice("plan:".length).trim();

        const lowerTitle = title.toLowerCase();
        const derivedIdx = lowerTitle.indexOf(" (derived from");
        if (derivedIdx >= 0) title = title.slice(0, derivedIdx).trim();

        return title;
    }

    function enrichEntriesWithWbs(
        entries: ConportProgressEntry[],
    ): ProgressEntryWithWbs[] {
        return entries.map((e) => ({
            ...e,
            wbs_meta: wbsMetaMap.get(e.id),
        }));
    }

    function buildTree(
        entries: ProgressEntryWithWbs[],
    ): ProgressTreeNodeWithWbs[] {
        const nodes: Record<number, ProgressTreeNodeWithWbs> = {};

        for (const e of entries) {
            nodes[e.id] = { entry: e, children: [] };
        }

        const roots: ProgressTreeNodeWithWbs[] = [];
        for (const node of Object.values(nodes)) {
            const parentId = node.entry.parent_id;
            const parent = parentId != null ? nodes[parentId] : undefined;
            if (parent) parent.children.push(node);
            else roots.push(node);
        }

        priorityScoreById = {};
        const computePriority = (node: ProgressTreeNodeWithWbs): number => {
            let best = extractPriorityNumber(node.entry) ?? 9999;
            for (const c of node.children) {
                const childBest = computePriority(c);
                if (childBest < best) best = childBest;
            }
            priorityScoreById[node.entry.id] = best;
            return best;
        };
        for (const r of roots) computePriority(r);

        const sortRecursive = (arr: ProgressTreeNodeWithWbs[]) => {
            arr.sort(compareTreeNodes);
            for (const n of arr) sortRecursive(n.children);
        };
        sortRecursive(roots);

        return roots;
    }

    function mergeProgressEntries(
        base: ProgressEntryWithWbs[],
        extra: ConportProgressEntry[],
    ): ProgressEntryWithWbs[] {
        const byId: Record<number, ProgressEntryWithWbs> = {};
        for (const e of base) byId[e.id] = e;
        for (const e of extra) {
            byId[e.id] = {
                ...e,
                wbs_meta: wbsMetaMap.get(e.id),
            };
        }
        return Object.values(byId);
    }

    function extractPhaseIdFromEntries(
        entries: ProgressEntryWithWbs[],
        phaseNumber: number,
    ): number | null {
        // Check WBS metadata first
        for (const e of entries) {
            if (e.wbs_meta?.entity_type === "phase") {
                const phaseMatch = e.wbs_meta.title.match(/phase\s*(\d+)/i);
                if (phaseMatch && Number(phaseMatch[1]) === phaseNumber) {
                    return e.id;
                }
            }
        }

        // Fallback to description parsing
        const re = new RegExp(
            `\\b(?:phase\\s*${phaseNumber}\\s*[—–-_]|phase${phaseNumber}\\s*[—–-_])`,
            "i",
        );
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

    function partitionTreeByLane(nodes: ProgressTreeNodeWithWbs[]): {
        lanes: Record<LaneStatus, ProgressTreeNodeWithWbs[]>;
        counts: Record<LaneStatus, number>;
    } {
        const lanes: Record<LaneStatus, ProgressTreeNodeWithWbs[]> = {
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
            node: ProgressTreeNodeWithWbs,
            lane: LaneStatus,
        ): ProgressTreeNodeWithWbs => {
            counts[lane] += 1;
            return {
                entry: node.entry,
                children: node.children.map((c: ProgressTreeNodeWithWbs) =>
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

            // Fetch WBS metadata first
            const wbsResp = await conportCustomDataList(fetch, {
                category: "wbs_meta",
                app_id,
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
            const initialEntries = (list as ConportProgressListResponse)
                .progress_entries;

            treeEntries = enrichEntriesWithWbs(initialEntries);

            // Backfill phase entries

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

            // Get unique phase numbers
            const phaseNumbers: number[] = [];
            for (const e of treeEntries) {
                if (e.wbs_meta?.entity_type === "phase") {
                    const match = e.wbs_meta.title.match(/phase\s*(\d+)/i);
                    if (match) {
                        const num = Number(match[1]);
                        if (!phaseNumbers.includes(num)) phaseNumbers.push(num);
                    }
                }
            }
            phaseNumbers.sort((a, b) => a - b);

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
                        conportProgressList(fetch, {
                            parent_id: null,
                            description_prefix: `Phase ${phaseNumber}:`,
                            limit: 50,
                            app_id,
                            db,
                        }),
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
                    // Don't modify the phase entry itself - only attach notes TO the phase
                    if (n.id === phaseId)
                        return { ...n, wbs_meta: wbsMetaMap.get(n.id) };
                    if (n.parent_id == null && re.test(n.description)) {
                        return {
                            ...n,
                            parent_id: phaseId,
                            wbs_meta: wbsMetaMap.get(n.id),
                        };
                    }
                    return { ...n, wbs_meta: wbsMetaMap.get(n.id) };
                });

                treeEntries = mergeProgressEntries(treeEntries, attachedNotes);
            }

            tree = buildTree(treeEntries);

            let planRoot = tree.find((n) => isPlanRoot(n.entry)) ?? null;
            if (
                planRoot == null &&
                tree.length === 1 &&
                tree[0].children.length > 0
            ) {
                planRoot = tree[0];
            } else if (planRoot == null && tree.length > 1) {
                let best: ProgressTreeNodeWithWbs | null = null;
                for (const n of tree) {
                    if (
                        best == null ||
                        n.children.length > best.children.length
                    )
                        best = n;
                }
                if (best != null && best.children.length >= 2) planRoot = best;
            }

            planTitle = planRoot ? planDisplayTitle(planRoot.entry) : null;

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
                            WBS v1.0 • {wbsMetaMap.size} records with metadata
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
