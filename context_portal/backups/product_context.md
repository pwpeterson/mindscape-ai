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
{'version': '1.0', 'entity_types': ['project', 'phase', 'task'], 'required_fields': ['entity_type', 'title'], 'optional_fields': ['owner', 'priority', 'tags', 'estimate_points', 'due_date', 'order', 'external_refs'], 'allowed_statuses': ['TODO', 'IN_PROGRESS', 'DONE'], 'priority_values': ['P0', 'P1', 'P2', 'P3'], 'notes': "One app per workspace. Use progress_entries for hierarchy (parent_id). Store metadata in custom_data category 'wbs_meta' keyed by 'progress:<ID>'."}

