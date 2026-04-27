import sqlite3
import os

db_path = "data/trading.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT instrument, shares, outcome FROM trades WHERE outcome='OPEN'")
    rows = cursor.fetchall()
    print("--- Open Trades in DB ---")
    for row in rows:
        print(row)
    conn.close()
else:
    print("DB not found")
