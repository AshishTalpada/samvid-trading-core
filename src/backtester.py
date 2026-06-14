"""
src/backtester.py
Walk-Forward Backtester — validates PatternDetector signal quality.

Generates synthetic but realistic OHLCV bars and runs the actual
PatternDetector.detect_all() on rolling windows to measure:
  - Signal frequency
  - Simulated win rate (price hits target before stop)
  - Average R-multiple
  - Expectancy

Usage:
    python src/backtester.py           # quick 500-bar test
    python src/backtester.py --bars 2000  # full walk-forward
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import polars as pl

# Allow running as a script or as an imported module
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def generate_ohlcv(
    n_bars: int = 500,
    seed: int = 42,
    trend_strength: float = 0.0002,
    volatility: float = 0.012,
    start_price: float = 450.0,
) -> pl.DataFrame:
    """
    Generate synthetic OHLCV data with a mild upward trend and realistic noise.
    Volume follows log-normal distribution.  ATR ≈ volatility × price.
    """
    rng = np.random.default_rng(seed)
    prices = [start_price]
    for _ in range(n_bars - 1):
        ret = trend_strength + rng.normal(0, volatility)
        prices.append(max(prices[-1] * (1 + ret), 1.0))

    opens, highs, lows, closes, volumes = [], [], [], [], []
    for i, close in enumerate(prices):
        spread = close * volatility * rng.uniform(0.5, 1.5)
        open_ = close * (1 + rng.normal(0, volatility * 0.3))
        high = max(close, open_) + abs(rng.normal(0, spread))
        low = min(close, open_) - abs(rng.normal(0, spread))
        vol = int(rng.lognormal(15, 0.8))
        opens.append(round(open_, 4))
        highs.append(round(high, 4))
        lows.append(round(low, 4))
        closes.append(round(close, 4))
        volumes.append(vol)

    from datetime import datetime, timedelta

    import polars as pl

    base_dt = datetime(2024, 1, 1, 9, 30)
    timestamps = [base_dt + timedelta(minutes=i) for i in range(n_bars)]

    return pl.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


def simulate_trade(
    df: pl.DataFrame,
    signal_idx: int,
    entry: float,
    stop: float,
    target: float,
    direction: str = "long",
    max_bars: int = 50,
) -> dict:
    """
    Simulate a trade from signal_idx forward.
    Returns dict with outcome, r_multiple, bars_held.
    """
    risk = abs(entry - stop)
    if risk <= 0:
        return {"outcome": "invalid", "r_multiple": 0.0, "bars_held": 0}

    for offset in range(1, min(max_bars + 1, len(df) - signal_idx)):
        bar_idx = signal_idx + offset
        row_high = df["high"][bar_idx]
        row_low = df["low"][bar_idx]

        if direction == "long":
            if row_low <= stop:
                r = (stop - entry) / risk  # negative
                return {"outcome": "loss", "r_multiple": round(r, 3), "bars_held": offset}
            if row_high >= target:
                r = (target - entry) / risk  # positive
                return {"outcome": "win", "r_multiple": round(r, 3), "bars_held": offset}
        else:  # short
            if row_high >= stop:
                r = (entry - stop) / risk
                return {"outcome": "loss", "r_multiple": round(-r, 3), "bars_held": offset}
            if row_low <= target:
                r = (entry - target) / risk
                return {"outcome": "win", "r_multiple": round(r, 3), "bars_held": offset}

    # Expired without hitting either level
    last_close = df["close"][signal_idx + min(max_bars, len(df) - signal_idx - 1)]
    if direction == "long":
        r = (last_close - entry) / risk
    else:
        r = (entry - last_close) / risk
    return {"outcome": "timeout", "r_multiple": round(r, 3), "bars_held": max_bars}


class WalkForwardBacktester:
    """
    Walk-Forward Backtester using real PatternDetector.
    Runs detect_all() on each window of real-ish OHLCV bars.
    """

    def __init__(self, window_size: int = 100, step_size: int = 20):
        self.window_size = window_size
        self.step_size = step_size

    def run(self, df: pl.DataFrame) -> dict:
        """
        Walk forward through df, running PatternDetector on each window.
        Returns aggregate statistics.
        """
        from agent_a import PatternDetector

        detector = PatternDetector()
        all_trades: list[dict] = []
        signal_count = 0

        n = len(df)
        for start in range(0, n - self.window_size, self.step_size):
            window = df.slice(start, self.window_size)
            try:
                patterns = detector.detect_all(window)
            except Exception as exc:
                logger.debug("PatternDetector error on window %d: %s", start, exc)
                continue

            for p in patterns:
                if p is None or p.confidence < 60.0:
                    continue
                signal_count += 1
                signal_bar = start + self.window_size - 1
                if signal_bar + 1 >= n:
                    continue
                direction = "long" if getattr(p, "direction", "long") in ("long", "BUY", "buy") else "short"
                result = simulate_trade(df, signal_bar, p.entry, p.stop, p.target, direction)
                result["pattern"] = p.name
                result["confidence"] = p.confidence
                result["r_r_ratio"] = getattr(p, "r_r_ratio", 0.0)
                all_trades.append(result)

        if not all_trades:
            return {
                "total_signals": signal_count,
                "simulated_trades": 0,
                "win_rate": 0.0,
                "avg_r_multiple": 0.0,
                "expectancy": 0.0,
                "sharpe_proxy": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_r": 0.0,
                "patterns_found": [],
            }

        wins = [t for t in all_trades if t["outcome"] == "win"]
        losses = [t for t in all_trades if t["outcome"] == "loss"]
        total = len(all_trades)
        win_rate = len(wins) / total if total > 0 else 0.0
        r_multiples = [t["r_multiple"] for t in all_trades]
        avg_r = sum(r_multiples) / total if total else 0.0
        expectancy = win_rate * (sum(t["r_multiple"] for t in wins) / max(len(wins), 1)) - \
                     (1 - win_rate) * abs(sum(t["r_multiple"] for t in losses) / max(len(losses), 1))

        std_r = float(np.std(r_multiples)) if len(r_multiples) > 1 else 1.0
        sharpe_proxy = avg_r / std_r if std_r > 0 else 0.0

        # Profit factor (gross win R / gross loss R) and peak-to-trough drawdown in R units,
        # measured on the cumulative R equity curve so the synthetic harness reports the
        # same risk metric (max drawdown) the live edge-validation engine does.
        gross_win_r = sum(r for r in r_multiples if r > 0)
        gross_loss_r = abs(sum(r for r in r_multiples if r < 0))
        profit_factor = gross_win_r / gross_loss_r if gross_loss_r > 0 else 0.0
        equity_curve = np.cumsum(r_multiples)
        running_peak = np.maximum.accumulate(equity_curve)
        max_drawdown_r = float(np.min(equity_curve - running_peak)) if len(equity_curve) else 0.0

        pattern_counts: dict[str, int] = {}
        for t in all_trades:
            pattern_counts[t["pattern"]] = pattern_counts.get(t["pattern"], 0) + 1

        return {
            "total_signals": signal_count,
            "simulated_trades": total,
            "win_rate": round(win_rate, 4),
            "avg_r_multiple": round(avg_r, 4),
            "expectancy": round(expectancy, 4),
            "sharpe_proxy": round(sharpe_proxy, 4),
            "profit_factor": round(profit_factor, 4),
            "max_drawdown_r": round(max_drawdown_r, 4),
            "patterns_found": sorted(pattern_counts.items(), key=lambda x: -x[1]),
        }


def run_walk_forward(
    n_bars: int = 500,
    window_size: int = 100,
    step_size: int = 20,
    seed: int = 42,
) -> dict:
    """Convenience function for tests and CLI."""
    df = generate_ohlcv(n_bars=n_bars, seed=seed)
    bt = WalkForwardBacktester(window_size=window_size, step_size=step_size)
    return bt.run(df)


def load_ohlcv_from_db(db_path: str, symbol: str) -> pl.DataFrame | None:
    """Load real OHLCV bars for *symbol* from a SQLite database."""
    import sqlite3
    from pathlib import Path

    if not Path(db_path).exists():
        logger.warning("Backtester: DB %s not found", db_path)
        return None
    conn = sqlite3.connect(db_path, timeout=60.0)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ohlcv'"
        )
        if not cursor.fetchone():
            logger.warning("Backtester: 'ohlcv' table missing in %s", db_path)
            return None
        cursor.execute(
            "SELECT timestamp, open, high, low, close, volume FROM ohlcv "
            "WHERE symbol=? ORDER BY timestamp ASC",
            (symbol,),
        )
        rows = cursor.fetchall()
        if not rows:
            logger.warning("Backtester: no OHLCV rows for %s", symbol)
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


def run_with_real_data(
    db_path: str,
    symbol: str,
    window_size: int = 100,
    step_size: int = 20,
) -> dict | None:
    """Run the PatternDetector walk-forward backtest on real DB data."""
    df = load_ohlcv_from_db(db_path, symbol)
    if df is None:
        return None
    bt = WalkForwardBacktester(window_size=window_size, step_size=step_size)
    return bt.run(df)


def simulate_trade_with_sizing(
    df: pl.DataFrame,
    signal_idx: int,
    entry: float,
    stop: float,
    target: float,
    direction: str = "long",
    equity: float = 500.0,
    risk_pct: float = 0.01,
    max_bars: int = 50,
) -> dict:
    """
    Simulate a trade with realistic PositionSizer sizing.
    Returns the same dict as simulate_trade() plus 'shares' and 'notional'.
    """
    from position_sizer import PositionSizer

    risk = abs(entry - stop)
    if risk <= 0:
        return {
            "outcome": "invalid",
            "r_multiple": 0.0,
            "bars_held": 0,
            "shares": 0,
            "notional": 0.0,
        }

    shares = PositionSizer.size_trade(
        equity=equity,
        risk_pct=risk_pct,
        entry=entry,
        stop=stop,
    )
    notional = shares * entry

    for offset in range(1, min(max_bars + 1, len(df) - signal_idx)):
        bar_idx = signal_idx + offset
        row_high = df["high"][bar_idx]
        row_low = df["low"][bar_idx]

        if direction == "long":
            if row_low <= stop:
                r = (stop - entry) / risk
                return {
                    "outcome": "loss",
                    "r_multiple": round(r, 3),
                    "bars_held": offset,
                    "shares": shares,
                    "notional": round(notional, 2),
                }
            if row_high >= target:
                r = (target - entry) / risk
                return {
                    "outcome": "win",
                    "r_multiple": round(r, 3),
                    "bars_held": offset,
                    "shares": shares,
                    "notional": round(notional, 2),
                }
        else:  # short
            if row_high >= stop:
                r = (entry - stop) / risk
                return {
                    "outcome": "loss",
                    "r_multiple": round(-r, 3),
                    "bars_held": offset,
                    "shares": shares,
                    "notional": round(notional, 2),
                }
            if row_low <= target:
                r = (entry - target) / risk
                return {
                    "outcome": "win",
                    "r_multiple": round(r, 3),
                    "bars_held": offset,
                    "shares": shares,
                    "notional": round(notional, 2),
                }

    # Expired
    last_close = df["close"][signal_idx + min(max_bars, len(df) - signal_idx - 1)]
    if direction == "long":
        r = (last_close - entry) / risk
    else:
        r = (entry - last_close) / risk
    return {
        "outcome": "timeout",
        "r_multiple": round(r, 3),
        "bars_held": max_bars,
        "shares": shares,
        "notional": round(notional, 2),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sovereign Walk-Forward Backtester")
    parser.add_argument("--bars", type=int, default=500, help="Number of synthetic bars")
    parser.add_argument("--window", type=int, default=100, help="Detection window size")
    parser.add_argument("--step", type=int, default=20, help="Step size between windows")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--db", type=str, default="", help="SQLite DB path for real data")
    parser.add_argument("--symbol", type=str, default="SPY", help="Symbol when using --db")
    args = parser.parse_args()

    if args.db:
        print(
            f"Running walk-forward backtest on REAL data: {args.symbol} "
            f"from {args.db} (window={args.window}, step={args.step})"
        )
        results = run_with_real_data(args.db, args.symbol, args.window, args.step)
        if results is None:
            print("No data available. Aborting.")
            raise SystemExit(1)
    else:
        print(
            f"Running walk-forward backtest: {args.bars} bars, "
            f"window={args.window}, step={args.step}"
        )
        results = run_walk_forward(args.bars, args.window, args.step, args.seed)

    print("\n=== BACKTEST RESULTS ===")
    print(f"  Total signals detected : {results['total_signals']}")
    print(f"  Simulated trades       : {results['simulated_trades']}")
    print(f"  Win rate               : {results['win_rate']:.1%}")
    print(f"  Avg R-multiple         : {results['avg_r_multiple']:+.3f}R")
    print(f"  Expectancy             : {results['expectancy']:+.3f}R/trade")
    print(f"  Sharpe proxy           : {results['sharpe_proxy']:+.3f}")
    print(f"  Profit factor          : {results['profit_factor']:.3f}")
    print(f"  Max drawdown           : {results['max_drawdown_r']:+.3f}R")
    if results["patterns_found"]:
        print("\n  Top patterns by signal count:")
        for name, count in results["patterns_found"][:5]:
            print(f"    {name}: {count}")
    print()
