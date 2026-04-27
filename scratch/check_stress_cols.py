import sqlite3
import os

def check_stress_cols():
    db_path = "data/trading_stress.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(agent_d_trades)")
    for col in cursor.fetchall():
        print(col)
    conn.close()

if __name__ == "__main__":
    check_stress_cols()
