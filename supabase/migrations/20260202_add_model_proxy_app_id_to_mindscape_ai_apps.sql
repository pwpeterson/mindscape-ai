-- ============================================================================
-- Add model_proxy_app_id mapping to mindscape_ai_apps
-- Date: 2026-02-02
--
-- Purpose:
--   Mindscape-AI uses string app_id values (typically workspace/app slug).
--   model-proxy's newer schema (model_proxy_api_requests) uses a numeric app_id.
--
--   Context Metrics endpoints accept Mindscape's string app_id and resolve it to
--   the numeric model-proxy app_id via this mapping column.
-- ============================================================================

BEGIN;

ALTER TABLE IF EXISTS public.mindscape_ai_apps
    ADD COLUMN IF NOT EXISTS model_proxy_app_id integer;

COMMENT ON COLUMN public.mindscape_ai_apps.model_proxy_app_id IS
    'Optional mapping to model-proxy numeric app_id (model_proxy_api_requests.app_id).';

CREATE INDEX IF NOT EXISTS idx_mindscape_ai_apps_model_proxy_app_id
    ON public.mindscape_ai_apps (model_proxy_app_id);

COMMIT;