import sqlite3
import os
import sys
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from database_security import DatabaseSecurity

def get_report():
    db_path = "data/trading.db"
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")
    
    # Query today's trades
    # Note: timestamp is stored as ISO format (e.g. 2026-04-10T14:41:00.123)
    cursor.execute("SELECT instrument, direction, pattern, entry_price, exit_price, pnl_dollars, outcome, timestamp FROM trades WHERE timestamp LIKE ?", (f"{today}%",))
    rows = cursor.fetchall()
    
    print(f"\n{'='*90}")
    print(f"🌌 SOVEREIGN TRADE LEDGER - {today}")
    print(f"{'='*90}")
    print(f"{'SYMBOL':<10} | {'SIDE':<6} | {'PATTERN':<20} | {'ENTRY':<8} | {'EXIT':<8} | {'PnL ($)':<12} | {'STATUS'}")
    print("-" * 90)

    total_pnl = 0.0
    wins = 0
    losses = 0

    for row in rows:
        sym, side, pattern, entry, exit_pr, raw_pnl, outcome, ts = row
        
        # Decrypt PnL if it's stored as an encrypted string
        pnl = 0.0
        if raw_pnl:
            try:
                # If it's a number (early version), just float it
                pnl = float(raw_pnl)
            except ValueError:
                # Otherwise, decrypt it
                pnl = DatabaseSecurity.decrypt_float(raw_pnl)

        pnl_str = f"{pnl:>10.2f}"
        exit_str = f"{exit_pr:>8.2f}" if exit_pr else "OPEN"
        entry_str = f"{entry:>8.2f}" if entry else "N/A"

        print(f"{sym:<10} | {side:<6} | {pattern:<20} | {entry_str} | {exit_str} | {pnl_str} | {outcome}")
        
        if outcome != "OPEN":
            total_pnl += pnl
            if pnl > 0: wins += 1
            elif pnl < 0: losses += 1

    print("-" * 90)
    print(f"TOTAL REALIZED P&L:  ${total_pnl:,.2f}")
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    print(f"PERFORMANCE:        {wins} Wins / {losses} Losses ({win_rate:.1f}% Win Rate)")
    print(f"{'='*90}\n")

    conn.close()

if __name__ == "__main__":
    get_report()
