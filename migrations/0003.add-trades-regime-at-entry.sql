-- Migration 0003: Add regime_at_entry column to trades table
-- brain_execution.py _log_trade_entry references pos.regime_at_entry for
-- display purposes; storing it explicitly enables per-regime P&L queries.

ALTER TABLE trades ADD COLUMN regime_at_entry TEXT;
