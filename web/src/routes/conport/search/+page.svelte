<script lang="ts">
	import { page } from "$app/stores";
	import { onMount } from "svelte";

	import type { ConportSearchResponse } from "$lib/api/conport";
	import { conportSearch } from "$lib/api/conport";

	let q = $state("");
	let limit = $state(10);

	let loading = $state(false);
	let error = $state<string | null>(null);
	let data = $state<ConportSearchResponse | null>(null);

	function withDb(url: string): string {
		const db = $page.url.searchParams.get("db");
		if (!db) return url;
		const u = new URL(url, "http://local");
		u.searchParams.set("db", db);
		return u.pathname + u.search;
	}

	function persistFiltersToUrl(): void {
		if (typeof window === "undefined") return;

		const u = new URL(window.location.href);

		const query = q.trim();
		if (query) u.searchParams.set("q", query);
		else u.searchParams.delete("q");

		u.searchParams.set("limit", String(limit));

		window.history.replaceState({}, "", u);
	}

	function prefillFiltersFromUrl(): void {
		const params = $page.url.searchParams;

		const preset = params.get("q");
		const rawLimit = params.get("limit");

		if (preset) q = preset;

		if (rawLimit) {
			const n = Number(rawLimit);
			if (Number.isFinite(n) && n >= 1 && n <= 100) limit = n;
		}
	}

	async function runSearch() {
		error = null;
		data = null;

		if (!q.trim()) return;

		loading = true;
		try {
			const db = $page.url.searchParams.get("db");
			data = await conportSearch(fetch, { q: q.trim(), limit, db });
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		prefillFiltersFromUrl();
		if (q.trim()) void runSearch();
	});
</script>

<svelte:head>
	<title>ConPort • Search</title>
</svelte:head>

<main class="page-container">
	<header class="mb-6">
		<h1 class="page-title">ConPort — Search</h1>
		<p class="page-subtitle">
			Search decisions and custom data (FTS when available).
		</p>
	</header>

	<form
		onsubmit={(e) => {
			e.preventDefault();
			persistFiltersToUrl();
			void runSearch();
		}}
		class="form-row mb-6"
	>
		<label class="field min-w-[260px] flex-1">
			<span class="field-label">Query</span>
			<input
				bind:value={q}
				placeholder="e.g. authentication, roadmap, caching"
				class="input"
			/>
		</label>

		<label class="field w-[120px]">
			<span class="field-label">Limit</span>
			<input
				type="number"
				min="1"
				max="100"
				bind:value={limit}
				class="input"
			/>
		</label>

		<button
			type="submit"
			disabled={loading || !q.trim()}
			class="btn btn-primary"
		>
			{loading ? "Searching…" : "Search"}
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
	{/if}

	{#if data}
		<div class="mb-4 text-sm text-gray-300">
			FTS: decisions={data.fts.decisions ? "yes" : "no"} • custom_data={data
				.fts.custom_data
				? "yes"
				: "no"}
		</div>

		<section class="grid gap-4 md:grid-cols-2">
			<div class="card">
				<h2 class="card-title">
					Decisions ({data.results.decisions.length})
				</h2>

				{#if data.results.decisions.length === 0}
					<p class="mt-2 text-sm text-gray-300">No matches.</p>
				{:else}
					<ul class="mt-3 space-y-2 text-sm">
						{#each data.results.decisions as d}
							<li
								class="rounded-lg border border-white/10 bg-white/5 p-3"
							>
								<div class="font-medium text-gray-100">
									<a
										href={withDb(
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
			</div>

			<div class="card">
				<h2 class="card-title">
					Custom Data ({data.results.custom_data.length})
				</h2>

				{#if data.results.custom_data.length === 0}
					<p class="mt-2 text-sm text-gray-300">No matches.</p>
				{:else}
					<ul class="mt-3 space-y-2 text-sm">
						{#each data.results.custom_data as c}
							<li
								class="rounded-lg border border-white/10 bg-white/5 p-3"
							>
								<div class="font-medium text-gray-100">
									<a
										href={withDb(
											`/conport/item?type=custom_data&id=${c.id}`,
										)}
										class="hover:underline underline-offset-2"
									>
										{c.category} / {c.key}
									</a>
								</div>
								<div class="mt-1 text-xs text-gray-400">
									id={c.id} • {c.timestamp}
								</div>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		</section>
	{/if}
</main>
