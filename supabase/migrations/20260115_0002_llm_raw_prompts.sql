-- 20260115_0002_llm_raw_prompts.sql
-- Optional raw prompt capture table (store only when explicitly enabled in model-proxy)
--
-- Design goals:
-- - Keep core usage events table free of raw prompts (privacy by default)
-- - Allow occasional raw prompt storage for debugging/analysis
-- - Link raw prompts 1:1 with llm_usage_events via request_id
-- - Restrict access: RLS enabled, no anon/auth access; writes via service role

begin;

create table if not exists public.llm_raw_prompts (
  request_id text primary key,

  -- Dimensions copied for convenience (also present in llm_usage_events)
  app_id text null,
  task text null,
  provider text null,
  model text null,

  -- Raw prompt payload
  -- Store both a structured JSON (messages array) and a canonical JSON string.
  messages jsonb not null,
  prompt_text text not null,

  -- Helpful derived fields (match llm_usage_events conventions)
  prompt_sha256 text null,
  prompt_chars integer null,
  message_count integer null,

  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),

  constraint llm_raw_prompts_request_id_fkey
    foreign key (request_id)
    references public.llm_usage_events (request_id)
    on delete cascade
);

comment on table public.llm_raw_prompts is
  'Optional raw prompt capture (privacy-sensitive). Written only when STORE_RAW_PROMPT=true in model-proxy.';

-- Indexes to support filtering and time-based queries
create index if not exists idx_llm_raw_prompts_created_at
  on public.llm_raw_prompts (created_at);

create index if not exists idx_llm_raw_prompts_app_task
  on public.llm_raw_prompts (app_id, task);

create index if not exists idx_llm_raw_prompts_provider_model
  on public.llm_raw_prompts (provider, model);

-- Optional: GIN index for searching/filtering within JSON messages (can be heavy; keep if useful)
create index if not exists idx_llm_raw_prompts_messages_gin
  on public.llm_raw_prompts using gin (messages);

-- Security: enable RLS and restrict grants
alter table public.llm_raw_prompts enable row level security;

revoke all on table public.llm_raw_prompts from anon;
revoke all on table public.llm_raw_prompts from authenticated;

commit;
