from __future__ import annotations

import os

from mindscape_ai.mem0.client import Mem0Settings


def test_mem0_settings_prefers_mem0_vars_over_memory_aliases(monkeypatch) -> None:
    monkeypatch.setenv("MEM0_COLLECTION_NAME", "mem0_primary")
    monkeypatch.setenv("MEMORY_COLLECTION_NAME", "mem0_alias")

    settings = Mem0Settings.from_env()
    assert settings.collection_name == "mem0_primary"


def test_mem0_settings_uses_memory_collection_name_alias(monkeypatch) -> None:
    monkeypatch.delenv("MEM0_COLLECTION_NAME", raising=False)
    monkeypatch.setenv("MEMORY_COLLECTION_NAME", "mem0_from_memory")

    settings = Mem0Settings.from_env()
    assert settings.collection_name == "mem0_from_memory"


def test_mem0_settings_uses_memory_vector_store_alias(monkeypatch) -> None:
    monkeypatch.delenv("MEM0_VECTOR_PROVIDER", raising=False)
    monkeypatch.setenv("MEMORY_VECTOR_STORE", "chroma")

    settings = Mem0Settings.from_env()
    assert settings.vector_provider == "chroma"


def test_mem0_settings_uses_qdrant_api_key_alias(monkeypatch) -> None:
    monkeypatch.delenv("MEM0_QDRANT_API_KEY", raising=False)
    monkeypatch.setenv("QDRANT_API_KEY", "secret-key")

    settings = Mem0Settings.from_env()
    assert settings.qdrant_api_key == "secret-key"


def test_mem0_settings_parses_qdrant_url_http(monkeypatch) -> None:
    monkeypatch.delenv("MEM0_QDRANT_HOST", raising=False)
    monkeypatch.delenv("MEM0_QDRANT_PORT", raising=False)
    monkeypatch.setenv("QDRANT_URL", "http://example.com:7777")

    settings = Mem0Settings.from_env()
    assert settings.qdrant_host == "example.com"
    assert settings.qdrant_port == 7777


def test_mem0_settings_parses_qdrant_url_host_port(monkeypatch) -> None:
    monkeypatch.delenv("MEM0_QDRANT_HOST", raising=False)
    monkeypatch.delenv("MEM0_QDRANT_PORT", raising=False)
    monkeypatch.setenv("QDRANT_URL", "example.net:8888")

    settings = Mem0Settings.from_env()
    assert settings.qdrant_host == "example.net"
    assert settings.qdrant_port == 8888


def test_mem0_settings_mem0_host_port_override_qdrant_url(monkeypatch) -> None:
    monkeypatch.setenv("QDRANT_URL", "http://example.com:7777")
    monkeypatch.setenv("MEM0_QDRANT_HOST", "override.host")
    monkeypatch.setenv("MEM0_QDRANT_PORT", "9999")

    settings = Mem0Settings.from_env()
    assert settings.qdrant_host == "override.host"
    assert settings.qdrant_port == 9999


def test_mem0_settings_qdrant_url_without_port_keeps_default_port(monkeypatch) -> None:
    monkeypatch.delenv("MEM0_QDRANT_HOST", raising=False)
    monkeypatch.delenv("MEM0_QDRANT_PORT", raising=False)
    monkeypatch.setenv("QDRANT_URL", "http://example.com")

    settings = Mem0Settings.from_env()
    assert settings.qdrant_host == "example.com"
    assert settings.qdrant_port == 6333


def test_mem0_settings_qdrant_url_invalid_port_keeps_default_port(monkeypatch) -> None:
    monkeypatch.delenv("MEM0_QDRANT_HOST", raising=False)
    monkeypatch.delenv("MEM0_QDRANT_PORT", raising=False)
    monkeypatch.setenv("QDRANT_URL", "example.com:notaport")

    settings = Mem0Settings.from_env()
    assert settings.qdrant_host == "example.com"
    assert settings.qdrant_port == 6333


def test_mem0_settings_does_not_leak_os_environ_into_test(monkeypatch) -> None:
    # Sanity check: ensure tests are not relying on ambient env.
    # We only assert that from_env returns a valid settings object.
    for k in list(os.environ.keys()):
        if k.startswith("MEM0_") or k.startswith("MEMORY_") or k.startswith("QDRANT_"):
            monkeypatch.delenv(k, raising=False)

    settings = Mem0Settings.from_env()
    assert settings.collection_name
