import sqlite3
import os

db_path = 'data/trading.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Tables: {tables}")
    if 'ohlcv' in tables:
        cursor.execute("SELECT COUNT(*) FROM ohlcv")
        count = cursor.fetchone()[0]
        print(f"ohlcv row count: {count}")
    conn.close()
