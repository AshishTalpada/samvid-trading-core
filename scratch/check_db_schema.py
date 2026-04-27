import sqlite3
import os

db_path = "data/trading.db"
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Trades Table Schema ---")
cursor.execute("PRAGMA table_info(trades);")
for col in cursor.fetchall():
    print(col)

print("\n--- System State Schema ---")
cursor.execute("PRAGMA table_info(system_state);")
for col in cursor.fetchall():
    print(col)

conn.close()
