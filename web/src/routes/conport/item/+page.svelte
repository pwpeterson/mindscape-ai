<script lang="ts">
	import { page } from "$app/stores";
	import { onMount } from "svelte";

	import type {
		ConportItemResponse,
		ConportItemType,
	} from "$lib/api/conport";
	import { conportItem } from "$lib/api/conport";

	let loading = $state(false);
	let error = $state<string | null>(null);
	let data = $state<ConportItemResponse | null>(null);

	let type = $state<ConportItemType>("decision");
	let id = $state<number>(1);

	function persistToUrl(): void {
		if (typeof window === "undefined") return;

		const u = new URL(window.location.href);
		u.searchParams.set("type", type);
		u.searchParams.set("id", String(id));
		// Keep any existing db=... param untouched.
		window.history.replaceState({}, "", u);
	}

	async function refresh() {
		error = null;
		data = null;
		loading = true;

		try {
			const db = $page.url.searchParams.get("db");
			data = await conportItem(fetch, { type, id, db });
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	}

	function parseQuery() {
		const params = $page.url.searchParams;
		const t = params.get("type") as ConportItemType | null;
		const rawId = params.get("id");
		if (t) type = t;
		if (rawId) {
			const num = Number(rawId);
			if (Number.isFinite(num) && num >= 1) id = num;
		}
	}

	onMount(() => {
		parseQuery();
		void refresh();
	});
</script>

<svelte:head>
	<title>ConPort • Item</title>
</svelte:head>

<main class="page-container">
	<form
		onsubmit={(e) => {
			e.preventDefault();
			persistToUrl();
			void refresh();
		}}
		class="form-row mb-6"
	>
		<label class="field">
			<span class="field-label">Type</span>
			<select bind:value={type} class="input">
				<option value="decision">decision</option>
				<option value="progress">progress</option>
				<option value="system_pattern">system_pattern</option>
				<option value="custom_data">custom_data</option>
				<option value="context_link">context_link</option>
				<option value="product_context">product_context</option>
				<option value="active_context">active_context</option>
			</select>
		</label>

		<label class="field w-[140px]">
			<span class="field-label">ID</span>
			<input type="number" min="1" bind:value={id} class="input" />
		</label>

		<button type="submit" disabled={loading} class="btn btn-primary">
			{loading ? "Loading…" : "Load"}
		</button>
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
		<div class="card overflow-auto">
			<pre
				class="text-xs leading-relaxed text-gray-200 whitespace-pre-wrap">{JSON.stringify(
					data,
					null,
					2,
				)}</pre>
		</div>
	{/if}
</main>
