import sqlite3
import os
import sys

# Ensure src can be imported
sys.path.append(os.getcwd())

from src.database_security import Vault

db_path = "data/trading.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

try:
    cur.execute("SELECT count(*) FROM trades")
    count = cur.fetchone()[0]
    
    cur.execute("SELECT instrument, direction, shares, entry_price, pnl_dollars FROM trades ORDER BY timestamp DESC LIMIT 10")
    rows = cur.fetchall()
    
    total_pnl = 0.0
    decrypted_rows = []
    
    for r in rows:
        instr, direction, shares, entry, pnl_encrypted = r
        pnl_val = 0.0
        if pnl_encrypted:
            try:
                pnl_val = float(Vault.get_vault_instance().decrypt(pnl_encrypted))
            except:
                pnl_val = 0.0
                
        total_pnl += pnl_val
        decrypted_rows.append((instr, direction, float(shares or 0), float(entry or 0), pnl_val))
        
    print("\n" + "="*65)
    print("      SETO V8.0 SOVEREIGN PERFORMANCE REPORT (DECRYPTED)")
    print("="*65)
    print(f" TOTAL TRADES COMPLETED : {count}")
    print(f" SYSTEM STATUS          : HEALING (Active)")
    print("="*65)
    print("\nLAST 10 AUTONOMOUS TRADES (SAMPLE):")
    print("-" * 65)
    print(f"{'INSTRUMENT':<12} {'DIR':<6} {'SHARES':<8} {'ENTRY':<10} {'P&L ($)':<10}")
    print("-" * 65)
    for r in decrypted_rows:
        print(f"{r[0]:<12} {r[1]:<6} {r[2]:<8.0f} {r[3]:<10.2f} {r[4]:<10.2f}")
    print("-" * 65)

except Exception as e:
    print(f"ERROR: {e}")
finally:
    conn.close()
