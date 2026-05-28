-- Rollback for migration 0001: Drop all core trading system tables
-- Applied in reverse order to respect any implicit dependencies.

DROP INDEX IF EXISTS idx_signals_symbol_time;
DROP INDEX IF EXISTS idx_dhatu_readings_ts;
DROP INDEX IF EXISTS idx_system_events_ts;
DROP INDEX IF EXISTS idx_ohlcv_sym_tf;
DROP INDEX IF EXISTS idx_trades_inst;
DROP INDEX IF EXISTS idx_trades_ts;

DROP TABLE IF EXISTS agent_d_trades;
DROP TABLE IF EXISTS news;
DROP TABLE IF EXISTS vix_data;
DROP TABLE IF EXISTS ohlcv;
DROP TABLE IF EXISTS brain_optimization;
DROP TABLE IF EXISTS decision_snapshots;
DROP TABLE IF EXISTS performance_summary;
DROP TABLE IF EXISTS positions;
DROP TABLE IF EXISTS dhatu_readings;
DROP TABLE IF EXISTS system_events;
DROP TABLE IF EXISTS calibration_log;
DROP TABLE IF EXISTS signals;
DROP TABLE IF EXISTS trades;
DROP TABLE IF EXISTS system_state;
