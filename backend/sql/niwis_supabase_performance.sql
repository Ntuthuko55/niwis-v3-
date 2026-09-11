-- Run once in Supabase Dashboard -> SQL Editor.
-- This matches the application's common read: one province, ordered by date.
-- CONCURRENTLY keeps the existing NIWIS table available while the index builds.
CREATE INDEX CONCURRENTLY IF NOT EXISTS niwis_daily_climate_v2_province_date_idx
    ON public.niwis_daily_climate_v2 (province, date);

-- Refresh planner statistics after a large import so PostgreSQL chooses this index.
ANALYZE public.niwis_daily_climate_v2;
