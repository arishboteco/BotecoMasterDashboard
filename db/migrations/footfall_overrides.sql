-- Footfall override table — manual Lunch/Dinner cover entries by outlet+date.
-- Created and read by repositories/footfall_override_repository.py and
-- services/footfall_override_service.py. Survives POS Dynamic Report
-- re-uploads because override rows live outside daily_summary.
--
-- Apply this once in the Supabase SQL editor for any project that runs the
-- BotecoMasterDashboard against Supabase. SQLite installs run the equivalent
-- DDL automatically via database.init_database().

CREATE TABLE IF NOT EXISTS footfall_overrides (
    id            BIGSERIAL PRIMARY KEY,
    location_id   BIGINT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    date          DATE NOT NULL,
    lunch_covers  INTEGER,
    dinner_covers INTEGER,
    note          TEXT,
    edited_by     TEXT,
    edited_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (location_id, date)
);

CREATE INDEX IF NOT EXISTS idx_footfall_overrides_loc_date
    ON footfall_overrides (location_id, date);
