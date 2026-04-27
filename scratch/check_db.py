import sqlite3
import os

db_path = "data/trading.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"Tables: {tables}")
    
    # Check system_state keys
    try:
        cursor.execute("SELECT key, value FROM system_state")
        print(f"States: {cursor.fetchall()}")
    except:
        pass
    conn.close()
