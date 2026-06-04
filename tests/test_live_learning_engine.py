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
