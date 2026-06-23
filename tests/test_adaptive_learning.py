import pytest

from adaptive_learning import LiveAdaptiveEngine, PatternFeedbackTracker


class TestPatternFeedbackTracker:
    def test_rolling_win_rate(self):
        tracker = PatternFeedbackTracker(lookback=10, min_sample=5)
        for i in range(7):
            tracker.record("AAPL", "VCP", "WIN" if i % 2 == 0 else "LOSS", 1.0, "BULL")
        assert tracker.rolling_win_rate("VCP", "BULL") == pytest.approx(4 / 7)

    def test_confidence_modifier_high_win_rate(self):
        tracker = PatternFeedbackTracker(lookback=10, min_sample=5)
        for _ in range(7):
            tracker.record("AAPL", "VCP", "WIN", 1.0, "BULL")
        assert tracker.confidence_modifier("VCP", "BULL") == 0.15

    def test_confidence_modifier_low_win_rate(self):
        tracker = PatternFeedbackTracker(lookback=10, min_sample=5)
        for _ in range(7):
            tracker.record("AAPL", "VCP", "LOSS", -1.0, "BULL")
        assert tracker.confidence_modifier("VCP", "BULL") == -0.15

    def test_insufficient_sample_returns_none(self):
        tracker = PatternFeedbackTracker(lookback=10, min_sample=5)
        for i in range(3):
            tracker.record("AAPL", "VCP", "WIN", 1.0, "BULL")
        assert tracker.rolling_win_rate("VCP", "BULL") is None


class TestLiveAdaptiveEngine:
    def test_ingest_trade_exit(self):
        engine = LiveAdaptiveEngine()
        engine.ingest_trade_exit(
            {"symbol": "AAPL", "pattern": "VCP", "pnl": 100.0, "r_multiple": 2.0, "regime": "BULL"}
        )
        assert len(engine.feedback._trades) == 1

    def test_recompute_updates_state(self):
        engine = LiveAdaptiveEngine()
        for _ in range(5):
            engine.ingest_trade_exit(
                {"symbol": "AAPL", "pattern": "VCP", "pnl": 100.0, "r_multiple": 2.0, "regime": "BULL"}
            )
        state = engine.recompute(force=True)
        assert state.pattern_confidence_mods.get("VCP", 0.0) > 0
        assert state.regime_permission_mods.get("BULL", 0.0) > 0

    def test_adjust_pattern_confidence(self):
        engine = LiveAdaptiveEngine()
        for _ in range(5):
            engine.ingest_trade_exit(
                {"symbol": "AAPL", "pattern": "VCP", "pnl": 100.0, "r_multiple": 2.0, "regime": "BULL"}
            )
        adjusted = engine.adjust_pattern_confidence("VCP", 70.0)
        assert adjusted > 70.0

    def test_streak_adjusts_interrogator_score(self):
        engine = LiveAdaptiveEngine()
        for _ in range(4):
            engine.ingest_trade_exit(
                {"symbol": "AAPL", "pattern": "VCP", "pnl": 100.0, "r_multiple": 2.0, "regime": "BULL"}
            )
        score = engine.adjust_interrogator_min_score()
        assert score < 0.65

    def test_negative_streak_raises_interrogator_score(self):
        engine = LiveAdaptiveEngine()
        for _ in range(4):
            engine.ingest_trade_exit(
                {"symbol": "AAPL", "pattern": "VCP", "pnl": -100.0, "r_multiple": -2.0, "regime": "BULL"}
            )
        score = engine.adjust_interrogator_min_score()
        assert score > 0.65

    def test_recompute_throttling(self):
        engine = LiveAdaptiveEngine()
        engine.recompute(force=True)
        state1 = engine._state
        state2 = engine.recompute()
        assert state1 is state2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
