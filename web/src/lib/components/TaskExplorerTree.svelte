<script lang="ts">
	import type { ProgressTreeNode } from "$lib/types/progress";
	import { onMount } from "svelte";
	import TaskExplorerTree from "./TaskExplorerTree.svelte";

	let {
		nodes,
		itemHref,
		level = 0,
		showIdPrefix = false,
	} = $props<{
		nodes: ProgressTreeNode[];
		itemHref: (id: number) => string;
		level?: number;
		showIdPrefix?: boolean;
	}>();

	function idPrefix(id: number): string {
		// UI-only prefix for progress entry IDs. Use P-nnn (e.g. P-007) to match
		// the project's "P-#" naming convention rather than legacy "T###".
		return `P-${String(id).padStart(3, "0")}`;
	}

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

	function indentStyle(): string {
		// VS Code-ish: small base indent + fixed indent per level.
		return `padding-left: ${0.75 + level * 1.0}rem;`;
	}

	function stripPriorityPrefix(description: string): string {
		// Hide the [P#] prefix in the UI, but keep it in the stored ConPort description.
		return description.replace(/^\s*\[p\d+\]\s*/i, "");
	}

	function splitDescription(description: string): {
		title: string;
		notes: string[];
	} {
		// Convention: multi-line descriptions are "title" on first line, followed by
		// status updates / narrative lines. We render those extra lines in the Notes panel.
		const cleaned = stripPriorityPrefix(description).trim();
		const lines = cleaned.split(/\r?\n/).map((l) => l.trimEnd());

		// Treat blank lines as separators; keep only non-empty lines for display.
		const nonEmpty = lines.filter((l) => l.trim().length > 0);
		const title = nonEmpty[0] ?? "";
		const notes = nonEmpty.slice(1);
		return { title, notes };
	}

	function displayDescription(description: string): string {
		return stripPriorityPrefix(description).trim();
	}

	function isNoteDescription(description: string): boolean {
		// Notes are narrative entries we want to show in a Notes subpanel.
		//
		// Supported formats (optional priority prefix like "[P1]"):
		// - "Phase 1: ..." (legacy phase notes)
		// - "Note: ..." / "Notes: ..."
		// - "[note]: ..." / "[notes]: ..."
		return /^\s*(?:\[p\d+\]\s*)?(?:phase\s+\d+\s*:|notes?\s*[:—–-]|\[notes?\]\s*[:—–-])/i.test(
			description,
		);
	}

	function isPhaseDescription(description: string): boolean {
		// Phase nodes look like: "Phase 1 — ..." (dash variants supported)
		// Allow optional priority prefix like "[P1]".
		return /^\s*(?:\[p\d+\]\s*)?phase\s+\d+\s*[—–-]/i.test(description);
	}

	function splitChildren(children: ProgressTreeNode[]): {
		tasks: ProgressTreeNode[];
		notes: ProgressTreeNode[];
	} {
		const tasks: ProgressTreeNode[] = [];
		const notes: ProgressTreeNode[] = [];

		for (const c of children) {
			if (isNoteDescription(c.entry.description)) notes.push(c);
			else tasks.push(c);
		}

		return { tasks, notes };
	}

	type AggregatedNote =
		| { kind: "text"; key: string; text: string }
		| { kind: "link"; key: string; text: string; href: string };

	function noteContextPrefix(node: ProgressTreeNode): string {
		return showIdPrefix ? `${idPrefix(node.entry.id)} ` : "";
	}

	function collectAggregatedNotes(node: ProgressTreeNode): AggregatedNote[] {
		// Policy: child tasks do NOT show their own Notes subpanels. Instead, we bubble
		// all notes (inline multi-line description + explicit note-children) to the
		// root node's Notes panel (level === 0).
		//
		// This keeps task titles clean while still preserving status updates.
		const out: AggregatedNote[] = [];

		const inline = splitDescription(node.entry.description);
		const title =
			inline.title || displayDescription(node.entry.description);
		const ctx = `${noteContextPrefix(node)}${title}`.trim();

		// 1) Inline multi-line notes from this node's description
		for (let i = 0; i < inline.notes.length; i += 1) {
			out.push({
				kind: "text",
				key: `t:${node.entry.id}:${i}`,
				text: ctx ? `${ctx}: ${inline.notes[i]}` : inline.notes[i],
			});
		}

		// 2) Explicit note-children (render as links)
		for (const child of node.children) {
			if (!isNoteDescription(child.entry.description)) continue;
			out.push({
				kind: "link",
				key: `l:${child.entry.id}`,
				href: itemHref(child.entry.id),
				text: `${noteContextPrefix(child)}${displayDescription(child.entry.description)}`.trim(),
			});
		}

		// 3) Recurse into task-children
		for (const child of node.children) {
			if (isNoteDescription(child.entry.description)) continue;
			out.push(...collectAggregatedNotes(child));
		}

		return out;
	}

	// Persist phase expand/collapse state (so collapsed phases stay collapsed on refresh).
	// Stored as a map of { [phaseId]: boolean } in localStorage.
	const PHASE_OPEN_STORAGE_KEY = "mindscape.conport.phaseOpen.v1";
	let phaseOpenLoaded = $state(false);
	let phaseOpenById = $state<Record<number, boolean>>({});

	function loadPhaseOpenState(): void {
		if (typeof window === "undefined") return;
		try {
			const raw = window.localStorage.getItem(PHASE_OPEN_STORAGE_KEY);
			if (!raw) return;

			const parsed: unknown = JSON.parse(raw);
			if (!parsed || typeof parsed !== "object") return;

			const out: Record<number, boolean> = {};
			for (const [k, v] of Object.entries(
				parsed as Record<string, unknown>,
			)) {
				const id = Number(k);
				if (!Number.isFinite(id)) continue;
				if (typeof v !== "boolean") continue;
				out[id] = v;
			}
			phaseOpenById = out;
		} catch {
			// Ignore corrupted storage / JSON parse errors.
		}
	}

	function savePhaseOpenState(): void {
		if (typeof window === "undefined") return;
		try {
			window.localStorage.setItem(
				PHASE_OPEN_STORAGE_KEY,
				JSON.stringify(phaseOpenById),
			);
		} catch {
			// Ignore quota / storage errors.
		}
	}

	function getPhaseOpen(id: number, defaultOpen: boolean): boolean {
		// During SSR or before storage is loaded, fall back to the existing default behavior.
		if (!phaseOpenLoaded) return defaultOpen;
		return phaseOpenById[id] ?? defaultOpen;
	}

	function onPhaseToggle(id: number, e: Event): void {
		const el = e.currentTarget as HTMLDetailsElement | null;
		if (!el) return;
		phaseOpenById[id] = el.open;
		savePhaseOpenState();
	}

	onMount(() => {
		loadPhaseOpenState();
		phaseOpenLoaded = true;
	});
</script>

<ul class="select-none">
	{#each nodes as node (node.entry.id)}
		{@const inline = splitDescription(node.entry.description)}
		<li>
			{#if node.children.length > 0}
				{@const split = splitChildren(node.children)}
				{@const tasks = split.tasks}
				{@const isPhaseNode = isPhaseDescription(
					node.entry.description,
				)}

				<details
					open={isPhaseNode
						? getPhaseOpen(node.entry.id, level < 1)
						: level < 1}
					ontoggle={(e) =>
						isPhaseNode && onPhaseToggle(node.entry.id, e)}
				>
					<summary
						class="flex items-center gap-2 rounded-md py-1 pr-2 text-sm text-gray-100 hover:bg-white/5"
						style={indentStyle()}
					>
						<span
							class={`inline-block h-2 w-2 shrink-0 rounded-full ${statusColor(node.entry.status)}`}
						></span>
						<a
							href={itemHref(node.entry.id)}
							class="min-w-0 truncate hover:underline underline-offset-4 decoration-white/20 hover:decoration-white/60"
							onclick={(e) => e.stopPropagation()}
						>
							{showIdPrefix
								? `${idPrefix(node.entry.id)} `
								: ""}{inline.title ||
								displayDescription(node.entry.description)}
						</a>
					</summary>

					<div class="mt-0.5">
						{#if tasks.length > 0}
							<TaskExplorerTree
								nodes={tasks}
								{itemHref}
								level={level + 1}
								{showIdPrefix}
							/>
						{/if}
					</div>
				</details>

				{#if level === 0}
					{@const aggregated = collectAggregatedNotes(node)}
					<!-- Root nodes get a Notes subpanel; child tasks do not. -->
					<details
						class="mt-2 rounded-md border border-white/10 bg-black/10 p-2"
						style={indentStyle()}
					>
						<summary
							class="cursor-pointer text-xs font-semibold text-gray-200"
						>
							Notes ({aggregated.length})
						</summary>

						{#if aggregated.length === 0}
							<p class="mt-2 text-xs text-gray-300/80">
								No notes.
							</p>
						{:else}
							<ul class="mt-2 space-y-1 pl-3">
								{#each aggregated as note (note.key)}
									<li>
										{#if note.kind === "link"}
											<a
												href={note.href}
												class="block whitespace-pre-wrap break-words text-xs leading-snug text-gray-300/90 hover:text-gray-100 hover:underline"
											>
												{note.text}
											</a>
										{:else}
											<div
												class="block whitespace-pre-wrap break-words text-xs leading-snug text-gray-300/90"
											>
												{note.text}
											</div>
										{/if}
									</li>
								{/each}
							</ul>
						{/if}
					</details>
				{/if}
			{:else if !isNoteDescription(node.entry.description)}
				{#if isPhaseDescription(node.entry.description)}
					<details
						open={getPhaseOpen(node.entry.id, level < 1)}
						ontoggle={(e) => onPhaseToggle(node.entry.id, e)}
					>
						<summary
							class="flex items-center gap-2 rounded-md py-1 pr-2 text-sm text-gray-100 hover:bg-white/5"
							style={indentStyle()}
						>
							<span
								class={`inline-block h-2 w-2 shrink-0 rounded-full ${statusColor(node.entry.status)}`}
							></span>
							<a
								href={itemHref(node.entry.id)}
								class="min-w-0 truncate hover:underline underline-offset-4 decoration-white/20 hover:decoration-white/60"
								onclick={(e) => e.stopPropagation()}
							>
								{showIdPrefix
									? `${idPrefix(node.entry.id)} `
									: ""}{inline.title ||
									displayDescription(node.entry.description)}
							</a>
						</summary>

						<div class="mt-0.5"></div>
					</details>
				{:else}
					<div
						class="flex items-center gap-2 rounded-md py-1 pr-2 text-sm text-gray-100 hover:bg-white/5"
						style={indentStyle()}
					>
						<span
							class={`inline-block h-2 w-2 shrink-0 rounded-full ${statusColor(node.entry.status)}`}
						></span>
						<a
							href={itemHref(node.entry.id)}
							class="min-w-0 truncate hover:underline underline-offset-4 decoration-white/20 hover:decoration-white/60"
						>
							{showIdPrefix
								? `${idPrefix(node.entry.id)} `
								: ""}{inline.title ||
								displayDescription(node.entry.description)}
						</a>
					</div>
				{/if}
			{/if}
		</li>
	{/each}
</ul>
