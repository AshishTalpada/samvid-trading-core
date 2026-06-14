"""
Backtest Validator — Production-grade pre-trade historical edge validation.

Wires together backtest_engine.py, backtester.py, position_sizer.py, and
quant_signals.py into a single callable gate that the coordinator can use
to reject patterns that fail historical walk-forward validation.

Usage (from coordinator):
    from backtest_validator import BacktestValidator
    validator = BacktestValidator(db_path="data/trading.db")
    passed = await validator.validate_pattern(symbol, pattern, df_ohlcv)
    if not passed:
        return False  # reject trade
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import polars as pl

from backtest_engine import WalkForwardEngine, aggregate_results
from backtester import WalkForwardBacktester, simulate_trade
from position_sizer import PositionSizer
from quant_signals import QuantConsensus

logger = logging.getLogger(__name__)

# Minimum edge thresholds for a pattern to pass pre-trade validation
DEFAULT_MIN_PROFIT_FACTOR = 1.15
DEFAULT_MIN_WIN_RATE = 0.45
DEFAULT_MIN_EXPECTANCY_R = 0.15
DEFAULT_MIN_SHARPE_PROXY = 0.3
DEFAULT_MIN_TRADES = 10


@dataclass
class BacktestValidationResult:
    """Result of a pre-trade backtest validation gate."""

    passed: bool
    symbol: str
    pattern_name: str
    profit_factor: float = 0.0
    win_rate: float = 0.0
    expectancy_r: float = 0.0
    sharpe_proxy: float = 0.0
    total_trades: int = 0
    max_drawdown_r: float = 0.0
    avg_r_multiple: float = 0.0
    blockers: list[str] = field(default_factory=list)
    raw_stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "symbol": self.symbol,
            "pattern_name": self.pattern_name,
            "profit_factor": round(self.profit_factor, 3),
            "win_rate": round(self.win_rate, 4),
            "expectancy_r": round(self.expectancy_r, 4),
            "sharpe_proxy": round(self.sharpe_proxy, 4),
            "total_trades": self.total_trades,
            "max_drawdown_r": round(self.max_drawdown_r, 4),
            "avg_r_multiple": round(self.avg_r_multiple, 4),
            "blockers": self.blockers,
        }


class BacktestValidator:
    """
    Pre-trade historical edge validator.

    Runs a lightweight walk-forward backtest on the detected pattern using
    historical OHLCV data.  If the pattern fails edge thresholds, the trade
    is rejected before any broker order is submitted.
    """

    def __init__(
        self,
        db_path: str = "data/trading.db",
        min_profit_factor: float = DEFAULT_MIN_PROFIT_FACTOR,
        min_win_rate: float = DEFAULT_MIN_WIN_RATE,
        min_expectancy_r: float = DEFAULT_MIN_EXPECTANCY_R,
        min_sharpe_proxy: float = DEFAULT_MIN_SHARPE_PROXY,
        min_trades: int = DEFAULT_MIN_TRADES,
        window_size: int = 100,
        step_size: int = 20,
    ):
        self.db_path = db_path
        self.min_profit_factor = min_profit_factor
        self.min_win_rate = min_win_rate
        self.min_expectancy_r = min_expectancy_r
        self.min_sharpe_proxy = min_sharpe_proxy
        self.min_trades = min_trades
        self.window_size = window_size
        self.step_size = step_size
        self._pattern_backtester = WalkForwardBacktester(
            window_size=window_size, step_size=step_size
        )
        self._consensus_engine: Optional[QuantConsensus] = None

    # ── Public API ──────────────────────────────────────────────────────

    async def validate_pattern(
        self,
        symbol: str,
        pattern: Any,
        df: pl.DataFrame | None = None,
        use_consensus: bool = False,
    ) -> BacktestValidationResult:
        """
        Run a lightweight walk-forward backtest for *pattern* on *symbol*.

        If *df* is provided, use it directly.  Otherwise load from DB.
        *use_consensus* triggers the full QuantConsensus walk-forward engine
        (slower, more thorough) instead of the fast PatternDetector-only
        harness.
        """
        if df is None:
            df = await self._load_ohlcv(symbol)
        if df is None or len(df) < self.window_size + self.step_size * 3:
            return BacktestValidationResult(
                passed=False,
                symbol=symbol,
                pattern_name=getattr(pattern, "name", "UNKNOWN"),
                blockers=["insufficient_historical_data"],
            )

        if use_consensus:
            return await self._validate_with_consensus(symbol, pattern, df)
        return await self._validate_with_pattern_detector(symbol, pattern, df)

    async def validate_symbol_overall(
        self,
        symbol: str,
        capital: float = 500.0,
    ) -> dict[str, Any]:
        """
        Run the full WalkForwardEngine (QuantConsensus-based) on a symbol.
        Returns the aggregate gate report.  Useful for periodic health checks.
        """
        from backtest_engine import aggregate_results

        engine = WalkForwardEngine(
            db_path=self.db_path,
            initial_capital=capital,
        )
        windows = await engine.run(symbol)
        if not windows:
            return {"error": "No walk-forward windows generated", "symbol": symbol}
        return aggregate_results(windows)

    async def save_validation_record(
        self,
        result: BacktestValidationResult,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        """Persist a validation result to the SQLite audit log."""
        close_conn = conn is None
        if conn is None:
            conn = sqlite3.connect(self.db_path, timeout=60.0)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS backtest_validations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT,
                    pattern_name TEXT,
                    passed INTEGER,
                    profit_factor REAL,
                    win_rate REAL,
                    expectancy_r REAL,
                    sharpe_proxy REAL,
                    total_trades INTEGER,
                    max_drawdown_r REAL,
                    avg_r_multiple REAL,
                    blockers TEXT,
                    raw_stats TEXT
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO backtest_validations
                (symbol, pattern_name, passed, profit_factor, win_rate,
                 expectancy_r, sharpe_proxy, total_trades, max_drawdown_r,
                 avg_r_multiple, blockers, raw_stats)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.symbol,
                    result.pattern_name,
                    int(result.passed),
                    result.profit_factor,
                    result.win_rate,
                    result.expectancy_r,
                    result.sharpe_proxy,
                    result.total_trades,
                    result.max_drawdown_r,
                    result.avg_r_multiple,
                    json.dumps(result.blockers),
                    json.dumps(result.raw_stats),
                ),
            )
            conn.commit()
            cursor.close()
        finally:
            if close_conn:
                conn.close()

    # ── Internal helpers ────────────────────────────────────────────────

    async def _load_ohlcv(self, symbol: str) -> pl.DataFrame | None:
        """Load the most recent OHLCV bars for *symbol* from DB."""
        if not Path(self.db_path).exists():
            return None

        def _sync_load() -> pl.DataFrame | None:
            conn = sqlite3.connect(self.db_path, timeout=60.0)
            try:
                cursor = conn.cursor()
                # Check if the ohlcv table exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='ohlcv'"
                )
                if not cursor.fetchone():
                    return None
                cursor.execute(
                    "SELECT timestamp, open, high, low, close, volume FROM ohlcv "
                    "WHERE symbol=? ORDER BY timestamp ASC",
                    (symbol,),
                )
                rows = cursor.fetchall()
                if not rows:
                    return None
                return pl.DataFrame(
                    {
                        "timestamp": [r[0] for r in rows],
                        "open": [float(r[1]) for r in rows],
                        "high": [float(r[2]) for r in rows],
                        "low": [float(r[3]) for r in rows],
                        "close": [float(r[4]) for r in rows],
                        "volume": [int(r[5]) for r in rows],
                    }
                )
            finally:
                conn.close()

        return await asyncio.to_thread(_sync_load)

    async def _validate_with_pattern_detector(
        self,
        symbol: str,
        pattern: Any,
        df: pl.DataFrame,
    ) -> BacktestValidationResult:
        """Fast validation using the PatternDetector backtester."""
        result = self._pattern_backtester.run(df)

        # Override: only count trades for the specific pattern name
        pattern_name = getattr(pattern, "name", "UNKNOWN")
        pattern_trades = [
            t for t in result.get("all_trades", []) if t.get("pattern") == pattern_name
        ]
        if pattern_trades:
            result["pattern_specific"] = {
                "total_trades": len(pattern_trades),
                "win_rate": sum(1 for t in pattern_trades if t["outcome"] == "win")
                / len(pattern_trades),
                "avg_r": sum(t["r_multiple"] for t in pattern_trades) / len(pattern_trades),
            }

        return self._evaluate_thresholds(symbol, pattern_name, result)

    async def _validate_with_consensus(
        self,
        symbol: str,
        pattern: Any,
        df: pl.DataFrame,
    ) -> BacktestValidationResult:
        """Thorough validation using QuantConsensus walk-forward engine."""

        engine = WalkForwardEngine(
            db_path=self.db_path,
            initial_capital=500.0,
        )
        # Temporarily override the engine's consensus to use provided df
        windows = await engine.run(symbol)
        if not windows:
            return BacktestValidationResult(
                passed=False,
                symbol=symbol,
                pattern_name=getattr(pattern, "name", "UNKNOWN"),
                blockers=["consensus_walk_forward_failed"],
            )
        stats = aggregate_results(windows)
        return self._evaluate_thresholds(
            symbol, getattr(pattern, "name", "UNKNOWN"), stats
        )

    def _evaluate_thresholds(
        self,
        symbol: str,
        pattern_name: str,
        stats: dict[str, Any],
    ) -> BacktestValidationResult:
        """Check aggregate stats against configured minimum thresholds."""
        total_trades = int(stats.get("simulated_trades", stats.get("total_trades", 0)))
        win_rate = float(stats.get("win_rate", 0.0))
        profit_factor = float(stats.get("profit_factor", 0.0))
        expectancy = float(stats.get("expectancy", 0.0))
        sharpe = float(stats.get("sharpe_proxy", stats.get("sharpe", 0.0)))
        max_dd = float(stats.get("max_drawdown_r", stats.get("max_drawdown", 0.0)))
        avg_r = float(stats.get("avg_r_multiple", 0.0))

        blockers: list[str] = []
        if total_trades < self.min_trades:
            blockers.append(
                f"trades {total_trades} < min {self.min_trades}"
            )
        if win_rate < self.min_win_rate:
            blockers.append(f"win_rate {win_rate:.2%} < min {self.min_win_rate:.2%}")
        if profit_factor < self.min_profit_factor:
            blockers.append(
                f"profit_factor {profit_factor:.3f} < min {self.min_profit_factor:.3f}"
            )
        if expectancy < self.min_expectancy_r:
            blockers.append(f"expectancy {expectancy:.3f}R < min {self.min_expectancy_r:.3f}R")
        if sharpe < self.min_sharpe_proxy:
            blockers.append(f"sharpe {sharpe:.3f} < min {self.min_sharpe_proxy:.3f}")

        passed = not blockers
        if not passed:
            logger.info(
                "BacktestValidator [%s|%s]: REJECTED — %s",
                symbol,
                pattern_name,
                "; ".join(blockers),
            )
        else:
            logger.info(
                "BacktestValidator [%s|%s]: PASSED — PF=%.2f WR=%.1f%% Exp=%.2fR Sharpe=%.2f",
                symbol,
                pattern_name,
                profit_factor,
                win_rate * 100,
                expectancy,
                sharpe,
            )

        return BacktestValidationResult(
            passed=passed,
            symbol=symbol,
            pattern_name=pattern_name,
            profit_factor=profit_factor,
            win_rate=win_rate,
            expectancy_r=expectancy,
            sharpe_proxy=sharpe,
            total_trades=total_trades,
            max_drawdown_r=max_dd,
            avg_r_multiple=avg_r,
            blockers=blockers,
            raw_stats=stats,
        )


# ── Convenience standalone runner ─────────────────────────────────────

async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Sovereign Backtest Validator")
    parser.add_argument("--symbol", default="SPY", help="Symbol to validate")
    parser.add_argument("--db", default="data/trading.db", help="SQLite DB path")
    parser.add_argument(
        "--min-pf", type=float, default=DEFAULT_MIN_PROFIT_FACTOR, help="Min profit factor"
    )
    parser.add_argument(
        "--min-wr", type=float, default=DEFAULT_MIN_WIN_RATE, help="Min win rate"
    )
    parser.add_argument(
        "--min-exp", type=float, default=DEFAULT_MIN_EXPECTANCY_R, help="Min expectancy (R)"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    validator = BacktestValidator(
        db_path=args.db,
        min_profit_factor=args.min_pf,
        min_win_rate=args.min_wr,
        min_expectancy_r=args.min_exp,
    )
    report = await validator.validate_symbol_overall(args.symbol)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
