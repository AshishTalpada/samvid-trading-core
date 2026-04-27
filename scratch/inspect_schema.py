import sqlite3
import os

def inspect_schema():
    db_path = "data/trading.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    tables = ["trades", "system_state"]
    for table in tables:
        print(f"\n--- Schema for {table} ---")
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            for col in cursor.fetchall():
                print(col)
        except Exception as e:
            print(f"Error: {e}")
            
    conn.close()

if __name__ == "__main__":
    inspect_schema()
