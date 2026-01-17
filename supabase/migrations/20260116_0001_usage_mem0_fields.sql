-- 20260116_0001_usage_mem0_fields.sql
--
-- Add fields to distinguish raw prompt usage from Mem0-injected usage.
--
-- Changes:
-- - llm_usage_events: input_tokens -> raw_input_tokens, add mem0_input_tokens
-- - llm_raw_prompts: prompt_text -> raw_prompt_text, add mem0_prompt_text
-- - llm_usage_daily view: update to new column names

begin;

-- 1) llm_usage_events: rename input_tokens -> raw_input_tokens (idempotent)
do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'llm_usage_events'
      and column_name = 'input_tokens'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'llm_usage_events'
      and column_name = 'raw_input_tokens'
  ) then
    alter table public.llm_usage_events
      rename column input_tokens to raw_input_tokens;
  end if;
end $$;

-- Add mem0_input_tokens (portion of prompt attributable to Mem0-injected blocks)
alter table public.llm_usage_events
  add column if not exists mem0_input_tokens bigint not null default 0
  check (mem0_input_tokens >= 0);

-- 2) llm_raw_prompts: rename prompt_text -> raw_prompt_text (idempotent)
do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'llm_raw_prompts'
      and column_name = 'prompt_text'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'llm_raw_prompts'
      and column_name = 'raw_prompt_text'
  ) then
    alter table public.llm_raw_prompts
      rename column prompt_text to raw_prompt_text;
  end if;
end $$;

-- Add mem0_prompt_text (optional raw text of Mem0-injected system blocks)
alter table public.llm_raw_prompts
  add column if not exists mem0_prompt_text text;

-- 3) Update rollup view to reference new columns
create or replace view public.llm_usage_daily as
select
  date_trunc('day', created_at) as day,
  app_id,
  task,
  provider,
  model,
  count(*)::bigint as requests,
  sum(raw_input_tokens)::bigint as raw_input_tokens,
  sum(mem0_input_tokens)::bigint as mem0_input_tokens,
  sum(output_tokens)::bigint as output_tokens,
  sum(total_tokens)::bigint as total_tokens,
  sum(estimated_cost)::numeric(12, 6) as estimated_cost
from public.llm_usage_events
group by 1, 2, 3, 4, 5;

-- Views inherit table permissions; keep defense-in-depth consistent.
revoke all on table public.llm_usage_daily from anon;
revoke all on table public.llm_usage_daily from authenticated;

commit;
