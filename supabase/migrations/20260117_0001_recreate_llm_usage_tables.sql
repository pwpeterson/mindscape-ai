-- 20260117_0001_recreate_llm_usage_tables.sql
--
-- DESTRUCTIVE MIGRATION
--
-- Drops and recreates:
-- - public.llm_raw_prompts
-- - public.llm_usage_daily (view)
-- - public.llm_usage_events
--
-- Purpose:
-- - Align schema to latest model-proxy telemetry changes:
--   - llm_usage_events:
--       * drop user_id, agent_id
--       * use input_tokens (not raw_input_tokens)
--       * drop mem0_* columns
--   - llm_raw_prompts:
--       * store only messages JSON (no raw_prompt_text / mem0_prompt_text)
--
-- WARNING:
-- - This will delete existing analytics data.

begin;

-- Drop dependents first
DROP VIEW IF EXISTS public.llm_usage_daily;

-- If payload capture migration was applied earlier, it adds a FK to llm_usage_events.
-- Drop it first to avoid: "cannot drop table llm_usage_events because other objects depend on it".
DROP TABLE IF EXISTS public.llm_http_payloads;

DROP TABLE IF EXISTS public.llm_raw_prompts;
DROP TABLE IF EXISTS public.llm_usage_events;

-- Supabase normally includes pgcrypto; keep this idempotent.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Recreate usage events table (public schema)
CREATE TABLE public.llm_usage_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Correlation / identity
    request_id text NOT NULL UNIQUE
        CHECK (length(request_id) <= 200),

    -- App/task dimensions
    app_id text NULL
        CHECK (length(app_id) <= 200)
        CHECK (app_id ~ '^[A-Za-z0-9_.-]+$')
        REFERENCES public.mindscape_ai_apps(app_id),

    task text NULL
        CHECK (length(task) <= 200)
        CHECK (task ~ '^[A-Za-z0-9_.:-]+$'),

    -- Project dimension (optional)
    project_id text NULL CHECK (length(project_id) <= 200),

    -- Routing
    provider text NOT NULL
        CHECK (length(provider) <= 50)
        CHECK (provider ~ '^[A-Za-z0-9_.-]+$'),

    model text NOT NULL
        CHECK (length(model) <= 200),

    -- Usage
    input_tokens bigint NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens bigint NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),

    -- Total prompt+completion tokens for cost aggregation.
    total_tokens bigint GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,

    -- Cost stored as numeric for safe aggregation
    estimated_cost numeric(12, 6) NOT NULL DEFAULT 0 CHECK (estimated_cost >= 0),

    -- Prompt privacy-safe fingerprints
    prompt_sha256 text NULL
        CHECK (prompt_sha256 ~ '^[a-f0-9]{64}$'),
    prompt_chars integer NULL CHECK (prompt_chars >= 0),
    message_count integer NULL CHECK (message_count >= 0),

    -- Request metadata
    route text NULL CHECK (length(route) <= 200),
    status_code integer NULL CHECK (status_code >= 100 AND status_code <= 599),
    latency_ms integer NULL CHECK (latency_ms >= 0),
    stream boolean NOT NULL DEFAULT false,

    -- Future-proof: additional structured metadata (no prompts)
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Helpful indexes for analytics queries
CREATE INDEX IF NOT EXISTS llm_usage_events_created_at_idx
    ON public.llm_usage_events (created_at DESC);

CREATE INDEX IF NOT EXISTS llm_usage_events_app_created_at_idx
    ON public.llm_usage_events (app_id, created_at DESC);

CREATE INDEX IF NOT EXISTS llm_usage_events_app_task_model_created_at_idx
    ON public.llm_usage_events (app_id, task, model, created_at DESC);

CREATE INDEX IF NOT EXISTS llm_usage_events_provider_model_created_at_idx
    ON public.llm_usage_events (provider, model, created_at DESC);

-- Keep updated_at current (function defined in 20260113_0001_mindscape_ai_apps.sql)
DROP TRIGGER IF EXISTS llm_usage_events_set_updated_at ON public.llm_usage_events;

CREATE TRIGGER llm_usage_events_set_updated_at
BEFORE UPDATE ON public.llm_usage_events
FOR EACH ROW
EXECUTE FUNCTION public.mindscape_set_updated_at();

-- Security: lock down table access. Writes occur using the service role key.
ALTER TABLE public.llm_usage_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.llm_usage_events FROM anon;
REVOKE ALL ON TABLE public.llm_usage_events FROM authenticated;

-- Recreate raw prompts table (privacy sensitive; only written when explicitly enabled)
CREATE TABLE public.llm_raw_prompts (
  request_id text PRIMARY KEY,

  -- Dimensions copied for convenience (also present in llm_usage_events)
  app_id text NULL,
  task text NULL,
  provider text NULL,
  model text NULL,

  -- Raw prompt payload
  -- Store only a structured JSON (messages array). No canonical JSON strings.
  messages jsonb NOT NULL,

  -- Helpful derived fields (match llm_usage_events conventions)
  prompt_sha256 text NULL,
  prompt_chars integer NULL,
  message_count integer NULL,

  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT llm_raw_prompts_request_id_fkey
    FOREIGN KEY (request_id)
    REFERENCES public.llm_usage_events (request_id)
    ON DELETE CASCADE
);

COMMENT ON TABLE public.llm_raw_prompts IS
  'Optional raw prompt capture (privacy-sensitive). Written only when STORE_RAW_PROMPT=true in model-proxy.';

-- Indexes to support filtering and time-based queries
CREATE INDEX IF NOT EXISTS idx_llm_raw_prompts_created_at
  ON public.llm_raw_prompts (created_at);

CREATE INDEX IF NOT EXISTS idx_llm_raw_prompts_app_task
  ON public.llm_raw_prompts (app_id, task);

CREATE INDEX IF NOT EXISTS idx_llm_raw_prompts_provider_model
  ON public.llm_raw_prompts (provider, model);

CREATE INDEX IF NOT EXISTS idx_llm_raw_prompts_messages_gin
  ON public.llm_raw_prompts USING gin (messages);

-- Security: enable RLS and restrict grants
ALTER TABLE public.llm_raw_prompts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.llm_raw_prompts FROM anon;
REVOKE ALL ON TABLE public.llm_raw_prompts FROM authenticated;

-- Recreate rollup view for daily analytics
CREATE VIEW public.llm_usage_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    app_id,
    task,
    provider,
    model,
    count(*)::bigint AS requests,
    sum(input_tokens)::bigint AS input_tokens,
    sum(output_tokens)::bigint AS output_tokens,
    sum(total_tokens)::bigint AS total_tokens,
    sum(estimated_cost)::numeric(12, 6) AS estimated_cost
FROM public.llm_usage_events
GROUP BY 1, 2, 3, 4, 5;

REVOKE ALL ON TABLE public.llm_usage_daily FROM anon;
REVOKE ALL ON TABLE public.llm_usage_daily FROM authenticated;

commit;
