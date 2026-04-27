
import asyncio
import logging
import sys
from pathlib import Path

# Setup paths
sys.path.append(str(Path(__file__).parent.parent / "src"))

from intelligence_bus import SharedIntelligenceBus
from agent_c_ibkr import IBKRConnection
from agent_d import LiveLearningEngine

async def run_phase7_audit():
    print("--- 🔬 PHASE 7: HIGH-FIDELITY EXECUTION AUDIT ---")
    bus = SharedIntelligenceBus()
    
    # 1. Verify Neural Warmup (Latency Check)
    print("\n[1/3] Verifying Neural Warmup Cache...")
    class MockIB:
        def isConnected(self): return True
        async def qualifyContractsAsync(self, contract):
            print(f"Qualifying {contract.symbol}...")
            return [contract]
    
    ibc = IBKRConnection(ib_client=MockIB())
    symbols = ["AAPL", "TSLA"]
    await ibc.warm_up_contracts(symbols)
    
    if "AAPL" in ibc._qualified_contracts and "TSLA" in ibc._qualified_contracts:
        print("SUCCESS: Contracts cached in _qualified_contracts.")
    else:
        print("FAIL: Cache missing contracts.")

    # 2. Verify Slippage Shield (Dirty Trade Filter)
    print("\n[2/3] Verifying Slippage Shield (Agent D Purity)...")
    engine = LiveLearningEngine(bus=bus)
    
    # Start the engine runner in the background so it can process events
    bg_task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.1) # Wait for subscription
    
    # Subscribe to check for calibration updates
    q_out = bus.subscribe("calibration.update")
    
    # Payload A: Clean Trade
    clean_trade = {
        "symbol": "SPY", "pnl": 100.0, "r_multiple": 1.0, 
        "is_dirty": False, "pattern": "BULL_FLAG", "regime": "BULL"
    }
    
    # Payload B: Dirty Trade (High Slippage)
    dirty_trade = {
        "symbol": "QQQ", "pnl": -50.0, "r_multiple": -0.5, 
        "is_dirty": True, "pattern": "GAP_FILL", "regime": "BEAR"
    }
    
    # Clear the initial bootstrap calibration if any
    while not q_out.empty():
        q_out.get_nowait()

    print("Publishing CLEAN trade...")
    await bus.publish("trade.exit", clean_trade)
    
    # Wait for the async engine to process and publish back
    try:
        update_clean = await asyncio.wait_for(q_out.get(), timeout=2.0)
        print(f"Clean Trade -> Calibration Update: YES (PASS)")
    except asyncio.TimeoutError:
        print("Clean Trade -> Calibration Update: NO (FAIL)")

    print("Publishing DIRTY trade...")
    await bus.publish("trade.exit", dirty_trade)
    
    # Wait a bit
    await asyncio.sleep(0.5)
    
    if q_out.empty():
        print("Dirty Trade -> Calibration Update: NO (PASS: Data purity maintained)")
    else:
        update_dirty = q_out.get_nowait()
        print("Dirty Trade -> Calibration Update: YES (FAIL: Should have been skipped)")

    bg_task.cancel()
    print("\n--- PHASE 7 AUDIT COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(run_phase7_audit())
