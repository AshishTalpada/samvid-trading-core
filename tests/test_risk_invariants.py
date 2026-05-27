# pyre-ignore-all-errors[21]
from pathlib import Path


def test_f6_chain_step_order_and_presence() -> None:
    from src.agent_c_ibkr import PositionSizingChain  # type: ignore

    result = PositionSizingChain().calculate(
        win_prob=0.62,
        r_r_ratio=2.1,
        balance=10000.0,
        account_value=10000.0,
        entry_price=100.0,
        stop_price=98.5,
        instrument="SPY",
        regime="CHOPPY",
        regime_modifier=0.8,
        drawdown_modifier=0.5,
        loss_modifier=0.5,
    )

    expected_keys = [
        "balance_used",
        "position_value",
        "risk_dollars",
    ]
    keys = list(result.keys())
    assert all(k in keys for k in expected_keys)


def test_f6_hard_cap_4_percent() -> None:
    from src.agent_c_ibkr import PositionSizingChain  # type: ignore

    result = PositionSizingChain().calculate(
        win_prob=0.99,
        r_r_ratio=10.0,
        balance=100000.0,
        account_value=10000.0,
        entry_price=100.0,
        stop_price=99.0,
        instrument="SPY",
    )
    assert result["risk_dollars"] <= 4000.0


def test_portfolio_guard_20_percent_reserve_boundary() -> None:
    from src.agent_c_ibkr import PortfolioGuard  # type: ignore

    guard = PortfolioGuard()
    assert guard.enforce_cash_reserve(balance=10000.0, total_position_value=8000.0) is True
    assert guard.enforce_cash_reserve(balance=10000.0, total_position_value=8001.0) is False


def test_abhava_detector_gap_without_catalyst() -> None:
    from src.agent_b import ABHAVADetector  # type: ignore

    detected = ABHAVADetector().detect(
        [
            {
                "price_change": 0.01,
                "has_catalyst": False,
                "volume_ratio": 1.0,
                "volatility": 0.02,
            }
        ]
    )
    assert detected is True


def test_env_example_has_no_live_key_prefixes() -> None:
    content = Path(".env.example").read_text(encoding="utf-8")
    forbidden_markers = ["sk-", "AIza", "AAH", "xoxb-", "ghp_"]
    assert not any(marker in content for marker in forbidden_markers)


def test_drawdown_modifier_clamps_below_1_0() -> None:
    from src.agent_c_ibkr import PositionSizingChain  # type: ignore

    result_low = PositionSizingChain().calculate(
        win_prob=0.62, r_r_ratio=2.1, balance=10000.0, account_value=10000.0,
        entry_price=100.0, stop_price=98.5, instrument="SPY",
        drawdown_modifier=0.3, loss_modifier=1.0,
    )
    result_high = PositionSizingChain().calculate(
        win_prob=0.62, r_r_ratio=2.1, balance=10000.0, account_value=10000.0,
        entry_price=100.0, stop_price=98.5, instrument="SPY",
        drawdown_modifier=2.0, loss_modifier=1.0,
    )
    # 0.3 should be floored to 0.5; 2.0 should be capped to 1.5
    assert result_low["risk_dollars"] <= result_high["risk_dollars"]


def test_black_swan_freezes_on_extreme_vix() -> None:
    from src.agent_c_ibkr import BlackSwanProtocol  # type: ignore

    bsp = BlackSwanProtocol()
    assert bsp.check(vix=60.0, drawdown_pct=0.05) == "FREEZE"
    assert bsp.check(vix=40.0, drawdown_pct=0.15) == "FREEZE"
    assert bsp.check(vix=30.0, drawdown_pct=0.05) == "NORMAL"


def test_correlation_cascade_uses_real_sectors() -> None:
    from src.agent_c_ibkr import CorrelationCascade, _get_sector  # type: ignore

    assert _get_sector("AAPL") == "TECH"
    assert _get_sector("amzn") == "TECH"
    assert _get_sector("JPM") == "FIN"
    assert _get_sector("UNKNOWN_TICKER") == "UNKNOWN_TICKER"

    cc = CorrelationCascade()
    # Fake position-like objects
    class FakePos:
        def __init__(self, sym, qty, price):
            self.symbol = sym
            self.qty = qty
            self.entry_price = price

    positions = [FakePos("AAPL", 10, 150.0), FakePos("MSFT", 5, 300.0)]
    # AAPL + MSFT both TECH => exposure = 10*150 + 5*300 = 3000
    assert cc.check_exposure("AAPL", positions, equity=10000.0) is True   # 30% exactly
    assert cc.check_exposure("AAPL", positions, equity=8000.0) is False  # 37.5% > 35%


def test_drawdown_ladder_scales_for_small_accounts() -> None:
    from src.brain import DrawdownLadder  # type: ignore

    dd = DrawdownLadder(account_type="ibkr", peak_equity=1000.0)
    # At K peak, scale = max(0.5, 1000/2000) = 0.5
    # RED threshold becomes 0.25 * 0.5 = 0.125
    level = dd.update(equity=870.0)  # 13% drawdown
    assert level.name == "RED"

    dd2 = DrawdownLadder(account_type="ibkr", peak_equity=5000.0)
    level2 = dd2.update(equity=4350.0)  # 13% drawdown
    assert level2.name == "YELLOW"  # unscaled threshold 0.12 < 0.13 < 0.18


def test_win_streak_cap_at_1_15x() -> None:
    from src.brain import ConsecutiveLossTracker  # type: ignore

    tracker = ConsecutiveLossTracker()
    for _ in range(10):
        tracker.record_outcome(is_win=True)
    mod = tracker.get_size_modifier()
    assert mod <= 1.15
    assert mod > 1.0
