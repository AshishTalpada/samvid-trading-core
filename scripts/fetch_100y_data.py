import sqlite3

import yfinance as yf

DB_PATH = "training_data.db"
SYMBOLS = ["^GSPC", "^DJI", "^IXIC", "SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "NVDA", "AAPL", "MSFT", "AMZN"]

def init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            symbol TEXT, timeframe TEXT, timestamp TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            PRIMARY KEY (symbol, timeframe, timestamp)
        )
    """)
    conn.commit()
    return conn

def fetch_max_history():
    print(f"📡 Initializing 100-year index backfill into {DB_PATH}...")
    conn = init_db(DB_PATH)

    for symbol in SYMBOLS:
        print(f"  ▶ Fetching MAX history for {symbol}...")
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="max", interval="1d", auto_adjust=True)
            if df.empty:
                print(f"    ⚠ No data found for {symbol}")
                continue

            rows = []
            for ts, row in df.iterrows():
                rows.append((
                    symbol, "1d",
                    str(ts),
                    float(row.get("Open", 0)),
                    float(row.get("High", 0)),
                    float(row.get("Low", 0)),
                    float(row.get("Close", 0)),
                    float(row.get("Volume", 0)),
                ))

            conn.executemany(
                "INSERT OR REPLACE INTO ohlcv VALUES (?,?,?,?,?,?,?,?)", rows
            )
            conn.commit()
            print(f"    ✓ Stored {len(rows)} daily bars for {symbol} (Start: {df.index[0].date()}, End: {df.index[-1].date()})")

        except Exception as e:
            print(f"    ❌ Error fetching {symbol}: {e}")

    conn.close()
    print("\n✅ 100-year (max available) backfill complete.")

if __name__ == "__main__":
    fetch_max_history()
