import sqlite3
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))
from database_security import DatabaseSecurity

def generate_report():
    db_path = "data/trading.db"
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("="*60)
    print("      SOVEREIGN OPERATIONAL REPORT - APRIL 14, 2026")
    print("="*60)

    # 1. Total Equity and Peak
    cursor.execute("SELECT value FROM system_state WHERE key='peak_equity'")
    peak = cursor.fetchone()
    peak_val = float(peak[0]) if peak else 0.0
    
    # Estimate current equity from last heartbeat or simply from drawndown state if available
    # For now we'll focus on the realized gains/losses today
    
    print(f"HIGH-WATER MARK (PEAK): ${peak_val:,.2f}")
    print("-" * 60)

    # 2. Today's Realized Trades
    # Note: Using date('now') works if the DB date matches system date
    cursor.execute("""
        SELECT instrument, shares, entry_price, exit_price, pnl_dollars, outcome, timestamp 
        FROM trades 
        WHERE date(timestamp) >= date('now', '-1 day')
        ORDER BY timestamp DESC
    """)
    rows = cursor.fetchall()

    if not rows:
        print("No realized trades recorded in the last 24 hours.")
    else:
        print(f"{'SYMBOL':<8} | {'STATUS':<10} | {'SHARES':<8} | {'PNL ($)':<12}")
        print("-" * 60)
        total_pnl = 0.0
        for r in rows:
            symbol, shares, entry, exit, pnl_raw, outcome, ts = r
            
            # Decrypt PnL if it's a byte string
            pnl = 0.0
            if isinstance(pnl_raw, bytes):
                try:
                    pnl = DatabaseSecurity.decrypt_float(pnl_raw)
                except:
                    pnl = 0.0
            elif isinstance(pnl_raw, (int, float)):
                pnl = float(pnl_raw)
            
            # Filter for only closed today or active
            # (In a real report we'd be more specific)
            
            print(f"{symbol:<8} | {outcome:<10} | {int(shares):<8} | ${pnl:>10.2f}")
            total_pnl += pnl
        
        print("-" * 60)
        print(f"{'TOTAL REALIZED PNL (LAST 24H):':<42} ${total_pnl:>10.2f}")

    print("="*60)
    print("SYSTEM STATUS: ACTIVE / MANAGING")
    
    conn.close()

if __name__ == "__main__":
    generate_report()
