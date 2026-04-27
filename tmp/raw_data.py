import sqlite3
import os

db_path = "data/trading.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT * FROM trades LIMIT 5")
rows = cur.fetchall()
print(f"Sample Rows: {rows}")
conn.close()
