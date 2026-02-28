# Product Context
## Project Name
Mindscape-AI

## Tagline
A unified dashboard for visualizing AI awareness - integrating ConPort (Context-Portal), Mem0, and prompt management.

## Description
Mindscape-AI is a unified dashboard and management interface for visualizing, monitoring, and managing the complete awareness landscape of AI systems. It unifies three context layers (Project Knowledge via ConPort, User Memory via Mem0, and Instructions/Prompts via local prompt files) into a single, real-time dashboard to improve debugging, transparency, and token optimization.

## Sources
{'readme': 'README.md', 'prd': 'docs/projectPRD.MD', 'project_brief': None}

## Status
docs/scaffolding phase

## Target Users
*   AI/ML developers building LLM-backed apps
*   Power users of coding assistants (Roo Code / Cline / Cursor)
*   Researchers studying memory/context systems

## Core Layers
*   {'name': 'Project Knowledge', 'source': 'ConPort (Context-Portal)'}
*   {'name': 'User Memory', 'source': 'Mem0'}
*   {'name': 'Instructions', 'source': 'Local prompts'}

## Planned Architecture
{'backend': 'FastAPI REST API (optional MCP client integration)', 'frontend': 'SvelteKit (Svelte 5)', 'realtime': 'Server-Sent Events (SSE)'}

## Roadmap
*   Phase 1: Core adapters and basic dashboard (ConPort UI parity)
*   Phase 2: Mem0 integration and prompt adapters
*   Phase 3: Processing monitor (context retrieval trace)
*   Phase 4: MCP server mode

## Notes
{'bootstrapped_at_utc': '2026-01-08T21:41:48.215Z', 'bootstrap_method': 'Derived from README.md and docs/projectPRD.MD (projectBrief.md not found in workspace root).'}

## Wbs Schema
{'project_root': {'id': 34, 'entity_type': 'project', 'title': 'Snapmail'}, 'phases': [{'id': 4, 'title': 'Phase 1: Prototype Development', 'weeks': '1-6'}, {'id': 15, 'title': 'Phase 2: Backend & Integration', 'weeks': '7-14'}, {'id': 27, 'title': 'Phase 3: Mobile Application', 'weeks': '15-22'}], 'notes': 'All phases now properly nested under project root per WBS v1.0 schema'}

## Last Mcp Test
2026-02-17T01:48:00Z

## Mcp Tools Status
{'log_progress': 'working', 'log_decision': 'working', 'update_product_context': 'working'}

## Known Issues
{'browser_cache': 'ConPort panel may show stale data due to browser caching. Solution: Clear browser cache/storage or use incognito mode for testing. The API correctly returns data but browsers may cache responses.'}

## Troubleshooting Tips
{'conport_not_updating': "If ConPort panel doesn't show new data: 1) Verify data in database directly, 2) Test API endpoints with curl, 3) Check browser DevTools Network tab for API responses, 4) Clear browser cache or use incognito mode, 5) Verify correct app_id parameter in URL"}

## Diagnostic Tools
{'check_conport_data': 'Python script to verify ConPort database contents and WBS metadata', 'test_conport_api': 'Python script to simulate API queries and verify responses', 'debug_dashboard_api': 'Markdown guide for debugging ConPort dashboard API calls in browser'}

