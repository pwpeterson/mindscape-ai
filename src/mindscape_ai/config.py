"""Configuration loading for Mindscape-AI.

Phase 1 focuses on ConPort Workbench parity. This config module intentionally stays lightweight
(no pydantic dependency) and uses YAML + environment variable overrides.

Expected config shape (subset):

```yaml
conport:
  workspace_path: "/path/to/workspace"
  mode: "mcp"  # or "direct"
  refresh_interval: 5

dashboard:
  host: "127.0.0.1"
  port: 8080

logging:
  level: "INFO"
  file: "./logs/mindscape.log"

# Comma-separated origins can also be provided via MINDSCAPE_CORS_ORIGINS
cors:
  origins:
    - "http://localhost:5173"
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CorsConfig:
    origins: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MindscapeConfig:
    """Top-level config object."""

    cors: CorsConfig = field(default_factory=CorsConfig)
    raw: dict[str, Any] = field(default_factory=dict)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def load_config(path: str | Path | None = None) -> MindscapeConfig:
    """Load configuration from YAML.

    Args:
        path: Path to config file. Defaults to `config.yaml` in the current working directory.

    Returns:
        Parsed MindscapeConfig.

    Notes:
        - Missing files result in an empty config (no exception).
        - Environment-variable overrides are applied by consumers (e.g. CORS in the API app).
    """

    cfg_path = Path(path) if path is not None else Path("config.yaml")

    raw: dict[str, Any] = {}
    if cfg_path.exists() and cfg_path.is_file():
        raw = _safe_dict(yaml.safe_load(cfg_path.read_text(encoding="utf-8")))

    cors_raw = _safe_dict(raw.get("cors"))

    return MindscapeConfig(
        cors=CorsConfig(origins=_safe_list_str(cors_raw.get("origins"))),
        raw=raw,
    )
