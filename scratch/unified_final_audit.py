import sqlite3
import os

def final_audit():
    dbs = {
        "Main Paper/Live": "data/trading.db",
        "Deep Stress/Agent D": "data/trading_stress.db"
    }
    
    print("=" * 125)
    print(f"{'DATABASE':<20} | {'SYM':<8} | {'ENTRY':<8} | {'EXIT':<8} | {'PNL ($)':<10} | {'STATUS':<6} | {'TIME'}")
    print("-" * 125)

    # 1. Check Main DB (Current Active Trades)
    if os.path.exists(dbs["Main Paper/Live"]):
        conn = sqlite3.connect(dbs["Main Paper/Live"])
        cursor = conn.cursor()
        cursor.execute("SELECT instrument, entry_price, exit_price, pnl_dollars, outcome, timestamp FROM trades ORDER BY timestamp DESC LIMIT 15")
        for r in cursor.fetchall():
            sym, ent, ext, pnl, out, ts = r
            pnl_v = f"{pnl:+.2f}" if pnl is not None else "0.00"
            ext_v = f"{ext:.2f}" if ext else "0.00"
            print(f"{'Main Trading':<20} | {sym:<8} | {ent:<8.2f} | {ext_v:<8} | {pnl_v:<10} | {out:<6} | {ts[:19]}")
        conn.close()

    # 2. Check Stress DB (Deep Historical Results)
    if os.path.exists(dbs["Deep Stress/Agent D"]):
        conn = sqlite3.connect(dbs["Deep Stress/Agent D"])
        cursor = conn.cursor()
        # Using verified columns: symbol, outcome, pnl, recorded_at
        cursor.execute("SELECT symbol, pnl, outcome, recorded_at FROM agent_d_trades WHERE pnl != 0 ORDER BY recorded_at DESC LIMIT 15")
        for r in cursor.fetchall():
            sym, pnl, out, ts = r
            # Since stress DB doesn't have entry/exit price columns (verified earlier), we show the result.
            print(f"{'Deep History':<20} | {sym:<8} | {'DATA':<8} | {'RESULTS':<8} | {pnl:+.2f} | {out:<6} | {ts[:19]}")
        conn.close()

    print("=" * 125)

if __name__ == "__main__":
    final_audit()
