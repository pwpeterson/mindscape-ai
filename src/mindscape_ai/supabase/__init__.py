"""Supabase integration for Mindscape-AI.

Mindscape uses Supabase as a shared persistence layer for cross-app configuration/state.

Security model (intended):
- The Mindscape backend uses a service-role key (server-side only) to perform CRUD.
- The Mindscape web UI talks only to the Mindscape API, not directly to Supabase.
- Do NOT log or expose Supabase keys to clients.

This package provides a thin wrapper around `supabase-py`.
"""