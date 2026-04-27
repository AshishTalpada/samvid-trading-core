import asyncio
import logging
import sys
from datetime import datetime
import sqlite3
import os

# Add the project root to sys.path
sys.path.append("c:/Users/talpa/Desktop/System_Beta/TradingSystem/src")

from sovereign_decision_engine import SovereignDecisionEngine

async def run_data_regression_test():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger("RegressionTest")
    
    engine = SovereignDecisionEngine()
    db_path = "data/evolution.db"
    
    if not os.path.exists(db_path):
        logger.error(f"Evolution DB not found at {db_path}")
        return

    logger.info("=" * 60)
    logger.info("SOVEREIGN SYSTEM REGRESSION TEST (Historical Data)")
    logger.info("=" * 60)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Use verified column names: 'prediction_bias' instead of 'bias'
        cursor.execute("""
            SELECT symbol, dhatu_state, confidence, prediction_bias, timestamp 
            FROM decision_snapshots 
            ORDER BY timestamp DESC LIMIT 10
        """)
        
        rows = cursor.fetchall()
        if not rows:
            logger.warning("No historical snapshots found in data/evolution.db to test.")
            return

        executed = 0
        rejected = 0
        
        for i, row in enumerate(rows):
            symbol, dhatu, snap_conf, bias, ts = row
            logger.info(f"\n[TEST {i+1}] Testing System Logic for {symbol} (Historical Context: {ts})")
            logger.info(f"Context: Dhatu={dhatu}, Initial Confidence={snap_conf:.2f}, Bias={bias}")
            
            context = {
                "symbol": symbol,
                "timestamp": ts,
                "is_long": (bias == "LONG")
            }
            
            # Reconstruct a Quorum simulation
            test_votes = [
                {"agent": "Agent_A", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
                {"agent": "Agent_B", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
                {"agent": "Agent_D", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
                {"agent": "Dhatu_Oracle", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
                {"agent": "Swarm_Predictor", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
                {"agent": "Risk_Guard", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
                {"agent": "Mind_Ultrathink", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
            ]
            
            # Manual check for Dhatu logic as evaluated by the engine
            if engine and hasattr(engine, "_dhatu_oracle") and engine._dhatu_oracle:
                 # Ensure mock oracle reflects historical dhatu if needed
                 pass

            result = await engine.evaluate(context, test_votes)
            
            logger.info(f"RESULT: {result['decision']}")
            logger.info(f"REASON: {result['reason']}")
            
            if result['decision'] == "EXECUTE":
                executed += 1
            else:
                rejected += 1
                
        logger.info("\n" + "=" * 60)
        logger.info(f"REGRESSION COMPLETE")
        logger.info(f"Total Tested: {len(rows)}")
        logger.info(f"Execution Approvals: {executed}")
        logger.info(f"Risk Logic Blocks: {rejected}")
        logger.info("=" * 60)

        conn.close()
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_data_regression_test())
