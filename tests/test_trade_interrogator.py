from dataclasses import dataclass

import pytest

from market_microstructure import MarketMicrostructure
from trade_interrogator import TradeInterrogator


@dataclass
class _Pattern:
    name: str
    entry: float
    stop: float
    target: float


@pytest.fixture
def micro():
    return MarketMicrostructure()


@pytest.fixture
def interrogator(micro):
    return TradeInterrogator(microstructure=micro, min_score=0.65)


class TestTradeInterrogator:
    def _seed_liquid(self, micro, symbol, price, direction="buy", size=100, n=20):
        for _ in range(n):
            micro.on_tick(
                {
                    "symbol": symbol,
                    "price": price,
                    "bid": price * 0.99999,
                    "ask": price * 1.00001,
                    "size": size,
                    "is_buy": direction == "buy",
                }
            )

    def test_passes_liquid_bullish_setup(self, interrogator):
        micro = interrogator.microstructure
        self._seed_liquid(micro, "AAPL", 150.0)
        pattern = _Pattern("VCP (Minervini Pivot)", 150.0, 149.0, 152.0)
        result = interrogator.interrogate(
            "AAPL",
            pattern,
            {"direction": "LONG"},
            current_regime="BULL",
            pattern_stats={"win_rate": 0.60, "sample_size": 20},
        )
        assert result.passed
        assert result.score >= 0.65

    def test_fails_bad_regime(self, interrogator):
        micro = interrogator.microstructure
        self._seed_liquid(micro, "META", 300.0)
        pattern = _Pattern("Rising Wedge", 300.0, 301.0, 298.0)
        result = interrogator.interrogate(
            "META",
            pattern,
            {"direction": "SHORT"},
            current_regime="RISK_OFF",
            pattern_stats={"win_rate": 0.60, "sample_size": 20},
        )
        assert not result.passed
        assert any("Regime" in r for r in result.reasons)

    def test_fails_illiquid(self, interrogator):
        micro = interrogator.microstructure
        micro.on_tick({"symbol": "ILLIQ", "price": 100.0, "bid": 90.0, "ask": 110.0, "size": 100})
        pattern = _Pattern("Deep Tape Absorption", 100.0, 99.0, 102.0)
        result = interrogator.interrogate(
            "ILLIQ",
            pattern,
            {"direction": "LONG"},
            current_regime="BULL",
            pattern_stats={"win_rate": 0.60, "sample_size": 20},
        )
        assert not result.passed
        assert any("Illiquid" in r for r in result.reasons)

    def test_fails_low_rr(self, interrogator):
        micro = interrogator.microstructure
        self._seed_liquid(micro, "SPY", 400.0)
        pattern = _Pattern("Bull Flag", 400.0, 399.0, 400.2)
        result = interrogator.interrogate(
            "SPY",
            pattern,
            {"direction": "LONG"},
            current_regime="BULL",
            pattern_stats={"win_rate": 0.60, "sample_size": 20},
        )
        assert not result.passed
        assert any("R:R" in r for r in result.reasons)

    def test_fails_weak_pattern_edge(self, interrogator):
        micro = interrogator.microstructure
        self._seed_liquid(micro, "QQQ", 350.0)
        pattern = _Pattern("VCP (Minervini Pivot)", 350.0, 349.0, 352.0)
        result = interrogator.interrogate(
            "QQQ",
            pattern,
            {"direction": "LONG"},
            current_regime="BULL",
            pattern_stats={"win_rate": 0.30, "sample_size": 20},
        )
        assert not result.passed
        assert any("weak edge" in r for r in result.reasons)

    def test_fails_against_order_flow(self, interrogator):
        micro = interrogator.microstructure
        self._seed_liquid(micro, "AMD", 120.0, direction="sell", size=200)
        pattern = _Pattern("Deep Tape Absorption", 120.0, 119.0, 122.0)
        result = interrogator.interrogate(
            "AMD",
            pattern,
            {"direction": "LONG"},
            current_regime="BULL",
            pattern_stats={"win_rate": 0.60, "sample_size": 20},
        )
        assert not result.passed
        assert any("Order flow" in r for r in result.reasons)

    def test_fails_chasing_vwap(self, interrogator):
        micro = interrogator.microstructure
        for i in range(20):
            micro.on_tick(
                {
                    "symbol": "NVDA",
                    "price": 100.0 + i * 5,
                    "bid": 100.0 + i * 5 - 0.01,
                    "ask": 100.0 + i * 5 + 0.01,
                    "size": 100,
                    "is_buy": True,
                }
            )
        pattern = _Pattern("Momentum", 200.0, 195.0, 210.0)
        result = interrogator.interrogate(
            "NVDA",
            pattern,
            {"direction": "LONG"},
            current_regime="BULL",
            pattern_stats={"win_rate": 0.60, "sample_size": 20},
        )
        assert not result.passed
        assert any("VWAP" in r for r in result.reasons)

    def test_details_populated(self, interrogator):
        micro = interrogator.microstructure
        micro.on_tick({"symbol": "TSLA", "price": 250.0, "bid": 249.99, "ask": 250.01, "size": 100})
        pattern = _Pattern("VCP (Minervini Pivot)", 250.0, 249.0, 252.0)
        result = interrogator.interrogate(
            "TSLA",
            pattern,
            {"direction": "LONG"},
            current_regime="BULL",
            pattern_stats={"win_rate": 0.60, "sample_size": 20},
        )
        assert "regime" in result.details
        assert "microstructure" in result.details
        assert "pattern_stats" in result.details


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
