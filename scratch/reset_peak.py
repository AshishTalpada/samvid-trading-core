import sqlite3
import os

db_path = 'data/trading.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE system_state SET value='500.0' WHERE key='peak_equity'")
        conn.commit()
        print("Successfully reset peak_equity to 500.0")
    except Exception as e:
        print(f"Error updating database: {e}")
    finally:
        conn.close()
else:
    print(f"Database not found at {db_path}")
