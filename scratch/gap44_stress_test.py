import os
import sys
import sqlite3
import json
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, os.getcwd() + "\\src")

import config
from agent_c import EvolutionManager

def setup_test_dbs():
    test_main_db = "data/test_trading.db"
    test_evol_db = "data/test_evolution.db"
    
    # Cleanup
    if os.path.exists(test_main_db): os.remove(test_main_db)
    if os.path.exists(test_evol_db): os.remove(test_evol_db)
    
    # Init main DB schema (minimal)
    conn = sqlite3.connect(test_main_db)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            trade_id TEXT UNIQUE,
            pnl_dollars REAL
        )
    """)
    
    # Inject 20 trades with high losses (approx 0.3 win rate)
    # Win rate 0.3, Drawdown will be significant
    import random
    random.seed(42)
    
    trade_ids = []
    for i in range(20):
        t_id = f"T-{1000+i}"
        trade_ids.append(t_id)
        # 30% wins, 70% losses
        pnl = random.uniform(5, 15) if random.random() < 0.3 else random.uniform(-20, -10)
        cursor.execute("INSERT INTO trades (timestamp, trade_id, pnl_dollars) VALUES (?, ?, ?)",
                       (datetime.now().isoformat(), t_id, pnl))
    
    conn.commit()
    conn.close()
    
    # EvolutionManager will init its own schema in test_evol_db
    ev_mgr = EvolutionManager(db_path=test_evol_db, main_db_path=test_main_db)
    
    # Add snapshots for the trades
    for t_id in trade_ids:
        ev_mgr.snapshot_decision(
            symbol="SPY",
            features={"rsi": 30},
            dhatu_state="Sthiti",
            trade_id=t_id
        )
        
    return test_main_db, test_evol_db, ev_mgr

async def run_test():
    main_path, evol_path, ev_mgr = setup_test_dbs()
    
    print(f"--- GAP-44 STRESS TEST START ---")
    print(f"Targeting Main DB: {main_path}")
    print(f"Targeting Evol DB: {evol_path}")
    
    # 1. Audit Global Performance
    metrics = ev_mgr.audit_global_performance(main_db_path=main_path)
    print(f"\n[METRICS]")
    print(f"Total Trades: {metrics.get('n')}")
    print(f"Win Rate:     {metrics.get('win_rate'):.2%}")
    print(f"Total PnL:    ${metrics.get('total_pnl'):.2f}")
    print(f"Max Drawdown: {metrics.get('max_drawdown'):.2%}")
    print(f"Sharpe Ratio: {metrics.get('sharpe')}")
    
    # 2. Propose Mutations
    # We must mock config state to ensure we know the baseline
    config.SYSTEM_MAX_RISK = 0.04
    config.BELIEF_EXIT_THRESHOLD = 0.35
    
    mutations = ev_mgr.evolve_parameters()
    
    print(f"\n[EVOLUTION PROPOSALS]")
    if not mutations:
        print("No mutations proposed.")
    for key, old, new, sharpe in mutations:
        print(f"🧬 MUTATION: {key} | {old} -> {new} (Decision Sharpe: {sharpe})")
        
    # Verify logic
    # Expected: Win rate < 0.45 or DD > 0.08 should trigger risk reduction
    risk_found = False
    for key, old, new, sharpe in mutations:
        if key == "SYSTEM_MAX_RISK":
            risk_found = True
            if new < old:
                print("\n✅ PASS: EvolutionManager correctly proposed a risk reduction.")
            else:
                print("\n❌ FAIL: EvolutionManager proposed a risk INCREASE during drawdown!")
    
    if not risk_found:
         print("\n❌ FAIL: EvolutionManager did not propose a risk reduction despite poor performance.")

    # Cleanup test files
    if os.path.exists(main_path): os.remove(main_path)
    if os.path.exists(evol_path): os.remove(evol_path)
    print(f"\n--- STRESS TEST COMPLETE ---")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_test())
