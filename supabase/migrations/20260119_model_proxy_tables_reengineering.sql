-- ============================================================================
-- Model Proxy Tables Re-engineering - Fresh Start Migration (Supabase)
-- Date: 2026-01-19
-- Description:
--   - Drop legacy llm_* objects (tables/views/materialized views)
--   - Create new model_proxy_* tables
--   - Create materialized view model_proxy_daily_stats + refresh function
--
-- IMPORTANT:
--   This migration DOES NOT preserve historical data.
--   All existing data in legacy llm_* objects will be permanently lost.
-- ============================================================================

BEGIN;

-- Required for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- If this migration was partially applied, re-running would fail on CREATE statements.
-- Since this is a "fresh start" migration, drop the new objects as well.
DROP MATERIALIZED VIEW IF EXISTS model_proxy_daily_stats CASCADE;
DROP TABLE IF EXISTS model_proxy_payloads CASCADE;
DROP TABLE IF EXISTS model_proxy_requests CASCADE;
DROP FUNCTION IF EXISTS refresh_model_proxy_daily_stats();

-- ============================================================================
-- STEP 1: Drop legacy llm_* objects
-- ============================================================================

DROP TABLE IF EXISTS llm_usage_events CASCADE;
DROP TABLE IF EXISTS llm_http_payloads CASCADE;
DROP TABLE IF EXISTS llm_raw_prompts CASCADE;

-- llm_usage_daily may have been created as a view/materialized view/table in older versions.
-- In Postgres, DROP MATERIALIZED VIEW will ERROR if the object exists but is a plain VIEW (and vice versa),
-- so we must detect the object type first.
DO $$
DECLARE
    obj regclass;
    kind "char";
BEGIN
    obj := to_regclass('public.llm_usage_daily');
    IF obj IS NULL THEN
        RETURN;
    END IF;

    SELECT c.relkind INTO kind
    FROM pg_class c
    WHERE c.oid = obj;

    IF kind = 'm' THEN
        EXECUTE 'DROP MATERIALIZED VIEW public.llm_usage_daily CASCADE';
    ELSIF kind = 'v' THEN
        EXECUTE 'DROP VIEW public.llm_usage_daily CASCADE';
    ELSE
        EXECUTE 'DROP TABLE public.llm_usage_daily CASCADE';
    END IF;
END $$;

-- Drop legacy backup tables if they exist
DROP TABLE IF EXISTS llm_usage_events_backup CASCADE;
DROP TABLE IF EXISTS llm_http_payloads_backup CASCADE;

SELECT 'Dropped all legacy llm_* objects' AS notice;

-- ============================================================================
-- STEP 2: Create model_proxy_requests table
--
-- NOTE: This schema is aligned with what TokenUsageTracker inserts via:
--       - src/utils/token_usage_tracker.py::_write_supabase_usage
-- ============================================================================

CREATE TABLE model_proxy_requests (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Stable request identifier used by the application (also used to link payloads)
    -- NOTE: model-proxy request_ids are opaque strings (often "req_<...>"); they are NOT guaranteed to be UUIDs.
    request_id TEXT UNIQUE NOT NULL,

    -- Identity & Project Tracking (for Mindscape-AI drill-down)
    app_id VARCHAR(255),
    project_id VARCHAR(255),
    user_id VARCHAR(255),

    -- Optional "task" label for drill-down
    task VARCHAR(255),

    -- Model & Provider
    model VARCHAR(255) NOT NULL,
    provider_name VARCHAR(100),

    -- Token tracking (with _tokens suffix)
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER GENERATED ALWAYS AS (
        COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)
    ) STORED,
    cached_tokens INTEGER DEFAULT 0,

    -- Character counts (with _count suffix)
    prompt_char_count INTEGER,
    response_char_count INTEGER,

    -- Prompt hashing / message counts
    prompt_sha256 TEXT,
    message_count INTEGER,

    -- Request routing & streaming
    route VARCHAR(255),
    stream BOOLEAN DEFAULT FALSE,

    -- Cost tracking (calculated from models_config.json)
    estimated_cost DECIMAL(12, 6),
    pricing_tier VARCHAR(50) DEFAULT 'standard',

    -- Timing fields
    request_timestamp TIMESTAMPTZ DEFAULT NOW(),
    response_timestamp TIMESTAMPTZ,
    latency_ms INTEGER,

    -- Status tracking
    status_code INTEGER,
    error_message TEXT,

    -- Freeform structured metadata (includes user_agent, etc.)
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Audit fields
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE model_proxy_requests IS
    'Tracks request-level usage events for model-proxy. Used by Mindscape-AI for project drill-down and analytics.';

COMMENT ON COLUMN model_proxy_requests.request_id IS 'Application request UUID (links to model_proxy_payloads.request_id)';
COMMENT ON COLUMN model_proxy_requests.app_id IS 'Application identifier for drill-down';
COMMENT ON COLUMN model_proxy_requests.project_id IS 'Project identifier for multi-project tracking';
COMMENT ON COLUMN model_proxy_requests.user_id IS 'User identifier for user-level analytics';
COMMENT ON COLUMN model_proxy_requests.task IS 'Optional task label for drill-down';
COMMENT ON COLUMN model_proxy_requests.input_tokens IS 'Input tokens sent to model';
COMMENT ON COLUMN model_proxy_requests.output_tokens IS 'Output tokens received from model';
COMMENT ON COLUMN model_proxy_requests.total_tokens IS 'Total tokens (input + output) - computed field';
COMMENT ON COLUMN model_proxy_requests.cached_tokens IS 'Cached tokens (prompt caching) - reduces cost';
COMMENT ON COLUMN model_proxy_requests.prompt_char_count IS 'Character count of prompt text';
COMMENT ON COLUMN model_proxy_requests.response_char_count IS 'Character count of response text';
COMMENT ON COLUMN model_proxy_requests.prompt_sha256 IS 'SHA-256 hash of canonical prompt JSON';
COMMENT ON COLUMN model_proxy_requests.message_count IS 'Number of chat messages in request';
COMMENT ON COLUMN model_proxy_requests.route IS 'API route that handled the request (e.g., /v1/chat/completions)';
COMMENT ON COLUMN model_proxy_requests.stream IS 'Whether request used streaming';
COMMENT ON COLUMN model_proxy_requests.estimated_cost IS 'Estimated cost in USD';
COMMENT ON COLUMN model_proxy_requests.pricing_tier IS 'Pricing tier used (standard, priority)';
COMMENT ON COLUMN model_proxy_requests.metadata IS 'Freeform JSON metadata (includes user_agent, extra context)';

-- ============================================================================
-- STEP 3: Create model_proxy_payloads table
--
-- NOTE: This schema is aligned with what TokenUsageTracker inserts via:
--       - src/utils/token_usage_tracker.py::write_http_payload
--       - src/utils/token_usage_tracker.py::_write_supabase_http_payload
-- ============================================================================

CREATE TABLE model_proxy_payloads (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Application request identifier (links to model_proxy_requests.request_id)
    request_id TEXT REFERENCES model_proxy_requests(request_id) ON DELETE CASCADE,

    -- Drill-down context
    app_id VARCHAR(255),
    project_id VARCHAR(255),
    user_id VARCHAR(255),
    task VARCHAR(255),

    -- Model routing
    provider VARCHAR(100),
    model VARCHAR(255),

    -- Full payloads (privacy-sensitive, controlled by ENABLE_SUPABASE_PAYLOAD_LOGGING)
    request_json JSONB NOT NULL,
    response_json JSONB,

    -- Prompt hashing / sizes
    prompt_sha256 TEXT,
    prompt_chars INTEGER,
    message_count INTEGER,

    -- Optional text storage (privacy-sensitive; controlled by STORE_PAYLOAD_PROMPT_TEXT)
    prompt_text TEXT,

    -- Context tracking
    context_length INTEGER,
    context_tokens INTEGER,
    context_text TEXT,

    -- Additional metadata (also used for route/status_code/latency_ms/stream)
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Audit fields
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE model_proxy_payloads IS
    'Stores full HTTP request/response payloads for model-proxy requests. Privacy-sensitive: controlled by ENABLE_SUPABASE_PAYLOAD_LOGGING.';

COMMENT ON COLUMN model_proxy_payloads.request_id IS 'Foreign key linking to model_proxy_requests.request_id';
COMMENT ON COLUMN model_proxy_payloads.request_json IS 'Full HTTP request payload as JSON';
COMMENT ON COLUMN model_proxy_payloads.response_json IS 'Full HTTP response payload as JSON';
COMMENT ON COLUMN model_proxy_payloads.prompt_text IS 'Prompt text (stored only if STORE_PAYLOAD_PROMPT_TEXT=true)';
COMMENT ON COLUMN model_proxy_payloads.context_length IS 'Model context window capacity (from models_config.json)';
COMMENT ON COLUMN model_proxy_payloads.context_tokens IS 'Actual tokens used in this specific request (estimated/observed)';
COMMENT ON COLUMN model_proxy_payloads.context_text IS 'Canonical prompt/messages JSON used for context tracking (privacy-sensitive)';
COMMENT ON COLUMN model_proxy_payloads.metadata IS 'Freeform JSON metadata (route/status_code/latency_ms/stream, etc.)';

-- ============================================================================
-- STEP 4: Create indexes for drill-down queries
-- ============================================================================

CREATE INDEX idx_requests_app_project_time
    ON model_proxy_requests(app_id, project_id, request_timestamp DESC);

CREATE INDEX idx_requests_model_time
    ON model_proxy_requests(model, request_timestamp DESC);

CREATE INDEX idx_requests_provider_time
    ON model_proxy_requests(provider_name, request_timestamp DESC);

CREATE INDEX idx_requests_cost
    ON model_proxy_requests(estimated_cost DESC, request_timestamp DESC);

CREATE INDEX idx_requests_errors
    ON model_proxy_requests(status_code)
    WHERE status_code >= 400;

CREATE INDEX idx_requests_request_id
    ON model_proxy_requests(request_id);

CREATE INDEX idx_requests_timestamp
    ON model_proxy_requests(request_timestamp DESC);

CREATE INDEX idx_payloads_request_id
    ON model_proxy_payloads(request_id);

CREATE INDEX idx_payloads_context
    ON model_proxy_payloads(context_length);

SELECT 'Created indexes for query optimization' AS notice;

-- ============================================================================
-- STEP 5: Create materialized view for daily statistics
-- ============================================================================

CREATE MATERIALIZED VIEW model_proxy_daily_stats AS
SELECT
    DATE(request_timestamp) AS stat_date,
    app_id,
    project_id,
    model,
    provider_name,
    pricing_tier,
    COUNT(*) AS request_count,
    SUM(input_tokens) AS total_input_tokens,
    SUM(output_tokens) AS total_output_tokens,
    SUM(total_tokens) AS total_tokens,
    SUM(cached_tokens) AS total_cached_tokens,
    SUM(estimated_cost) AS total_estimated_cost,
    AVG(latency_ms) AS avg_latency_ms,
    MAX(latency_ms) AS max_latency_ms,
    MIN(latency_ms) AS min_latency_ms,
    COUNT(*) FILTER (WHERE status_code >= 400) AS error_count,
    AVG(estimated_cost) AS avg_cost_per_request
FROM model_proxy_requests
WHERE request_timestamp IS NOT NULL
GROUP BY
    DATE(request_timestamp),
    app_id,
    project_id,
    model,
    provider_name,
    pricing_tier
ORDER BY stat_date DESC, total_estimated_cost DESC;

CREATE INDEX idx_daily_stats_date_app
    ON model_proxy_daily_stats(stat_date DESC, app_id, project_id);

CREATE INDEX idx_daily_stats_model
    ON model_proxy_daily_stats(model, stat_date DESC);

COMMENT ON MATERIALIZED VIEW model_proxy_daily_stats IS
    'Daily aggregated statistics for model proxy usage. Refresh nightly or on-demand via refresh_model_proxy_daily_stats().';

SELECT 'Created materialized view for daily statistics' AS notice;

-- ============================================================================
-- STEP 6: Create function to refresh materialized view
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_model_proxy_daily_stats()
RETURNS void AS $$
BEGIN
    -- Use non-concurrent refresh for Supabase compatibility.
    REFRESH MATERIALIZED VIEW model_proxy_daily_stats;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_model_proxy_daily_stats() IS
    'Refreshes model_proxy_daily_stats materialized view. Call nightly or on-demand for updated statistics.';

-- ============================================================================
-- STEP 7: Verify migration
-- ============================================================================

DO $$
DECLARE
    requests_count INTEGER;
    payloads_count INTEGER;
    view_exists BOOLEAN;
BEGIN
    SELECT COUNT(*) INTO requests_count
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename = 'model_proxy_requests';

    SELECT COUNT(*) INTO payloads_count
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename = 'model_proxy_payloads';

    SELECT EXISTS (
        SELECT 1
        FROM pg_matviews
        WHERE schemaname = 'public'
          AND matviewname = 'model_proxy_daily_stats'
    ) INTO view_exists;

    IF requests_count = 0 THEN
        RAISE EXCEPTION 'Migration failed: model_proxy_requests table not found';
    END IF;

    IF payloads_count = 0 THEN
        RAISE EXCEPTION 'Migration failed: model_proxy_payloads table not found';
    END IF;

    IF NOT view_exists THEN
        RAISE EXCEPTION 'Migration failed: model_proxy_daily_stats view not found';
    END IF;

    RAISE NOTICE '✓ Migration verification passed';
    RAISE NOTICE '✓ model_proxy_requests table created';
    RAISE NOTICE '✓ model_proxy_payloads table created';
    RAISE NOTICE '✓ model_proxy_daily_stats view created';
    RAISE NOTICE '✓ All indexes created';
END $$;

COMMIT;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
