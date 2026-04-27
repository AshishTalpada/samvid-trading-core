import sqlite3
import os

db_path = 'data/trading.db'
if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT * FROM system_events WHERE event_type LIKE '%Architect%' OR message LIKE '%fix%' ORDER BY timestamp DESC LIMIT 5;")
    rows = cursor.fetchall()
    if not rows:
        print("No self-healing events found yet.")
    for row in rows:
        print(row)
    conn.close()
