<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import {
        contextMetricsRequestDetails,
        contextMetricsRequestLookup,
        contextMetricsRoi,
        type ContextMetricsRequestDetailsResponse,
        type ContextMetricsRequestLookupRow,
        type ContextMetricsRoiStats,
    } from "$lib/api/contextMetrics";

    const scopedAppId = $derived(
        $page.url.searchParams.get("app_id") ?? undefined,
    );

    // Filters
    let appIdOverride = $state("");
    let projectId = $state("");
    let provider = $state("");
    let model = $state("");

    let sinceDays = $state<number>(7);
    let maxRows = $state<number>(10_000);

    // Data
    let roi = $state<ContextMetricsRoiStats | null>(null);

    // Drill-down
    let requestSearch = $state("");
    let requestLookupLoading = $state(false);
    let requestLookupError = $state<string | null>(null);
    let requestLookupRows = $state<ContextMetricsRequestLookupRow[]>([]);

    function rowKey(r: ContextMetricsRequestLookupRow): string {
        // Minimal schema should provide context_id; fall back to request_id for legacy schemas.
        const cid = typeof r.context_id === "string" ? r.context_id : "";
        return cid ? `${r.request_id}::${cid}` : r.request_id;
    }

    let expandedRowKey = $state<string | null>(null);

    let selectedRowKey = $state<string>("");
    let selectedRequestId = $state<string>("");
    let selectedContextId = $state<string | null>(null);
    let requestDetailsLoading = $state(false);
    let requestDetailsError = $state<string | null>(null);
    let requestDetails = $state<ContextMetricsRequestDetailsResponse | null>(
        null,
    );

    let loading = $state(false);
    let error = $state<string | null>(null);

    function effectiveAppId(): string | null {
        const v = appIdOverride.trim();
        if (v) return v;
        if (scopedAppId && scopedAppId.trim()) return scopedAppId.trim();
        return null;
    }

    function effectiveProjectId(): string | null {
        const v = projectId.trim();
        return v ? v : null;
    }

    function effectiveProvider(): string | null {
        const v = provider.trim();
        return v ? v : null;
    }

    function effectiveModel(): string | null {
        const v = model.trim();
        return v ? v : null;
    }

    function fmtInt(n: number | null | undefined): string {
        if (typeof n !== "number" || !Number.isFinite(n)) return "—";
        return Math.trunc(n).toLocaleString();
    }

    function toNumber(v: number | string | null | undefined): number | null {
        if (v == null) return null;
        if (typeof v === "number" && Number.isFinite(v)) return v;
        if (typeof v === "string" && v.trim()) {
            const parsed = Number(v);
            if (Number.isFinite(parsed)) return parsed;
        }
        return null;
    }

    function fmtUsd(v: number | string | null | undefined, digits = 4): string {
        const n = toNumber(v);
        if (n == null) return "—";
        return `$${n.toFixed(digits)}`;
    }

    function fmtPct(v: number | null | undefined, digits = 1): string {
        if (typeof v !== "number" || !Number.isFinite(v)) return "—";
        return `${v.toFixed(digits)}%`;
    }

    async function refresh(): Promise<void> {
        loading = true;
        error = null;

        try {
            const roiResp = await contextMetricsRoi(fetch, {
                app_id: effectiveAppId(),
                project_id: effectiveProjectId(),
                provider: effectiveProvider(),
                model: effectiveModel(),
                since_days: sinceDays,
                max_rows: maxRows,
            });

            roi = roiResp.stats ?? null;

            // Keep drill-down list in sync with filters (best-effort; don't fail the whole page)
            void refreshRequestLookup();
        } catch (e) {
            error = e instanceof Error ? e.message : String(e);
            roi = null;
        } finally {
            loading = false;
        }
    }

    async function refreshRequestLookup(): Promise<void> {
        requestLookupLoading = true;
        requestLookupError = null;

        try {
            const resp = await contextMetricsRequestLookup(fetch, {
                q: requestSearch.trim() ? requestSearch.trim() : null,
                app_id: effectiveAppId(),
                project_id: effectiveProjectId(),
                provider: effectiveProvider(),
                model: effectiveModel(),
                since_days: sinceDays,
                limit: 50,
            });
            requestLookupRows = resp.rows ?? [];
        } catch (e) {
            requestLookupError = e instanceof Error ? e.message : String(e);
            requestLookupRows = [];
        } finally {
            requestLookupLoading = false;
        }
    }

    async function loadRequestDetails(
        requestId: string,
        contextId: string | null,
        rk: string,
    ): Promise<void> {
        selectedRowKey = rk;
        selectedRequestId = requestId;
        selectedContextId = contextId;

        requestDetailsLoading = true;
        requestDetailsError = null;
        requestDetails = null;

        try {
            requestDetails = await contextMetricsRequestDetails(fetch, {
                request_id: requestId,
                context_id: contextId,
                include_payloads: true,
                include_messages: true,
                include_tools: true,
                include_tool_executions: true,
                max_child_rows: 500,
            });
        } catch (e) {
            requestDetailsError = e instanceof Error ? e.message : String(e);
            requestDetails = null;
        } finally {
            requestDetailsLoading = false;
        }
    }

    function toggleExpandedRow(r: ContextMetricsRequestLookupRow): void {
        const rk = rowKey(r);
        if (expandedRowKey === rk) {
            expandedRowKey = null;
            return;
        }

        expandedRowKey = rk;

        const cid =
            typeof r.context_id === "string" && r.context_id.trim()
                ? r.context_id.trim()
                : null;

        // Best-effort: only load details if not already the current one
        if (selectedRowKey !== rk) {
            void loadRequestDetails(r.request_id, cid, rk);
        }
    }

    function getRequestContextField(
        details: ContextMetricsRequestDetailsResponse | null,
        key: string,
    ): string | null {
        const ctx = (details as any)?.request_context;
        const v = ctx?.[key];
        return typeof v === "string" ? v : null;
    }

    function getRequestContextNumber(
        details: ContextMetricsRequestDetailsResponse | null,
        key: string,
    ): number | null {
        const ctx = (details as any)?.request_context;
        const v = ctx?.[key];
        return typeof v === "number" && Number.isFinite(v) ? v : null;
    }

    onMount(() => {
        if (!appIdOverride.trim() && scopedAppId) {
            appIdOverride = scopedAppId;
        }
        void refresh();
    });
</script>

<svelte:head>
    <title>Context Metrics — Summary</title>
</svelte:head>

<section class="card">
    <h2 class="card-title">Filters</h2>

    <div class="mt-2 text-sm text-gray-200">
        URL scope app_id:
        <code class="rounded bg-white/5 px-1.5 py-0.5 text-xs text-gray-300">
            {scopedAppId ?? "(none)"}
        </code>
    </div>

    <form
        class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3"
        onsubmit={(e) => {
            e.preventDefault();
            void refresh();
        }}
    >
        <div>
            <label class="text-xs text-gray-300/80" for="cm-app-id"
                >app_id</label
            >
            <input
                id="cm-app-id"
                class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                placeholder={scopedAppId ?? "(optional)"}
                bind:value={appIdOverride}
            />
            <div class="mt-1 text-xs text-gray-300/70">
                Blank falls back to URL scope (if set). <code>app_id</code> is
                typically the workspace/app slug (e.g.
                <code>mindscape-ai</code>).
            </div>
        </div>

        <div>
            <label class="text-xs text-gray-300/80" for="cm-project-id"
                >project_id</label
            >
            <input
                id="cm-project-id"
                class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                placeholder="(optional)"
                bind:value={projectId}
            />
        </div>

        <div>
            <label class="text-xs text-gray-300/80" for="cm-provider"
                >provider</label
            >
            <input
                id="cm-provider"
                class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                placeholder="(optional)"
                bind:value={provider}
            />
        </div>

        <div>
            <label class="text-xs text-gray-300/80" for="cm-model">model</label>
            <input
                id="cm-model"
                class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                placeholder="(optional)"
                bind:value={model}
            />
        </div>

        <div>
            <label class="text-xs text-gray-300/80" for="cm-since-days"
                >since_days (ROI / drill-down)</label
            >
            <input
                id="cm-since-days"
                type="number"
                min="1"
                max="365"
                class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                bind:value={sinceDays}
            />
        </div>

        <div>
            <label class="text-xs text-gray-300/80" for="cm-max-rows"
                >max_rows</label
            >
            <input
                id="cm-max-rows"
                type="number"
                min="100"
                max="20000"
                class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                bind:value={maxRows}
            />
            <div class="mt-1 text-xs text-gray-300/70">
                Backend aggregates in-memory; keep this reasonable.
            </div>
        </div>

        <div class="md:col-span-3">
            <button class="btn btn-primary" type="submit" disabled={loading}>
                {loading ? "Loading…" : "Apply"}
            </button>
        </div>
    </form>

    {#if error}
        <div
            class="mt-4 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-100"
        >
            {error}
        </div>
    {/if}
</section>

<section class="card mt-6">
    <h2 class="card-title">Condensation ROI (summary)</h2>

    <div class="mt-4 grid gap-3 md:grid-cols-4">
        <div class="rounded-lg border border-white/10 bg-black/10 p-3">
            <div
                class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
            >
                Requests
            </div>
            <div class="mt-2 text-sm text-gray-200">
                {fmtInt(roi?.total_requests)}
            </div>
            <div class="mt-1 text-xs text-gray-300/70">
                condensed: {fmtInt(roi?.condensed_requests)}
            </div>
        </div>

        <div class="rounded-lg border border-white/10 bg-black/10 p-3">
            <div
                class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
            >
                Condensation rate
            </div>
            <div class="mt-2 text-sm text-gray-200">
                {fmtPct(roi?.condensation_rate_pct)}
            </div>
            <div class="mt-1 text-xs text-gray-300/70">
                token reduction: {fmtPct(roi?.token_reduction_pct)}
            </div>
        </div>

        <div class="rounded-lg border border-white/10 bg-black/10 p-3">
            <div
                class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
            >
                Avg tokens saved
            </div>
            <div class="mt-2 text-sm text-gray-200">
                {fmtInt(roi?.avg_tokens_saved_per_request)}
            </div>
            <div class="mt-1 text-xs text-gray-300/70">
                (from <code>model_proxy_request_contexts.tokens_saved</code>)
            </div>
        </div>

        <div class="rounded-lg border border-white/10 bg-black/10 p-3">
            <div
                class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
            >
                Cost
            </div>
            <div class="mt-2 text-sm text-gray-200">
                total: {fmtUsd(roi?.total_cost_usd)}
            </div>
            <div class="mt-1 text-xs text-gray-300/70">
                est savings: {fmtUsd(roi?.estimated_savings_usd)}
            </div>
        </div>
    </div>

    <div class="mt-3 text-xs text-gray-300/70">
        Note: Estimated savings uses a flat <code>$0.000005/token</code> heuristic
        (matches the sample SQL). Adjust in backend if you want model-tier aware
        savings.
    </div>
</section>

<section class="card mt-6">
    <h2 class="card-title">Context Metrics (per-request drill-down)</h2>

    <div class="mt-2 text-sm text-gray-200">
        Click a row to expand and compare the raw vs condensed request contexts.
    </div>

    <form
        class="mt-4 flex flex-wrap items-end gap-2"
        onsubmit={(e) => {
            e.preventDefault();
            void refreshRequestLookup();
        }}
    >
        <div class="min-w-[260px]">
            <label class="text-xs text-gray-300/80" for="cm-req-search"
                >Search request_id</label
            >
            <input
                id="cm-req-search"
                class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                placeholder="req_… or UUID…"
                bind:value={requestSearch}
            />
        </div>

        <button class="btn" type="submit" disabled={requestLookupLoading}>
            {requestLookupLoading ? "Searching…" : "Search"}
        </button>

        <button
            class="btn"
            type="button"
            disabled={requestLookupLoading}
            onclick={() => {
                requestSearch = "";
                void refreshRequestLookup();
            }}
        >
            Clear
        </button>
    </form>

    {#if requestLookupError}
        <div
            class="mt-3 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-100"
        >
            {requestLookupError}
        </div>
    {/if}

    <div class="mt-4 overflow-auto rounded-lg border border-white/10">
        <table class="min-w-full text-left text-xs text-gray-200">
            <thead class="bg-black/20 text-gray-300">
                <tr>
                    <th class="px-3 py-2">request_id</th>
                    <th class="px-3 py-2">Inserted</th>
                    <th class="px-3 py-2">Provider</th>
                    <th class="px-3 py-2">Model</th>
                    <th class="px-3 py-2">Raw tok</th>
                    <th class="px-3 py-2">Condensed tok</th>
                    <th class="px-3 py-2">Saved</th>
                    <th class="px-3 py-2">Status</th>
                </tr>
            </thead>
            <tbody>
                {#if !requestLookupLoading && requestLookupRows.length === 0}
                    <tr class="border-t border-white/10">
                        <td class="px-3 py-2 text-gray-300" colspan="8">
                            No requests found for this scope/time window.
                        </td>
                    </tr>
                {:else}
                    {#each requestLookupRows as r (rowKey(r))}
                        <tr
                            class="border-t border-white/10 hover:bg-white/5 focus:bg-white/5 cursor-pointer"
                            tabindex="0"
                            role="button"
                            aria-expanded={expandedRowKey === rowKey(r)}
                            onclick={() => toggleExpandedRow(r)}
                            onkeydown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                    e.preventDefault();
                                    toggleExpandedRow(r);
                                }
                            }}
                        >
                            <td
                                class="px-3 py-2 font-mono text-[11px] whitespace-nowrap"
                            >
                                {r.request_id}
                            </td>
                            <td
                                class="px-3 py-2 font-mono text-[11px] whitespace-nowrap"
                            >
                                {r.timestamp
                                    ? new Date(r.timestamp)
                                          .toISOString()
                                          .slice(0, 16)
                                          .replace("T", " ")
                                    : "—"}
                            </td>
                            <td class="px-3 py-2">{r.provider ?? "—"}</td>
                            <td class="px-3 py-2 font-mono text-[11px]">
                                {r.model ?? "—"}
                            </td>
                            <td class="px-3 py-2 font-mono">
                                {fmtInt(r.raw_context_token_count ?? null)}
                            </td>
                            <td class="px-3 py-2 font-mono">
                                {fmtInt(
                                    r.condensed_context_token_count ?? null,
                                )}
                            </td>
                            <td class="px-3 py-2 font-mono">
                                {fmtInt(r.tokens_saved ?? null)}
                            </td>
                            <td class="px-3 py-2 font-mono">
                                {r.status_code ?? "—"}
                            </td>
                        </tr>

                        {#if expandedRowKey === rowKey(r)}
                            <tr class="border-t border-white/10">
                                <td class="px-3 py-3" colspan="8">
                                    {#if requestDetailsLoading && selectedRowKey === rowKey(r)}
                                        <div class="text-sm text-gray-200">
                                            Loading…
                                        </div>
                                    {:else if requestDetailsError && selectedRowKey === rowKey(r)}
                                        <div
                                            class="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-100"
                                        >
                                            {requestDetailsError}
                                        </div>
                                    {:else if requestDetails && selectedRowKey === rowKey(r)}
                                        <div
                                            class="text-xs text-gray-300/80 flex flex-wrap gap-3"
                                        >
                                            <div>
                                                method:
                                                <code
                                                    >{(requestDetails as any)
                                                        ?.request_context
                                                        ?.condensation_method ??
                                                        "—"}</code
                                                >
                                            </div>
                                            <div>
                                                version:
                                                <code
                                                    >{(requestDetails as any)
                                                        ?.request_context
                                                        ?.condensation_version ??
                                                        "—"}</code
                                                >
                                            </div>
                                            <div>
                                                trigger:
                                                <code
                                                    >{(requestDetails as any)
                                                        ?.request_context
                                                        ?.condensation_trigger ??
                                                        "—"}</code
                                                >
                                            </div>
                                            <div>
                                                tokens_saved:
                                                <code
                                                    >{fmtInt(
                                                        getRequestContextNumber(
                                                            requestDetails,
                                                            "tokens_saved",
                                                        ),
                                                    )}</code
                                                >
                                            </div>
                                        </div>

                                        <div
                                            class="mt-3 grid gap-3 md:grid-cols-2"
                                        >
                                            <div
                                                class="rounded-lg border border-white/10 bg-black/10 p-3"
                                            >
                                                <div
                                                    class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
                                                >
                                                    Raw request context
                                                </div>
                                                <pre
                                                    class="mt-2 max-h-[420px] overflow-auto rounded bg-black/30 p-2 text-[11px] text-gray-200">{getRequestContextField(
                                                        requestDetails,
                                                        "raw_request_context",
                                                    ) ?? "—"}</pre>
                                            </div>

                                            <div
                                                class="rounded-lg border border-white/10 bg-black/10 p-3"
                                            >
                                                <div
                                                    class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
                                                >
                                                    Condensed request context
                                                </div>
                                                <pre
                                                    class="mt-2 max-h-[420px] overflow-auto rounded bg-black/30 p-2 text-[11px] text-gray-200">{getRequestContextField(
                                                        requestDetails,
                                                        "condensed_request_context",
                                                    ) ?? "—"}</pre>
                                            </div>
                                        </div>
                                    {:else}
                                        <div class="text-sm text-gray-200">
                                            No details available for this
                                            request.
                                        </div>
                                    {/if}
                                </td>
                            </tr>
                        {/if}
                    {/each}
                {/if}
            </tbody>
        </table>
    </div>
</section>
