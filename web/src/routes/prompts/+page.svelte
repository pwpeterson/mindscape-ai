<script lang="ts">
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    import {
        connectPromptsStream,
        promptsFiles,
        promptsSignature,
        type PromptsFileRow,
        type PromptsFilesResponse,
        type PromptsSignatureResponse,
    } from "$lib/api/prompts";

    const appId = $derived($page.url.searchParams.get("app_id"));

    let loading = $state(true);
    let error = $state<string | null>(null);

    let signature = $state<string | null>(null);
    let fileCount = $state<number | null>(null);
    let configured = $state<boolean | null>(null);
    let lastChangedAt = $state<string | null>(null);

    let filesLoading = $state(false);
    let filesError = $state<string | null>(null);
    let files = $state<PromptsFileRow[]>([]);

    // Controls for per-file stats
    let maxFiles = $state<number>(500);
    let maxFileBytes = $state<number>(200_000);

    async function refreshFiles() {
        filesLoading = true;
        filesError = null;

        try {
            const resp: PromptsFilesResponse = await promptsFiles(fetch, {
                app_id: appId,
                max_files: maxFiles,
                max_file_bytes: maxFileBytes,
            });

            // Keep global configured/fileCount aligned when possible.
            configured = resp.configured;
            fileCount = resp.file_count;
            files = resp.files;
        } catch (err) {
            filesError = err instanceof Error ? err.message : String(err);
            files = [];
        } finally {
            filesLoading = false;
        }
    }

    async function refresh() {
        loading = true;
        error = null;

        try {
            const [sigResp, filesResp] = await Promise.all([
                promptsSignature(fetch, {
                    app_id: appId,
                }) as Promise<PromptsSignatureResponse>,
                promptsFiles(fetch, {
                    app_id: appId,
                    max_files: maxFiles,
                    max_file_bytes: maxFileBytes,
                }) as Promise<PromptsFilesResponse>,
            ]);

            signature = sigResp.signature;
            configured = sigResp.configured;

            // Prefer files endpoint for file_count since it reflects applied max_files.
            fileCount = filesResp.file_count;
            files = filesResp.files;
        } catch (err) {
            error = err instanceof Error ? err.message : String(err);
            signature = null;
            fileCount = null;
            configured = null;
            files = [];
        } finally {
            loading = false;
        }
    }

    onMount(() => {
        void refresh();

        // Browser-only: subscribe to prompt signature changes.
        const conn = connectPromptsStream(
            {
                onSignature: (ev) => {
                    signature = ev.data.signature;
                    fileCount = ev.data.file_count;
                    configured = true;
                    // Fetch file stats in the background so the table stays current.
                    void refreshFiles();
                },
                onChanged: (ev) => {
                    signature = ev.data.signature;
                    fileCount = ev.data.file_count;
                    lastChangedAt = ev.ts;
                    void refreshFiles();
                },
                onErrorEvent: (ev) => {
                    // Backend emitted an application-level error (e.g., unknown app_id).
                    error = ev.data.message;
                },
                onError: () => {
                    // Network-level error. Keep the last known signature and allow manual refresh.
                },
            },
            {
                app_id: appId,
                poll_seconds: 2,
            },
        );

        return () => conn.close();
    });
</script>

<svelte:head>
    <title>Prompts</title>
</svelte:head>

<main class="page-container">
    <header class="page-header">
        <div>
            <h1 class="page-title">Prompts</h1>
            <p class="page-subtitle">
                Prompt hot reload status (signature changes when prompt files
                change).
            </p>
        </div>

        <div class="flex items-center gap-2">
            <button
                class="btn"
                onclick={() => void refreshFiles()}
                disabled={filesLoading}
            >
                {filesLoading ? "Loading…" : "Refresh files"}
            </button>
            <button
                class="btn btn-primary"
                onclick={() => refresh()}
                disabled={loading}
            >
                {loading ? "Loading…" : "Refresh all"}
            </button>
        </div>
    </header>

    {#if error}
        <div
            class="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-100"
        >
            <div class="text-sm font-semibold">Error</div>
            <div class="mt-2 whitespace-pre-wrap text-sm text-red-100/90">
                {error}
            </div>
        </div>
    {/if}

    <section class="card">
        <h2 class="card-title">Current scope</h2>
        <div class="mt-2 text-sm text-gray-200">
            app_id:
            <code
                class="rounded bg-white/5 px-1.5 py-0.5 text-xs text-gray-300"
            >
                {appId ?? "(local/default)"}
            </code>
        </div>

        <div class="mt-4 grid gap-3 md:grid-cols-2">
            <div class="rounded-lg border border-white/10 bg-black/10 p-3">
                <div
                    class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
                >
                    Prompts directory
                </div>
                <div class="mt-2 text-sm text-gray-200">
                    {#if configured === null}
                        (unknown)
                    {:else if configured}
                        configured
                    {:else}
                        not configured (no prompts directory found)
                    {/if}
                </div>
            </div>

            <div class="rounded-lg border border-white/10 bg-black/10 p-3">
                <div
                    class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
                >
                    File count
                </div>
                <div class="mt-2 text-sm text-gray-200">
                    {fileCount ?? (loading ? "…" : "0")}
                </div>
            </div>

            <div
                class="rounded-lg border border-white/10 bg-black/10 p-3 md:col-span-2"
            >
                <div
                    class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
                >
                    Signature
                </div>
                <div class="mt-2 break-all font-mono text-xs text-gray-300">
                    {signature ?? (loading ? "…" : "(none)")}
                </div>
                {#if lastChangedAt}
                    <div class="mt-2 text-xs text-gray-300/80">
                        Last changed: <code>{lastChangedAt}</code>
                    </div>
                {/if}
            </div>
        </div>

        <p class="mt-4 text-sm text-gray-300">Next steps:</p>
        <ul class="mt-2 list-disc pl-5 text-sm text-gray-200">
            <li>UI: list/create/edit prompt templates in a library view</li>
            <li>
                Backend: add Supabase prompt store endpoints scoped by <code
                    >app_id</code
                >
            </li>
        </ul>
    </section>

    <section class="card mt-6">
        <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
                <h2 class="card-title">Prompt files</h2>
                <div class="mt-1 text-xs text-gray-300/80">
                    Approx tokens use chars/4 for text files. Files larger than <code
                        >{maxFileBytes}</code
                    > bytes skip deep stats.
                </div>
            </div>

            <form
                class="flex flex-wrap items-end gap-2"
                onsubmit={(e) => {
                    e.preventDefault();
                    void refreshFiles();
                }}
            >
                <label class="field w-[140px]">
                    <span class="field-label">max_files</span>
                    <input
                        type="number"
                        min="1"
                        max="5000"
                        bind:value={maxFiles}
                        class="input"
                    />
                </label>

                <label class="field w-[160px]">
                    <span class="field-label">max_file_bytes</span>
                    <input
                        type="number"
                        min="1000"
                        max="5000000"
                        bind:value={maxFileBytes}
                        class="input"
                    />
                </label>

                <button
                    type="submit"
                    class="btn btn-primary"
                    disabled={filesLoading}
                >
                    {filesLoading ? "Loading…" : "Apply"}
                </button>
            </form>
        </div>

        {#if filesError}
            <div
                class="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-100"
            >
                <div class="text-sm font-semibold">Error</div>
                <div class="mt-2 whitespace-pre-wrap text-sm text-red-100/90">
                    {filesError}
                </div>
            </div>
        {/if}

        {#if !filesLoading && files.length === 0}
            <p class="mt-4 text-sm text-gray-300">
                No files found for this scope.
            </p>
        {:else}
            <div class="mt-4 overflow-auto rounded-lg border border-white/10">
                <table class="min-w-full text-left text-xs text-gray-200">
                    <thead class="bg-black/20 text-gray-300">
                        <tr>
                            <th class="px-3 py-2">Path</th>
                            <th class="px-3 py-2">Bytes</th>
                            <th class="px-3 py-2">Chars</th>
                            <th class="px-3 py-2">Lines</th>
                            <th class="px-3 py-2">Approx tokens</th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each files as f (f.path)}
                            <tr class="border-t border-white/10">
                                <td
                                    class="px-3 py-2 font-mono text-[11px] whitespace-nowrap"
                                >
                                    {f.path}
                                </td>
                                <td class="px-3 py-2">{f.bytes}</td>
                                <td class="px-3 py-2">
                                    {f.char_count ?? "—"}
                                </td>
                                <td class="px-3 py-2">
                                    {f.line_count ?? "—"}
                                </td>
                                <td class="px-3 py-2">
                                    {f.approx_tokens ?? "—"}
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        {/if}
    </section>
</main>
