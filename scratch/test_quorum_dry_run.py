import asyncio
import logging
import sys
from datetime import datetime
from typing import Any, Dict, List

# Add the project root to sys.path
sys.path.append("c:/Users/talpa/Desktop/System_Beta/TradingSystem/src")

from sovereign_decision_engine import SovereignDecisionEngine

async def run_dry_run_test():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("DryRun")
    
    engine = SovereignDecisionEngine()
    ts = datetime.now().isoformat()
    
    context = {
        "symbol": "AAPL",
        "timestamp": ts
    }
    
    # CASE 1: 4 YES + Risk Guard VETO (Risk NO)
    # Result: Should be REJECT due to VETO rule
    case1_votes = [
        {"agent": "Agent_A", "vote": "YES", "confidence": 0.9, "timestamp": ts},
        {"agent": "Agent_B", "vote": "YES", "confidence": 0.8, "timestamp": ts},
        {"agent": "Agent_D", "vote": "YES", "confidence": 0.7, "timestamp": ts},
        {"agent": "Dhatu_Oracle", "vote": "YES", "confidence": 0.6, "timestamp": ts},
        {"agent": "Swarm_Predictor", "vote": "NO", "confidence": 0.4, "timestamp": ts},
        {"agent": "Risk_Guard", "vote": "NO", "confidence": 0.2, "timestamp": ts}, # VETO!
        {"agent": "Mind_Ultrathink", "vote": "YES", "confidence": 0.8, "timestamp": ts},
    ]
    
    logger.info("--- STARTING TEST CASE 1: 4 YES + Risk Guard VETO ---")
    result1 = await engine.evaluate(context, case1_votes)
    logger.info(f"TEST CASE 1 DECISION: {result1['decision']}")
    logger.info(f"REASON: {result1['reason']}")
    
    # CASE 2: Incomplete Quorum (6 agents instead of 7)
    # Result: Should be REJECT due to Quorum Violation
    case2_votes = case1_votes[:-1]
    logger.info("\n--- STARTING TEST CASE 2: INCOMPLETE QUORUM (6/7) ---")
    result2 = await engine.evaluate(context, case2_votes)
    logger.info(f"TEST CASE 2 DECISION: {result2['decision']}")
    logger.info(f"REASON: {result2['reason']}")

    # CASE 3: 5 YES + No Veto (Confidence > 0.65)
    # Result: Should be EXECUTE
    case3_votes = [
        {"agent": "Agent_A", "vote": "YES", "confidence": 0.9, "timestamp": ts},
        {"agent": "Agent_B", "vote": "YES", "confidence": 0.8, "timestamp": ts},
        {"agent": "Agent_D", "vote": "YES", "confidence": 0.7, "timestamp": ts},
        {"agent": "Dhatu_Oracle", "vote": "YES", "confidence": 0.9, "timestamp": ts},
        {"agent": "Swarm_Predictor", "vote": "YES", "confidence": 0.8, "timestamp": ts},
        {"agent": "Risk_Guard", "vote": "YES", "confidence": 0.8, "timestamp": ts},
        {"agent": "Mind_Ultrathink", "vote": "YES", "confidence": 0.8, "timestamp": ts},
    ]
    logger.info("\n--- STARTING TEST CASE 3: UNANIMOUS EXECUTION ---")
    result3 = await engine.evaluate(context, case3_votes)
    logger.info(f"TEST CASE 3 DECISION: {result3['decision']}")
    logger.info(f"REASON: {result3['reason']}")

if __name__ == "__main__":
    asyncio.run(run_dry_run_test())
