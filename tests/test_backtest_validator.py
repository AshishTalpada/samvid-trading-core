"""
Tests for backtest_validator.py — pre-trade historical edge validation gate.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from backtest_validator import BacktestValidationResult, BacktestValidator


class FakePattern:
    """Minimal stand-in for a Pattern object."""

    def __init__(self, name="BullFlag", confidence=75.0):
        self.name = name
        self.confidence = confidence
        self.entry = 100.0
        self.stop = 98.0
        self.target = 104.0


@pytest.fixture
def sample_ohlcv() -> pl.DataFrame:
    """Generate a 300-bar synthetic OHLCV DataFrame."""
    rng = np.random.default_rng(42)
    n = 300
    prices = [100.0]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + rng.normal(0, 0.01)))
    opens, highs, lows, closes, volumes = [], [], [], [], []
    for close in prices:
        spread = close * 0.005
        open_ = close * (1 + rng.normal(0, 0.003))
        high = max(close, open_) + abs(rng.normal(0, spread))
        low = min(close, open_) - abs(rng.normal(0, spread))
        opens.append(round(open_, 4))
        highs.append(round(high, 4))
        lows.append(round(low, 4))
        closes.append(round(close, 4))
        volumes.append(int(rng.lognormal(15, 0.8)))
    return pl.DataFrame(
        {
            "timestamp": list(range(n)),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


@pytest.fixture
def temp_db_with_ohlcv(sample_ohlcv: pl.DataFrame) -> str:
    """Create a temp SQLite DB with an ohlcv table populated from sample data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE ohlcv (timestamp TEXT, symbol TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER)"
    )
    for row in sample_ohlcv.to_dicts():
        conn.execute(
            "INSERT INTO ohlcv VALUES (?, 'SPY', ?, ?, ?, ?, ?)",
            (str(row["timestamp"]), row["open"], row["high"], row["low"], row["close"], row["volume"]),
        )
    conn.commit()
    conn.close()
    yield db_path
    Path(db_path).unlink(missing_ok=True)


class TestBacktestValidator:
    @pytest.mark.asyncio
    async def test_validate_pattern_with_df(self, sample_ohlcv: pl.DataFrame):
        validator = BacktestValidator(
            db_path=":memory:",
            min_profit_factor=0.0,
            min_win_rate=0.0,
            min_expectancy_r=-999.0,
            min_sharpe_proxy=-999.0,
            min_trades=0,
        )
        pattern = FakePattern()
        result = await validator.validate_pattern("SPY", pattern, df=sample_ohlcv)
        assert isinstance(result, BacktestValidationResult)
        assert result.symbol == "SPY"
        assert result.pattern_name == "BullFlag"
        assert result.total_trades >= 0

    @pytest.mark.asyncio
    async def test_validate_pattern_fails_when_no_data(self):
        validator = BacktestValidator(db_path=":memory:")
        pattern = FakePattern()
        result = await validator.validate_pattern("SPY", pattern, df=None)
        assert not result.passed
        assert "insufficient_historical_data" in result.blockers

    @pytest.mark.asyncio
    async def test_validate_symbol_overall_no_data(self):
        validator = BacktestValidator(db_path=":memory:")
        report = await validator.validate_symbol_overall("SPY")
        assert "error" in report

    @pytest.mark.asyncio
    async def test_save_validation_record(self, sample_ohlcv: pl.DataFrame):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            validator = BacktestValidator(db_path=db_path, min_trades=0)
            pattern = FakePattern()
            result = await validator.validate_pattern("SPY", pattern, df=sample_ohlcv)
            await validator.save_validation_record(result)

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT symbol, pattern_name, passed FROM backtest_validations")
            rows = cur.fetchall()
            conn.close()

            assert len(rows) == 1
            assert rows[0][0] == "SPY"
            assert rows[0][1] == "BullFlag"
        finally:
            Path(db_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_thresholds_block_weak_results(self, sample_ohlcv: pl.DataFrame):
        validator = BacktestValidator(
            db_path=":memory:",
            min_profit_factor=999.0,  # impossibly high
        )
        pattern = FakePattern()
        result = await validator.validate_pattern("SPY", pattern, df=sample_ohlcv)
        assert not result.passed
        assert any("profit_factor" in b for b in result.blockers)

    def test_evaluate_thresholds_passes(self):
        validator = BacktestValidator(db_path=":memory:", min_trades=1)
        stats = {
            "simulated_trades": 20,
            "win_rate": 0.55,
            "profit_factor": 1.5,
            "expectancy": 0.3,
            "sharpe_proxy": 0.8,
            "max_drawdown_r": -0.05,
            "avg_r_multiple": 0.35,
        }
        result = validator._evaluate_thresholds("SPY", "BullFlag", stats)
        assert result.passed
        assert result.total_trades == 20

    def test_evaluate_thresholds_blocks(self):
        validator = BacktestValidator(db_path=":memory:", min_trades=1)
        stats = {
            "simulated_trades": 5,
            "win_rate": 0.20,
            "profit_factor": 0.80,
            "expectancy": -0.1,
            "sharpe_proxy": 0.1,
            "max_drawdown_r": -0.30,
            "avg_r_multiple": -0.05,
        }
        result = validator._evaluate_thresholds("SPY", "BullFlag", stats)
        assert not result.passed
        assert len(result.blockers) >= 1


class TestBacktestValidationResult:
    def test_to_dict(self):
        result = BacktestValidationResult(
            passed=True,
            symbol="SPY",
            pattern_name="BullFlag",
            profit_factor=1.5,
            win_rate=0.55,
            total_trades=20,
            blockers=[],
        )
        d = result.to_dict()
        assert d["symbol"] == "SPY"
        assert d["win_rate"] == 0.55
        assert d["passed"] is True
