import sqlite3
import os

def check_deep_history():
    # Target the massive stress DB
    db_path = "data/trading_stress.db"
    if not os.path.exists(db_path):
        return

    print(f"--- ANALYZING DEEP HISTORY: Agent D Execution Records ---")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check columns of agent_d_trades
    cursor.execute("PRAGMA table_info(agent_d_trades)")
    cols = {c[1]: c[2] for c in cursor.fetchall()}
    
    # Build query based on common schema
    # Selecting the top 20 most recent COMPLETED trades from the 500,000 entries
    query = f"""
        SELECT 
            symbol, 
            entry_price, 
            exit_price, 
            pnl_dollars, 
            result_label,
            timestamp
        FROM agent_d_trades 
        WHERE pnl_dollars != 0
        ORDER BY timestamp DESC
        LIMIT 20
    """
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        
        print("=" * 110)
        print(f"{'TIMESTAMP':<25} | {'SYM':<7} | {'ENTRY':<10} | {'EXIT':<10} | {'PROFIT/LOSS':<15} | {'RESULT'}")
        print("-" * 110)
        
        for r in rows:
            sym, entry, exit_p, pnl, label, ts = r
            pnl_f = f"${pnl:+.2f}"
            print(f"{ts[:23]:<25} | {sym:<7} | {entry:<10.2f} | {exit_p:<10.2f} | {pnl_f:<15} | {label}")
            
        print("=" * 110)
        
        # Aggregate Performance
        cursor.execute("SELECT COUNT(*), SUM(pnl_dollars), AVG(pnl_dollars) FROM agent_d_trades WHERE pnl_dollars != 0")
        total, gross, avg = cursor.fetchone()
        
        print(f"\nDEEP ANALYTICS REPORT (500,000 Simulation Samples):")
        print(f"Total Completed Trades: {total:,}")
        print(f"Cumulative Gross P&L:  ${gross:+.2f}")
        print(f"Average P&L per Trade: ${avg:+.2f}")
        
    except Exception as e:
        print(f"Search failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_deep_history()
