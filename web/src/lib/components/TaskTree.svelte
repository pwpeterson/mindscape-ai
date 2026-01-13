<script lang="ts">
	import type { ConportProgressEntry } from "$lib/api/conport";
	import type { ProgressTreeNode } from "$lib/types/progress";
	import TaskTree from "./TaskTree.svelte";

	let { nodes, itemHref } = $props<{
		nodes: ProgressTreeNode[];
		itemHref: (id: number) => string;
	}>();

	function statusColor(status: string): string {
		switch (status) {
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

	function displayDescription(description: string): string {
		// Hide the [P#] prefix in the UI, but keep it in the stored ConPort description.
		return description.trim().replace(/^\[p\d+\]\s*/i, "");
	}

	function isNoteEntry(entry: ConportProgressEntry): boolean {
		// Treat narrative milestone summaries like "Phase 1: ... delivered ..." as notes.
		// (Do NOT match "Phase 1 — ..." which we treat as a phase node.)
		return /^\s*phase\s+\d+\s*:/i.test(entry.description);
	}

	function splitChildren(children: ProgressTreeNode[]): {
		tasks: ProgressTreeNode[];
		notes: ProgressTreeNode[];
	} {
		const tasks: ProgressTreeNode[] = [];
		const notes: ProgressTreeNode[] = [];

		for (const c of children) {
			if (isNoteEntry(c.entry)) notes.push(c);
			else tasks.push(c);
		}

		return { tasks, notes };
	}

</script>

<ul class="space-y-1">
	{#each nodes as node (node.entry.id)}
		<li class="rounded-md border border-white/10 bg-black/10">
			<details open={node.entry.status === "IN_PROGRESS"}>
				<summary class="cursor-pointer list-none select-none px-3 py-2">
					<div class="flex items-start justify-between gap-3">
						<div class="flex min-w-0 items-start gap-2">
							<span
								class={`mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full ${statusColor(node.entry.status)}`}
							></span>
							<a
								href={itemHref(node.entry.id)}
								class="min-w-0 truncate text-sm font-medium hover:underline underline-offset-4 decoration-white/20 hover:decoration-white/60"
								onclick={(e) => e.stopPropagation()}
							>
								{displayDescription(node.entry.description)}
							</a>
						</div>

						<div class="flex items-center gap-2">
							{#if node.children.length > 0}
								<span class="text-[11px] text-gray-300/80">{node.children.length}</span>
							{/if}
						</div>
					</div>
				</summary>

				{#if node.children.length > 0}
					{@const { tasks, notes } = splitChildren(node.children)}
					<div class="border-t border-white/10 px-3 py-2">
						{#if tasks.length > 0}
							<div class="pl-3">
								<TaskTree nodes={tasks} itemHref={itemHref} />
							</div>
						{/if}

						{#if notes.length > 0}
							<details class="mt-2 rounded-md border border-white/10 bg-black/10 p-2">
								<summary class="cursor-pointer text-xs font-semibold text-gray-200">
									Notes ({notes.length})
								</summary>
								<ul class="mt-2 space-y-1 pl-3">
									{#each notes as note (note.entry.id)}
										<li>
											<a
												href={itemHref(note.entry.id)}
												class="block text-xs leading-snug text-gray-300/90 hover:text-gray-100 hover:underline"
											>
												{displayDescription(note.entry.description)}
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
