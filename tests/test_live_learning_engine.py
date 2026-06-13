import sqlite3
from unittest.mock import AsyncMock, MagicMock

import pytest

import agent_d
from agent_d import LiveLearningEngine


def test_live_learning_engine_treats_mock_history_as_empty(monkeypatch):
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = MagicMock()
    conn.execute.return_value.fetchall.return_value = MagicMock()
    monkeypatch.setattr(agent_d._sqlite3, "connect", MagicMock(return_value=conn))

    engine = LiveLearningEngine(db_path=":memory:")

    assert engine._n_trades == 0
    assert engine._n_wins == 0
    assert list(engine._recent_trades) == []


@pytest.mark.asyncio
async def test_live_learning_engine_updates_alpha_watchdog_on_exit(tmp_path):
    bus = MagicMock()
    bus.publish = AsyncMock()
    engine = LiveLearningEngine(db_path=str(tmp_path / "learning.db"), bus=bus)

    await engine._handle_trade_exit(
        {
            "symbol": "SPY",
            "pattern": "opening_range_breakout",
            "pnl": 25.0,
            "r_multiple": 1.2,
            "regime": "TRENDING",
            "session": "RTH",
        }
    )

    strategy_id = "opening_range_breakout|TRENDING|RTH"
    assert engine._latest_alpha_health[strategy_id]["status"] == "WARMING_UP"
    assert engine._latest_alpha_health[strategy_id]["strategy_id"] == strategy_id


def test_live_learning_engine_can_hydrate_alpha_health_silently(tmp_path):
    engine = LiveLearningEngine(db_path=str(tmp_path / "learning.db"))
    engine.alpha_watchdog.evaluate = MagicMock(return_value={"status": "RETIRE"})

    health = engine._record_alpha_health(
        {"pattern": "ADOPTED_ORPHAN", "regime": "BULL", "session": "RTH", "pnl": -10.0},
        emit_log=False,
    )

    assert health["strategy_id"] == "ADOPTED_ORPHAN|BULL|RTH"
    engine.alpha_watchdog.evaluate.assert_called_once_with(
        "ADOPTED_ORPHAN|BULL|RTH", emit_log=False
    )


def test_live_learning_engine_migrates_legacy_observation_schema(tmp_path):
    db_path = tmp_path / "learning.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE agent_d_market_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            observed_at TEXT,
            symbol TEXT NOT NULL,
            event_type TEXT NOT NULL,
            pattern TEXT,
            confidence REAL,
            price REAL,
            regime TEXT,
            dhatu_state TEXT,
            source TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    LiveLearningEngine(db_path=str(db_path))

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(agent_d_market_observations)")}
    conn.close()
    assert {
        "forward_status",
        "forward_return_5m",
        "forward_return_15m",
        "forward_return_60m",
        "metadata_json",
    } <= columns


@pytest.mark.asyncio
async def test_live_learning_engine_persists_market_observation(tmp_path):
    engine = LiveLearningEngine(db_path=str(tmp_path / "learning.db"))

    await engine._handle_market_observation(
        {
            "observed_at": "2026-06-05T14:00:00+00:00",
            "symbol": "SPY",
            "event_type": "PATTERN_LOW_CONFIDENCE",
            "pattern": "bull_flag",
            "confidence": 57.5,
            "price": 604.25,
            "regime": "TRENDING",
            "dhatu_state": "STHIRA",
            "source": "brain.scan",
            "metadata": {"reason": "confidence below approval floor"},
        }
    )

    conn = sqlite3.connect(tmp_path / "learning.db")
    row = conn.execute(
        """
        SELECT symbol, event_type, pattern, confidence, price, regime, forward_status
        FROM agent_d_market_observations
        """
    ).fetchone()
    conn.close()

    assert row == (
        "SPY",
        "PATTERN_LOW_CONFIDENCE",
        "bull_flag",
        57.5,
        604.25,
        "TRENDING",
        "PENDING",
    )


@pytest.mark.asyncio
async def test_market_observations_mature_into_bounded_forward_returns(tmp_path):
    bus = MagicMock()
    bus.publish = AsyncMock()
    engine = LiveLearningEngine(db_path=str(tmp_path / "learning.db"), bus=bus)

    observations = [
        ("2026-06-05T14:00:00+00:00", 100.0),
        ("2026-06-05T14:05:00+00:00", 101.0),
        ("2026-06-05T14:15:00+00:00", 103.0),
        ("2026-06-05T15:00:00+00:00", 110.0),
    ]
    for observed_at, price in observations:
        await engine._handle_market_observation(
            {
                "observed_at": observed_at,
                "symbol": "SPY",
                "event_type": "PRICE_DRIFT_UP",
                "pattern": "REALTIME_PRICE_DRIFT",
                "price": price,
                "regime": "TRENDING",
            }
        )

    conn = sqlite3.connect(tmp_path / "learning.db")
    row = conn.execute(
        """
        SELECT forward_status, forward_return_5m, forward_return_15m, forward_return_60m
        FROM agent_d_market_observations
        ORDER BY id ASC LIMIT 1
        """
    ).fetchone()
    conn.close()

    assert row[0] == "RESOLVED"
    assert row[1:] == pytest.approx((1.0, 3.0, 10.0))
    learning_events = [
        call.args[1]
        for call in bus.publish.await_args_list
        if call.args[0] == "observation.learning"
    ]
    assert learning_events[-1]["execution_authority"] is False
    edges = engine.observation_edge_summary(min_samples=1)
    assert edges[0]["event_type"] == "PRICE_DRIFT_UP"
    assert edges[0]["samples"] == 1
    assert edges[0]["avg_return_60m_pct"] == pytest.approx(10.0)
    assert edges[0]["shadow_only"] is True


@pytest.mark.asyncio
async def test_market_observation_expiry_does_not_invent_stale_returns(tmp_path):
    engine = LiveLearningEngine(db_path=str(tmp_path / "learning.db"))

    for observed_at, price in (
        ("2026-06-05T14:00:00+00:00", 100.0),
        ("2026-06-05T15:20:00+00:00", 120.0),
    ):
        await engine._handle_market_observation(
            {
                "observed_at": observed_at,
                "symbol": "SPY",
                "event_type": "PRICE_DRIFT_UP",
                "price": price,
            }
        )

    conn = sqlite3.connect(tmp_path / "learning.db")
    row = conn.execute(
        """
        SELECT forward_status, forward_return_5m, forward_return_15m, forward_return_60m
        FROM agent_d_market_observations
        ORDER BY id ASC LIMIT 1
        """
    ).fetchone()
    conn.close()

    assert row == ("EXPIRED", None, None, None)
