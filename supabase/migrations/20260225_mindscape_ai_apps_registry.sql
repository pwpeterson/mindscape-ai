-- ============================================================================
-- Mindscape AI Apps Registry (Supabase)
-- Date: 2026-02-25
--
-- Goal:
--   Recreate the Supabase-backed Apps registry table used by the Mindscape-AI API.
--
-- Used by:
--   - GET /api/v1/apps (UI dropdown; server returns only app_id + has_conport)
--   - GET /api/v1/apps/registry (Apps Manager UI; server returns full row including root_path)
--
-- Notes:
--   - The backend uses the Supabase *service role key* server-side.
--   - This table includes filesystem paths (root_path) and MUST NOT be broadly readable.
--   - Therefore: enable RLS and grant access to service_role only by default.
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Create table
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.mindscape_ai_apps (
    app_id TEXT PRIMARY KEY,
    display_name TEXT NULL,
    root_path TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.mindscape_ai_apps IS
    'Apps registry for Mindscape-AI. Stores app_id -> root_path (sensitive) plus display metadata.';

COMMENT ON COLUMN public.mindscape_ai_apps.app_id IS
    'Stable unique app identifier (e.g., project/package name).';

COMMENT ON COLUMN public.mindscape_ai_apps.root_path IS
    'Absolute path to the app/workspace root on the server runtime. Sensitive; not for direct client access.';

-- ============================================================================
-- STEP 2: Indexes
-- ============================================================================

-- Listing for UI dropdown: stable ordering by sort_order then app_id
CREATE INDEX IF NOT EXISTS mindscape_ai_apps_enabled_sort_idx
    ON public.mindscape_ai_apps (enabled, sort_order, app_id);

-- Useful for admin edits / lookups
CREATE INDEX IF NOT EXISTS mindscape_ai_apps_sort_idx
    ON public.mindscape_ai_apps (sort_order, app_id);

-- ============================================================================
-- STEP 3: updated_at trigger (best-effort convenience)
-- ============================================================================

CREATE OR REPLACE FUNCTION public.mindscape_ai_apps_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_mindscape_ai_apps_set_updated_at ON public.mindscape_ai_apps;

CREATE TRIGGER trg_mindscape_ai_apps_set_updated_at
BEFORE UPDATE ON public.mindscape_ai_apps
FOR EACH ROW
EXECUTE FUNCTION public.mindscape_ai_apps_set_updated_at();

-- ============================================================================
-- STEP 4: Row Level Security (service_role only by default)
-- ============================================================================

ALTER TABLE public.mindscape_ai_apps ENABLE ROW LEVEL SECURITY;

-- Fail closed: do not allow authenticated/anon by default because root_path is sensitive.
-- The application uses service_role for all access.
DROP POLICY IF EXISTS "Allow authenticated read access" ON public.mindscape_ai_apps;
DROP POLICY IF EXISTS "Allow service role full access" ON public.mindscape_ai_apps;

CREATE POLICY "Allow service role full access" ON public.mindscape_ai_apps
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- STEP 5: Verify migration
-- ============================================================================

DO $$
DECLARE
    apps_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO apps_count
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename = 'mindscape_ai_apps';

    IF apps_count = 0 THEN
        RAISE EXCEPTION 'Migration failed: mindscape_ai_apps table not found';
    END IF;

    RAISE NOTICE '✓ Migration verification passed';
    RAISE NOTICE '✓ mindscape_ai_apps table created';
END $$;

COMMIT;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================