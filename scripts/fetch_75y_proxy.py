import logging
import sqlite3

import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HistoryFetcher")

DB_PATH = "training_data.db"

def fetch_75y():
    print("🚀 FETCHING 75 YEARS OF MULTI-SECTOR MACRO-FIDELITY DATA...")
    tickers = {
        "^GSPC": "SPY_PROXY",
        "^NDX": "QQQ_PROXY",
        "^RUT": "IWM_PROXY"
    }

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for symbol, proxy_name in tickers.items():
        print(f"  ▶ Downloading {symbol} ({proxy_name})...")
        df = yf.download(symbol, start="1950-01-01", end="2026-04-12", interval="1d")

        if df.empty:
            print(f"  ⚠️ No data for {symbol}")
            continue

        # Flatten columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]

        records = []
        for ts, row in df.iterrows():
            o, h, l, c = float(row['open']), float(row['high']), float(row['low']), float(row['close'])
            if h <= l:
                h = max(o, c, h) + 0.01
                l = min(o, c, l) - 0.01

            records.append((
                proxy_name,
                ts.strftime("%Y-%m-%d %H:%M:%S"),
                o, h, l, c,
                float(row['volume']),
                "1d"
            ))

        cursor.executemany("INSERT OR IGNORE INTO ohlcv VALUES (?,?,?,?,?,?,?,?)", records)
        conn.commit()
        print(f"  ✅ Ingested {len(records)} days of {proxy_name}.")

    conn.close()
    print("✨ Sector-Hardening Data Fetch Complete.")

if __name__ == "__main__":
    fetch_75y()
