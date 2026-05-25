from unittest.mock import MagicMock

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
