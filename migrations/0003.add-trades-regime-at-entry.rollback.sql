-- Rollback for migration 0003: Remove regime_at_entry column from trades
-- Requires SQLite >= 3.35.0 (DROP COLUMN support).

ALTER TABLE trades DROP COLUMN regime_at_entry;
