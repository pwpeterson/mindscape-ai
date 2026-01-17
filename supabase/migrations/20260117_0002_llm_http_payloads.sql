-- 20260117_0002_llm_http_payloads.sql
--
-- Optional request/response payload capture (privacy-sensitive)
--
-- Design goals:
-- - Keep llm_usage_events lean for analytics
-- - Store full inbound request JSON + (optionally) the full non-streaming response JSON
-- - Link 1:1 with llm_usage_events via request_id
-- - Restrict access: RLS enabled, no anon/auth access; writes via service role
--
-- NOTE:
-- - Streaming responses may be reconstructed and stored in response_json by buffering the
--   final response payload (implementation-dependent; increases CPU/memory and may require
--   careful backpressure handling).
-- - Consider TTL/retention policies separately (e.g., scheduled cleanup).

begin;

-- Supabase normally includes pgcrypto; keep this idempotent.
create extension if not exists pgcrypto;

create table if not exists public.llm_http_payloads (
  request_id text primary key,

  -- Dimensions copied for convenience (also present in llm_usage_events)
  app_id text null,
  task text null,
  provider text null,
  model text null,

  -- Payloads
  -- request_json: inbound request received by model-proxy (validated JSON body)
  -- response_json: non-streaming response returned to client; NULL for streaming
  request_json jsonb not null,
  response_json jsonb null,

  -- Helpful derived fields (match llm_usage_events conventions)
  prompt_sha256 text null,
  prompt_chars integer null,
  message_count integer null,

  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),

  constraint llm_http_payloads_request_id_fkey
    foreign key (request_id)
    references public.llm_usage_events (request_id)
    on delete cascade
);

comment on table public.llm_http_payloads is
  'Optional request/response payload capture (privacy-sensitive). Written only when explicitly enabled in model-proxy.';

-- Indexes to support filtering and time-based queries
create index if not exists idx_llm_http_payloads_created_at
  on public.llm_http_payloads (created_at);

create index if not exists idx_llm_http_payloads_app_task
  on public.llm_http_payloads (app_id, task);

create index if not exists idx_llm_http_payloads_provider_model
  on public.llm_http_payloads (provider, model);

-- GIN indexes for JSON querying (can be heavy; keep if you plan to query JSON fields)
create index if not exists idx_llm_http_payloads_request_json_gin
  on public.llm_http_payloads using gin (request_json);

create index if not exists idx_llm_http_payloads_response_json_gin
  on public.llm_http_payloads using gin (response_json);

-- Security: enable RLS and restrict grants
alter table public.llm_http_payloads enable row level security;

revoke all on table public.llm_http_payloads from anon;
revoke all on table public.llm_http_payloads from authenticated;

commit;