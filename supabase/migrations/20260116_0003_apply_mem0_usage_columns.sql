-- 20260116_0003_apply_mem0_usage_columns.sql
--
-- Apply Mem0 telemetry columns + safe llm_usage_daily view recreation.
--
-- Reason:
-- - Prior migration 20260116_0001 failed due to CREATE OR REPLACE VIEW attempting
--   to rename output columns (42P16), which caused the whole transaction to roll back.
-- - This migration applies the table changes and then drops/recreates the view in a
--   way that won't trigger 42P16.

begin;

-- 1) llm_usage_events: rename input_tokens -> raw_input_tokens (idempotent)
do $$
begin
  if exists (
    select 1
    from information_schema.tables
    where table_schema = 'public'
      and table_name = 'llm_usage_events'
  ) then
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

    -- Add mem0_input_tokens (portion of prompt attributable to Mem0-injected blocks)
    alter table public.llm_usage_events
      add column if not exists mem0_input_tokens bigint not null default 0
      check (mem0_input_tokens >= 0);
  end if;
end $$;

-- 2) llm_raw_prompts: rename prompt_text -> raw_prompt_text (idempotent)
do $$
begin
  if exists (
    select 1
    from information_schema.tables
    where table_schema = 'public'
      and table_name = 'llm_raw_prompts'
  ) then
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

    -- Add mem0_prompt_text (optional raw text of Mem0-injected system blocks)
    alter table public.llm_raw_prompts
      add column if not exists mem0_prompt_text text;
  end if;
end $$;

-- 3) Recreate rollup view safely (DROP + CREATE, no OR REPLACE)
--    This avoids 42P16 and ensures view matches the latest column names.
drop view if exists public.llm_usage_daily;

do $$
begin
  if exists (
    select 1
    from information_schema.tables
    where table_schema = 'public'
      and table_name = 'llm_usage_events'
  ) then
    execute $v$
      create view public.llm_usage_daily as
      select
        date_trunc('day', created_at) as day,
        app_id,
        task,
        provider,
        model,
        count(*)::bigint as requests,
        -- Expose new names; if a deployment hasn't renamed yet, this migration
        -- would have done so above.
        sum(raw_input_tokens)::bigint as raw_input_tokens,
        sum(mem0_input_tokens)::bigint as mem0_input_tokens,
        sum(output_tokens)::bigint as output_tokens,
        sum(total_tokens)::bigint as total_tokens,
        sum(estimated_cost)::numeric(12, 6) as estimated_cost
      from public.llm_usage_events
      group by 1, 2, 3, 4, 5;
    $v$;
  end if;
end $$;

-- Views inherit table permissions; keep defense-in-depth consistent.
revoke all on table public.llm_usage_daily from anon;
revoke all on table public.llm_usage_daily from authenticated;

commit;
