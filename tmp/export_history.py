import sqlite3
import os
import sys

sys.path.insert(0, os.path.abspath('.'))
from src.database_security import DatabaseSecurity

conn = sqlite3.connect('data/trading.db')
cursor = conn.cursor()
cursor.execute("SELECT timestamp, instrument, direction, pattern, regime, entry_price, exit_price, outcome, pnl_dollars, hold_hours FROM trades ORDER BY timestamp")
rows = cursor.fetchall()

md = []
md.append("| Time | Symbol | Side | Pattern | Regime | Entry | Exit | PnL | Status | Hold (hrs) |")
md.append("|---|---|---|---|---|---|---|---|---|---|")

for r in rows:
    ts, symbol, direction, pattern, regime, entry, exit_px, outcome, pnl, hold = r
    
    # Decrypt PnL if available
    try:
        if pnl and pnl != '':
            pnl_val = DatabaseSecurity.decrypt_float(pnl)
            pnl_str = f"${pnl_val:,.2f}"
        else:
            pnl_str = "-"
    except:
        pnl_str = "Err"
        
    entry_str = f"${entry:.2f}" if entry else "-"
    exit_str = f"${exit_px:.2f}" if exit_px else "-"
    hold_str = f"{hold:.1f}" if hold else "-"
    
    # Clean up timestamp
    ts_short = ts[:19].replace('T', ' ') if ts else "-"
    
    md.append(f"| {ts_short} | {symbol} | {direction} | {pattern} | {regime} | {entry_str} | {exit_str} | {pnl_str} | {outcome} | {hold_str} |")

with open('tmp/trade_history.md', 'w') as f:
    f.write("\n".join(md))

print(f"Exported {len(rows)} trades to tmp/trade_history.md")
