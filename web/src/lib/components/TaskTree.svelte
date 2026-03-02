<script lang="ts">
	import type { ProgressTreeNodeWithWbs } from "$lib/types/progress";
	import TaskTree from "./TaskTree.svelte";

	let { nodes, itemHref } = $props<{
		nodes: ProgressTreeNodeWithWbs[];
		itemHref: (id: number) => string;
	}>();

	function statusColor(status: string): string {
		const normalized = status.toUpperCase();
		switch (normalized) {
			case "IN_PROGRESS":
				return "bg-emerald-400";
			case "DONE":
				return "bg-sky-400";
			case "TODO":
				return "bg-amber-400";
			default:
				return "bg-gray-400";
		}
	}

	function entityIcon(type: string, status: string): string {
		const normalizedStatus = status.toUpperCase();
		switch (type) {
			case "project":
				return "📦";
			case "phase":
				return "📋";
			case "task":
				// DONE: gray X, TODO: blue check, IN_PROGRESS: green check
				return normalizedStatus === "DONE" ? "X" : "✓";
			default:
				return "•";
		}
	}

	function phaseMarker(status: string): string {
		const normalized = status.toUpperCase();
		switch (normalized) {
			case "IN_PROGRESS":
				return "🟩";
			case "DONE":
				return "🟦";
			case "TODO":
			default:
				return "🟨";
		}
	}

	function phaseMarkerLabel(status: string): string {
		const normalized = status.toUpperCase();
		switch (normalized) {
			case "IN_PROGRESS":
				return "Phase (In progress)";
			case "DONE":
				return "Phase (Done)";
			case "TODO":
			default:
				return "Phase (Pending action)";
		}
	}

	function getTitle(node: ProgressTreeNodeWithWbs): string {
		return (
			node.entry.wbs_meta?.title ??
			stripPriorityPrefix(node.entry.description)
		);
	}

	function stripPriorityPrefix(description: string): string {
		return description.replace(/^\s*\[p\d+\]\s*/i, "");
	}

	function displayDescription(description: string): string {
		return description.trim().replace(/^\[p\d+\]\s*/i, "");
	}

	function isPhaseNode(node: ProgressTreeNodeWithWbs): boolean {
		return node.entry.wbs_meta?.entity_type === "phase";
	}

	function isNoteEntry(node: ProgressTreeNodeWithWbs): boolean {
		return /^\s*phase\s+\d+\s*:/i.test(node.entry.description);
	}

	function splitChildren(children: ProgressTreeNodeWithWbs[]): {
		tasks: ProgressTreeNodeWithWbs[];
		notes: ProgressTreeNodeWithWbs[];
	} {
		const tasks: ProgressTreeNodeWithWbs[] = [];
		const notes: ProgressTreeNodeWithWbs[] = [];

		for (const c of children) {
			if (isNoteEntry(c)) notes.push(c);
			else tasks.push(c);
		}

		return { tasks, notes };
	}
</script>

<ul class="space-y-1">
	{#each nodes as node (node.entry.id)}
		{@const title = getTitle(node)}
		{@const entityType = node.entry.wbs_meta?.entity_type ?? "unknown"}
		{@const isPhase = isPhaseNode(node)}
		<li class="rounded-md border border-white/10 bg-black/10">
			<details open={node.entry.status.toUpperCase() === "IN_PROGRESS"}>
				<summary class="cursor-pointer list-none select-none px-3 py-2">
					<div class="flex items-start justify-between gap-3">
						<div class="flex min-w-0 items-start gap-2">
							{#if isPhase}
								<span
									class="mt-0.5 shrink-0"
									aria-hidden="true"
									title={phaseMarkerLabel(node.entry.status)}
									>{phaseMarker(node.entry.status)}</span
								>
							{:else}
								<span
									class="mt-0.5 shrink-0"
									title={entityType}
									style={`color: ${
										node.entry.status.toUpperCase() ===
										"DONE"
											? "rgba(156,163,175,0.9)"
											: node.entry.status.toUpperCase() ===
												  "TODO"
												? "rgb(59,130,246)"
												: "rgb(34,197,94)"
									};`}
									>{entityIcon(
										entityType,
										node.entry.status,
									)}</span
								>
							{/if}
							<div class="min-w-0">
								<a
									href={itemHref(node.entry.id)}
									class="min-w-0 truncate text-sm font-medium hover:underline underline-offset-4 decoration-white/20 hover:decoration-white/60"
									onclick={(e) => e.stopPropagation()}
								>
									{title}
								</a>
								{#if node.entry.wbs_meta?.priority}
									<span class="ml-1 text-xs opacity-60">
										[{node.entry.wbs_meta.priority}]
									</span>
								{/if}
								{#if node.entry.wbs_meta?.tags && node.entry.wbs_meta.tags.length > 0}
									<div class="mt-1 flex flex-wrap gap-1">
										{#each node.entry.wbs_meta.tags.slice(0, 3) as tag}
											<span
												class="rounded bg-gray-700 px-1 py-0.5 text-xs"
											>
												{tag}
											</span>
										{/each}
									</div>
								{/if}
							</div>
						</div>

						<div class="flex items-center gap-2">
							{#if node.children.length > 0}
								<span class="text-[11px] text-gray-300/80"
									>{node.children.length}</span
								>
							{/if}
						</div>
					</div>
				</summary>

				{#if node.children.length > 0}
					{@const { tasks, notes } = splitChildren(node.children)}
					<div class="border-t border-white/10 px-3 py-2">
						{#if tasks.length > 0}
							<div class="pl-3">
								<TaskTree nodes={tasks} {itemHref} />
							</div>
						{/if}

						{#if notes.length > 0}
							<details
								class="mt-2 rounded-md border border-white/10 bg-black/10 p-2"
							>
								<summary
									class="cursor-pointer text-xs font-semibold text-gray-200"
								>
									Notes ({notes.length})
								</summary>
								<ul class="mt-2 space-y-1 pl-3">
									{#each notes as note (note.entry.id)}
										<li>
											<a
												href={itemHref(note.entry.id)}
												class="block text-xs leading-snug text-gray-300/90 hover:text-gray-100 hover:underline"
											>
												{displayDescription(
													note.entry.description,
												)}
											</a>
										</li>
									{/each}
								</ul>
							</details>
						{/if}
					</div>
				{/if}
			</details>
		</li>
	{/each}
</ul>
