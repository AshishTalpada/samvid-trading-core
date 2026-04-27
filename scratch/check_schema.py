import sqlite3
import os

db_path = "data/trading.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='trades'")
    row = cursor.fetchone()
    if row:
        print(f"SCHEMA: {row[0]}")
    else:
        print("TABLE NOT FOUND")
    conn.close()
else:
    print("DB NOT FOUND")
