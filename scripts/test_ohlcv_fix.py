# pyre-ignore-all-errors[21]
import sqlite3  # pyre-ignore[21]
import sys  # pyre-ignore[21]
from pathlib import Path  # pyre-ignore[21]

import pandas as pd  # pyre-ignore[21]

# Add project root and src to path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

from data_pipeline import DataPipeline  # pyre-ignore[21]


def test_fix():
    pipeline = DataPipeline(db_path="test_trading.db")

    # Simulate YFinance DataFrame (TitleCase, DatetimeIndex)
    dates = pd.date_range("2026-03-23", periods=5, freq="h")
    df = pd.DataFrame(
        {
            "Open": [100.0] * 5,
            "High": [101.0] * 5,
            "Low": [99.0] * 5,
            "Close": [100.5] * 5,
            "Volume": [1000] * 5,
        },
        index=dates,
    )

    conn = sqlite3.connect("test_trading.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv
        (symbol TEXT, timestamp TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, timeframe TEXT)
    """)
    conn.commit()

    print("Testing store_ohlcv with NQ=F simulation...")
    try:
        pipeline.store_ohlcv("NQ=F", df, conn)
        print("Success! No KeyError.")

        cursor.execute("SELECT * FROM ohlcv LIMIT 1")
        row = cursor.fetchone()
        print(f"Sample stored row: {row}")
    except Exception as e:
        print(f"FAILED: {e}")
    finally:
        conn.close()
        # Path("test_trading.db").unlink()


if __name__ == "__main__":
    test_fix()
