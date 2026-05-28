-- Migration 0002: Add key/value/updated_at columns to performance_summary
-- These columns were added ad-hoc via ALTER TABLE in database/schema.py
-- (ensure_runtime_telemetry_schema). This migration makes them declarative.

-- SQLite does not support IF NOT EXISTS on ALTER TABLE, so we use a guard:
-- yoyo will only run this once thanks to its migration tracking table.
ALTER TABLE performance_summary ADD COLUMN key TEXT;
ALTER TABLE performance_summary ADD COLUMN value TEXT;
ALTER TABLE performance_summary ADD COLUMN updated_at TIMESTAMP;
