import sqlite3
import os

def check_data_v2():
    db_path = "data/trading.db"
    
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    print(f"--- Checking {db_path} ---")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check trades count
        cursor.execute("SELECT COUNT(*) FROM trades")
        trade_count = cursor.fetchone()[0]
        print(f"Total Trades: {trade_count}")
        
        if trade_count > 0:
            # Use 'instrument' instead of 'symbol'
            cursor.execute("SELECT instrument, pnl_dollars, timestamp, outcome FROM trades ORDER BY timestamp DESC LIMIT 5")
            print("\nRecent 5 trades:")
            for row in cursor.fetchall():
                print(f"  - {row[0]}: ${row[1]:.2f} ({row[3]}) at {row[2]}")
                
        # Calculate overall P&L
        cursor.execute("SELECT SUM(pnl_dollars), SUM(net_pnl) FROM trades")
        totals = cursor.fetchone()
        print(f"\nOverall Gross P&L: ${totals[0]:.2f}")
        print(f"Overall Net P&L:   ${totals[1]:.2f}")

        conn.close()
    except Exception as e:
        print(f"Error reading DB: {e}")

if __name__ == "__main__":
    check_data_v2()
