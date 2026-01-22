import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';

export type ConportDecision = {
	id: number;
	timestamp: string;
	summary: string;
	rationale: string | null;
	implementation_details: string | null;
	tags: unknown;
};

export type ConportProgressEntry = {
	id: number;
	timestamp: string;
	status: string;
	description: string;
	parent_id: number | null;
};

export type ConportSystemPattern = {
	id: number;
	timestamp: string;
	name: string;
	description: string | null;
	tags: unknown;
};

export type ConportCustomData = {
	id: number;
	timestamp: string;
	category: string;
	key: string;
	value: unknown;
};

export type ConportLink = {
	id: number;
	timestamp: string;
	workspace_id: string;
	source_item_type: string;
	source_item_id: string;
	target_item_type: string;
	target_item_id: string;
	relationship_type: string;
	description: string | null;
};

export type ConportNowResponse = {
	app_id: string | null;
	db: string;
	product_context: unknown;
	active_context: unknown;
	recent_activity: {
		decisions: ConportDecision[];
		progress_entries: ConportProgressEntry[];
		system_patterns: ConportSystemPattern[];
		custom_data: ConportCustomData[];
		links: ConportLink[];
	};
};

export type ConportDashboardResponse = {
	app_id: string | null;
	db: string;
	progress: {
		by_status: Record<string, number>;
	};
	graph_health: {
		links: number;
		decisions: number;
		custom_data: number;
	};
};

export type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function apiBase(): string {
	// Never use an absolute base in the browser; it breaks remote access scenarios
	// where 127.0.0.1 refers to the client machine (not the server running containers).
	// Always prefer same-origin "/api/*" (reverse-proxied by SvelteKit in hooks.server.ts).
	if (browser) return '';

	// If PUBLIC_MINDSCAPE_API_BASE is unset, assume the UI is served behind a proxy
	// (same-origin) and use a relative base.
	const configured = env.PUBLIC_MINDSCAPE_API_BASE?.trim();
	return configured ? configured.replace(/\/$/, '') : '';
}

function apiUrl(path: string): string {
	const base = apiBase();
	return base ? `${base}${path}` : path;
}

async function getJson<T>(fetchFn: FetchLike, url: string): Promise<T> {
	// Prevent UI hangs when the dev proxy target is unreachable.
	// Can be overridden via PUBLIC_MINDSCAPE_API_TIMEOUT_MS.
	const timeoutMs = Number(env.PUBLIC_MINDSCAPE_API_TIMEOUT_MS ?? '10000');
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), Number.isFinite(timeoutMs) ? timeoutMs : 10000);

	try {
		const resp = await fetchFn(url, {
			headers: {
				accept: 'application/json'
			},
			signal: controller.signal
		});

		if (!resp.ok) {
			const text = await resp.text().catch(() => '');
			throw new Error(
				`Request failed: ${resp.status} ${resp.statusText}${text ? ` — ${text}` : ''}`
			);
		}

		return (await resp.json()) as T;
	} catch (err) {
		const name = (err as { name?: string } | null)?.name;
		if (name === 'AbortError') {
			throw new Error(`Request timed out after ${timeoutMs}ms`);
		}
		throw err;
	} finally {
		clearTimeout(timer);
	}
}

function buildUrl(path: string, params: Record<string, string | null | undefined> = {}): string {
	const base = apiBase();

	console.log('[ConPort API Client] buildUrl called:', { path, params, base });

	if (base) {
		const url = new URL(`${base}${path}`);
		for (const [k, v] of Object.entries(params)) {
			if (v != null && v !== '') url.searchParams.set(k, v);
		}
		const result = url.toString();
		console.log('[ConPort API Client] buildUrl result (with base):', result);
		return result;
	}

	// Same-origin relative path.
	const url = new URL(path, 'http://local');
	for (const [k, v] of Object.entries(params)) {
		console.log(`[ConPort API Client] Adding param: ${k}=${v}, condition: v != null (${v != null}) && v !== '' (${v !== ''})`);
		if (v != null && v !== '') url.searchParams.set(k, v);
	}
	const result = url.pathname + url.search;
	console.log('[ConPort API Client] buildUrl result (same-origin):', result);
	return result;
}

export async function conportNow(
	fetchFn: FetchLike,
	opts: { app_id?: string | null; db?: string | null } = {}
): Promise<ConportNowResponse> {
	return getJson(
		fetchFn,
		buildUrl('/api/v1/conport/now', { app_id: opts.app_id ?? null, db: opts.db ?? null })
	);
}

export async function conportDashboard(
	fetchFn: FetchLike,
	opts: { app_id?: string | null; db?: string | null } = {}
): Promise<ConportDashboardResponse> {
	return getJson(
		fetchFn,
		buildUrl('/api/v1/conport/dashboard', { app_id: opts.app_id ?? null, db: opts.db ?? null })
	);
}

export type ConportSearchResponse = {
	app_id: string | null;
	db: string;
	query: string;
	fts: {
		decisions: boolean;
		custom_data: boolean;
	};
	results: {
		decisions: ConportDecision[];
		custom_data: ConportCustomData[];
	};
};

export type ConportDecisionsListResponse = {
	app_id: string | null;
	db: string;
	decisions: ConportDecision[];
};

export type ConportCustomDataListResponse = {
	app_id: string | null;
	db: string;
	custom_data: ConportCustomData[];
};

export type ConportSystemPatternsListResponse = {
	app_id: string | null;
	db: string;
	system_patterns: ConportSystemPattern[];
};

export type ConportProgressListResponse = {
	app_id: string | null;
	db: string;
	progress_entries: ConportProgressEntry[];
};

export type ConportViewsListResponse = {
	app_id: string | null;
	db: string;
	views: Array<{
		id: number;
		timestamp: string;
		category: string;
		key: string;
		value: unknown;
	}>;
};

export type ConportItemType =
	| 'decision'
	| 'progress'
	| 'system_pattern'
	| 'custom_data'
	| 'context_link'
	| 'product_context'
	| 'active_context';

export type ConportItemResponse = {
	app_id: string | null;
	db: string;
	type: ConportItemType;
	item: Record<string, unknown>;
};

export type ConportLinksResponse = {
	app_id: string | null;
	db: string;
	links: ConportLink[];
};

export type ConportProgressResponse = {
	app_id: string | null;
	db: string;
	progress: ConportProgressEntry;
};

export type ConportViewResponse = {
	app_id: string | null;
	db: string;
	view: {
		id: number;
		timestamp: string;
		category: string;
		key: string;
		value: unknown;
	};
};

export async function conportSearch(
	fetchFn: FetchLike,
	opts: { q: string; limit?: number; app_id?: string | null; db?: string | null }
): Promise<ConportSearchResponse> {
	return getJson(
		fetchFn,
		buildUrl('/api/v1/conport/search', {
			q: opts.q,
			limit: opts.limit != null ? String(opts.limit) : null,
			app_id: opts.app_id ?? null,
			db: opts.db ?? null
		})
	);
}

export async function conportDecisionsList(
	fetchFn: FetchLike,
	opts: { limit?: number; app_id?: string | null; db?: string | null } = {}
): Promise<ConportDecisionsListResponse> {
	return getJson(
		fetchFn,
		buildUrl('/api/v1/conport/decisions', {
			limit: opts.limit != null ? String(opts.limit) : null,
			app_id: opts.app_id ?? null,
			db: opts.db ?? null
		})
	);
}

export async function conportCustomDataList(
	fetchFn: FetchLike,
	opts: {
		category?: string | null;
		key?: string | null;
		limit?: number;
		app_id?: string | null;
		db?: string | null;
	} = {}
): Promise<ConportCustomDataListResponse> {
	return getJson(
		fetchFn,
		buildUrl('/api/v1/conport/custom-data', {
			category: opts.category ?? null,
			key: opts.key ?? null,
			limit: opts.limit != null ? String(opts.limit) : null,
			app_id: opts.app_id ?? null,
			db: opts.db ?? null
		})
	);
}

export async function conportSystemPatternsList(
	fetchFn: FetchLike,
	opts: { limit?: number; app_id?: string | null; db?: string | null } = {}
): Promise<ConportSystemPatternsListResponse> {
	return getJson(
		fetchFn,
		buildUrl('/api/v1/conport/system-patterns', {
			limit: opts.limit != null ? String(opts.limit) : null,
			app_id: opts.app_id ?? null,
			db: opts.db ?? null
		})
	);
}

export async function conportProgressList(
	fetchFn: FetchLike,
	opts: {
		status?: string | null;
		parent_id?: number | null;
		description_prefix?: string | null;
		limit?: number;
		app_id?: string | null;
		db?: string | null;
	} = {}
): Promise<ConportProgressListResponse> {
	return getJson(
		fetchFn,
		buildUrl('/api/v1/conport/progress', {
			status: opts.status ?? null,
			parent_id: opts.parent_id != null ? String(opts.parent_id) : null,
			description_prefix: opts.description_prefix ?? null,
			limit: opts.limit != null ? String(opts.limit) : null,
			app_id: opts.app_id ?? null,
			db: opts.db ?? null
		})
	);
}

export async function conportViewsList(
	fetchFn: FetchLike,
	opts: { limit?: number; app_id?: string | null; db?: string | null } = {}
): Promise<ConportViewsListResponse> {
	return getJson(
		fetchFn,
		buildUrl('/api/v1/conport/views', {
			limit: opts.limit != null ? String(opts.limit) : null,
			app_id: opts.app_id ?? null,
			db: opts.db ?? null
		})
	);
}

export async function conportItem(
	fetchFn: FetchLike,
	opts: { type: ConportItemType; id: number; app_id?: string | null; db?: string | null }
): Promise<ConportItemResponse> {
	return getJson(
		fetchFn,
		buildUrl('/api/v1/conport/item', {
			type: opts.type,
			id: String(opts.id),
			app_id: opts.app_id ?? null,
			db: opts.db ?? null
		})
	);
}

export async function conportLinks(
	fetchFn: FetchLike,
	opts: {
		source_item_type?: string | null;
		source_item_id?: string | null;
		target_item_type?: string | null;
		target_item_id?: string | null;
		limit?: number;
		app_id?: string | null;
		db?: string | null;
	} = {}
): Promise<ConportLinksResponse> {
	return getJson(
		fetchFn,
		buildUrl('/api/v1/conport/links', {
			source_item_type: opts.source_item_type ?? null,
			source_item_id: opts.source_item_id ?? null,
			target_item_type: opts.target_item_type ?? null,
			target_item_id: opts.target_item_id ?? null,
			limit: opts.limit != null ? String(opts.limit) : null,
			app_id: opts.app_id ?? null,
			db: opts.db ?? null
		})
	);
}

export async function conportProgress(
	fetchFn: FetchLike,
	opts: { id: number; app_id?: string | null; db?: string | null }
): Promise<ConportProgressResponse> {
	const base = apiBase();
	if (base) {
		const url = new URL(`${base}/api/v1/conport/progress/${opts.id}`);
		if (opts.app_id) url.searchParams.set('app_id', opts.app_id);
		if (opts.db) url.searchParams.set('db', opts.db);
		return getJson(fetchFn, url.toString());
	}

	const url = new URL(`/api/v1/conport/progress/${opts.id}`, 'http://local');
	if (opts.app_id) url.searchParams.set('app_id', opts.app_id);
	if (opts.db) url.searchParams.set('db', opts.db);
	return getJson(fetchFn, url.pathname + url.search);
}

export async function conportGetView(
	fetchFn: FetchLike,
	opts: { key: string; app_id?: string | null; db?: string | null }
): Promise<ConportViewResponse> {
	const base = apiBase();
	if (base) {
		const url = new URL(`${base}/api/v1/conport/views/${encodeURIComponent(opts.key)}`);
		if (opts.app_id) url.searchParams.set('app_id', opts.app_id);
		if (opts.db) url.searchParams.set('db', opts.db);
		return getJson(fetchFn, url.toString());
	}

	const url = new URL(`/api/v1/conport/views/${encodeURIComponent(opts.key)}`, 'http://local');
	if (opts.app_id) url.searchParams.set('app_id', opts.app_id);
	if (opts.db) url.searchParams.set('db', opts.db);
	return getJson(fetchFn, url.pathname + url.search);
}
