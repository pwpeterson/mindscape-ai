<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import {
        llmUsageDaily,
        llmUsageEvents,
        type LlmUsageDailyResponse,
        type LlmUsageDailyRow,
        type LlmUsageEventRow,
        type LlmUsageEventsResponse,
    } from "$lib/api/llmUsage";

    const scopedAppId = $derived(
        $page.url.searchParams.get("app_id") ?? undefined,
    );

    // Filters
    let appIdOverride = $state("");
    let provider = $state("");
    let model = $state("");
    let sinceHours = $state<number>(24);
    let limit = $state<number>(50);
    let days = $state<number>(30);

    // Data
    let events = $state<LlmUsageEventRow[]>([]);
    let daily = $state<LlmUsageDailyRow[]>([]);
    let loading = $state(false);
    let error = $state<string | null>(null);

    const summary = $derived(summarizeEvents(events));

    function effectiveAppId(): string | null {
        const v = appIdOverride.trim();
        if (v) return v;
        if (scopedAppId && scopedAppId.trim()) return scopedAppId.trim();
        return null;
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

    function fmtUsd(v: number | string | null | undefined): string {
        const n = toNumber(v);
        if (n == null) return "—";
        return `$${n.toFixed(4)}`;
    }

    function summarizeEvents(events: LlmUsageEventRow[]): {
        requests: number;
        totalTokens: number;
        inputTokens: number;
        outputTokens: number;
        estimatedCost: number | null;
        avgLatencyMs: number | null;
        errorCount: number;
    } {
        let requests = 0;
        let totalTokens = 0;
        let inputTokens = 0;
        let outputTokens = 0;
        let estimatedCost = 0;

        let latencySum = 0;
        let latencyCount = 0;

        let errorCount = 0;

        for (const ev of events) {
            requests += 1;
            totalTokens += Number(ev.total_tokens ?? 0) || 0;
            inputTokens += Number(ev.input_tokens ?? 0) || 0;
            outputTokens += Number(ev.output_tokens ?? 0) || 0;

            const c = toNumber(ev.estimated_cost);
            if (c != null) estimatedCost += c;

            const lat = ev.latency_ms;
            if (typeof lat === "number" && Number.isFinite(lat)) {
                latencySum += lat;
                latencyCount += 1;
            }

            const status = ev.status_code;
            if (typeof status === "number" && status >= 400) errorCount += 1;
        }

        return {
            requests,
            totalTokens,
            inputTokens,
            outputTokens,
            estimatedCost: requests ? estimatedCost : null,
            avgLatencyMs: latencyCount ? latencySum / latencyCount : null,
            errorCount,
        };
    }

    async function refresh(): Promise<void> {
        loading = true;
        error = null;

        try {
            const [eventsResp, dailyResp] = await Promise.all([
                llmUsageEvents(fetch, {
                    app_id: effectiveAppId(),
                    provider: effectiveProvider(),
                    model: effectiveModel(),
                    since_hours: sinceHours,
                    limit,
                }) as Promise<LlmUsageEventsResponse>,
                llmUsageDaily(fetch, {
                    app_id: effectiveAppId(),
                    provider: effectiveProvider(),
                    model: effectiveModel(),
                    days,
                    limit: days,
                }) as Promise<LlmUsageDailyResponse>,
            ]);

            events = eventsResp.events ?? [];
            daily = dailyResp.rows ?? [];
        } catch (e) {
            error = e instanceof Error ? e.message : String(e);
            events = [];
            daily = [];
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
    <title>Tokens</title>
</svelte:head>

<main class="page-container">
    <header class="page-header">
        <div>
            <h1 class="page-title">Token usage</h1>
            <p class="page-subtitle">
                Model-proxy token analytics from Supabase (<code
                    >model_proxy_requests</code
                >
                /
                <code>model_proxy_daily_stats</code>).
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
                <label class="text-xs text-gray-300/80" for="tokens-app-id"
                    >app_id</label
                >
                <input
                    id="tokens-app-id"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    placeholder={scopedAppId ?? "mindscape-ai"}
                    bind:value={appIdOverride}
                />
                <div class="mt-1 text-xs text-gray-300/70">
                    Blank falls back to URL scope (if set).
                </div>
            </div>

            <div>
                <label class="text-xs text-gray-300/80" for="tokens-provider"
                    >provider</label
                >
                <input
                    id="tokens-provider"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    placeholder="(optional)"
                    bind:value={provider}
                />
            </div>

            <div>
                <label class="text-xs text-gray-300/80" for="tokens-model"
                    >model</label
                >
                <input
                    id="tokens-model"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    placeholder="(optional)"
                    bind:value={model}
                />
            </div>

            <div>
                <label class="text-xs text-gray-300/80" for="tokens-since-hours"
                    >since_hours</label
                >
                <input
                    id="tokens-since-hours"
                    type="number"
                    min="0"
                    max="8760"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    bind:value={sinceHours}
                />
            </div>

            <div>
                <label class="text-xs text-gray-300/80" for="tokens-limit"
                    >limit</label
                >
                <input
                    id="tokens-limit"
                    type="number"
                    min="1"
                    max="500"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    bind:value={limit}
                />
            </div>

            <div>
                <label class="text-xs text-gray-300/80" for="tokens-days"
                    >days</label
                >
                <input
                    id="tokens-days"
                    type="number"
                    min="1"
                    max="365"
                    class="mt-1 w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-400 focus:outline-none"
                    bind:value={days}
                />
                <div class="mt-1 text-xs text-gray-300/70">
                    Applies to daily rollups.
                </div>
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
        <h2 class="card-title">Summary (recent)</h2>

        <div class="mt-4 grid gap-3 md:grid-cols-4">
            <div class="rounded-lg border border-white/10 bg-black/10 p-3">
                <div
                    class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
                >
                    Requests
                </div>
                <div class="mt-2 text-sm text-gray-200">
                    {fmtInt(summary.requests)}
                </div>
                <div class="mt-1 text-xs text-gray-300/70">
                    errors: {fmtInt(summary.errorCount)}
                </div>
            </div>

            <div class="rounded-lg border border-white/10 bg-black/10 p-3">
                <div
                    class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
                >
                    Total tokens
                </div>
                <div class="mt-2 text-sm text-gray-200">
                    {fmtInt(summary.totalTokens)}
                </div>
                <div class="mt-1 text-xs text-gray-300/70">
                    in: {fmtInt(summary.inputTokens)} / out: {fmtInt(
                        summary.outputTokens,
                    )}
                </div>
            </div>

            <div class="rounded-lg border border-white/10 bg-black/10 p-3">
                <div
                    class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
                >
                    Estimated cost
                </div>
                <div class="mt-2 text-sm text-gray-200">
                    {fmtUsd(summary.estimatedCost)}
                </div>
            </div>

            <div class="rounded-lg border border-white/10 bg-black/10 p-3">
                <div
                    class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
                >
                    Avg latency
                </div>
                <div class="mt-2 text-sm text-gray-200">
                    {summary.avgLatencyMs == null
                        ? "—"
                        : `${Math.round(summary.avgLatencyMs)}ms`}
                </div>
            </div>
        </div>
    </section>

    <section class="card mt-6">
        <h2 class="card-title">Recent requests</h2>

        <div class="mt-4 overflow-auto rounded-lg border border-white/10">
            <table class="min-w-full text-left text-xs text-gray-200">
                <thead class="bg-black/20 text-gray-300">
                    <tr>
                        <th class="px-3 py-2">Created</th>
                        <th class="px-3 py-2">Provider</th>
                        <th class="px-3 py-2">Model</th>
                        <th class="px-3 py-2">Task</th>
                        <th class="px-3 py-2">Tokens</th>
                        <th class="px-3 py-2">Cost</th>
                        <th class="px-3 py-2">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {#if !loading && events.length === 0}
                        <tr class="border-t border-white/10">
                            <td class="px-3 py-2 text-gray-300" colspan="7">
                                No requests found for this scope/time window.
                            </td>
                        </tr>
                    {:else}
                        {#each events as ev (ev.request_id)}
                            <tr class="border-t border-white/10">
                                <td
                                    class="px-3 py-2 font-mono text-[11px] whitespace-nowrap"
                                >
                                    {ev.created_at}
                                </td>
                                <td class="px-3 py-2">{ev.provider}</td>
                                <td class="px-3 py-2 font-mono text-[11px]"
                                    >{ev.model}</td
                                >
                                <td class="px-3 py-2">{ev.task ?? "—"}</td>
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(ev.total_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtUsd(ev.estimated_cost)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{ev.status_code ?? "—"}</td
                                >
                            </tr>
                        {/each}
                    {/if}
                </tbody>
            </table>
        </div>
    </section>

    <section class="card mt-6">
        <h2 class="card-title">Daily rollups</h2>

        <div class="mt-4 overflow-auto rounded-lg border border-white/10">
            <table class="min-w-full text-left text-xs text-gray-200">
                <thead class="bg-black/20 text-gray-300">
                    <tr>
                        <th class="px-3 py-2">Day</th>
                        <th class="px-3 py-2">Requests</th>
                        <th class="px-3 py-2">Tokens</th>
                        <th class="px-3 py-2">Cost</th>
                    </tr>
                </thead>
                <tbody>
                    {#if !loading && daily.length === 0}
                        <tr class="border-t border-white/10">
                            <td class="px-3 py-2 text-gray-300" colspan="4"
                                >No daily rollups found.</td
                            >
                        </tr>
                    {:else}
                        {#each daily as row (row.day)}
                            <tr class="border-t border-white/10">
                                <td
                                    class="px-3 py-2 font-mono text-[11px] whitespace-nowrap"
                                >
                                    {row.day}
                                </td>
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(row.requests)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtInt(row.total_tokens)}</td
                                >
                                <td class="px-3 py-2 font-mono"
                                    >{fmtUsd(row.estimated_cost)}</td
                                >
                            </tr>
                        {/each}
                    {/if}
                </tbody>
            </table>
        </div>

        <div class="mt-2 text-xs text-gray-300/70">
            Note: daily rollups are from a materialized view and may require
            refresh if you just loaded new data.
        </div>
    </section>
</main>
