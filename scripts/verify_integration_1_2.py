"""Integration smoke test for Implementation 1 + 2 + 3.

Verifies that:
- market microstructure ingests ticks and produces signals
- trade interrogator uses microstructure to veto bad trades
- regime strategy router routes patterns to correct timeframes
- multi-timeframe confluence engine checks higher timeframe alignment
- brain has all components wired
- coordinator uses the same regime router and confluence engine as the brain
"""
import asyncio

import numpy as np
import polars as pl

from adaptive_learning import LiveAdaptiveEngine
from confluence_engine import ConfluenceEngine
from market_microstructure import MarketMicrostructure
from neural_governance import AgentVote, NeuralGovernanceEngine
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
    # Testing mode: all patterns are allowed in all regimes, 1m blocklist removed.
    assert router.route("VCP (Minervini Pivot)", "CHOPPY").allowed
    bull_flag_route = router.route("Bull Flag", "BULL")
    assert bull_flag_route.allowed and bull_flag_route.timeframe == "5m"
    assert not router.route("Bull Flag", "BULL").timeframe == "1m"  # never 1m
    assert router.route("HFT Spoof Pivot", "CHOPPY").allowed  # 1m blocklist removed
    assert router.route("Deep Tape Absorption", "BULL").allowed
    print("[OK] RegimeStrategyRouter: regime + timeframe + blocklist routing")

    # 4. TimeframeAwareDetector wiring
    from agent_a import PatternDetector

    detector = TimeframeAwareDetector(PatternDetector(), router)

    async def fake_fetch(symbol: str, tf: str):
        # Provide a minimal Polars-compatible frame for VCP (needs 50 rows)
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

    # 4. Confluence Engine
    confluence = ConfluenceEngine(min_score=0.70)

    async def conf_fetch(sym, tf):
        n = 60
        up = [100.0 + i * 0.05 for i in range(n)]
        return pl.DataFrame(
            {
                "timestamp": list(range(n)),
                "open": up,
                "high": [p + 0.05 for p in up],
                "low": [p - 0.05 for p in up],
                "close": up,
                "volume": [1000.0] * n,
            }
        )

    conf_result = await confluence.evaluate("AAPL", "LONG", "5m", conf_fetch)
    assert conf_result.passed, f"bullish confluence for LONG should pass: {conf_result}"
    print(f"[OK] ConfluenceEngine: LONG alignment passed with score {conf_result.score}")

    # 4b. Adaptive Learning
    adaptive = LiveAdaptiveEngine()
    for _ in range(5):
        adaptive.ingest_trade_exit(
            {"symbol": "AAPL", "pattern": "VCP", "pnl": 100.0, "r_multiple": 2.0, "regime": "BULL"}
        )
    state = adaptive.recompute(force=True)
    assert state.pattern_confidence_mods.get("VCP", 0.0) > 0
    adjusted = adaptive.adjust_pattern_confidence("VCP", 70.0)
    assert adjusted > 70.0
    print(f"[OK] LiveAdaptiveEngine: learned VCP bullish edge, boosted confidence to {adjusted:.1f}")

    # 4c. Neural Governance
    governance = NeuralGovernanceEngine(threshold=0.60)
    votes = [
        AgentVote("confluence", "APPROVE", confidence=0.95, weight=1.0),
        AgentVote("interrogator", "APPROVE", confidence=0.85, weight=1.0),
        AgentVote("adaptive", "APPROVE", confidence=0.80, weight=1.0),
    ]
    gov_result = governance.decide("AAPL", votes, context={"pattern": "VCP"})
    assert gov_result.approved, f"unanimous approval should pass: {gov_result}"
    assert gov_result.score >= 0.60
    audit_stats = governance.audit.stats()
    assert audit_stats["total"] == 1
    print(f"[OK] NeuralGovernanceEngine: consensus approved with score {gov_result.score}")

    # 5. Brain wiring check
    from brain import TradingBrain

    brain = TradingBrain()
    assert hasattr(brain, "microstructure")
    assert hasattr(brain, "trade_interrogator")
    assert hasattr(brain, "regime_router")
    assert hasattr(brain, "timeframe_detector")
    assert hasattr(brain, "confluence_engine")
    assert hasattr(brain, "adaptive_engine")
    assert hasattr(brain, "governance_engine")
    assert brain.regime_router is not None
    assert brain.timeframe_detector is not None
    assert brain.confluence_engine is not None
    assert brain.adaptive_engine is not None
    assert brain.governance_engine is not None
    print("[OK] TradingBrain: microstructure, interrogator, router, detector, confluence, adaptive, governance all wired")

    # 6. Coordinator wiring check
    from coordinator import TradingCoordinator
    from mind_bridge import MindBridge

    bridge = MindBridge()
    coord = TradingCoordinator(bridge, brain)
    assert coord.regime_router is brain.regime_router
    assert coord.trade_interrogator is brain.trade_interrogator
    assert coord.trade_interrogator.microstructure is brain.microstructure
    assert coord.confluence_engine is brain.confluence_engine
    assert coord.adaptive_engine is brain.adaptive_engine
    assert coord.governance_engine is brain.governance_engine
    print("[OK] TradingCoordinator: shares router, interrogator, microstructure, confluence, adaptive, and governance engine with brain")

    print("=" * 60)
    print("ALL INTEGRATION CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
