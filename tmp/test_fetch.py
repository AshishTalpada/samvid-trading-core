import sqlite3
import pandas as pd
import asyncio

async def test_fetch():
    db_path = "data/trading.db"
    conn = sqlite3.connect(
        db_path,
        check_same_thread=False,
        isolation_level=None,
        timeout=30,
    )
    symbol = "SPY"
    query = (
        "SELECT timestamp, open, high, low, close, volume "
        "FROM ohlcv WHERE symbol=? AND timeframe='1m' "
        "ORDER BY timestamp DESC LIMIT 200"
    )
    df = await asyncio.to_thread(pd.read_sql_query, query, conn, params=(symbol,))
    print(f"DataFrame empty? {df.empty}")
    print(f"Rows: {len(df)}")
    if not df.empty:
        print(df.head(2))
        
    conn.close()

asyncio.run(test_fetch())
