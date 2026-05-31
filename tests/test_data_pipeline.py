"""
Tests for DataPipeline DB and Polars consistency.
"""

import os
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


@pytest.fixture
def pipeline_with_db():
    """Create a DataPipeline with a temporary SQLite DB."""
    import sys

    src = os.path.join(os.path.dirname(__file__), "..", "src")
    if src not in sys.path:
        sys.path.insert(0, src)

    from data_pipeline import DataPipeline

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        pipeline = DataPipeline(db_path=db_path)
        yield pipeline


def test_init_database_creates_tables(pipeline_with_db) -> None:
    """_init_database should create the ohlcv table."""
    conn = sqlite3.connect(pipeline_with_db.db_path)
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ohlcv'"
        )
        assert cursor.fetchone() is not None
    finally:
        conn.close()


def test_get_last_timestamp_no_data(pipeline_with_db) -> None:
    """get_last_timestamp should return None when no data exists."""
    result = pipeline_with_db.get_last_timestamp("SPY")
    assert result is None


def test_get_last_timestamp_with_data(pipeline_with_db) -> None:
    """get_last_timestamp should parse the most recent timestamp."""
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(pipeline_with_db.db_path)
    try:
        conn.execute(
            "INSERT INTO ohlcv (symbol, timeframe, timestamp, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("SPY", "1m", now.isoformat(), 100.0, 101.0, 99.0, 100.5, 1000),
        )
        conn.commit()
    finally:
        conn.close()

    result = pipeline_with_db.get_last_timestamp("SPY")
    assert result is not None


def test_safe_polars_from_pandas_conversion() -> None:
    """safe_polars_from_pandas should convert a pandas DataFrame to Polars."""
    import pandas as pd
    import polars as pl

    from pandas_safety import safe_polars_from_pandas

    pdf = pd.DataFrame({"Open": [1.0], "High": [2.0], "Close": [1.5]})
    pl_df = safe_polars_from_pandas(pdf)
    assert isinstance(pl_df, pl.DataFrame)
    assert len(pl_df) == 1
    assert set(pl_df.columns) == {"Open", "High", "Close"}


@pytest.mark.asyncio
async def test_realtime_tick_outranks_polling_fallback(pipeline_with_db, monkeypatch) -> None:
    monkeypatch.setattr(
        "data_pipeline.yf.Ticker",
        lambda _symbol: SimpleNamespace(fast_info={"lastPrice": 400.0}),
    )
    pipeline_with_db.qdb = SimpleNamespace(enabled=False)
    pipeline_with_db.finnhub_key = ""
    pipeline_with_db.openbb = None
    pipeline_with_db.record_realtime_tick(
        {"symbol": "SPY", "price": 525.25, "source": "TradingView_WS"}
    )

    price = await pipeline_with_db.get_current_price("SPY")

    assert price == pytest.approx(525.25)
    assert pipeline_with_db._price_cache_source["SPY"] == "TradingView_WS"


@pytest.mark.asyncio
async def test_stale_realtime_tick_falls_back_to_yfinance(pipeline_with_db, monkeypatch) -> None:
    monkeypatch.setenv("SOVEREIGN_REALTIME_TICK_MAX_AGE_SEC", "1")
    monkeypatch.setattr(
        "data_pipeline.yf.Ticker",
        lambda _symbol: SimpleNamespace(fast_info={"lastPrice": 400.0}),
    )
    pipeline_with_db.qdb = SimpleNamespace(enabled=False)
    pipeline_with_db.finnhub_key = ""
    pipeline_with_db.openbb = None
    pipeline_with_db.record_realtime_tick(
        {"symbol": "SPY", "price": 525.25, "source": "TradingView_WS"}
    )
    pipeline_with_db._price_cache_ts["SPY"] = time.monotonic() - 5.0

    price = await pipeline_with_db.get_current_price("SPY")

    assert price == pytest.approx(400.0)
    assert pipeline_with_db.get_last_price("SPY") is None
