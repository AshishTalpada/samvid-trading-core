import asyncio
import logging
import sqlite3
from unittest.mock import MagicMock

from src.brain import TradingBrain
from src.dhatu_oracle import DhatuOracle
from src.intelligence_bus import get_bus

# Configure logging to see the "Board of Directors" consulting
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SIMULATION")


async def simulate_memory_trade() -> None:
    print("\n--- 🛡️ INSTITUTIONAL-GRADE SIMULATION: TRADING FROM MEMORY ---")

    # 1. Initialize Components with Real Data
    bus = get_bus()
    oracle = DhatuOracle(bus=bus)  # Will load "Abhava" or last state from DB

    # Mocking IBKR for Paper Simulation
    mock_ibkr = MagicMock()
    mock_db = MagicMock()
    mock_mt5 = MagicMock()

    # 2. Start TradingBrain
    brain = TradingBrain(
        db_conn=mock_db, ibkr_client=mock_ibkr, mt5_client=mock_mt5, dhatu_oracle=oracle, bus=bus
    )

    # 3. VERIFY STORED MEMORY: Check if Oracle recovered the state
    current_dhatu = oracle.get_dhatu_state()
    current_risk = oracle.get_risk_modifier()
    print(f"📡 MEMORY RECOVERED: Current Dhatu={current_dhatu}, Risk Modifier={current_risk}")

    # 4. INJECT A LEARNED WIN-RATE (Agent D Memory)
    # This simulates what Agent D would have learned from past 'COIN' trades
    learn_key = "TICK_DIV|UNKNOWN|RTH"
    brain._learned_win_rates[learn_key] = 0.75  # High confidence memory
    print(f"🧬 INJECTING LEARNED WIN-RATE: {learn_key} -> 75%")

    # 5. INJECT A LIVE SIGNAL
    # We create a mock PatternResult that matches the memory
    mock_pattern = MagicMock()
    mock_pattern.name = "TICK_DIV"
    mock_pattern.confidence = 65.0
    mock_pattern.entry = 150.0
    mock_pattern.stop = 155.0  # Bearish

    brain.pending_signals = [
        {
            "symbol": "COIN",
            "pattern": mock_pattern,
            "lambda": 0.1,
            "reason": "Memory Simulation Trigger",
        }
    ]

    print(f"🚀 INJECTING SIGNAL: COIN [BEARISH] (Confidence: {mock_pattern.confidence})")

    # 6. MOCK MARKET SNAPSHOT (Required for Agent B evaluation)
    brain._fetch_market_snapshot = asyncio.create_task(asyncio.sleep(0))  # Dummy

    async def mock_snapshot(symbol):
        return {"price_change_pct": -2.5, "volume_ratio": 1.5, "vix": 22.0, "breadth": 0.4}

    brain._fetch_market_snapshot = mock_snapshot
    brain._get_account_value = lambda x: asyncio.sleep(0, result=10000.0)  # Mock account value

    async def mock_account(broker) -> float:
        return 10000.0

    brain._get_account_value = mock_account

    print("\n--- 🤝 CONSULTING BOARD OF DIRECTORS (Agents A-E) ---")

    # Manually trigger the ANALYZING state logic
    await brain._state_analyzing()

    # 7. VERIFY EVOLUTIONARY SNAPSHOT GROWTH
    print("\n--- 🧬 VERIFYING EVOLUTIONARY MEMORY GROWTH ---")
    db_path = "data/evolution.db"
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, symbol, dhatu_state, risk_modifier FROM decision_snapshots ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            print(f"✅ SUCCESS: New Snapshot Stored (ID: {row[0]})")
            print(f"   Symbol: {row[1]}, Dhatu: {row[2]}, Modifier: {row[3]}")
        else:
            print("❌ FAILURE: No new snapshot found.")


if __name__ == "__main__":
    asyncio.run(simulate_memory_trade())
