import sqlite3
import os
import sys

def check_data():
    db_path = "data/trading.db"
    evolution_db = "data/evolution.db"
    
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    print(f"--- Checking {db_path} ---")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check trades
        cursor.execute("SELECT COUNT(*) FROM trades")
        trade_count = cursor.fetchone()[0]
        print(f"Total Trades: {trade_count}")
        
        if trade_count > 0:
            cursor.execute("SELECT symbol, pnl_dollars, timestamp FROM trades ORDER BY timestamp DESC LIMIT 5")
            print("Recent 5 trades:")
            for row in cursor.fetchall():
                print(f"  - {row[0]}: ${row[1]:.2f} at {row[2]}")
                
        # Check system_state
        cursor.execute("SELECT key, value FROM system_state")
        print("\nSystem State:")
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[1]}")
            
        conn.close()
    except Exception as e:
        print(f"Error reading main DB: {e}")

    if os.path.exists(evolution_db):
        print(f"\n--- Checking {evolution_db} ---")
        try:
            conn = sqlite3.connect(evolution_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM decision_snapshots")
            snap_count = cursor.fetchone()[0]
            print(f"Total Decision Snapshots: {snap_count}")
            conn.close()
        except Exception as e:
            print(f"Error reading Evolution DB: {e}")
    else:
        print(f"\nEvolution DB {evolution_db} not found.")

if __name__ == "__main__":
    check_data()
