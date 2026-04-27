import sqlite3, datetime

# Replicate EXACTLY what brain._fetch_ohlcv does
import pandas as pd

conn = sqlite3.connect('data/trading.db', check_same_thread=False)

symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'GS', 'MA']

print(f"Now local: {datetime.datetime.now()}")
print(f"Now pd.Timestamp.now(): {pd.Timestamp.now()}\n")

for sym in symbols:
    # Exact brain query
    query = (
        "SELECT timestamp, open, high, low, close, volume "
        "FROM ohlcv WHERE symbol=? AND timeframe='1m' "
        "ORDER BY timestamp DESC LIMIT 200"
    )
    df = pd.read_sql_query(query, conn, params=(sym,))
    
    if df.empty:
        print(f"{sym:8s}: EMPTY from DB query with timeframe='1m'")
        # Try without timeframe filter
        df2 = pd.read_sql_query("SELECT timestamp FROM ohlcv WHERE symbol=? ORDER BY timestamp DESC LIMIT 1", conn, params=(sym,))
        if not df2.empty:
            print(f"         (without timeframe filter: {df2['timestamp'].iloc[0]})")
        continue

    df.columns = [c.lower() for c in df.columns]
    latest_bar_ts = pd.to_datetime(df['timestamp']).max()
    now_ts = pd.Timestamp.now()

    if latest_bar_ts.tzinfo is not None:
        latest_bar_ts_naive = latest_bar_ts.tz_localize(None)
    else:
        latest_bar_ts_naive = latest_bar_ts

    staleness = (now_ts - latest_bar_ts_naive).total_seconds()
    staleness_min = staleness / 60
    stale_limit = 600  # market open = 10 min

    raw_ts_max = df['timestamp'].iloc[0]
    status = "STALE!" if staleness > stale_limit else "OK"
    print(f"{sym:8s}: raw_max={raw_ts_max}  naive={latest_bar_ts_naive}  age={staleness_min:.1f}min  [{status}]  rows={len(df)}")

conn.close()
