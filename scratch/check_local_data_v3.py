import sqlite3
import os

def check_data_v3():
    db_path = "data/trading.db"
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Simple summary query
    cursor.execute("SELECT instrument, pnl_dollars, timestamp, outcome FROM trades ORDER BY timestamp DESC LIMIT 5")
    rows = cursor.fetchall()
    
    print("--- RECENT TRADES ---")
    for r in rows:
        pnl = r[1] if r[1] is not None else 0.0
        print(f"[{r[2]}] {r[0]}: ${pnl:.2f} ({r[3]})")
    
    cursor.execute("SELECT SUM(pnl_dollars), SUM(net_pnl), COUNT(*) FROM trades")
    res = cursor.fetchone()
    gross = res[0] if res[0] is not None else 0.0
    net = res[1] if res[1] is not None else 0.0
    count = res[2]
    
    print(f"\nTOTAL TRADES: {count}")
    print(f"GROSS P&L:    ${gross:.2f}")
    print(f"NET P&L:      ${net:.2f}")
    conn.close()

if __name__ == "__main__":
    check_data_v3()
