import sqlite3, os

for path in ["data/trading.db", "trading.db", "market_data.db"]:
    exists = os.path.exists(path)
    print(f"\n=== {path} (exists={exists}) ===")
    if not exists:
        continue
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in c.fetchall()]
    print(f"  Tables: {tables}")
    if "ohlcv" in tables:
        c.execute("SELECT COUNT(*) FROM ohlcv")
        cnt = c.fetchone()[0]
        print(f"  ohlcv rows: {cnt}")
        if cnt > 0:
            c.execute("SELECT symbol, COUNT(*), MAX(timestamp) FROM ohlcv GROUP BY symbol ORDER BY MAX(timestamp) DESC LIMIT 5")
            for row in c.fetchall():
                print(f"    {row[0]}: {row[1]} rows, latest={row[2]}")
    conn.close()
