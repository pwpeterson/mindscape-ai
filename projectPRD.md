# Mindscape-AI - Product Requirements Document

## Document Information

| Field | Value |
|-------|-------|
| **Project Name** | Mindscape-AI |
| **Version** | 1.0.0 |
| **Author** | Paul |
| **Created** | January 2026 |
| **Status** | Draft |

---

## 1. Executive Summary

Mindscape-AI is a unified dashboard and management interface for visualizing, monitoring, and managing the complete "awareness landscape" of AI systems. It integrates three critical layers of AI context: project knowledge (Context-Portal/ConPort), persistent user memory (Mem0), and local prompts/instructions. The application provides real-time visibility into what an AI model "sees" during inference, enabling developers and power users to understand, debug, and optimize AI interactions.

---

## 2. Problem Statement

### Current Challenges

1. **Fragmented Context Visibility**: Developers working with AI systems have no unified view of all context sources feeding into their models. ConPort manages project knowledge, Mem0 handles user memory, and prompts exist in various files—but there's no single pane of glass.

2. **Debugging Complexity**: When AI responses are unexpected, it's difficult to understand which context influenced the output. Was it a stale memory? A conflicting prompt? Missing project context?

3. **Context Optimization Blindness**: Without visibility into token usage across context sources, developers can't effectively optimize their context budgets or identify redundant information.

4. **Operational Overhead**: Managing three separate systems requires context-switching between different interfaces, APIs, and mental models.

### Target Users

- **AI/ML Developers**: Building applications with LLM backends using ConPort and Mem0
- **DevOps Engineers**: Managing AI infrastructure and monitoring context pipelines
- **Power Users**: Advanced users of AI coding assistants (Roo Code, Cline, Cursor) who want visibility into their context systems
- **Researchers**: Studying AI memory systems and context management patterns

---

## 3. Product Vision

**Vision Statement**: Mindscape-AI provides a window into the AI's situational awareness—making the invisible visible so developers can build more effective, predictable, and personalized AI experiences.

**Core Philosophy**: Just as a pilot needs instrumentation to understand their aircraft's state, AI developers need instrumentation to understand their model's context state. Mindscape-AI is that instrumentation panel.

---

## 4. Goals & Success Metrics

### Primary Goals

| Goal | Description | Success Metric |
|------|-------------|----------------|
| **Unified Visibility** | Single interface for all context sources | 100% of ConPort, Mem0, and prompt data accessible |
| **Real-time Monitoring** | Live view of context as prompts are processed | < 500ms latency for context updates |
| **Context Debugging** | Identify context issues affecting AI output | Reduce debugging time by 50% |
| **Token Optimization** | Visibility into token usage per source | Enable 20% context efficiency improvement |

### Secondary Goals

- Enable context export/import across systems
- Provide context diff visualization between sessions
- Support multi-workspace management
- Offer context analytics and usage patterns

---

## 5. Functional Requirements

### 5.1 Context Integration Layer

#### 5.1.1 ConPort (Context-Portal) Integration

| Requirement | Priority | Description |
|-------------|----------|-------------|
| **CP-001** | P0 | Connect to ConPort MCP server via STDIO or HTTP |
| **CP-002** | P0 | Display Product Context with real-time updates |
| **CP-003** | P0 | Display Active Context (current focus, open issues) |
| **CP-004** | P0 | List and search Decisions with filtering by tags |
| **CP-005** | P0 | Display Progress entries with status filtering |
| **CP-006** | P1 | Visualize System Patterns |
| **CP-007** | P1 | Browse and edit Custom Data (categories/keys) |
| **CP-008** | P1 | Display Context Links as knowledge graph visualization |
| **CP-009** | P2 | Show Item History with version comparison |
| **CP-010** | P2 | Execute full-text search across all ConPort data |

#### 5.1.2 Mem0 Integration

| Requirement | Priority | Description |
|-------------|----------|-------------|
| **M0-001** | P0 | Connect to Mem0 instance (self-hosted or cloud) |
| **M0-002** | P0 | Display user memories with search capability |
| **M0-003** | P0 | Show memory relevance scores and metadata |
| **M0-004** | P1 | Support multiple user_id contexts |
| **M0-005** | P1 | Display memory creation/update timestamps |
| **M0-006** | P1 | Enable memory CRUD operations |
| **M0-007** | P2 | Visualize Graph Memory relationships (if enabled) |
| **M0-008** | P2 | Show memory analytics (access frequency, decay) |

#### 5.1.3 Prompt Management

| Requirement | Priority | Description |
|-------------|----------|-------------|
| **PM-001** | P0 | Load and display system prompts from configurable paths |
| **PM-002** | P0 | Real-time prompt file watching with hot reload |
| **PM-003** | P0 | Display prompt token counts |
| **PM-004** | P1 | Prompt version history (git-aware) |
| **PM-005** | P1 | Prompt template variable highlighting |
| **PM-006** | P2 | Prompt linting and validation |
| **PM-007** | P2 | Prompt diff visualization |

### 5.2 Unified Dashboard

| Requirement | Priority | Description |
|-------------|----------|-------------|
| **UD-001** | P0 | Combined context view showing all three sources |
| **UD-002** | P0 | Total token count across all context sources |
| **UD-003** | P0 | Context source breakdown visualization (pie/bar chart) |
| **UD-004** | P1 | Configurable layout with drag-and-drop panels |
| **UD-005** | P1 | Dark/light theme support |
| **UD-006** | P1 | Multi-workspace tabbed interface |
| **UD-007** | P2 | Context timeline showing changes over time |

### 5.3 Processing Monitor

| Requirement | Priority | Description |
|-------------|----------|-------------|
| **PM-001** | P0 | Real-time display of prompts being processed |
| **PM-002** | P0 | Show which context was retrieved for each prompt |
| **PM-003** | P1 | Processing latency metrics per context source |
| **PM-004** | P1 | Request/response logging with context snapshots |
| **PM-005** | P2 | Performance analytics and bottleneck identification |

### 5.4 Configuration & Settings

| Requirement | Priority | Description |
|-------------|----------|-------------|
| **CS-001** | P0 | ConPort connection configuration (workspace path) |
| **CS-002** | P0 | Mem0 connection configuration (API key, host) |
| **CS-003** | P0 | Prompt directories configuration |
| **CS-004** | P1 | Token counting model selection (tiktoken model) |
| **CS-005** | P1 | Refresh intervals configuration |
| **CS-006** | P2 | Export/import configuration profiles |

---

## 6. Non-Functional Requirements

### 6.1 Performance

| Requirement | Target |
|-------------|--------|
| Dashboard initial load | < 2 seconds |
| Context refresh latency | < 500ms |
| Memory usage (idle) | < 200MB |
| Concurrent workspace support | 5+ workspaces |

### 6.2 Compatibility

| Platform | Support Level |
|----------|---------------|
| Linux (Ubuntu 22.04+) | Primary |
| macOS (13+) | Secondary |
| Windows 11 | Secondary |
| Docker/Podman | Container support |

### 6.3 Security

- Secure credential storage for Mem0 API keys
- No telemetry or data collection without consent
- Local-first architecture (no cloud dependencies for core features)
- Optional encryption for cached context data

---

## 7. Technical Architecture

### 7.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Mindscape-AI                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Web UI     │  │   REST API   │  │   WebSocket Server   │  │
│  │  (React/Vue) │  │   (FastAPI)  │  │   (Real-time)        │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                      │              │
│         └─────────────────┼──────────────────────┘              │
│                           │                                     │
│  ┌────────────────────────┴────────────────────────────────┐   │
│  │                   Context Aggregator                     │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐    │   │
│  │  │   ConPort   │ │    Mem0     │ │     Prompt      │    │   │
│  │  │   Adapter   │ │   Adapter   │ │     Loader      │    │   │
│  │  └──────┬──────┘ └──────┬──────┘ └────────┬────────┘    │   │
│  └─────────┼───────────────┼─────────────────┼─────────────┘   │
│            │               │                 │                  │
└────────────┼───────────────┼─────────────────┼──────────────────┘
             │               │                 │
             ▼               ▼                 ▼
      ┌──────────┐    ┌──────────┐      ┌──────────┐
      │ ConPort  │    │   Mem0   │      │  Local   │
      │   MCP    │    │  Server  │      │  Files   │
      │  Server  │    │          │      │          │
      └──────────┘    └──────────┘      └──────────┘
```

### 7.2 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Backend** | Python 3.11+ / FastAPI | Matches ConPort/Mem0 ecosystem |
| **Frontend** | React + TypeScript | Rich component ecosystem |
| **State Management** | Zustand or Redux | Complex state requirements |
| **Real-time** | WebSockets | Live context updates |
| **Token Counting** | tiktoken | Accurate OpenAI-compatible counts |
| **Database** | SQLite | Local-first, matches ConPort pattern |
| **Containerization** | Podman | User's existing infrastructure |

### 7.3 Integration Patterns

**ConPort Integration**:
- Primary: MCP client connecting via STDIO to ConPort server
- Secondary: Direct SQLite read access (read-only) for performance

**Mem0 Integration**:
- Python SDK (`mem0` package) for self-hosted instances
- REST API client for Mem0 Platform (cloud)

**Prompt Loading**:
- File system watcher (watchdog) for prompt directories
- Git integration for version tracking

---

## 8. User Interface Wireframes

### 8.1 Main Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Mindscape-AI                              [Workspace ▼] [Settings] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐  │
│  │  📊 Context Overview        │  │  🔄 Live Processing         │  │
│  │  ─────────────────────────  │  │  ─────────────────────────  │  │
│  │  Total Tokens: 24,532       │  │  [Processing stream...]     │  │
│  │  ┌────┐ ┌────┐ ┌────┐      │  │                             │  │
│  │  │ CP │ │ M0 │ │ PR │      │  │  Latest: "Explain the..."   │  │
│  │  │42% │ │28% │ │30% │      │  │  Context: 3 decisions,      │  │
│  │  └────┘ └────┘ └────┘      │  │           2 memories        │  │
│  └─────────────────────────────┘  └─────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐  │
│  │  📁 ConPort                 │  │  🧠 Mem0 Memories           │  │
│  │  ─────────────────────────  │  │  ─────────────────────────  │  │
│  │  [Product] [Active] [Dec]   │  │  User: paul_dev             │  │
│  │  ─────────────────────────  │  │  ─────────────────────────  │  │
│  │  Product Context:           │  │  • Python developer, VS...  │  │
│  │  "TaskFlow-AI is a..."      │  │  • Prefers Podman over...   │  │
│  │                             │  │  • Uses RTX 3090 Ti...      │  │
│  │  Recent Decisions: 5        │  │                             │  │
│  │  Active Tasks: 3            │  │  [12 memories] [Search]     │  │
│  └─────────────────────────────┘  └─────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  📝 Prompts                                                   │  │
│  │  ────────────────────────────────────────────────────────────  │  │
│  │  [system_prompt.md] [custom_instructions.md] [+2 more]        │  │
│  │                                                               │  │
│  │  # System Prompt (4,521 tokens)                               │  │
│  │  You are an AI assistant specialized in...                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 9. Release Roadmap

### Phase 1: Foundation (MVP) - 6 weeks

**Goal**: Basic unified visibility across all three context sources

- [ ] Project setup and architecture
- [ ] ConPort adapter with core read operations
- [ ] Mem0 adapter with memory listing/search
- [ ] Prompt file loader with token counting
- [ ] Basic React dashboard with three panels
- [ ] Configuration management

**Deliverable**: Functional dashboard showing ConPort, Mem0, and prompts

### Phase 2: Real-time & Interaction - 4 weeks

**Goal**: Live monitoring and basic editing capabilities

- [ ] WebSocket server for real-time updates
- [ ] File watcher for prompt changes
- [ ] ConPort change polling/notifications
- [ ] Basic CRUD operations for all sources
- [ ] Token budget visualization

**Deliverable**: Live-updating dashboard with edit capabilities

### Phase 3: Advanced Features - 4 weeks

**Goal**: Knowledge graph visualization and analytics

- [ ] Context link visualization (D3.js graph)
- [ ] Processing history and analytics
- [ ] Context diff between sessions
- [ ] Multi-workspace management
- [ ] Export/import functionality

**Deliverable**: Full-featured context management platform

### Phase 4: Polish & Optimization - 2 weeks

**Goal**: Production readiness

- [ ] Performance optimization
- [ ] Comprehensive error handling
- [ ] Documentation and tutorials
- [ ] Container image publication
- [ ] CI/CD pipeline

**Deliverable**: Production-ready release

---

## 10. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| ConPort API changes | Medium | High | Version pin, adapter abstraction |
| Mem0 breaking changes | Medium | Medium | SDK version pinning, fallback support |
| Token counting accuracy | Low | Medium | Use official tiktoken, allow model selection |
| Performance with large contexts | Medium | High | Pagination, lazy loading, caching |
| Real-time sync complexity | High | Medium | Eventual consistency model, clear UX feedback |

---

## 11. Open Questions

1. **Prompt Interception**: Should Mindscape-AI intercept prompts in real-time (proxy mode) or just display configured prompt files?

2. **Write Operations**: Should editing be supported for all sources, or should ConPort/Mem0 be read-only with links to their native interfaces?

3. **Multi-user Support**: Is supporting multiple Mem0 user_ids simultaneously a requirement?

4. **Cloud vs Local Mem0**: Should we prioritize self-hosted Mem0 or Mem0 Platform integration first?

5. **MCP Server Mode**: Should Mindscape-AI itself expose an MCP server for AI assistants to query its aggregated view?

---

## 12. Appendix

### A. Glossary

| Term | Definition |
|------|------------|
| **ConPort** | Context Portal - MCP server for project-specific knowledge graphs |
| **Mem0** | Intelligent memory layer for personalized AI interactions |
| **MCP** | Model Context Protocol - standard for AI assistant tool integration |
| **Context Window** | The total input a model can process in a single inference |
| **RAG** | Retrieval Augmented Generation - enhancing LLM output with retrieved context |

### B. References

- [Context-Portal GitHub](https://github.com/GreatScottyMac/context-portal)
- [Mem0 GitHub](https://github.com/mem0ai/mem0)
- [Mem0 Documentation](https://docs.mem0.ai)
- [MCP Specification](https://modelcontextprotocol.io)

---

*Document End*
