"""Supabase client utilities for Mindscape-AI (server-side).

This module intentionally supports *server-side* Supabase access using a service role key.
The browser UI should never receive Supabase keys or connect to Supabase directly.

Env vars (recommended):
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY

Fallback env vars (supported for convenience / backward compatibility):
- MINDSCAPE_SUPABASE_URL
- MINDSCAPE_SUPABASE_SERVICE_ROLE_KEY

Security:
- Never log keys.
- Fail closed when misconfigured.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Final
from urllib.parse import urlparse, urlunparse


class SupabaseUnavailableError(RuntimeError):
    """Raised when supabase client is unavailable or misconfigured."""


# Supabase stack commonly exposes Kong externally as SUPABASE_PUBLIC_URL / API_EXTERNAL_URL.
SUPABASE_URL_ENV_KEYS: Final[tuple[str, ...]] = (
    "SUPABASE_URL",
    "SUPABASE_PUBLIC_URL",
    "API_EXTERNAL_URL",
    # Backward compatibility:
    "MINDSCAPE_SUPABASE_URL",
)

# Supabase stack commonly uses SERVICE_ROLE_KEY / SUPABASE_SERVICE_ROLE_KEY.
SUPABASE_SERVICE_KEY_ENV_KEYS: Final[tuple[str, ...]] = (
    "SUPABASE_SERVICE_ROLE_KEY",
    "SERVICE_ROLE_KEY",
    "SERVICE_KEY",
    # Backward compatibility:
    "MINDSCAPE_SUPABASE_SERVICE_ROLE_KEY",
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
    def from_env() -> SupabaseSettings:
        url_raw = _first_env(*SUPABASE_URL_ENV_KEYS)
        key = _first_env(*SUPABASE_SERVICE_KEY_ENV_KEYS)

        if not url_raw:
            raise SupabaseUnavailableError(
                "Supabase is not configured (missing SUPABASE_URL/SUPABASE_PUBLIC_URL)."
            )
        if not key:
            raise SupabaseUnavailableError(
                "Supabase is not configured (missing SUPABASE_SERVICE_ROLE_KEY/SERVICE_ROLE_KEY)."
            )

        url = _normalize_supabase_url(url_raw)

        return SupabaseSettings(url=url, service_role_key=key)


def _normalize_supabase_url(url: str) -> str:
    """Normalize SUPABASE_URL to the *base* Supabase URL expected by supabase-py.

    Common misconfigurations include setting SUPABASE_URL to a subpath like:
    - http://localhost:8000/rest/v1
    - http://localhost:8000/auth/v1

    supabase-py expects the base (Kong) URL and appends service paths internally.
    """
    u = (url or "").strip()
    if not u:
        return u

    parsed = urlparse(u)

    # If it's not a normal URL, keep as-is and let downstream raise a helpful error.
    if not parsed.scheme or not parsed.netloc:
        return u.rstrip("/")

    path = parsed.path or ""

    # Trim at well-known Supabase service prefixes if present.
    for marker in ("/rest/v1", "/auth/v1", "/storage/v1", "/functions/v1"):
        idx = path.find(marker)
        if idx != -1:
            path = path[:idx]
            break

    path = path.rstrip("/")

    normalized = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    return normalized.rstrip("/")


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
