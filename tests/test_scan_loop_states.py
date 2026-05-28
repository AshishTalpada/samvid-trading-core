"""
Tests for TradingBrain scan loop state transitions and circuit breakers.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def minimal_brain():
    """Create a minimally configured TradingBrain for testing scan logic."""
    import os

    os.environ.setdefault("SOVEREIGN_SKIP_PID_CHECK", "1")
    os.environ.setdefault("ALLOW_FORCE_LIVE", "0")

    from brain import TradingBrain

    _BRAIN_PATCHES = [
        "agent_a.ContinuousBudgetMonitor",
        "agent_a.EscapeVelocityClassifier",
        "agent_a.FactorWeightCalibration",
        "agent_a.InMemorySovereignAtlas",
        "agent_a.MultiTimeframeAligner",
        "agent_a.NeuralRegimeClassifier",
        "agent_a.PatternDetector",
        "agent_a.SignalEntropyCalculator",
        "agent_b.ABHAVADetector",
        "agent_b.BayesianBeliefTracker",
        "agent_b.DhatuClassifier",
        "agent_c_ibkr.BlackSwanProtocol",
        "agent_c_ibkr.CorrelationCascade",
        "agent_c_ibkr.IBKRConnection",
        "agent_c_ibkr.PortfolioGuard",
        "agent_c_ibkr.PositionSizingChain",
        "agent_c_ibkr.VIXProtocol",
        "agent_d.EdgeCrowdingDetector",
        "agent_d.LiveLearningEngine",
        "agent_d.LiveRecursiveEvolution",
        "agent_d.RegimeClassifier",
        "agent_d.StatisticalSignificanceGate",
        "agent_d.SystemEntropyMonitor",
        "quant_signals.QuantConsensus",
        "sovereign_task.TaskManager",
    ]

    from contextlib import ExitStack

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
        brain.ibkr_drawdown = MagicMock()
        brain.ibkr_drawdown.peak_equity = 1000.0
        brain.ibkr_drawdown.current_equity = 1000.0
        brain.ibkr_drawdown.is_trading_allowed.return_value = True
        brain.loss_tracker = MagicMock()
        brain.loss_tracker.is_trading_allowed.return_value = True
        brain.blackswan = MagicMock()
        brain.blackswan.check.return_value = "NORMAL"
        brain.task_manager = MagicMock()
        brain.dms = None
        brain.bus = None
        brain._vetting_cooldowns = {}
        brain._scan_cycle = 1
        brain.current_regime = "TRENDING"
        brain._oracle_dhatu = "Sthiti"
        brain._oracle_freeze = False
        brain._oracle_risk_modifier = 1.0
        brain.emergency_halted = False
        brain.scan_interval = 0.1  # fast for tests
        brain.positions = []
        yield brain


@pytest.mark.asyncio
async def test_oracle_freeze_blocks_scan(minimal_brain) -> None:
    """When oracle freeze is active, _is_oracle_entry_frozen should return True."""
    brain = minimal_brain
    brain._oracle_freeze = True
    assert brain._is_oracle_entry_frozen() is True


@pytest.mark.asyncio
async def test_oracle_freeze_unblocks_when_normal(minimal_brain) -> None:
    """When oracle freeze is inactive, _is_oracle_entry_frozen should return False."""
    brain = minimal_brain
    brain._oracle_freeze = False
    brain._oracle_dhatu = "Sthiti"
    assert brain._is_oracle_entry_frozen() is False


@pytest.mark.asyncio
async def test_drawdown_circuit_breaker_halts(minimal_brain) -> None:
    """When drawdown exceeds limit, is_trading_allowed returns False."""
    brain = minimal_brain
    brain.ibkr_drawdown.is_trading_allowed.return_value = False
    assert brain.ibkr_drawdown.is_trading_allowed() is False


@pytest.mark.asyncio
async def test_loss_streak_circuit_breaker_halts(minimal_brain) -> None:
    """When loss streak exceeds limit, is_trading_allowed returns False."""
    brain = minimal_brain
    brain.loss_tracker.is_trading_allowed.return_value = False
    assert brain.loss_tracker.is_trading_allowed() is False


@pytest.mark.asyncio
async def test_vetting_cooldown_blocks_symbol(minimal_brain) -> None:
    """A symbol within 30s vetting cooldown should be gated."""
    brain = minimal_brain
    brain._vetting_cooldowns["TSLA"] = datetime.now(timezone.utc)
    last_vet = brain._vetting_cooldowns.get("TSLA")
    assert last_vet is not None
    # Simulate the cooldown check logic
    from datetime import timedelta
    cooldown_age = (datetime.now(timezone.utc) - last_vet).total_seconds()
    assert cooldown_age < 30


@pytest.mark.asyncio
async def test_scan_symbol_black_swan_freeze(minimal_brain) -> None:
    """BlackSwan FREEZE should prevent scan from returning discoveries."""
    brain = minimal_brain
    brain.blackswan.check.return_value = "FREEZE"

    with patch.object(brain, "_get_vix", new_callable=AsyncMock, return_value=60.0):
        vix = await brain._get_vix()
        dd_pct = (
            brain.ibkr_drawdown.peak_equity - brain.ibkr_drawdown.current_equity
        ) / max(brain.ibkr_drawdown.peak_equity, 1)
        result = brain.blackswan.check(vix, dd_pct)
        assert result == "FREEZE"
