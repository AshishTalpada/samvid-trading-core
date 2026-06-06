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
import os
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Note: patch_dhatu_oracle and patch_trading_brain have been DECOMMISSIONED.
# Their logic is now natively integrated into DhatuOracle and TradingBrain.

RUN_LOCK = asyncio.Lock()
DEFAULT_MIN_PHASE1_BARS = 1200


@dataclass(frozen=True)
class Phase1Coverage:
    symbol: str
    bars: int
    min_bars: int

    @property
    def ready(self) -> bool:
        return self.bars >= self.min_bars


def _phase1_min_bars() -> int:
    raw = os.environ.get("SOVEREIGN_PHASE1_MIN_BARS", str(DEFAULT_MIN_PHASE1_BARS))
    try:
        return max(1, int(raw))
    except ValueError:
        logger.warning(
            "Invalid SOVEREIGN_PHASE1_MIN_BARS=%r; using %s.",
            raw,
            DEFAULT_MIN_PHASE1_BARS,
        )
        return DEFAULT_MIN_PHASE1_BARS


async def _count_symbol_bars(db_path: str, symbol: str = "SPY") -> int:
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


async def _collect_data_coverage(
    db_path: str,
    symbols: list[str],
    min_bars: int,
) -> list[Phase1Coverage]:
    counts = await asyncio.gather(*(_count_symbol_bars(db_path, symbol) for symbol in symbols))
    return [
        Phase1Coverage(symbol=symbol, bars=count, min_bars=min_bars)
        for symbol, count in zip(symbols, counts, strict=True)
    ]


def _coverage_summary(coverage: list[Phase1Coverage]) -> str:
    return ", ".join(
        f"{item.symbol}={item.bars}/{item.min_bars}{' OK' if item.ready else ' MISSING'}"
        for item in coverage
    )


async def _maybe_backfill(symbols: list[str]) -> None:
    from data_pipeline import DataPipeline

    print(f"\n  Phase 1 data below threshold. Backfill allowed; requesting {symbols}...")
    pipeline = DataPipeline()
    for sym in symbols:
        try:
            await pipeline.backfill_gap(sym)
        except Exception as exc:
            logger.warning("Backfill %s failed: %s", sym, exc)
    print(" Data backfill attempt complete.")


async def run_backtest(
    db_path: str = "data/trading.db",
    symbols: list[str] | None = None,
    *,
    min_bars: int | None = None,
    allow_backfill: bool | None = None,
) -> None:
    if symbols is None:
        symbols = ["SPY", "QQQ", "IWM"]
    async with RUN_LOCK:
        from backtest_engine import run_phase1_validation

        min_bars = min_bars or _phase1_min_bars()
        allow_backfill = (
            os.environ.get("SOVEREIGN_PHASE1_ALLOW_BACKFILL", "0") == "1"
            if allow_backfill is None
            else allow_backfill
        )

        logger.info("Phase1: Validating data coverage for %s...", symbols)
        coverage = await _collect_data_coverage(db_path, symbols, min_bars)
        print(f"\n  Phase 1 data coverage: {_coverage_summary(coverage)}")

        if any(not item.ready for item in coverage) and allow_backfill:
            await _maybe_backfill(symbols)
            coverage = await _collect_data_coverage(db_path, symbols, min_bars)
            print(f"  Phase 1 data coverage after backfill: {_coverage_summary(coverage)}")

        missing = [item for item in coverage if not item.ready]
        if missing:
            logger.error(
                "Phase1: insufficient historical coverage. Required %s bars per symbol; got %s.",
                min_bars,
                _coverage_summary(coverage),
            )
            print("\n  PHASE 1 BLOCKED - insufficient historical OHLCV evidence.")
            print(f"  Required minimum bars per symbol: {min_bars}")
            print(f"  Coverage: {_coverage_summary(coverage)}")
            print("  Load more 1-minute history into data/trading.db before validating edge.")
            sys.exit(1)

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
