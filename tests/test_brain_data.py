import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from brain_data import DataProvider


class _Provider(DataProvider):
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.db_conn = None
        self.qdb = SimpleNamespace(enabled=False)
        self._hot_cache = {}
        self._hot_cache_time = {}
        self._qdb_circuit_broken = False
        self._qdb_last_failure_time = 0.0
        self._qdb_failure_count = 0


def _seed_bar(db_path: str, timestamp: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE ohlcv (
                symbol TEXT,
                timestamp TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                timeframe TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO ohlcv VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("SPY", timestamp, 500.0, 501.0, 499.0, 500.5, 1000, "1m"),
        )


def test_live_bar_age_contract_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOVEREIGN_MAX_LIVE_BAR_AGE_SEC", "10")
    assert DataProvider._live_bar_staleness_limit_sec() == 60.0

    monkeypatch.setenv("SOVEREIGN_MAX_LIVE_BAR_AGE_SEC", "99999")
    assert DataProvider._live_bar_staleness_limit_sec() == 900.0

    monkeypatch.setenv("SOVEREIGN_MAX_LIVE_BAR_AGE_SEC", "invalid")
    assert DataProvider._live_bar_staleness_limit_sec() == 180.0


@pytest.mark.asyncio
async def test_fetch_ohlcv_rejects_stale_live_bar(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "stale.db")
    _seed_bar(db_path, (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat())
    monkeypatch.setenv("SOVEREIGN_MAX_LIVE_BAR_AGE_SEC", "180")
    provider = _Provider(db_path)
    monkeypatch.setattr(provider, "_is_market_open", lambda: True)

    result = await provider._fetch_ohlcv("SPY")

    assert result == "STALE"


@pytest.mark.asyncio
async def test_fetch_ohlcv_rejects_unprovable_live_timestamp(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = str(tmp_path / "invalid.db")
    _seed_bar(db_path, "not-a-timestamp")
    provider = _Provider(db_path)
    monkeypatch.setattr(provider, "_is_market_open", lambda: True)

    result = await provider._fetch_ohlcv("SPY")

    assert result == "STALE"


@pytest.mark.asyncio
async def test_fetch_ohlcv_records_recent_freshness_proof(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = str(tmp_path / "fresh.db")
    _seed_bar(db_path, datetime.now(timezone.utc).isoformat())
    provider = _Provider(db_path)
    monkeypatch.setattr(provider, "_is_market_open", lambda: True)

    result = await provider._fetch_ohlcv("SPY")

    assert not isinstance(result, str)
    assert provider._last_fresh_bar_at["SPY"] > 0
