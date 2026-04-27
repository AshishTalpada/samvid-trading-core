import sqlite3, datetime

conn = sqlite3.connect('market_data.db')
cur = conn.cursor()

# Check schema
print("=== OHLCV SCHEMA ===")
cur.execute("PRAGMA table_info(ohlcv)")
for col in cur.fetchall():
    print(col)

print("\n=== SAMPLE ROWS (first 3) ===")
cur.execute("SELECT * FROM ohlcv LIMIT 3")
for row in cur.fetchall():
    print(row)

print("\n=== DISTINCT SYMBOLS ===")
cur.execute("SELECT DISTINCT symbol, COUNT(*) FROM ohlcv GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 10")
for row in cur.fetchall():
    print(row)

print("\n=== TIMEFRAME VALUES ===")
cur.execute("SELECT DISTINCT timeframe, COUNT(*) FROM ohlcv GROUP BY timeframe")
for row in cur.fetchall():
    print(repr(row))

print("\n=== AAPL LATEST ROWS ===")
# Try without timeframe filter first
cur.execute("SELECT timestamp, open, close FROM ohlcv WHERE symbol='AAPL' ORDER BY timestamp DESC LIMIT 3")
for row in cur.fetchall():
    print(row)

print("\n=== AAPL WITH TIMEFRAME='1m' ===")
cur.execute("SELECT COUNT(*) FROM ohlcv WHERE symbol='AAPL' AND timeframe='1m'")
print("count:", cur.fetchone())

conn.close()
