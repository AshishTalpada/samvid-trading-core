import time

import pytest

from market_microstructure import (
    MarketMicrostructure,
    MicrostructureSnapshot,
    get_imbalance,
    get_pressure,
    get_vwap_deviation,
    ingest_tick,
    is_liquid,
    reset,
    reset_global_microstructure,
)


@pytest.fixture(autouse=True)
def _reset_micro():
    reset_global_microstructure()
    yield


class TestMarketMicrostructure:
    def test_ingest_tick_basic(self):
        micro = MarketMicrostructure()
        micro.on_tick(
            {
                "symbol": "AAPL",
                "price": 150.0,
                "bid": 149.99,
                "ask": 150.01,
                "size": 100,
            }
        )
        snap = micro.get_snapshot("AAPL")
        assert snap.last_price == 150.0
        assert snap.bid == 149.99
        assert snap.ask == 150.01
        assert snap.spread == pytest.approx(0.02)
        assert snap.mid == 150.0

    def test_global_helpers(self):
        for _ in range(20):
            ingest_tick({"symbol": "TSLA", "price": 200.0, "bid": 199.999, "ask": 200.001, "size": 100})
        assert is_liquid("TSLA")
        # With no explicit side, all ticks are inferred as buys at the mid → fully buy-side imbalance.
        assert get_imbalance("TSLA") == 1.0
        assert get_vwap_deviation("TSLA") == 0.0
        reset()

    def test_vwap_computation(self):
        micro = MarketMicrostructure()
        for i in range(10):
            micro.on_tick(
                {
                    "symbol": "MSFT",
                    "price": 100.0 + i,
                    "bid": 100.0 + i - 0.01,
                    "ask": 100.0 + i + 0.01,
                    "size": float(i + 1),
                }
            )
        snap = micro.get_snapshot("MSFT")
        weighted = sum((100.0 + i) * (i + 1) for i in range(10)) / sum(i + 1 for i in range(10))
        assert snap.vwap == pytest.approx(weighted, abs=1e-6)

    def test_imbalance_and_pressure(self):
        micro = MarketMicrostructure()
        for _ in range(5):
            micro.on_tick(
                {
                    "symbol": "NVDA",
                    "price": 300.0,
                    "bid": 299.99,
                    "ask": 300.01,
                    "size": 200.0,
                    "is_buy": True,
                }
            )
        for _ in range(5):
            micro.on_tick(
                {
                    "symbol": "NVDA",
                    "price": 300.0,
                    "bid": 299.99,
                    "ask": 300.01,
                    "size": 50.0,
                    "is_buy": False,
                }
            )
        snap = micro.get_snapshot("NVDA")
        assert snap.large_lot_pressure > 0
        assert snap.book_imbalance > 0
        assert micro.get_pressure("NVDA") > 0

    def test_liquidity_threshold(self):
        micro = MarketMicrostructure()
        # Wide spread
        micro.on_tick({"symbol": "WIDE", "price": 100.0, "bid": 99.5, "ask": 100.5, "size": 100})
        assert not micro.is_liquid("WIDE")
        # Tight spread, no tape
        micro.on_tick({"symbol": "TIGHT", "price": 100.0, "bid": 99.999, "ask": 100.001, "size": 100})
        assert not micro.is_liquid("TIGHT")
        # Tight spread + tape
        for _ in range(20):
            micro.on_tick(
                {
                    "symbol": "TIGHT",
                    "price": 100.0,
                    "bid": 99.999,
                    "ask": 100.001,
                    "size": 100,
                    "timestamp": time.monotonic(),
                }
            )
        assert micro.is_liquid("TIGHT")

    def test_prune_oldest(self):
        micro = MarketMicrostructure(max_symbols=2)
        micro.on_tick({"symbol": "A", "price": 1.0})
        micro.on_tick({"symbol": "B", "price": 2.0})
        micro.on_tick({"symbol": "C", "price": 3.0})
        assert len(micro) == 2
        assert "A" not in micro._snapshot

    def test_reset_symbol(self):
        micro = MarketMicrostructure()
        micro.on_tick({"symbol": "X", "price": 10.0})
        assert len(micro) == 1
        micro.reset("X")
        assert len(micro) == 0


class TestMicrostructureSnapshot:
    def test_defaults(self):
        snap = MicrostructureSnapshot(symbol="TEST")
        assert snap.last_price == 0.0
        assert snap.vwap == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
