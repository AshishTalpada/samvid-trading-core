import sqlite3
import os

db_path = "data/trading.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
try:
    cur.execute("SELECT count(*) FROM trades")
    count = cur.fetchone()[0]
    
    cur.execute("SELECT SUM(pnl_dollars) FROM trades")
    pnl = cur.fetchone()[0] or 0.0
    
    cur.execute("SELECT instrument, direction, shares, entry_price, pnl_dollars FROM trades ORDER BY timestamp DESC LIMIT 10")
    rows = cur.fetchall()
    
    print("\n" + "="*50)
    print("      SETO V8.0 SOVEREIGN PERFORMANCE REPORT")
    print("="*50)
    print(f" TOTAL TRADES COMPLETED : {count}")
    print(f" TOTAL CUMULATIVE P&L   : ${pnl:,.2f}")
    print(f" SYSTEM STATUS          : HEALING (Active)")
    print("="*50)
    print("\nLAST 10 AUTONOMOUS TRADES:")
    print("-" * 65)
    print(f"{'INSTRUMENT':<12} {'DIR':<6} {'SHARES':<8} {'ENTRY':<10} {'P&L ($)':<10}")
    print("-" * 65)
    for r in rows:
        print(f"{r[0]:<12} {r[1]:<6} {r[2]:<8.0f} {r[3]:<10.2f} {r[4]:<10.2f}")
    print("-" * 65)

except Exception as e:
    print(f"ERROR: {e}")
finally:
    conn.close()
