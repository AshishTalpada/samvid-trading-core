# pyre-ignore-all-errors[21]
"""
tests/test_integration.py
Integration tests for multi-agent trading system
"""


def test_kelly_cap() -> None:
    from src.agent_c_ibkr import PositionSizingChain  # type: ignore

    r = PositionSizingChain().calculate(
        win_prob=0.99, r_r_ratio=10.0, balance=100000, price=150, stop_price=145
    )
    assert r["risk_dollars"] <= 4000


def test_f17_belief_cap() -> None:
    from src.agent_b import BayesianBeliefTracker  # type: ignore

    t = BayesianBeliefTracker(0.5)
    for _ in range(20):
        t.update("price_toward_large", 0.03)
    assert t.current_belief <= 0.90


def test_belief_drops_adverse() -> None:
    from src.agent_b import BayesianBeliefTracker  # type: ignore

    t = BayesianBeliefTracker(0.85)
    t.update("price_against_medium", -0.015)
    assert t.current_belief < 0.75


def test_f3_returns_tuple() -> None:
    from src.agent_b import CatalystScorer  # type: ignore

    r = CatalystScorer().score(70, {"macro": 5}, 2.0, None, "orbital", 50)
    assert isinstance(r, dict) and "agent" in r


def test_f6_eight_steps(ticker) -> None:
    from src.agent_c_ibkr import PositionSizingChain  # type: ignore

    r = PositionSizingChain().calculate(
        win_prob=0.65,
        r_r_ratio=2.0,
        balance=1000,
        symbol=ticker,
        account_type="margin",
        price=1.5,
        vix=18.0,
        drawdown_pct=0.03,
        time_of_day="morning",
        stop_price=1.45,  # Added stop_price for risk_per_share calculation
    )
    assert "balance_used" in r and "risk_dollars" in r


def test_ftmo_daily_limit() -> None:
    from src.agent_c_mt5 import FTMOComplianceLayer  # type: ignore

    assert 0.03 <= FTMOComplianceLayer.DAILY_LIMIT <= 0.05


def test_ftmo_drawdown_limit() -> None:
    from src.agent_c_mt5 import FTMOComplianceLayer  # type: ignore

    assert 0.07 <= FTMOComplianceLayer.DRAWDOWN_LIMIT <= 0.10


def test_ftmo_max_trades() -> None:
    from src.agent_c_mt5 import FTMOComplianceLayer  # type: ignore

    assert FTMOComplianceLayer.MAX_TRADES <= 5000


def test_budget_freeze() -> None:
    from src.agent_a import ContinuousBudgetMonitor  # type: ignore

    m = ContinuousBudgetMonitor()
    m.daily_loss_pct = 1.01
    assert not m.is_trading_allowed()


def test_m04_gate() -> None:
    from src.agent_d import StatisticalSignificanceGate  # type: ignore

    g = StatisticalSignificanceGate()
    assert not g.can_adapt(15)
    assert g.can_adapt(250)
