# pyright: reportMissingImports=false
import sqlite3, sys, os
sys.path.insert(0, os.getcwd())
try:
    from src.database_security import DatabaseSecurity  # type: ignore
except ImportError:
    from database_security import DatabaseSecurity  # type: ignore

conn = sqlite3.connect('data/trading.db')
c = conn.cursor()
c.execute('''SELECT id, timestamp, instrument, direction, pattern, entry_price, exit_price, shares, pnl_dollars, r_multiple, hold_hours, outcome, trading_mode FROM trades ORDER BY id''')
rows = c.fetchall()

lines = []
lines.append(f'Total trades in DB: {len(rows)}')
lines.append('')

total_pnl = 0.0
closed = 0
wins = 0
losses = 0
breakeven = 0

for r in rows:
    tid, ts, sym, direction, pat, entry, exit_p, qty, pnl_enc, rm_enc, hold, outcome, mode = r
    pnl_val = None
    rm_val = None
    if pnl_enc and outcome not in ('OPEN', 'ORPHANED'):
        try:
            # HYBRID RECOVERY: Handle plaintext and encrypted
            if isinstance(pnl_enc, (float, int)):
                pnl_val = float(pnl_enc)
            else:
                pnl_val = DatabaseSecurity.decrypt_float(str(pnl_enc))
            total_pnl += pnl_val
            closed += 1
            if pnl_val > 0:
                wins += 1
            elif pnl_val < 0:
                losses += 1
            else:
                breakeven += 1
        except Exception:
            pnl_val = 'ERR'
    if rm_enc and outcome not in ('OPEN', 'ORPHANED'):
        try:
            if isinstance(rm_enc, (float, int)):
                rm_val = float(rm_enc)
            else:
                rm_val = DatabaseSecurity.decrypt_float(str(rm_enc))
        except Exception:
            rm_val = 'ERR'

    if isinstance(pnl_val, float):
        pnl_str = f'${pnl_val:+.2f}'
    else:
        pnl_str = str(pnl_val)

    if isinstance(rm_val, float):
        rm_str = f'{rm_val:+.2f}R'
    else:
        rm_str = str(rm_val)

    exit_str = f'{exit_p:.2f}' if exit_p else 'OPEN'
    hold_str = f'{hold:.1f}h' if hold else '-'
    pat_short = (pat or '-')[:22]

    lines.append(
        f'#{tid:>2} | {ts[:19]} | {sym:>5} | {direction:>5} | {pat_short:>22} '
        f'| E:{entry:.2f} X:{exit_str} Q:{qty:.0f} '
        f'| PnL:{pnl_str:>10} | R:{rm_str:>7} | Hold:{hold_str:>6} | {outcome} | {mode}'
    )

lines.append('')
lines.append('=' * 40)
lines.append('SUMMARY')
lines.append('=' * 40)
lines.append(f'Total trades:    {len(rows)}')
lines.append(f'Closed trades:   {closed}')
lines.append(f'Open/Orphaned:   {len(rows) - closed}')
lines.append(f'Wins:            {wins}')
lines.append(f'Losses:          {losses}')
lines.append(f'Breakeven:       {breakeven}')
if closed:
    lines.append(f'Win Rate:        {wins/closed*100:.1f}%')
    lines.append(f'Total PnL:       ${total_pnl:+.2f}')
    lines.append(f'Avg PnL/trade:   ${total_pnl/closed:.2f}')
else:
    lines.append('No closed trades.')

report = '\n'.join(lines)
print(report)

with open('tmp/pnl_output.txt', 'w') as f:
    f.write(report)

conn.close()
