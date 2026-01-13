"""FastAPI application factory for Mindscape-AI.

Phase 1 scope: ConPort Workbench (SQLite read-only) API parity and minimal dashboard support.
"""

from __future__ import annotations

import os
from typing import Final

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from mindscape_ai.api.routes.apps import router as apps_router
from mindscape_ai.api.routes.conport import router as conport_router
from mindscape_ai.api.routes.events import router as events_router
from mindscape_ai.api.routes.mem0 import router as mem0_router
from mindscape_ai.api.routes.prompts import router as prompts_router
from mindscape_ai.api.routes.tokens import router as tokens_router

API_PREFIX: Final[str] = "/api/v1"


def _parse_cors_origins(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""

    app = FastAPI(title="Mindscape-AI API", version="0.1.0")

    cors_origins = _parse_cors_origins(os.getenv("MINDSCAPE_CORS_ORIGINS"))
    if not cors_origins:
        cors_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix=API_PREFIX)

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    api.include_router(apps_router)
    api.include_router(conport_router)
    api.include_router(mem0_router)
    api.include_router(prompts_router)
    api.include_router(tokens_router)
    api.include_router(events_router)
    app.include_router(api)

    logger.info("Mindscape-AI API initialized")

    return app
