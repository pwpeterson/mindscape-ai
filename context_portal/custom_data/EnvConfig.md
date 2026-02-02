# Custom Data: EnvConfig

### 2026-02-02_mindscape-ai.env_summary

*   [2026-02-02 19:27:00]

Summary of the repo-level non-secret defaults file [`mindscape-ai.env`](mindscape-ai.env:1):

- Purpose: hold **NON-SECRET** defaults for Mindscape-AI services (secrets should live elsewhere).
- Loaded by the API container unit via `EnvironmentFile` in [`mindscape-ai-api.container`](mindscape-ai-api.container:56).
- Current keys of interest (Mem0/Qdrant):
  - `ENABLE_MEMORY=true` (feature flag placeholder for future use)
  - `MEMORY_VECTOR_STORE=qdrant` (alias for Mem0 vector provider)
  - `MEMORY_COLLECTION_NAME=mem0_memories` (alias for Mem0 collection name)
  - `QDRANT_URL=http://local-ai-qdrant:6333` (parsed into host/port when MEM0_QDRANT_HOST is not set)
  - `QDRANT_API_KEY=` (alias for Mem0 Qdrant API key)

Implementation note:
- Mindscape-AI’s Mem0 integration primarily uses `MEM0_*` env vars, but supports aliases for these keys (see [`Mem0Settings.from_env()`](src/mindscape_ai/mem0/client.py:109)).