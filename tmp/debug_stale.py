import sqlite3
import pandas as pd
from datetime import datetime, timezone

conn = sqlite3.connect('data/trading.db')
# Get a few rows for AAPL
df = pd.read_sql_query(
    "SELECT timestamp, open, high, low, close, volume FROM ohlcv WHERE symbol='AAPL' AND timeframe='1m' ORDER BY timestamp DESC LIMIT 5",
    conn
)
conn.close()

print("Raw timestamps from DB:")
print(df['timestamp'].tolist())
print()

# Simulate exactly what brain does
latest_bar_ts = pd.to_datetime(df['timestamp']).max()
now_ts = pd.Timestamp.now()
print(f"latest_bar_ts = {latest_bar_ts}  (tzinfo={latest_bar_ts.tzinfo})")
print(f"now_ts        = {now_ts}  (tzinfo={now_ts.tzinfo})")

if latest_bar_ts.tzinfo is not None:
    latest_bar_ts_stripped = latest_bar_ts.tz_localize(None)
else:
    latest_bar_ts_stripped = latest_bar_ts

print(f"latest_bar stripped = {latest_bar_ts_stripped}")
staleness = (now_ts - latest_bar_ts_stripped).total_seconds()
print(f"Staleness = {staleness:.0f}s = {staleness/60:.1f} min  ← BUG HERE")

# Correct approach: convert to UTC first, then strip
print()
print("=== CORRECT approach ===")
latest_bar_utc = pd.to_datetime(df['timestamp']).max()
if latest_bar_utc.tzinfo is not None:
    latest_bar_utc = latest_bar_utc.tz_convert('UTC').tz_localize(None)
now_utc = pd.Timestamp.utcnow()
staleness_correct = (now_utc - latest_bar_utc).total_seconds()
print(f"latest_bar (UTC stripped) = {latest_bar_utc}")
print(f"now (UTC)                 = {now_utc}")
print(f"Correct staleness = {staleness_correct:.0f}s = {staleness_correct/60:.1f} min")
