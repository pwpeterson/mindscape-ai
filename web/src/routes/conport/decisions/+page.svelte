<script lang="ts">
	import { page } from "$app/stores";
	import { onMount } from "svelte";

	import type {
		ConportDecision,
		ConportDecisionsListResponse,
	} from "$lib/api/conport";
	import { conportDecisionsList } from "$lib/api/conport";

	let loading = $state(true);
	let error = $state<string | null>(null);
	let decisions = $state<ConportDecision[]>([]);
	let dbResolved = $state<string>("");

	let limit = $state<number>(50);

	function withScope(url: string): string {
		const app_id = $page.url.searchParams.get("app_id");
		const db = $page.url.searchParams.get("db");

		const u = new URL(url, "http://local");

		if (app_id) {
			u.searchParams.set("app_id", app_id);
			u.searchParams.delete("db");
		} else if (db) {
			u.searchParams.set("db", db);
		}

		return u.pathname + u.search;
	}

	function persistFiltersToUrl(): void {
		if (typeof window === "undefined") return;
		const u = new URL(window.location.href);
		u.searchParams.set("limit", String(limit));
		window.history.replaceState({}, "", u);
	}

	async function refresh() {
		loading = true;
		error = null;

		try {
			const app_id = $page.url.searchParams.get("app_id");
			const db = $page.url.searchParams.get("db");

			const data: ConportDecisionsListResponse =
				await conportDecisionsList(fetch, {
					limit,
					app_id,
					db,
				});
			dbResolved = data.db;
			decisions = data.decisions;
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		const rawLimit = $page.url.searchParams.get("limit");
		if (rawLimit) {
			const n = Number(rawLimit);
			if (Number.isFinite(n) && n >= 1 && n <= 500) limit = n;
		}
		void refresh();
	});
</script>

<svelte:head>
	<title>ConPort • Decisions</title>
</svelte:head>

<main class="page-container">
	<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
		{#if dbResolved}
			<div class="break-all text-xs text-gray-400">
				DB: <code>{dbResolved}</code>
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

	<form
		onsubmit={(e) => {
			e.preventDefault();
			persistFiltersToUrl();
			void refresh();
		}}
		class="form-row mb-6"
	>
		<label class="field w-[140px]">
			<span class="field-label">Limit</span>
			<input
				type="number"
				min="1"
				max="500"
				bind:value={limit}
				class="input"
			/>
		</label>

		<button type="submit" disabled={loading} class="btn">
			{loading ? "Loading…" : "Apply"}
		</button>
	</form>

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
	{:else if decisions.length === 0}
		<p class="text-sm text-gray-300">No decisions found.</p>
	{:else}
		<ul class="space-y-2">
			{#each decisions as d}
				<li class="rounded-xl border border-white/10 bg-white/5 p-4">
					<div class="font-medium text-gray-100">
						<a
							href={withScope(
								`/conport/item?type=decision&id=${d.id}`,
							)}
							class="hover:underline underline-offset-2"
						>
							{d.summary}
						</a>
					</div>
					<div class="mt-1 text-xs text-gray-400">
						id={d.id} • {d.timestamp}
					</div>
				</li>
			{/each}
		</ul>
	{/if}
</main>
