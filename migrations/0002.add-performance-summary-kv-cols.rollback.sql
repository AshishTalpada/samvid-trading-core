-- Rollback for migration 0002: Remove key/value/updated_at columns from performance_summary
-- Requires SQLite >= 3.35.0 (DROP COLUMN support).

ALTER TABLE performance_summary DROP COLUMN updated_at;
ALTER TABLE performance_summary DROP COLUMN value;
ALTER TABLE performance_summary DROP COLUMN key;
