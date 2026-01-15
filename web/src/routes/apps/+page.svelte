<script lang="ts">
    import { page } from "$app/stores";
    import {
        createApp,
        deleteApp,
        listAppsRegistry,
        patchApp,
        type AppsRegistryResponse,
        type CreateAppRequest,
    } from "$lib/api/apps";
    import { onMount } from "svelte";

    type RowEditState = {
        display_name: string;
        sort_order: number;
        enabled: boolean;
        // Current root_path from registry + editable root_path (shown in input)
        root_path_original: string;
        root_path: string;
        saving: boolean;
        error: string | null;
    };

    let loading = $state(false);
    let error = $state<string | null>(null);
    let source = $state<AppsRegistryResponse["source"] | null>(null);

    let apps = $state<AppsRegistryResponse["apps"]>([]);
    let edits = $state<Record<string, RowEditState>>({});

    let creating = $state(false);
    let createError = $state<string | null>(null);

    // Form state (bindings must be assignable l-values; avoid `as any` in bind targets)
    let form_app_id = $state("");
    let form_display_name = $state("");
    let form_root_path = $state("");
    let form_enabled = $state(true);
    let form_sort_order = $state(0);

    function currentScopeQuery(): string {
        // Preserve app scoping if user navigated here with ?app_id=... (or legacy db)
        const app_id = $page.url.searchParams.get("app_id");
        const db = $page.url.searchParams.get("db");
        const url = new URL("/apps", "http://local");
        if (app_id) {
            url.searchParams.set("app_id", app_id);
            url.searchParams.delete("db");
        } else if (db) {
            url.searchParams.set("db", db);
        }
        return url.search;
    }

    function ensureRowState(app_id: string): RowEditState {
        if (!edits[app_id]) {
            edits = {
                ...edits,
                [app_id]: {
                    display_name: "",
                    sort_order: 0,
                    enabled: true,
                    root_path_original: "",
                    root_path: "",
                    saving: false,
                    error: null,
                },
            };
        }
        return edits[app_id];
    }

    function setRow(app_id: string, patch: Partial<RowEditState>) {
        edits = {
            ...edits,
            [app_id]: { ...ensureRowState(app_id), ...patch },
        };
    }

    async function refresh() {
        loading = true;
        error = null;
        try {
            const resp = await listAppsRegistry(fetch);
            apps = resp.apps;
            source = resp.source;

            // Sensible default: new apps appended after existing ones.
            // Only set when the user hasn't started entering a custom sort order.
            if (!creating && Number(form_sort_order) === 0) {
                form_sort_order = apps.length + 1;
            }

            // Initialize edit state from the Supabase registry response (all fields present).
            for (const a of apps) {
                setRow(a.app_id, {
                    display_name:
                        typeof a.display_name === "string" &&
                        a.display_name.trim()
                            ? a.display_name
                            : a.app_id,
                    enabled: Boolean(a.enabled),
                    sort_order: Number(a.sort_order),
                    root_path_original: String(a.root_path ?? ""),
                    root_path: String(a.root_path ?? ""),
                    error: null,
                });
            }
        } catch (err) {
            error = err instanceof Error ? err.message : String(err);
            apps = [];
            source = null;
        } finally {
            loading = false;
        }
    }

    async function submitCreate() {
        creating = true;
        createError = null;
        try {
            const req: CreateAppRequest = {
                app_id: form_app_id.trim(),
                // UX: default display_name to app_id when omitted
                display_name: form_display_name.trim() || form_app_id.trim(),
                root_path: form_root_path.trim(),
                enabled: Boolean(form_enabled),
                sort_order: Number(form_sort_order),
            };

            await createApp(fetch, req);

            // Reset minimal fields, keep enabled/sort_order defaults.
            form_app_id = "";
            form_display_name = "";
            form_root_path = "";

            await refresh();
        } catch (err) {
            createError = err instanceof Error ? err.message : String(err);
        } finally {
            creating = false;
        }
    }

    async function saveRow(app_id: string) {
        const row = ensureRowState(app_id);
        setRow(app_id, { saving: true, error: null });

        try {
            const patch: Record<string, unknown> = {
                display_name: row.display_name.trim() || null,
                enabled: Boolean(row.enabled),
                sort_order: Number(row.sort_order),
            };

            // Only update root_path when it actually changes.
            const nextRoot = row.root_path.trim();
            const prevRoot = row.root_path_original.trim();
            if (nextRoot && nextRoot !== prevRoot) {
                patch.root_path = nextRoot;
            }

            await patchApp(fetch, app_id, patch);

            await refresh();
        } catch (err) {
            setRow(app_id, {
                error: err instanceof Error ? err.message : String(err),
            });
        } finally {
            setRow(app_id, { saving: false });
        }
    }

    async function removeRow(app_id: string) {
        const ok = confirm(`Delete app '${app_id}' from registry?`);
        if (!ok) return;

        setRow(app_id, { saving: true, error: null });
        try {
            await deleteApp(fetch, app_id);
            await refresh();
        } catch (err) {
            setRow(app_id, {
                error: err instanceof Error ? err.message : String(err),
            });
        } finally {
            setRow(app_id, { saving: false });
        }
    }

    onMount(() => {
        void refresh();
    });
</script>

<div class="module-shell mx-auto max-w-7xl px-6 py-6">
    <header class="page-header">
        <div class="flex items-start gap-6">
            <div class="w-64 shrink-0">
                <h1 class="page-title">Apps</h1>
            </div>

            <div class="min-w-0 flex-1">
                <div class="text-lg font-medium text-gray-200/90">
                    Manage the Supabase-backed app registry used by the App
                    dropdown.
                </div>
                <div class="text-xs text-gray-300/80 mt-1">
                    Backend writes require <code>MINDSCAPE_APPS_WRITE=true</code
                    >. Current URL scope:
                    <code>{currentScopeQuery() || "(none)"}</code>
                </div>
            </div>

            <div class="shrink-0 flex items-center gap-2">
                <button
                    class="text-xs px-3 py-2 rounded-md border border-white/10 bg-white/5 text-gray-200 hover:bg-white/10"
                    disabled={loading}
                    onclick={() => refresh()}
                >
                    {loading ? "Loading…" : "Reload"}
                </button>
            </div>
        </div>
    </header>

    {#if error}
        <div
            class="card border border-red-500/20 bg-red-500/5 text-red-200/90 whitespace-pre-wrap"
        >
            {error}
        </div>
    {/if}

    <div class="grid grid-cols-1 gap-6 mt-6">
        <section class="card">
            <div class="flex items-center justify-between gap-4">
                <div>
                    <div class="text-sm font-semibold text-gray-100">
                        Create app
                    </div>
                    <div class="text-xs text-gray-300/80 mt-1">
                        Note: <code>root_path</code> is sensitive, but required to
                        resolve ConPort DB paths.
                    </div>
                </div>
            </div>

            <form
                class="mt-4 overflow-x-auto"
                onsubmit={(e) => (e.preventDefault(), submitCreate())}
            >
                <table class="w-full text-sm">
                    <thead class="text-xs text-gray-300/80">
                        <tr class="border-b border-white/10">
                            <th class="text-left py-2 pr-3">app_id</th>
                            <th class="text-left py-2 pr-3">display_name</th>
                            <th class="text-left py-2 pr-3">root_path</th>
                            <th class="text-left py-2 pr-3">enabled</th>
                            <th class="text-left py-2 pr-3">sort_order</th>
                            <th class="text-right py-2">actions</th>
                        </tr>
                    </thead>

                    <tbody>
                        <tr class="border-b border-white/10 align-top">
                            <td class="py-3 pr-3">
                                <label class="sr-only" for="create-app-id"
                                    >app_id</label
                                >
                                <input
                                    id="create-app-id"
                                    class="w-[70%] rounded-md border border-white/10 bg-black/30 px-2 py-1 text-sm text-gray-100 font-mono"
                                    placeholder=""
                                    bind:value={form_app_id}
                                    disabled={creating}
                                />
                            </td>

                            <td class="py-3 pr-3">
                                <label class="sr-only" for="create-display-name"
                                    >display_name</label
                                >
                                <input
                                    id="create-display-name"
                                    class="w-[60%] rounded-md border border-white/10 bg-black/30 px-2 py-1 text-sm text-gray-100"
                                    placeholder=""
                                    bind:value={form_display_name}
                                    disabled={creating}
                                />
                            </td>

                            <td class="py-3 pr-3">
                                <label class="sr-only" for="create-root-path"
                                    >root_path</label
                                >
                                <input
                                    id="create-root-path"
                                    class="w-[75%] rounded-md border border-white/10 bg-black/30 px-2 py-1 text-sm text-gray-100"
                                    placeholder=""
                                    bind:value={form_root_path}
                                    disabled={creating}
                                />
                            </td>

                            <td class="py-3 pr-3">
                                <label class="sr-only" for="create-enabled"
                                    >enabled</label
                                >
                                <input
                                    id="create-enabled"
                                    type="checkbox"
                                    bind:checked={form_enabled}
                                    disabled={creating}
                                />
                            </td>

                            <td class="py-3 pr-3">
                                <label class="sr-only" for="create-sort-order"
                                    >sort_order</label
                                >
                                <input
                                    id="create-sort-order"
                                    class="w-24 rounded-md border border-white/10 bg-black/30 px-2 py-1 text-sm text-gray-100"
                                    type="number"
                                    bind:value={form_sort_order}
                                    disabled={creating}
                                />
                            </td>

                            <td class="py-3 text-right">
                                <button
                                    class="text-xs px-2 py-1 rounded-md border border-white/10 bg-white/5 text-gray-200 hover:bg-white/10"
                                    disabled={creating ||
                                        !form_app_id.trim() ||
                                        !form_root_path.trim()}
                                    type="submit"
                                >
                                    {creating ? "Creating…" : "Create"}
                                </button>
                            </td>
                        </tr>

                        {#if createError}
                            <tr class="border-b border-white/10">
                                <td colspan="6" class="py-3">
                                    <div
                                        class="text-xs text-red-200/90 whitespace-pre-wrap"
                                    >
                                        {createError}
                                    </div>
                                </td>
                            </tr>
                        {/if}
                    </tbody>
                </table>
            </form>
        </section>

        <section class="card">
            <div class="flex items-center justify-between gap-4">
                <div>
                    <div class="text-sm font-semibold text-gray-100">
                        Registry
                    </div>
                    {#if source}
                        <div
                            class="text-xs text-gray-300/80 mt-1 whitespace-pre-wrap"
                        >
                            Source: {JSON.stringify(source)}
                        </div>
                    {/if}
                </div>
            </div>

            {#if apps.length === 0}
                <div class="text-sm text-gray-300/80 mt-4">
                    No apps returned. Seed at least one row in <code
                        >mindscape_ai_apps</code
                    >
                    or configure
                    <code>MINDSCAPE_APP_ROOTS</code> for legacy mode.
                </div>
            {:else}
                <div class="mt-4 overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead class="text-xs text-gray-300/80">
                            <tr class="border-b border-white/10">
                                <th class="text-left py-2 pr-3 min-w-[12rem]">
                                    app_id
                                </th>
                                <th class="text-left py-2 pr-3">display_name</th
                                >
                                <th class="text-left py-2 pr-3 w-1/2"
                                    >root_path</th
                                >
                                <th class="text-left py-2 pr-3">enabled</th>
                                <th class="text-left py-2 pr-3">sort_order</th>
                                <th class="text-left py-2 pr-3">has_conport</th>
                                <th class="text-right py-2">actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {#each apps as a (a.app_id)}
                                {@const row = ensureRowState(a.app_id)}
                                <tr class="border-b border-white/10 align-top">
                                    <td
                                        class="py-3 pr-3 font-mono text-xs whitespace-nowrap min-w-[12rem]"
                                        >{a.app_id}</td
                                    >

                                    <td class="py-3 pr-3">
                                        <input
                                            class="w-[60%] rounded-md border border-white/10 bg-black/30 px-2 py-1 text-sm text-gray-100"
                                            bind:value={row.display_name}
                                            disabled={row.saving}
                                        />
                                    </td>

                                    <td class="py-3 pr-3 w-1/2">
                                        <input
                                            class="w-3/4 rounded-md border border-white/10 bg-black/30 px-2 py-1 text-sm text-gray-100"
                                            placeholder="/home/pwp/srv/mcps/mem0-mcp"
                                            bind:value={row.root_path}
                                            disabled={row.saving}
                                        />
                                    </td>

                                    <td class="py-3 pr-3">
                                        <input
                                            type="checkbox"
                                            bind:checked={row.enabled}
                                            disabled={row.saving}
                                        />
                                    </td>

                                    <td class="py-3 pr-3">
                                        <input
                                            class="w-24 rounded-md border border-white/10 bg-black/30 px-2 py-1 text-sm text-gray-100"
                                            type="number"
                                            bind:value={row.sort_order}
                                            disabled={row.saving}
                                        />
                                    </td>

                                    <td class="py-3 pr-3">
                                        <span
                                            class={a.has_conport
                                                ? "text-emerald-200/90"
                                                : "text-amber-200/90"}
                                        >
                                            {a.has_conport ? "yes" : "no"}
                                        </span>
                                    </td>

                                    <td class="py-3 text-right">
                                        <div class="flex justify-end gap-2">
                                            <button
                                                class="text-xs px-2 py-1 rounded-md border border-white/10 bg-white/5 text-gray-200 hover:bg-white/10"
                                                disabled={row.saving}
                                                onclick={() =>
                                                    saveRow(a.app_id)}
                                            >
                                                {row.saving
                                                    ? "Saving…"
                                                    : "Save"}
                                            </button>
                                            <button
                                                class="text-xs px-2 py-1 rounded-md border border-red-500/30 bg-red-500/10 text-red-100 hover:bg-red-500/15"
                                                disabled={row.saving}
                                                onclick={() =>
                                                    removeRow(a.app_id)}
                                            >
                                                Delete
                                            </button>
                                        </div>

                                        {#if row.error}
                                            <div
                                                class="text-xs text-red-200/90 whitespace-pre-wrap mt-2 text-left"
                                            >
                                                {row.error}
                                            </div>
                                        {/if}
                                    </td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                </div>
            {/if}
        </section>
    </div>
</div>
