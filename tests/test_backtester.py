"""
Tests for backtester.py — PatternDetector walk-forward backtest harness.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from backtester import (
    WalkForwardBacktester,
    generate_ohlcv,
    load_ohlcv_from_db,
    run_walk_forward,
    simulate_trade,
    simulate_trade_with_sizing,
)


class FakePattern:
    """Minimal stand-in for a Pattern object returned by PatternDetector."""

    def __init__(self, name="BullFlag", confidence=75.0, direction="long"):
        self.name = name
        self.confidence = confidence
        self.entry = 100.0
        self.stop = 98.0
        self.target = 104.0
        self.direction = direction
        self.r_r_ratio = 2.0


class TestGenerateOhlcv:
    def test_generates_expected_columns(self):
        df = generate_ohlcv(n_bars=100, seed=42)
        assert set(df.columns) == {"timestamp", "open", "high", "low", "close", "volume"}
        assert len(df) == 100
        assert df["high"].to_list()[0] >= df["low"].to_list()[0]

    def test_seed_reproducibility(self):
        df1 = generate_ohlcv(n_bars=100, seed=123)
        df2 = generate_ohlcv(n_bars=100, seed=123)
        assert df1["close"].to_list() == df2["close"].to_list()


class TestSimulateTrade:
    def test_long_win(self):
        df = pl.DataFrame(
            {
                "timestamp": [1, 2, 3, 4],
                "open": [100, 100, 100, 100],
                "high": [100, 100, 105, 105],
                "low": [100, 99, 99, 99],
                "close": [100, 100, 105, 105],
                "volume": [1000, 1000, 1000, 1000],
            }
        )
        result = simulate_trade(df, signal_idx=0, entry=100, stop=98, target=104, direction="long")
        assert result["outcome"] == "win"
        assert result["r_multiple"] > 0

    def test_long_loss(self):
        df = pl.DataFrame(
            {
                "timestamp": [1, 2, 3, 4],
                "open": [100, 100, 100, 100],
                "high": [100, 100, 100, 100],
                "low": [100, 97, 97, 97],
                "close": [100, 97, 97, 97],
                "volume": [1000, 1000, 1000, 1000],
            }
        )
        result = simulate_trade(df, signal_idx=0, entry=100, stop=98, target=104, direction="long")
        assert result["outcome"] == "loss"
        assert result["r_multiple"] < 0

    def test_invalid_risk(self):
        df = pl.DataFrame({"timestamp": [1], "open": [100], "high": [100], "low": [100], "close": [100], "volume": [1]})
        result = simulate_trade(df, signal_idx=0, entry=100, stop=100, target=104)
        assert result["outcome"] == "invalid"


class TestSimulateTradeWithSizing:
    def test_returns_shares_and_notional(self):
        df = pl.DataFrame(
            {
                "timestamp": [1, 2, 3, 4],
                "open": [100, 100, 100, 100],
                "high": [100, 100, 105, 105],
                "low": [100, 99, 99, 99],
                "close": [100, 100, 105, 105],
                "volume": [1000, 1000, 1000, 1000],
            }
        )
        result = simulate_trade_with_sizing(
            df, signal_idx=0, entry=100, stop=98, target=104, direction="long", equity=500.0, risk_pct=0.01
        )
        assert "shares" in result
        assert "notional" in result
        assert result["shares"] > 0
        assert result["notional"] > 0


class TestWalkForwardBacktester:
    def test_run_on_synthetic_data(self):
        df = generate_ohlcv(n_bars=500, seed=42)
        bt = WalkForwardBacktester(window_size=100, step_size=20)
        result = bt.run(df)
        assert "total_signals" in result
        assert "simulated_trades" in result
        assert "win_rate" in result
        assert "avg_r_multiple" in result
        assert "expectancy" in result
        assert "sharpe_proxy" in result
        assert "profit_factor" in result
        assert "max_drawdown_r" in result
        assert "patterns_found" in result

    def test_empty_df(self):
        df = pl.DataFrame(
            {"timestamp": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
        )
        bt = WalkForwardBacktester(window_size=10, step_size=5)
        result = bt.run(df)
        assert result["simulated_trades"] == 0
        assert result["win_rate"] == 0.0


class TestLoadOhlcvFromDb:
    def test_loads_existing_table(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE ohlcv (timestamp TEXT, symbol TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER)"
            )
            # Insert a row for a different symbol — SPY query should return None
            conn.execute(
                "INSERT INTO ohlcv VALUES ('2024-01-01', 'QQQ', 100, 101, 99, 100.5, 1000)"
            )
            conn.commit()
            conn.close()

            df = load_ohlcv_from_db(db_path, "SPY")
            assert df is None  # no rows for SPY

            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO ohlcv VALUES ('2024-01-01', 'SPY', 100, 101, 99, 100.5, 1000)"
            )
            conn.commit()
            conn.close()

            df = load_ohlcv_from_db(db_path, "SPY")
            assert df is not None
            assert len(df) == 1
            assert df["close"][0] == 100.5
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_returns_none_when_table_missing(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            df = load_ohlcv_from_db(db_path, "SPY")
            assert df is None
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestRunWalkForward:
    def test_convenience_function(self):
        result = run_walk_forward(n_bars=300, window_size=60, step_size=15, seed=7)
        assert result["total_signals"] >= 0
        assert result["simulated_trades"] >= 0
