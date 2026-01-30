<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import {
        contextMetricsByType,
        contextMetricsDaily,
        contextMetricsErrors,
        contextMetricsHourly,
        contextMetricsRoi,
        contextMetricsTopCost,
        type ContextMetricsByTypeRow,
        type ContextMetricsDailyRow,
        type ContextMetricsErrorsRow,
        type ContextMetricsHourlyRow,
        type ContextMetricsRoiStats,
        type ContextMetricsTopCostRow,
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
    let days = $state<number>(30);
    let sinceHours = $state<number>(24 * 7);

    let maxRows = $state<number>(10_000);
    let topLimit = $state<number>(50);

    // Data
    let roi = $state<ContextMetricsRoiStats | null>(null);
    let daily = $state<ContextMetricsDailyRow[]>([]);
    let byType = $state<ContextMetricsByTypeRow[]>([]);
    let hourly = $state<ContextMetricsHourlyRow[]>([]);
    let errors = $state<ContextMetricsErrorsRow[]>([]);
    let topCost = $state<ContextMetricsTopCostRow[]>([]);

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
            const [
                roiResp,
                dailyResp,
                byTypeResp,
                hourlyResp,
                errorsResp,
                topCostResp,
            ] = await Promise.all([
                contextMetricsRoi(fetch, {
                    app_id: effectiveAppId(),
                    project_id: effectiveProjectId(),
                    provider: effectiveProvider(),
                    model: effectiveModel(),
                    since_days: sinceDays,
                    max_rows: maxRows,
                }),
                contextMetricsDaily(fetch, {
                    app_id: effectiveAppId(),
                    project_id: effectiveProjectId(),
                    provider: effectiveProvider(),
                    model: effectiveModel(),
                    days,
                    max_rows: maxRows,
                }),
                contextMetricsByType(fetch, {
                    app_id: effectiveAppId(),
                    project_id: effectiveProjectId(),
                    provider: effectiveProvider(),
                    model: effectiveModel(),
                    days,
                    max_rows: maxRows,
                }),
                contextMetricsHourly(fetch, {
                    app_id: effectiveAppId(),
                    project_id: effectiveProjectId(),
                    provider: effectiveProvider(),
                    model: effectiveModel(),
                    since_hours: sinceHours,
                    max_rows: maxRows,
                }),
                contextMetricsErrors(fetch, {
                    app_id: effectiveAppId(),
                    project_id: effectiveProjectId(),
                    provider: effectiveProvider(),
                    model: effectiveModel(),
                    days,
                    max_rows: maxRows,
                }),
                contextMetricsTopCost(fetch, {
                    app_id: effectiveAppId(),
                    project_id: effectiveProjectId(),
                    provider: effectiveProvider(),
                    model: effectiveModel(),
                    since_days: sinceDays,
                    limit: topLimit,
                }),
            ]);

            roi = roiResp.stats ?? null;
            daily = dailyResp.rows ?? [];
            byType = byTypeResp.rows ?? [];
            hourly = hourlyResp.rows ?? [];
            errors = errorsResp.rows ?? [];
            topCost = topCostResp.rows ?? [];
        } catch (e) {
            error = e instanceof Error ? e.message : String(e);
            roi = null;
            daily = [];
            byType = [];
            hourly = [];
            errors = [];
            topCost = [];
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        if (!appIdOverride.trim() && scopedAppId) {
            appIdOverride = scopedAppId;
        }
        void refresh();
    });
</script>

<svelte:head>
    <title>Context Metrics</title>
</svelte:head>

<main class="page-container">
    <header class="page-header">
        <div>
            <h1 class="page-title">Context Metrics</h1>
            <p class="page-subtitle">
                Condensation effectiveness metrics derived from model-proxy
                request logs.
            </p>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-2">
            <button class="btn" onclick={refresh} disabled={loading}>
                {loading ? "Loading…" : "Refresh"}
            </button>
        </div>
    </header>

    <section class="card">
        <h2 class="card-title">Filters</h2>

        <div class="mt-2 text-sm text-gray-200">
            URL scope app_id:
            <code
                class="rounded bg-white/5 px-1.5 py-0.5 text-xs text-gray-300"
            >
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
                    Blank falls back to URL scope (if set). For model-proxy new
                    schema, a digits-only value is treated as numeric app_id;
                    otherwise it may match project_id depending on backend.
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
                <label class="text-xs text-gray-300/80" for="cm-model"
                    >model</label
                >
                <input
                    id="cm-model"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    placeholder="(optional)"
                    bind:value={model}
                />
            </div>

            <div>
                <label class="text-xs text-gray-300/80" for="cm-since-days"
                    >since_days (ROI / Top cost)</label
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
                <label class="text-xs text-gray-300/80" for="cm-days"
                    >days (daily/by-type/errors)</label
                >
                <input
                    id="cm-days"
                    type="number"
                    min="1"
                    max="365"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    bind:value={days}
                />
            </div>

            <div>
                <label class="text-xs text-gray-300/80" for="cm-since-hours"
                    >since_hours (hourly)</label
                >
                <input
                    id="cm-since-hours"
                    type="number"
                    min="1"
                    max="8760"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    bind:value={sinceHours}
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

            <div>
                <label class="text-xs text-gray-300/80" for="cm-top-limit"
                    >top_cost limit</label
                >
                <input
                    id="cm-top-limit"
                    type="number"
                    min="1"
                    max="200"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    bind:value={topLimit}
                />
            </div>

            <div class="md:col-span-3">
                <button
                    class="btn btn-primary"
                    type="submit"
                    disabled={loading}
                >
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
                    (from <code>metadata.context_tokens_saved</code>)
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
        <h2 class="card-title">
            Condensation breakdown (rules / code JIT / context)
        </h2>

        <div class="mt-4 overflow-auto rounded-lg border border-white/10">
            <table class="min-w-full text-left text-xs text-gray-200">
                <thead class="bg-black/20 text-gray-300">
                    <tr>
                        <th class="px-3 py-2">Date</th>
                        <th class="px-3 py-2">Model</th>
                        <th class="px-3 py-2">Req</th>
                        <th class="px-3 py-2">Rules</th>
                        <th class="px-3 py-2">Avg rules tok</th>
                        <th class="px-3 py-2">Code JIT</th>
                        <th class="px-3 py-2">Avg code tok</th>
                        <th class="px-3 py-2">Condensed</th>
                        <th class="px-3 py-2">Avg saved</th>
                        <th class="px-3 py-2">Avg prompt</th>
                        <th class="px-3 py-2">Avg cost</th>
                    </tr>
                </thead>
                <tbody>
                    {#if !loading && byType.length === 0}
                        <tr class="border-t border-white/10">
                            <td class="px-3 py-2 text-gray-300" colspan="11">
                                No rows for this scope/time window.
                            </td>
                        </tr>
                    {:else}
                        {#each byType as r (r.date + r.model)}
                            <tr class="border-t border-white/10">
                                <td
                                    class="px-3 py-2 font-mono text-[11px] whitespace-nowrap"
                                >
                                    {r.date}
                                </td>
                                <td class="px-3 py-2 font-mono text-[11px]"
                                    >{r.model}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.total_requests)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.rules_injected_count)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.avg_rules_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.code_jit_count)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.avg_code_jit_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.condensed_count)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.avg_tokens_saved)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.avg_prompt_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtUsd(r.avg_cost_usd, 6)}</td
                                >
                            </tr>
                        {/each}
                    {/if}
                </tbody>
            </table>
        </div>
    </section>

    <section class="card mt-6">
        <h2 class="card-title">Daily prompt token trends</h2>

        <div class="mt-4 overflow-auto rounded-lg border border-white/10">
            <table class="min-w-full text-left text-xs text-gray-200">
                <thead class="bg-black/20 text-gray-300">
                    <tr>
                        <th class="px-3 py-2">Date</th>
                        <th class="px-3 py-2">Model</th>
                        <th class="px-3 py-2">Req</th>
                        <th class="px-3 py-2">Avg prompt</th>
                        <th class="px-3 py-2">Median</th>
                        <th class="px-3 py-2">P95</th>
                        <th class="px-3 py-2">Max</th>
                        <th class="px-3 py-2">Avg completion</th>
                        <th class="px-3 py-2">Avg cost</th>
                        <th class="px-3 py-2">Total cost</th>
                    </tr>
                </thead>
                <tbody>
                    {#if !loading && daily.length === 0}
                        <tr class="border-t border-white/10">
                            <td class="px-3 py-2 text-gray-300" colspan="10">
                                No rows for this scope/time window.
                            </td>
                        </tr>
                    {:else}
                        {#each daily as r (r.date + r.model)}
                            <tr class="border-t border-white/10">
                                <td
                                    class="px-3 py-2 font-mono text-[11px] whitespace-nowrap"
                                >
                                    {r.date}
                                </td>
                                <td class="px-3 py-2 font-mono text-[11px]"
                                    >{r.model}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.request_count)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.avg_prompt_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.median_prompt_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.p95_prompt_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.max_prompt_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.avg_completion_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtUsd(r.avg_cost_usd, 6)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtUsd(r.total_cost_usd)}</td
                                >
                            </tr>
                        {/each}
                    {/if}
                </tbody>
            </table>
        </div>
    </section>

    <section class="card mt-6">
        <h2 class="card-title">Hourly usage</h2>

        <div class="mt-4 overflow-auto rounded-lg border border-white/10">
            <table class="min-w-full text-left text-xs text-gray-200">
                <thead class="bg-black/20 text-gray-300">
                    <tr>
                        <th class="px-3 py-2">Hour</th>
                        <th class="px-3 py-2">Model</th>
                        <th class="px-3 py-2">Req</th>
                        <th class="px-3 py-2">Avg prompt</th>
                        <th class="px-3 py-2">Total cost</th>
                        <th class="px-3 py-2">Avg latency</th>
                    </tr>
                </thead>
                <tbody>
                    {#if !loading && hourly.length === 0}
                        <tr class="border-t border-white/10">
                            <td class="px-3 py-2 text-gray-300" colspan="6">
                                No rows for this scope/time window.
                            </td>
                        </tr>
                    {:else}
                        {#each hourly as r (r.hour + r.model)}
                            <tr class="border-t border-white/10">
                                <td
                                    class="px-3 py-2 font-mono text-[11px] whitespace-nowrap"
                                >
                                    {r.hour}
                                </td>
                                <td class="px-3 py-2 font-mono text-[11px]"
                                    >{r.model}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.request_count)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.avg_prompt_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtUsd(r.total_cost_usd)}</td
                                >
                                <td class="px-3 py-2 font-mono">
                                    {r.avg_latency_ms == null
                                        ? "—"
                                        : `${Math.round(r.avg_latency_ms)}ms`}
                                </td>
                            </tr>
                        {/each}
                    {/if}
                </tbody>
            </table>
        </div>
    </section>

    <section class="card mt-6">
        <h2 class="card-title">Errors / stability</h2>

        <div class="mt-4 overflow-auto rounded-lg border border-white/10">
            <table class="min-w-full text-left text-xs text-gray-200">
                <thead class="bg-black/20 text-gray-300">
                    <tr>
                        <th class="px-3 py-2">Date</th>
                        <th class="px-3 py-2">Total</th>
                        <th class="px-3 py-2">Errors</th>
                        <th class="px-3 py-2">Error rate</th>
                        <th class="px-3 py-2">400</th>
                        <th class="px-3 py-2">429</th>
                        <th class="px-3 py-2">5xx</th>
                        <th class="px-3 py-2">Avg latency</th>
                    </tr>
                </thead>
                <tbody>
                    {#if !loading && errors.length === 0}
                        <tr class="border-t border-white/10">
                            <td class="px-3 py-2 text-gray-300" colspan="8">
                                No rows for this scope/time window.
                            </td>
                        </tr>
                    {:else}
                        {#each errors as r (r.date)}
                            <tr class="border-t border-white/10">
                                <td
                                    class="px-3 py-2 font-mono text-[11px] whitespace-nowrap"
                                >
                                    {r.date}
                                </td>
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.total_requests)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.error_count)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtPct(r.error_rate_pct, 2)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.bad_request_errors)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.rate_limit_errors)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.server_errors)}</td
                                >
                                <td class="px-3 py-2 font-mono">
                                    {r.avg_latency_ms == null
                                        ? "—"
                                        : `${Math.round(r.avg_latency_ms)}ms`}
                                </td>
                            </tr>
                        {/each}
                    {/if}
                </tbody>
            </table>
        </div>
    </section>

    <section class="card mt-6">
        <h2 class="card-title">Top cost requests (optimization targets)</h2>

        <div class="mt-4 overflow-auto rounded-lg border border-white/10">
            <table class="min-w-full text-left text-xs text-gray-200">
                <thead class="bg-black/20 text-gray-300">
                    <tr>
                        <th class="px-3 py-2">When</th>
                        <th class="px-3 py-2">Provider</th>
                        <th class="px-3 py-2">Model</th>
                        <th class="px-3 py-2">Prompt</th>
                        <th class="px-3 py-2">Completion</th>
                        <th class="px-3 py-2">Cost</th>
                        <th class="px-3 py-2">Latency</th>
                        <th class="px-3 py-2">Status</th>
                        <th class="px-3 py-2">Rules</th>
                        <th class="px-3 py-2">Condensed</th>
                        <th class="px-3 py-2">request_id</th>
                    </tr>
                </thead>
                <tbody>
                    {#if !loading && topCost.length === 0}
                        <tr class="border-t border-white/10">
                            <td class="px-3 py-2 text-gray-300" colspan="11">
                                No rows for this scope/time window.
                            </td>
                        </tr>
                    {:else}
                        {#each topCost as r (r.request_id)}
                            <tr class="border-t border-white/10">
                                <td
                                    class="px-3 py-2 font-mono text-[11px] whitespace-nowrap"
                                >
                                    {r.timestamp}
                                </td>
                                <td class="px-3 py-2">{r.provider ?? "—"}</td>
                                <td class="px-3 py-2 font-mono text-[11px]">
                                    {r.model ?? "—"}
                                </td>
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.prompt_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.completion_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtUsd(r.total_cost_usd, 6)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(r.duration_ms)}ms</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{r.status_code ?? "—"}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{r.rules_injected ? "yes" : "no"}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{r.context_condensed ? "yes" : "no"}</td
                                >
                                <td
                                    class="px-3 py-2 font-mono text-[11px] whitespace-nowrap"
                                >
                                    {r.request_id}
                                </td>
                            </tr>
                        {/each}
                    {/if}
                </tbody>
            </table>
        </div>
    </section>
</main>
