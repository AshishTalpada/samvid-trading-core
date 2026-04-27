import sqlite3
import os

db_path = "data/trading.db"

def inspect_data():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- TRADES TABLE COLUMNS ---")
    cursor.execute("PRAGMA table_info(trades)")
    for col in cursor.fetchall():
        print(col)
        
    print("\n--- SAMPLE ROWS ---")
    cursor.execute("SELECT * FROM trades LIMIT 3")
    rows = cursor.fetchall()
    for r in rows:
        print(r)
        
    print("\n--- UNIQUE OUTCOMES ---")
    cursor.execute("SELECT DISTINCT outcome FROM trades")
    print(cursor.fetchall())

    print("\n--- PNL SUMMARY (if available) ---")
    try:
        cursor.execute("SELECT SUM(pnl_dollars), AVG(pnl_dollars) FROM trades")
        print(cursor.fetchone())
    except:
        print("PnL summary failed.")

    conn.close()

if __name__ == "__main__":
    inspect_data()
