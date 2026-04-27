import sqlite3
import os

db_path = "data/trading.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM loss_tracker")
    cursor.execute("UPDATE system_state SET value='0' WHERE key='consecutive_losses'")
    conn.commit()
    conn.close()
    print("Sovereign Bridge: DB Reset Successful.")
else:
    print("Sovereign Bridge: DB not found.")
