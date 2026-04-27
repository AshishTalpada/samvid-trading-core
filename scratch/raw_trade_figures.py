import sqlite3
import os

def extract_raw_figures():
    db_path = "data/trading_stress.db"
    if not os.path.exists(db_path):
        print("Data error: Stress DB not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Selecting raw historical figures from Agent D's 500,000 trade history
    # We use outcome, r_multiple, pnl, and symbol
    query = """
        SELECT 
            recorded_at, 
            symbol, 
            pattern, 
            outcome, 
            r_multiple, 
            pnl
        FROM agent_d_trades 
        WHERE pnl != 0
        ORDER BY recorded_at DESC
        LIMIT 50
    """
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        
        print("=" * 130)
        print(f"{'TIMESTAMP (UTC)':<20} | {'STOCK':<12} | {'STRATEGY':<18} | {'STATUS':<8} | {'RR':<6} | {'GROSS PNL':<12} | {'NEW NET (INC $4 FEE)'}")
        print("-" * 130)
        
        for r in rows:
            ts, sym, patt, out, r_mult, pnl = r
            
            # Applying the NEW $2.00 entry + $2.00 exit commission fee from today's update
            new_net = pnl - 4.00
            
            pnl_f = f"${pnl:+.2f}"
            net_f = f"${new_net:+.2f}"
            r_f = f"{r_mult:+.2f}R"
            
            print(f"{ts:<20} | {sym:<12} | {patt:<18} | {out:<8} | {r_f:<6} | {pnl_f:<12} | {net_f}")
            
        print("=" * 130)
        
    except Exception as e:
        print(f"Extraction failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    extract_raw_figures()
