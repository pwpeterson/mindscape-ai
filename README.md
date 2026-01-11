# Mindscape-AI

**A unified dashboard for visualizing AI awareness - integrating Context-Portal, Mem0, and prompt management.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## Overview

Mindscape-AI provides a window into what your AI models "see" during inference. It unifies three critical layers of AI context into a single, real-time dashboard:

| Layer | Source | What It Provides |
|-------|--------|------------------|
| **Project Knowledge** | [Context-Portal (ConPort)](https://github.com/GreatScottyMac/context-portal) | Decisions, progress, patterns, architecture |
| **User Memory** | [Mem0](https://github.com/mem0ai/mem0) | Persistent user preferences and interaction history |
| **Instructions** | Local Prompts | System prompts and custom instructions |

Think of it as an instrumentation panel for AI context—essential for debugging, optimizing, and understanding AI behavior.

```
┌─────────────────────────────────────────────────────────┐
│                    AI Context Window                    │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐   │
│  │   ConPort   │ │    Mem0     │ │     Prompts     │   │
│  │   (Project) │ │   (User)    │ │  (Instructions) │   │
│  │             │ │             │ │                 │   │
│  │  Decisions  │ │ Preferences │ │ System Prompt   │   │
│  │  Progress   │ │  Memories   │ │ Custom Rules    │   │
│  │  Patterns   │ │  History    │ │ Templates       │   │
│  └─────────────┘ └─────────────┘ └─────────────────┘   │
│                         │                               │
│                         ▼                               │
│              [ Mindscape-AI Dashboard ]                 │
│                  Unified Visibility                     │
└─────────────────────────────────────────────────────────┘
```

---

## Features

### Core Capabilities

- **Unified Context View**: See all context sources in one dashboard
- **Real-time Monitoring**: Watch context updates as they happen
- **Token Analytics**: Track token usage across all sources
- **Context Search**: Full-text search across ConPort, Mem0, and prompts

### ConPort Integration

- View Product Context and Active Context
- Browse decisions with tag filtering
- Track progress entries and task status
- Explore system patterns
- Visualize knowledge graph relationships

### Mem0 Integration

- Display user memories with relevance scores
- Search memories semantically
- Support for multiple user contexts
- Memory CRUD operations

### Prompt Management

- Load prompts from configurable directories
- Real-time file watching with hot reload
- Token counting per prompt file
- Git-aware version tracking

---

## Installation

### Prerequisites

- Python 3.10+ (per `pyproject.toml`)
- Node.js 18+ (for the SvelteKit UI)
- [ConPort](https://github.com/GreatScottyMac/context-portal) available (SQLite DB and/or MCP server)
- [Mem0](https://github.com/mem0ai/mem0) available (self-hosted or cloud)

### Quick Start (dev)

This repo is currently scaffolding-first; the recommended workflow is to install deps with `uv` and run the dev targets once the backend/UI modules land.

```bash
git clone https://github.com/yourusername/mindscape-ai.git
cd mindscape-ai

# Create venv + install base deps
uv venv
uv sync --extra dev --extra web

# (Optional) if/when MCP client/server code is enabled
# uv sync --extra mcp
```

### Containerization

Podman/Quadlet deployment will mirror the TaskFlow AI “unified service” approach once Mindscape-AI has its UI/API entrypoints:
- single container image
- FastAPI backend + SvelteKit frontend
- health checks and systemd-managed lifecycle

---

## Configuration

Create a `config.yaml` file in the project root:

```yaml
# Mindscape-AI Configuration

# ConPort (Context-Portal) settings
conport:
  # Path to workspace containing context_portal/context.db
  workspace_path: "/path/to/your/project"
  # Connection mode: "mcp" (recommended) or "direct" (read-only SQLite)
  mode: "mcp"
  # Refresh interval in seconds
  refresh_interval: 5

# Mem0 settings
mem0:
  # For self-hosted Mem0
  type: "self-hosted"
  # Or for Mem0 Platform: type: "cloud"
  
  # Self-hosted configuration
  config:
    vector_store:
      provider: "qdrant"
      config:
        host: "localhost"
        port: 6333
    llm:
      provider: "openai"
      config:
        model: "gpt-4o-mini"
  
  # Default user ID for memory queries
  default_user_id: "default_user"
  
  # Cloud configuration (if type: "cloud")
  # api_key: "${MEM0_API_KEY}"  # Use environment variable
  # host: "https://api.mem0.ai"

# Prompt directories to monitor
prompts:
  directories:
    - "/path/to/prompts"
    - "./prompts"
  # File patterns to watch
  patterns:
    - "*.md"
    - "*.txt"
    - "*_prompt*"
  # Enable file watching for hot reload
  watch: true

# Dashboard settings
dashboard:
  host: "127.0.0.1"
  port: 8080
  # Theme: "dark" or "light"
  theme: "dark"

# Token counting
tokens:
  # Model for tiktoken encoding
  model: "gpt-4"
  # Show token warnings above this threshold
  warning_threshold: 50000

# Logging
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: "./logs/mindscape.log"
```

### Environment Variables

Sensitive values can be set via environment variables:

```bash
export MEM0_API_KEY="your-api-key"
export OPENAI_API_KEY="your-openai-key"
```

---

## Usage

Mindscape-AI is currently in a docs + scaffolding phase.

Planned runtime characteristics (matching the proven TaskFlow/ConPort-UI patterns):

- **FastAPI** backend exposes a REST API
  - ConPort Workbench routes under `GET /api/v1/conport/*`
  - real-time updates via **SSE** at `GET /api/v1/events/stream`
- **SvelteKit** UI consumes the REST API and subscribes to SSE using `EventSource`

Until the backend/UI entrypoints are implemented, the most useful artifacts are:

- [`docs/projectPRD.MD`](../mindscape-ai/docs/projectPRD.MD:1) (canonical PRD)
- [`projectPRD.md`](../mindscape-ai/projectPRD.md:1) (source draft)

---

## Architecture

Mindscape-AI will reuse the proven TaskFlow/ConPort-UI architecture patterns:

- **Backend**: FastAPI REST API (plus optional MCP client integration)
- **UI**: SvelteKit (Svelte 5) dashboard
- **Real-time**: **Server-Sent Events (SSE)** (EventSource) for push updates (same pattern as TaskFlow’s `/api/v1/events/stream`)
- **ConPort access**:
  - **Read-only Workbench API** pattern (safe SQLite path resolution, parameterized SQL, FTS graceful degradation)
  - Optional MCP-based read/write where appropriate

Repository layout (current):

```
mindscape-ai/
├── docs/
├── modules/
├── scripts/
├── projectPRD.md            # Source PRD (authored in repo root)
├── pyproject.toml
└── README.md
```

The application packages (API server + UI) will be added under `src/` as implementation starts.

---

## Integration with AI Assistants

### Roo Code / Cline

Mindscape-AI can be used alongside ConPort in your AI coding assistant. Configure ConPort as your MCP server, then use Mindscape-AI to visualize what context is being provided.

### Custom MCP Server (Planned)

Future versions will expose Mindscape-AI as an MCP server, allowing AI assistants to query the aggregated context view directly.

---

## Development

### Setup

```bash
git clone https://github.com/yourusername/mindscape-ai.git
cd mindscape-ai

uv venv
uv sync --extra dev --extra web
pre-commit install

# Optional (when MCP client/server code is enabled)
# uv sync --extra mcp
```

### Tests

Tests will be added once the API/UI packages land (there is no `tests/` directory yet).

### Code style

```bash
uv run ruff check .
uv run black .
```

---

## Roadmap

- [x] Project specification and architecture
- [ ] **Phase 1**: Core adapters and basic dashboard
- [ ] **Phase 2**: Real-time updates and editing
- [ ] **Phase 3**: Knowledge graph visualization
- [ ] **Phase 4**: MCP server mode
- [ ] **Future**: VS Code extension

See `docs/projectPRD.MD` for detailed requirements and roadmap.

---

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [Context-Portal (ConPort)](https://github.com/GreatScottyMac/context-portal) by GreatScottyMac
- [Mem0](https://github.com/mem0ai/mem0) by Mem0.ai
- The MCP (Model Context Protocol) community

---

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/mindscape-ai/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/mindscape-ai/discussions)

---

*Mindscape-AI: See what your AI sees.*
