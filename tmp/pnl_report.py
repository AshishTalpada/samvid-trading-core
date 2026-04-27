# pyright: reportMissingImports=false
import sqlite3
import sys, os
sys.path.insert(0, os.getcwd())

try:
    from src.database_security import DatabaseSecurity  # type: ignore
except ImportError:
    from database_security import DatabaseSecurity  # type: ignore

conn = sqlite3.connect('data/trading.db')
c = conn.cursor()

c.execute("""
    SELECT id, timestamp, instrument, pattern, entry_price, exit_price, shares,
           pnl_dollars, r_multiple, hold_hours, outcome, trading_mode
    FROM trades ORDER BY id
""")
rows = c.fetchall()

print("=" * 90)
print(f"{'#':>2} | {'Time':>16} | {'Sym':>5} | {'Pattern':>25} | {'Entry':>8} | {'Exit':>8} | {'Qty':>4} | {'PnL':>10} | {'R-Mult':>7} | {'Hold':>6} | Outcome")
print("-" * 90)

total_pnl = 0.0
closed = 0

for r in rows:
    tid, ts, sym, pat, entry, exit_p, qty, pnl_enc, rm_enc, hold, outcome, mode = r
    
    ts_short = ts[5:16] if ts else "?"
    
    # Decrypt PnL and R-multiple
    pnl_str = "—"
    rm_str = "—"
    pnl_val = 0.0
    if pnl_enc and outcome not in ('OPEN', 'ORPHANED'):
        try:
            # HYBRID RECOVERY: Check if it's already a float or needs decryption
            if isinstance(pnl_enc, (float, int)):
                pnl_val = float(pnl_enc)
            else:
                pnl_val = DatabaseSecurity.decrypt_float(str(pnl_enc))
            pnl_str = f"${pnl_val:+.2f}"
            total_pnl += pnl_val
            closed += 1
        except:
            pnl_str = "[ERR]"
    if rm_enc and outcome not in ('OPEN', 'ORPHANED'):
        try:
            if isinstance(rm_enc, (float, int)):
                rm_val = float(rm_enc)
            else:
                rm_val = DatabaseSecurity.decrypt_float(str(rm_enc))
            rm_str = f"{rm_val:+.2f}R"
        except:
            rm_str = "[ERR]"
    
    hold_str = f"{hold:.1f}m" if hold and hold < 1 else (f"{hold:.1f}h" if hold else "—")
    if hold and hold < 1:
        hold_str = f"{hold*60:.0f}m"
    
    exit_str = f"${exit_p:.2f}" if exit_p else "—"
    
    print(f"{tid:>2} | {ts_short:>16} | {sym:>5} | {pat:>25} | ${entry:>7.2f} | {exit_str:>8} | {qty:>4.0f} | {pnl_str:>10} | {rm_str:>7} | {hold_str:>6} | {outcome}")

print("-" * 90)
print(f"\nClosed trades: {closed}")
print(f"Total P&L:     ${total_pnl:+.2f}")
print(f"Open/Orphaned: {len(rows) - closed}")

conn.close()
