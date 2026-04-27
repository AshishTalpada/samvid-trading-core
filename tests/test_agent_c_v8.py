import pytest

# Samvid v1.0-beta-beta-beta AGENT C AUDIT (Agent S)
# This test verifies that the refactored Execution Mind is functional
# and all 5 Lynchpin Risk Pillars are active.


@pytest.mark.asyncio
async def test_agent_c_sovereign_integrity(ticker) -> None:
    from src.agent_c_ibkr import (
        BlackSwanProtocol,
        CorrelationCascade,
        IBKRConnection,
        PortfolioGuard,
        PositionSizingChain,
        VIXProtocol,
    )

    # 1. Instantiation Check
    IBKRConnection()
    sizer = PositionSizingChain()
    vix_gate = VIXProtocol()
    CorrelationCascade()
    swan_gate = BlackSwanProtocol()
    port_gate = PortfolioGuard()

    assert sizer is not None

    # 2. Sizing Test (Mathematical Integrity)
    # Samvid v1.0-beta-beta-beta: Corrected r_r_ratio key alignment
    sizing = sizer.calculate(
        win_prob=0.65, r_r_ratio=2.0, balance=100000.0, symbol=ticker, price=150.0, stop_price=145.0
    )
    assert sizing["step8_shares"] > 0

    # 3. VIX Protocol Test (VIX=28.0)
    mod = vix_gate.get_modifier(vix=28.0)
    assert mod == 0.5

    # 4. Portfolio Guard Test
    # Test PortfolioGuard - Proposed 95k on 100k (violates 20% reserve)
    exposure_ok = port_gate.enforce_cash_reserve(balance=100000.0, total_position_value=95000.0)
    assert exposure_ok is False

    # 5. Black Swan Check
    assert swan_gate.check(vix=60.0, drawdown_pct=0.15) == "FREEZE"


if __name__ == "__main__":
    pytest.main([__file__])
