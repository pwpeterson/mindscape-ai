# Mindscape-AI — Product Requirements Document (PRD)

> Canonical PRD location for the repo docs.
>
> Source draft: `../projectPRD.md` (kept for authoring convenience).

## Document Information

| Field | Value |
|---|---|
| Project | Mindscape-AI |
| Version | 1.0.0 |
| Status | Draft |
| Created | January 2026 |
| Owner | Paul |

---

## 1. Executive Summary

Mindscape-AI is a unified dashboard and management interface for visualizing, monitoring, and managing the complete “awareness landscape” of AI systems.

It integrates three context layers:

1. **Project Knowledge** via Context-Portal (ConPort)
2. **User Memory** via Mem0
3. **Instructions / Prompts** via local prompt files

The immediate goal is to provide a *single pane of glass* that shows:

- what context exists,
- what context was retrieved for a given prompt,
- how that context changes over time,
- and how those changes impact token budgets.

---

## 2. Problem Statement

### 2.1 Current Challenges

1. **Fragmented context visibility**: ConPort, Mem0, and local prompts are separate surfaces.
2. **Debugging complexity**: unexpected model output is hard to attribute to a specific context source.
3. **Token optimization blindness**: no consolidated view of token consumption per source.
4. **Operational overhead**: context-switching between different tools and interfaces.

### 2.2 Target Users

- AI/ML developers building LLM-backed apps
- power users of coding assistants (Roo Code / Cline / Cursor)
- researchers studying memory/context systems

---

## 3. Product Vision

Mindscape-AI makes the invisible visible: an instrumentation panel for AI context.

---

## 4. Goals & Success Metrics

### 4.1 Primary Goals

| Goal | Description | Metric |
|---|---|---|
| Unified visibility | One interface for ConPort + Mem0 + prompts | 100% of core data surfaces reachable |
| Real-time monitoring | Live updates as context changes | < 500ms UI update latency (typical local env) |
| Context debugging | Attribute “why did the model do that?” | reduce debugging time by 50% |
| Token optimization | Identify redundancies and budget hotspots | enable 20% context efficiency improvement |

---

## 5. Functional Requirements

### 5.1 ConPort Integration

#### 5.1.1 Modes

Mindscape-AI must support two ConPort access modes (mirroring what we built for ConPort-UI / TaskFlow patterns):

1. **Workbench (SQLite) mode (read-only by default)**
   - Reads a ConPort SQLite DB under `context_portal/`.
   - Uses parameterized SQL only.
   - Degrades gracefully if optional FTS tables don’t exist.
   - Uses strict DB path resolution rules:
     - must be under `context_portal/`
     - must end in `.db`
     - disallow `..` traversal

2. **MCP mode (recommended for read/write)**
   - Connect to ConPort’s MCP server.
   - Enables using ConPort’s official tools/resources.

#### 5.1.2 Workbench API surface (minimum)

This is the *pattern we will copy from TaskFlow/ConPort-UI*.

- `GET /api/v1/conport/now`
  - returns product_context, active_context, recent_activity
- `GET /api/v1/conport/dashboard`
  - includes progress rollups and “graph health” summary
- `GET /api/v1/conport/search`
  - FTS-backed when available
- `GET /api/v1/conport/item?type=...&id=...`
- `GET /api/v1/conport/progress/{id}` and `PATCH /api/v1/conport/progress/{id}` (status updates)
- `GET/PUT/DELETE /api/v1/conport/views/{view_key}` for saved Workbench views
- `GET/POST/DELETE /api/v1/conport/links` for knowledge-graph links

#### 5.1.3 UI requirements (ConPort)

- Support selecting a DB via `?db=context_portal/context.db` (default DB path: `context_portal/context.db`).
- Show “Now” summary:
  - active_context.current_focus
  - product_context.project_name
- Provide full-text search UI (decisions/custom_data).
- Provide recent activity list with deep-links to item detail routes.

---

### 5.2 Mem0 Integration

- Connect to Mem0 (self-hosted or cloud) using a config-driven adapter.
- List/search memories by user_id.
- Display basic metadata (timestamps, relevance score, tags/attributes).

---

### 5.3 Prompt / Instruction Management

- Load prompts from configurable directories.
- Watch prompt files for updates (hot reload).
- Token count per prompt and aggregate token totals.

---

### 5.4 Unified Dashboard

- Single dashboard view with panels for:
  - ConPort
  - Mem0
  - prompts
  - processing monitor
- Token breakdown by source.

---

### 5.5 Processing Monitor (Context Retrieval Trace)

- Show a timeline of “prompt processed” events.
- For each event, show:
  - which ConPort queries/tools were executed
  - which memories were retrieved
  - which prompt files were used
  - token totals and breakdown

---

## 6. Non-Functional Requirements

### 6.1 Performance

- Initial dashboard load: < 2 seconds (typical local env)
- Context refresh: < 500ms (typical local env)

### 6.2 Security

- Never log secrets (Mem0 keys, OpenAI keys, etc.).
- Enforce safe file/DB path resolution.
- Prefer read-only access for SQLite Workbench mode.

### 6.3 Compatibility

- Linux primary
- macOS / Windows secondary
- Podman/Docker supported

---

## 7. Technical Architecture (Aligned to TaskFlow/ConPort-UI)

This section intentionally matches the proven implementation approach used in TaskFlow/ConPort-UI.

### 7.1 Backend

- **FastAPI** provides:
  - REST API for dashboard + adapters
  - optional SSE endpoint for real-time events

### 7.2 Frontend

- **SvelteKit** (Svelte 5) provides the dashboard UI.

### 7.3 Real-time updates: SSE (not WebSockets)

Mindscape-AI should use **Server-Sent Events (SSE)** as the default push mechanism:

- Backend exposes `GET /api/v1/events/stream`
  - heartbeat every ~15s
  - emits event objects of the form:

```json
{
  "type": "<event_type>",
  "data": {"...": "..."},
  "timestamp": "2026-01-01T12:00:00.000Z"
}
```

- Frontend uses `EventSource` (Svelte store wrapper) with auto-reconnect.

Rationale:
- simpler client implementation than WebSockets
- one-way push fits the dashboard update model
- matches what’s already working in TaskFlow AI

### 7.4 ConPort Workbench API design notes

The Workbench API (SQLite) must follow these implementation constraints:

- Read-only by default
- Parameterized SQL only
- Optional FTS tables:
  - if missing, endpoints should still succeed with empty results / fallback behavior
- DB resolution must be CWD-independent:
  - detect workspace root by walking upward until `context_portal/` exists
  - resolve DB paths relative to that root

### 7.5 CORS and dev defaults

Local dev should allow the Svelte dev server origins, with the ability to tighten later via env vars.

---

## 8. Release Roadmap

### Phase 0 — Doc and parity alignment (current)

- [x] Align README with actual proven patterns (SSE + SvelteKit + FastAPI)
- [ ] Produce this canonical docs PRD file (`docs/projectPRD.MD`)

### Phase 1 — ConPort UI parity (copy from TaskFlow → Mindscape)

- [ ] Add ConPort Workbench backend (FastAPI + aiosqlite) and endpoints listed in §5.1.2
- [ ] Add SvelteKit ConPort Workbench UI routes:
  - landing/now view
  - item detail
  - decisions list
  - custom-data list
  - patterns
  - progress
  - views
  - tree/links

### Phase 2 — Mem0 + prompt adapters

- [ ] Mem0 adapter + UI panel
- [ ] prompt directories + token counting + file watching

### Phase 3 — Processing monitor

- [ ] event taxonomy and trace model
- [ ] context retrieval timeline UI

### Phase 4 — Optional MCP server mode

- [ ] expose Mindscape aggregated view as its own MCP server

---

## 9. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| ConPort schema/behavior changes | Medium | High | adapter isolation + strict validation |
| Mem0 API/SDK breaking changes | Medium | Medium | pin versions + abstraction layer |
| Performance with large contexts | Medium | High | pagination + lazy loading + caching |

---

## 10. References

- ConPort: https://github.com/GreatScottyMac/context-portal
- Mem0: https://github.com/mem0ai/mem0
- MCP spec: https://modelcontextprotocol.io
