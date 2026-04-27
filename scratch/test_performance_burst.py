import asyncio
import logging
import sys
import time
from datetime import datetime

# Add the project root to sys.path
sys.path.append("c:/Users/talpa/Desktop/System_Beta/TradingSystem/src")

from sovereign_decision_engine import SovereignDecisionEngine

async def run_stress_test(burst_size: int = 20):
    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger("StressTest")
    
    engine = SovereignDecisionEngine()
    ts = datetime.now().isoformat()
    
    context = {
        "symbol": "STRESS_TEST",
        "timestamp": ts
    }
    
    valid_votes = [
        {"agent": "Agent_A", "vote": "YES", "confidence": 0.9, "timestamp": ts},
        {"agent": "Agent_B", "vote": "YES", "confidence": 0.8, "timestamp": ts},
        {"agent": "Agent_D", "vote": "YES", "confidence": 0.7, "timestamp": ts},
        {"agent": "Dhatu_Oracle", "vote": "YES", "confidence": 0.9, "timestamp": ts},
        {"agent": "Swarm_Predictor", "vote": "YES", "confidence": 0.8, "timestamp": ts},
        {"agent": "Risk_Guard", "vote": "YES", "confidence": 0.8, "timestamp": ts},
        {"agent": "Mind_Ultrathink", "vote": "YES", "confidence": 0.8, "timestamp": ts},
    ]

    print(f"--- STARTING PERFORMANCE STRESS TEST: {burst_size} Trades Burst ---")
    
    # We want to test the SYMBOL LOCK.
    # We will launch multiple tasks for the SAME symbol simultaneously.
    # Since the main evaluate() method is 'async with self._lock', it will 
    # process them one by one. To test the 'if symbol in self._active_symbols' logic,
    # the tasks would need to be running in parallel WITHOUT the global lock,
    # or the logic inside _evaluate_logic would need to be truly async (awaiting).
    
    # Currently, evaluate processes synchronously because of the lock.
    # Let's see how many decisions we can process per second.
    
    start_time = time.perf_counter()
    tasks = [engine.evaluate(context, valid_votes) for _ in range(burst_size)]
    results = await asyncio.gather(*tasks)
    end_time = time.perf_counter()
    
    total_time = end_time - start_time
    print(f"--- TEST COMPLETE ---")
    print(f"Total Time for {burst_size} decisions: {total_time:.6f}s")
    print(f"Throughput: {burst_size/total_time:.2f} decisions/sec")
    
    # Verify results
    executes = len([r for r in results if r["decision"] == "EXECUTE"])
    print(f"Executions: {executes}")

if __name__ == "__main__":
    asyncio.run(run_stress_test(100))
