import sqlite3
import os

db_path = "data/trading.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
try:
    cur.execute("PRAGMA table_info(trades)")
    columns = cur.fetchall()
    print("Columns in 'trades' table:")
    for c in columns:
        print(f" - {c[1]} ({c[2]})")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
