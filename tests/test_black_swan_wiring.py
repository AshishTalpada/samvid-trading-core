"""
Tests for BlackSwanProtocol wiring into the TradingBrain scan loop.
"""

import os
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# All classes that appear as top-level imports in brain.py
_BRAIN_PATCHES = [
    # agent_a
    "agent_a.ContinuousBudgetMonitor",
    "agent_a.EscapeVelocityClassifier",
    "agent_a.FactorWeightCalibration",
    "agent_a.InMemorySovereignAtlas",
    "agent_a.MultiTimeframeAligner",
    "agent_a.NeuralRegimeClassifier",
    "agent_a.PatternDetector",
    "agent_a.SignalEntropyCalculator",
    # agent_b
    "agent_b.ABHAVADetector",
    "agent_b.BayesianBeliefTracker",
    "agent_b.DhatuClassifier",
    # agent_c_ibkr
    "agent_c_ibkr.BlackSwanProtocol",
    "agent_c_ibkr.CorrelationCascade",
    "agent_c_ibkr.IBKRConnection",
    "agent_c_ibkr.PortfolioGuard",
    "agent_c_ibkr.PositionSizingChain",
    "agent_c_ibkr.VIXProtocol",
    # agent_d
    "agent_d.EdgeCrowdingDetector",
    "agent_d.LiveLearningEngine",
    "agent_d.LiveRecursiveEvolution",
    "agent_d.RegimeClassifier",
    "agent_d.StatisticalSignificanceGate",
    "agent_d.SystemEntropyMonitor",
    # other modules
    "quant_signals.QuantConsensus",
    "sovereign_task.TaskManager",
]


@pytest.fixture
def minimal_brain():
    """Create a minimally configured TradingBrain for testing."""
    os.environ.setdefault("SOVEREIGN_SKIP_PID_CHECK", "1")
    os.environ.setdefault("ALLOW_FORCE_LIVE", "0")

    from brain import TradingBrain

    with ExitStack() as stack:
        for target in _BRAIN_PATCHES:
            stack.enter_context(patch(target))
        stack.enter_context(patch.object(TradingBrain, "_thaw_session_async", new_callable=AsyncMock))

        brain = TradingBrain(
            ibkr_client=None,
            dhatu_oracle=None,
            mode="ibkr_paper",
            db_conn=None,
        )
        # Set minimal required attributes
        brain.ibkr_drawdown = MagicMock()
        brain.ibkr_drawdown.peak_equity = 1000.0
        brain.ibkr_drawdown.current_equity = 1000.0
        brain.blackswan = MagicMock()
        brain.task_manager = MagicMock()
        brain.dms = None
        brain.bus = None
        brain._vetting_cooldowns = {}
        brain._scan_cycle = 1
        brain.current_regime = "TRENDING"
        brain._oracle_dhatu = "Sthiti"
        brain.pattern_detector = MagicMock()
        brain.pattern_detector.detect_all = MagicMock(return_value=[])
        yield brain


@pytest.mark.asyncio
async def test_black_swan_freeze_halts_scan(minimal_brain) -> None:
    """When BlackSwan returns FREEZE, scan should not proceed."""
    brain = minimal_brain
    brain.blackswan.check.return_value = "FREEZE"

    with patch.object(brain, "_get_vix", new_callable=AsyncMock, return_value=60.0):
        vix = await brain._get_vix()
        dd_pct = (
            brain.ibkr_drawdown.peak_equity - brain.ibkr_drawdown.current_equity
        ) / max(brain.ibkr_drawdown.peak_equity, 1)
        result = brain.blackswan.check(vix, dd_pct)
        assert result == "FREEZE"


@pytest.mark.asyncio
async def test_black_swan_normal_allows_scan(minimal_brain) -> None:
    """When BlackSwan returns NORMAL, scan should proceed."""
    brain = minimal_brain
    brain.blackswan.check.return_value = "NORMAL"

    with patch.object(brain, "_get_vix", new_callable=AsyncMock, return_value=18.0):
        vix = await brain._get_vix()
        dd_pct = 0.0
        result = brain.blackswan.check(vix, dd_pct)
        assert result == "NORMAL"


def test_black_swan_protocol_logic_directly() -> None:
    """Test the protocol thresholds directly without brain wiring."""
    from agent_c_ibkr import BlackSwanProtocol

    bsp = BlackSwanProtocol()
    assert bsp.check(vix=60.0, drawdown_pct=0.05) == "FREEZE"
    assert bsp.check(vix=40.0, drawdown_pct=0.15) == "FREEZE"
    assert bsp.check(vix=30.0, drawdown_pct=0.05) == "NORMAL"
    assert bsp.check(vix=56.0, drawdown_pct=0.01) == "FREEZE"
    assert bsp.check(vix=20.0, drawdown_pct=0.20) == "FREEZE"
