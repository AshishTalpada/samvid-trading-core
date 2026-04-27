import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)

def wipe_dirty_memory():
    db1 = "data/sovereign_memory.db"
    db2 = "data/evolution.db"

    # Wipe Trading Memory
    if os.path.exists(db1):
        try:
            conn = sqlite3.connect(db1)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades")
            cursor.execute("DELETE FROM signals")
            conn.commit()
            conn.close()
            logging.info("SUCCESS: Wiped 'trades' and 'signals' from Sovereign Memory.")
        except Exception as e:
            logging.error(f"Failed to wipe {db1}: {e}\n(Please stop your running Python processes first!)")

    # Wipe Evolution / Reinforcement Learning Memory
    if os.path.exists(db2):
        try:
            conn = sqlite3.connect(db2)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM decision_snapshots")
            conn.commit()
            conn.close()
            logging.info("SUCCESS: Wiped 'decision_snapshots' from Evolution Memory.")
        except Exception as e:
            logging.error(f"Failed to wipe {db2}: {e}")

if __name__ == "__main__":
    wipe_dirty_memory()
