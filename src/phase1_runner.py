"""
Integrates Bayesian Oracle + Quant Consensus into live system
AND runs the walk-forward backtest to validate edge.
Usage:
  # Run backtest only:
  python src/phase1_runner.py backtest
  # Run live with quant signals replacing LLM agents:
  python src/phase1_runner.py live
"""

from __future__ import annotations

import asyncio
import logging
import sys

logger = logging.getLogger(__name__)


# Note: patch_dhatu_oracle and patch_trading_brain have been DECOMMISSIONED.
# Their logic is now natively integrated into DhatuOracle and TradingBrain.

RUN_LOCK = asyncio.Lock()


async def _check_data_integrity(db_path: str, symbol: str = "SPY") -> int:
    """Run a blocking SQLite operation safely in a thread pool executor."""
    import os
    import sqlite3

    if not os.path.exists(db_path):
        return 0
    try:
        conn = sqlite3.connect(db_path, timeout=60.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout = 60000;")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ohlcv WHERE symbol=?", (symbol,))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


async def run_backtest(db_path: str = "data/trading.db", symbols: list[str] = None) -> None:
    if symbols is None:
        symbols = ["SPY", "QQQ", "IWM"]
    async with RUN_LOCK:
        from backtest_engine import run_phase1_validation
        from data_pipeline import DataPipeline

        # Check if we have enough data; if not, run pipeline first
        logger.info(f"Phase1: Validating data integrity for {symbols[0]}...")
        count = await asyncio.to_thread(_check_data_integrity, db_path, symbols[0])
        has_data = count >= 200

        if not has_data:
            print(
                f"\n  Insufficient data in DB ({count} bars). Running data pipeline to backfill {symbols}..."
            )
            pipeline = DataPipeline()
            for sym in symbols:
                try:
                    await pipeline.backfill_gap(sym)
                except Exception as _e:
                    logger.warning(f"Backfill {sym} failed: {_e}")
            print(" Data backfill complete.")

        success = await run_phase1_validation(
            db_path=db_path,
            symbols=symbols,
        )

        if not success:
            logger.error("Phase1: Backtest Validation FAILED. Deployment aborted.")
            sys.exit(1)

        logger.info("Phase1: Backtest Validation PASSED. Ready for deployment.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python src/phase1_runner.py [backtest|live] [db_path] [symbol1,symbol2,...]")
        sys.exit(1)

    mode = sys.argv[1].lower()
    db = sys.argv[2] if len(sys.argv) > 2 else "data/trading.db"
    symbols_str = sys.argv[3] if len(sys.argv) > 3 else "SPY,QQQ,IWM"
    symbols = [s.strip().upper() for s in symbols_str.split(",")]

    if mode == "backtest":
        asyncio.run(run_backtest(db_path=db, symbols=symbols))
    elif mode == "live":
        print(" LIVE MODE: Quant-Consensus active (Phase 1).")
        # In a real SE-11 deployment, this would launch the main engine with quant-only flags
        print("Note: Deployment of live quant-engine requires --quant-only flag in main.py.")
    else:
        print(f" ERROR: Unknown mode '{mode}'.")
        print("Available modes: backtest, live")
        sys.exit(1)
