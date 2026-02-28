# Decision Log

---
## Decision
*   [2026-02-28 19:51:35] Resolved ConPort panel display issue for model-proxy app

## Rationale
*   User reported that newly added LiteLLM migration phases (IDs 94-100) were not displaying in the ConPort panel, despite being present in the database. Investigation revealed the data was correctly stored and the API was returning it properly, but the browser was showing cached data.

## Implementation Details
*   Diagnostic process:
1. Verified database contained all 100 progress entries including new phases (IDs 94-100)
2. Confirmed API on port 8011 correctly returns phases with description_prefix=Phase filter
3. Verified web UI configuration: port 8012 (web) proxies to port 8011 (API)
4. Tested API endpoints directly - all working correctly
5. Root cause: Browser cache preventing display of new data
6. Solution: Clear browser cache/storage or use incognito mode

Key findings:
- Database: ✅ 100 entries, 10 phases with WBS metadata
- API: ✅ Returns all 7 LiteLLM phases (94-100) correctly
- Configuration: ✅ Correct ports and app_id parameter
- Issue: Browser-side caching

Created diagnostic scripts: check_conport_data.py, test_conport_api.py, debug_dashboard_api.md

---
## Decision
*   [2026-02-17 01:46:26] MCP ConPort integration test completed successfully

## Rationale
*   Verified that ConPort MCP tools (log_progress, log_decision, update_product_context) are functioning correctly via the MCP server interface

## Implementation Details
*   Successfully called log_progress with parent-child relationship (id 39 -> id 40). MCP server is operational and ready for production use.

---
## Decision
*   [2026-02-06 02:22:22] Implemented WBS v1 schema with project root for snapmail

## Rationale
*   Following WBS v1 schema which requires project > phase > task hierarchy. Created project entry (ID 34) with entity_type='project' and linked existing phases (4, 15, 27) as children. This enables proper plan root detection in dashboard.

## Implementation Details
*   1) Created progress entry '[Plan] Snapmail' (ID 34) with parent_id=null
2) Added WBS metadata: entity_type='project', title='Snapmail', priority=P0, order=0
3) Updated phases 4, 15, 27 to have parent_id=34
4) Fixed frontend bug where phases were incorrectly assigned as their own parent during 'attached notes' processing
5) Deleted stray entry ID 39 from mindscape-ai database

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
