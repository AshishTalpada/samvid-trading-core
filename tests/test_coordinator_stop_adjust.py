import pandas as pd
import pytest

from coordinator import TradingCoordinator


class FakeBrain:
    current_regime = "BULL"


class FakeBridge:
    pass


class FakePattern:
    def __init__(self, entry, stop, target, category="SCALP", name="Bull Flag"):
        self.name = name
        self.category = category
        self.entry = entry
        self.stop = stop
        self.target = target
        self.r_r_ratio = 2.0


def make_ohlcv(n=50, price=100.0, atr=1.0):
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-06-23 09:30", periods=n, freq="1min"),
        "open": [price] * n,
        "high": [price + atr] * n,
        "low": [price - atr] * n,
        "close": [price] * n,
        "volume": [1000] * n,
    })
    return df


@pytest.mark.asyncio
async def test_stop_adjustment_widens_tight_stop():
    coord = TradingCoordinator(FakeBridge(), FakeBrain())
    pattern = FakePattern(entry=100.0, stop=99.95, target=103.0)  # 0.05% stop
    ohlcv = make_ohlcv(price=100.0, atr=1.0)
    coord._apply_adaptive_stops("AAPL", pattern, ohlcv, "BULL")
    assert pattern.stop < 99.95, "tight long stop should be widened"
    assert pattern.r_r_ratio <= 5.0


@pytest.mark.asyncio
async def test_stop_adjustment_respects_wide_stop():
    coord = TradingCoordinator(FakeBridge(), FakeBrain())
    pattern = FakePattern(entry=100.0, stop=95.0, target=110.0)  # 5% stop
    ohlcv = make_ohlcv(price=100.0, atr=1.0)
    coord._apply_adaptive_stops("AAPL", pattern, ohlcv, "BULL")
    assert pattern.stop == 95.0, "already-wide stop should not be changed"


@pytest.mark.asyncio
async def test_stop_adjustment_short_tight_stop():
    coord = TradingCoordinator(FakeBridge(), FakeBrain())
    pattern = FakePattern(entry=100.0, stop=100.05, target=97.0)  # 0.05% stop
    ohlcv = make_ohlcv(price=100.0, atr=1.0)
    coord._apply_adaptive_stops("AAPL", pattern, ohlcv, "BULL")
    assert pattern.stop > 100.05, "tight short stop should be widened"


@pytest.mark.asyncio
async def test_stop_adjustment_no_ohlcv():
    coord = TradingCoordinator(FakeBridge(), FakeBrain())
    pattern = FakePattern(entry=100.0, stop=99.95, target=103.0)
    coord._apply_adaptive_stops("AAPL", pattern, None, "BULL")
    assert pattern.stop == 99.95


@pytest.mark.asyncio
async def test_directional_regime_guard_blocks_long_breakout_in_choppy():
    coord = TradingCoordinator(FakeBridge(), FakeBrain())
    pattern = FakePattern(entry=100.0, stop=99.0, target=103.0, name="Rising Wedge")
    result = coord._apply_directional_regime_guard("AAPL", pattern, "CHOPPY")
    assert result is not None, "Rising Wedge LONG in CHOPPY should be blocked"
    assert "blocked" in result


@pytest.mark.asyncio
async def test_directional_regime_guard_allows_short_in_choppy():
    coord = TradingCoordinator(FakeBridge(), FakeBrain())
    pattern = FakePattern(entry=100.0, stop=101.0, target=97.0, name="Rising Wedge")
    result = coord._apply_directional_regime_guard("AAPL", pattern, "CHOPPY")
    assert result is None, "SHORT Rising Wedge in CHOPPY should be allowed"


@pytest.mark.asyncio
async def test_directional_regime_guard_allows_long_in_bull():
    coord = TradingCoordinator(FakeBridge(), FakeBrain())
    pattern = FakePattern(entry=100.0, stop=99.0, target=103.0, name="Rising Wedge")
    result = coord._apply_directional_regime_guard("AAPL", pattern, "BULL")
    assert result is None, "Rising Wedge LONG in BULL should be allowed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
