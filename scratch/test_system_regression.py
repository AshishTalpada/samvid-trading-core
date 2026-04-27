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
        
        # Pull snapshots that represent real historical trade attempts
        cursor.execute("""
            SELECT symbol, dhatu_state, confidence, bias, features, timestamp 
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
            symbol, dhatu, snap_conf, bias, features, ts = row
            logger.info(f"\n[TEST {i+1}] Testing System Logic for {symbol} (Historical Context: {ts})")
            logger.info(f"Context: Dhatu={dhatu}, Initial Confidence={snap_conf:.2f}, Bias={bias}")
            
            context = {
                "symbol": symbol,
                "timestamp": ts,
                "is_long": (bias == "LONG")
            }
            
            # Reconstruct a Quorum simulation based on the historical confidence
            # In a real system, the quorum agents would re-evaluate, but for this regression
            # we want to see if our NEW hardening logic (modifier < 0.70, etc) changes things.
            
            # Simulate a 7-agent quorum where the consensus matches the historical confidence
            # but is subject to the NEW HARDENED VETO RULES.
            test_votes = [
                {"agent": "Agent_A", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
                {"agent": "Agent_B", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
                {"agent": "Agent_D", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
                {"agent": "Dhatu_Oracle", "vote": "YES", "confidence": snap_conf, "timestamp": ts, "dhatu_state": dhatu},
                {"agent": "Swarm_Predictor", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
                {"agent": "Risk_Guard", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
                {"agent": "Mind_Ultrathink", "vote": "YES", "confidence": snap_conf, "timestamp": ts},
            ]
            
            # --- OVERRIDE: Check if the NEW hardening would have VETOED this ---
            # If Dhatu was Viyoga or Abhava, the new logic should block it.
            if dhatu in ("Abhava", "Viyoga"):
                logger.info(f"LOG: Historical state was {dhatu}. Monitoring for Hard-Veto...")
            
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
        logger.info(f"Passed System Logic: {executed}")
        logger.info(f"Filtered by Hardening: {rejected}")
        logger.info("=" * 60)

        conn.close()
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_data_regression_test())
