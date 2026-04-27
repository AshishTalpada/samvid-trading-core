import sqlite3
import os

db_path = "data/trading.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT count(*) FROM trades")
        count = cur.fetchone()[0]
        print(f"Total Trades: {count}")
        
        cur.execute("SELECT symbol, side, shares, price, pnl_dollars FROM trades ORDER BY timestamp DESC LIMIT 5")
        rows = cur.fetchall()
        print("\nLast 5 Trades:")
        for r in rows:
            print(r)
            
        cur.execute("SELECT SUM(pnl_dollars) FROM trades")
        total_pnl = cur.fetchone()[0]
        print(f"\nTotal P&L ($): {total_pnl or 0.0}")
    except Exception as e:
        print(f"Error querying trades: {e}")
    finally:
        conn.close()
else:
    print(f"Database not found: {db_path}")
