<script lang="ts">
	import type { ProgressTreeNodeWithWbs } from "$lib/types/progress";
	import { onMount } from "svelte";
	import TaskExplorerTree from "./TaskExplorerTree.svelte";

	let {
		nodes,
		itemHref,
		level = 0,
		showIdPrefix = false,
	} = $props<{
		nodes: ProgressTreeNodeWithWbs[];
		itemHref: (id: number) => string;
		level?: number;
		showIdPrefix?: boolean;
	}>();

	function idPrefix(id: number): string {
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

	function entityIcon(type: string): string {
		switch (type) {
			case "project":
				return "📦";
			case "phase":
				return "📋";
			case "task":
				return "✓";
			default:
				return "•";
		}
	}

	function phaseMarker(status: string): string {
		switch (status) {
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
		switch (status) {
			case "IN_PROGRESS":
				return "Phase (In progress)";
			case "DONE":
				return "Phase (Done)";
			case "TODO":
			default:
				return "Phase (Pending action)";
		}
	}

	function indentStyle(): string {
		return `padding-left: ${0.75 + level * 1.0}rem;`;
	}

	function getTitle(node: ProgressTreeNodeWithWbs): string {
		return node.entry.wbs_meta?.title ?? stripPriorityPrefix(node.entry.description);
	}

	function stripPriorityPrefix(description: string): string {
		return description.replace(/^\s*\[p\d+\]\s*/i, "");
	}

	function splitDescription(description: string): {
		title: string;
		notes: string[];
	} {
		const cleaned = stripPriorityPrefix(description).trim();
		const lines = cleaned.split(/\r?\n/).map((l) => l.trimEnd());
		const nonEmpty = lines.filter((l) => l.trim().length > 0);
		const title = nonEmpty[0] ?? "";
		const notes = nonEmpty.slice(1);
		return { title, notes };
	}

	function displayDescription(description: string): string {
		return stripPriorityPrefix(description).trim();
	}

	function isNoteDescription(description: string): boolean {
		return /^\s*(?:\[p\d+\]\s*)?(?:phase\s+\d+\s*:|notes?\s*[:—–-]|\[notes?\]\s*[:—–-])/i.test(
			description,
		);
	}

	const UI_FORCE_TASK_IDS = new Set<number>([29]);
	const UI_STATUS_ONLY_IDS = new Set<number>([29]);

	function isNoteNode(node: ProgressTreeNodeWithWbs): boolean {
		if (UI_FORCE_TASK_IDS.has(node.entry.id)) return false;
		return isNoteDescription(node.entry.description);
	}

	function cleanStatusUpdateLine(line: string): string {
		return line.replace(/^\s*[—–-]\s*/, "").trim();
	}

	function isPhaseNode(node: ProgressTreeNodeWithWbs): boolean {
		return node.entry.wbs_meta?.entity_type === "phase";
	}

	function splitChildren(children: ProgressTreeNodeWithWbs[]): {
		tasks: ProgressTreeNodeWithWbs[];
		notes: ProgressTreeNodeWithWbs[];
	} {
		const tasks: ProgressTreeNodeWithWbs[] = [];
		const notes: ProgressTreeNodeWithWbs[] = [];

		for (const c of children) {
			if (isNoteNode(c)) notes.push(c);
			else tasks.push(c);
		}

		return { tasks, notes };
	}

	type AggregatedNote =
		| { kind: "text"; key: string; text: string }
		| { kind: "link"; key: string; text: string; href: string };

	function noteContextPrefix(node: ProgressTreeNodeWithWbs): string {
		return showIdPrefix ? `${idPrefix(node.entry.id)} ` : "";
	}

	function collectAggregatedNotes(node: ProgressTreeNodeWithWbs): AggregatedNote[] {
		const out: AggregatedNote[] = [];
		const inline = splitDescription(node.entry.description);
		const title = getTitle(node);
		const ctx = `${noteContextPrefix(node)}${title}`.trim();
		const statusOnly = UI_STATUS_ONLY_IDS.has(node.entry.id);

		for (let i = 0; i < inline.notes.length; i += 1) {
			const cleaned = cleanStatusUpdateLine(inline.notes[i]);
			if (!cleaned) continue;

			out.push({
				kind: "text",
				key: `t:${node.entry.id}:${i}`,
				text: statusOnly
					? cleaned
					: ctx
						? `${ctx}: ${cleaned}`
						: cleaned,
			});
		}

		for (const child of node.children) {
			if (!isNoteNode(child)) continue;
			out.push({
				kind: "link",
				key: `l:${child.entry.id}`,
				href: itemHref(child.entry.id),
				text: `${noteContextPrefix(child)}${getTitle(child)}`.trim(),
			});
		}

		for (const child of node.children) {
			if (isNoteNode(child)) continue;
			out.push(...collectAggregatedNotes(child));
		}

		return out;
	}

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
		{@const title = getTitle(node)}
		{@const entityType = node.entry.wbs_meta?.entity_type ?? "unknown"}
		{@const isPhase = isPhaseNode(node)}
		<li>
			{#if node.children.length > 0}
				{@const split = splitChildren(node.children)}
				{@const tasks = split.tasks}

				<details
					open={isPhase
						? getPhaseOpen(node.entry.id, level < 1)
						: level < 1}
					ontoggle={(e) =>
						isPhase && onPhaseToggle(node.entry.id, e)}
				>
					<summary
						class="flex items-center gap-2 rounded-md py-1 pr-2 text-sm text-gray-100 hover:bg-white/5"
						style={indentStyle()}
					>
						{#if isPhase}
							<span
								class="shrink-0"
								aria-hidden="true"
								title={phaseMarkerLabel(node.entry.status)}
								>{phaseMarker(node.entry.status)}</span
							>
						{:else}
							<span
								class="shrink-0"
								title={entityType}
								>{entityIcon(entityType)}</span
							>
						{/if}
						<a
							href={itemHref(node.entry.id)}
							class="min-w-0 truncate hover:underline underline-offset-4 decoration-white/20 hover:decoration-white/60"
							onclick={(e) => e.stopPropagation()}
						>
							{showIdPrefix ? `${idPrefix(node.entry.id)} ` : ""}{title}
						</a>
						{#if node.entry.wbs_meta?.priority}
							<span class="ml-1 text-xs opacity-60">
								[{node.entry.wbs_meta.priority}]
							</span>
						{/if}
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
			{:else if !isNoteNode(node)}
				{#if isPhase}
					<details
						open={getPhaseOpen(node.entry.id, level < 1)}
						ontoggle={(e) => onPhaseToggle(node.entry.id, e)}
					>
						<summary
							class="flex items-center gap-2 rounded-md py-1 pr-2 text-sm text-gray-100 hover:bg-white/5"
							style={indentStyle()}
						>
							<span
								class="shrink-0"
								aria-hidden="true"
								title={phaseMarkerLabel(node.entry.status)}
								>{phaseMarker(node.entry.status)}</span
							>
							<a
								href={itemHref(node.entry.id)}
								class="min-w-0 truncate hover:underline underline-offset-4 decoration-white/20 hover:decoration-white/60"
								onclick={(e) => e.stopPropagation()}
							>
								{showIdPrefix ? `${idPrefix(node.entry.id)} ` : ""}{title}
							</a>
							{#if node.entry.wbs_meta?.priority}
								<span class="ml-1 text-xs opacity-60">
									[{node.entry.wbs_meta.priority}]
								</span>
							{/if}
						</summary>

						<div class="mt-0.5"></div>
					</details>
				{:else}
					<div
						class="flex items-center gap-2 rounded-md py-1 pr-2 text-sm text-gray-100 hover:bg-white/5"
						style={indentStyle()}
					>
						<span
							class="shrink-0"
							title={entityType}
							>{entityIcon(entityType)}</span
						>
						<a
							href={itemHref(node.entry.id)}
							class="min-w-0 truncate hover:underline underline-offset-4 decoration-white/20 hover:decoration-white/60"
						>
							{showIdPrefix ? `${idPrefix(node.entry.id)} ` : ""}{title}
						</a>
						{#if node.entry.wbs_meta?.priority}
							<span class="ml-1 text-xs opacity-60">
								[{node.entry.wbs_meta.priority}]
							</span>
						{/if}
					</div>
				{/if}
			{/if}
		</li>
	{/each}
</ul>
