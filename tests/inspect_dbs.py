import os
import sqlite3

for db in ["data/trading.db", "data/trading_system.db", "data/trading_stress.db"]:
    if os.path.exists(db):
        conn = sqlite3.connect(db)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"DB: {db}")
        print(f"Tables: {[t[0] for t in tables]}")
        conn.close()
    else:
        print(f"DB: {db} does not exist")
