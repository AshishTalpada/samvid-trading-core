import sqlite3, datetime

conn = sqlite3.connect('data/trading.db')
cur = conn.cursor()

symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'GS', 'MA', 'SPY', 'QQQ']
print(f"Local now: {datetime.datetime.now()}")
print(f"UTC   now: {datetime.datetime.utcnow()}\n")

for sym in symbols:
    row = cur.execute(
        "SELECT timestamp, close FROM ohlcv WHERE symbol=? AND timeframe='1m' ORDER BY timestamp DESC LIMIT 1",
        (sym,)
    ).fetchone()
    if row:
        ts_str, close = row
        # Try parsing as-is
        print(f"{sym:8s}: raw_ts={ts_str!r}  close={close}")
        # Try to compute age
        try:
            import pandas as pd
            ts = pd.to_datetime(ts_str)
            now_naive = pd.Timestamp.now()
            now_utc   = pd.Timestamp.utcnow()
            
            if ts.tzinfo is not None:
                ts_naive = ts.tz_localize(None)
            else:
                ts_naive = ts
                
            age_local = (now_naive - ts_naive).total_seconds() / 60
            print(f"         → ts_naive={ts_naive}  age_vs_local={age_local:.1f}min")
        except Exception as e:
            print(f"         → parse error: {e}")
    else:
        print(f"{sym:8s}: NO ROWS with timeframe='1m'")

conn.close()
