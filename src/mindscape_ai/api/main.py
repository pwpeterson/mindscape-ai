"""ASGI entrypoint for the Mindscape-AI FastAPI service.

Usage (dev):
    uv run uvicorn mindscape_ai.api.main:app --reload

If you prefer the factory style:
    uv run uvicorn mindscape_ai.api.app:create_app --factory --reload
"""

from __future__ import annotations

from loguru import logger

from mindscape_ai.api.app import create_app


def _try_setup_logging() -> None:
    """Best-effort logging setup.

    The repo currently has logging utilities in
    [`utils/logging_setup.py`](utils/logging_setup.py:1), which aren't part of the
    `mindscape_ai` package yet. In local dev (repo root), that module is
    importable; in packaged installs it may not be.
    """

    try:
        # Dev convenience: reuse existing project logging configuration.
        from utils.logging_setup import setup_logging  # type: ignore

        setup_logging(app_name="mindscape_api")
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Logging setup skipped: {exc}")


_try_setup_logging()
app = create_app()
