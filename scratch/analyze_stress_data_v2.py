import sqlite3
import os

def analyze_deep_history():
    db_path = "data/trading_stress.db"
    if not os.path.exists(db_path):
        return

    print(f"--- ANALYZING DEEP HISTORY: Agent D Execution Records (STRESS DATA) ---")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Selecting the top 20 most recent results from the 500,000 entries
    query = """
        SELECT 
            recorded_at,
            symbol, 
            pattern,
            outcome, 
            r_multiple,
            pnl, 
            regime
        FROM agent_d_trades 
        WHERE pnl != 0
        ORDER BY recorded_at DESC
        LIMIT 20
    """
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        
        print("=" * 110)
        print(f"{'TIMESTAMP':<25} | {'SYM':<7} | {'PATTERN':<15} | {'OUTCOME':<10} | {'R-MULT':<8} | {'PNL':<10} | {'REGIME'}")
        print("-" * 110)
        
        for r in rows:
            ts, sym, patt, out, r_mult, pnl, reg = r
            pnl_f = f"${pnl:+.2f}"
            r_mult_f = f"{r_mult:+.2f}R"
            print(f"{ts[:23]:<25} | {sym:<7} | {patt:<15} | {out:<10} | {r_mult_f:<8} | {pnl_f:<10} | {reg}")
            
        print("=" * 110)
        
        # Aggregate Performance across ALL 500,000 trades
        cursor.execute("SELECT COUNT(*), SUM(pnl), AVG(pnl), AVG(r_multiple) FROM agent_d_trades WHERE pnl != 0")
        total, gross, avg_pnl, avg_r = cursor.fetchone()
        
        print(f"\nDEEP ANALYTICS REPORT:")
        print(f"Total Completed Trades: {total:,}")
        print(f"Cumulative Gross P&L:  ${gross:+.2f}")
        print(f"Average P&L per Trade: ${avg_pnl:+.2f}")
        print(f"Average R-Multiple:    {avg_r:+.2f}R")
        
    except Exception as e:
        print(f"Deep Analysis failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    analyze_deep_history()
