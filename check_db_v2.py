import sqlite3
import os

db_path = 'data/trading.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT symbol, COUNT(*) FROM ohlcv GROUP BY symbol")
    rows = cursor.fetchall()
    print("Symbol counts in ohlcv:")
    for row in rows:
        print(f"  {row[0]}: {row[1]}")
    
    cursor.execute("SELECT * FROM ohlcv LIMIT 1")
    col_names = [description[0] for description in cursor.description]
    print(f"Columns in ohlcv: {col_names}")
    
    conn.close()
