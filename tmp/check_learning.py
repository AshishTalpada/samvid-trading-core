import sqlite3
import os

db_path = "data/trading.db"
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found.")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get count of trades
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Found tables: {tables}")
        
        if 'trades' in tables:
            cursor.execute("SELECT COUNT(*) FROM trades;")
            trade_count = cursor.fetchone()[0]
            print(f"Total trades: {trade_count}")
        
        if 'signals' in tables:
            cursor.execute("SELECT COUNT(*) FROM signals;")
            signal_count = cursor.fetchone()[0]
            print(f"Total signals: {signal_count}")
            
        if 'ohlcv' in tables:
            cursor.execute("SELECT COUNT(*) FROM ohlcv;")
            ohlcv_count = cursor.fetchone()[0]
            print(f"Total OHLCV rows: {ohlcv_count}")

        # Check for any knowledge or learning related tables
        knowledge_tables = [t for t in tables if 'knowledge' in t.lower() or 'evolution' in t.lower() or 'learning' in t.lower()]
        for kt in knowledge_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {kt};")
            count = cursor.fetchone()[0]
            print(f"Table {kt} rows: {count}")
            
        conn.close()
    except Exception as e:
        print(f"Error checking DB: {e}")
