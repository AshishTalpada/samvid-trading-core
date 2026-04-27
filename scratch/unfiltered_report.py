import sqlite3
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))
from database_security import DatabaseSecurity

def generate_unfiltered_report():
    db_path = "data/trading.db"
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("="*120)
    print("      UNFILTERED SOVEREIGN RAW TRADE LOG")
    print("="*120)

    print(f"{'TIMESTAMP':<20} | {'SYM':<6} | {'DIR':<6} | {'OUTCOME':<10} | {'SHARES':<8} | {'ENTRY':<8} | {'EXIT':<8} | {'PNL ($)':<12}")
    print("-" * 120)

    cursor.execute("""
        SELECT timestamp, instrument, direction, outcome, shares, entry_price, exit_price, pnl_dollars 
        FROM trades 
        ORDER BY timestamp ASC
    """)
    rows = cursor.fetchall()

    for r in rows:
        ts, symbol, direction, outcome, shares, entry, exit, pnl_raw = r
        
        pnl = 0.0
        if isinstance(pnl_raw, (bytes, str)):
            if str(pnl_raw).startswith("gAAAA"):
                try:
                    pnl = DatabaseSecurity.decrypt_float(pnl_raw)
                except:
                    pnl = 0.0
            else:
                pnl = 0.0
        elif pnl_raw is not None:
            pnl = float(pnl_raw)

        entry = entry if entry is not None else 0.0
        exit = exit if exit is not None else 0.0
        shares = shares if shares is not None else 0.0

        print(f"{ts:<20} | {symbol:<6} | {str(direction):<6} | {str(outcome):<10} | {shares:<8.0f} | {entry:<8.2f} | {exit:<8.2f} | ${pnl:>10.2f}")

    print("="*120)
    conn.close()

if __name__ == "__main__":
    generate_unfiltered_report()
