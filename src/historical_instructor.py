import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from backtest_engine import WalkForwardEngine, aggregate_results
from backtest_validator import BacktestValidator
from position_sizer import PositionSizer
from quant_signals import QuantConsensus

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Outcome of a historical instruction validation run."""

    symbol: str
    passed: bool
    sharpe: float
    max_drawdown_pct: float
    total_return_pct: float
    win_rate: float
    profit_factor: float
    expectancy_r: float
    total_trades: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "passed": self.passed,
            "sharpe": round(self.sharpe, 3),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "total_return_pct": round(self.total_return_pct, 4),
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 3),
            "expectancy_r": round(self.expectancy_r, 4),
            "total_trades": self.total_trades,
            "notes": self.notes,
        }


class HistoricalInstructor:
    """
    Validates century-scale models using the backtest engine.

    Provides both full QuantConsensus walk-forward validation and a fast
    sanity-check baseline (200MA cross) to detect self-agreement bias.
    """

    def __init__(self, db_path: str = "data/trading.db", capital: float = 500.0):
        self.db_path = db_path
        self.capital = capital
        self.consensus = QuantConsensus()
        self.validator = BacktestValidator(db_path=db_path)

    async def run_validation(
        self,
        symbol: str = "SPY",
        min_sharpe: float = 0.5,
        min_profit_factor: float = 1.15,
        min_win_rate: float = 0.45,
    ) -> ValidationResult:
        """Run full QuantConsensus walk-forward validation on *symbol*."""
        logger.info("Instructor: Validating %s against historical regimes...", symbol)

        stats = await self.validator.validate_symbol_overall(symbol, capital=self.capital)
        if "error" in stats:
            return ValidationResult(
                symbol=symbol,
                passed=False,
                sharpe=0.0,
                max_drawdown_pct=0.0,
                total_return_pct=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                expectancy_r=0.0,
                total_trades=0,
                notes=[stats["error"]],
            )

        sharpe = float(stats.get("sharpe", 0.0))
        pf = float(stats.get("profit_factor", 0.0))
        wr = float(stats.get("win_rate", 0.0))
        max_dd = float(stats.get("max_drawdown", 0.0))
        total_trades = int(stats.get("total_trades", 0))
        total_pnl = float(stats.get("total_pnl_usd", 0.0))
        expectancy = float(stats.get("expectancy_net_usd", 0.0))

        total_return_pct = (total_pnl / self.capital) * 100 if self.capital else 0.0

        notes: list[str] = []
        if sharpe < min_sharpe:
            notes.append(f"sharpe {sharpe:.3f} < min {min_sharpe:.3f}")
        if pf < min_profit_factor:
            notes.append(f"profit_factor {pf:.3f} < min {min_profit_factor:.3f}")
        if wr < min_win_rate:
            notes.append(f"win_rate {wr:.2%} < min {min_win_rate:.2%}")
        if total_trades < 10:
            notes.append(f"total_trades {total_trades} < min 10")

        passed = not notes
        result = ValidationResult(
            symbol=symbol,
            passed=passed,
            sharpe=sharpe,
            max_drawdown_pct=max_dd,
            total_return_pct=total_return_pct,
            win_rate=wr,
            profit_factor=pf,
            expectancy_r=expectancy,
            total_trades=total_trades,
            notes=notes,
        )

        logger.info(
            "Instructor: %s validation %s — Sharpe=%.3f PF=%.2f WR=%.1f%% Trades=%d",
            symbol,
            "PASSED" if passed else "FAILED",
            sharpe,
            pf,
            wr * 100,
            total_trades,
        )
        return result

    async def run_sanity_check(self, symbol: str = "SPY") -> ValidationResult:
        """
        Neutral Baseline: 200-SMA crossover.
        If the sophisticated model can't beat a simple 200MA rule,
        it's likely overfit or self-agreeing.
        """
        logger.info("Instructor: Running NEUTRAL sanity check for %s...", symbol)

        df = await self.validator._load_ohlcv(symbol)
        if df is None or len(df) < 210:
            return ValidationResult(
                symbol=symbol,
                passed=False,
                sharpe=0.0,
                max_drawdown_pct=0.0,
                total_return_pct=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                expectancy_r=0.0,
                total_trades=0,
                notes=["insufficient data for 200MA baseline"],
            )

        closes = df["close"].to_numpy()
        sma200 = np.convolve(closes, np.ones(200) / 200, mode="valid")
        aligned_closes = closes[199:]

        trades = []
        position = 0  # 0 = flat, 1 = long
        entry_price = 0.0

        for i in range(1, len(sma200)):
            price = aligned_closes[i]
            prev_price = aligned_closes[i - 1]
            sma = sma200[i]
            prev_sma = sma200[i - 1]

            if position == 0:
                if prev_price < prev_sma and price > sma:
                    position = 1
                    entry_price = price
            elif position == 1:
                if prev_price > prev_sma and price < sma:
                    pnl_pct = (price - entry_price) / entry_price
                    trades.append(pnl_pct)
                    position = 0

        # Close open position at end
        if position == 1:
            pnl_pct = (aligned_closes[-1] - entry_price) / entry_price
            trades.append(pnl_pct)

        if not trades:
            return ValidationResult(
                symbol=symbol,
                passed=False,
                sharpe=0.0,
                max_drawdown_pct=0.0,
                total_return_pct=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                expectancy_r=0.0,
                total_trades=0,
                notes=["200MA baseline generated zero trades"],
            )

        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]
        win_rate = len(wins) / len(trades)
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        pf = gross_win / gross_loss if gross_loss > 0 else 0.0

        equity = np.cumsum(trades)
        peak = np.maximum.accumulate(equity)
        max_dd = float(np.min((equity - peak) / (np.abs(peak) + 1e-10)))

        std = float(np.std(trades)) if len(trades) > 1 else 1e-10
        sharpe = float(np.mean(trades) / std * np.sqrt(252))

        total_return_pct = equity[-1] * 100

        result = ValidationResult(
            symbol=symbol,
            passed=True,
            sharpe=sharpe,
            max_drawdown_pct=max_dd,
            total_return_pct=total_return_pct,
            win_rate=win_rate,
            profit_factor=pf,
            expectancy_r=float(np.mean(trades)),
            total_trades=len(trades),
            notes=["200MA neutral baseline"],
        )

        logger.info(
            "Instructor: %s 200MA baseline — Sharpe=%.3f PF=%.2f WR=%.1f%% Trades=%d",
            symbol,
            sharpe,
            pf,
            win_rate * 100,
            len(trades),
        )
        return result

    async def compare_model_vs_baseline(self, symbol: str = "SPY") -> dict[str, Any]:
        """Run both sophisticated and baseline models and compare."""
        model_result = await self.run_validation(symbol)
        baseline_result = await self.run_sanity_check(symbol)

        comparison = {
            "symbol": symbol,
            "model": model_result.to_dict(),
            "baseline": baseline_result.to_dict(),
            "model_beats_baseline": bool(
                model_result.sharpe > baseline_result.sharpe * 0.8
                and model_result.profit_factor >= baseline_result.profit_factor * 0.9
            ),
        }

        if not comparison["model_beats_baseline"]:
            logger.warning(
                "Instructor: %s sophisticated model UNDERPERFORMS 200MA baseline. "
                "Risk of overfitting or self-agreement bias.",
                symbol,
            )
        else:
            logger.info(
                "Instructor: %s sophisticated model beats 200MA baseline. Edge likely real.",
                symbol,
            )

        return comparison

    def persist_result(self, result: ValidationResult) -> None:
        """Write validation result to SQLite for audit trail."""
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS historical_validations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT,
                    passed INTEGER,
                    sharpe REAL,
                    max_drawdown_pct REAL,
                    total_return_pct REAL,
                    win_rate REAL,
                    profit_factor REAL,
                    expectancy_r REAL,
                    total_trades INTEGER,
                    notes TEXT
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO historical_validations
                (symbol, passed, sharpe, max_drawdown_pct, total_return_pct,
                 win_rate, profit_factor, expectancy_r, total_trades, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.symbol,
                    int(result.passed),
                    result.sharpe,
                    result.max_drawdown_pct,
                    result.total_return_pct,
                    result.win_rate,
                    result.profit_factor,
                    result.expectancy_r,
                    result.total_trades,
                    json.dumps(result.notes),
                ),
            )
            conn.commit()
            cursor.close()
        finally:
            conn.close()


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Sovereign Historical Instructor")
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--db", default="data/trading.db")
    parser.add_argument("--compare", action="store_true", help="Compare model vs 200MA baseline")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    instructor = HistoricalInstructor(db_path=args.db)
    if args.compare:
        result = await instructor.compare_model_vs_baseline(args.symbol)
        print(json.dumps(result, indent=2, default=str))
    else:
        result = await instructor.run_validation(args.symbol)
        print(json.dumps(result.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
