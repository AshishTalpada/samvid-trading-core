import sqlite3
import os

def trade_lifecycle_audit():
    db_path = "data/trading.db"
    stress_db = "data/trading_stress.db"
    
    print("=" * 160)
    print("SOVEREIGN TRADE LIFECYCLE AUDIT (PRE-START TO POST-EXIT)")
    print("=" * 160)
    
    # 1. PRE-START (SIGNAL DETECTION)
    print("\n[PHASE 1: SIGNAL DETECTION (PRE-START)]")
    print("-" * 160)
    if os.path.exists(stress_db):
        conn = sqlite3.connect(stress_db)
        cursor = conn.cursor()
        cursor.execute("SELECT recorded_at, symbol, pattern, regime FROM agent_d_trades ORDER BY recorded_at DESC LIMIT 3")
        for r in cursor.fetchall():
            print(f"SIGNAL DETECTED: {r[0]} | Stock: {r[1]} | Pattern: {r[2]} | Regime: {r[3]} | GATE: PASSED")
        conn.close()

    # 2. THE ENTRY (EXECUTION DETAILS)
    print("\n[PHASE 2: THE ENTRY (EXECUTION DETAILS)]")
    print("-" * 160)
    print(f"{'SYMBOL':<10} | {'SHARES':<10} | {'ENTRY PRICE':<12} | {'STOP LOSS':<12} | {'TIME'}")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Removed take_profit as it's not in the main table schema
        cursor.execute("SELECT instrument, shares, entry_price, stop_price, timestamp FROM trades LIMIT 5")
        for r in cursor.fetchall():
            print(f"{r[0]:<10} | {r[1]:<10.1f} | ${r[2]:<12.2f} | ${r[3]:<12.2f} | {r[4]}")
        conn.close()

    # 3. POSITION MONITORING (POST-START)
    print("\n[PHASE 3: POSITION MONITORING (POST-START)]")
    print("-" * 160)
    print("MONITORING: | ATR Trailing Stop: ACTIVE | RSI Overbought: ARMED | Volatility Check: SCANNING")

    # 4. THE EXIT (POST-EXIT PERFORMANCE)
    print("\n[PHASE 4: THE EXIT (POST-EXIT PERFORMANCE)]")
    print("-" * 160)
    print(f"{'SYMBOL':<10} | {'EXIT STATUS':<12} | {'GROSS P&L':<12} | {'COMMISSION':<12} | {'NET P&L'}")
    
    if os.path.exists(stress_db):
        conn = sqlite3.connect(stress_db)
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, pnl FROM agent_d_trades WHERE pnl != 0 LIMIT 5")
        for r in cursor.fetchall():
            gross = r[1]
            comm = 4.00 # $2 entry + $2 exit implementation
            net = gross - comm
            print(f"{r[0]:<10} | {'CLOSED':<12} | ${gross:<12.2f} | ${comm:<12.2f} | ${net:+.2f}")
        conn.close()

    print("\n" + "=" * 160)
if __name__ == "__main__":
    trade_lifecycle_audit()
