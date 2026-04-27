import pandas as pd
import sqlite3
from datetime import datetime

conn = sqlite3.connect("data/trading.db")
df = pd.read_sql_query(
    "SELECT timestamp FROM ohlcv WHERE symbol='SPY' ORDER BY timestamp DESC LIMIT 1",
    conn
)
conn.close()

ts_str = df['timestamp'].iloc[0]
print(f"Raw timestamp string: {repr(ts_str)}")

latest_bar_ts = pd.to_datetime(ts_str)
print(f"pd.to_datetime result: {latest_bar_ts}")
print(f"tzinfo: {latest_bar_ts.tzinfo}")

now_ts = pd.Timestamp.now()
print(f"pd.Timestamp.now(): {now_ts}")
print(f"now tzinfo: {now_ts.tzinfo}")

# --- Simulate the brain's staleness logic ---
try:
    if latest_bar_ts.tzinfo is not None:
        latest_bar_ts = latest_bar_ts.tz_localize(None)  # This would FAIL on tz-aware ts
    if now_ts.tzinfo is not None:
        now_ts = now_ts.tz_localize(None)

    staleness = (now_ts - latest_bar_ts).total_seconds()
    print(f"\nStaleness: {staleness/3600:.2f} hours ({staleness:.0f}s)")
    print(f"24h limit = 86400s")
    print(f"STALE? {staleness > 86400}")
except Exception as e:
    print(f"\nERROR during staleness check: {type(e).__name__}: {e}")

# --- Correct approach ---
print("\n--- Correct approach (tz_convert then tz_localize) ---")
ts2 = pd.to_datetime(ts_str)
if ts2.tzinfo is not None:
    ts2 = ts2.tz_convert(None)  # Convert to UTC-naive
now2 = pd.Timestamp.now()
staleness2 = (now2 - ts2).total_seconds()
print(f"Staleness: {staleness2/3600:.2f} hours")
print(f"STALE? {staleness2 > 86400}")
