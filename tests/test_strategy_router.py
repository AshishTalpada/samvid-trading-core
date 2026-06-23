import pytest

from strategy_router import (
    BLOCKLIST_1M,
    PATTERN_TIMEFRAMES,
    REGIME_ALLOWED_PATTERNS,
    RegimeStrategyRouter,
    RouteResult,
    TimeframeAwareDetector,
)


class MockPatternResult:
    def __init__(self, name, confidence=70.0):
        self.name = name
        self.confidence = confidence


class MockDetector:
    def _contains(self, df, token):
        return any(token in str(item) for item in df)

    def detect_vcp_pattern(self, df):
        if self._contains(df, "VCP"):
            return MockPatternResult("VCP (Minervini Pivot)")
        return None

    def detect_bull_flag(self, df):
        if self._contains(df, "BULL"):
            return MockPatternResult("Bull Flag")
        return None

    def detect_deep_tape_absorption(self, df):
        if self._contains(df, "TAPE"):
            return MockPatternResult("Deep Tape Absorption")
        return None


class TestRegimeStrategyRouter:
    def test_route_allows_bull_vcp(self):
        router = RegimeStrategyRouter()
        route = router.route("VCP (Minervini Pivot)", "BULL")
        assert route.allowed
        assert route.timeframe == "15m"

    def test_route_blocks_vcp_in_choppy(self):
        router = RegimeStrategyRouter()
        route = router.route("VCP (Minervini Pivot)", "CHOPPY")
        assert not route.allowed
        assert "not allowed" in route.reason

    def test_route_blocks_blocklisted_1m(self):
        router = RegimeStrategyRouter()
        # Micro Imbalance is allowed in CHOPPY but blocklisted on 1m.
        route = router.route("Micro Imbalance (Bullish)", "CHOPPY")
        assert not route.allowed
        assert "blocklisted" in route.reason

    def test_allowed_patterns_bull(self):
        router = RegimeStrategyRouter()
        allowed = router.allowed_patterns("BULL")
        assert "VCP (Minervini Pivot)" in allowed
        assert "Bull Flag" in allowed
        assert "Deep Tape Absorption" in allowed

    def test_allowed_patterns_risk_off_empty(self):
        router = RegimeStrategyRouter()
        assert router.allowed_patterns("RISK_OFF") == []

    def test_patterns_for_timeframe(self):
        router = RegimeStrategyRouter()
        bull_15m = router.patterns_for_timeframe("BULL", "15m")
        assert "VCP (Minervini Pivot)" in bull_15m
        assert "Deep Tape Absorption" not in bull_15m


class TestTimeframeAwareDetector:
    @pytest.mark.asyncio
    async def test_detects_allowed_patterns(self):
        router = RegimeStrategyRouter()
        detector = TimeframeAwareDetector(MockDetector(), router)

        async def fetch(sym, tf):
            return [f"VCP_BULL_TAPE_{tf}"] * 50

        results = await detector.detect_for_regime("AAPL", "BULL", fetch)
        names = {r.name for r in results}
        assert "VCP (Minervini Pivot)" in names
        # Bull Flag is on 5m so it is allowed, and mock returns it when "BULL" is in df.
        assert "Bull Flag" in names

    @pytest.mark.asyncio
    async def test_no_results_for_risk_off(self):
        detector = TimeframeAwareDetector(MockDetector())

        async def fetch(sym, tf):
            return ["VCP_BULL_TAPE"] * 50

        results = await detector.detect_for_regime("AAPL", "RISK_OFF", fetch)
        assert results == []

    @pytest.mark.asyncio
    async def test_filters_by_timeframe(self):
        router = RegimeStrategyRouter()
        detector = TimeframeAwareDetector(MockDetector(), router)

        async def fetch(sym, tf):
            # 15m data only triggers VCP; 5m/1m data would also trigger Bull/TAPE.
            return [f"VCP_{tf}_DATA"] * 50

        results = await detector.detect_for_regime("AAPL", "BULL", fetch, timeframe="15m")
        names = {r.name for r in results}
        assert names == {"VCP (Minervini Pivot)"}
        for r in results:
            assert r.timeframe == "15m"

    @pytest.mark.asyncio
    async def test_handles_fetch_failure(self):
        detector = TimeframeAwareDetector(MockDetector())

        async def fetch(sym, tf):
            raise RuntimeError("boom")

        results = await detector.detect_for_regime("AAPL", "BULL", fetch)
        assert results == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
