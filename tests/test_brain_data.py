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
async def test_safe_buying_power_caps_sizing_to_allocation_fraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sizer must deploy only the allocation fraction of the ACTUAL account NAV.

    Regression: paper accounts default to ~$1M of phantom money. Without the cap the
    sizer opened $30k-$60k positions on a small-account-calibrated system.
    """
    import config

    monkeypatch.setattr(config, "IBKR_ALLOCATION_FRACTION", 0.40, raising=False)
    monkeypatch.setattr(config, "FTMO_ALLOCATION_FRACTION", 0.49, raising=False)

    provider = _Provider(":memory:")

    async def _fake_nav(account_type: str, force_fresh: bool = False) -> float:
        return 1_000_000.0  # phantom IBKR paper balance

    async def _fake_vix() -> float:
        return 0.0  # haircut = 2% base only -> deterministic

    monkeypatch.setattr(provider, "_get_account_value", _fake_nav, raising=False)
    monkeypatch.setattr(provider, "_get_vix", _fake_vix, raising=False)

    ibkr_bp = await provider.get_safe_buying_power("ibkr")
    mt5_bp = await provider.get_safe_buying_power("mt5")

    # safe = NAV * (1 - 0.02 haircut) * alloc_fraction
    assert ibkr_bp == pytest.approx(1_000_000.0 * 0.98 * 0.40)  # ~$392k, not $1M
    assert mt5_bp == pytest.approx(1_000_000.0 * 0.98 * 0.49)
    assert ibkr_bp < 1_000_000.0  # the phantom balance is never used in full


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
