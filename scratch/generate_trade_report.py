import sqlite3
import os

def generate_report():
    db_path = "data/trading.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Selecting the core trade details
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
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        
        print("=" * 100)
        print(f"{'TIMESTAMP':<25} | {'SYM':<6} | {'DIR':<5} | {'ENTRY':<8} | {'EXIT':<8} | {'PNL':<8} | {'NET':<8} | {'FEES':<6} | {'STATUS'}")
        print("-" * 100)
        
        for r in rows:
            ts, sym, direct, entry, exit_p, shares, pnl, net, fees, outcome = r
            
            # Formatting values for display
            entry_f = f"{entry:.2f}" if entry else "0.00"
            exit_f = f"{exit_p:.2f}" if exit_p else "0.00"
            pnl_f = f"{pnl:+.2f}" if pnl is not None else "0.00"
            net_f = f"{net:+.2f}" if net is not None else "0.00"
            fees_f = f"{fees:.2f}" if fees is not None else "0.00"
            
            print(f"{ts[:23]:<25} | {sym:<6} | {direct:<5} | {entry_f:<8} | {exit_f:<8} | {pnl_f:<8} | {net_f:<8} | {fees_f:<6} | {outcome}")
            
        print("=" * 100)
        
        # Performance Summary
        cursor.execute("SELECT SUM(pnl_dollars), SUM(net_pnl), SUM(commission + slippage) FROM trades WHERE outcome != 'OPEN'")
        summary = cursor.fetchone()
        
        if summary and summary[0] is not None:
             print(f"\nCLOSED TRADE SUMMARY:")
             print(f"Total Gross P&L: ${summary[0]:+.2f}")
             print(f"Total Fees:      ${summary[2]:.2f}")
             print(f"Total Net P&L:    ${summary[1]:+.2f}")
        else:
             print("\nNote: All trades in the database are currently marked as 'OPEN' (No closed trades to summarize).")

    except Exception as e:
        print(f"Error generating report: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    generate_report()
