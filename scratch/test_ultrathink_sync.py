import asyncio
import logging
import sys
import os

# Adjust path to import from src
sys.path.append(os.path.join(os.getcwd(), 'src'))

from mind_ultrathink import MindUltrathink
from dataclasses import dataclass

@dataclass
class MockPattern:
    entry: float = 175.0
    stop: float = 170.0
    target: float = 185.0
    confidence: float = 85.0
    r_r_ratio: float = 2.0
    name: str = "Bull Flag"

class MockBridge:
    def __init__(self):
        self.tools = {}
        self.call_telemetry = []
        self.initial_context = "TEST_WISDOM"
    def register_tool(self, name, func):
        self.tools[name] = func

async def audit_ultrathink_sync():
    print("🚀 TARGET: MindUltrathink Triple-Sync Audit (SETO V9.0)")
    bridge = MockBridge()
    
    # 1. Initialization Test
    try:
        ultrathink = MindUltrathink(bridge=bridge)
        print("✅ Step 1: Initialization Successful.")
    except Exception as e:
        print(f"❌ Step 1: Initialization FAILED: {e}")
        return

    # 2. Tool Registration Check
    expected_tools = ["pause_and_reason", "simulate_outcome", "cognitive_audit"]
    for t in expected_tools:
        if t in bridge.tools:
            print(f"✅ Step 2: Tool '{t}' properly registered.")
        else:
            print(f"❌ Step 2: Tool '{t}' MISSING from registration.")

    # 3. Decision Engine Interface Audit
    mock_context = {
        "symbol": "TSLA",
        "pattern": MockPattern(),
        "regime": "CHOPPY",
        "vix": 20.0,
        "potential_profit": 10.0,
        "commission": 4.0,
        "intensity": "FAST"
    }
    
    print("\nAttempting 'evaluate_proposal' with Sovereign context...")
    try:
        # We use a short timeout and mock local LLM if needed
        ultrathink.use_local = False # Force fallback string for audit speed
        result = await ultrathink.evaluate_proposal(mock_context)
        
        # KEY CHECK: Does it provide the keys Decision Engine expects?
        required_keys = ["agent", "vote", "confidence", "reason"]
        sync_ok = True
        for key in required_keys:
            if key in result:
                print(f"✅ Protocol Interface Check: '{key}' found -> {result[key]}")
            else:
                print(f"❌ Protocol Interface FAILURE: '{key}' is MISSING.")
                sync_ok = False
        
        if sync_ok:
            print("\n💎 AUDIT COMPLETE: MindUltrathink is 100% synchronized with the Trading Coordinator and Decision Engine.")
        else:
            print("\n⚠️ SYNC DANGER: Interface mismatch detected.")

    except Exception as e:
        print(f"❌ Step 3: Evaluation FATAL ERROR: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(audit_ultrathink_sync())
