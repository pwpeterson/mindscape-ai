-- Mindscape-AI Supabase schema: LLM usage analytics events
--
-- Applies to Supabase Postgres (public schema).
-- Intended usage:
-- - model-proxy (and other apps) write rows using Supabase service role key
-- - dashboards/analysis query rollups by app_id/task/model/provider
--
-- Privacy:
-- - NO raw prompts stored
-- - Only prompt hashes + counts (chars/message_count)

begin;

-- Supabase normally includes pgcrypto; keep this idempotent.
create extension if not exists pgcrypto;

create table if not exists public.llm_usage_events (
    id uuid primary key default gen_random_uuid(),

    -- Correlation / identity
    request_id text not null unique
        check (length(request_id) <= 200),

    -- App/task dimensions
    app_id text null
        check (length(app_id) <= 200)
        check (app_id ~ '^[A-Za-z0-9_.-]+$')
        references public.mindscape_ai_apps(app_id),

    task text null
        check (length(task) <= 200)
        check (task ~ '^[A-Za-z0-9_.:-]+$'),

    -- Who/what initiated the run (optional; may be null)
    user_id text null check (length(user_id) <= 200),
    agent_id text null check (length(agent_id) <= 200),
    project_id text null check (length(project_id) <= 200),

    -- Routing
    provider text not null
        check (length(provider) <= 50)
        check (provider ~ '^[A-Za-z0-9_.-]+$'),

    model text not null
        check (length(model) <= 200),

    -- Usage
    input_tokens bigint not null default 0 check (input_tokens >= 0),
    output_tokens bigint not null default 0 check (output_tokens >= 0),
    total_tokens bigint generated always as (input_tokens + output_tokens) stored,

    -- Cost stored as numeric for safe aggregation
    estimated_cost numeric(12, 6) not null default 0 check (estimated_cost >= 0),

    -- Prompt privacy-safe fingerprints
    prompt_sha256 text null
        check (prompt_sha256 ~ '^[a-f0-9]{64}$'),
    prompt_chars integer null check (prompt_chars >= 0),
    message_count integer null check (message_count >= 0),

    -- Request metadata
    route text null check (length(route) <= 200),
    status_code integer null check (status_code >= 100 and status_code <= 599),
    latency_ms integer null check (latency_ms >= 0),
    stream boolean not null default false,

    -- Future-proof: additional structured metadata (no prompts)
    metadata jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Helpful indexes for analytics queries
create index if not exists llm_usage_events_created_at_idx
    on public.llm_usage_events (created_at desc);

create index if not exists llm_usage_events_app_created_at_idx
    on public.llm_usage_events (app_id, created_at desc);

create index if not exists llm_usage_events_app_task_model_created_at_idx
    on public.llm_usage_events (app_id, task, model, created_at desc);

create index if not exists llm_usage_events_provider_model_created_at_idx
    on public.llm_usage_events (provider, model, created_at desc);

-- Keep updated_at current (function defined in 20260113_0001_mindscape_ai_apps.sql)
drop trigger if exists llm_usage_events_set_updated_at on public.llm_usage_events;

create trigger llm_usage_events_set_updated_at
before update on public.llm_usage_events
for each row
execute function public.mindscape_set_updated_at();

-- Security: lock down table access. Writes occur using the service role key.
alter table public.llm_usage_events enable row level security;

-- Explicitly revoke browser-facing roles (defense-in-depth).
revoke all on table public.llm_usage_events from anon;
revoke all on table public.llm_usage_events from authenticated;

-- Rollup view for daily analytics
create or replace view public.llm_usage_daily as
select
    date_trunc('day', created_at) as day,
    app_id,
    task,
    provider,
    model,
    count(*)::bigint as requests,
    sum(input_tokens)::bigint as input_tokens,
    sum(output_tokens)::bigint as output_tokens,
    sum(total_tokens)::bigint as total_tokens,
    sum(estimated_cost)::numeric(12, 6) as estimated_cost
from public.llm_usage_events
group by 1, 2, 3, 4, 5;

-- Views inherit table permissions; keep defense-in-depth consistent.
revoke all on table public.llm_usage_daily from anon;
revoke all on table public.llm_usage_daily from authenticated;

commit;
