-- 20260116_0002_fix_llm_usage_daily_view.sql
--
-- Fix: Postgres error 42P16 when CREATE OR REPLACE VIEW attempts to rename
-- existing view output columns.
--
-- Additional fix: handle environments where the underlying table hasn't yet
-- been migrated (e.g. still has input_tokens instead of raw_input_tokens).
-- We use dynamic SQL so the view definition never references missing columns
-- at parse time.

begin;

drop view if exists public.llm_usage_daily;

do $$
declare
  has_raw_input boolean;
  has_mem0_input boolean;
begin
  select exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'llm_usage_events'
      and column_name = 'raw_input_tokens'
  ) into has_raw_input;

  select exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'llm_usage_events'
      and column_name = 'mem0_input_tokens'
  ) into has_mem0_input;

  if has_raw_input then
    if has_mem0_input then
      execute $v$
        create view public.llm_usage_daily as
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
      $v$;
    else
      execute $v$
        create view public.llm_usage_daily as
        select
          date_trunc('day', created_at) as day,
          app_id,
          task,
          provider,
          model,
          count(*)::bigint as requests,
          sum(raw_input_tokens)::bigint as raw_input_tokens,
          0::bigint as mem0_input_tokens,
          sum(output_tokens)::bigint as output_tokens,
          sum(total_tokens)::bigint as total_tokens,
          sum(estimated_cost)::numeric(12, 6) as estimated_cost
        from public.llm_usage_events
        group by 1, 2, 3, 4, 5;
      $v$;
    end if;
  else
    -- Pre-migration schema fallback (input_tokens exists, mem0_input_tokens does not)
    execute $v$
      create view public.llm_usage_daily as
      select
        date_trunc('day', created_at) as day,
        app_id,
        task,
        provider,
        model,
        count(*)::bigint as requests,
        sum(input_tokens)::bigint as raw_input_tokens,
        0::bigint as mem0_input_tokens,
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
