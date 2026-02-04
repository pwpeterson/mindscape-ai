"""Mem0 client wrapper for Mindscape-AI.

This module provides a small abstraction around the `mem0` Python import and
environment-driven configuration (aligned with the mem0 MCP server's MEM0_* env
conventions).

Design goals:
- Lazy-import mem0 so Mindscape can run without mem0 installed.
- Centralized configuration parsing and safe defaults.
- Single-process cached client (FastAPI workers will each have their own cache).
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from typing import Any, Literal, cast

from loguru import logger


class Mem0UnavailableError(RuntimeError):
    """Raised when mem0 is not available (not installed or misconfigured)."""


VectorProvider = Literal["qdrant", "chroma", "pgvector"]
LLMProvider = Literal["openai", "ollama", "anthropic", "azure_openai"]
EmbedderProvider = Literal["openai", "ollama", "huggingface"]


def _env(key: str, default: str | None = None) -> str | None:
    """Read an environment variable with whitespace/empty-string normalization."""
    val = os.getenv(key)
    if val is None:
        return default
    s = val.strip()
    return s if s != "" else default


def _env_alias(keys: list[str], default: str | None = None) -> str | None:
    """Read the first non-empty env var from a list of aliases.

    This allows Mindscape-AI to support both the upstream mem0 conventions (MEM0_*)
    and Mindscape's own non-secret defaults file conventions (MEMORY_*, QDRANT_*).

    Precedence: first key in `keys` wins.
    """
    for k in keys:
        v = _env(k)
        if v is not None:
            return v
    return default


def _env_int(key: str, default: int) -> int:
    raw = _env(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    raw = _env(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Mem0Settings:
    # Identity
    default_user_id: str = "default"
    default_app_id: str = "mindscape-ai"

    # Vector store (Qdrant default)
    vector_provider: VectorProvider = "qdrant"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None
    collection_name: str = "mem0_memories"

    # LLM
    llm_provider: LLMProvider = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2000
    llm_base_url: str | None = None

    # Embedder
    embedder_provider: EmbedderProvider = "openai"
    embedder_model: str = "text-embedding-3-small"
    embedder_base_url: str | None = None
    embedding_dims: int | None = None

    # API keys
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    @staticmethod
    def from_env() -> Mem0Settings:
        """Load Mem0 settings from environment variables.

        Supported conventions:
        - Upstream mem0 / mem0-mcp: MEM0_*
        - Mindscape non-secret defaults (mindscape-ai.env): MEMORY_* and QDRANT_*

        Notes:
            - Aliases are best-effort and intentionally conservative.
            - Precedence favors MEM0_* when both are set.
        """
        vector_provider = cast(
            VectorProvider,
            (
                _env_alias(["MEM0_VECTOR_PROVIDER", "MEMORY_VECTOR_STORE"], "qdrant")
                or "qdrant"
            ).lower(),
        )
        llm_provider = cast(
            LLMProvider,
            (_env("MEM0_LLM_PROVIDER", "openai") or "openai").lower(),
        )
        embedder_provider = cast(
            EmbedderProvider,
            (_env("MEM0_EMBEDDER_PROVIDER", "openai") or "openai").lower(),
        )

        # Qdrant host/port can be provided either as MEM0_QDRANT_HOST/PORT (preferred)
        # or as a single QDRANT_URL (Mindscape defaults file).
        qdrant_url = _env("QDRANT_URL")
        qdrant_host = _env("MEM0_QDRANT_HOST")
        qdrant_port = _env_int("MEM0_QDRANT_PORT", 6333)

        if (qdrant_host is None or qdrant_host == "") and qdrant_url:
            # Accept http(s)://host:port or host:port
            try:
                from urllib.parse import urlparse
            except Exception:  # noqa: BLE001
                urlparse = None  # type: ignore[assignment]

            parsed_host: str | None = None
            parsed_port: int | None = None

            if urlparse is not None and "://" in qdrant_url:
                u = urlparse(qdrant_url)
                parsed_host = u.hostname
                parsed_port = u.port
            else:
                # host:port
                if ":" in qdrant_url:
                    h, p = qdrant_url.rsplit(":", 1)
                    parsed_host = h.strip() or None
                    try:
                        parsed_port = int(p.strip())
                    except ValueError:
                        parsed_port = None
                else:
                    parsed_host = qdrant_url.strip() or None

            if parsed_host:
                qdrant_host = parsed_host
            if parsed_port is not None:
                qdrant_port = parsed_port

        return Mem0Settings(
            default_user_id=_env("MEM0_DEFAULT_USER_ID", "default") or "default",
            default_app_id=_env("MEM0_DEFAULT_APP_ID", "mindscape-ai") or "mindscape-ai",
            vector_provider=vector_provider,
            qdrant_host=qdrant_host or "localhost",
            qdrant_port=qdrant_port,
            qdrant_api_key=_env_alias(["MEM0_QDRANT_API_KEY", "QDRANT_API_KEY"]),
            collection_name=(
                _env_alias(["MEM0_COLLECTION_NAME", "MEMORY_COLLECTION_NAME"], "mem0_memories")
                or "mem0_memories"
            ),
            llm_provider=llm_provider,
            llm_model=_env("MEM0_LLM_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
            llm_temperature=_env_float("MEM0_LLM_TEMPERATURE", 0.1),
            llm_max_tokens=_env_int("MEM0_LLM_MAX_TOKENS", 2000),
            llm_base_url=_env("MEM0_LLM_BASE_URL"),
            embedder_provider=embedder_provider,
            embedder_model=_env("MEM0_EMBEDDER_MODEL", "text-embedding-3-small")
            or "text-embedding-3-small",
            embedder_base_url=_env("MEM0_EMBEDDER_BASE_URL"),
            embedding_dims=(
                int(_env("MEM0_EMBEDDING_DIMS") or "0") or None
                if _env("MEM0_EMBEDDING_DIMS") is not None
                else None
            ),
            openai_api_key=_env("OPENAI_API_KEY"),
            anthropic_api_key=_env("ANTHROPIC_API_KEY"),
            ollama_base_url=_env("MEM0_OLLAMA_BASE_URL", "http://localhost:11434")
            or "http://localhost:11434",
        )

    def build_mem0_config(self) -> dict[str, Any]:
        """Build a mem0 config dict (compatible with Memory.from_config)."""
        config: dict[str, Any] = {"version": "v1.1"}

        # Vector store
        vector_config: dict[str, Any] = {"collection_name": self.collection_name}
        if self.vector_provider == "qdrant":
            vector_config["host"] = self.qdrant_host
            vector_config["port"] = self.qdrant_port
            if self.qdrant_api_key:
                vector_config["api_key"] = self.qdrant_api_key
            if self.embedding_dims:
                vector_config["embedding_model_dims"] = self.embedding_dims

        config["vector_store"] = {"provider": self.vector_provider, "config": vector_config}

        # LLM
        llm_config: dict[str, Any] = {
            "model": self.llm_model,
            "temperature": self.llm_temperature,
            "max_tokens": self.llm_max_tokens,
        }
        if self.llm_provider == "openai":
            if self.openai_api_key:
                llm_config["api_key"] = self.openai_api_key
            if self.llm_base_url:
                llm_config["openai_base_url"] = self.llm_base_url
        elif self.llm_provider == "ollama":
            llm_config["ollama_base_url"] = self.ollama_base_url
        elif self.llm_provider == "anthropic":
            if self.anthropic_api_key:
                llm_config["api_key"] = self.anthropic_api_key

        config["llm"] = {"provider": self.llm_provider, "config": llm_config}

        # Embedder
        embedder_config: dict[str, Any] = {"model": self.embedder_model}
        if self.embedder_provider == "openai":
            if self.openai_api_key:
                embedder_config["api_key"] = self.openai_api_key
            if self.embedder_base_url:
                embedder_config["openai_base_url"] = self.embedder_base_url
        elif self.embedder_provider == "ollama":
            embedder_config["ollama_base_url"] = self.embedder_base_url or self.ollama_base_url
        elif self.embedder_provider == "huggingface":
            if self.embedding_dims:
                embedder_config["embedding_dims"] = self.embedding_dims

        config["embedder"] = {"provider": self.embedder_provider, "config": embedder_config}
        return config


_client: Any | None = None


def reset_mem0_client_cache_for_tests() -> None:
    """Reset the global cached client (used by tests)."""
    global _client
    _client = None


def get_mem0_client() -> Any:
    """Get or initialize the mem0 Memory client.

    Raises:
        Mem0UnavailableError: if the mem0 SDK is not installed or cannot be initialized.
    """
    global _client
    if _client is not None:
        return _client

    try:
        from mem0 import Memory  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise Mem0UnavailableError(
            "mem0 SDK not available. Install the Python package 'mem0ai' to enable Mem0 features."
        ) from exc

    # Allow a full JSON config override (useful for experiments / avoiding many env vars).
    raw_json = _env("MINDSCAPE_MEM0_CONFIG_JSON") or _env("MEM0_CONFIG_JSON")
    if raw_json:
        try:
            config_dict = json.loads(raw_json)
        except Exception as exc:  # noqa: BLE001
            raise Mem0UnavailableError("Invalid JSON in MINDSCAPE_MEM0_CONFIG_JSON/MEM0_CONFIG_JSON") from exc
    else:
        settings = Mem0Settings.from_env()
        config_dict = settings.build_mem0_config()

    def _redact_secrets(value: Any) -> Any:
        """Redact obvious secret-bearing keys from config before logging.

        This avoids leaking API keys in debug logs.
        """

        if isinstance(value, dict):
            redacted: dict[str, Any] = {}
            for k, v in value.items():
                lk = str(k).lower()
                if lk in {"api_key", "apikey", "token", "password", "secret", "key"}:
                    redacted[k] = "***REDACTED***"
                else:
                    redacted[k] = _redact_secrets(v)
            return redacted
        if isinstance(value, list):
            return [_redact_secrets(v) for v in value]
        return value

    def _build_init_error_detail(config: dict[str, Any], exc: Exception) -> str:
        base = f"Failed to initialize mem0 client: {exc}"

        msg = str(exc)
        if "Errno 111" in msg or "Connection refused" in msg:
            vector_store = config.get("vector_store") if isinstance(config, dict) else None
            if isinstance(vector_store, dict):
                provider = vector_store.get("provider")
                vcfg = vector_store.get("config")
                if provider == "qdrant" and isinstance(vcfg, dict):
                    host = vcfg.get("host", "localhost")
                    port = vcfg.get("port", 6333)
                    return (
                        f"{base}. "
                        f"Qdrant appears unreachable at {host}:{port}. "
                        "Start Qdrant, or switch to another vector store via MEM0_* env vars "
                        "or MINDSCAPE_MEM0_CONFIG_JSON/MEM0_CONFIG_JSON."
                    )

        return base

    logger.debug(
        "Initializing mem0 with config: {}",
        json.dumps(_redact_secrets(copy.deepcopy(config_dict)), indent=2),
    )

    try:
        _client = Memory.from_config(config_dict=config_dict)
    except Exception as exc:  # noqa: BLE001
        raise Mem0UnavailableError(_build_init_error_detail(config_dict, exc)) from exc

    return _client
