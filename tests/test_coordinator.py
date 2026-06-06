"""
Tests for TradingCoordinator logic and wiring.
"""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_coordinator():
    """Create a TradingCoordinator with a minimally mocked brain and bridge."""
    from coordinator import TradingCoordinator

    brain = MagicMock()
    brain.bus = None
    brain.current_regime = "TRENDING"
    brain._oracle_dhatu = "Sthiti"
    brain._vetting_cooldowns = {}
    brain.data_pipeline = None
    brain.ibkr_drawdown = MagicMock()
    brain.ibkr_drawdown.peak_equity = 5000.0
    brain.ibkr_drawdown.current_equity = 5000.0

    bridge = MagicMock()
    coord = TradingCoordinator(bridge, brain)
    return coord


class TestVoteMetrics:
    """Pure logic tests for _vote_metrics."""

    def test_empty_votes(self, mock_coordinator) -> None:
        result = mock_coordinator._vote_metrics([])
        assert result["yes_votes"] == 0.0
        assert result["active_voters"] == 0
        assert result["no_agents"] == []
        assert result["hard_no_agents"] == []
        assert result["avg_confidence"] == 0.0

    def test_all_yes(self, mock_coordinator) -> None:
        votes = [
            {"agent": "A", "vote": "YES", "confidence": 0.8},
            {"agent": "B", "vote": "YES", "confidence": 0.9},
        ]
        result = mock_coordinator._vote_metrics(votes)
        assert result["yes_votes"] == pytest.approx(2.0, 0.01)
        assert result["active_voters"] == 2
        assert result["no_agents"] == []
        assert result["avg_confidence"] == pytest.approx(0.85, 0.01)

    def test_agent_d_double_weight(self, mock_coordinator) -> None:
        votes = [
            {"agent": "Agent_D", "vote": "YES", "confidence": 0.9},
            {"agent": "A", "vote": "YES", "confidence": 0.5},
        ]
        result = mock_coordinator._vote_metrics(votes)
        assert result["yes_votes"] == pytest.approx(3.0, 0.01)

    def test_mixed_votes(self, mock_coordinator) -> None:
        votes = [
            {"agent": "A", "vote": "YES", "confidence": 0.8},
            {"agent": "B", "vote": "NO", "confidence": 0.9},
            {"agent": "C", "vote": "MAYBE", "confidence": 0.5},
        ]
        result = mock_coordinator._vote_metrics(votes)
        assert result["yes_votes"] == pytest.approx(1.0, 0.01)
        assert result["active_voters"] == 3
        assert result["no_agents"] == ["B"]
        assert result["hard_no_agents"] == []

    def test_hard_no(self, mock_coordinator) -> None:
        votes = [
            {"agent": "Risk_Guard", "vote": "NO", "confidence": 1.0},
            {"agent": "Agent_D", "vote": "NO", "confidence": 1.0},
        ]
        result = mock_coordinator._vote_metrics(votes)
        assert result["hard_no_agents"] == ["Risk_Guard", "Agent_D"]

    def test_missing_confidence_defaults(self, mock_coordinator) -> None:
        votes = [
            {"agent": "A", "vote": "YES"},
            {"agent": "B", "vote": "YES"},
        ]
        result = mock_coordinator._vote_metrics(votes)
        assert result["yes_votes"] == pytest.approx(2.0, 0.01)
        assert result["avg_confidence"] == 0.0

    def test_abstain_excluded(self, mock_coordinator) -> None:
        votes = [
            {"agent": "A", "vote": "ABSTAIN", "confidence": 0.9},
            {"agent": "B", "vote": "YES", "confidence": 0.8},
        ]
        result = mock_coordinator._vote_metrics(votes)
        assert result["active_voters"] == 1
        assert result["avg_confidence"] == pytest.approx(0.8, 0.01)


class TestEntryDataFreshness:
    """Last-mile orders require recent verified market-data evidence."""

    def test_paper_simulation_does_not_require_live_data_proof(self, mock_coordinator) -> None:
        mock_coordinator.brain.mode = "paper"

        assert mock_coordinator._entry_data_block_reason("SPY") is None

    def test_ibkr_entry_without_freshness_proof_is_blocked(self, mock_coordinator) -> None:
        mock_coordinator.brain.mode = "ibkr_paper"
        mock_coordinator.brain._last_fresh_bar_at = {}

        assert mock_coordinator._entry_data_block_reason("SPY") == "no verified fresh bar available"

    def test_ibkr_entry_with_recent_freshness_proof_is_allowed(self, mock_coordinator) -> None:
        mock_coordinator.brain.mode = "ibkr_paper"
        mock_coordinator.brain._last_fresh_bar_at = {"SPY": time.monotonic()}

        assert mock_coordinator._entry_data_block_reason("SPY") is None

    def test_ibkr_entry_with_realtime_tick_proof_is_allowed(self, mock_coordinator) -> None:
        mock_coordinator.brain.mode = "ibkr_paper"
        mock_coordinator.brain._last_fresh_bar_at = {}
        mock_coordinator.brain.data_pipeline = MagicMock()
        mock_coordinator.brain.data_pipeline.get_last_price.return_value = 501.25

        assert mock_coordinator._entry_data_block_reason("SPY") is None
        mock_coordinator.brain.data_pipeline.get_last_price.assert_called_once_with("SPY")

    def test_ibkr_entry_with_expired_freshness_proof_is_blocked(
        self, mock_coordinator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_coordinator.brain.mode = "ibkr_paper"
        mock_coordinator.brain._last_fresh_bar_at = {"SPY": time.monotonic() - 60.0}
        monkeypatch.setenv("SOVEREIGN_ENTRY_DATA_PROOF_MAX_AGE_SEC", "30")

        assert "expired" in mock_coordinator._entry_data_block_reason("SPY")

    def test_ibkr_entry_with_expired_bar_and_realtime_tick_is_allowed(
        self, mock_coordinator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_coordinator.brain.mode = "ibkr_paper"
        mock_coordinator.brain._last_fresh_bar_at = {"SPY": time.monotonic() - 60.0}
        mock_coordinator.brain.data_pipeline = MagicMock()
        mock_coordinator.brain.data_pipeline.get_last_price.return_value = 501.25
        monkeypatch.setenv("SOVEREIGN_ENTRY_DATA_PROOF_MAX_AGE_SEC", "30")

        assert mock_coordinator._entry_data_block_reason("SPY") is None


class TestExecutionFriction:
    """Execution cost estimation should use the wired slippage model safely."""

    def test_entry_friction_uses_spread_and_model_slippage(self, mock_coordinator) -> None:
        friction = mock_coordinator._estimate_entry_friction_per_share(
            entry_price=100.0,
            shares=10,
            spread_data={
                "bid": 99.99,
                "ask": 100.01,
                "spread": 0.02,
                "top_liquidity": 10000.0,
            },
        )

        assert friction > 0.02
        assert friction < 0.05

    def test_entry_friction_handles_missing_l2_liquidity(self, mock_coordinator) -> None:
        friction = mock_coordinator._estimate_entry_friction_per_share(
            entry_price=100.0,
            shares=10,
            spread_data={"bid": 99.99, "ask": 100.01, "spread": 0.02},
        )

        assert friction > 0.02
        assert friction == pytest.approx(0.045, abs=0.001)


class TestExecutionAlerts:
    """Telegram execution alerts should identify the actual broker-paper route."""

    def test_execution_alert_includes_ibkr_paper_context(self, mock_coordinator) -> None:
        mock_coordinator.brain.mode = "ibkr_paper"
        mock_coordinator.brain.active_broker = "IBKR"
        pattern = SimpleNamespace(
            name="opening_range_breakout",
            category="SCALP",
            entry=501.25,
            stop=499.75,
            target=505.50,
            r_r_ratio=2.3,
        )

        message = mock_coordinator._format_execution_alert(
            symbol="SPY",
            order_id=4812,
            pattern=pattern,
            order_side="BUY",
            intent="Scalp",
            shares=3,
            quorum_count=7,
            decision={
                "confidence": 0.64,
                "paper_exploration": True,
                "reason": "IBKR_PAPER_EXPLORATION near-miss accepted",
            },
            task_id="TASK-1",
        )

        assert "<b>Mode:</b> <code>IBKR_PAPER</code>" in message
        assert "<b>Broker:</b> IBKR" in message
        assert "<b>Order ID:</b> <code>4812</code>" in message
        assert "<b>Side / Method:</b> LONG Scalp" in message
        assert "<b>Pattern:</b> opening_range_breakout" in message
        assert "<b>Paper Exploration:</b> YES" in message
        assert "IBKR_PAPER_EXPLORATION" in message


class TestLifecycleBasics:
    """Smoke tests for coordinator lifecycle wiring."""

    @pytest.mark.asyncio
    async def test_initiate_trade_lifecycle_cooldown_blocks(self, mock_coordinator) -> None:
        """If a symbol is on cooldown, lifecycle should reject quickly."""
        from datetime import datetime, timezone

        mock_coordinator.brain._vetting_cooldowns["AAPL"] = datetime.now(timezone.utc)
        proposal = {"pattern": None, "task": None}
        result = await mock_coordinator.initiate_trade_lifecycle("AAPL", proposal, is_probe=False)
        assert result is False
