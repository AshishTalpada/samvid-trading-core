import os
import sys

sys.path.append(os.getcwd())
import asyncio
import os
import sqlite3

from src.data_pipeline import DataPipeline


async def verify_sync() -> None:
    print("🔍 VERIFYING ZERO-GAP SYNC LOGIC")
    db_path = "data/trading.db"

    # 1. Check current SPY state
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, timestamp FROM ohlcv WHERE symbol='SPY' AND timeframe='1m' ORDER BY timestamp DESC LIMIT 1"
    )
    row = cursor.fetchone()
    if not row:
        print("No SPY data found. Initializing...")
    else:
        print(f"Current Latest SPY: {row[1]} (id={row[0]})")

        # 2. Simulate Gap: Delete last 5 rows
        print("🗑️ Deleting last 5 rows to simulate gap...")
        cursor.execute(
            "DELETE FROM ohlcv WHERE id IN (SELECT id FROM ohlcv WHERE symbol='SPY' AND timeframe='1m' ORDER BY timestamp DESC LIMIT 5)"
        )
        conn.commit()

    conn.close()

    # 3. Start DataPipeline Sync
    pipeline = DataPipeline(db_path=db_path)
    # Only sync SPY to save time/api
    pipeline.INSTRUMENTS = ["SPY"]

    print("🔄 Running Sync...")
    # We call backfill_gap directly
    await pipeline.backfill_gap("SPY")

    # 4. Verify Recovery
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, timestamp FROM ohlcv WHERE symbol='SPY' AND timeframe='1m' ORDER BY timestamp DESC LIMIT 1"
    )
    new_row = cursor.fetchone()
    conn.close()

    if row and new_row:
        if new_row[1] >= row[1]:
            print(f"✅ SUCCESS: SPY recovered to {new_row[1]}")
        else:
            print(f"❌ FAILURE: SPY still at {new_row[1]}")
    elif not row and new_row:
        print(f"✅ SUCCESS: SPY initialized to {new_row[1]}")


if __name__ == "__main__":
    asyncio.run(verify_sync())
