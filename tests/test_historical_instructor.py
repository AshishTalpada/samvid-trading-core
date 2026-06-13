"""
Tests for historical_instructor.py — HistoricalInstructor validation & baseline.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from historical_instructor import HistoricalInstructor, ValidationResult


@pytest.fixture
def temp_db_with_ohlcv() -> str:
    """Create a temp SQLite DB with enough OHLCV rows for 200MA baseline."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    rng = np.random.default_rng(42)
    n = 300
    prices = [100.0]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + rng.normal(0, 0.01)))
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE ohlcv (timestamp TEXT, symbol TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER)"
    )
    for i, close in enumerate(prices):
        spread = close * 0.005
        open_ = close * (1 + rng.normal(0, 0.003))
        high = max(close, open_) + abs(rng.normal(0, spread))
        low = min(close, open_) - abs(rng.normal(0, spread))
        conn.execute(
            "INSERT INTO ohlcv VALUES (?, 'SPY', ?, ?, ?, ?, ?)",
            (str(i), round(open_, 4), round(high, 4), round(low, 4), round(close, 4), int(rng.lognormal(15, 0.8))),
        )
    conn.commit()
    conn.close()
    yield db_path
    Path(db_path).unlink(missing_ok=True)


class TestValidationResult:
    def test_to_dict(self):
        result = ValidationResult(
            symbol="SPY",
            passed=True,
            sharpe=1.2,
            max_drawdown_pct=-0.05,
            total_return_pct=5.0,
            win_rate=0.55,
            profit_factor=1.5,
            expectancy_r=0.3,
            total_trades=20,
            notes=["ok"],
        )
        d = result.to_dict()
        assert d["symbol"] == "SPY"
        assert d["sharpe"] == 1.2
        assert d["notes"] == ["ok"]


class TestHistoricalInstructor:
    @pytest.mark.asyncio
    async def test_run_sanity_check_with_data(self, temp_db_with_ohlcv: str):
        instructor = HistoricalInstructor(db_path=temp_db_with_ohlcv)
        result = await instructor.run_sanity_check("SPY")
        assert isinstance(result, ValidationResult)
        assert result.symbol == "SPY"
        assert result.total_trades > 0
        assert "200MA neutral baseline" in result.notes

    @pytest.mark.asyncio
    async def test_run_sanity_check_insufficient_data(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            # Empty DB
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE ohlcv (timestamp TEXT, symbol TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER)"
            )
            conn.commit()
            conn.close()
            instructor = HistoricalInstructor(db_path=db_path)
            result = await instructor.run_sanity_check("SPY")
            assert not result.passed
            assert "insufficient data" in result.notes[0]
        finally:
            Path(db_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_run_validation_no_data(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE ohlcv (timestamp TEXT, symbol TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER)"
            )
            conn.commit()
            conn.close()
            instructor = HistoricalInstructor(db_path=db_path)
            result = await instructor.run_validation("SPY")
            assert not result.passed
            assert len(result.notes) > 0
        finally:
            Path(db_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_compare_model_vs_baseline(self, temp_db_with_ohlcv: str):
        instructor = HistoricalInstructor(db_path=temp_db_with_ohlcv)
        comparison = await instructor.compare_model_vs_baseline("SPY")
        assert "model" in comparison
        assert "baseline" in comparison
        assert "model_beats_baseline" in comparison
        assert isinstance(comparison["model_beats_baseline"], bool)

    def test_persist_result(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            instructor = HistoricalInstructor(db_path=db_path)
            result = ValidationResult(
                symbol="SPY",
                passed=True,
                sharpe=1.2,
                max_drawdown_pct=-0.05,
                total_return_pct=5.0,
                win_rate=0.55,
                profit_factor=1.5,
                expectancy_r=0.3,
                total_trades=20,
                notes=["test"],
            )
            instructor.persist_result(result)

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT symbol, passed, sharpe FROM historical_validations")
            rows = cur.fetchall()
            conn.close()

            assert len(rows) == 1
            assert rows[0][0] == "SPY"
            assert rows[0][1] == 1
            assert rows[0][2] == 1.2
        finally:
            Path(db_path).unlink(missing_ok=True)
