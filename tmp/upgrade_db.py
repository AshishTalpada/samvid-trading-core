import sqlite3
import os

db_path = "data/trading.db"

def upgrade_schema():
    if not os.path.exists(db_path):
        print("DB not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if we already added true cost columns
    cursor.execute("PRAGMA table_info(trades)")
    cols = [col[1] for col in cursor.fetchall()]
    
    new_cols = ['commission', 'slippage', 'net_pnl', 'mfe', 'mae']
    for col in new_cols:
        if col not in cols:
            try:
                cursor.execute(f"ALTER TABLE trades ADD COLUMN {col} REAL DEFAULT 0.0")
                print(f"Added column {col} to trades table.")
            except Exception as e:
                print(f"Could not add {col}: {e}")
                
    conn.commit()
    conn.close()

if __name__ == "__main__":
    upgrade_schema()
