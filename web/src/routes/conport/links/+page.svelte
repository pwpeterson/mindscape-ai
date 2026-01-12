<script lang="ts">
	import { page } from "$app/stores";
	import { onMount } from "svelte";

	import type { ConportLinksResponse } from "$lib/api/conport";
	import { conportLinks } from "$lib/api/conport";

	let source_item_type = $state<string>("");
	let source_item_id = $state<string>("");
	let target_item_type = $state<string>("");
	let target_item_id = $state<string>("");
	let limit = $state<number>(50);

	let loading = $state(true);
	let error = $state<string | null>(null);
	let data = $state<ConportLinksResponse | null>(null);

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

		const sType = source_item_type.trim();
		const sId = source_item_id.trim();
		const tType = target_item_type.trim();
		const tId = target_item_id.trim();

		if (sType) u.searchParams.set("source_item_type", sType);
		else u.searchParams.delete("source_item_type");

		if (sId) u.searchParams.set("source_item_id", sId);
		else u.searchParams.delete("source_item_id");

		if (tType) u.searchParams.set("target_item_type", tType);
		else u.searchParams.delete("target_item_type");

		if (tId) u.searchParams.set("target_item_id", tId);
		else u.searchParams.delete("target_item_id");

		u.searchParams.set("limit", String(limit));

		window.history.replaceState({}, "", u);
	}

	function prefillFiltersFromUrl(): void {
		const params = $page.url.searchParams;

		const sType = params.get("source_item_type");
		const sId = params.get("source_item_id");
		const tType = params.get("target_item_type");
		const tId = params.get("target_item_id");
		const rawLimit = params.get("limit");

		if (sType) source_item_type = sType;
		if (sId) source_item_id = sId;
		if (tType) target_item_type = tType;
		if (tId) target_item_id = tId;

		if (rawLimit) {
			const n = Number(rawLimit);
			if (Number.isFinite(n) && n >= 1 && n <= 500) limit = n;
		}
	}

	async function refresh() {
		loading = true;
		error = null;

		try {
			const db = $page.url.searchParams.get("db");
			data = await conportLinks(fetch, {
				source_item_type: source_item_type.trim() || null,
				source_item_id: source_item_id.trim() || null,
				target_item_type: target_item_type.trim() || null,
				target_item_id: target_item_id.trim() || null,
				limit,
				db,
			});
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		prefillFiltersFromUrl();
		void refresh();
	});
</script>

<svelte:head>
	<title>ConPort • Links</title>
</svelte:head>

<main
	style="max-width: 1100px; margin: 0 auto; padding: 24px; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;"
>
	<header style="margin-bottom: 16px;">
		<h1 style="margin: 0; font-size: 24px;">ConPort — Links</h1>
		<p style="margin: 6px 0 0; opacity: 0.8;">
			Workbench view of context links (knowledge graph edges).
		</p>
	</header>

	<form
		onsubmit={(e) => {
			e.preventDefault();
			persistFiltersToUrl();
			void refresh();
		}}
		style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px;"
	>
		<label style="display: grid; gap: 6px;">
			<span style="font-size: 12px; opacity: 0.8;">Source type</span>
			<input
				bind:value={source_item_type}
				style="padding: 8px 10px; border: 1px solid #ccc; border-radius: 8px;"
			/>
		</label>
		<label style="display: grid; gap: 6px;">
			<span style="font-size: 12px; opacity: 0.8;">Source id</span>
			<input
				bind:value={source_item_id}
				style="padding: 8px 10px; border: 1px solid #ccc; border-radius: 8px;"
			/>
		</label>
		<label style="display: grid; gap: 6px;">
			<span style="font-size: 12px; opacity: 0.8;">Target type</span>
			<input
				bind:value={target_item_type}
				style="padding: 8px 10px; border: 1px solid #ccc; border-radius: 8px;"
			/>
		</label>
		<label style="display: grid; gap: 6px;">
			<span style="font-size: 12px; opacity: 0.8;">Target id</span>
			<input
				bind:value={target_item_id}
				style="padding: 8px 10px; border: 1px solid #ccc; border-radius: 8px;"
			/>
		</label>

		<div style="display: flex; gap: 10px; align-items: end;">
			<label style="display: grid; gap: 6px;">
				<span style="font-size: 12px; opacity: 0.8;">Limit</span>
				<input
					type="number"
					min="1"
					max="500"
					bind:value={limit}
					style="padding: 8px 10px; border: 1px solid #ccc; border-radius: 8px; width: 110px;"
				/>
			</label>
			<button
				type="submit"
				disabled={loading}
				style="padding: 8px 12px; border: 1px solid #ccc; border-radius: 8px; background: white; cursor: pointer;"
			>
				{loading ? "Loading…" : "Apply"}
			</button>
		</div>
	</form>

	{#if error}
		<div
			style="padding: 12px; border: 1px solid #f5c2c7; background: #f8d7da; color: #842029; border-radius: 8px;"
		>
			<strong>Error</strong>
			<div style="margin-top: 6px; white-space: pre-wrap;">{error}</div>
		</div>
	{:else if loading}
		<p>Loading…</p>
	{:else if data}
		{#if data.links.length === 0}
			<p style="opacity: 0.7;">No links found.</p>
		{:else}
			<table style="width: 100%; border-collapse: collapse;">
				<thead>
					<tr>
						<th
							style="text-align: left; padding: 6px 0; border-bottom: 1px solid #eee;"
							>Relationship</th
						>
						<th
							style="text-align: left; padding: 6px 0; border-bottom: 1px solid #eee;"
							>Source</th
						>
						<th
							style="text-align: left; padding: 6px 0; border-bottom: 1px solid #eee;"
							>Target</th
						>
						<th
							style="text-align: left; padding: 6px 0; border-bottom: 1px solid #eee;"
							>Timestamp</th
						>
					</tr>
				</thead>
				<tbody>
					{#each data.links as l}
						<tr>
							<td
								style="padding: 8px 0; border-bottom: 1px solid #f3f4f6;"
							>
								<div style="font-weight: 600;">
									<a
										href={withDb(
											`/conport/item?type=context_link&id=${l.id}`,
										)}
										style="text-decoration: none;"
									>
										{l.relationship_type}
									</a>
								</div>
								<div style="font-size: 12px; opacity: 0.75;">
									id={l.id}
								</div>
								{#if l.description}
									<div style="font-size: 12px; opacity: 0.8;">
										{l.description}
									</div>
								{/if}
							</td>
							<td
								style="padding: 8px 0; border-bottom: 1px solid #f3f4f6;"
							>
								<code>{l.source_item_type}</code> /
								<code>{l.source_item_id}</code>
							</td>
							<td
								style="padding: 8px 0; border-bottom: 1px solid #f3f4f6;"
							>
								<code>{l.target_item_type}</code> /
								<code>{l.target_item_id}</code>
							</td>
							<td
								style="padding: 8px 0; border-bottom: 1px solid #f3f4f6; font-size: 12px; opacity: 0.8;"
							>
								{l.timestamp}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	{:else}
		<p>No data.</p>
	{/if}
</main>
