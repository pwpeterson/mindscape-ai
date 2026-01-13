-- Mindscape-AI Supabase schema: managed apps registry
--
-- Applies to Supabase Postgres (public schema).
-- Intended usage: Mindscape-AI backend uses the service role key to perform CRUD.
--
-- Notes:
-- - We intentionally store filesystem paths in this table to let the Mindscape server
--   resolve local resources (e.g., ConPort DBs) per app. The Mindscape API should
--   avoid returning these paths to the browser UI.

begin;

-- Supabase normally includes pgcrypto; keep this idempotent.
create extension if not exists pgcrypto;

create table if not exists public.mindscape_ai_apps (
    id uuid primary key default gen_random_uuid(),

    -- Stable identifier used throughout Mindscape (matches ConPort/Mem0 metadata.app_id convention).
    -- Constrained to a safe charset so it can be used in URLs/paths/labels without escaping.
    app_id text not null unique
        check (length(app_id) <= 200)
        check (app_id ~ '^[A-Za-z0-9_.-]+$'),

    -- Optional human-friendly label.
    display_name text null,

    -- Local filesystem root of the managed app/project (absolute path required).
    -- NOTE: This is sensitive; Mindscape API must never return it to browser clients.
    root_path text not null
        check (length(root_path) <= 4096)
        check (root_path like '/%'),

    -- Soft-disable apps without deleting configuration.
    enabled boolean not null default true,

    -- UI ordering (lower first).
    sort_order integer not null default 0,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists mindscape_ai_apps_enabled_sort_idx
    on public.mindscape_ai_apps (enabled, sort_order, app_id);

-- Keep updated_at current.
create or replace function public.mindscape_set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists mindscape_ai_apps_set_updated_at on public.mindscape_ai_apps;

create trigger mindscape_ai_apps_set_updated_at
before update on public.mindscape_ai_apps
for each row
execute function public.mindscape_set_updated_at();

-- Security: lock down table access. Mindscape-AI backend uses service role key.
-- Enable RLS to ensure PostgREST/JWT roles cannot access without explicit policies.
alter table public.mindscape_ai_apps enable row level security;

-- Explicitly revoke browser-facing roles (defense-in-depth).
revoke all on table public.mindscape_ai_apps from anon;
revoke all on table public.mindscape_ai_apps from authenticated;

commit;