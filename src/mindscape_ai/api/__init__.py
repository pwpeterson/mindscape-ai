"""API package for Mindscape-AI.

Phase 1 provides the ConPort Workbench (SQLite read-only) API surface.
"""

from __future__ import annotations

__all__ = ["create_app"]

from mindscape_ai.api.app import create_app
