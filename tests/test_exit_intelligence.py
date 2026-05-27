"""
Tests for exit_intelligence.py safety guards.
"""

from datetime import datetime, timezone

from exit_intelligence import ExitDecision, ExitIntelligence


def test_belief_exit_blocked_by_min_hold_time() -> None:
    """Belief collapse within min_hold_minutes should NOT trigger exit."""
    ei = ExitIntelligence()
    ei.min_hold_minutes = 2.0

    pos = {
        "symbol": "AAPL",
        "side": "long",
        "quantity": 10,
        "entry_price": 150.0,
        "stop_loss": 148.0,
        "initial_stop": 148.0,
        "bayesian_belief": 0.10,  # Below 0.15 threshold
        "initial_belief": 0.80,
        "mfe_r": 0.0,  # No trailing stop activation
        "runner_active": False,
        "entry_time": datetime(2026, 1, 1, tzinfo=timezone.utc),  # very old = held long enough
    }
    market = {"price": 150.5, "vix": 15.5, "vix_baseline": 15.0}  # vix_change=3.3% < 15% threshold
    account = {"equity": 10000.0, "daily_pnl": 0.0}

    # With old entry_time, belief collapse SHOULD trigger
    decision = ei.evaluate(pos, market, account)
    assert decision.action.value == "EXIT", f"Expected EXIT for old position, got {decision.action.value}"

    # With recent entry_time, belief collapse should NOT trigger
    pos["entry_time"] = datetime.now(timezone.utc)
    decision = ei.evaluate(pos, market, account)
    assert decision.action.value == "HOLD", f"Expected HOLD for fresh position, got {decision.action.value}"


def test_belief_exit_blocked_when_in_profit() -> None:
    """Belief collapse when R > min_r_for_belief_exit should NOT trigger exit."""
    ei = ExitIntelligence()
    ei.min_r_for_belief_exit = 0.5

    pos = {
        "symbol": "AAPL",
        "side": "long",
        "quantity": 10,
        "entry_price": 150.0,
        "stop_loss": 148.0,
        "initial_stop": 148.0,
        "bayesian_belief": 0.10,  # Below threshold
        "initial_belief": 0.80,
        "mfe_r": 0.0,  # No trailing stop activation
        "runner_active": False,
        "entry_time": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    market = {"price": 153.0, "vix": 15.5, "vix_baseline": 15.0}  # vix_change=3.3% < 15% threshold
    account = {"equity": 10000.0, "daily_pnl": 0.0}

    decision = ei.evaluate(pos, market, account)
    assert decision.action.value == "HOLD", f"Expected HOLD when in profit, got {decision.action.value}"


def test_hard_stop_always_exits() -> None:
    """Price hitting stop_loss should always exit regardless of belief."""
    ei = ExitIntelligence()

    pos = {
        "symbol": "AAPL",
        "side": "long",
        "quantity": 10,
        "entry_price": 150.0,
        "stop_loss": 148.0,
        "initial_stop": 148.0,
        "bayesian_belief": 0.90,  # High belief
        "initial_belief": 0.80,
        "mfe_r": 0.0,
        "runner_active": False,
        "entry_time": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    market = {"price": 147.5, "vix": 15.5, "vix_baseline": 15.0}  # Below stop
    account = {"equity": 10000.0, "daily_pnl": 0.0}

    decision = ei.evaluate(pos, market, account)
    assert decision.action.value == "EXIT", f"Expected EXIT at hard stop, got {decision.action.value}"


def test_invalid_input_returns_hold() -> None:
    """None position or market should return HOLD with safe fallback."""
    ei = ExitIntelligence()
    decision = ei.evaluate(None, {"price": 100.0}, {"equity": 10000.0})
    assert decision.action.value == "HOLD"
    assert "Invalid input" in decision.reason

    decision = ei.evaluate({"entry_price": 100.0}, None, {"equity": 10000.0})
    assert decision.action.value == "HOLD"
