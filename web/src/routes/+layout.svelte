<script lang="ts">
	import { page } from "$app/stores";
	import favicon from "$lib/assets/favicon.svg";

	import "../app.css";

	let { children } = $props();

	function withDb(path: string): string {
		const db = $page.url.searchParams.get("db");
		if (!db) return path;

		// Preserve existing query params on `path` while adding `db`.
		const url = new URL(path, "http://local");
		url.searchParams.set("db", db);
		return url.pathname + url.search;
	}
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="min-h-screen bg-[#111111] text-gray-100">
	<header class="sticky top-0 z-10 border-b border-white/10 bg-[#0d0d0d]">
		<nav
			class="mx-auto max-w-7xl px-6 py-4 flex items-center gap-2 flex-wrap"
		>
			<a
				href="/"
				class="text-lg font-semibold tracking-tight hover:underline underline-offset-4 decoration-white/20 hover:decoration-white/60"
			>
				Mindscape-AI
			</a>

			<span class="mx-1 opacity-30">|</span>

			<a
				href={withDb("/conport/now")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname ===
					"/conport/now"}
				class:text-white={$page.url.pathname === "/conport/now"}
			>
				Now
			</a>
			<a
				href={withDb("/conport/dashboard")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname ===
					"/conport/dashboard"}
				class:text-white={$page.url.pathname === "/conport/dashboard"}
			>
				Dashboard
			</a>
			<a
				href={withDb("/conport/search")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname ===
					"/conport/search"}
				class:text-white={$page.url.pathname === "/conport/search"}
			>
				Search
			</a>
			<a
				href={withDb("/conport/decisions")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname ===
					"/conport/decisions"}
				class:text-white={$page.url.pathname === "/conport/decisions"}
			>
				Decisions
			</a>
			<a
				href={withDb("/conport/custom-data")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname ===
					"/conport/custom-data"}
				class:text-white={$page.url.pathname === "/conport/custom-data"}
			>
				Custom Data
			</a>
			<a
				href={withDb("/conport/system-patterns")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname ===
					"/conport/system-patterns"}
				class:text-white={$page.url.pathname ===
					"/conport/system-patterns"}
			>
				Patterns
			</a>
			<a
				href={withDb("/conport/progress")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname ===
					"/conport/progress"}
				class:text-white={$page.url.pathname === "/conport/progress"}
			>
				Progress
			</a>
			<a
				href={withDb("/conport/views")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname ===
					"/conport/views"}
				class:text-white={$page.url.pathname === "/conport/views"}
			>
				Views
			</a>
			<a
				href={withDb("/conport/links")}
				class="text-sm font-medium px-2 py-1 rounded-md transition-colors duration-150 text-gray-300 hover:text-white hover:bg-white/5"
				class:bg-sidebar-selected={$page.url.pathname ===
					"/conport/links"}
				class:text-white={$page.url.pathname === "/conport/links"}
			>
				Links
			</a>
		</nav>
	</header>

	<main>
		{@render children()}
	</main>
</div>
