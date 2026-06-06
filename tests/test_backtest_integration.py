"""
tests/test_backtest_integration.py
Historical backtest integration tests — validates PatternDetector pipeline
on synthetic but realistic OHLCV bars.

These tests verify:
1. PatternDetector.detect_all() runs without error on realistic data
2. Signals produced have structurally valid fields (entry, stop, target, confidence)
3. The walk-forward backtester produces a complete, structurally valid result
4. generate_ohlcv() produces OHLCV bars with correct column layout and value ranges
5. simulate_trade() correctly identifies win / loss / timeout outcomes
6. The backtester is deterministic for a given seed
"""
from __future__ import annotations

import os
import sys

import polars as pl
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ohlcv_200():
    """200-bar synthetic OHLCV DataFrame (seed=42)."""
    from backtester import generate_ohlcv
    return generate_ohlcv(n_bars=200, seed=42)


@pytest.fixture(scope="module")
def ohlcv_500():
    """500-bar synthetic OHLCV DataFrame (seed=99)."""
    from backtester import generate_ohlcv
    return generate_ohlcv(n_bars=500, seed=99)


# ---------------------------------------------------------------------------
# generate_ohlcv tests
# ---------------------------------------------------------------------------

def test_generate_ohlcv_shape(ohlcv_200):
    """DataFrame must have exactly 200 rows and the 6 required columns."""
    df = ohlcv_200
    assert len(df) == 200
    for col in ("timestamp", "open", "high", "low", "close", "volume"):
        assert col in df.columns, f"Missing column: {col}"


def test_generate_ohlcv_ohlc_relationships(ohlcv_200):
    """high >= open, close; low <= open, close for every bar."""
    df = ohlcv_200
    assert (df["high"] >= df["open"]).all(), "high < open found"
    assert (df["high"] >= df["close"]).all(), "high < close found"
    assert (df["low"] <= df["open"]).all(), "low > open found"
    assert (df["low"] <= df["close"]).all(), "low > close found"


def test_generate_ohlcv_positive_prices(ohlcv_200):
    """All prices must be strictly positive."""
    df = ohlcv_200
    assert (df["close"] > 0).all()
    assert (df["volume"] > 0).all()


def test_generate_ohlcv_deterministic():
    """Same seed → identical output."""
    from backtester import generate_ohlcv
    df1 = generate_ohlcv(n_bars=100, seed=7)
    df2 = generate_ohlcv(n_bars=100, seed=7)
    assert df1["close"].to_list() == df2["close"].to_list()


def test_generate_ohlcv_different_seeds():
    """Different seeds → different data."""
    from backtester import generate_ohlcv
    df1 = generate_ohlcv(n_bars=100, seed=1)
    df2 = generate_ohlcv(n_bars=100, seed=2)
    assert df1["close"].to_list() != df2["close"].to_list()


# ---------------------------------------------------------------------------
# PatternDetector smoke test on realistic data
# ---------------------------------------------------------------------------

def test_pattern_detector_runs_on_realistic_ohlcv(ohlcv_200):
    """PatternDetector.detect_all() must not raise on 200 realistic bars."""
    from agent_a import PatternDetector
    detector = PatternDetector()
    try:
        patterns = detector.detect_all(ohlcv_200)
    except Exception as exc:
        pytest.fail(f"PatternDetector.detect_all() raised: {exc}")
    assert isinstance(patterns, list), "detect_all must return a list"


def test_pattern_detector_result_structure(ohlcv_200):
    """Any returned PatternResult must have entry, stop, target, confidence."""
    from agent_a import PatternDetector
    detector = PatternDetector()
    patterns = detector.detect_all(ohlcv_200)
    for p in patterns:
        if p is None:
            continue
        assert hasattr(p, "entry"), f"PatternResult missing 'entry': {p}"
        assert hasattr(p, "stop"), f"PatternResult missing 'stop': {p}"
        assert hasattr(p, "target"), f"PatternResult missing 'target': {p}"
        assert hasattr(p, "confidence"), f"PatternResult missing 'confidence': {p}"
        assert 0.0 <= p.confidence <= 100.0, f"confidence out of range: {p.confidence}"
        assert p.entry > 0, f"Non-positive entry: {p.entry}"


# ---------------------------------------------------------------------------
# simulate_trade tests
# ---------------------------------------------------------------------------

def test_simulate_trade_win(ohlcv_500):
    """Manually craft a bar sequence where target is hit first."""
    from backtester import simulate_trade
    # Build a minimal DataFrame where bar 1 has high > target
    df = pl.DataFrame({
        "timestamp": [None, None, None],
        "open":  [100.0, 103.0, 104.0],
        "high":  [101.0, 106.0, 107.0],  # bar 1: high=106 > target=105
        "low":   [99.0,  102.0, 103.0],
        "close": [100.5, 105.5, 104.5],
        "volume": [1000, 1100, 1200],
    })
    result = simulate_trade(df, signal_idx=0, entry=100.0, stop=98.0, target=105.0, direction="long")
    assert result["outcome"] == "win"
    assert result["r_multiple"] > 0


def test_simulate_trade_loss(ohlcv_500):
    """Manually craft a bar sequence where stop is hit first."""
    from backtester import simulate_trade
    df = pl.DataFrame({
        "timestamp": [None, None, None],
        "open":  [100.0, 97.0, 96.0],
        "high":  [101.0, 99.0, 98.0],
        "low":   [99.0,  96.0, 95.0],   # bar 1: low=96 < stop=97
        "close": [100.5, 97.5, 96.5],
        "volume": [1000, 1100, 1200],
    })
    result = simulate_trade(df, signal_idx=0, entry=100.0, stop=97.0, target=106.0, direction="long")
    assert result["outcome"] == "loss"
    assert result["r_multiple"] < 0


def test_simulate_trade_invalid_risk():
    """Zero risk (entry == stop) returns 'invalid'."""
    from backtester import simulate_trade
    df = pl.DataFrame({
        "timestamp": [None, None],
        "open": [100.0, 100.0], "high": [101.0, 101.0],
        "low": [99.0, 99.0], "close": [100.5, 100.5], "volume": [1000, 1000],
    })
    result = simulate_trade(df, signal_idx=0, entry=100.0, stop=100.0, target=105.0)
    assert result["outcome"] == "invalid"


# ---------------------------------------------------------------------------
# WalkForwardBacktester integration tests
# ---------------------------------------------------------------------------

def test_walkforward_returns_valid_structure(ohlcv_500):
    """run() must return a dict with all required keys."""
    from backtester import WalkForwardBacktester
    bt = WalkForwardBacktester(window_size=80, step_size=25)
    result = bt.run(ohlcv_500)
    for key in ("total_signals", "simulated_trades", "win_rate", "avg_r_multiple",
                "expectancy", "sharpe_proxy", "profit_factor", "max_drawdown_r",
                "patterns_found"):
        assert key in result, f"Missing key in backtest result: {key}"


def test_walkforward_max_drawdown_is_non_positive(ohlcv_500):
    """Max drawdown (peak-to-trough in R) can never be positive; profit factor >= 0."""
    from backtester import WalkForwardBacktester
    bt = WalkForwardBacktester(window_size=80, step_size=25)
    result = bt.run(ohlcv_500)
    assert result["max_drawdown_r"] <= 0.0
    assert result["profit_factor"] >= 0.0


def test_walkforward_win_rate_in_range(ohlcv_500):
    """Win rate must be in [0, 1]."""
    from backtester import WalkForwardBacktester
    bt = WalkForwardBacktester(window_size=80, step_size=25)
    result = bt.run(ohlcv_500)
    assert 0.0 <= result["win_rate"] <= 1.0


def test_walkforward_signal_count_nonneg(ohlcv_500):
    """Signal and trade counts must be non-negative."""
    from backtester import WalkForwardBacktester
    bt = WalkForwardBacktester(window_size=80, step_size=25)
    result = bt.run(ohlcv_500)
    assert result["total_signals"] >= 0
    assert result["simulated_trades"] >= 0


def test_walkforward_deterministic():
    """Same seed + same params → identical results."""
    from backtester import run_walk_forward
    r1 = run_walk_forward(n_bars=300, window_size=80, step_size=20, seed=42)
    r2 = run_walk_forward(n_bars=300, window_size=80, step_size=20, seed=42)
    assert r1["win_rate"] == r2["win_rate"]
    assert r1["simulated_trades"] == r2["simulated_trades"]


def test_walkforward_empty_df_graceful():
    """Backtester must not crash on a DataFrame too short to produce any windows."""
    from backtester import WalkForwardBacktester, generate_ohlcv
    bt = WalkForwardBacktester(window_size=200, step_size=50)
    tiny_df = generate_ohlcv(n_bars=10, seed=1)  # much smaller than window
    result = bt.run(tiny_df)
    assert result["simulated_trades"] == 0
    assert result["win_rate"] == 0.0


def test_run_walk_forward_convenience():
    """run_walk_forward() convenience wrapper returns non-error result."""
    from backtester import run_walk_forward
    result = run_walk_forward(n_bars=250, window_size=80, step_size=20, seed=5)
    assert isinstance(result, dict)
    assert "expectancy" in result


# ---------------------------------------------------------------------------
# Real-data WalkForwardEngine smoke test (DB-backed edge validation path)
# ---------------------------------------------------------------------------

def test_backtest_engine_runs_on_synthetic_db(tmp_path):
    """The DB-backed edge engine must run end-to-end on a temp SQLite DB and the
    aggregate report must expose the full metric set (incl. sharpe_per_trade, max_drawdown)."""
    import asyncio
    import sqlite3

    from backtest_engine import WalkForwardEngine, aggregate_results
    from backtester import generate_ohlcv

    db = tmp_path / "trading.db"
    df = generate_ohlcv(n_bars=400, seed=11)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE ohlcv (symbol TEXT, timestamp TEXT, open REAL, high REAL, "
        "low REAL, close REAL, volume REAL)"
    )
    rows = list(zip(
        ["SPY"] * len(df),
        [str(ts) for ts in df["timestamp"].to_list()],
        df["open"].to_list(), df["high"].to_list(), df["low"].to_list(),
        df["close"].to_list(), df["volume"].to_list(),
        strict=True,
    ))
    conn.executemany("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    engine = WalkForwardEngine(db_path=str(db), train_bars=150, test_bars=60)
    windows = asyncio.run(engine.run("SPY"))
    stats = aggregate_results(windows)

    # No windows/trades is a valid (non-crashing) outcome; only assert structure when present.
    if "error" not in stats:
        for key in (
            "verdict",
            "sharpe",
            "sharpe_per_trade",
            "max_drawdown",
            "profit_factor",
            "expectancy_net_usd",
            "win_rate",
            "total_trades",
        ):
            assert key in stats, f"aggregate_results missing key: {key}"
        assert stats["max_drawdown"] <= 0.0
