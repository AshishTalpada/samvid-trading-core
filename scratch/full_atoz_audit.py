import sqlite3
import os

def extract_full_audit():
    db_path = "data/trading.db"
    if not os.path.exists(db_path):
        print("Data error: Main Trading DB not found.")
        return

    conn = sqlite3.connect(db_path)
    # This allows us to access columns by name
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Selecting the COMPLETE A-to-Z audit trail for the main paper/live history
    query = """
        SELECT 
            timestamp, 
            instrument, 
            direction, 
            pattern,
            shares, 
            entry_price, 
            stop_price,
            exit_price, 
            commission,
            slippage,
            pnl_dollars,
            net_pnl,
            outcome
        FROM trades 
        ORDER BY timestamp DESC
    """
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        
        print("=" * 160)
        print(f"{'TIMESTAMP':<25} | {'SYM':<6} | {'DIR':<5} | {'SHARES':<7} | {'ENTRY':<8} | {'STOP':<8} | {'EXIT':<8} | {'GROSS':<9} | {'FEES':<6} | {'NET PNL':<9} | {'STATUS'}")
        print("-" * 160)
        
        for r in rows:
            ts = r['timestamp'][:23]
            sym = r['instrument']
            direct = r['direction']
            shares = f"{r['shares']:.1f}"
            entry = f"{r['entry_price']:.2f}"
            # Some entries might not have an exit yet
            exit_p = f"{r['exit_price']:.2f}" if r['exit_price'] else "0.00"
            stop = f"{r['stop_price']:.2f}" if r['stop_price'] else "0.00"
            
            gross = f"{r['pnl_dollars']:+.2f}" if r['pnl_dollars'] is not None else "0.00"
            net = f"{r['net_pnl']:+.2f}" if r['net_pnl'] is not None else "0.00"
            
            # Total fees = commission + slippage
            fees = (r['commission'] or 0.0) + (r['slippage'] or 0.0)
            fees_f = f"{fees:.2f}"
            
            outcome = r['outcome']
            
            print(f"{ts:<25} | {sym:<6} | {direct:<5} | {shares:<7} | {entry:<8} | {stop:<8} | {exit_p:<8} | {gross:<9} | {fees_f:<6} | {net:<9} | {outcome}")
            
        print("=" * 160)
        
    except Exception as e:
        print(f"Full Audit failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    extract_full_audit()
