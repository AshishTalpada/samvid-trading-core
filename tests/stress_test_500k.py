import asyncio
import logging
import os
import random
import sqlite3
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.agent_a import PatternResult
from src.brain import TradingBrain
from src.dhatu_oracle import DhatuOracle

# Project Imports
from src.intelligence_bus import get_bus

# Aggressive Logging Suppression
logging.getLogger("src.brain").setLevel(logging.CRITICAL)
logging.getLogger("src.agent_c").setLevel(logging.CRITICAL)
logging.getLogger("src.agent_d").setLevel(logging.CRITICAL)
logging.getLogger("STRESS_TEST").setLevel(logging.INFO)


class GigastressMarket:
    def __init__(self) -> None:
        self.symbols = [f"GIGA-{i}" for i in range(1000)]

    def generate_signals(self, count=1000):
        discoveries = []
        for _ in range(count):
            symbol = random.choice(self.symbols)
            entry = random.uniform(100, 1000)
            pattern = PatternResult(
                name="GIGA_PATTERN",
                confidence=random.uniform(90, 99),
                entry=entry,
                stop=entry * 0.99,
                target=entry * 1.05,
                r_r_ratio=5.0,
                confirmed=True,
                lambda_val=25,
            )
            discoveries.append(
                {"symbol": symbol, "pattern": pattern, "lambda": 25, "reason": "Gigastress"}
            )
        return discoveries


async def run_gigastress(target_trades=500000) -> None:
    print(f"💣 NITRO OVERRIDE: DISPATCHING {target_trades:,} TRADES")

    bus = get_bus()
    market = GigastressMarket()
    oracle = DhatuOracle(bus=bus)

    brain = TradingBrain(
        db_conn=MagicMock(),
        ibkr_client=MagicMock(),
        mt5_client=MagicMock(),
        dhatu_oracle=oracle,
        bus=bus,
        mode="paper",
    )

    # --- AGGRESSIVE NITRO BYPASSES ---
    brain._oracle_freeze = False
    brain.emergency_halted = False
    brain.morning_budget.generated_at = datetime.now()
    brain.morning_budget.max_trades = 1000000

    brain.portfolio_guard.enforce_cash_reserve = lambda *args: True
    brain.correlation_guard.check_exposure = lambda *args: True
    brain.blackswan.check = lambda *args: "NONE"

    brain.ibkr_drawdown.is_trading_allowed = lambda: True
    brain.prop_drawdown.is_trading_allowed = lambda: True

    # Bypass heavy I/O mocking
    brain._fetch_market_snapshot = lambda symbol: asyncio.sleep(
        0, result={"price": 500, "volume_ratio": 10.0, "vix": 12.0}
    )
    brain._get_account_value = AsyncMock(return_value=10000000000.0)
    # ---------------------------------

    from src.agent_d import LiveLearningEngine

    learning_engine = LiveLearningEngine(db_path="data/trading_stress.db", bus=bus)

    trades_completed = 0
    start_time = time.time()

    try:
        while trades_completed < target_trades:
            # 1. Bulk Process (1000 signals per cycle)
            signals = market.generate_signals(1000)
            brain.pending_signals = signals

            # 2. State Analyzing (Entry Logic)
            await brain._state_analyzing()

            # 3. Mass Exit Simulation
            batch_to_persist = []
            for pos in list(brain.positions):
                is_win = random.random() < 0.6
                pnl = random.uniform(100, 1000) if is_win else random.uniform(-200, -50)

                trade = {
                    "symbol": pos.symbol,
                    "pattern": pos.pattern,
                    "outcome": "WIN" if is_win else "LOSS",
                    "pnl": pnl,
                    "r_multiple": pnl / 100.0,
                    "regime": "BULL",
                    "session": "RTH",
                    "hold_hours": 0.1,
                }
                batch_to_persist.append(trade)
                brain.positions.remove(pos)
                trades_completed += 1

            # 4. NITRO BATCH PERSIST (Bypass terminal logs and bus for bulk)
            if batch_to_persist:
                learning_engine.persist_batch(batch_to_persist)

            # 5. Heartbeat every 50k
            if trades_completed % 50000 == 0 or trades_completed >= target_trades:
                elapsed = time.time() - start_time
                tps = trades_completed / elapsed if elapsed > 0 else 0
                print(
                    f"📈 [NITRO] Progress: {trades_completed:,}/{target_trades:,} | TPS: {tps:.0f}"
                )

            await asyncio.sleep(0.001)

    except Exception as e:
        print(f"ERROR: {e}")

    duration = time.time() - start_time
    print(f"🏁 NITRO COMPLETE: {trades_completed} trades in {duration:.1f}s")

    # Final count verify
    with sqlite3.connect("data/trading_stress.db") as conn:
        count = conn.execute("SELECT COUNT(*) FROM agent_d_trades").fetchone()[0]
        print(f"💾 STORAGE VERIFIED: {count:,} historical trades in memory.")


if __name__ == "__main__":
    db_file = "data/trading_stress.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    asyncio.run(run_gigastress(500000))
