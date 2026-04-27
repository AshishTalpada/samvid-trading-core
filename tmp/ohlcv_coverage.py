import sqlite3

conn = sqlite3.connect("data/trading.db")
c = conn.cursor()
c.execute("SELECT symbol, COUNT(*), MIN(timestamp), MAX(timestamp) FROM ohlcv GROUP BY symbol ORDER BY symbol")
rows = c.fetchall()
print(f"Total symbols with data: {len(rows)}")
print(f"{'SYMBOL':<10} {'ROWS':>5}  LATEST TIMESTAMP")
print("-" * 55)
for r in rows:
    print(f"{r[0]:<10} {r[1]:>5}  {r[3]}")

c.execute("SELECT COUNT(DISTINCT symbol) FROM ohlcv")
print(f"\nDistinct symbols in ohlcv: {c.fetchone()[0]}")

c.execute("SELECT DISTINCT timeframe FROM ohlcv")
print(f"Timeframes: {[t[0] for t in c.fetchall()]}")
conn.close()
