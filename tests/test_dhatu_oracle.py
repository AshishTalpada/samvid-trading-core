import asyncio
import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.dhatu_oracle import DhatuOracle, OracleState


def test_oracle_initialization():
    oracle = DhatuOracle()
    assert oracle.current_state == "NEUTRAL"
    assert oracle.confidence == 0


def test_macro_bias_synthesis():
    oracle = DhatuOracle()
    # Test Bearish Synthesis (High VIX, Inverted Yields)
    mock_data = {
        "vix": 35.0,
        "yield_10y": 3.5,
        "yield_2y": 4.5,  # Inverted
        "oil": 95.0,
    }
    bias = oracle.calculate_bias(mock_data)
    assert bias == "BEARISH"
    assert oracle.current_state == "KSHAYA"  # Decay/Decline


def test_macro_bias_bullish():
    oracle = DhatuOracle()
    # Test Bullish Synthesis (Low VIX, Normal Yields)
    mock_data = {"vix": 12.0, "yield_10y": 4.5, "yield_2y": 3.5, "oil": 75.0}
    bias = oracle.calculate_bias(mock_data)
    assert bias == "BULLISH"
    assert oracle.current_state == "VRIDDHI"  # Growth


def test_blackswan_detection():
    oracle = DhatuOracle()
    # Extreme VIX spike
    mock_data = {"vix": 85.0}
    is_safe = oracle.check_safety(mock_data)
    assert is_safe is False


@pytest.mark.asyncio
async def test_oracle_deduplicates_replayed_flash_headlines():
    oracle = DhatuOracle()
    headline = {"headline": "War escalation triggers market panic", "source": "TEST"}

    with patch("src.dhatu_oracle.time.time", return_value=1000.0) as clock:
        await oracle._on_news_received(headline)
        assert oracle._flash_event.is_set()
        oracle._flash_event.clear()
        clock.return_value = 1401.0
        await oracle._on_news_received(headline)

    assert not oracle._flash_event.is_set()


def test_oracle_persistence_retries_transient_database_lock(tmp_path):
    oracle = object.__new__(DhatuOracle)
    oracle._db_path = str(tmp_path / "oracle.db")
    oracle._init_db()
    state = OracleState(
        dhatu_state="Sthira",
        action_protocol="NORMAL",
        risk_modifier=1.0,
        causation_summary="Verified test state",
        confidence=0.8,
        generated_at=datetime.now(timezone.utc),
    )
    real_connect = sqlite3.connect
    attempts = 0

    def connect_with_one_lock(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise sqlite3.OperationalError("database is locked")
        return real_connect(*args, **kwargs)

    with (
        patch("sqlite3.connect", side_effect=connect_with_one_lock),
        patch("src.dhatu_oracle.time.sleep") as sleep,
    ):
        oracle._persist_state(state)

    assert attempts == 2
    sleep.assert_called_once_with(0.25)
    with sqlite3.connect(oracle._db_path) as conn:
        persisted = conn.execute(
            "SELECT value FROM system_state WHERE key = 'oracle_state'"
        ).fetchone()
        readings = conn.execute("SELECT COUNT(*) FROM dhatu_readings").fetchone()[0]
    assert persisted is not None
    assert '"dhatu_state": "Sthira"' in persisted[0]
    assert readings == 1
