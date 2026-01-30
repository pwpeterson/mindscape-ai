# Progress Log

## Completed Tasks
*   [2026-01-22 23:32:00] Improved Progress page UX: hide project board when status filter active, standardized button styling
*   [2026-01-22 23:31:43] Fixed app_id parameter propagation in web UI components (ConportNowView, Progress page, Item page, Dashboard view)
*   [2026-01-22 19:18:57] WBS v1.0 Schema Implementation & Migration Complete
*   [2026-01-13 00:09:58] (Superseded) Temporary Phase 2 parent created during renaming — DONE (rolled up into P-18 notes).
*   [2026-01-13 00:04:31] [P1] Implement Mem0 adapter (self-hosted + cloud config) + API endpoints — DONE (rolled up into P-18 notes).
*   [2026-01-11 23:01:14] [P0] Phase 0 — Docs & parity alignment
*   [2026-01-11 23:01:14] [P0] Publish canonical PRD at docs/projectPRD.MD
*   [2026-01-11 23:01:14] [P0] Align README with target architecture patterns (FastAPI + SvelteKit + SSE)
*   [2026-01-11 23:01:14] [P0] Phase 1 — ConPort Workbench parity (API + UI)

Notes (rolled up):
[P2] Security hardening: never log secrets; strict input validation and parameterized SQL everywhere

DONE (2026-01-12):
- Added a defensive length limit for the db query parameter (DoS guardrail).
- Removed dynamic SQL string construction for item reads (use fixed per-type SELECT statements).
- Added API test coverage for oversized db parameter rejection.
- Tests pass in uv environment.
*   [2026-01-11 23:01:14] [P0] Implement Workbench DB resolution + safe path validation (context_portal/, *.db, no traversal)
*   [2026-01-11 23:01:14] [P0] Implement Workbench API endpoints: GET /conport/now, /dashboard, /search, /item
*   [2026-01-11 23:01:14] [P0] Implement Workbench API endpoints: GET/PATCH /conport/progress/{id}
*   [2026-01-11 23:01:14] [P0] Implement Workbench API endpoints: GET/PUT/DELETE /conport/views/{view_key}
*   [2026-01-11 23:01:14] [P0] Implement Workbench API endpoints: GET/POST/DELETE /conport/links
*   [2026-01-11 23:01:14] [P0] Add SSE endpoint: GET /api/v1/events/stream (heartbeat + event objects)
*   [2026-01-11 23:01:14] [P0] Add Svelte EventSource client + live refresh for key panels
*   [2026-01-11 23:01:14] [P1] UI: ensure deep-links and filtering across decisions/custom-data/patterns/progress
*   [2026-01-11 23:01:14] [P1] UI: improve Progress visualization (tree/board) and navigation affordances
*   [2026-01-11 23:01:14] [P1] Testing: add API tests for ConPort Workbench endpoints + DB validation rules
*   [2026-01-11 23:01:14] [P2] Security hardening: never log secrets; strict input validation and parameterized SQL everywhere

DONE (2026-01-12):
- Added a defensive length limit for the db query parameter (DoS guardrail).
- Removed dynamic SQL string construction for item reads (use fixed per-type SELECT statements).
- Added API test coverage for oversized db parameter rejection.
- Tests pass in uv environment.
*   [2026-01-11 23:01:14] [P1] Phase 2 — Mem0 + prompts + token analytics

DONE (2026-01-13):
- Phase 2 delivered end-to-end across API + UI.
- Multi-app scoping: app_id derived from each app’s pyproject.toml; global app selector + module tabs.
- ConPort UI: sidebar layout + consistent headers; Progress explorer tree/board; notes behavior updated so child tasks don’t render note subpanels and notes bubble into parent/root.
- Mem0: in-process client + FastAPI routes + UI for list/search with filters.
- Prompts: signature endpoint + SSE hot reload; per-file scan/stats + approx tokens via `GET /api/v1/prompts/files` + UI table.
- Token analytics: `/api/v1/tokens/breakdown` + Tokens UI.

Child rollups:
- P-19 DONE (implemented as part of P-34)
- P-20 DONE (Mem0 UI list/search)
- P-21 DONE (Prompts files + per-file token estimation)
- P-22 DONE (Prompts hot reload)
- P-23 DONE (Token analytics)
- P-33 DONE (Phase 2 completion snapshot)
- P-34 DONE (Mem0 integration)
- P-35 DONE (superseded placeholder)

Validation:
- `uv run pytest -q` passes for relevant suites; `cd web && npm run check` passes.
*   [2026-01-11 23:01:14] [P1] Implement Mem0 adapter (self-hosted + cloud config) + API endpoints — DONE (implemented as part of P-34; details rolled up into P-18 notes).
*   [2026-01-11 23:01:14] [P1] UI panel: list/search memories by user_id with metadata + relevance scores — DONE (details rolled up into P-18 notes).
*   [2026-01-11 23:01:14] [P1] Prompt management: scan configurable directories + per-file token counts

DONE (2026-01-13):
- Backend: added `GET /api/v1/prompts/files` in [`prompts router`](src/mindscape_ai/api/routes/prompts.py:1) to list prompt files with per-file stats (approx tokens via chars/4), scoped by `app_id`, with safe virtual paths (no absolute path leakage). Supports `max_files` and `max_file_bytes` (skip deep stats for large files).
- Tests: extended [`tests/test_prompts_api.py`](tests/test_prompts_api.py:1) to cover `/prompts/files` (configured/unconfigured + no path leakage).
- Frontend: added `promptsFiles()` in [`web/src/lib/api/prompts.ts`](web/src/lib/api/prompts.ts:1) and updated [`web/src/routes/prompts/+page.svelte`](web/src/routes/prompts/+page.svelte:1) to display a per-file table (path/bytes/chars/lines/approx_tokens) with controls for `max_files` and `max_file_bytes`.
- Validation: `uv run pytest -q tests/test_prompts_api.py` passes; `cd web && npm run check` passes.
*   [2026-01-11 23:01:14] [P1] Prompt hot reload: file watching + UI updates — DONE (details rolled up into P-18 notes).
*   [2026-01-11 23:01:14] [P1] Unified token breakdown by source (ConPort / Mem0 / prompts) — DONE (details rolled up into P-18 notes).
*   [2026-01-11 23:01:14] [P3] Phase 4 — Optional MCP server mode — DONE (2026-01-13): implemented local stdio MCP server via FastMCP in `mindscape_ai.mcp_server` exposing tools (conport.now/search, mem0.search, prompts.files, tokens.breakdown) + resources (conport://now, tokens://breakdown); documented usage in README; backend tests passed.
*   [2026-01-11 23:01:14] [P3] Expose Mindscape-AI aggregated view as an MCP server — DONE (2026-01-13): added local stdio FastMCP server in `mindscape_ai.mcp_server` exposing conport.now/search, mem0.search, prompts.files, tokens.breakdown and resources conport://now + tokens://breakdown; validated via pytest.

## In Progress Tasks
*   [2026-01-11 23:01:14] [PLAN] Mindscape-AI project plan (derived from README + PRD v1.0.0)

## TODO Tasks
*   [2026-01-28 21:47:45] Seed progress entry for tests
*   [2026-01-11 23:01:14] [P2] Phase 3 — Processing monitor + knowledge graph visualization
*   [2026-01-11 23:01:14] [P2] Define event taxonomy + context retrieval trace model
*   [2026-01-11 23:01:14] [P2] UI: timeline of 'prompt processed' events with token breakdown and sources
*   [2026-01-11 23:01:14] [P2] Graph visualization UI for ConPort links (relationships view)
*   [2026-01-11 23:01:14] [P2] Deployment & ops
*   [2026-01-11 23:01:14] [P2] Containerize (Podman/Quadlet): single image with FastAPI + SvelteKit + health checks
*   [2026-01-11 23:01:14] [P2] Add production config + CORS tightening via env vars
