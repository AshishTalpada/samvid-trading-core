import asyncio
import logging
import random
import sqlite3
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from typing import ClassVar

from src.agent_a import PatternResult
from src.brain import TradingBrain
from src.dhatu_oracle import DhatuOracle

# Project Imports
from src.intelligence_bus import get_bus

# Configure logging for the stress test (Minimal noise)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/stress_test_5000.log"), logging.StreamHandler()],
)
logger = logging.getLogger("STRESS_TEST")
logging.getLogger("src.brain").setLevel(logging.WARNING)  # Silence the board of directors


class SyntheticMarket:
    """Generates synthetic high-frequency signals."""

    SYMBOLS: ClassVar[list[str]] = [f"SYM-{i}" for i in range(100)]

    def get_next_signal(self):
        symbol = random.choice(self.SYMBOLS)
        entry = random.uniform(100, 500)
        return {
            "symbol": symbol,
            "pattern": PatternResult(
                name="STRESS_PATTERN",
                confidence=random.uniform(85, 95),  # High confidence to ensure 100% acceptance
                entry=entry,
                stop=entry * 0.99,
                target=entry * 1.05,
                r_r_ratio=5.0,
                confirmed=True,
                lambda_val=20,
            ),
        }


async def run_stress_test(total_trades=5000) -> None:
    logger.info("🚀 STARTING AGGRESSIVE 5,000 TRADE EXECUTION TEST")

    # 1. Setup Components
    bus = get_bus()
    market = SyntheticMarket()
    oracle = DhatuOracle(bus=bus)

    # 2. Instance Brain with Bypasses
    brain = TradingBrain(
        db_conn=MagicMock(),
        ibkr_client=MagicMock(),
        mt5_client=MagicMock(),
        dhatu_oracle=oracle,
        bus=bus,
        mode="paper",
    )

    # --- AGGRESSIVE BYPASSES (Just for this test) ---
    brain._oracle_freeze = False
    brain._oracle_dhatu = "Vriddhi"  # Expand
    brain._oracle_risk_modifier = 2.0  # Aggressive sizing
    # Bypass all risk-guards for this simulation
    brain.portfolio_guard.enforce_cash_reserve = lambda *args: True
    brain.correlation_guard.check_exposure = lambda *args: True
    brain.blackswan.check = lambda *args: "NORMAL"

    brain._fetch_market_snapshot = lambda symbol: asyncio.sleep(
        0, result={"price": 200, "volume_ratio": 2.0, "vix": 18.0}
    )
    brain._get_account_value = AsyncMock(return_value=1000000000.0)  # $1B
    brain._get_daily_pnl = AsyncMock(return_value=0.0)
    brain._log_trade_entry = AsyncMock()
    brain._log_signal = AsyncMock()
    # -----------------------------------------------

    from src.agent_d import LiveLearningEngine

    learning_engine = LiveLearningEngine(db_path="data/trading.db", bus=bus)
    asyncio.create_task(learning_engine.run())

    trades_completed = 0
    start_time = datetime.now()

    logger.info("--- 🔥 EXECUTING HIGH-CHURN LOOP ---")

    while trades_completed < total_trades:
        # Step A: Inject 50 signals per cycle for max velocity
        discoveries = []
        for _ in range(50):
            sig = market.get_next_signal()
            discoveries.append(
                {
                    "symbol": sig["symbol"],
                    "pattern": sig["pattern"],
                    "lambda": 20,
                    "reason": "Stress",
                }
            )
        brain.pending_signals = discoveries

        # Step B: Entry Phase
        await brain._state_analyzing()

        # Step C: Exit Phase (Extreme churn)
        for pos in list(brain.positions):
            # 80% chance to exit every cycle to hit 5,000 quickly
            if random.random() < 0.8:
                is_win = random.random() < 0.65  # Target 65% win rate for the report
                pnl = random.uniform(100, 500) if is_win else random.uniform(-200, -50)

                await bus.publish(
                    "trade.exit",
                    {
                        "symbol": pos.symbol,
                        "pattern": pos.pattern,
                        "pnl": pnl,
                        "r_multiple": pnl / 100.0,
                        "regime": "BULL",
                        "hold_hours": 1.0,
                    },
                )
                brain.positions.remove(pos)
                trades_completed += 1

                if trades_completed % 1000 == 0:
                    logger.info(f"📊 MILESTONE: {trades_completed}/5000 trades.")

        # Yield to let the Bus and Agent D process
        await asyncio.sleep(0.01)

    # Allow final events to clear
    await asyncio.sleep(1.0)
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"--- 🏁 5,000 TRADES COMPLETED in {duration:.1f}s ---")

    # Final count in DB
    db_path = "data/trading.db"
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM agent_d_trades").fetchone()[0]
        logger.info(f"💾 Agent D Storage: {count} historical trades now in memory.")


if __name__ == "__main__":
    asyncio.run(run_stress_test(5000))
