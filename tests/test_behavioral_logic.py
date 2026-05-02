from unittest.mock import MagicMock

import pytest

from src.agent_b import AgentB
from src.agent_c_ibkr import AgentC
from src.dhatu_oracle import OracleState


@pytest.mark.asyncio
async def test_logical_chain_abhava_zero_risk():
    """
    Logic Validation (GAP-81):
    Verifies that if the Oracle signals 'Abhava' (Absence/Cash),
    the system correctly suppresses all position sizing to zero.
    """
    # 1. Mock Oracle State representing a total shutdown
    mock_state = OracleState(
        dhatu_state="Abhava",
        action_protocol="CASH",
        risk_modifier=0.0,
        causation_summary="Systemic Collapse Scenario",
        confidence=1.0,
    )

    # 2. Mock Agent B receiving this state
    bus = MagicMock()
    AgentB(bus=bus)

    # We simulate the signal propagation
    # In reality, Agent B listens on the bus, but here we test the logic integration

    # 3. Test Agent C's sizing logic under this modifier
    AgentC()

    # We need to see how Agent C consumes the risk_modifier.
    # Usually it's passed via the 'regime_modifier' or 'external_risk_scale'

    # Let's test the PositionSizingChain directly with the modifier
    from src.agent_c_ibkr import PositionSizingChain

    chain = PositionSizingChain()

    result = chain.calculate(
        win_prob=0.9,
        r_r_ratio=3.0,
        balance=10000.0,
        account_value=10000.0,
        entry_price=450.0,
        stop_price=440.0,
        instrument="SPY",
        regime_modifier=mock_state.risk_modifier,  # This is the crucial logic link
    )

    assert result["risk_dollars"] == 0.0, "Abhava protocol must result in zero risk."
    assert result["position_size"] == 0, "Abhava protocol must result in zero size."


@pytest.mark.asyncio
async def test_logical_chain_vriddhi_acceleration():
    """
    Logic Validation (GAP-81):
    Verifies that 'Vriddhi' (Growth) correctly accelerates sizing via the multiplier.
    """
    mock_state = OracleState(
        dhatu_state="Vriddhi",
        action_protocol="MAX_RISK",
        risk_modifier=1.5,  # 50% boost
        causation_summary="Bullish expansion",
        confidence=0.9,
    )

    from src.agent_c_ibkr import PositionSizingChain

    chain = PositionSizingChain()

    # Base calculation (modifier = 1.0)
    base_result = chain.calculate(
        win_prob=0.5,
        r_r_ratio=2.0,
        balance=10000.0,
        account_value=10000.0,
        entry_price=100.0,
        stop_price=95.0,
        instrument="SPY",
        regime_modifier=1.0,
    )

    # Boosted calculation
    boosted_result = chain.calculate(
        win_prob=0.5,
        r_r_ratio=2.0,
        balance=10000.0,
        account_value=10000.0,
        entry_price=100.0,
        stop_price=95.0,
        instrument="SPY",
        regime_modifier=mock_state.risk_modifier,
    )

    assert boosted_result["risk_dollars"] > base_result["risk_dollars"]
    # 1.5x of the base risk (within the 4% hard cap)
    assert boosted_result["risk_dollars"] == pytest.approx(base_result["risk_dollars"] * 1.5)
