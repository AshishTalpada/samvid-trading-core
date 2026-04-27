import sqlite3
import os

def check_stress_data():
    db_path = "data/trading_stress.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    print(f"--- Checking {db_path} (Deep History) ---")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Pull everything from deep history
        query = """
        SELECT 
            timestamp, 
            instrument, 
            direction, 
            entry_price, 
            exit_price, 
            shares, 
            pnl_dollars, 
            net_pnl, 
            commission + slippage as total_fees,
            outcome
        FROM trades 
        ORDER BY timestamp DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("No trades found in deep history table.")
            return

        print("=" * 110)
        print(f"{'TIMESTAMP':<25} | {'SYM':<7} | {'DIR':<5} | {'ENTRY':<8} | {'EXIT':<8} | {'PNL':<9} | {'NET':<9} | {'FEES':<6} | {'STATUS'}")
        print("-" * 110)
        
        for r in rows:
            ts, sym, direct, entry, exit_p, shares, pnl, net, fees, outcome = r
            
            entry_f = f"{entry:.2f}" if entry else "---"
            exit_f = f"{exit_p:.2f}" if exit_p else "---"
            pnl_f = f"{pnl:+.2f}" if pnl is not None else "0.00"
            net_f = f"{net:+.2f}" if net is not None else "0.00"
            fees_f = f"{fees:.2f}" if fees is not None else "0.00"
            
            print(f"{ts[:23]:<25} | {sym:<7} | {direct:<5} | {entry_f:<8} | {exit_f:<8} | {pnl_f:<9} | {net_f:<9} | {fees_f:<6} | {outcome}")
            
        print("=" * 110)
        
        # Summary
        cursor.execute("SELECT COUNT(*), SUM(pnl_dollars), SUM(net_pnl), SUM(commission + slippage) FROM trades WHERE outcome != 'OPEN'")
        count, gross, net_total, fees_total = cursor.fetchone()
        
        if count and count > 0:
            print(f"\nDEEP HISTORY ANALYSIS:")
            print(f"Total Trades Analyzed: {count}")
            print(f"Gross P&L:             ${gross:+.2f}")
            print(f"Total Fees:           ${fees_total:.2f}")
            print(f"Net Realized P&L:      ${net_total:+.2f}")
            print(f"Win Rate:              {(gross > 0):.0%}")
        else:
             print("\nNote: Deep history shows no closed trades.")

        conn.close()
    except Exception as e:
        print(f"Error reading stress DB: {e}")

if __name__ == "__main__":
    check_stress_data()
