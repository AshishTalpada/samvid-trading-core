# Agent Reference — Unified Trading System V3.0

## Build / Verification Commands

```bash
# Run all tests
python -m pytest tests/ -q --tb=short

# Run specific test modules
python -m pytest tests/test_risk_invariants.py tests/test_dms.py -v

# Ruff lint check
python -m ruff check src/

# Startup validation (dry-run system health check)
python scripts/startup_validation.py

# Live startup test (25s timeout)
rm -f data/main.pid data/watchdog.pid && timeout 25 python src/main.py
```

## Critical Architecture Notes

- **Entry point**: `python src/main.py`
- **Main orchestrator**: `src/brain.py` (TradingBrain)
- **State primitives**: `src/brain_state.py` (DrawdownLadder, ConsecutiveLossTracker, MorningBudget, TokenBucketRateLimiter)
- **Pattern detection**: `src/agent_a.py` (uses Polars DataFrames — NOT pandas)
- **Position sizing**: `src/agent_c_ibkr.py` (F6 8-step chain, called from `src/coordinator.py`)
- **Exit intelligence**: `src/exit_intelligence.py` (7-level priority engine)
- **Black Swan circuit**: `src/agent_c_ibkr.py` BlackSwanProtocol, wired into `brain.py::_scan_symbol`

## Broker Connections

- **IBKR**: Paper mode by default (`TRADING_MODE=ibkr_paper`). Connects to TWS/Gateway at 127.0.0.1:7497.
- **MT5**: Optional. Disabled if `MT5_LOGIN` is missing or placeholder.

## Singleton Lock

- PID file at `data/main.pid`
- Stale PID detection uses `psutil.pid_exists()` + cmdline matching
- Override for tests: `SOVEREIGN_SKIP_PID_CHECK=1`

## Recent Critical Fixes (2026-05-27)

1. **Drawdown modifier clamp**: `max(0.8, ...)` → `min(max(..., 0.5), 1.5)` (was preventing risk reduction)
2. **Polars indexing**: Fixed 95 instances of pandas-style `df['close'][-1]` in `agent_a.py`
3. **H&S peak sorting**: Sort by time index `x[0]` instead of price height `x[1]`
4. **Warm-slot safety**: Removed live `$0.01` IBKR orders; internal tracking only
5. **Black Swan wiring**: `BlackSwanProtocol.check()` now halts new trade discovery in `_scan_symbol`
6. **Win-streak cap**: Capped at `1.15x` (was uncapped up to `2.0x`)
7. **Drawdown scaling**: Accounts under `$2K` get compressed thresholds
8. **Sector mapping**: Replaced broken `symbol[:2]` with real `SECTOR_MAP` (80+ tickers)
9. **brain_state.py extraction**: Removed 355 lines from `brain.py` into dedicated module
10. **Advisory agents wired**: ContrarianAgent, ChaosAgent, ContagionSentinel, AuditAgent initialized in Brain

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `TRADING_MODE` | `paper`, `ibkr_paper`, or `live` |
| `ALLOW_FORCE_LIVE` | `1` to permit live mode |
| `SOVEREIGN_SKIP_PID_CHECK` | `1` to bypass singleton lock (tests only) |
| `SOVEREIGN_TVNEWS_AFTER_HOURS` | `1` to force TVNewsScent when market closed |
| `SOVEREIGN_AFTER_HOURS_FULL_BACKFILL` | `1` for full backfill instead of compact mode |
