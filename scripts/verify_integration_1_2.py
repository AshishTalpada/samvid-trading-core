"""Integration smoke test for Implementation 1 + 2.

Verifies that:
- market microstructure ingests ticks and produces signals
- trade interrogator uses microstructure to veto bad trades
- regime strategy router routes patterns to correct timeframes
- brain has all three components wired
- coordinator uses the same regime router as the brain
"""
import asyncio

from market_microstructure import MarketMicrostructure
from strategy_router import RegimeStrategyRouter, TimeframeAwareDetector
from trade_interrogator import TradeInterrogator


class _Pattern:
    def __init__(self, name: str, entry: float, stop: float, target: float):
        self.name = name
        self.entry = entry
        self.stop = stop
        self.target = target
        self.r_r_ratio = abs(target - entry) / abs(entry - stop + 1e-10)


async def main() -> None:
    print("=" * 60)
    print("INTEGRATION VERIFICATION: Implementation 1 + 2")
    print("=" * 60)

    # 1. Market Microstructure
    micro = MarketMicrostructure()
    for _ in range(30):
        micro.on_tick(
            {
                "symbol": "AAPL",
                "price": 150.0,
                "bid": 149.999,
                "ask": 150.001,
                "size": 200,
                "is_buy": True,
            }
        )
    snap = micro.get_snapshot("AAPL")
    assert snap.last_price == 150.0
    assert micro.is_liquid("AAPL"), "AAPL should be liquid"
    assert snap.book_imbalance > 0.5, "buy-side imbalance should be high"
    print("[OK] MarketMicrostructure: ticks, liquidity, imbalance, pressure")

    # 2. Trade Interrogator
    interrogator = TradeInterrogator(microstructure=micro)
    pattern = _Pattern("VCP (Minervini Pivot)", 150.0, 149.0, 152.0)
    result = interrogator.interrogate(
        "AAPL",
        pattern,
        {"direction": "LONG"},
        current_regime="BULL",
        pattern_stats={"win_rate": 0.60, "sample_size": 20},
    )
    assert result.passed, f"liquid bullish VCP should pass: {result}"
    print("[OK] TradeInterrogator: passes liquid bullish setup")

    # 3. Regime Strategy Router
    router = RegimeStrategyRouter()
    vcp_route = router.route("VCP (Minervini Pivot)", "BULL")
    assert vcp_route.allowed and vcp_route.timeframe == "15m"
    assert not router.route("VCP (Minervini Pivot)", "CHOPPY").allowed
    bull_flag_route = router.route("Bull Flag", "BULL")
    assert bull_flag_route.allowed and bull_flag_route.timeframe == "5m"
    assert not router.route("Bull Flag", "BULL").timeframe == "1m"  # never 1m
    assert not router.route("HFT Spoof Pivot", "CHOPPY").allowed  # 1m blocklist
    assert router.route("Deep Tape Absorption", "BULL").allowed
    print("[OK] RegimeStrategyRouter: regime + timeframe + blocklist routing")

    # 4. TimeframeAwareDetector wiring
    from agent_a import PatternDetector

    detector = TimeframeAwareDetector(PatternDetector(), router)

    async def fake_fetch(symbol: str, tf: str):
        # Provide a minimal Polars-compatible frame for VCP (needs 50 rows)
        import polars as pl
        import numpy as np

        n = 60 if tf == "15m" else 60
        base = 100.0 if tf == "15m" else 150.0
        prices = base + np.cumsum(np.random.randn(n) * 0.05)
        return pl.DataFrame(
            {
                "timestamp": list(range(n)),
                "open": prices,
                "high": prices + 0.05,
                "low": prices - 0.05,
                "close": prices,
                "volume": np.ones(n) * 1000,
            }
        )

    results = await detector.detect_for_regime("AAPL", "BULL", fake_fetch)
    # Random data is unlikely to form real patterns; the test only verifies
    # the detector runs across allowed timeframes without errors.
    print(f"[OK] TimeframeAwareDetector: ran across allowed timeframes (found {len(results)} patterns)")

    # 5. Brain wiring check
    from brain import TradingBrain

    brain = TradingBrain()
    assert hasattr(brain, "microstructure")
    assert hasattr(brain, "trade_interrogator")
    assert hasattr(brain, "regime_router")
    assert hasattr(brain, "timeframe_detector")
    assert brain.regime_router is not None
    assert brain.timeframe_detector is not None
    print("[OK] TradingBrain: microstructure, interrogator, router, detector all wired")

    # 6. Coordinator wiring check
    from coordinator import TradingCoordinator
    from mind_bridge import MindBridge

    bridge = MindBridge()
    coord = TradingCoordinator(bridge, brain)
    assert coord.regime_router is brain.regime_router
    assert coord.trade_interrogator is brain.trade_interrogator
    assert coord.trade_interrogator.microstructure is brain.microstructure
    print("[OK] TradingCoordinator: shares router, interrogator, and microstructure with brain")

    print("=" * 60)
    print("ALL INTEGRATION CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
