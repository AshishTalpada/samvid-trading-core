import polars as pl
import pytest

from confluence_engine import ConfluenceEngine, ConfluenceResult, _higher_timeframes


def _make_df(trend: str, n: int = 60) -> pl.DataFrame:
    """Create a Polars DataFrame with a controlled trend."""
    if trend == "up":
        close = pl.Series("close", [100.0 + i * 0.1 for i in range(n)])
    elif trend == "down":
        close = pl.Series("close", [100.0 - i * 0.1 for i in range(n)])
    elif trend == "flat":
        close = pl.Series("close", [100.0 + (i % 2) * 0.01 for i in range(n)])
    else:
        raise ValueError(trend)
    return pl.DataFrame(
        {
            "timestamp": list(range(n)),
            "open": close,
            "high": close + 0.05,
            "low": close - 0.05,
            "close": close,
            "volume": pl.Series("volume", [1000.0] * n),
        }
    )


class TestHigherTimeframes:
    def test_higher_timeframes_15m(self):
        assert _higher_timeframes("15m") == ["15m", "1h", "4h"]

    def test_higher_timeframes_5m(self):
        assert _higher_timeframes("5m") == ["5m", "15m", "1h"]

    def test_higher_timeframes_unknown(self):
        assert _higher_timeframes("30m") == ["30m"]


class TestConfluenceEngine:
    @pytest.mark.asyncio
    async def test_passes_long_bullish_alignment(self):
        engine = ConfluenceEngine(min_score=0.70)

        async def fetch(sym, tf):
            return _make_df("up")

        result = await engine.evaluate("AAPL", "LONG", "5m", fetch)
        assert isinstance(result, ConfluenceResult)
        assert result.passed
        assert result.score >= 0.70
        assert "15m" in result.checked_timeframes

    @pytest.mark.asyncio
    async def test_fails_long_bearish_alignment(self):
        engine = ConfluenceEngine(min_score=0.70)

        async def fetch(sym, tf):
            return _make_df("down")

        result = await engine.evaluate("AAPL", "LONG", "5m", fetch)
        assert not result.passed

    @pytest.mark.asyncio
    async def test_passes_short_bearish_alignment(self):
        engine = ConfluenceEngine(min_score=0.70)

        async def fetch(sym, tf):
            return _make_df("down")

        result = await engine.evaluate("AAPL", "SHORT", "5m", fetch)
        assert result.passed
        assert result.score >= 0.70

    @pytest.mark.asyncio
    async def test_fails_short_bullish_alignment(self):
        engine = ConfluenceEngine(min_score=0.70)

        async def fetch(sym, tf):
            return _make_df("up")

        result = await engine.evaluate("AAPL", "SHORT", "5m", fetch)
        assert not result.passed

    @pytest.mark.asyncio
    async def test_fails_insufficient_data(self):
        engine = ConfluenceEngine(min_score=0.70)

        async def fetch(sym, tf):
            return None

        result = await engine.evaluate("AAPL", "LONG", "5m", fetch)
        assert not result.passed
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_fails_below_min_timeframes(self):
        engine = ConfluenceEngine(min_score=0.70, min_timeframes=5)

        async def fetch(sym, tf):
            return _make_df("up")

        result = await engine.evaluate("AAPL", "LONG", "15m", fetch)
        assert not result.passed
        assert "need 5" in result.reasons[-1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
