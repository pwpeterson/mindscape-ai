"""Supabase client utilities for Mindscape-AI (server-side).

This module intentionally supports *server-side* Supabase access using a service role key.
The browser UI should never receive Supabase keys or connect to Supabase directly.

Env vars (recommended):
- MINDSCAPE_SUPABASE_URL
- MINDSCAPE_SUPABASE_SERVICE_ROLE_KEY

Fallback env vars (supported for convenience):
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY

Security:
- Never log keys.
- Fail closed when misconfigured.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Final


class SupabaseUnavailableError(RuntimeError):
    """Raised when supabase client is unavailable or misconfigured."""


# Supabase stack commonly exposes Kong externally as SUPABASE_PUBLIC_URL / API_EXTERNAL_URL.
SUPABASE_URL_ENV_KEYS: Final[tuple[str, ...]] = (
    "MINDSCAPE_SUPABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_PUBLIC_URL",
    "API_EXTERNAL_URL",
)

# Supabase stack commonly uses SERVICE_ROLE_KEY / SUPABASE_SERVICE_ROLE_KEY.
SUPABASE_SERVICE_KEY_ENV_KEYS: Final[tuple[str, ...]] = (
    "MINDSCAPE_SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SERVICE_ROLE_KEY",
    "SERVICE_KEY",
)


def _first_env(*keys: str) -> str | None:
    for k in keys:
        v = os.getenv(k)
        if v and v.strip():
            return v.strip()
    return None


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    service_role_key: str

    @staticmethod
    def from_env() -> "SupabaseSettings":
        url = _first_env(*SUPABASE_URL_ENV_KEYS)
        key = _first_env(*SUPABASE_SERVICE_KEY_ENV_KEYS)

        if not url:
            raise SupabaseUnavailableError(
                "Supabase is not configured (missing MINDSCAPE_SUPABASE_URL/SUPABASE_PUBLIC_URL)."
            )
        if not key:
            raise SupabaseUnavailableError(
                "Supabase is not configured (missing MINDSCAPE_SUPABASE_SERVICE_ROLE_KEY/SERVICE_ROLE_KEY)."
            )

        return SupabaseSettings(url=url, service_role_key=key)


def get_supabase_client() -> Any:
    """Create a Supabase client (service role) from environment variables."""
    settings = SupabaseSettings.from_env()

    try:
        from supabase import create_client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise SupabaseUnavailableError(
            "Supabase client library is not available. Install dependency: supabase."
        ) from exc

    # NOTE: Do not log settings/service_role_key.
    return create_client(settings.url, settings.service_role_key)