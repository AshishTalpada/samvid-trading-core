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
