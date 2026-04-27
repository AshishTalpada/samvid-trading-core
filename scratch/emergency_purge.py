import asyncio
import sqlite3
from datetime import datetime
import os

DB_PATH = "c:/Users/talpa/Desktop/System_Beta/TradingSystem/trades.db"
SESSION_PATH = "c:/Users/talpa/Desktop/System_Beta/TradingSystem/.session.bin"

def purge_corruption():
    print("🏹 SOVEREIGN EMERGENCY PURGE: Cleaning session-state poisoning...")
    
    # 1. Kill the corrupted session file
    if os.path.exists(SESSION_PATH):
        try:
            os.remove(SESSION_PATH)
            print(f"✅ DELETED: {SESSION_PATH} (Corrupted state excised)")
        except Exception as e:
            print(f"❌ FAILED to delete session: {e}")
    else:
        print("ℹ️ SESSION: No file found, proceed to DB check.")

    # 2. Verify DB Integrity
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM trades WHERE outcome='OPEN'")
        open_trades = cursor.fetchone()[0]
        print(f"🏛️ DATABASE: {open_trades} open trades identified for recovery.")
        conn.close()
    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")

    print("🚀 PURGE COMPLETE. Restart the system now.")

if __name__ == "__main__":
    purge_corruption()
