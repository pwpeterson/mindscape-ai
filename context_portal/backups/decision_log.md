# Decision Log

---
## Decision
*   [2026-01-30 22:21:28] Rename MCP tool names to remove '.' (use underscore names)

## Rationale
*   Some MCP hosts/clients and tooling ecosystems treat '.' as a namespace separator or have restrictions/edge cases around dotted tool identifiers. Using underscore tool names avoids ambiguity and improves compatibility.

## Implementation Details
*   Updated FastMCP tool registrations in src/mindscape_ai/mcp_server.py: conport.now→conport_now, conport.search→conport_search, mem0.search→mem0_search, prompts.files→prompts_files, tokens.breakdown→tokens_breakdown. Updated documentation references in README.md and context_portal/backups/progress_log.md. MCP resources remained unchanged: conport://now and tokens://breakdown.

---
## Decision
*   [2026-01-22 23:31:26] Fixed multi-app database selection in web UI by ensuring app_id parameter propagation

## Rationale
*   The web UI has a multi-app architecture where users can select different projects (e.g., mindscape-ai, model-proxy) via an app dropdown. However, several UI components were missing the app_id query parameter in their API calls, causing them to default to the wrong database. The fix ensures all components read app_id from the URL and pass it to API calls, maintaining correct database context throughout navigation.

## Implementation Details
*   Modified 4 components: (1) ConportNowView.svelte - added app_id to WBS metadata fetch, (2) progress/+page.svelte - added buildQuery() helper and app_id to all API calls, (3) item/+page.svelte - added app_id parameter reading/passing, (4) ConportDashboardView.svelte - added app_id to WBS metadata fetch. Pattern: Use buildQuery() helper that prioritizes app_id over db parameter and preserves existing query params in links.

---
## Decision
*   [2026-01-22 19:18:40] Implemented WBS v1.0 schema for progress management

## Rationale
*   Adopted Work Breakdown Structure (WBS) v1.0 to provide hierarchical project/phase/task organization with rich metadata (entity_type, priority P0-P3, tags, owner, estimates, order). This enables proper project management visualization and improves UI clarity with entity-based icons and structured sorting.

## Implementation Details
*   Schema stored in product_context.wbs_schema. Metadata stored in custom_data category='wbs_meta' with keys 'progress:<ID>'. Migrated 33 existing progress records: 1 project, 6 phases, 26 tasks. Updated 5 frontend components (progress page, TaskExplorerTree, TaskTree, ConportDashboardView, ConportNowView) to fetch and display WBS metadata with entity icons, priority badges, and tag chips.

---
## Decision
*   [2026-01-12 23:25:00] P-19: Integrate Mem0 by embedding a Mem0 client in Mindscape-AI FastAPI (HTTP) and mirroring the mem0-mcp tool surface; do not try to call the mem0 MCP stdio server from the web API.

## Rationale
*   The existing mem0 MCP server runs over stdio transport (designed for MCP clients), which is not a practical/secure/operationally-simple interface for the Mindscape web API. Mindscape already exposes HTTP endpoints for ConPort and the web UI expects HTTP. Therefore, implement /api/v1/mem0/* endpoints that wrap mem0 operations directly.

## Implementation Details
*   - Add a new FastAPI router, similar to conport routes, under /api/v1/mem0.
- Provide endpoints mirroring tools: add_memory, search_memories, list_memories, get_memory, update_memory, delete_memory, delete_all_memories, get_memory_history.
- Use safe query param validation patterns from conport routes (length/charset guardrails).
- Use a separate write-gate env var (e.g., MINDSCAPE_MEM0_WRITE=true) for mutating endpoints.
- Keep scoping consistent with mem0-mcp: store app_id/project_id in metadata and filter results accordingly.
- Configure mem0 via env (preferably MEM0_* to align with mem0-mcp Settings) or a Mindscape config stanza; avoid hardcoded secrets.
- Add tests similar to existing API tests for ConPort.
