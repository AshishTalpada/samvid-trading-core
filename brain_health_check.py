import sys
import os
import asyncio
import logging
from datetime import datetime

# Set up logging to match the system
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.append(os.path.join(os.getcwd(), 'src'))

async def test_brain_health():
    print("--- Brain Health Check ---")
    try:
        from brain import TradingBrain
        print("✓ TradingBrain imported successfully.")
        
        # Test initialization
        brain = TradingBrain(
            db_conn=None,
            ibkr_client=None,
            mt5_client=None,
            mode="paper"
        )
        print("✓ TradingBrain initialized successfully (Dry Run).")
        
        # Check Agent A
        if brain.pattern_detector:
            print("✓ Agent A PatternDetector initialized.")
            
        # Check Decision Engine
        if brain.decision_engine:
            print("✓ SovereignDecisionEngine active.")
            
        print("--- Final Status: HEALTHY ---")
    except Exception as e:
        import traceback
        print(f"FAILED: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_brain_health())
