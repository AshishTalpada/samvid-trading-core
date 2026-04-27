import sqlite3
import os

def check_evolution_schema():
    db_path = "data/evolution.db"
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print(f"\n--- Schema for decision_snapshots ---")
    cursor.execute(f"PRAGMA table_info(decision_snapshots)")
    for col in cursor.fetchall():
        print(col)
    conn.close()

if __name__ == "__main__":
    check_evolution_schema()
