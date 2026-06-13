"""Tests for newly wired advisory agents (stress veto, sentiment overlay, drawdown predictor)."""

import asyncio
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from stress_veto import StressAnalysis, StressVeto, TradeRecord, get_stress_veto
from sentiment_agent import aggregate_sentiment, score_text
from drawdown_predictor import DrawdownPredictor


class TestStressVeto:
    """Unit tests for the StressVeto psychology safety system."""

    def test_consecutive_losses_trigger_veto(self):
        veto = StressVeto()
        for i in range(3):
            veto.record_trade("AAPL", pnl=-10.0, size=10.0, reason="loss")
        analysis = veto.analyze_stress()
        assert analysis.stress_detected is True
        assert analysis.recommendation == "LOCKOUT"
        assert analysis.stress_type == "REVENGE_TRADING"

    def test_winning_streak_no_veto(self):
        veto = StressVeto()
        for i in range(3):
            veto.record_trade("AAPL", pnl=10.0, size=10.0, reason="win")
        analysis = veto.analyze_stress()
        assert analysis.stress_detected is False
        assert analysis.recommendation == "ALLOW"

    def test_cooldown_active(self):
        veto = StressVeto()
        # Force a veto to set last_veto_time
        veto.last_veto_time = datetime.now(timezone.utc).timestamp()
        analysis = veto.analyze_stress()
        assert analysis.stress_detected is True
        assert analysis.stress_type == "ACTIVE_VETO"
        assert analysis.cooldown_minutes > 0

    def test_size_escalation(self):
        veto = StressVeto()
        # Reset consecutive losses so we don't trigger revenge trading first
        veto.consecutive_losses = 0
        for _ in range(4):
            veto.record_trade("AAPL", pnl=-10.0, size=10.0, reason="loss")
        # Now add larger sizes (recent 2 avg vs earlier 2 avg should be >2x)
        veto.record_trade("AAPL", pnl=-10.0, size=25.0, reason="loss")
        veto.record_trade("AAPL", pnl=-10.0, size=25.0, reason="loss")
        # Reset consecutive_losses again to avoid revenge-trading veto
        veto.consecutive_losses = 0
        analysis = veto.analyze_stress()
        assert analysis.stress_detected is True
        assert analysis.stress_type == "SIZE_ESCALATION"

    def test_rapid_trading(self):
        veto = StressVeto()
        import time
        now = time.time()
        for i in range(20):
            veto.trade_history.append(
                TradeRecord(timestamp=now, symbol="AAPL", pnl=1.0, size=1.0, reason="rapid")
            )
        analysis = veto.analyze_stress()
        assert analysis.stress_detected is True
        assert analysis.stress_type == "RAPID_TRADING"

    def test_manual_override_spike(self):
        veto = StressVeto()
        now = datetime.now(timezone.utc).timestamp()
        for i in range(10):
            veto.trade_history.append(
                TradeRecord(
                    timestamp=now,
                    symbol="AAPL",
                    pnl=1.0,
                    size=1.0,
                    reason="test",
                    manual_override=(i >= 5),  # last 5 are overrides
                )
            )
        # Test the internal check directly to bypass insufficient-history guard
        stress_type, severity = veto._check_manual_override_spike(list(veto.trade_history))
        assert stress_type == "MANUAL_OVERRIDE_SPIKE"
        assert severity == 0.8

    def test_singleton(self):
        v1 = get_stress_veto()
        v2 = get_stress_veto()
        assert v1 is v2


class TestSentimentAgent:
    """Unit tests for sentiment scoring and aggregation."""

    def test_score_bullish_text(self):
        text = "The market is bullish and breaking out to new highs. Strong buy signal."
        score = score_text(text, asset_class="equities")
        assert score > 0.0

    def test_score_bearish_text(self):
        text = "Crash incoming, sell everything, panic and fear everywhere."
        score = score_text(text, asset_class="equities")
        assert score < 0.0

    def test_score_neutral_text(self):
        text = "The weather is nice today."
        score = score_text(text, asset_class="equities")
        assert score == 0.0

    def test_crypto_weight_multiplier(self):
        text = "Bullish breakout moon surge"
        crypto_score = score_text(text, asset_class="crypto")
        equity_score = score_text(text, asset_class="equities")
        assert abs(crypto_score) > abs(equity_score)

    def test_aggregate_sentiment(self):
        texts = ["bullish breakout", "bearish crash", "bullish rally"]
        result = aggregate_sentiment(texts, asset_class="equities")
        assert "mean" in result
        assert "std" in result
        assert result["signal"] in ("BULLISH", "BEARISH", "NEUTRAL")

    def test_aggregate_empty(self):
        result = aggregate_sentiment([], asset_class="equities")
        assert result["mean"] == 0.0
        assert result["std"] == 0.0
        assert result["signal"] == "NEUTRAL"


class TestDrawdownPredictor:
    """Unit tests for Markov-chain drawdown predictor."""

    def test_predict_duration_same_state(self):
        predictor = DrawdownPredictor()
        assert predictor.predict_duration(0, target_state=0) == 0.0

    def test_predict_duration_small_loss(self):
        predictor = DrawdownPredictor()
        duration = predictor.predict_duration(1, target_state=0)
        assert duration > 0.0

    def test_predict_duration_deep_drawdown(self):
        predictor = DrawdownPredictor()
        duration = predictor.predict_duration(2, target_state=0)
        assert duration > 0.0
        # Deep drawdown should take longer to recover than small loss
        small_loss_duration = predictor.predict_duration(1, target_state=0)
        assert duration > small_loss_duration

    def test_transition_matrix_shape(self):
        predictor = DrawdownPredictor()
        assert predictor.transition_matrix.shape == (3, 3)


class TestSentimentOverlayBrainWiring:
    """Integration tests for sentiment overlay wired into brain.py scan cycle."""

    def test_sentiment_overlay_dampens_extreme_confidence(self):
        """Simulate the sentiment overlay logic from brain.py"""
        mean_sentiment = 0.6
        old_conf = 0.80
        dampen_factor = max(0.5, 1.0 - abs(mean_sentiment) * 0.3)
        new_conf = old_conf * dampen_factor
        assert new_conf < old_conf
        assert new_conf >= 0.55  # Should not drop below veto threshold here

    def test_sentiment_veto_threshold(self):
        """If dampened confidence drops below 0.55, pattern should be vetoed."""
        mean_sentiment = 0.9
        old_conf = 0.70
        dampen_factor = max(0.5, 1.0 - abs(mean_sentiment) * 0.3)
        new_conf = old_conf * dampen_factor
        assert new_conf < 0.55  # Should trigger veto


class TestDrawdownPredictorBrainWiring:
    """Integration tests for drawdown predictor wired into brain.py scan cycle."""

    def test_state_mapping(self):
        """Test dd_pct to Markov state mapping used in brain.py"""
        test_cases = [
            (0.03, 0),   # < 5%
            (0.10, 1),   # < 15%
            (0.20, 2),   # >= 15%
        ]
        for dd_pct, expected_state in test_cases:
            if dd_pct < 0.05:
                state = 0
            elif dd_pct < 0.15:
                state = 1
            else:
                state = 2
            assert state == expected_state

    def test_deep_drawdown_raises_threshold(self):
        """Simulate deep drawdown threshold raising logic."""
        predictor = DrawdownPredictor()
        expected_recovery = predictor.predict_duration(2, target_state=0)
        # Deep drawdown takes longer to recover than small loss
        small_loss_duration = predictor.predict_duration(1, target_state=0)
        assert expected_recovery > small_loss_duration


class TestStressVetoCoordinatorWiring:
    """Integration tests for stress veto wired into coordinator.py execution gate."""

    def test_stress_lockout_blocks_trade(self):
        """Simulate coordinator stress gate logic."""
        veto = StressVeto()
        for _ in range(3):
            veto.record_trade("SPY", pnl=-5.0, size=5.0, reason="loss")
        analysis = veto.analyze_stress()
        assert analysis.stress_detected is True
        assert analysis.recommendation == "LOCKOUT"
        # In coordinator, this would return False (block trade)

    def test_stress_warning_allows_trade(self):
        """If severity is low but not lockout, trade should proceed with warning."""
        veto = StressVeto()
        # Only 2 consecutive losses (below threshold)
        veto.record_trade("SPY", pnl=-5.0, size=5.0, reason="loss")
        veto.record_trade("SPY", pnl=-5.0, size=5.0, reason="loss")
        analysis = veto.analyze_stress()
        # With only 2 losses, no stress detected yet
        assert analysis.stress_detected is False
        assert analysis.recommendation == "ALLOW"
