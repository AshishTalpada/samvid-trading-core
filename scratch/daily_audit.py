import sqlite3
import json
from datetime import datetime

db_path = "data/trading.db"

def audit():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        
        if "trades" in tables:
            # Query trades for today
            today = datetime.now().strftime("%Y-%m-%d")
            # Using net_pnl as the ultimate truth
            query = """
                SELECT instrument, outcome, shares, entry_price, exit_price, net_pnl, timestamp, trading_mode, direction 
                FROM trades 
                WHERE timestamp LIKE ? 
                ORDER BY timestamp DESC
            """
            cursor.execute(query, (f"{today}%",))
            trades = cursor.fetchall()
            
            print(f"--- TODAY'S TRADES ({today}) ---")
            total_pnl = 0.0
            wins = 0
            losses = 0
            
            for t in trades:
                symbol, outcome, qty, entry, exit, pnl, time, mode, side = t
                total_pnl += (float(pnl) if pnl else 0.0)
                if outcome == "WIN" or (pnl and float(pnl) > 0): wins += 1
                elif outcome == "LOSS" or (pnl and float(pnl) < 0): losses += 1
                
                status = "✅ WIN" if (outcome == "WIN" or (pnl and float(pnl) > 0)) else "❌ LOSS" if (outcome == "LOSS" or (pnl and float(pnl) < 0)) else "⚪ EVEN"
                print(f"[{time}] {symbol} ({side} {qty} @ {entry} -> {exit}): {status} | Net PnL: ${pnl:+.2f} ({mode})")
            
            wr = (wins / len(trades) * 100) if trades else 0
            print(f"\nSUMMARY:")
            print(f"Total Trades: {len(trades)}")
            print(f"Win Rate: {wr:.1f}%")
            print(f"Daily Net PnL: ${total_pnl:+.2f}")
        else:
            print("No 'trades' table found.")
            
        conn.close()
    except Exception as e:
        print(f"Audit Error: {e}")

if __name__ == "__main__":
    audit()
