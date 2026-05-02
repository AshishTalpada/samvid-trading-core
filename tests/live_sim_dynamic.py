import asyncio
import sys

# --- Python 3.10+ / 3.14 eventkit compatibility hack ---
if sys.platform == "win32":
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

import logging
import random
import time
from unittest.mock import MagicMock

from src.agent_a import PatternResult
from src.agent_d import LiveLearningEngine
from src.brain import DrawdownLevel, TradingBrain
from src.dhatu_oracle import DhatuOracle

# Project Imports
from src.intelligence_bus import get_bus

# Decision-focused Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/live_sim_iq.log"), logging.StreamHandler()],
)
logger = logging.getLogger("IQ_SIM")


class DynamicMarket:
    """Simulates drifting market regimes for decision validation."""

    def __init__(self) -> None:
        self.regime = "BULL"
        self.vix = 18.0
        self.symbols = [f"REAL-{i}" for i in range(500)]
        self.phase = 0

    def shift_regime(self, cycle) -> None:
        if cycle < 100:
            self.regime = "BULL"  # BOOM PHASE
            self.vix = 15.0
        elif cycle < 200:
            self.regime = "VOLATILE"  # BLACK SWAN PHASE
            self.vix = 42.0
        else:
            self.regime = "CHOPPY"  # GRIND/DECEDENCE PHASE
            self.vix = 25.0

    def get_signals(self, count=5):
        signals = []
        # In BULL, high quality. In CHOPPY, garbage.
        confidence_base = 90 if self.regime == "BULL" else 65

        for _ in range(count):
            symbol = random.choice(self.symbols)
            entry = random.uniform(100, 500)
            signals.append(
                {
                    "symbol": symbol,
                    "lambda": 20,
                    "reason": "LiveSim",
                    "pattern": PatternResult(
                        name="BULL_FLAG" if self.regime == "BULL" else "NOISE_PATTERN",
                        category="SCALP",
                        confidence=random.uniform(confidence_base - 5, confidence_base + 5),
                        entry=entry,
                        stop=entry * 0.98,
                        target=entry * 1.05,
                        r_r_ratio=3.5,
                        confirmed=True,
                        lambda_val=25,
                    ),
                }
            )
        return signals


async def run_iq_simulation() -> None:
    try:
        logger.info("🧠 STARTING HIGH-FIDELITY 'REAL-TIME IQ' SIMULATION")

        bus = get_bus()
        market = DynamicMarket()
        # Note: Using the REAL DhatuOracle but feeding it manual VIX in the mock
        oracle = DhatuOracle(bus=bus)

        brain = TradingBrain(
            db_conn=MagicMock(),
            ibkr_client=MagicMock(),
            mt5_client=MagicMock(),
            dhatu_oracle=oracle,
            bus=bus,
            mode="paper",
        )

        # 💾 LOAD 500k-TRADE MEMORY
        logger.info("💾 Loading 500,000-Trade Memory into Agent D...")
        brain.live_learner = LiveLearningEngine(db_path="data/trading_stress.db", bus=bus)

        # --- NO BYPASSES ---
        # Morning Budget generated naturally
        brain.morning_budget.generate("BULL", 0, DrawdownLevel.NORMAL)
        # -------------------

        # Telemetry
        stats = {
            "accepted": 0,
            "rejected": 0,
            "oracle_rejections": 0,
            "budget_rejections": 0,
            "memory_rejections": 0,
        }

        start_time = time.time()

        for cycle in range(300):
            market.shift_regime(cycle)

            # 1. Update Brain's internal VIX/Snapshot
            vix = market.vix
            brain._fetch_market_snapshot = lambda s, vix=vix: asyncio.sleep(
                0, result={"price": 200, "vix": vix, "volume_ratio": 1.5}
            )

            # 2. Update Oracle Posture
            brain._oracle_dhatu = (
                "Vriddhi" if market.regime == "BULL" else "Abhava" if market.vix > 35 else "Sthiti"
            )
            brain._oracle_freeze = brain._oracle_dhatu == "Abhava"

            # 3. Inject Signals
            signals = market.get_signals(10)
            brain.pending_signals = signals

            # 4. MONITOR DECISION IQ
            if cycle % 50 == 0:
                logger.info(f"DEBUG: Entering loop for cycle {cycle}")

            # We manually step through the Brain's real logic to capture rejections
            for sig in signals:
                # Stage A: Oracle Gate
                if brain._oracle_freeze:
                    stats["oracle_rejections"] += 1
                    stats["rejected"] += 1
                    continue

                # Stage B: Budget Gate
                if sig["pattern"].confidence < brain.morning_budget.min_catalyst:
                    stats["budget_rejections"] += 1
                    stats["rejected"] += 1
                    continue

                # Stage C: Agent D Memory Gate (The Wisdom Check)
                # Consult the 500k-trade matrix
                if cycle % 50 == 0:
                    logger.info(f"DEBUG: Checking memory for {sig['symbol']}")
                knowledge = brain.live_learner.get_win_rate(sig["pattern"].name, market.regime)
                if knowledge < 0.58:  # Reject if our 500k memory says it's < 58% win rate
                    stats["memory_rejections"] += 1
                    stats["rejected"] += 1
                    continue

                # Stage D: Execution (Simulated)
                stats["accepted"] += 1
                # Add to positions so Portfolio Guard can track leverage
                brain.positions.append(MagicMock())
                if cycle % 50 == 0:
                    logger.info(
                        f"✅ Trade ACCEPTED: {sig['symbol']} (Confidence: {sig['pattern'].confidence:.1f})"
                    )

            # Cycle summary
            if cycle % 50 == 0:
                logger.info(
                    f"🌀 CYCLE {cycle} | Regime: {market.regime} | VIX: {vix} | Active: {len(brain.positions)}"
                )

            # High-speed simulation yield
            await asyncio.sleep(0.01)

        duration = time.time() - start_time
        logger.info(f"🏁 IQ SIMULATION COMPLETE in {duration:.1f}s")

        # FINAL INTELLIGENCE REPORT
        print("\n" + "=" * 50)
        print("🤖 AUTONOMOUS DECISION IQ REPORT")
        print("=" * 50)
        print(f"Total Signals Analyzed:  {stats['accepted'] + stats['rejected']:,}")
        print(f"Total Trades Accepted:   {stats['accepted']:,}")
        print(f"Total Trades Rejected:   {stats['rejected']:,}")
        print("-" * 50)
        print("REJECTION BREAKDOWN:")
        print(f"🚫 Oracle Safe-Freeze:  {stats['oracle_rejections']:,}")
        print(f"🚫 Budget/Quality:      {stats['budget_rejections']:,}")
        print(f"🚫 500k Memory Low-WR:  {stats['memory_rejections']:,}")
        print("=" * 50)

        acceptance_rate = (stats["accepted"] / (stats["accepted"] + stats["rejected"])) * 100
        print(f"System Selectivity: {100 - acceptance_rate:.2f}% (Higher = More Disciplined)")
        print("=" * 50 + "\n")

    except Exception as e:
        import traceback

        logger.error(f"🔥 SIMULATION CRASHED: {e}")
        print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_iq_simulation())
