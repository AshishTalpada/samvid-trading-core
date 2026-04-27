import sqlite3
import os

def find_trades():
    dbs = ["data/trading.db", "data/trading_stress.db", "data/evolution.db"]
    
    for db_path in dbs:
        if not os.path.exists(db_path):
            continue
            
        print(f"\n--- Checking DB: {db_path} ---")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Tables: {tables}")
        
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  - Table '{table}': {count} rows")
                
                if count > 0 and table.lower() in ["trades", "trade_history", "completed_trades", "results"]:
                    cursor.execute(f"PRAGMA table_info({table})")
                    cols = [c[1] for c in cursor.fetchall()]
                    print(f"    Columns: {cols}")
                    
                    # Try to fetch actual results if it looks like a trade table
                    if "pnl_dollars" in cols or "pnl" in cols:
                        pnl_col = "pnl_dollars" if "pnl_dollars" in cols else "pnl"
                        cursor.execute(f"SELECT instrument, {pnl_col}, timestamp FROM {table} WHERE {pnl_col} != 0 LIMIT 5")
                        actuals = cursor.fetchall()
                        if actuals:
                            print(f"    Actual Results found!")
                            for act in actuals:
                                print(f"      * {act}")
            except:
                pass
        conn.close()

if __name__ == "__main__":
    find_trades()
