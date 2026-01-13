<script lang="ts">
	import { goto } from "$app/navigation";
	import { page } from "$app/stores";
	import { listApps, type MindscapeAppSummary } from "$lib/api/apps";
	import favicon from "$lib/assets/favicon.svg";
	import { onMount } from "svelte";

	import "../app.css";

	let { children } = $props();

	let apps = $state<MindscapeAppSummary[]>([]);
	let appsLoading = $state(false);
	let appsError = $state<string | null>(null);

	function withScope(path: string): string {
		const app_id = $page.url.searchParams.get("app_id");
		const db = $page.url.searchParams.get("db");

		// Preserve existing query params on `path` while adding scope.
		const url = new URL(path, "http://local");

		if (app_id) {
			url.searchParams.set("app_id", app_id);
			// If app_id is set, db is ignored server-side anyway; omit it to reduce confusion.
			url.searchParams.delete("db");
		} else if (db) {
			// Legacy/workbench fallback.
			url.searchParams.set("db", db);
		}

		return url.pathname + url.search;
	}

	function currentAppId(): string {
		return $page.url.searchParams.get("app_id") ?? "";
	}

	async function refreshApps() {
		appsLoading = true;
		appsError = null;
		try {
			const resp = await listApps(fetch);
			apps = resp.apps;
		} catch (err) {
			appsError = err instanceof Error ? err.message : String(err);
			apps = [];
		} finally {
			appsLoading = false;
		}
	}

	function onAppChange(e: Event) {
		const select = e.currentTarget as HTMLSelectElement;
		const next = select.value;

		const url = new URL($page.url);
		if (next) url.searchParams.set("app_id", next);
		else url.searchParams.delete("app_id");

		// Since app_id is now the scope, clear any legacy db param.
		url.searchParams.delete("db");

		void goto(url.pathname + url.search, {
			replaceState: true,
			keepFocus: true,
			noScroll: true,
		});
	}

	onMount(() => {
		void refreshApps();
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="min-h-screen bg-[#111111] text-gray-100">
	<header class="sticky top-0 z-10 border-b border-white/10 bg-[#0d0d0d]">
		<nav
			class="mx-auto max-w-7xl px-6 py-4 flex items-center gap-3 flex-wrap"
		>
			<a
				href="/"
				class="text-lg font-semibold tracking-tight hover:underline underline-offset-4 decoration-white/20 hover:decoration-white/60"
			>
				Mindscape-AI
			</a>

			<span class="mx-1 opacity-30">|</span>

			<!-- Top-level modules -->
			<a
				href={withScope("/conport")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname.startsWith(
					"/conport",
				)}
				class:text-white={$page.url.pathname.startsWith("/conport")}
			>
				Conport
			</a>

			<a
				href={withScope("/mem0")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname.startsWith(
					"/mem0",
				)}
				class:text-white={$page.url.pathname.startsWith("/mem0")}
			>
				Mem0
			</a>

			<a
				href={withScope("/prompts")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname.startsWith(
					"/prompts",
				)}
				class:text-white={$page.url.pathname.startsWith("/prompts")}
			>
				Prompts
			</a>

			<a
				href={withScope("/tokens")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname.startsWith(
					"/tokens",
				)}
				class:text-white={$page.url.pathname.startsWith("/tokens")}
			>
				Tokens
			</a>

			<span class="mx-1 opacity-30">|</span>

			<!-- Global app selector -->
			<div class="flex items-center gap-2">
				<label class="text-xs text-gray-300/80" for="app-select"
					>App</label
				>
				<select
					id="app-select"
					class="rounded-md border border-white/10 bg-black/30 px-2 py-1 text-sm text-gray-100"
					disabled={appsLoading}
					onchange={onAppChange}
					value={currentAppId()}
				>
					<option value="">(local/default)</option>
					{#each apps as a (a.app_id)}
						<option value={a.app_id}>
							{a.app_id}{a.has_conport ? "" : " (no conport db)"}
						</option>
					{/each}
				</select>

				<button
					class="text-xs px-2 py-1 rounded-md border border-white/10 bg-white/5 text-gray-200 hover:bg-white/10"
					disabled={appsLoading}
					onclick={() => refreshApps()}
				>
					{appsLoading ? "Loading…" : "Reload"}
				</button>

				<a
					href={withScope("/apps")}
					class="text-xs px-2 py-1 rounded-md border border-white/10 bg-white/5 text-gray-200 hover:bg-white/10"
				>
					Manage
				</a>
			</div>

			{#if appsError}
				<div class="text-xs text-red-200/90 whitespace-pre-wrap">
					{appsError}
				</div>
			{/if}
		</nav>
	</header>

	<main>
		{@render children()}
	</main>
</div>
