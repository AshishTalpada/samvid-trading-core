import sqlite3
import os
import sys
from datetime import datetime

# Add src to path
sys.path.append('src')

try:
    from database_security import DatabaseSecurity
    from vault import Vault
except ImportError:
    print("Could not import security modules.")
    sys.exit(1)

db_path = "data/trading.db"

def final_audit():
    if not os.path.exists(db_path):
        print("DB not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Get total trades
    cursor.execute("SELECT COUNT(*) FROM trades")
    total = cursor.fetchone()[0]
    
    # 2. Get breakdown of outcomes
    cursor.execute("SELECT outcome, COUNT(*) FROM trades GROUP BY outcome")
    outcomes = cursor.fetchall()
    
    # 3. Decrypt PnL and calculate total
    # Columns: 14 is pnl_dollars (based on inspect_db output guessing index, but let's check name)
    cursor.execute("PRAGMA table_info(trades)")
    cols = [c[1] for c in cursor.fetchall()]
    pnl_idx = cols.index('pnl_dollars') if 'pnl_dollars' in cols else -1
    outcome_idx = cols.index('outcome') if 'outcome' in cols else -1
    
    cursor.execute("SELECT * FROM trades")
    rows = cursor.fetchall()
    
    total_pnl = 0.0
    wins = 0
    losses = 0
    
    for row in rows:
        out = row[outcome_idx] if outcome_idx != -1 else "UNKNOWN"
        pnl_enc = row[pnl_idx] if pnl_idx != -1 else None
        
        pnl_val = 0.0
        if pnl_enc and isinstance(pnl_enc, str) and pnl_enc.startswith('gAAAA'): # Fernet prefix
             try:
                 pnl_val = DatabaseSecurity.decrypt_float(pnl_enc)
             except:
                 pass
        
        total_pnl += pnl_val
        if out == 'TARGET' or out == 'SL_TRAIL' or pnl_val > 0:
            wins += 1
        elif out == 'STOP' or out == 'EXIT_MANUAL' or pnl_val < 0:
            losses += 1
            
    print(f"--- FINAL GENUINE AUDIT ---")
    print(f"Total Database Trades: {total}")
    print(f"Outcome Breakdown: {outcomes}")
    print(f"Estimated Total PnL: ${total_pnl:.2f}")
    if (wins + losses) > 0:
        print(f"Calculated Win Rate: {(wins / (wins + losses) * 100):.1f}% (excluding open/orphaned)")
    
    conn.close()

if __name__ == "__main__":
    final_audit()
