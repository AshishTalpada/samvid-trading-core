import sqlite3
import pandas as pd
from datetime import datetime
import os

db_path = r'c:\Users\talpa\Desktop\System_Beta\TradingSystem\data\trading.db'
if not os.path.exists(db_path):
    print(f"Database not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)

with open(r'c:\Users\talpa\Desktop\System_Beta\TradingSystem\tmp\db_check_results.txt', 'w') as f:
    f.write("--- System State ---\n")
    try:
        df_state = pd.read_sql_query("SELECT * FROM system_state", conn)
        f.write(df_state.to_string() + "\n")
    except Exception as e:
        f.write(f"Error reading system_state: {e}\n")

    f.write("\n--- OHLCV Counts and Latest Timestamps ---\n")
    try:
        df_ohlcv = pd.read_sql_query("""
            SELECT symbol, COUNT(*) as count, MAX(timestamp) as latest
            FROM ohlcv 
            GROUP BY symbol
        """, conn)
        f.write(df_ohlcv.to_string() + "\n")
    except Exception as e:
        f.write(f"Error reading ohlcv: {e}\n")

    f.write("\n--- Latest VIX ---\n")
    try:
        df_vix = pd.read_sql_query("SELECT * FROM vix_data ORDER BY timestamp DESC LIMIT 5", conn)
        f.write(df_vix.to_string() + "\n")
    except Exception as e:
        f.write(f"Error reading vix_data: {e}\n")

conn.close()
