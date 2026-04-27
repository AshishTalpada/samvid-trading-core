import sqlite3
from datetime import datetime, timezone

conn = sqlite3.connect('data/trading.db')
cur = conn.cursor()
rows = cur.execute("SELECT symbol, MAX(timestamp) FROM ohlcv WHERE timeframe='1m' GROUP BY symbol ORDER BY MAX(timestamp) DESC LIMIT 10").fetchall()
now = datetime.now(timezone.utc)
print("UTC now:", now.isoformat())
for r in rows:
    sym, ts = r
    try:
        t = datetime.fromisoformat(str(ts).replace('Z','+00:00'))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        age = (now - t).total_seconds() / 60
        print(f"{sym}: {ts}  age={age:.1f} min")
    except Exception as e:
        print(f"{sym}: {ts}  ERROR={e}")
conn.close()
