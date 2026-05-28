"""
tests/test_best_day_rule.py
Tests for FTMO Best Day Rule enforcement in TradingCoordinator.
"""
import pytest
from unittest.mock import MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def mock_coordinator():
    """Create a TradingCoordinator with a minimal mock brain."""
    with patch("coordinator.LEDGER", MagicMock()):
        from coordinator import TradingCoordinator
        brain = MagicMock()
        brain.db_conn = None  # No DB for unit tests
        brain.session_pnl = 0.0
        brain.active_broker = "ibkr"
        bridge = MagicMock()
        coord = TradingCoordinator(bridge, brain)
        return coord


def test_best_day_rule_no_profit_passes(mock_coordinator):
    """Rule only applies when today is profitable — zero/negative always passes."""
    passes, reason = mock_coordinator._check_best_day_rule(today_pnl=0.0, broker="ibkr")
    assert passes is True
    passes2, _ = mock_coordinator._check_best_day_rule(today_pnl=-50.0, broker="ibkr")
    assert passes2 is True


def test_best_day_rule_no_db_passes(mock_coordinator):
    """Without DB, rule cannot be checked — must allow (fail-open)."""
    mock_coordinator.brain.db_conn = None
    passes, _ = mock_coordinator._check_best_day_rule(today_pnl=500.0, broker="mt5")
    assert passes is True


def test_best_day_rule_no_history_passes(mock_coordinator):
    """No prior profitable days — rule cannot trigger."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_db.cursor.return_value = mock_cursor
    mock_coordinator.brain.db_conn = mock_db
    passes, _ = mock_coordinator._check_best_day_rule(today_pnl=300.0, broker="mt5")
    assert passes is True


def test_best_day_rule_below_threshold_passes(mock_coordinator):
    """Today < 2/3 × avg_others — should pass."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    # avg_others = 300, threshold = 200, today = 150 -> passes
    mock_cursor.fetchall.return_value = [("2026-01-01", 300.0), ("2026-01-02", 300.0)]
    mock_db.cursor.return_value = mock_cursor
    mock_coordinator.brain.db_conn = mock_db
    passes, reason = mock_coordinator._check_best_day_rule(today_pnl=150.0, broker="ibkr")
    assert passes is True
    assert reason == ""


def test_best_day_rule_exceeds_threshold_fails(mock_coordinator):
    """Today > 2/3 × avg_others — should fail on prop track."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    # avg_others = 300, threshold = 200, today = 250 -> fails
    mock_cursor.fetchall.return_value = [("2026-01-01", 300.0), ("2026-01-02", 300.0)]
    mock_db.cursor.return_value = mock_cursor
    mock_coordinator.brain.db_conn = mock_db
    passes, reason = mock_coordinator._check_best_day_rule(today_pnl=250.0, broker="mt5")
    assert passes is False
    assert "Best Day Rule" in reason
    assert "250.00" in reason


def test_best_day_rule_negative_days_ignored(mock_coordinator):
    """Only profitable days count in avg_others — negative days ignored."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    # Only one profitable day at 300; today at 250 < 200 -> fails
    mock_cursor.fetchall.return_value = [
        ("2026-01-01", 300.0),
        ("2026-01-02", -100.0),  # loss day — must be excluded
        ("2026-01-03", -50.0),
    ]
    mock_db.cursor.return_value = mock_cursor
    mock_coordinator.brain.db_conn = mock_db
    # avg_others of profitable only = 300, threshold = 200, today = 250 -> fails
    passes, reason = mock_coordinator._check_best_day_rule(today_pnl=250.0, broker="mt5")
    assert passes is False


def test_best_day_rule_db_exception_passes(mock_coordinator):
    """DB exception must fail-open (allow trade) to avoid blocking on DB errors."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.side_effect = Exception("DB error")
    mock_db.cursor.return_value = mock_cursor
    mock_coordinator.brain.db_conn = mock_db
    passes, _ = mock_coordinator._check_best_day_rule(today_pnl=999.0, broker="mt5")
    assert passes is True
