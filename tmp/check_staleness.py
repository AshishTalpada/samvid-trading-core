import sqlite3
from datetime import datetime, timezone

conn = sqlite3.connect('data/trading.db')
cur = conn.cursor()

# Check latest timestamps per symbol
rows = cur.execute(
    "SELECT symbol, MAX(timestamp) as latest, COUNT(*) as bars "
    "FROM ohlcv WHERE timeframe='1m' "
    "GROUP BY symbol ORDER BY latest DESC LIMIT 20"
).fetchall()

now_utc = datetime.now(timezone.utc)
print(f"Current UTC time: {now_utc.isoformat()}")
print(f"{'Symbol':10s} | {'Latest bar (raw)':30s} | {'Age (min)':10s} | {'Bars':6s}")
print('-' * 70)
for r in rows:
    sym, ts_raw, bars = r
    try:
        # Try parsing with timezone info
        if ts_raw and '+' in ts_raw:
            ts = datetime.fromisoformat(ts_raw)
        elif ts_raw and ts_raw.endswith('Z'):
            ts = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
        elif ts_raw:
            # Assume UTC if no tz info
            ts = datetime.fromisoformat(ts_raw).replace(tzinfo=timezone.utc)
        else:
            ts = None
        
        if ts:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_min = (now_utc - ts).total_seconds() / 60
            print(f"{sym:10s} | {ts_raw:30s} | {age_min:10.1f} | {bars:6d}")
        else:
            print(f"{sym:10s} | {'NO TIMESTAMP':30s} | {'N/A':10s} | {bars:6d}")
    except Exception as e:
        print(f"{sym:10s} | {str(ts_raw):30s} | ERROR: {e}")

conn.close()

# Now check what the brain's staleness logic expects
print()
print("--- Brain staleness gate context ---")
print("Brain uses: (now - latest_bar).total_seconds() / 60 > threshold")
print("The threshold is set in _fetch_ohlcv(). Let's find it.")
