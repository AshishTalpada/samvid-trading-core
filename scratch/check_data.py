import sqlite3
import pandas as pd
from datetime import datetime

def check_ohlcv():
    conn = sqlite3.connect("data/trading.db")
    try:
        query = "SELECT * FROM ohlcv WHERE symbol='SPY' ORDER BY timestamp DESC LIMIT 5"
        df = pd.read_sql_query(query, conn)
        print("Recent SPY OHLCV data:")
        print(df)
        
        query_vix = "SELECT * FROM vix_data ORDER BY timestamp DESC LIMIT 5"
        df_vix = pd.read_sql_query(query_vix, conn)
        print("\nRecent VIX data:")
        print(df_vix)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_ohlcv()
